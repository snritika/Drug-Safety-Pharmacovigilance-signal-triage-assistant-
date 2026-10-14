import unittest

from pharmsignal.retrieval import find_mentions, label_passages

RECORD = {
    "found": True,
    "response": {
        "results": [
            {
                "warnings_and_cautions": [
                    {"text": "Hepatotoxicity has been reported.\n  Liver   injury may occur."},
                ],
                "adverse_reactions": ["Nausea was the most common event.", "Patients were nauseated."],
                "contraindications": "Do not use in patients with severe liver disease.",
                "indications_and_usage": ["Not searched: nausea appears here too."],
            }
        ]
    },
}


class PassageTests(unittest.TestCase):
    def test_passages_keep_section_and_index(self):
        passages = label_passages(RECORD)
        self.assertEqual(
            [(p.section, p.index) for p in passages],
            [
                ("warnings_and_cautions", 0),
                ("adverse_reactions", 0),
                ("adverse_reactions", 1),
                ("contraindications", 0),
            ],
        )

    def test_whitespace_is_normalised(self):
        passages = label_passages(RECORD)
        self.assertEqual(passages[0].text, "Hepatotoxicity has been reported. Liver injury may occur.")

    def test_unsearched_section_is_ignored(self):
        texts = " ".join(p.text for p in label_passages(RECORD))
        self.assertNotIn("indications", texts.lower())

    def test_not_found_record_gives_no_passages(self):
        self.assertEqual(label_passages({"found": False, "response": None}), [])


class MentionTests(unittest.TestCase):
    def test_case_insensitive_whole_word_match(self):
        mentions = find_mentions(label_passages(RECORD), "NAUSEA")
        whole = [m for m in mentions if m.whole_word]
        self.assertEqual(len(whole), 1)
        self.assertEqual(whole[0].passage.section, "adverse_reactions")
        self.assertEqual(whole[0].passage.index, 0)

    def test_substring_match_is_flagged_weaker(self):
        mentions = find_mentions(label_passages(RECORD), "nausea")
        flags = {m.passage.text: m.whole_word for m in mentions}
        self.assertEqual(flags["Patients were nauseated."], False)

    def test_multi_word_term_matches_across_whitespace(self):
        mentions = find_mentions(label_passages(RECORD), "liver   injury")
        self.assertEqual(len(mentions), 1)
        self.assertEqual(mentions[0].passage.section, "warnings_and_cautions")

    def test_no_mention_returns_empty(self):
        self.assertEqual(find_mentions(label_passages(RECORD), "rash"), [])

    def test_empty_term_raises(self):
        with self.assertRaises(ValueError):
            find_mentions(label_passages(RECORD), "   ")


if __name__ == "__main__":
    unittest.main()