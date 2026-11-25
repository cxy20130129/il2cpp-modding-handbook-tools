#!/usr/bin/env python3
"""Turn the three Iron Nest mission dumps into a machine-readable patch rule file.

Input:
  structure_base.txt   base mission graph, printed by the mission-build plugin
  structure_new.txt    the built "Extreme Counter Battery" graph
  result.txt           the plugin's own line-by-line change log

Output (default missions/extreme-counter-battery.json):
  {
    "mission": "ExtremeCounterBattery",
    "base_graph": "Artillery Introduction",
    "rules": [
      {"index": 11, "type": "State_StartTimer", "set": {"InitalTime": 60},
       "was": {"InitalTime": 300}, "evidence": ["StartTimer before=300", "StartTimer -> 60"]}
    ]
  }

``index`` is the node index in the BASE graph, because the BepInEx patch runs on
the freshly instantiated base mission before the custom build plugin adds nodes.
The node type is always checked at runtime; a mismatch is logged and skipped.

Only scalar fields with a verified C# field name (from dump.cs) are emitted.
Graph rewiring, node insertion and entity visual changes are NOT expressed as
rules -- those remain plugin work. See docs/mission-rules.md.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field as dc_field
from pathlib import Path

# dump.cs field names. Keep in sync with docs/mission-rules.md.
DUMP_KEY_TO_CSHARP: dict[str, str] = {
    "id": "ID",
    "num": "NumberToSpawn",
    "init": "InitalTime",
    "time": "Time",
    "mod": "ModifyType",
    "key": "Text.Key",
    "sec": "InitialSeconds",
    "timer": "TimerID",
}

# Enum legal values, from dump.cs:62746 (State_TimerAddTime.ModifyTypes).
# Keep as strings for the C# side to parse with Enum.Parse.
ENUM_VALUES: dict[str, list[str]] = {
    "ModifyType": ["Add", "Set", "Subtract", "Reset"],
}

NODE_RE = re.compile(
    r"^\[(\d+)\]\s+Node(?:\s+name='(?P<name>.*?)')?(?P<params>.*?)"
    r"\s*\|\s*out:\s*(?P<out>[^|]*?)\s+in:\s*(?P<in>[\d\s-]+?)\s*$",
    re.DOTALL,
)
PARAM_RE = re.compile(r"(?P<key>[A-Za-z][A-Za-z0-9_]*)\s*=\s*(?P<value>'(?:[^']|'')*'|[^\s]+)")
EVIDENCE_RE = re.compile(r"(StartTimer|TimerAdd|spawn\[\d+\]|intro replaced|alert replaced|teleprinters=|iron nest|zones|progression|win chain)")


@dataclass
class GraphNode:
    index: int
    name: str
    node_type: str
    params: dict[str, str]
    out: str
    in_: str
    line_no: int


@dataclass
class Graph:
    mission_id: str
    nodes: list[GraphNode] = dc_field(default_factory=list)


def _clean_node_name(name: str) -> str:
    """Strip the Unity (Clone) suffix left by Instantiate."""
    return name.removesuffix("(Clone)")


def parse_graph(path: Path) -> Graph:
    """Parse a structure_*.txt dump, including multi-line key='...' values."""
    mission_id = ""
    nodes: list[GraphNode] = []
    pending: dict[str, object] | None = None
    key_buffer: list[str] = []

    lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1

        if pending is not None:
            # Continuation of a multi-line key='...' value. Assemble the node
            # directly instead of round-tripping through the line regex: the
            # key itself contains quotes, which confuse a generic parser.
            if "' | out:" in line:
                tail = line.rsplit("' | out:", 1)
                key_buffer.append(tail[0])
                edge = re.match(r"\s*(\S+)\s+in:\s*(\S+)\s*$", tail[1])
                if edge:
                    nodes.append(
                        GraphNode(
                            index=int(pending["index"]),
                            name=str(pending["name"]),
                            node_type=str(pending["name"]).split(" ", 1)[0],
                            params={"key": "\n".join(key_buffer)},
                            out=edge.group(1),
                            in_=edge.group(2),
                            line_no=int(pending["line_no"]),
                        )
                    )
                pending = None
                key_buffer = []
                continue
            key_buffer.append(line)
            continue

        header = re.match(r"^graph id=(.+?)\s+nodes=(\d+)", line)
        if header:
            mission_id = header.group(1)
            continue

        # Multi-line key='...' starts with a node line that has no "| out:"
        # yet. Detect it before the full-node regex, which requires the edges.
        multiline = re.match(
            r"^\[(\d+)\]\s+Node\s+name='(?P<name>[^']+)'\s+key='(?P<key>.*)$", line
        )
        if multiline and "| out:" not in line:
            pending = {
                "index": int(multiline.group(1)),
                "name": _clean_node_name(multiline.group("name")),
                "line_no": i,
            }
            key_buffer = [multiline.group("key")]
            continue

        match = NODE_RE.match(line)
        if not match:
            continue
        node = _parse_single_node(line, i)
        if node:
            nodes.append(node)

    return Graph(mission_id=mission_id, nodes=nodes)


def _parse_single_node(line: str, line_no: int) -> GraphNode | None:
    match = NODE_RE.match(line)
    if not match:
        return None
    name = _clean_node_name(match.group("name") or "")
    params_text = match.group("params")
    params: dict[str, str] = {}
    for param in PARAM_RE.finditer(params_text):
        raw = param.group("value")
        value = raw[1:-1].replace("''", "'") if raw.startswith("'") else raw
        params[param.group("key")] = value
    node_type = name.split(" ", 1)[0] if name else "Node"
    return GraphNode(
        index=int(match.group(1)),
        name=name,
        node_type=node_type,
        params=params,
        out=match.group("out"),
        in_=match.group("in"),
        line_no=line_no,
    )


def collect_evidence(path: Path) -> list[str]:
    """Pull the plugin's own change log lines into rule evidence."""
    if not path.is_file():
        return []
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
        if EVIDENCE_RE.search(line)
    ]


