import tempfile
import unittest
from pathlib import Path

from pharmsignal.schema import (
    DEMO_COLUMNS,
    SchemaError,
    check_table_file,
    parse_header,
    validate_header,
)

# Header lines captured from the 2024Q1 FAERS extract.
REAL_HEADERS = {
    "DEMO": "primaryid$caseid$caseversion$i_f_code$event_dt$mfr_dt$init_fda_dt$fda_dt$rept_cod$auth_num$mfr_num$mfr_sndr$lit_ref$age$age_cod$age_grp$sex$e_sub$wt$wt_cod$rept_dt$to_mfr$occp_cod$reporter_country$occr_country",
    "DRUG": "primaryid$caseid$drug_seq$role_cod$drugname$prod_ai$val_vbm$route$dose_vbm$cum_dose_chr$cum_dose_unit$dechal$rechal$lot_num$exp_dt$nda_num$dose_amt$dose_unit$dose_form$dose_freq",
    "REAC": "primaryid$caseid$pt$drug_rec_act",
}


class ParseHeaderTests(unittest.TestCase):
    def test_splits_on_dollar_and_lowercases(self):
        self.assertEqual(parse_header("PrimaryID$CaseID\n"), ("primaryid", "caseid"))

    def test_strips_windows_line_endings(self):
        self.assertEqual(parse_header("a$b\r\n"), ("a", "b"))


class ValidateHeaderTests(unittest.TestCase):
    def test_real_2024q1_headers_match_constants(self):
        for table, line in REAL_HEADERS.items():
            with self.subTest(table=table):
                validate_header(parse_header(line), table)

    def test_missing_column_raises(self):
        columns = tuple(c for c in DEMO_COLUMNS if c != "caseid")
        with self.assertRaisesRegex(SchemaError, r"missing columns \['caseid'\]"):
            validate_header(columns, "DEMO")

    def test_unexpected_column_raises(self):
        columns = DEMO_COLUMNS + ("new_col",)
        with self.assertRaisesRegex(SchemaError, r"unexpected columns \['new_col'\]"):
            validate_header(columns, "DEMO")

    def test_duplicate_column_raises(self):
        columns = DEMO_COLUMNS + ("caseid",)
        with self.assertRaisesRegex(SchemaError, r"duplicate columns \['caseid'\]"):
            validate_header(columns, "DEMO")

    def test_unknown_table_raises(self):
        with self.assertRaisesRegex(SchemaError, "unknown FAERS table"):
            validate_header(("a",), "XXXX")


class CheckTableFileTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_reads_table_name_from_file_name(self):
        path = self.dir / "DEMO24Q1.txt"
        path.write_text(REAL_HEADERS["DEMO"] + "\n1$2$3\n", encoding="latin-1")
        self.assertEqual(check_table_file(path), "DEMO")

    def test_bad_file_raises_with_path(self):
        path = self.dir / "REAC24Q1.txt"
        path.write_text("primaryid$caseid$pt\n", encoding="latin-1")
        with self.assertRaisesRegex(SchemaError, "drug_rec_act"):
            check_table_file(path)


if __name__ == "__main__":
    unittest.main()