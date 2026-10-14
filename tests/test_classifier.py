import unittest

from pharmsignal.classifier import (
    ALREADY_LABELLED,
    INSUFFICIENT_DATA,
    NEW_CANDIDATE,
    classify,
)
from pharmsignal.retrieval import Mention, Passage

WHOLE_MENTION = Mention(
    Passage("adverse_reactions", 0, "Nausea was the most common event."), whole_word=True
)
PARTIAL_MENTION = Mention(
    Passage("adverse_reactions", 1, "Patients were nauseated."), whole_word=False
)
STRONG = dict(a=20, b=80, c=50, d=950)  # PRR 4.0, chi-square about 34, 20 cases


class ClassifyTests(unittest.TestCase):
    def test_labelled_reaction_is_already_labelled_with_citation(self):
        result = classify(**STRONG, mentions=[WHOLE_MENTION], label_found=True)
        self.assertEqual(result.category, ALREADY_LABELLED)
        self.assertIn("adverse_reactions", result.rationale)
        self.assertIn("whole-word", result.rationale)
        self.assertEqual(result.citations[0][0], "adverse_reactions")

    def test_label_check_wins_over_strong_statistics(self):
        result = classify(**STRONG, mentions=[WHOLE_MENTION], label_found=True)
        self.assertNotEqual(result.category, NEW_CANDIDATE)

    def test_partial_match_is_marked_as_such(self):
        result = classify(**STRONG, mentions=[PARTIAL_MENTION], label_found=True)
        self.assertEqual(result.category, ALREADY_LABELLED)
        self.assertIn("partial-word only", result.rationale)

    def test_unlabelled_strong_signal_is_new_candidate(self):
        result = classify(**STRONG, mentions=[], label_found=True)
        self.assertEqual(result.category, NEW_CANDIDATE)
        self.assertEqual(result.citations, ())

    def test_unlabelled_weak_signal_is_insufficient_with_reason(self):
        result = classify(a=2, b=0, c=1, d=997, mentions=[], label_found=True)
        self.assertEqual(result.category, INSUFFICIENT_DATA)
        self.assertIn("only 2 case(s)", result.rationale)

    def test_low_prr_is_reported(self):
        result = classify(a=10, b=90, c=100, d=900, mentions=[], label_found=True)
        self.assertEqual(result.category, INSUFFICIENT_DATA)
        self.assertIn("PRR 1.00", result.rationale)

    def test_missing_label_is_insufficient_even_with_strong_signal(self):
        result = classify(**STRONG, mentions=[], label_found=False)
        self.assertEqual(result.category, INSUFFICIENT_DATA)
        self.assertIn("No FDA label text was found", result.rationale)


if __name__ == "__main__":
    unittest.main()