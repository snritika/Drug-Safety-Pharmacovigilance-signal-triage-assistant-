import tempfile
import unittest
from pathlib import Path

from pharmsignal.faers import ContingencyCounts, count_cases, find_table_files, open_faers
from pharmsignal.schema import DEMO_COLUMNS, DRUG_COLUMNS, REAC_COLUMNS


def row(columns, **values):
    return "$".join(values.get(c, "") for c in columns)


def write_extract(path: Path, columns, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(["$".join(columns)] + rows) + "\n", encoding="latin-1")


def build_fixture(root: Path) -> None:
    """Two quarters of synthetic data, shaped like the real extracts.

    Case 1 has a newer version in 2024Q2 (its ibuprofen and nausea reports in
    2024Q1 are superseded). Case 5 is listed as excluded in the tests.
    """
    q1 = root / "2024q1" / "ASCII"
    q2 = root / "2024q2" / "ASCII"

    write_extract(q1 / "DEMO24Q1.txt", DEMO_COLUMNS, [
        row(DEMO_COLUMNS, primaryid="100001", caseid="1", caseversion="1"),
        row(DEMO_COLUMNS, primaryid="200001", caseid="2", caseversion="1"),
        row(DEMO_COLUMNS, primaryid="300001", caseid="3", caseversion="1"),
        row(DEMO_COLUMNS, primaryid="400001", caseid="4", caseversion="1"),
    ])
    write_extract(q1 / "DRUG24Q1.txt", DRUG_COLUMNS, [
        row(DRUG_COLUMNS, primaryid="100001", caseid="1", role_cod="PS",
            drugname="IBUPROFEN", prod_ai="IBUPROFEN"),
    ])
    write_extract(q1 / "REAC24Q1.txt", REAC_COLUMNS, [
        row(REAC_COLUMNS, primaryid="100001", caseid="1", pt="Nausea"),
        row(REAC_COLUMNS, primaryid="300001", caseid="3", pt="Headache"),
    ])

    write_extract(q2 / "DEMO24Q2.txt", DEMO_COLUMNS, [
        row(DEMO_COLUMNS, primaryid="100002", caseid="1", caseversion="2"),
        row(DEMO_COLUMNS, primaryid="500001", caseid="5", caseversion="1"),
    ])
    write_extract(q2 / "DRUG24Q2.txt", DRUG_COLUMNS, [
        row(DRUG_COLUMNS, primaryid="100002", caseid="1", role_cod="PS",
            drugname="Aspirin", prod_ai="ASPIRIN"),
        row(DRUG_COLUMNS, primaryid="200001", caseid="2", role_cod="SS",
            drugname="aspirin 81 mg", prod_ai="ASPIRIN"),
        row(DRUG_COLUMNS, primaryid="300001", caseid="3", role_cod="C",
            drugname="ASPIRIN", prod_ai="ASPIRIN"),
        row(DRUG_COLUMNS, primaryid="400001", caseid="4", role_cod="PS",
            drugname="IBUPROFEN", prod_ai="IBUPROFEN"),
        row(DRUG_COLUMNS, primaryid="500001", caseid="5", role_cod="PS",
            drugname="ASPIRIN", prod_ai="ASPIRIN"),
    ])
    write_extract(q2 / "REAC24Q2.txt", REAC_COLUMNS, [
        row(REAC_COLUMNS, primaryid="100002", caseid="1", pt="Headache"),
        row(REAC_COLUMNS, primaryid="200001", caseid="2", pt="Headache"),
        row(REAC_COLUMNS, primaryid="400001", caseid="4", pt="Nausea"),
        row(REAC_COLUMNS, primaryid="500001", caseid="5", pt="Headache"),
    ])

    # A removal-list folder that must be ignored, even though its name starts with DEMO.
    write_extract(q2 / "Deleted" / "DEMO99Q2.txt", ["bogus"], [])


class FindTableFilesTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        build_fixture(self.root)

    def tearDown(self):
        self._tmp.cleanup()

    def test_skips_deleted_folder(self):
        files = find_table_files(self.root, "DEMO")
        self.assertEqual([p.name for p in files], ["DEMO24Q1.txt", "DEMO24Q2.txt"])


class CountCasesTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        build_fixture(self.root)

    def tearDown(self):
        self._tmp.cleanup()

    def _counts(self, drug, reaction, excluded=("5",)):
        con = open_faers(self.root, excluded_caseids=excluded)
        try:
            return count_cases(con, drug, reaction)
        finally:
            con.close()

    def test_aspirin_headache_excludes_deleted_case(self):
        # Cases 1 and 2 have aspirin and headache. Case 3 has headache with
        # aspirin only as a concomitant, so it lands in c. Case 4 has neither.
        self.assertEqual(
            self._counts("aspirin", "headache"),
            ContingencyCounts(a=2, b=0, c=1, d=1),
        )

    def test_excluded_case_is_counted_without_exclusion(self):
        self.assertEqual(
            self._counts("aspirin", "headache", excluded=()),
            ContingencyCounts(a=3, b=0, c=1, d=1),
        )

    def test_superseded_versions_are_ignored(self):
        # Case 1's 2024Q1 ibuprofen and nausea reports are superseded by its
        # 2024Q2 version, which lists aspirin and headache only.
        self.assertEqual(
            self._counts("ibuprofen", "nausea"),
            ContingencyCounts(a=1, b=0, c=0, d=3),
        )

    def test_matching_is_case_insensitive(self):
        self.assertEqual(
            self._counts("ASPIRIN", "HEADACHE"),
            self._counts("aspirin", "headache"),
        )


class OpenFaersTests(unittest.TestCase):
    def test_missing_table_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_extract(root / "2024q1" / "DEMO24Q1.txt", DEMO_COLUMNS, [])
            with self.assertRaises(FileNotFoundError):
                open_faers(root)


if __name__ == "__main__":
    unittest.main()