def build_rules(base: Graph, new: Graph, evidence: list[str]) -> list[dict[str, object]]:
    """Diff base vs new by node index; emit only fields we can safely patch."""
    new_by_index = {node.index: node for node in new.nodes}
    rules: list[dict[str, object]] = []

    for node in base.nodes:
        target = new_by_index.get(node.index)
        if target is None:
            continue
        # Node identity must match; (Clone) is stripped, but a reused index with
        # a different node type means the graphs diverged too much to patch.
        if target.node_type != node.node_type:
            continue

        changes: dict[str, str] = {}
        previous: dict[str, str] = {}
        for dump_key, csharp_key in DUMP_KEY_TO_CSHARP.items():
            before = node.params.get(dump_key)
            after = target.params.get(dump_key)
            if after is None or before == after:
                continue
            changes[csharp_key] = after
            if before is not None:
                previous[csharp_key] = before

        if not changes:
            continue

        node_evidence = [
            line for line in evidence
            if (
                (node.node_type == "State_StartTimer" and "StartTimer" in line)
                or (node.node_type == "State_TimerAddTime" and "TimerAdd" in line)
                or (node.node_type == "State_SpawnMapEntity" and "spawn[" in line)
                or (node.node_type == "State_TeleprinterText" and ("replaced" in line or "teleprinters=" in line))
            )
        ][:6]

        rules.append(
            {
                "index": node.index,
                "type": node.node_type,
                "set": changes,
                "was": previous,
                "evidence": node_evidence,
                "source_line": node.line_no,
            }
        )

    return rules


