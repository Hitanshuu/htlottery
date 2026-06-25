import datetime as dt
import random

import pytest

from src import backtest, models, storage


def _row(draw_date, d1, d2, d3):
    return {
        "draw_date": draw_date,
        "d1": d1, "d2": d2, "d3": d3,
        "pattern": storage.classify_pattern(d1, d2, d3),
    }


def _synthetic_uniform_history(n, seed=42):
    rng = random.Random(seed)
    history = []
    start = dt.date(2026, 1, 1)
    for i in range(n):
        d1, d2, d3 = rng.randint(0, 9), rng.randint(0, 9), rng.randint(0, 9)
        history.append(_row(start + dt.timedelta(days=i), d1, d2, d3))
    return history


def test_walk_forward_scores_skips_non_distinct_draws():
    history = [
        _row(dt.date(2026, 1, i), i % 10, (i + 1) % 10, (i + 2) % 10) for i in range(1, 10)
    ] + [_row(dt.date(2026, 1, 10), 5, 5, 5)]  # AAA, non-distinct, last test draw
    result = backtest.walk_forward_scores(history, models.UniformBaseline, min_train_size=5)
    # the final draw is AAA and must be excluded from scoring
    assert result["n_scored"] == len(history) - 5 - 1


def test_walk_forward_scores_uniform_logloss_matches_log_120():
    import math
    history = _synthetic_uniform_history(20)
    result = backtest.walk_forward_scores(history, models.UniformBaseline, min_train_size=5)
    scored = [r for r in history[5:] if r["pattern"] == "ABC"]
    assert result["n_scored"] == len(scored)
    for ll in result["logloss_per_draw"]:
        assert abs(ll - math.log(120)) < 1e-9


def test_selection_guard_returns_uniform_on_synthetic_random_data():
    history = _synthetic_uniform_history(200, seed=7)
    selected_name, table, reason = backtest.select_model(history)
    assert selected_name == "UniformBaseline"
    assert "UniformBaseline" in table
    assert all(name in table for name in [
        "UniformBaseline", "PerPositionFrequency", "MarkovOrder1", "MarkovOrder2", "MLClassifier",
    ])


def test_selection_guard_handles_insufficient_history():
    history = _synthetic_uniform_history(3)
    selected_name, table, reason = backtest.select_model(history)
    assert selected_name == "UniformBaseline"
    assert "insufficient" in reason.lower()


def test_compare_models_reports_mean_logloss_and_hit_rate():
    history = _synthetic_uniform_history(50, seed=1)
    table = backtest.compare_models(history)
    assert "UniformBaseline" in table
    stats = table["UniformBaseline"]
    assert "mean_logloss" in stats and "top1_hit_rate" in stats and "n_scored" in stats
    assert stats["n_scored"] > 0
