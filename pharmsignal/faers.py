"""Load FAERS quarterly extracts into DuckDB and compute 2x2 case counts.

Each FAERS quarter comes as '$'-delimited text files. Each file is read on
its own, the latest version of every case is kept, cases FDA has deleted are
dropped, and cases are counted for one drug-reaction pair.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import duckdb

from .schema import read_header, validate_header

TABLES = ("DEMO", "DRUG", "REAC")
DRUG_ROLES = ("PS", "SS")  # primary and secondary suspect drugs

# Matches the quarter in names like DEMO24Q1.txt: two-digit year, then quarter.
QUARTER_RE = re.compile(r"([0-9]{2})[Qq]([1-4])\.txt$", re.IGNORECASE)

DUCKDB_TEMP_DIR = Path("data/duckdb_tmp")
DUCKDB_MEMORY_LIMIT = "4GB"


@dataclass(frozen=True)
class ContingencyCounts:
    """Case counts for one drug-reaction pair.

    a: cases with the drug and the reaction
    b: cases with the drug, without the reaction
    c: cases with the reaction, without the drug
    d: cases with neither
    """

    a: int
    b: int
    c: int
    d: int


def sql_literal(value: str) -> str:
    """Quote a string for use inside SQL text."""
    return "'" + value.replace("'", "''") + "'"


def _quarter_key(path: Path) -> int:
    """Turn a file name like DEMO24Q1.txt into a sortable key such as 20241."""
    match = QUARTER_RE.search(path.name)
    if not match:
        raise ValueError(f"cannot read the quarter from {path.name}")
    return (2000 + int(match.group(1))) * 10 + int(match.group(2))


def _in_deleted_folder(path: Path, root: Path) -> bool:
    """True if the file sits inside a folder named Deleted under root."""
    return any(part.lower() == "deleted" for part in path.relative_to(root).parts[:-1])


def find_table_files(data_dir: Path, table: str) -> list[Path]:
    """Return the validated {table} text extracts under data_dir.

    Files in Deleted folders are skipped. Each file's header is checked
    against the expected columns before the file is returned.
    """
    prefix = table.upper()
    found: list[Path] = []
    for path in sorted(data_dir.rglob("*.txt")):
        if _in_deleted_folder(path, data_dir):
            continue
        if not path.name.upper().startswith(prefix):
            continue
        if not QUARTER_RE.search(path.name):
            continue
        validate_header(read_header(path), table, source=str(path))
        found.append(path)
    return found


def _load_raw_table(con: duckdb.DuckDBPyConnection, table: str, paths: list[Path]) -> None:
    """Load every quarterly file for one table into raw_<table>.

    Each file is read on its own and added BY NAME, so columns are matched
    by name rather than by position across files.
    """
    if not paths:
        raise FileNotFoundError(f"no {table} files found")
    name = f"raw_{table.lower()}"
    con.execute(f"DROP TABLE IF EXISTS {name}")
    for index, path in enumerate(sorted(paths, key=_quarter_key)):
        source = (
            f"read_csv({sql_literal(str(path))}, delim='$', header=true, "
            "all_varchar=true, quote='', escape='', encoding='latin-1')"
        )
        select = f"SELECT *, {_quarter_key(path)} AS quarter_key FROM {source}"
        if index == 0:
            con.execute(f"CREATE TABLE {name} AS {select}")
        else:
            con.execute(f"INSERT INTO {name} BY NAME {select}")


def _create_excluded(con: duckdb.DuckDBPyConnection, excluded_caseids: Iterable[str]) -> None:
    """Create the table of case IDs to leave out (FDA deletions)."""
    con.execute("CREATE OR REPLACE TABLE excluded (caseid VARCHAR)")
    rows = [(str(caseid).strip(),) for caseid in excluded_caseids]
    if rows:
        con.executemany("INSERT INTO excluded VALUES (?)", rows)


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
    DUCKDB_TEMP_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(db_path)
    con.execute(f"SET memory_limit = '{DUCKDB_MEMORY_LIMIT}'")
    con.execute(f"SET temp_directory = {sql_literal(str(DUCKDB_TEMP_DIR))}")
    for table in TABLES:
        _load_raw_table(con, table, find_table_files(data_dir, table))
    _create_excluded(con, excluded_caseids)
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
    """Read one FDA deletion list: one numeric case ID per line.

    Blank lines are skipped. Any other line that is not a number is an error.
    """
    ids: list[str] = []
    text = path.read_text(encoding="latin-1")
    for number, line in enumerate(text.splitlines(), start=1):
        value = line.strip()
        if not value:
            continue
        if not value.isdigit():
            raise ValueError(f"{path}, line {number}: expected a case ID, got {value!r}")
        ids.append(value)
    return sorted(set(ids))


def find_deletion_files(data_dir: Path) -> list[Path]:
    """Return the DELETE*.txt lists inside Deleted folders under data_dir."""
    return sorted(
        path
        for path in data_dir.rglob("*.txt")
        if path.name.upper().startswith("DELETE") and _in_deleted_folder(path, data_dir)
    )


def load_deleted_caseids(data_dir: Path) -> set[str]:
    """Union of every FDA deletion list under data_dir."""
    deleted: set[str] = set()
    for path in find_deletion_files(data_dir):
        deleted.update(read_deleted_caseids(path))
    return deleted