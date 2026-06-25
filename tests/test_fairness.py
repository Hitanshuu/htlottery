import datetime as dt

import pytest

from src import fairness, storage


def _row(d1, d2, d3, day=1):
    return {
        "draw_date": dt.date(2026, 1, day),
        "d1": d1, "d2": d2, "d3": d3,
        "pattern": storage.classify_pattern(d1, d2, d3),
    }


def test_per_position_chi_square_uniform_data_no_anomaly():
    # Roughly uniform: each digit 0-9 appears exactly twice in each position over 20 draws.
    history = []
    for day in range(20):
        d = day % 10
        history.append(_row(d, (d + 1) % 10, (d + 2) % 10, day=day % 28 + 1))
    result = fairness.per_position_chi_square(history)
    for pos in ("d1", "d2", "d3"):
        assert "statistic" in result[pos]
        assert "p_value" in result[pos]
        assert result[pos]["p_value"] >= 0.01  # no anomaly on engineered-uniform data


def test_per_position_chi_square_flags_extreme_skew():
    # All draws have d1 always 7 -- a wildly non-uniform position.
    history = [_row(7, i % 10, (i + 1) % 10, day=i % 28 + 1) for i in range(40)]
    result = fairness.per_position_chi_square(history)
    assert result["d1"]["p_value"] < 0.01


def test_per_position_chi_square_observed_frequency_table():
    history = [_row(3, 3, 3, day=i % 28 + 1) for i in range(5)]
    result = fairness.per_position_chi_square(history)
    assert result["d1"]["observed"][3] == 5
    assert result["d1"]["observed"][0] == 0


def test_pattern_split_chi_square_matches_expected_proportions():
    # 1 AAA, 27 AAB-ish, 72 ABC -- matches theoretical 1%/27%/72% split closely.
    history = []
    history.append(_row(1, 1, 1, day=1))
    for i in range(27):
        history.append(_row(2, 2, 3, day=(i % 28) + 1))
    for i in range(72):
        history.append(_row(i % 10, (i + 1) % 10, (i + 3) % 10, day=(i % 28) + 1))
    result = fairness.pattern_split_chi_square(history)
    assert result["p_value"] >= 0.01
    assert set(result["observed"].keys()) == {"AAA", "AAB", "ABC"}


def test_flag_anomaly_uses_threshold():
    assert fairness.flag_anomaly(0.005) is True
    assert fairness.flag_anomaly(0.05) is False
