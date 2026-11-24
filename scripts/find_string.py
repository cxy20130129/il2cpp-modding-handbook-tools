#!/usr/bin/env python3
"""Search Il2CppDumper stringliteral.json for string literals.

Il2CppDumper writes an array of {"address": "...", "value": "..."} objects.
This tool accepts that shape, a bare list of strings, or {"strings": [...]}.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def load_strings(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
        data = json.load(handle)

    if isinstance(data, dict):
        data = data.get("strings", data.get("values", []))

    if not isinstance(data, list):
        raise SystemExit(f"error: unsupported JSON shape in {path}")

    strings: list[dict[str, str]] = []
    for index, item in enumerate(data):
        if isinstance(item, str):
            strings.append({"index": str(index), "address": "", "value": item})
            continue
        if not isinstance(item, dict):
            continue
        value = item.get("value", item.get("text", item.get("str")))
        if not isinstance(value, str):
            continue
        strings.append(
            {
                "index": str(item.get("index", index)),
                "address": str(item.get("address", "")),
                "value": value,
            }
        )
    return strings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Search stringliteral.json produced by Il2CppDumper.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("json_file", type=Path, help="path to stringliteral.json")
    parser.add_argument("query", help="substring, or regex with --regex")
    parser.add_argument("--regex", action="store_true", help="treat query as a regex")
    parser.add_argument(
        "--exact", action="store_true", help="require the whole string to match"
    )
    parser.add_argument(
        "--case-sensitive", action="store_true", help="case sensitive matching"
    )
    parser.add_argument("--limit", type=int, default=50, help="0 means unlimited")
    parser.add_argument("--json", action="store_true", help="emit JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.json_file.is_file():
        print(f"error: file not found: {args.json_file}", file=sys.stderr)
        return 2

    strings = load_strings(args.json_file)
    flags = 0 if args.case_sensitive else re.IGNORECASE
    if args.regex:
        try:
            pattern = re.compile(args.query, flags)
        except re.error as exc:
            print(f"error: invalid regex {args.query!r}: {exc}", file=sys.stderr)
            return 2
    else:
        needle = args.query if args.case_sensitive else args.query.lower()

    hits: list[dict[str, str]] = []
    for item in strings:
        value = item["value"]
        if args.regex:
            matched = pattern.search(value) is not None
        elif args.exact:
            matched = value == args.query if args.case_sensitive else value.lower() == needle
        else:
            matched = args.query in value if args.case_sensitive else needle in value.lower()
        if matched:
            hits.append(item)
            if args.limit and len(hits) >= args.limit:
                break

    if args.json:
        print(
            json.dumps(
                {
                    "source": str(args.json_file),
                    "query": args.query,
                    "count": len(hits),
                    "matches": hits,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if not hits:
        print("no matches")
        return 0

    for item in hits:
        address = f" {item['address']}" if item["address"] else ""
        escaped = json.dumps(item["value"], ensure_ascii=False)
        print(f"[{item['index']:>6}]{address}  {escaped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
