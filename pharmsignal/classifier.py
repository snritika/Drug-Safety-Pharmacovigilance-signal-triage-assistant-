"""Triage one drug-reaction pair into one of three categories.

    already labelled   the FDA label mentions the reaction
    new candidate      the label does not mention it, and the pair meets the Evans signal rule
    insufficient data  neither of the above; the rationale gives the reason

The output is a prompt for human review, not a safety conclusion.
"""

from __future__ import annotations

from dataclasses import dataclass

from .disproportionality import (
    EVANS_MIN_CASES,
    EVANS_MIN_CHI2,
    EVANS_MIN_PRR,
    DisproportionalityResult,
    compute,
)
from .retrieval import Mention

ALREADY_LABELLED = "already labelled"
NEW_CANDIDATE = "new candidate"
INSUFFICIENT_DATA = "insufficient data"


@dataclass(frozen=True)
class Triage:
    category: str
    rationale: str
    citations: tuple[tuple[str, str], ...]
    stats: DisproportionalityResult


def _stats_summary(stats: DisproportionalityResult) -> str:
    text = (
        f"{stats.a} cases with the drug and reaction; "
        f"PRR {stats.prr:.2f} (95% CI {stats.prr_lower:.2f}-{stats.prr_upper:.2f}); "
        f"ROR {stats.ror:.2f}; chi-square {stats.chi2:.1f}."
    )
    if stats.haldane_applied:
        text += " A zero cell was present, so a 0.5 correction was applied to the ratios."
    return text


def _unmet_criteria(stats: DisproportionalityResult) -> str:
    reasons = []
    if stats.a < EVANS_MIN_CASES:
        reasons.append(f"only {stats.a} case(s), need {EVANS_MIN_CASES}")
    if stats.prr < EVANS_MIN_PRR:
        reasons.append(f"PRR {stats.prr:.2f}, need {EVANS_MIN_PRR:g}")
    if stats.chi2 < EVANS_MIN_CHI2:
        reasons.append(f"chi-square {stats.chi2:.2f}, need {EVANS_MIN_CHI2:g}")
    return "Criteria not met: " + "; ".join(reasons) + "."


def classify(
    a: int,
    b: int,
    c: int,
    d: int,
    mentions: list[Mention],
    label_found: bool,
) -> Triage:
    """Assign a triage category. The label check is made before the statistics."""
    stats = compute(a, b, c, d)
    citations = tuple((m.passage.section, m.passage.text) for m in mentions)

    if not label_found:
        return Triage(
            INSUFFICIENT_DATA,
            "No FDA label text was found, so the label check could not be made. "
            + _stats_summary(stats),
            (),
            stats,
        )

    if mentions:
        strength = "whole-word" if any(m.whole_word for m in mentions) else "partial-word only"
        sections = ", ".join(sorted({m.passage.section for m in mentions}))
        rationale = (
            f"The label mentions this reaction ({strength} match) in: {sections}. "
            + _stats_summary(stats)
        )
        return Triage(ALREADY_LABELLED, rationale, citations, stats)

    if stats.meets_evans:
        rationale = (
            "The label does not mention this reaction, and the pair meets the Evans "
            "signal rule. " + _stats_summary(stats)
        )
        return Triage(NEW_CANDIDATE, rationale, (), stats)

    return Triage(
        INSUFFICIENT_DATA,
        "The label does not mention this reaction, and the pair does not meet the "
        "Evans signal rule. " + _unmet_criteria(stats) + " " + _stats_summary(stats),
        (),
        stats,
    )