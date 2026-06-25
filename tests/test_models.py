import datetime as dt

import pytest

from src import models

ALL_SETS = models.ALL_SETS


def _row(draw_date, d1, d2, d3):
    return {"draw_date": draw_date, "d1": d1, "d2": d2, "d3": d3}


def test_all_sets_has_120_distinct_digit_combinations():
    assert len(ALL_SETS) == 120
    assert all(len(set(s)) == 3 for s in ALL_SETS)
    assert len(set(ALL_SETS)) == 120  # all unique


def _assert_valid_distribution(dist):
    assert set(dist.keys()) == set(ALL_SETS)
    assert abs(sum(dist.values()) - 1.0) < 1e-9
    assert all(p > 0 for p in dist.values())


def test_uniform_baseline_assigns_equal_probability():
    model = models.UniformBaseline()
    model.fit([])
    dist = model.predict_dist(dt.date(2026, 6, 23))
    _assert_valid_distribution(dist)
    assert all(abs(p - 1 / 120) < 1e-9 for p in dist.values())


def test_per_position_frequency_is_valid_distribution_with_history():
    history = [_row(dt.date(2026, 6, i), i % 10, (i + 1) % 10, (i + 2) % 10) for i in range(1, 30)]
    model = models.PerPositionFrequency()
    model.fit(history)
    dist = model.predict_dist(dt.date(2026, 7, 1))
    _assert_valid_distribution(dist)


def test_per_position_frequency_with_empty_history_is_uniform():
    model = models.PerPositionFrequency()
    model.fit([])
    dist = model.predict_dist(dt.date(2026, 6, 23))
    _assert_valid_distribution(dist)
    assert all(abs(p - 1 / 120) < 1e-6 for p in dist.values())


def test_markov_order1_is_valid_distribution_with_history():
    history = [_row(dt.date(2026, 6, i), i % 10, (i + 1) % 10, (i + 2) % 10) for i in range(1, 30)]
    model = models.MarkovOrder1()
    model.fit(history)
    dist = model.predict_dist(dt.date(2026, 7, 1))
    _assert_valid_distribution(dist)


def test_markov_order1_learns_deterministic_increment_pattern():
    # Each position deterministically increments by 1 mod 10 each draw.
    history = [_row(dt.date(2026, 1, 1) + dt.timedelta(days=i), i % 10, (i + 1) % 10, (i + 2) % 10) for i in range(50)]
    model = models.MarkovOrder1()
    model.fit(history)
    dist = model.predict_dist(dt.date(2026, 1, 1) + dt.timedelta(days=50))
    last = history[-1]
    expected_next = tuple(sorted({(last["d1"] + 1) % 10, (last["d2"] + 1) % 10, (last["d3"] + 1) % 10}))
    best = max(dist, key=dist.get)
    assert best == expected_next


def test_markov_order1_empty_history_is_uniform():
    model = models.MarkovOrder1()
    model.fit([])
    dist = model.predict_dist(dt.date(2026, 6, 23))
    _assert_valid_distribution(dist)
    assert all(abs(p - 1 / 120) < 1e-6 for p in dist.values())


def test_markov_order2_is_valid_distribution_with_history():
    history = [_row(dt.date(2026, 6, i), i % 10, (i + 1) % 10, (i + 2) % 10) for i in range(1, 30)]
    model = models.MarkovOrder2()
    model.fit(history)
    dist = model.predict_dist(dt.date(2026, 7, 1))
    _assert_valid_distribution(dist)


def test_markov_order2_insufficient_history_is_uniform():
    model = models.MarkovOrder2()
    model.fit([_row(dt.date(2026, 6, 1), 1, 2, 3)])
    dist = model.predict_dist(dt.date(2026, 6, 23))
    _assert_valid_distribution(dist)
    assert all(abs(p - 1 / 120) < 1e-6 for p in dist.values())


def test_ml_classifier_is_valid_distribution_with_enough_history():
    history = [_row(dt.date(2026, 1, 1) + dt.timedelta(days=i), i % 10, (i + 1) % 10, (i + 2) % 10) for i in range(60)]
    model = models.MLClassifier(n_lags=5)
    model.fit(history)
    dist = model.predict_dist(dt.date(2026, 1, 1) + dt.timedelta(days=60))
    _assert_valid_distribution(dist)


def test_ml_classifier_falls_back_to_uniform_with_insufficient_history():
    history = [_row(dt.date(2026, 6, 1), 1, 2, 3), _row(dt.date(2026, 6, 2), 4, 5, 6)]
    model = models.MLClassifier(n_lags=5)
    model.fit(history)  # should not raise despite far too little data
    dist = model.predict_dist(dt.date(2026, 6, 23))
    _assert_valid_distribution(dist)
    assert all(abs(p - 1 / 120) < 1e-6 for p in dist.values())
