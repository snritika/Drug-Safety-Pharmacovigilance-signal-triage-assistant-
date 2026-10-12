import tempfile
import unittest
from pathlib import Path

from pharmsignal.faers import read_deleted_caseids


class ReadDeletedCaseidsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_reads_ids_and_skips_blank_lines(self):
        path = self.dir / "DELETE24Q1.txt"
        path.write_text("\n10096604\n10096642\n", encoding="latin-1")
        self.assertEqual(read_deleted_caseids(path), ["10096604", "10096642"])

    def test_non_numeric_line_raises(self):
        path = self.dir / "DELETE24Q1.txt"
        path.write_text("10096604\ncaseid\n", encoding="latin-1")
        with self.assertRaisesRegex(ValueError, "expected a case ID"):
            read_deleted_caseids(path)