"""Command-line entry point: triage one drug-reaction pair.

    python -m pharmsignal triage ibuprofen "Nausea"

Importing this module does not load DuckDB. The database is only imported
when a triage is actually run.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

from .classifier import Triage, classify
from .labels import api_key_from_env, fetch_label
from .retrieval import find_mentions, label_coverage, label_passages

DEFAULT_DATA_DIR = Path("data/faers")
DEFAULT_DB = "data/faers.duckdb"
DEFAULT_CACHE = Path("data/openfda")
PASSAGE_PREVIEW_CHARS = 300


def triage_from_parts(
    drug: str,
    reaction: str,
    counts: tuple[int, int, int, int],
    label_record: dict,
) -> Triage:
    """Combine FAERS counts and a cached label record into one triage result."""
    found = bool(label_record.get("found"))
    mentions = find_mentions(label_passages(label_record), reaction) if found else []
    a, b, c, d = counts
    result = classify(a, b, c, d, mentions, found)
    return replace(result, rationale=result.rationale + " " + label_coverage(label_record))


def run_triage(
    drug: str,
    reaction: str,
    data_dir: Path,
    db_path: str,
    cache_dir: Path,
    api_key: str | None,
) -> Triage:
    """Load FAERS data, count the 2x2 table, fetch the label, and classify."""
    from .faers import count_cases, load_deleted_caseids, open_faers

    excluded = load_deleted_caseids(data_dir)
    con = open_faers(data_dir, db_path=db_path, excluded_caseids=excluded)
    try:
        counts = count_cases(con, drug, reaction)
    finally:
        con.close()
    label = fetch_label(drug, cache_dir, api_key=api_key)
    return triage_from_parts(drug, reaction, (counts.a, counts.b, counts.c, counts.d), label)


def format_triage(drug: str, reaction: str, result: Triage) -> str:
    """Plain-text report for the terminal."""
    lines = [
        f"Drug: {drug}",
        f"Reaction: {reaction}",
        f"Category: {result.category}",
        f"Rationale: {result.rationale}",
    ]
    if result.citations:
        lines.append("Label passages:")
        for section, text in result.citations:
            preview = text if len(text) <= PASSAGE_PREVIEW_CHARS else text[:PASSAGE_PREVIEW_CHARS] + "..."
            lines.append(f"  - [{section}] {preview}")
    lines.append("This is a prompt for human review, not a safety conclusion.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pharmsignal",
        description="Pharmacovigilance signal triage: hypothesis generation, not causal inference.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    triage = subparsers.add_parser("triage", help="triage one drug-reaction pair")
    triage.add_argument("drug", help="drug name, e.g. ibuprofen")
    triage.add_argument("reaction", help="MedDRA preferred term, e.g. Nausea")
    triage.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    triage.add_argument("--db", default=DEFAULT_DB, help="DuckDB file to build")
    triage.add_argument("--cache", type=Path, default=DEFAULT_CACHE)

    args = parser.parse_args(argv)
    try:
        result = run_triage(
            args.drug, args.reaction, args.data_dir, args.db, args.cache, api_key_from_env()
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(format_triage(args.drug, args.reaction, result))
    return 0