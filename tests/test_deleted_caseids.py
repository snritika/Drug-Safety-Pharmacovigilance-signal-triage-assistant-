import tempfile
import unittest
from pathlib import Path

from pharmsignal.faers import load_deleted_caseids, read_deleted_caseids


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


class LoadDeletedCaseidsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_combines_lists_from_all_quarters(self):
        q1 = self.root / "2024q1" / "Deleted"
        q2 = self.root / "2024q2" / "Deleted"
        q1.mkdir(parents=True)
        q2.mkdir(parents=True)
        (q1 / "DELETE24Q1.txt").write_text("1\n2\n", encoding="latin-1")
        (q2 / "DELETE24Q2.txt").write_text("2\n3\n", encoding="latin-1")
        self.assertEqual(load_deleted_caseids(self.root), {"1", "2", "3"})

    def test_ignores_delete_files_outside_deleted_folder(self):
        (self.root / "2024q1").mkdir()
        (self.root / "2024q1" / "DELETE24Q1.txt").write_text("9\n", encoding="latin-1")
        self.assertEqual(load_deleted_caseids(self.root), set())


if __name__ == "__main__":
    unittest.main()