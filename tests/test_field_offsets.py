from __future__ import annotations

import csv
import io
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import field_offsets  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "dump.sample.cs"


class FieldOffsetsTests(unittest.TestCase):
    def test_extract_instance_fields(self) -> None:
        tables = field_offsets.extract_fields(FIXTURE, "LayoutProbe")
        self.assertEqual(len(tables), 1)
        table = tables[0]
        self.assertEqual(table.full_name, "IronNest.Gameplay.LayoutProbe")
        by_name = {entry.name: entry for entry in table.fields}
        self.assertEqual(by_name["flag"].offset, 0x18)
        self.assertEqual(by_name["count"].offset, 0x1C)
        self.assertEqual(by_name["weight"].field_type, "double")
        self.assertEqual(by_name["samples"].field_type, "List<float>")

    def test_static_and_const_excluded_from_delta(self) -> None:
        tables = field_offsets.extract_fields(FIXTURE, "LayoutProbe")
        by_name = {e.name: e for e in tables[0].fields}
        self.assertTrue(by_name["Instance"].is_static)
        self.assertTrue(by_name["MAX"].is_const)
        self.assertIsNone(by_name["Instance"].delta)
        self.assertIsNone(by_name["MAX"].delta)
        # The first instance field has no predecessor; later ones are contiguous.
        self.assertIsNone(by_name["flag"].delta)
        self.assertEqual(by_name["count"].delta, 0x4)
        self.assertEqual(by_name["weight"].delta, 0x8)

    def test_fields_without_offset_annotation_are_skipped(self) -> None:
        # find_type.classify_member only treats "// 0x.." lines as fields.
        tables = field_offsets.extract_fields(FIXTURE, "LayoutProbe")
        names = {e.name for e in tables[0].fields}
        self.assertNotIn("noOffset", names)

    def test_property_not_treated_as_field(self) -> None:
        tables = field_offsets.extract_fields(FIXTURE, "LayoutProbe")
        names = {e.name for e in tables[0].fields}
        self.assertNotIn("PageIndex", names)

    def test_modifiers(self) -> None:
        tables = field_offsets.extract_fields(FIXTURE, "LayoutProbe")
        by_name = {e.name: e for e in tables[0].fields}
        self.assertIn("readonly", by_name["weight"].modifiers)
        self.assertIn("internal", by_name["weight"].modifiers)

    def test_regex_and_limit(self) -> None:
        tables = field_offsets.extract_fields(FIXTURE, r"^IronNest\..*Timer$", use_regex=True)
        names = {item.full_name for item in tables}
        self.assertIn("IronNest.Gameplay.ArtilleryTimer", names)
        self.assertEqual(len(field_offsets.extract_fields(FIXTURE, ".*", use_regex=True, limit=1)), 1)

    def test_markdown_output(self) -> None:
        tables = field_offsets.extract_fields(FIXTURE, "LayoutProbe")
        text = field_offsets.format_markdown(tables, "dump.cs")
        self.assertIn("TypeDefIndex 2200", text)
        self.assertIn("| 偏移 | 增量 |", text)
        self.assertIn("| `0x30` | `0x8` | `double` | 实例 | `weight` |", text)
        self.assertIn("| 静态 | `Instance` |", text)
        self.assertIn("| 常量 | `MAX` |", text)

    def test_json_output(self) -> None:
        tables = field_offsets.extract_fields(FIXTURE, "LayoutProbe")
        payload = json.loads(field_offsets.format_json(tables, "dump.cs", "LayoutProbe"))
        self.assertEqual(payload["count"], 1)
        fields = payload["types"][0]["fields"]
        weight = next(f for f in fields if f["name"] == "weight")
        self.assertEqual(weight["offset"], 0x30)
        self.assertEqual(weight["delta"], 8)
        self.assertFalse(weight["static"])

    def test_csv_output(self) -> None:
        tables = field_offsets.extract_fields(FIXTURE, "LayoutProbe")
        rows = list(csv.DictReader(io.StringIO(field_offsets.format_csv(tables))))
        self.assertTrue(any(r["name"] == "Instance" and r["static"] == "1" for r in rows))
        self.assertTrue(any(r["name"] == "MAX" and r["const"] == "1" for r in rows))
        self.assertTrue(any(r["name"] == "weight" and r["delta"] == "0x8" for r in rows))

    def test_no_match(self) -> None:
        self.assertEqual(field_offsets.extract_fields(FIXTURE, "NoSuchType"), [])


if __name__ == "__main__":
    unittest.main()
