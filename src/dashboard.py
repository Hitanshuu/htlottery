"""Builds the console report, last_report.md, and the mobile docs/ page.

Always shows the real running ~49% expected loss and the fixed honesty
banner -- this tool never claims to predict draws or beat the odds.
"""
import json

from src import config

ANY6_WIN_PROBABILITY = 6 / 1000
THEORETICAL_RTP = config.PAYOUT_AED * ANY6_WIN_PROBABILITY / config.STAKE_AED

HONESTY_BANNER = (
    "Pick 3 is i.i.d. uniform. This pick does not beat the odds. "
    "Expected return ≈ 51% (≈49% expected loss). "
    "For entertainment; play at most AED 5/day."
)

LOGLOSS_SCOPE_NOTE = (
    "Log-loss computed over distinct-digit (ABC) draws only (~72% of days) -- "
    "non-distinct draws fall outside the Any-6 outcome space and always result "
    "in a loss for this play type."
)


def pnl_summary(predictions: list[dict]) -> dict:
    """Real running P&L: days played, staked, won, net, actual vs theoretical RTP, expected vs actual wins."""
    days_played = len(predictions)
    total_staked = sum(int(p["stake"]) for p in predictions if p.get("stake"))
    resolved = [p for p in predictions if p.get("won") not in ("", None)]
    total_won = sum(int(p["payout"]) for p in resolved if p.get("payout"))
    net_pnl = total_won - total_staked
    actual_rtp = (total_won / total_staked) if total_staked else 0.0
    actual_wins = sum(1 for p in resolved if p["won"] == "True")
    expected_wins = len(resolved) * ANY6_WIN_PROBABILITY
    return {
        "days_played": days_played,
        "total_staked": total_staked,
        "total_won": total_won,
        "net_pnl": net_pnl,
        "actual_rtp": actual_rtp,
        "theoretical_rtp": THEORETICAL_RTP,
        "resolved_days": len(resolved),
        "actual_wins": actual_wins,
        "expected_wins": expected_wins,
    }


def win_record(predictions: list[dict]) -> dict:
    """Running win/loss record over resolved (settled) days only."""
    resolved = [p for p in predictions if p.get("won") not in ("", None)]
    wins = sum(1 for p in resolved if p["won"] == "True")
    return {"wins": wins, "days_resolved": len(resolved)}


def build_context(
    history: list[dict],
    predictions: list[dict],
    model_table: dict,
    selected_model_name: str,
    selection_reason: str,
    tonight_pick: dict,
    fairness_position: dict,
    fairness_pattern: dict,
    generated_at: str,
) -> dict:
    """Assemble all data the three renderers need into one plain dict."""
    last_draw = history[-1] if history else None
    return {
        "generated_at": generated_at,
        "history_count": len(history),
        "first_draw_date": str(history[0]["draw_date"]) if history else None,
        "last_draw_date": str(last_draw["draw_date"]) if last_draw else None,
        "last_result": (
            {
                "draw_id": last_draw["draw_id"],
                "combo": f"{last_draw['d1']}-{last_draw['d2']}-{last_draw['d3']}",
                "pattern": last_draw["pattern"],
            }
            if last_draw else None
        ),
        "win_record": win_record(predictions),
        "model_table": model_table,
        "selected_model_name": selected_model_name,
        "selection_reason": selection_reason,
        "target_draw_id": tonight_pick["target_draw_id"],
        "target_date": tonight_pick["target_date"],
        "predicted_combo": tonight_pick["predicted_combo"],
        "predicted_digits_sorted": tonight_pick["predicted_digits_sorted"],
        "pnl": pnl_summary(predictions),
        "fairness_position": fairness_position,
        "fairness_pattern": fairness_pattern,
        "honesty_banner": HONESTY_BANNER,
        "logloss_scope_note": LOGLOSS_SCOPE_NOTE,
    }


def _format_last_result(last_result: dict | None) -> str:
    if last_result is None:
        return "no draws on file yet"
    return f"{last_result['draw_id']}: {last_result['combo']} ({last_result['pattern']})"


def _model_table_lines(model_table: dict) -> list[str]:
    lines = []
    for name, stats in model_table.items():
        n = stats["n_scored"]
        ll = f"{stats['mean_logloss']:.4f}" if n else "n/a"
        hr = f"{stats['top1_hit_rate']:.4%}" if n else "n/a"
        lines.append(f"{name}: log-loss={ll}, top1_hit_rate={hr}, n_scored={n}")
    return lines


