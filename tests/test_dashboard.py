import datetime as dt

from src import config, dashboard

HONESTY_BANNER = (
    "Pick 3 is i.i.d. uniform. This pick does not beat the odds. "
    "Expected return ≈ 51% (≈49% expected loss). "
    "For entertainment; play at most AED 5/day."
)


def _resolved(target_draw_id, won):
    return {
        "target_draw_id": target_draw_id, "target_date": "2026-06-23",
        "predicted_combo": "4-2-7", "predicted_digits_sorted": "2-4-7",
        "play_type": "Any 6", "model_used": "UniformBaseline", "model_logloss": "",
        "baseline_logloss": "", "stake": "5", "generated_at": "2026-06-23T00:00:00+00:00",
        "actual_combo": "4-2-7" if won else "9-9-9", "won": str(won), "payout": "425" if won else "0",
        "cum_stake": "", "cum_payout": "", "cum_pnl": "",
    }


def _pending(target_draw_id):
    return {
        "target_draw_id": target_draw_id, "target_date": "2026-06-24",
        "predicted_combo": "4-2-7", "predicted_digits_sorted": "2-4-7",
        "play_type": "Any 6", "model_used": "UniformBaseline", "model_logloss": "",
        "baseline_logloss": "", "stake": "5", "generated_at": "2026-06-24T00:00:00+00:00",
        "actual_combo": "", "won": "", "payout": "",
        "cum_stake": "", "cum_payout": "", "cum_pnl": "",
    }


def test_pnl_summary_counts_resolved_and_pending_correctly():
    predictions = [_resolved("260621", True), _resolved("260622", False), _pending("260623")]
    summary = dashboard.pnl_summary(predictions)
    assert summary["days_played"] == 3
    assert summary["total_staked"] == 15
    assert summary["total_won"] == 425
    assert summary["net_pnl"] == 410
    assert summary["actual_rtp"] == 425 / 15
    assert summary["resolved_days"] == 2
    assert summary["actual_wins"] == 1
    assert abs(summary["expected_wins"] - 2 * (6 / 1000)) < 1e-9


def test_win_record_reports_wins_over_resolved_days():
    predictions = [_resolved("260621", True), _resolved("260622", False), _pending("260623")]
    record = dashboard.win_record(predictions)
    assert record["wins"] == 1
    assert record["days_resolved"] == 2


def test_render_outputs_contain_honesty_banner_and_required_sections():
    context = dashboard.build_context(
        history=[{"draw_id": "260622", "draw_date": dt.date(2026, 6, 22), "d1": 4, "d2": 2, "d3": 7, "pattern": "ABC"}],
        predictions=[_resolved("260621", True), _pending("260622")],
        model_table={"UniformBaseline": {"mean_logloss": 4.787, "top1_hit_rate": 0.0, "n_scored": 0}},
        selected_model_name="UniformBaseline",
        selection_reason="insufficient data to validate any candidate -- defaulting to chance",
        tonight_pick={"target_draw_id": "260623", "target_date": "2026-06-23",
                      "predicted_combo": "4-2-7", "predicted_digits_sorted": "2-4-7"},
        fairness_position={"d1": {"statistic": 1.0, "p_value": 0.9, "observed": {d: 0 for d in range(10)}}},
        fairness_pattern={"statistic": 1.0, "p_value": 0.9, "observed": {"AAA": 0, "AAB": 0, "ABC": 1}},
        generated_at="2026-06-23T00:00:00+00:00",
    )
    console_text = dashboard.render_console(context)
    markdown_text = dashboard.render_markdown(context)
    html_text = dashboard.render_html(context)
    json_data = dashboard.render_json(context)

    for text in (console_text, markdown_text, html_text):
        assert HONESTY_BANNER in text
        assert "260623" in text  # tonight's target draw id
        assert "Any 6" in text
        assert "AED 5" in text

    assert json_data["target_draw_id"] == "260623"
    assert json_data["predicted_combo"] == "4-2-7"
    assert json_data["honesty_banner"] == HONESTY_BANNER
