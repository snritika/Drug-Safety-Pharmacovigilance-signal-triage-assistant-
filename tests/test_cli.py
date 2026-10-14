import io
import unittest
from contextlib import redirect_stdout

from pharmsignal.cli import format_triage, main, triage_from_parts
from pharmsignal.classifier import ALREADY_LABELLED, INSUFFICIENT_DATA, NEW_CANDIDATE

LABEL_WITH_HEADACHE = {
    "drug": "aspirin",
    "found": True,
    "fetched_at": "2026-10-14T20:00:00+00:00",
    "response": {
        "results": [
            {"warnings_and_cautions": ["Headache was reported in trials."]}
        ]
    },
}
LABEL_NOT_FOUND = {"drug": "aspirin", "found": False, "fetched_at": "x", "response": None}
STRONG = (20, 80, 50, 950)


class TriageFromPartsTests(unittest.TestCase):
    def test_label_mention_is_already_labelled(self):
        result = triage_from_parts("aspirin", "headache", STRONG, LABEL_WITH_HEADACHE)
        self.assertEqual(result.category, ALREADY_LABELLED)
        self.assertEqual(result.citations[0][0], "warnings_and_cautions")

    def test_strong_signal_without_label_mention_is_new_candidate(self):
        result = triage_from_parts("aspirin", "rash", STRONG, LABEL_WITH_HEADACHE)
        self.assertEqual(result.category, NEW_CANDIDATE)

    def test_missing_label_is_insufficient(self):
        result = triage_from_parts("aspirin", "headache", STRONG, LABEL_NOT_FOUND)
        self.assertEqual(result.category, INSUFFICIENT_DATA)


class FormatTests(unittest.TestCase):
    def test_report_contains_category_and_passages(self):
        result = triage_from_parts("aspirin", "headache", STRONG, LABEL_WITH_HEADACHE)
        text = format_triage("aspirin", "headache", result)
        self.assertIn("Category: already labelled", text)
        self.assertIn("[warnings_and_cautions] Headache was reported", text)
        self.assertIn("not a safety conclusion", text)

    def test_long_passage_is_truncated(self):
        long_record = {
            "found": True,
            "response": {"results": [{"warnings_and_cautions": ["Headache " + "x" * 500]}]},
        }
        result = triage_from_parts("aspirin", "headache", STRONG, long_record)
        self.assertIn("...", format_triage("aspirin", "headache", result))


class MainTests(unittest.TestCase):
    def test_missing_subcommand_exits_with_usage_error(self):
        with self.assertRaises(SystemExit) as ctx:
            main([])
        self.assertEqual(ctx.exception.code, 2)

    def test_triage_requires_two_arguments(self):
        with self.assertRaises(SystemExit):
            main(["triage", "aspirin"])


if __name__ == "__main__":
    unittest.main()