def render_console(ctx: dict) -> str:
    lines = [
        "=== UAE Pick 3 Any-6 Tracker ===",
        f"Generated: {ctx['generated_at']}",
        "",
        "-- History --",
        f"Draws on file: {ctx['history_count']} ({ctx['first_draw_date']} to {ctx['last_draw_date']})",
        f"Last result: {_format_last_result(ctx['last_result'])}",
        "",
        "-- Reconciliation --",
        f"Record: {ctx['win_record']['wins']} wins / {ctx['win_record']['days_resolved']} days resolved",
        "",
        "-- Model Selection --",
        *_model_table_lines(ctx["model_table"]),
        f"Selected: {ctx['selected_model_name']} -- {ctx['selection_reason']}",
        ctx["logloss_scope_note"],
        "",
        "-- TONIGHT'S PICK --",
        f"Play type: Any 6 | Target draw: {ctx['target_draw_id']} ({ctx['target_date']}) | Stake: AED {config.STAKE_AED}",
        f"Pick: {ctx['predicted_combo']} (matches if drawn digits sort to {ctx['predicted_digits_sorted']})",
        "",
        "-- P&L Ledger --",
        f"Days played: {ctx['pnl']['days_played']} | Staked: AED {ctx['pnl']['total_staked']} | Won: AED {ctx['pnl']['total_won']}",
        f"Net P&L: AED {ctx['pnl']['net_pnl']} | Actual RTP: {ctx['pnl']['actual_rtp']:.2%} vs theoretical {ctx['pnl']['theoretical_rtp']:.2%}",
        f"Expected wins: {ctx['pnl']['expected_wins']:.3f} | Actual wins: {ctx['pnl']['actual_wins']}",
        "",
        "-- Fairness Audit (not a predictor) --",
        *(f"{pos}: p={stats['p_value']:.4f}" for pos, stats in ctx["fairness_position"].items()),
        f"pattern split: p={ctx['fairness_pattern']['p_value']:.4f}",
        "",
        ctx["honesty_banner"],
    ]
    return "\n".join(lines)


def render_markdown(ctx: dict) -> str:
    lines = [
        "# UAE Pick 3 Any-6 Tracker",
        f"_Generated: {ctx['generated_at']}_",
        "",
        "## History",
        f"- Draws on file: {ctx['history_count']} ({ctx['first_draw_date']} to {ctx['last_draw_date']})",
        f"- Last result: {_format_last_result(ctx['last_result'])}",
        "",
        "## Reconciliation",
        f"- Record: {ctx['win_record']['wins']} wins / {ctx['win_record']['days_resolved']} days resolved",
        "",
        "## Model Selection",
        *(f"- {line}" for line in _model_table_lines(ctx["model_table"])),
        f"- **Selected:** {ctx['selected_model_name']} -- {ctx['selection_reason']}",
        f"- {ctx['logloss_scope_note']}",
        "",
        "## Tonight's Pick",
        f"- Play type: **Any 6** | Target draw: **{ctx['target_draw_id']}** ({ctx['target_date']}) | Stake: AED {config.STAKE_AED}",
        f"- Pick: **{ctx['predicted_combo']}**",
        "",
        "## P&L Ledger",
        f"- Days played: {ctx['pnl']['days_played']} | Staked: AED {ctx['pnl']['total_staked']} | Won: AED {ctx['pnl']['total_won']}",
        f"- Net P&L: AED {ctx['pnl']['net_pnl']} | Actual RTP: {ctx['pnl']['actual_rtp']:.2%} vs theoretical {ctx['pnl']['theoretical_rtp']:.2%}",
        f"- Expected wins: {ctx['pnl']['expected_wins']:.3f} | Actual wins: {ctx['pnl']['actual_wins']}",
        "",
        "## Fairness Audit (not a predictor)",
        *(f"- {pos}: p={stats['p_value']:.4f}" for pos, stats in ctx["fairness_position"].items()),
        f"- pattern split: p={ctx['fairness_pattern']['p_value']:.4f}",
        "",
        f"> {ctx['honesty_banner']}",
        "",
    ]
    return "\n".join(lines)


def render_html(ctx: dict) -> str:
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>UAE Pick 3 Any-6 Tracker</title>
<style>
body {{ font-family: -apple-system, sans-serif; margin: 0; padding: 16px; background: #111; color: #eee; }}
.pick {{ font-size: 48px; font-weight: 700; text-align: center; letter-spacing: 4px; margin: 8px 0; }}
.meta {{ text-align: center; color: #aaa; margin-bottom: 4px; }}
.updated {{ text-align: center; color: #f5a623; font-weight: 600; margin-bottom: 16px; }}
.card {{ background: #1c1c1c; border-radius: 12px; padding: 12px 16px; margin: 12px 0; }}
.banner {{ background: #2a1a1a; border: 1px solid #663; padding: 12px; border-radius: 8px; font-size: 14px; }}
</style></head>
<body>
<div class="updated">Last updated: {ctx['generated_at']}</div>
<div class="meta">Play type: Any 6 | Target draw {ctx['target_draw_id']} | {ctx['target_date']}</div>
<div class="pick">{ctx['predicted_combo']}</div>
<div class="meta">Stake: AED {config.STAKE_AED}</div>
<div class="card">
<strong>Last result:</strong> {_format_last_result(ctx['last_result'])}<br>
<strong>Record:</strong> {ctx['win_record']['wins']} wins / {ctx['win_record']['days_resolved']} days resolved<br>
<strong>Net P&amp;L:</strong> AED {ctx['pnl']['net_pnl']} (RTP {ctx['pnl']['actual_rtp']:.2%} vs theoretical {ctx['pnl']['theoretical_rtp']:.2%})
</div>
<div class="banner">{ctx['honesty_banner']}</div>
</body></html>
"""


def render_json(ctx: dict) -> dict:
    return {
        "generated_at": ctx["generated_at"],
        "target_draw_id": ctx["target_draw_id"],
        "target_date": ctx["target_date"],
        "predicted_combo": ctx["predicted_combo"],
        "predicted_digits_sorted": ctx["predicted_digits_sorted"],
        "play_type": "Any 6",
        "stake": config.STAKE_AED,
        "last_result": ctx["last_result"],
        "win_record": ctx["win_record"],
        "pnl": ctx["pnl"],
        "selected_model_name": ctx["selected_model_name"],
        "selection_reason": ctx["selection_reason"],
        "honesty_banner": ctx["honesty_banner"],
    }
