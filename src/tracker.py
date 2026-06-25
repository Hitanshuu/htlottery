"""Reconciliation of predictions against real draws, and the running P&L ledger."""
from src import config


def reconcile(predictions: list[dict], draws_by_id: dict[str, dict]) -> list[dict]:
    """Fill in actual_combo/won/payout for predictions whose draw has landed, and
    recompute cumulative stake/payout/PnL in chronological (target_draw_id) order.

    Already-reconciled rows are left untouched, and recomputing cumulative
    columns on them is idempotent -- safe to call on every run.
    """
    sorted_rows = sorted(predictions, key=lambda r: r["target_draw_id"])
    result = []
    cum_stake = 0
    cum_payout = 0
    for original in sorted_rows:
        row = dict(original)
        if not row.get("actual_combo"):
            draw = draws_by_id.get(row["target_draw_id"])
            if draw is not None:
                won = sorted((draw["d1"], draw["d2"], draw["d3"])) == [
                    int(d) for d in row["predicted_digits_sorted"].split("-")
                ]
                row["actual_combo"] = f"{draw['d1']}-{draw['d2']}-{draw['d3']}"
                row["won"] = str(won)
                row["payout"] = str(config.PAYOUT_AED if won else 0)

        stake = int(row["stake"]) if row.get("stake") else config.STAKE_AED
        payout = int(row["payout"]) if row.get("payout") else 0
        cum_stake += stake
        cum_payout += payout
        row["cum_stake"] = str(cum_stake)
        row["cum_payout"] = str(cum_payout)
        row["cum_pnl"] = str(cum_payout - cum_stake)
        result.append(row)
    return result
