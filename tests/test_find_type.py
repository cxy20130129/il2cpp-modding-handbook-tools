from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import find_type  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "dump.sample.cs"


class FindTypeTests(unittest.TestCase):
    def test_class_search(self) -> None:
        matches = find_type.find_matches(FIXTURE, "TelegraphPanel", kind="class")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].kind, "class")
        self.assertEqual(matches[0].name, "IronNest.UI.TelegraphPanel")
        self.assertEqual(matches[0].type_ctx.typedef_index, "1187")
        self.assertEqual(matches[0].line_no, 4)

    def test_method_search_has_enclosing_type(self) -> None:
        matches = find_type.find_matches(FIXTURE, "SetText", kind="method")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].kind, "method")
        self.assertEqual(matches[0].type_ctx.full_name, "IronNest.UI.TelegraphPanel")
        self.assertIn("// RVA: 0x1A2B3C0", matches[0].signature)

    def test_field_search(self) -> None:
        matches = find_type.find_matches(FIXTURE, "remaining", kind="field")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].name, "remaining")
        self.assertEqual(matches[0].type_ctx.full_name, "IronNest.Gameplay.ArtilleryTimer")

    def test_property_search(self) -> None:
        matches = find_type.find_matches(FIXTURE, "CurrentPage", kind="property")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].kind, "property")
        self.assertEqual(matches[0].name, "CurrentPage")

    def test_regex_and_case(self) -> None:
        matches = find_type.find_matches(
            FIXTURE, r"^start.*", kind="method", use_regex=True, case_sensitive=False
        )
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].name, "StartCountdown")

    def test_nested_type(self) -> None:
        matches = find_type.find_matches(FIXTURE, "Inner", kind="class")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].name, "IronNest.UI.Outer.Inner")

    def test_nested_member(self) -> None:
        matches = find_type.find_matches(FIXTURE, "Ping", kind="method")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].type_ctx.full_name, "IronNest.UI.Outer.Inner")

    def test_no_match(self) -> None:
        self.assertEqual(find_type.find_matches(FIXTURE, "NoSuchSymbol"), [])


if __name__ == "__main__":
    unittest.main()
