"""Load FAERS extracts into DuckDB and count the 2x2 table for a drug-reaction pair.

Counts are per unique case. Each case is represented by its latest version,
and cases FDA has deleted can be excluded.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import duckdb

from .schema import check_table_file

TABLES = ("DEMO", "DRUG", "REAC")
DRUG_ROLES = ("PS", "SS")  # primary and secondary suspect
# Matches the quarter in names like DEMO24Q1.txt: year digits, then quarter number.
QUARTER_PATTERN = r"([0-9]{2})[Qq]([1-4])\.txt$"


@dataclass(frozen=True)
class ContingencyCounts:
    """2x2 case counts for one drug-reaction pair.

    a: cases with the drug and the reaction
    b: cases with the drug, without the reaction
    c: cases without the drug, with the reaction
    d: cases with neither
    """

    a: int
    b: int
    c: int
    d: int


def sql_literal(value: str) -> str:
    """Quote a Python string as an SQL string literal."""
    return "'" + value.replace("'", "''") + "'"


def find_table_files(data_dir: Path, table: str) -> list[Path]:
    """Return the validated {table} text extracts under data_dir.

    Files inside any folder named Deleted are skipped, since those hold removal lists.
    """
    found = []
    for path in sorted(data_dir.rglob("*.txt")):
        if any(part.lower() == "deleted" for part in path.parts):
            continue
        if path.name.upper().startswith(table):
            found.append(path)
    for path in found:
        check_table_file(path)
    return found


def _load_raw_table(con: duckdb.DuckDBPyConnection, table: str, paths: list[Path]) -> None:
    if not paths:
        raise FileNotFoundError(f"no {table} extracts found")
    file_list = ", ".join(sql_literal(str(p)) for p in paths)
    year = f"(2000 + CAST(regexp_extract(filename, {sql_literal(QUARTER_PATTERN)}, 1) AS INTEGER))"
    quarter = f"CAST(regexp_extract(filename, {sql_literal(QUARTER_PATTERN)}, 2) AS INTEGER)"
    con.execute(
        f"CREATE OR REPLACE TABLE raw_{table.lower()} AS "
        f"SELECT *, {year} * 10 + {quarter} AS quarter_key "
        f"FROM read_csv([{file_list}], delim='$', header=true, all_varchar=true, "
        f"filename=true, encoding='latin-1')"
    )


def _create_excluded(con: duckdb.DuckDBPyConnection, caseids: list[str]) -> None:
    con.execute("CREATE OR REPLACE TABLE excluded (caseid VARCHAR)")
    if caseids:
        con.executemany("INSERT INTO excluded VALUES (?)", [(c,) for c in caseids])


def _create_latest_demo(con: duckdb.DuckDBPyConnection) -> None:
    """Keep one row per case: the highest caseversion, then the latest quarter."""
    con.execute("""
        CREATE OR REPLACE TABLE latest_demo AS
        SELECT * EXCLUDE (rn) FROM (
            SELECT d.*,
                row_number() OVER (
                    PARTITION BY d.caseid
                    ORDER BY TRY_CAST(d.caseversion AS INTEGER) DESC, d.quarter_key DESC
                ) AS rn
            FROM raw_demo d
            WHERE d.caseid NOT IN (SELECT caseid FROM excluded)
        ) ranked
        WHERE rn = 1
    """)


def open_faers(
    data_dir: Path,
    db_path: str = ":memory:",
    excluded_caseids: Iterable[str] = (),
) -> duckdb.DuckDBPyConnection:
    """Load every DEMO, DRUG and REAC extract under data_dir.

    For the full data set, pass a file path as db_path (for example
    "data/faers.duckdb"). In-memory tables for several GB of text can
    exhaust the Codespace's RAM.
    """
    con = duckdb.connect(db_path)
    for table in TABLES:
        _load_raw_table(con, table, find_table_files(data_dir, table))
    _create_excluded(con, [str(c).strip() for c in excluded_caseids])
    _create_latest_demo(con)
    return con


def count_cases(con: duckdb.DuckDBPyConnection, drug: str, reaction: str) -> ContingencyCounts:
    """Count unique cases for one drug and one reaction term.

    Matching is case-insensitive and exact. The drug matches prod_ai or drugname,
    and only suspect roles (PS, SS) count.
    """
    roles = ", ".join(sql_literal(r) for r in DRUG_ROLES)
    drug_key = drug.strip().upper()
    reaction_key = reaction.strip().upper()
    total, n_drug, n_reac, a = con.execute(
        f"""
        WITH drug_cases AS (
            SELECT DISTINCT d.caseid
            FROM latest_demo d
            JOIN raw_drug dr ON dr.primaryid = d.primaryid
            WHERE upper(dr.role_cod) IN ({roles})
              AND (upper(dr.prod_ai) = ? OR upper(dr.drugname) = ?)
        ),
        reac_cases AS (
            SELECT DISTINCT d.caseid
            FROM latest_demo d
            JOIN raw_reac r ON r.primaryid = d.primaryid
            WHERE upper(r.pt) = ?
        )
        SELECT
            (SELECT count(*) FROM latest_demo),
            (SELECT count(*) FROM drug_cases),
            (SELECT count(*) FROM reac_cases),
            (SELECT count(*) FROM drug_cases JOIN reac_cases USING (caseid))
        """,
        [drug_key, drug_key, reaction_key],
    ).fetchone()
    b = n_drug - a
    c = n_reac - a
    d = total - a - b - c
    return ContingencyCounts(a=a, b=b, c=c, d=d)

def read_deleted_caseids(path: Path) -> list[str]:
    """Read case IDs from a FAERS deletion list: one ID per line, no header.

    Blank lines are skipped. Any other non-numeric line raises ValueError, so a
    changed file format fails loudly instead of deleting the wrong cases.
    """
    ids = []
    with path.open(encoding="latin-1") as handle:
        for number, line in enumerate(handle, start=1):
            value = line.strip()
            if not value:
                continue
            if not value.isdigit():
                raise ValueError(f"{path}:{number}: expected a case ID, got {value!r}")
            ids.append(value)
    return ids


def read_deleted_caseids(path: Path) -> list[str]:
    """Read case IDs from a FAERS deletion list: one ID per line, no header.

    Blank lines are skipped. Any other non-numeric line raises ValueError, so a
    changed file format fails loudly instead of deleting the wrong cases.
    """
    ids = []
    with path.open(encoding="latin-1") as handle:
        for number, line in enumerate(handle, start=1):
            value = line.strip()
            if not value:
                continue
            if not value.isdigit():
                raise ValueError(f"{path}:{number}: expected a case ID, got {value!r}")
            ids.append(value)
    return ids