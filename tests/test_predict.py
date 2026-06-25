import datetime as dt

import pytest

from src import models, predict


def test_generate_pick_has_three_distinct_digits():
    model = models.UniformBaseline()
    model.fit([])
    pick = predict.generate_pick(model, "260623", dt.date(2026, 6, 23))
    assert len(set([pick["d1"], pick["d2"], pick["d3"]])) == 3


@pytest.mark.parametrize("seed_draw_id", [f"2606{d:02d}" for d in range(1, 29)])
def test_generate_pick_always_eligible_across_many_draw_ids(seed_draw_id):
    model = models.UniformBaseline()
    model.fit([])
    pick = predict.generate_pick(model, seed_draw_id, dt.date(2026, 6, 23))
    digits = [pick["d1"], pick["d2"], pick["d3"]]
    assert len(set(digits)) == 3
    assert all(0 <= d <= 9 for d in digits)


def test_generate_pick_is_deterministic_for_same_draw_id():
    model = models.UniformBaseline()
    model.fit([])
    pick1 = predict.generate_pick(model, "260623", dt.date(2026, 6, 23))
    pick2 = predict.generate_pick(model, "260623", dt.date(2026, 6, 23))
    assert pick1 == pick2


def test_generate_pick_differs_for_different_draw_ids_usually():
    model = models.UniformBaseline()
    model.fit([])
    picks = {
        predict.generate_pick(model, f"2606{d:02d}", dt.date(2026, 6, 23))["predicted_digits_sorted"]
        for d in range(1, 15)
    }
    assert len(picks) > 1  # not literally always the same set


def test_generate_pick_predicted_combo_matches_sorted_digits():
    model = models.UniformBaseline()
    model.fit([])
    pick = predict.generate_pick(model, "260623", dt.date(2026, 6, 23))
    combo_digits = tuple(int(x) for x in pick["predicted_combo"].split("-"))
    sorted_digits = tuple(int(x) for x in pick["predicted_digits_sorted"].split("-"))
    assert tuple(sorted(combo_digits)) == sorted_digits