def find_not_covered(
    base: Graph, new: Graph, rules: list[dict[str, object]], evidence: list[str]
) -> list[dict[str, object]]:
    """List functional changes the scalar rule format cannot express.

    Only report things a mission author would actually miss. Plain index
    renumbering from plugin node insertion is not a functional gap, so it is
    intentionally left out; see docs/mission-rules.md for the full boundary.

    Sources:
      * result.txt log lines naming a change with no matching rule
      * target nodes with timer/spawn parameters at indices absent from base
    """
    base_by_index = {node.index: node for node in base.nodes}
    new_by_index = {node.index: node for node in new.nodes}
    result: list[dict[str, object]] = []

    # Functional gaps stated in the plugin's own log. Each of these is a real
    # behaviour change that the 8 scalar rules do not apply.
    gap_patterns = [
        # The +200s bonus is reported from the graph side below, with its index.
        ("iron nest via CopyNode", "enemy iron nest entity insertion", "entity"),
        ("removed TimerAdd(Set 500)", "Deletion of the base graph's Set(500) node", "graph"),
        ("printer: intro=", "teleprinter priority/replacement configuration", "graph"),
        ("win chain:", "win condition chain rewiring", "graph"),
        ("mission wired:", "campaign progression wiring", "graph"),
    ]
    for needle, description, category in gap_patterns:
        matches = [line.strip() for line in evidence if needle in line]
        if matches:
            result.append(
                {
                    "change": description,
                    "category": category,
                    "evidence": matches[:2],
                    "reason": (
                        "requires inserting/removing nodes or rewiring edges; "
                        "the rule format only edits scalar fields on existing nodes"
                    ),
                }
            )

    # A target-only node carrying timer params is the same +200s gap seen from
    # the graph side. Keep it as a cross-check with an explicit index.
    for index in sorted(set(new_by_index) - set(base_by_index)):
        node = new_by_index[index]
        if "time" not in node.params and "mod" not in node.params:
            continue
        result.insert(
            0,
            {
                "index": index,
                "change": "second +200s add-time bonus (Target node, not State_TimerAddTime)",
                "category": "timer",
                "params": ", ".join(f"{k}={v}" for k, v in node.params.items()),
                "reason": (
                    "inserted node; the patch cannot create it, so this add-time "
                    "step is MISSING after applying the JSON rules"
                ),
                "source_line": node.line_no,
            },
        )
        break

    return result


def build_document(
    base: Graph,
    new: Graph,
    rules: list[dict[str, object]],
    evidence: list[str],
    mission_name: str,
) -> dict[str, object]:
    not_covered = find_not_covered(base, new, rules, evidence)
    return {
        "mission": mission_name,
        "base_graph": base.mission_id,
        "target_graph": new.mission_id,
        "base_node_count": len(base.nodes),
        "target_node_count": len(new.nodes),
        "note": (
            "index is the base graph's node index. Node type is verified at runtime. "
            "This is a PARTIAL patch: see not_covered for changes the rule format "
            "cannot express. It is not a full replica of the target mission."
        ),
        "enum_values": ENUM_VALUES,
        "rules": rules,
        "not_covered": not_covered,
        "build_log_evidence": evidence[:40],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build mission patch rules from the three Iron Nest mission dumps.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--dumps", type=Path, default=Path("examples/iron-nest/mission-dumps"))
    parser.add_argument("--base", type=Path, default=None, help="override structure_base.txt")
    parser.add_argument("--new", type=Path, default=None, help="override structure_new.txt")
    parser.add_argument("--result", type=Path, default=None, help="override result.txt")
    parser.add_argument(
        "--mission", default=None,
        help="mission name for the generated JSON (default: graph id from --new)",
    )
    parser.add_argument(
        "-o", "--out", type=Path,
        default=Path("missions/extreme-counter-battery.json"),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    base_path = args.base or args.dumps / "structure_base.txt"
    new_path = args.new or args.dumps / "structure_new.txt"
    result_path = args.result or args.dumps / "result.txt"

    for path in (base_path, new_path):
        if not path.is_file():
            print(f"error: dump not found: {path}", file=sys.stderr)
            return 2

    base = parse_graph(base_path)
    new = parse_graph(new_path)
    if not base.nodes or not new.nodes:
        print("error: could not parse any nodes from the dumps", file=sys.stderr)
        return 2

    mission_name = args.mission or new.mission_id
    if not mission_name:
        print("error: could not derive mission name from --new; pass --mission", file=sys.stderr)
        return 2

    rules = build_rules(base, new, collect_evidence(result_path))
    document = build_document(base, new, rules, collect_evidence(result_path), mission_name)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {args.out}: {len(rules)} rules "
          f"(base nodes={len(base.nodes)}, target nodes={len(new.nodes)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
