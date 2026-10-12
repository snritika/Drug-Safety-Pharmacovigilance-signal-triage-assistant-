"""FAERS ASCII table layouts and header validation.

The column lists match the quarterly extracts captured from 2024Q1. Other
quarters can differ, so every file's header is checked before any data is
read. A mismatch raises SchemaError rather than guessing.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

DELIMITER = "$"

DEMO_COLUMNS: tuple[str, ...] = (
    "primaryid", "caseid", "caseversion", "i_f_code", "event_dt", "mfr_dt",
    "init_fda_dt", "fda_dt", "rept_cod", "auth_num", "mfr_num", "mfr_sndr",
    "lit_ref", "age", "age_cod", "age_grp", "sex", "e_sub", "wt", "wt_cod",
    "rept_dt", "to_mfr", "occp_cod", "reporter_country", "occr_country",
)
DRUG_COLUMNS: tuple[str, ...] = (
    "primaryid", "caseid", "drug_seq", "role_cod", "drugname", "prod_ai",
    "val_vbm", "route", "dose_vbm", "cum_dose_chr", "cum_dose_unit",
    "dechal", "rechal", "lot_num", "exp_dt", "nda_num", "dose_amt",
    "dose_unit", "dose_form", "dose_freq",
)
REAC_COLUMNS: tuple[str, ...] = ("primaryid", "caseid", "pt", "drug_rec_act")

EXPECTED_COLUMNS: dict[str, tuple[str, ...]] = {
    "DEMO": DEMO_COLUMNS,
    "DRUG": DRUG_COLUMNS,
    "REAC": REAC_COLUMNS,
}


class SchemaError(ValueError):
    """Raised when a FAERS file's header does not match the expected layout."""


def parse_header(line: str) -> tuple[str, ...]:
    """Split a raw header line into lowercase column names."""
    return tuple(part.strip().lower() for part in line.rstrip("\r\n").split(DELIMITER))


def validate_header(actual: tuple[str, ...], table: str, source: str = "") -> None:
    """Raise SchemaError unless `actual` contains exactly the expected columns.

    Column order is not checked, because the loader reads columns by name.
    """
    if table not in EXPECTED_COLUMNS:
        raise SchemaError(f"unknown FAERS table {table!r}")
    expected = EXPECTED_COLUMNS[table]
    where = f" in {source}" if source else ""

    duplicates = sorted(name for name, count in Counter(actual).items() if count > 1)
    unexpected = [name for name in actual if name not in expected]
    missing = [name for name in expected if name not in actual]

    problems = []
    if duplicates:
        problems.append(f"duplicate columns {duplicates}")
    if unexpected:
        problems.append(f"unexpected columns {unexpected}")
    if missing:
        problems.append(f"missing columns {missing}")
    if problems:
        raise SchemaError(f"{table} header{where}: " + "; ".join(problems))


def read_header(path: Path) -> tuple[str, ...]:
    """Read and parse the first line of a FAERS text file.

    Latin-1 accepts every byte, so a stray non-UTF-8 character in the header
    cannot stop the check.
    """
    with path.open(encoding="latin-1") as handle:
        return parse_header(handle.readline())


def check_table_file(path: Path) -> str:
    """Validate one FAERS table file and return its table name.

    The table name comes from the file name, e.g. DEMO24Q1.txt -> DEMO.
    """
    table = path.name[:4].upper()
    validate_header(read_header(path), table, source=str(path))
    return table