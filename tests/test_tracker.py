from src import tracker


def _prediction(target_draw_id, predicted_digits_sorted, actual_combo="", won="", payout="",
                 cum_stake="", cum_payout="", cum_pnl=""):
    return {
        "target_draw_id": target_draw_id, "target_date": "2026-06-23",
        "predicted_combo": "4-2-7", "predicted_digits_sorted": predicted_digits_sorted,
        "play_type": "Any 6", "model_used": "UniformBaseline", "model_logloss": "",
        "baseline_logloss": "", "stake": "5", "generated_at": "2026-06-23T00:00:00+00:00",
        "actual_combo": actual_combo, "won": won, "payout": payout,
        "cum_stake": cum_stake, "cum_payout": cum_payout, "cum_pnl": cum_pnl,
    }


def _draw(draw_id, d1, d2, d3):
    return {"draw_id": draw_id, "d1": d1, "d2": d2, "d3": d3}


def test_reconcile_fills_win_and_payout_on_match():
    predictions = [_prediction("260623", "2-4-7")]
    draws_by_id = {"260623": _draw("260623", 4, 2, 7)}  # sorted -> 2-4-7, matches
    reconciled = tracker.reconcile(predictions, draws_by_id)
    row = reconciled[0]
    assert row["won"] == "True"
    assert row["payout"] == "425"
    assert row["actual_combo"] == "4-2-7"


def test_reconcile_fills_loss_and_zero_payout_on_no_match():
    predictions = [_prediction("260623", "1-2-3")]
    draws_by_id = {"260623": _draw("260623", 4, 2, 7)}
    reconciled = tracker.reconcile(predictions, draws_by_id)
    row = reconciled[0]
    assert row["won"] == "False"
    assert row["payout"] == "0"


def test_reconcile_leaves_unmatched_predictions_pending():
    predictions = [_prediction("260699", "1-2-3")]  # no draw yet
    reconciled = tracker.reconcile(predictions, draws_by_id={})
    row = reconciled[0]
    assert row["won"] == ""
    assert row["actual_combo"] == ""


def test_reconcile_computes_cumulative_pnl_in_chronological_order():
    predictions = [
        _prediction("260621", "2-4-7"),  # win, 4-2-7 -> matches
        _prediction("260622", "1-2-3"),  # loss
    ]
    draws_by_id = {
        "260621": _draw("260621", 4, 2, 7),
        "260622": _draw("260622", 9, 8, 7),
    }
    reconciled = tracker.reconcile(predictions, draws_by_id)
    row1, row2 = reconciled
    assert row1["cum_stake"] == "5"
    assert row1["cum_payout"] == "425"
    assert row1["cum_pnl"] == "420"
    assert row2["cum_stake"] == "10"
    assert row2["cum_payout"] == "425"
    assert row2["cum_pnl"] == "415"


def test_reconcile_skips_already_reconciled_rows_idempotently():
    already_done = _prediction("260621", "2-4-7", actual_combo="4-2-7", won="True", payout="425",
                                cum_stake="5", cum_payout="425", cum_pnl="420")
    reconciled = tracker.reconcile([already_done], draws_by_id={})
    assert reconciled[0] == already_done
