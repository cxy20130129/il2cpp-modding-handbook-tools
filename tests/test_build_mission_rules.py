from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_mission_rules as b  # noqa: E402

DUMPS = ROOT / "examples" / "iron-nest" / "mission-dumps"


class BuildMissionRulesTests(unittest.TestCase):
    def test_parse_real_dumps(self) -> None:
        base = b.parse_graph(DUMPS / "structure_base.txt")
        new = b.parse_graph(DUMPS / "structure_new.txt")
        self.assertEqual(base.mission_id, "Artillery Introduction")
        self.assertEqual(new.mission_id, "ExtremeCounterBattery")
        self.assertEqual(len(base.nodes), 52)
        self.assertEqual(len(new.nodes), 61)

    def test_multiline_key(self) -> None:
        new = b.parse_graph(DUMPS / "structure_new.txt")
        node = next(n for n in new.nodes if n.index == 6)
        self.assertEqual(node.node_type, "State_TeleprinterText")
        self.assertIn("最高统帅部", node.params["key"])
        self.assertIn("光荣归于卡斯蒂利亚", node.params["key"])
        self.assertEqual(node.out, "43")
        self.assertEqual(node.in_, "50")

    def test_multi_predecessor_node(self) -> None:
        new = b.parse_graph(DUMPS / "structure_new.txt")
        node = next(n for n in new.nodes if n.index == 57)
        self.assertIn("38", node.in_)
        self.assertIn("56", node.in_)

    def test_rules_from_real_dumps(self) -> None:
        base = b.parse_graph(DUMPS / "structure_base.txt")
        new = b.parse_graph(DUMPS / "structure_new.txt")
        rules = b.build_rules(base, new, b.collect_evidence(DUMPS / "result.txt"))
        by_index = {r["index"]: r for r in rules}

        self.assertEqual(by_index[11]["set"], {"InitalTime": "60"})
        self.assertEqual(by_index[11]["was"], {"InitalTime": "300"})
        self.assertEqual(by_index[15]["set"], {"Time": "40"})
        self.assertEqual(by_index[1]["set"], {"NumberToSpawn": "20"})
        self.assertEqual(by_index[4]["set"], {"ID": "EnemyBunker", "NumberToSpawn": "3"})
        self.assertIn("Text.Key", by_index[6]["set"])
        self.assertIn("最高统帅部", by_index[6]["set"]["Text.Key"])

    def test_type_mismatch_skipped(self) -> None:
        # base [30] is TimerAddTime, new [30] is TeleprinterText -- rewired by
        # the plugin. Such nodes must not produce a field rule.
        base = b.parse_graph(DUMPS / "structure_base.txt")
        new = b.parse_graph(DUMPS / "structure_new.txt")
        rules = b.build_rules(base, new, [])
        self.assertNotIn(30, {r["index"] for r in rules})

    def test_cli_writes_document(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "rules.json"
            with contextlib.redirect_stdout(io.StringIO()):
                code = b.main(["--dumps", str(DUMPS), "-o", str(out)])
            self.assertEqual(code, 0)
            doc = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(doc["mission"], "ExtremeCounterBattery")
            self.assertEqual(len(doc["rules"]), 8)
            self.assertEqual(
                doc["enum_values"]["ModifyType"],
                ["Add", "Set", "Subtract", "Reset"],
            )

    def test_mission_name_from_new_graph_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "rules.json"
            with contextlib.redirect_stdout(io.StringIO()):
                b.main(["--dumps", str(DUMPS), "-o", str(out)])
            self.assertEqual(
                json.loads(out.read_text(encoding="utf-8"))["mission"],
                "ExtremeCounterBattery",
            )

    def test_mission_name_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "rules.json"
            with contextlib.redirect_stdout(io.StringIO()):
                code = b.main(["--dumps", str(DUMPS), "--mission", "MyMission", "-o", str(out)])
            self.assertEqual(code, 0)
            self.assertEqual(
                json.loads(out.read_text(encoding="utf-8"))["mission"], "MyMission"
            )

    def test_not_covered_declares_the_200s_gap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "rules.json"
            with contextlib.redirect_stdout(io.StringIO()):
                b.main(["--dumps", str(DUMPS), "-o", str(out)])
            doc = json.loads(out.read_text(encoding="utf-8"))
            gaps = doc["not_covered"]
            timer = [g for g in gaps if g.get("category") == "timer"]
            self.assertTrue(timer)
            self.assertEqual(timer[0]["index"], 60)
            self.assertIn("MISSING", timer[0]["reason"])
            self.assertTrue(any(g.get("category") == "entity" for g in gaps))
            self.assertIn("PARTIAL", doc["note"])

    def test_generation_is_byte_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "first.json"
            second = Path(tmp) / "second.json"
            with contextlib.redirect_stdout(io.StringIO()):
                b.main(["--dumps", str(DUMPS), "-o", str(first)])
                b.main(["--dumps", str(DUMPS), "-o", str(second)])
            self.assertEqual(first.read_bytes(), second.read_bytes())


class CommittedRuleGuardTests(unittest.TestCase):
    """Guard the rule JSON that actually ships in the repo.

    game updates silently invalidate indices and field names. Without these
    checks the generator tests stay green while the committed rules are stale.
    """

    def setUp(self) -> None:
        path = ROOT / "missions" / "extreme-counter-battery.json"
        if not path.is_file():
            self.skipTest("committed rule file not present")
        self.doc = json.loads(path.read_text(encoding="utf-8"))
        self.base = b.parse_graph(DUMPS / "structure_base.txt")
        self.base_text = (DUMPS / "structure_base.txt").read_text(
            encoding="utf-8-sig", errors="replace"
        )

    def test_indices_within_base_graph(self) -> None:
        count = self.doc["base_node_count"]
        self.assertEqual(count, len(self.base.nodes))
        for rule in self.doc["rules"]:
            with self.subTest(index=rule["index"]):
                self.assertGreaterEqual(rule["index"], 0)
                self.assertLess(rule["index"], count)

    def test_field_keys_are_supported(self) -> None:
        supported = set(b.DUMP_KEY_TO_CSHARP.values())
        for rule in self.doc["rules"]:
            for key in rule["set"]:
                with self.subTest(index=rule["index"], key=key):
                    self.assertIn(key, supported)

    def test_node_types_exist_in_base_dump(self) -> None:
        for rule in self.doc["rules"]:
            with self.subTest(index=rule["index"], type=rule["type"]):
                self.assertIn(rule["type"], self.base_text)
                node = next(n for n in self.base.nodes if n.index == rule["index"])
                self.assertEqual(node.node_type, rule["type"])

    def test_committed_file_matches_current_dumps(self) -> None:
        # Strongest guard: regenerate from the committed dumps and compare
        # bytes. Fails on any dump update that has not been reflected in JSON.
        with tempfile.TemporaryDirectory() as tmp:
            regenerated = Path(tmp) / "rules.json"
            with contextlib.redirect_stdout(io.StringIO()):
                b.main(["--dumps", str(DUMPS), "-o", str(regenerated)])
            committed = (ROOT / "missions" / "extreme-counter-battery.json").read_bytes()
            self.assertEqual(committed, regenerated.read_bytes())


if __name__ == "__main__":
    unittest.main()
