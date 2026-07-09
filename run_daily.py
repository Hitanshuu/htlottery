"""Single entrypoint, run twice a day in two modes: scrape, reconcile, select
model, generate tonight's pick, report.

--mode predict (evening, before the draw): generates/upserts tonight's pick.
--mode reconcile (night, after the draw): scrapes the landed result, settles
today's prediction, and refreshes the dashboard -- never touches the pick.

Idempotent within a mode -- safe to run twice in the same day. Degrades
gracefully if scraping fails: proceeds with existing history rather than
hard-failing, and the dashboard plainly notes that results weren't updated
this run.
"""
import datetime as dt
import json
import logging
from pathlib import Path

from src import backtest, config, dashboard, fairness, importer, predict, scraper, storage, tracker

logger = logging.getLogger(__name__)


def _today_dubai() -> dt.date:
    return dt.datetime.now(config.TIMEZONE).date()


def _import_history_raw_if_present(data_dir: Path, draws_path: Path) -> None:
    for name in ("history_raw.csv", "history_raw.txt"):
        candidate = data_dir / name
        if candidate.exists():
            summary = importer.import_history_text(candidate.read_text(), draws_path)
            logger.info("Imported %s: %s", name, summary)


def _to_draws_csv_row(record: dict) -> dict:
    d1, d2, d3 = record["d1"], record["d2"], record["d3"]
    return {
        "draw_id": record["draw_id"],
        "draw_date": record["draw_date"].isoformat(),
        "d1": d1, "d2": d2, "d3": d3,
        "combo": f"{d1}-{d2}-{d3}",
        "pattern": storage.classify_pattern(d1, d2, d3),
        "source": record["source"],
        "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }


def _load_history(draws_path: Path) -> list[dict]:
    rows = storage.read_rows(draws_path, config.DRAWS_FIELDNAMES)
    rows.sort(key=lambda r: r["draw_id"])
    return [
        {
            "draw_id": r["draw_id"],
            "draw_date": dt.date.fromisoformat(r["draw_date"]),
            "d1": int(r["d1"]), "d2": int(r["d2"]), "d3": int(r["d3"]),
            "pattern": r["pattern"],
        }
        for r in rows
    ]


def run(
    data_dir: Path = config.DATA_DIR,
    docs_dir: Path = config.DOCS_DIR,
    today: dt.date | None = None,
    fetch_fn=scraper.fetch_with_fallback,
    mode: str = "predict",
) -> dict:
    """mode="predict" generates/upserts tonight's pick (run before buying a ticket).
    mode="reconcile" only scrapes+settles predictions against real results and
    refreshes the dashboard -- it never touches an already-placed pick, so it's
    safe to run again later the same day once the draw has landed.
    """
    if mode not in ("predict", "reconcile"):
        raise ValueError(f"unknown mode: {mode!r}")

    today = today or _today_dubai()
    data_dir, docs_dir = Path(data_dir), Path(docs_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    docs_dir.mkdir(parents=True, exist_ok=True)

    draws_path = data_dir / "draws.csv"
    predictions_path = data_dir / "predictions.csv"

    _import_history_raw_if_present(data_dir, draws_path)

    target_draw_id = storage.date_to_draw_id(today)
    existing_draws = storage.read_rows(draws_path, config.DRAWS_FIELDNAMES)
    max_existing_id = max((r["draw_id"] for r in existing_draws), default=None)

    try:
        records, source_used = fetch_fn()
    except Exception as exc:
        logger.warning("Scrape failed unexpectedly, proceeding with existing history: %s", exc)
        records, source_used = [], None

    if source_used is None:
        scrape_note = "results not updated this run"
    else:
        scrape_note = "results updated this run"
        new_rows = [
            _to_draws_csv_row(rec)
            for rec in records
            if max_existing_id is None or rec["draw_id"] > max_existing_id
        ]
        added = storage.append_draws(draws_path, config.DRAWS_FIELDNAMES, new_rows)
        logger.info("Scraped %d new draw(s) from %s", added, source_used)

    history = _load_history(draws_path)
    draws_by_id = {h["draw_id"]: h for h in history}

    predictions = storage.read_rows(predictions_path, config.PREDICTIONS_FIELDNAMES)
    reconciled = tracker.reconcile(predictions, draws_by_id)
    if reconciled:
        storage.atomic_write_csv(predictions_path, config.PREDICTIONS_FIELDNAMES, reconciled)

    if history:
        selected_name, model_table, reason = backtest.select_model(history)
    else:
        selected_name, model_table, reason = "UniformBaseline", {}, "no history yet -- defaulting to chance"

    if mode == "predict":
        model = backtest.CANDIDATE_MODEL_CLASSES[selected_name]()
        model.fit(history)
        pick = predict.generate_pick(model, target_draw_id, today)

        def _logloss_str(name: str) -> str:
            stats = model_table.get(name)
            return f"{stats['mean_logloss']:.6f}" if stats and stats["n_scored"] else ""

        prediction_row = {
            "target_draw_id": target_draw_id,
            "target_date": today.isoformat(),
            "predicted_combo": pick["predicted_combo"],
            "predicted_digits_sorted": pick["predicted_digits_sorted"],
            "play_type": config.PLAY_TYPE,
            "model_used": selected_name,
            "model_logloss": _logloss_str(selected_name),
            "baseline_logloss": _logloss_str("UniformBaseline"),
            "stake": str(config.STAKE_AED),
            "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "actual_combo": "", "won": "", "payout": "",
            "cum_stake": "", "cum_payout": "", "cum_pnl": "",
        }
        storage.upsert_prediction(predictions_path, config.PREDICTIONS_FIELDNAMES, prediction_row)
        selection_reason = f"{reason} ({scrape_note})"
    else:
        selection_reason = f"{reason} (reconcile run -- {scrape_note}, no new pick generated)"

    final_predictions = storage.read_rows(predictions_path, config.PREDICTIONS_FIELDNAMES)
    final_predictions = tracker.reconcile(final_predictions, draws_by_id)
    storage.atomic_write_csv(predictions_path, config.PREDICTIONS_FIELDNAMES, final_predictions)

    if mode == "predict":
        tonight_pick = {
            "target_draw_id": target_draw_id,
            "target_date": today.isoformat(),
            "predicted_combo": pick["predicted_combo"],
            "predicted_digits_sorted": pick["predicted_digits_sorted"],
        }
    else:
        existing_pick_row = next(
            (p for p in final_predictions if p["target_draw_id"] == target_draw_id), None
        )
        if existing_pick_row:
            tonight_pick = {
                "target_draw_id": existing_pick_row["target_draw_id"],
                "target_date": existing_pick_row["target_date"],
                "predicted_combo": existing_pick_row["predicted_combo"],
                "predicted_digits_sorted": existing_pick_row["predicted_digits_sorted"],
            }
        else:
            tonight_pick = {
                "target_draw_id": target_draw_id,
                "target_date": today.isoformat(),
                "predicted_combo": "n/a -- run predict mode first",
                "predicted_digits_sorted": "n/a",
            }

    fairness_position = fairness.per_position_chi_square(history) if history else {}
    fairness_pattern = (
        fairness.pattern_split_chi_square(history) if history
        else {"statistic": 0.0, "p_value": 1.0, "observed": {}}
    )

    context = dashboard.build_context(
        history=history,
        predictions=final_predictions,
        model_table=model_table,
        selected_model_name=selected_name,
        selection_reason=selection_reason,
        tonight_pick=tonight_pick,
        fairness_position=fairness_position,
        fairness_pattern=fairness_pattern,
        generated_at=dt.datetime.now(dt.timezone.utc).isoformat(),
    )

    print(dashboard.render_console(context))
    (data_dir / "last_report.md").write_text(dashboard.render_markdown(context))
    (docs_dir / "index.html").write_text(dashboard.render_html(context))
    (docs_dir / "today.json").write_text(json.dumps(dashboard.render_json(context), indent=2))

    return context


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["predict", "reconcile"], default="predict")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    run(mode=args.mode)
