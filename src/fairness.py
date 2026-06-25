"""Fairness / randomness audit -- NOT a predictor.

Chi-square goodness-of-fit checks that the draw history looks like what
i.i.d. uniform draws should look like. This is a sanity audit on the
operator's randomness, not a tool for finding predictive edge.
"""
from collections import Counter

from scipy.stats import chisquare

ANOMALY_P_VALUE_THRESHOLD = 0.01

EXPECTED_PATTERN_PROPORTIONS = {"AAA": 0.01, "AAB": 0.27, "ABC": 0.72}


def flag_anomaly(p_value: float) -> bool:
    """Flag only on p < 0.01, per spec -- and even then, it's most likely noise."""
    return p_value < ANOMALY_P_VALUE_THRESHOLD


def per_position_chi_square(history: list[dict]) -> dict:
    """Chi-square goodness-of-fit vs uniform (1/10 each, df=9) for d1, d2, d3."""
    result = {}
    for pos_key in ("d1", "d2", "d3"):
        observed_counts = Counter(row[pos_key] for row in history)
        observed = [observed_counts.get(d, 0) for d in range(10)]
        n = sum(observed)
        expected = [n / 10] * 10
        if n == 0:
            statistic, p_value = 0.0, 1.0
        else:
            statistic, p_value = chisquare(observed, f_exp=expected)
        result[pos_key] = {
            "statistic": float(statistic),
            "p_value": float(p_value),
            "observed": {d: observed_counts.get(d, 0) for d in range(10)},
        }
    return result


def pattern_split_chi_square(history: list[dict]) -> dict:
    """Chi-square goodness-of-fit of AAA/AAB/ABC split vs expected 1%/27%/72%."""
    observed_counts = Counter(row["pattern"] for row in history)
    patterns = ["AAA", "AAB", "ABC"]
    observed = [observed_counts.get(p, 0) for p in patterns]
    n = sum(observed)
    if n == 0:
        statistic, p_value = 0.0, 1.0
    else:
        expected = [n * EXPECTED_PATTERN_PROPORTIONS[p] for p in patterns]
        statistic, p_value = chisquare(observed, f_exp=expected)
    return {
        "statistic": float(statistic),
        "p_value": float(p_value),
        "observed": {p: observed_counts.get(p, 0) for p in patterns},
    }
