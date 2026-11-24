from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import find_string  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "stringliteral.sample.json"


class FindStringTests(unittest.TestCase):
    def test_load_strings(self) -> None:
        strings = find_string.load_strings(FIXTURE)
        self.assertEqual(len(strings), 4)
        self.assertEqual(strings[0]["value"], "Artillery incoming. Adjust fire.")

    def test_case_insensitive_substring(self) -> None:
        # main() prints; here we only verify the data source and matcher contract.
        strings = find_string.load_strings(FIXTURE)
        hits = [item for item in strings if "artillery" in item["value"].lower()]
        self.assertEqual(len(hits), 2)

    def test_exact_match_is_exact(self) -> None:
        strings = find_string.load_strings(FIXTURE)
        hits = [item for item in strings if item["value"] == "artillery"]
        self.assertEqual(len(hits), 1)


if __name__ == "__main__":
    unittest.main()
