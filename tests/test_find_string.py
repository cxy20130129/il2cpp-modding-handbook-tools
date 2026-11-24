from __future__ import annotations

import contextlib
import io
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import find_string  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "stringliteral.sample.json"


def run_main(*args: str) -> tuple[int, str]:
    """Call find_string.main() and capture stdout; return (exit_code, output)."""
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        code = find_string.main([str(FIXTURE), *args])
    return code, output.getvalue()


class FindStringTests(unittest.TestCase):
    def test_load_strings(self) -> None:
        strings = find_string.load_strings(FIXTURE)
        self.assertEqual(len(strings), 4)
        self.assertEqual(strings[0]["value"], "Artillery incoming. Adjust fire.")

    def test_case_insensitive_substring(self) -> None:
        code, output = run_main("artillery")
        self.assertEqual(code, 0)
        self.assertIn("Artillery incoming. Adjust fire.", output)
        self.assertIn('"artillery"', output)
        self.assertNotIn("Telegraph line two", output)
        self.assertEqual(len(output.strip().splitlines()), 2)

    def test_exact_match_is_exact(self) -> None:
        code, output = run_main("artillery", "--exact")
        self.assertEqual(code, 0)
        self.assertIn('"artillery"', output)
        self.assertNotIn("Artillery incoming", output)
        self.assertEqual(len(output.strip().splitlines()), 1)

    def test_case_sensitive_substring(self) -> None:
        _, output = run_main("artillery", "--case-sensitive")
        self.assertNotIn("Artillery incoming", output)
        self.assertIn('"artillery"', output)

    def test_regex(self) -> None:
        _, output = run_main(r"radar|telegraph", "--regex")
        self.assertIn("Counter-battery radar online", output)
        self.assertIn("Telegraph line two", output)

    def test_no_match_prints_message(self) -> None:
        code, output = run_main("no-such-string-anywhere")
        self.assertEqual(code, 0)
        self.assertEqual(output.strip(), "no matches")

    def test_json_output(self) -> None:
        code, output = run_main("artillery", "--json")
        self.assertEqual(code, 0)
        payload = json.loads(output)
        self.assertEqual(payload["count"], 2)
        self.assertEqual(payload["query"], "artillery")

    def test_limit(self) -> None:
        _, output = run_main("artillery", "--limit", "1")
        self.assertEqual(len(output.strip().splitlines()), 1)

    def test_malformed_bytes_do_not_crash(self) -> None:
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as handle:
            # Malformed byte inside a string value: decoding must survive, and
            # the replacement character must stay inside a valid JSON string.
            handle.write(b'[{"value": "bad \xff byte"}, {"value": "ok"}]')
            broken = Path(handle.name)
        try:
            strings = find_string.load_strings(broken)
            self.assertIn("\ufffd", strings[0]["value"])
            self.assertEqual(strings[1]["value"], "ok")
        finally:
            broken.unlink()

    def test_missing_file_returns_error_code(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stderr(output):
            code = find_string.main(
                [str(ROOT / "tests" / "fixtures" / "does-not-exist.json"), "x"]
            )
        self.assertEqual(code, 2)
        self.assertIn("file not found", output.getvalue())


if __name__ == "__main__":
    unittest.main()
