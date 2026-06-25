import csv
import datetime as dt
import os

import pytest

from src import storage


def test_draw_id_to_date_converts_yymmdd():
    assert storage.draw_id_to_date("260623") == dt.date(2026, 6, 23)


def test_draw_id_to_date_zero_pads_month_and_day():
    assert storage.draw_id_to_date("260105") == dt.date(2026, 1, 5)


def test_date_to_draw_id_round_trips():
    d = dt.date(2026, 6, 23)
    assert storage.date_to_draw_id(d) == "260623"
    assert storage.draw_id_to_date(storage.date_to_draw_id(d)) == d


def test_draw_id_to_date_rejects_non_six_digit():
    with pytest.raises(ValueError):
        storage.draw_id_to_date("2606")


def test_draw_id_to_date_rejects_invalid_calendar_date():
    with pytest.raises(ValueError):
        storage.draw_id_to_date("260230")  # Feb 30 doesn't exist


def test_draw_id_to_date_rejects_future_date():
    with pytest.raises(ValueError):
        storage.draw_id_to_date("991231")  # year 2099, far future


@pytest.mark.parametrize(
    "d1,d2,d3,expected",
    [
        (4, 4, 4, "AAA"),
        (4, 4, 7, "AAB"),
        (4, 7, 4, "AAB"),
        (7, 4, 4, "AAB"),
        (4, 2, 7, "ABC"),
    ],
)
def test_classify_pattern(d1, d2, d3, expected):
    assert storage.classify_pattern(d1, d2, d3) == expected


def test_atomic_write_csv_writes_rows(tmp_path):
    path = tmp_path / "out.csv"
    storage.atomic_write_csv(path, ["a", "b"], [{"a": "1", "b": "2"}])
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows == [{"a": "1", "b": "2"}]


def test_atomic_write_csv_leaves_no_partial_file_on_failure(tmp_path, monkeypatch):
    path = tmp_path / "out.csv"

    def boom(*args, **kwargs):
        raise RuntimeError("simulated write failure")

    monkeypatch.setattr(csv, "DictWriter", boom)

    with pytest.raises(RuntimeError):
        storage.atomic_write_csv(path, ["a"], [{"a": "1"}])

    assert not path.exists()
    leftover = [p for p in tmp_path.iterdir()]
    assert leftover == []


DRAW_FIELDS = ["draw_id", "draw_date", "d1", "d2", "d3", "combo", "pattern", "source", "fetched_at"]


def _draw_row(draw_id, d1=4, d2=2, d3=7, source="manual"):
    return {
        "draw_id": draw_id,
        "draw_date": storage.draw_id_to_date(draw_id).isoformat(),
        "d1": d1, "d2": d2, "d3": d3,
        "combo": f"{d1}-{d2}-{d3}",
        "pattern": storage.classify_pattern(d1, d2, d3),
        "source": source,
        "fetched_at": "2026-06-23T00:00:00+00:00",
    }


def test_append_draws_dedup_adds_new_rows(tmp_path):
    path = tmp_path / "draws.csv"
    added = storage.append_draws(path, DRAW_FIELDS, [_draw_row("260621"), _draw_row("260622")])
    assert added == 2
    rows = storage.read_rows(path, DRAW_FIELDS)
    assert {r["draw_id"] for r in rows} == {"260621", "260622"}


def test_append_draws_twice_adds_zero_duplicates(tmp_path):
    path = tmp_path / "draws.csv"
    storage.append_draws(path, DRAW_FIELDS, [_draw_row("260621")])
    added_second_time = storage.append_draws(path, DRAW_FIELDS, [_draw_row("260621"), _draw_row("260622")])
    rows = storage.read_rows(path, DRAW_FIELDS)
    assert added_second_time == 1
    assert len(rows) == 2
    assert sorted(r["draw_id"] for r in rows) == ["260621", "260622"]


PRED_FIELDS = [
    "target_draw_id", "target_date", "predicted_combo", "predicted_digits_sorted",
    "play_type", "model_used", "model_logloss", "baseline_logloss", "stake",
    "generated_at", "actual_combo", "won", "payout", "cum_stake", "cum_payout", "cum_pnl",
]


def _pred_row(target_draw_id, model_used="UniformBaseline"):
    return {
        "target_draw_id": target_draw_id, "target_date": "2026-06-23",
        "predicted_combo": "4-2-7", "predicted_digits_sorted": "2-4-7",
        "play_type": "Any 6", "model_used": model_used, "model_logloss": "",
        "baseline_logloss": "", "stake": "5", "generated_at": "2026-06-23T00:00:00+00:00",
        "actual_combo": "", "won": "", "payout": "",
        "cum_stake": "", "cum_payout": "", "cum_pnl": "",
    }


def test_upsert_prediction_inserts_new_row(tmp_path):
    path = tmp_path / "predictions.csv"
    storage.upsert_prediction(path, PRED_FIELDS, _pred_row("260623"))
    rows = storage.read_rows(path, PRED_FIELDS)
    assert len(rows) == 1
    assert rows[0]["target_draw_id"] == "260623"


def test_upsert_prediction_twice_keeps_one_row_per_target(tmp_path):
    path = tmp_path / "predictions.csv"
    storage.upsert_prediction(path, PRED_FIELDS, _pred_row("260623", model_used="UniformBaseline"))
    storage.upsert_prediction(path, PRED_FIELDS, _pred_row("260623", model_used="PerPositionFrequency"))
    rows = storage.read_rows(path, PRED_FIELDS)
    assert len(rows) == 1
    assert rows[0]["model_used"] == "PerPositionFrequency"
