#!/usr/bin/env python3
"""Search an Il2CppDumper dump.cs for types, methods, fields and properties.

Designed for the standard dump.cs produced by Il2CppDumper:
  // Namespace: IronNest.UI
  public class TelegraphPanel : MonoBehaviour // TypeDefIndex: 1187
  {
      public void SetText(string text) { } // RVA: 0x1A2B3C0 Offset: ...
  }

The parser is line based and deliberately forgiving. It does not evaluate C#.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator

TYPE_HEADER_RE = re.compile(
    r"^\s*(?:(?:public|internal|private|protected|static|sealed|abstract|partial|unsafe|new)\s+)*"
    r"(?P<kind>class|struct|interface|enum)\s+(?P<name>[^\s:{]+)"
)
TYPEDEF_INDEX_RE = re.compile(r"//\s*TypeDefIndex:\s*(\d+)")
NAMESPACE_RE = re.compile(r"^\s*//\s*Namespace:\s*(?P<ns>.+?)\s*$")
METHOD_NAME_RE = re.compile(r"([A-Za-z_@]\w*(?:<[^>]*>)?)\s*\(")
FIELD_NAME_RE = re.compile(r"([A-Za-z_@]\w*)\s*(?:=[^;]*)?;")
PROPERTY_NAME_RE = re.compile(r"([A-Za-z_@]\w*)\s*\{\s*(?:get|set)")

MEMBER_KINDS = ("method", "field", "property")


@dataclass
class TypeContext:
    kind: str
    name: str
    full_name: str
    header: str
    line_no: int
    depth: int
    typedef_index: str | None = None
    opened: bool = False
    members: list["Member"] = field(default_factory=list)


@dataclass
class Member:
    kind: str
    name: str
    signature: str
    line_no: int
    type_ctx: TypeContext


@dataclass
class Match:
    kind: str
    name: str
    signature: str
    line_no: int
    type_ctx: TypeContext


def _match_text(text: str, query: str, use_regex: bool, case_sensitive: bool) -> bool:
    if use_regex:
        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            return re.search(query, text, flags) is not None
        except re.error as exc:
            raise SystemExit(f"invalid regex {query!r}: {exc}") from exc
    if case_sensitive:
        return query in text
    return query.lower() in text.lower()


def _class_matches(ctx: TypeContext, query: str, use_regex: bool, case_sensitive: bool) -> bool:
    return _match_text(ctx.full_name, query, use_regex, case_sensitive) or _match_text(
        ctx.name, query, use_regex, case_sensitive
    )


def _member_name(kind: str, line: str) -> str | None:
    match: re.Match[str] | None
    if kind == "method":
        match = METHOD_NAME_RE.search(line)
    elif kind == "field":
        match = FIELD_NAME_RE.search(line)
    else:
        match = PROPERTY_NAME_RE.search(line)
    return match.group(1) if match else None


def classify_member(line: str) -> str | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("//"):
        return None
    if "// RVA:" in line and "(" in line:
        return "method"
    if "// 0x" in line and ";" in line:
        return "field"
    if re.search(r"\{\s*(?:get|set)", line):
        return "property"
    return None


def iter_types(lines: Iterable[str]) -> Iterator[TypeContext]:
    """Yield every type with its members, in closing order (nested types first).

    A type is yielded only after its closing brace, so ``ctx.members`` is complete
    by the time the caller sees it. Callers that need source order should sort by
    ``line_no``.
    """
    stack: list[TypeContext] = []
    pending_namespace = ""
    depth = 0

    for line_no, raw in enumerate(lines, 1):
        line = raw.rstrip("\n")

        ns_match = NAMESPACE_RE.match(line)
        if ns_match:
            pending_namespace = ns_match.group("ns").strip()
            continue

        header_match = TYPE_HEADER_RE.match(line)
        if header_match:
            name = header_match.group("name").rstrip("{").strip()
            if stack:
                full_name = f"{stack[-1].full_name}.{name}"
            elif pending_namespace:
                full_name = f"{pending_namespace}.{name}"
            else:
                full_name = name
            typedef = TYPEDEF_INDEX_RE.search(line)
            ctx = TypeContext(
                kind=header_match.group("kind"),
                name=name,
                full_name=full_name,
                header=line.strip(),
                line_no=line_no,
                depth=depth,
                typedef_index=typedef.group(1) if typedef else None,
                opened="{" in line,
            )
            stack.append(ctx)
            pending_namespace = ""

        if stack:
            member_kind = classify_member(line)
            if member_kind:
                member_name = _member_name(member_kind, line)
                if member_name:
                    stack[-1].members.append(
                        Member(
                            kind=member_kind,
                            name=member_name,
                            signature=line.strip(),
                            line_no=line_no,
                            type_ctx=stack[-1],
                        )
                    )

        depth += line.count("{") - line.count("}")
        if stack and "{" in line:
            stack[-1].opened = True
        while stack and stack[-1].opened and depth <= stack[-1].depth:
            yield stack.pop()

    while stack:
        yield stack.pop()


def find_matches(
    path: Path,
    query: str,
    kind: str = "all",
    use_regex: bool = False,
    case_sensitive: bool = False,
    limit: int = 50,
) -> list[Match]:
    results: list[Match] = []
    search_classes = kind in ("all", "class")
    search_members = kind == "all" or kind in MEMBER_KINDS

    with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
        for ctx in iter_types(handle):
            if search_classes and _class_matches(ctx, query, use_regex, case_sensitive):
                results.append(
                    Match(
                        kind="class",
                        name=ctx.full_name,
                        signature=ctx.header,
                        line_no=ctx.line_no,
                        type_ctx=ctx,
                    )
                )
            if search_members:
                for member in ctx.members:
                    if kind not in ("all", member.kind):
                        continue
                    if _match_text(
                        f"{member.name} {member.signature}", query, use_regex, case_sensitive
                    ):
                        results.append(
                            Match(
                                kind=member.kind,
                                name=member.name,
                                signature=member.signature,
                                line_no=member.line_no,
                                type_ctx=ctx,
                            )
                        )

    results.sort(key=lambda item: (item.line_no, 0 if item.kind == "class" else 1))
    if limit:
        return results[:limit]
    return results


def _format_text(matches: list[Match], source_name: str) -> str:
    if not matches:
        return "no matches"
    lines: list[str] = []
    last_type: int | None = None
    for item in matches:
        if item.kind != "class":
            if item.type_ctx.line_no != last_type:
                typedef = (
                    f"  // TypeDefIndex: {item.type_ctx.typedef_index}"
                    if item.type_ctx.typedef_index
                    else ""
                )
                lines.append(
                    f"{item.type_ctx.full_name}  "
                    f"({source_name}:{item.type_ctx.line_no}){typedef}"
                )
                last_type = item.type_ctx.line_no
            lines.append(
                f"  {source_name}:{item.line_no}  [{item.kind}] {item.signature}"
            )
        else:
            lines.append(
                f"{source_name}:{item.line_no}  [class] {item.name}  |  "
                f"{item.signature}"
            )
            last_type = item.type_ctx.line_no
    return "\n".join(lines)


def _format_json(matches: list[Match], source: Path, query: str) -> str:
    payload = {
        "source": str(source),
        "query": query,
        "count": len(matches),
        "matches": [
            {
                "kind": item.kind,
                "name": item.name,
                "signature": item.signature,
                "line": item.line_no,
                "type": item.type_ctx.full_name,
                "type_line": item.type_ctx.line_no,
                "typedef_index": item.type_ctx.typedef_index,
            }
            for item in matches
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Search an Il2CppDumper dump.cs for types and members.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("dump", type=Path, help="path to dump.cs")
    parser.add_argument("query", help="class/method/field name, or regex with --regex")
    parser.add_argument(
        "--kind",
        choices=("all", "class", "method", "field", "property"),
        default="all",
        help="restrict result kind",
    )
    parser.add_argument("--regex", action="store_true", help="treat query as a regex")
    parser.add_argument(
        "--case-sensitive", action="store_true", help="case sensitive matching"
    )
    parser.add_argument("--limit", type=int, default=50, help="0 means unlimited")
    parser.add_argument("--json", action="store_true", help="emit JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.dump.is_file():
        print(f"error: dump file not found: {args.dump}", file=sys.stderr)
        return 2
    matches = find_matches(
        args.dump,
        args.query,
        kind=args.kind,
        use_regex=args.regex,
        case_sensitive=args.case_sensitive,
        limit=args.limit,
    )
    if args.json:
        print(_format_json(matches, args.dump, args.query))
    else:
        print(_format_text(matches, args.dump.name))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
