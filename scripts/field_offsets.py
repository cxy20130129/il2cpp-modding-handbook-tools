#!/usr/bin/env python3
"""Extract field offset tables for a type from an Il2CppDumper dump.cs.

Il2CppDumper annotates instance fields with their byte offset:

    public float totalDurationSeconds; // 0x20

This tool turns those annotations into a readable table so you can see the
runtime layout without opening a hex editor. It reuses the parser in
``find_type.py`` and therefore inherits its tolerance for odd dump formatting.

Caveats, in order of importance:

* Offsets are **relative to the start of the object**, including the base
  class part. A field declared in a derived class can sit at 0x58 even if the
  class itself only declares three fields.
* ``static`` fields are reported with their own marker. Their offsets come
  from the static storage area, not from an object instance, and the ``delta``
  column is meaningless for them.
* ``delta`` is the difference between two consecutive offsets. It is **not**
  the field size -- padding and alignment are included. Use it to spot gaps,
  not to compute sizeof(T).
* Properties are skipped. A property's ``// 0x28`` is the backing field's
  offset; the property itself has no storage.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
from dataclasses import dataclass, field as dc_field
from pathlib import Path

from find_type import _match_text, iter_types

OFFSET_RE = re.compile(r"//\s*(?:0x)?([0-9A-Fa-f]+)\b")
FIELD_LINE_RE = re.compile(
    r"^\s*(?P<mods>(?:(?:public|private|protected|internal|static|readonly|"
    r"const|volatile|new|unsafe)\s+)*)"
    r"(?P<type>[^;=]+?)\s+"
    r"(?P<name><[^>]+>|[A-Za-z_@]\w*)\s*(?:=[^;]*)?;"
)
STATIC_RE = re.compile(r"\bstatic\b")
MODS = (
    "public",
    "private",
    "protected",
    "internal",
    "static",
    "readonly",
    "const",
    "volatile",
    "new",
    "unsafe",
)


@dataclass
class FieldEntry:
    name: str
    field_type: str
    offset: int | None
    is_static: bool
    is_const: bool
    signature: str
    line_no: int
    modifiers: list[str] = dc_field(default_factory=list)
    delta: int | None = None

    @property
    def has_instance_storage(self) -> bool:
        return not (self.is_static or self.is_const)

    @property
    def storage_text(self) -> str:
        if self.is_const:
            return "const"
        if self.is_static:
            return "static"
        return ""

    @property
    def offset_text(self) -> str:
        if self.offset is None:
            return "-"
        return f"0x{self.offset:X}"

    @property
    def delta_text(self) -> str:
        if self.offset is None or self.delta is None:
            return "-"
        return f"0x{self.delta:X}"


@dataclass
class TypeFields:
    full_name: str
    line_no: int
    typedef_index: str | None
    fields: list[FieldEntry]


def parse_field(line: str, line_no: int) -> FieldEntry | None:
    """Parse one field line. Return None when the line is not a field."""
    match = FIELD_LINE_RE.match(line)
    if not match:
        return None

    mods_text = match.group("mods")
    modifiers = [m for m in MODS if re.search(rf"\b{m}\b", mods_text)]
    offset_match = OFFSET_RE.search(line)
    offset = int(offset_match.group(1), 16) if offset_match else None

    return FieldEntry(
        name=match.group("name"),
        field_type=match.group("type").strip(),
        offset=offset,
        is_static=bool(STATIC_RE.search(mods_text)),
        is_const="const" in modifiers,
        signature=line.strip(),
        line_no=line_no,
        modifiers=modifiers,
    )


def compute_deltas(entries: list[FieldEntry]) -> None:
    """Fill ``delta`` with the gap to the previous instance-field offset."""
    previous: int | None = None
    for entry in sorted(
        (e for e in entries if e.has_instance_storage and e.offset is not None),
        key=lambda e: e.offset,  # type: ignore[arg-type]
    ):
        if previous is not None:
            entry.delta = entry.offset - previous  # type: ignore[operator]
        previous = entry.offset


def extract_fields(
    path: Path,
    query: str,
    use_regex: bool = False,
    case_sensitive: bool = False,
    limit: int = 0,
) -> list[TypeFields]:
    """Find types matching ``query`` and return their field layout tables."""
    results: list[TypeFields] = []
    with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
        for ctx in iter_types(handle):
            if not _match_text(ctx.full_name, query, use_regex, case_sensitive):
                continue
            entries: list[FieldEntry] = []
            for member in ctx.members:
                if member.kind != "field":
                    continue
                parsed = parse_field(member.signature, member.line_no)
                if parsed:
                    entries.append(parsed)
            compute_deltas(entries)
            entries.sort(
                key=lambda e: (not e.has_instance_storage, e.offset is None, e.offset or 0)
            )
            results.append(
                TypeFields(
                    full_name=ctx.full_name,
                    line_no=ctx.line_no,
                    typedef_index=ctx.typedef_index,
                    fields=entries,
                )
            )
    results.sort(key=lambda item: item.line_no)
    return results[:limit] if limit else results


def _field_rows(item: TypeFields) -> list[list[str]]:
    return [
        [
            entry.offset_text,
            entry.delta_text if entry.has_instance_storage else "",
            entry.storage_text,
            entry.field_type,
            entry.name,
            str(entry.line_no),
        ]
        for entry in item.fields
    ]


def format_text(tables: list[TypeFields], source: str) -> str:
    if not tables:
        return "no matching types"
    lines: list[str] = []
    for item in tables:
        typedef = f"  typedef={item.typedef_index}" if item.typedef_index else ""
        lines.append(f"{item.full_name}  ({source}:{item.line_no}){typedef}")
        if not item.fields:
            lines.append("  (no fields)")
            continue
        rows = _field_rows(item)
        headers = ["offset", "delta", "kind", "type", "name", "line"]
        widths = [max(len(h), *(len(r[i]) for r in rows)) for i, h in enumerate(headers)]
        lines.append("  " + "  ".join(h.ljust(w) for h, w in zip(headers, widths)))
        for row in rows:
            lines.append("  " + "  ".join(c.ljust(w) for c, w in zip(row, widths)))
        lines.append("")
    return "\n".join(lines).rstrip()


def format_markdown(tables: list[TypeFields], source: str) -> str:
    if not tables:
        return "No matching types."
    lines: list[str] = []
    for item in tables:
        typedef = f" · TypeDefIndex {item.typedef_index}" if item.typedef_index else ""
        lines.append(f"### `{item.full_name}`{typedef}")
        lines.append("")
        lines.append(f"来源：`{source}:{item.line_no}`")
        lines.append("")
        if not item.fields:
            lines.append("（无字段）")
            lines.append("")
            continue
        lines.append("| 偏移 | 增量 | 类型 | 存储 | 字段 | 行号 |")
        lines.append("|---|---|---|---|---|---|")
        for entry in item.fields:
            storage = {"": "实例", "static": "静态", "const": "常量"}[entry.storage_text]
            lines.append(
                f"| `{entry.offset_text}` | `{entry.delta_text}` | "
                f"`{entry.field_type}` | {storage} | `{entry.name}` | "
                f"{entry.line_no} |"
            )
        lines.append("")
    return "\n".join(lines).rstrip()


def format_json(tables: list[TypeFields], source: str, query: str) -> str:
    payload = {
        "source": source,
        "query": query,
        "count": len(tables),
        "types": [
            {
                "name": item.full_name,
                "line": item.line_no,
                "typedef_index": item.typedef_index,
                "fields": [
                    {
                        "name": entry.name,
                        "type": entry.field_type,
                        "offset": entry.offset,
                        "delta": entry.delta,
                        "static": entry.is_static,
                        "const": entry.is_const,
                        "modifiers": entry.modifiers,
                        "line": entry.line_no,
                    }
                    for entry in item.fields
                ],
            }
            for item in tables
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def format_csv(tables: list[TypeFields]) -> str:
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        ["type", "typedef_index", "offset", "delta", "static", "const", "type_of_field", "name", "line"]
    )
    for item in tables:
        for entry in item.fields:
            writer.writerow(
                [
                    item.full_name,
                    item.typedef_index or "",
                    entry.offset_text,
                    entry.delta_text if entry.has_instance_storage else "",
                    "1" if entry.is_static else "0",
                    "1" if entry.is_const else "0",
                    entry.field_type,
                    entry.name,
                    entry.line_no,
                ]
            )
    return output.getvalue().rstrip()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract field offsets for a type from an Il2CppDumper dump.cs.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("dump", type=Path, help="path to dump.cs")
    parser.add_argument("query", help="type name, or regex with --regex")
    parser.add_argument("--regex", action="store_true", help="treat query as a regex")
    parser.add_argument(
        "--case-sensitive", action="store_true", help="case sensitive matching"
    )
    parser.add_argument(
        "--format",
        choices=("text", "markdown", "json", "csv"),
        default="text",
        help="output format",
    )
    parser.add_argument("--limit", type=int, default=20, help="0 means unlimited")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.dump.is_file():
        print(f"error: dump file not found: {args.dump}", file=sys.stderr)
        return 2
    tables = extract_fields(
        args.dump,
        args.query,
        use_regex=args.regex,
        case_sensitive=args.case_sensitive,
        limit=args.limit,
    )
    if args.format == "json":
        print(format_json(tables, str(args.dump), args.query))
    elif args.format == "csv":
        print(format_csv(tables))
    elif args.format == "markdown":
        print(format_markdown(tables, args.dump.name))
    else:
        print(format_text(tables, args.dump.name))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
