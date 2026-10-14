"""Disproportionality statistics for a 2x2 drug-reaction table.

PRR and ROR compare how often a reaction is reported with a drug against how
often it is reported with all other drugs. They describe reporting patterns
only. They do not estimate risk and do not establish causation.

Table layout:
    a: cases with the drug and the reaction
    b: cases with the drug, without the reaction
    c: cases without the drug, with the reaction
    d: cases with neither
"""

from __future__ import annotations

import math
from dataclasses import dataclass

Z_95 = 1.959963984540054
EVANS_MIN_CASES = 3
EVANS_MIN_PRR = 2.0
EVANS_MIN_CHI2 = 4.0


@dataclass(frozen=True)
class DisproportionalityResult:
    a: int
    b: int
    c: int
    d: int
    prr: float
    prr_lower: float
    prr_upper: float
    ror: float
    ror_lower: float
    ror_upper: float
    chi2: float
    haldane_applied: bool
    meets_evans: bool
    ror_lower_above_one: bool


def _chi_square(a: int, b: int, c: int, d: int) -> float:
    """Pearson chi-square on the raw 2x2 table, without continuity correction."""
    n = a + b + c + d
    total = 0.0
    cells = (
        (a, a + b, a + c),
        (b, a + b, b + d),
        (c, c + d, a + c),
        (d, c + d, b + d),
    )
    for observed, row, col in cells:
        expected = row * col / n
        if expected > 0:
            total += (observed - expected) ** 2 / expected
    return total


def compute(a: int, b: int, c: int, d: int) -> DisproportionalityResult:
    """Return PRR, ROR, 95% intervals, chi-square and the Evans flag for one table.

    If any cell is zero, 0.5 is added to every cell (Haldane-Anscombe correction)
    so the ratios and intervals stay finite. The result is flagged with
    haldane_applied. The Evans case-count rule always uses the raw count a.
    """
    counts = (a, b, c, d)
    if any(value < 0 for value in counts):
        raise ValueError(f"counts cannot be negative: {counts}")
    if sum(counts) == 0:
        raise ValueError("empty 2x2 table")

    chi2 = _chi_square(a, b, c, d)

    haldane = min(counts) == 0
    if haldane:
        aa, bb, cc, dd = (value + 0.5 for value in counts)
    else:
        aa, bb, cc, dd = (float(value) for value in counts)

    prr = (aa / (aa + bb)) / (cc / (cc + dd))
    se_log_prr = math.sqrt(1 / aa - 1 / (aa + bb) + 1 / cc - 1 / (cc + dd))
    prr_lower = prr * math.exp(-Z_95 * se_log_prr)
    prr_upper = prr * math.exp(Z_95 * se_log_prr)

    ror = (aa * dd) / (bb * cc)
    se_log_ror = math.sqrt(1 / aa + 1 / bb + 1 / cc + 1 / dd)
    ror_lower = ror * math.exp(-Z_95 * se_log_ror)
    ror_upper = ror * math.exp(Z_95 * se_log_ror)

    meets_evans = (
        a >= EVANS_MIN_CASES and prr >= EVANS_MIN_PRR and chi2 >= EVANS_MIN_CHI2
    )

    return DisproportionalityResult(
        a=a,
        b=b,
        c=c,
        d=d,
        prr=prr,
        prr_lower=prr_lower,
        prr_upper=prr_upper,
        ror=ror,
        ror_lower=ror_lower,
        ror_upper=ror_upper,
        chi2=chi2,
        haldane_applied=haldane,
        meets_evans=meets_evans,
        ror_lower_above_one=ror_lower > 1,
    )