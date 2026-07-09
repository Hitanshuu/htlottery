import datetime as dt

import run_daily
from src import config, storage

TODAY = dt.date(2026, 6, 20)


def _no_op_fetch():
    return [], None


def test_cold_start_creates_pending_prediction_and_dashboard(tmp_path):
    data_dir = tmp_path / "data"
    docs_dir = tmp_path / "docs"
    run_daily.run(data_dir=data_dir, docs_dir=docs_dir, today=TODAY, fetch_fn=_no_op_fetch)

    predictions = storage.read_rows(data_dir / "predictions.csv", config.PREDICTIONS_FIELDNAMES)
    assert len(predictions) == 1
    assert predictions[0]["target_draw_id"] == storage.date_to_draw_id(TODAY)
    assert predictions[0]["model_used"] == "UniformBaseline"

    assert (data_dir / "last_report.md").exists()
    assert (docs_dir / "index.html").exists()
    assert (docs_dir / "today.json").exists()


def test_run_is_idempotent_same_day(tmp_path):
    data_dir = tmp_path / "data"
    docs_dir = tmp_path / "docs"
    run_daily.run(data_dir=data_dir, docs_dir=docs_dir, today=TODAY, fetch_fn=_no_op_fetch)
    run_daily.run(data_dir=data_dir, docs_dir=docs_dir, today=TODAY, fetch_fn=_no_op_fetch)

    predictions = storage.read_rows(data_dir / "predictions.csv", config.PREDICTIONS_FIELDNAMES)
    assert len(predictions) == 1


def test_bootstrap_imports_history_raw_csv(tmp_path):
    data_dir = tmp_path / "data"
    docs_dir = tmp_path / "docs"
    data_dir.mkdir(parents=True)
    (data_dir / "history_raw.csv").write_text("260617,4,2,7\n260618,1,1,1\n260619,8,5,2\n")

    run_daily.run(data_dir=data_dir, docs_dir=docs_dir, today=TODAY, fetch_fn=_no_op_fetch)

    draws = storage.read_rows(data_dir / "draws.csv", config.DRAWS_FIELDNAMES)
    assert {r["draw_id"] for r in draws} == {"260617", "260618", "260619"}


def test_scrape_failure_degrades_gracefully_and_notes_it(tmp_path):
    data_dir = tmp_path / "data"
    docs_dir = tmp_path / "docs"

    def failing_fetch():
        raise RuntimeError("network down")

    context = run_daily.run(data_dir=data_dir, docs_dir=docs_dir, today=TODAY, fetch_fn=failing_fetch)

    assert "not updated this run" in context["selection_reason"]
    predictions = storage.read_rows(data_dir / "predictions.csv", config.PREDICTIONS_FIELDNAMES)
    assert len(predictions) == 1  # still generated a pick despite scrape failure


def test_new_scraped_draws_are_appended_and_deduped(tmp_path):
    data_dir = tmp_path / "data"
    docs_dir = tmp_path / "docs"

    def fetch_with_one_new_draw():
        return ([{
            "draw_id": "260619", "draw_date": dt.date(2026, 6, 19),
            "d1": 8, "d2": 5, "d3": 2, "source": "goodreturns.in",
        }], "goodreturns")

    run_daily.run(data_dir=data_dir, docs_dir=docs_dir, today=TODAY, fetch_fn=fetch_with_one_new_draw)
    run_daily.run(data_dir=data_dir, docs_dir=docs_dir, today=TODAY, fetch_fn=fetch_with_one_new_draw)  # run again, same source

    draws = storage.read_rows(data_dir / "draws.csv", config.DRAWS_FIELDNAMES)
    assert len(draws) == 1  # deduped, not doubled
    assert draws[0]["draw_id"] == "260619"


def test_reconcile_mode_settles_result_without_touching_the_pick(tmp_path):
    """The two-runs-a-day flow: predict (evening) locks in a pick, then
    reconcile (night, after the draw landed) must settle win/loss without
    regenerating or overwriting that pick."""
    data_dir = tmp_path / "data"
    docs_dir = tmp_path / "docs"

    predict_ctx = run_daily.run(
        data_dir=data_dir, docs_dir=docs_dir, today=TODAY, fetch_fn=_no_op_fetch, mode="predict"
    )
    placed_combo = predict_ctx["predicted_combo"]

    predictions_before = storage.read_rows(data_dir / "predictions.csv", config.PREDICTIONS_FIELDNAMES)
    assert len(predictions_before) == 1
    assert predictions_before[0]["won"] == ""  # still pending

    target_draw_id = storage.date_to_draw_id(TODAY)
    d1, d2, d3 = (int(x) for x in predictions_before[0]["predicted_digits_sorted"].split("-"))

    def fetch_todays_landed_draw():
        return ([{
            "draw_id": target_draw_id, "draw_date": TODAY,
            "d1": d1, "d2": d2, "d3": d3, "source": "goodreturns.in",
        }], "goodreturns")

    reconcile_ctx = run_daily.run(
        data_dir=data_dir, docs_dir=docs_dir, today=TODAY,
        fetch_fn=fetch_todays_landed_draw, mode="reconcile",
    )

    assert reconcile_ctx["predicted_combo"] == placed_combo  # pick untouched
    predictions_after = storage.read_rows(data_dir / "predictions.csv", config.PREDICTIONS_FIELDNAMES)
    assert len(predictions_after) == 1  # no second row was generated
    assert predictions_after[0]["predicted_combo"] == placed_combo
    assert predictions_after[0]["won"] == "True"
    assert predictions_after[0]["payout"] == str(config.PAYOUT_AED)


def test_reconcile_mode_before_any_predict_shows_placeholder(tmp_path):
    data_dir = tmp_path / "data"
    docs_dir = tmp_path / "docs"

    context = run_daily.run(
        data_dir=data_dir, docs_dir=docs_dir, today=TODAY, fetch_fn=_no_op_fetch, mode="reconcile"
    )

    assert "n/a" in context["predicted_combo"]
    predictions = storage.read_rows(data_dir / "predictions.csv", config.PREDICTIONS_FIELDNAMES)
    assert predictions == []  # reconcile never generates a pick
