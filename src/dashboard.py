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


_ICON_TARGET = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.2" fill="currentColor"/></svg>'
_ICON_TROPHY = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M7 4h10v4a5 5 0 0 1-10 0V4Z"/><path d="M7 6H4.5A1.5 1.5 0 0 0 3 7.5 3.5 3.5 0 0 0 7 11"/><path d="M17 6h2.5A1.5 1.5 0 0 1 21 7.5 3.5 3.5 0 0 1 17 11"/><path d="M9 17h6M12 13v6"/></svg>'
_ICON_WALLET = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="3" y="6" width="18" height="13" rx="2.5"/><path d="M3 10h18"/><circle cx="16.5" cy="14.5" r="1.2" fill="currentColor" stroke="none"/></svg>'
_ICON_SHIELD = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6l7-3Z"/><path d="m9 12 2 2 4-4"/></svg>'
_ICON_BRAIN = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M9 3a3 3 0 0 0-3 3v1a3 3 0 0 0-2 5 3 3 0 0 0 2 5v1a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3Z"/><path d="M15 3a3 3 0 0 1 3 3v1a3 3 0 0 1 2 5 3 3 0 0 1-2 5v1a3 3 0 0 1-6 0"/></svg>'
_ICON_INFO = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/></svg>'


def _stat_card(icon: str, label: str, value: str, sub: str = "") -> str:
    sub_html = f'<div class="stat-sub">{sub}</div>' if sub else ""
    return f"""<div class="card stat-card">
<div class="stat-icon">{icon}</div>
<div class="stat-label">{label}</div>
<div class="stat-value">{value}</div>
{sub_html}</div>"""


def render_html(ctx: dict) -> str:
    pnl = ctx["pnl"]
    win = ctx["win_record"]
    net_class = "pos" if pnl["net_pnl"] >= 0 else "neg"
    model_rows = "".join(
        f'<div class="model-row{" model-row--selected" if name == ctx["selected_model_name"] else ""}">'
        f'<span class="model-name">{name}</span>'
        f'<span class="model-metric">{f"{stats["mean_logloss"]:.4f}" if stats["n_scored"] else "n/a"}</span>'
        f"</div>"
        for name, stats in ctx["model_table"].items()
    )
    fairness_rows = "".join(
        f'<div class="fair-row"><span>{pos}</span><span>p = {stats["p_value"]:.4f}</span></div>'
        for pos, stats in ctx["fairness_position"].items()
    )

    last_result = ctx["last_result"]
    if last_result:
        last_result_value = last_result["draw_id"]
        last_result_sub = f"{last_result['combo']} ({last_result['pattern']})"
    else:
        last_result_value = "n/a"
        last_result_sub = "no draws on file yet"

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>UAE Pick 3 · Any 6 Tracker</title>
<style>
:root {{
  --bg-deep: #0a0a14; --bg-mid: #1a0b2e; --bg-glow: #2d1b4e;
  --violet: #7c3aed; --pink: #f472b6; --orange: #fb923c; --cyan: #22d3ee;
  --surface: rgba(255,255,255,0.045); --border: rgba(255,255,255,0.09);
  --fg: #f4f3f8; --fg-muted: #a9a5bd;
  --pos: #34d399; --neg: #fb7185;
  --radius: 20px;
}}
* {{ box-sizing: border-box; }}
html {{ -webkit-text-size-adjust: 100%; }}
body {{
  margin: 0; min-height: 100dvh; color: var(--fg);
  font: 16px/1.5 -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  background: radial-gradient(circle at 15% -10%, rgba(124,58,237,0.35), transparent 45%),
              radial-gradient(circle at 110% 15%, rgba(244,114,182,0.25), transparent 40%),
              radial-gradient(circle at 50% 110%, rgba(34,211,238,0.12), transparent 45%),
              linear-gradient(160deg, var(--bg-deep) 0%, var(--bg-mid) 55%, var(--bg-glow) 100%);
  overflow-x: hidden;
}}
.wrap {{ max-width: 480px; margin: 0 auto; padding: 20px 16px 40px; position: relative; }}
.deco {{ position: absolute; pointer-events: none; opacity: 0.5; z-index: 0; }}
.deco--tri {{ top: 18px; right: 8px; width: 64px; height: 64px; }}
.deco--ring {{ bottom: 120px; left: -30px; width: 140px; height: 140px; border: 1.5px solid rgba(124,58,237,0.35); border-radius: 28px; transform: rotate(18deg); }}
.content {{ position: relative; z-index: 1; }}
.topbar {{ display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; margin-bottom: 18px; }}
.brand {{ font-size: 13px; font-weight: 700; letter-spacing: 0.06em; color: var(--fg-muted); text-transform: uppercase; }}
.pill {{ display: inline-flex; align-items: center; gap: 6px; padding: 6px 12px; border-radius: 999px; background: var(--surface); border: 1px solid var(--border); font-size: 12px; color: var(--fg-muted); white-space: nowrap; }}
.pill-dot {{ width: 6px; height: 6px; border-radius: 50%; background: var(--orange); box-shadow: 0 0 8px var(--orange); }}
.hero {{ text-align: center; padding: 28px 16px 24px; }}
.hero-eyebrow {{ font-size: 13px; color: var(--fg-muted); margin-bottom: 10px; }}
.hero-pick {{
  font-size: 56px; font-weight: 800; letter-spacing: 0.08em; margin: 4px 0 12px; line-height: 1;
  background: linear-gradient(90deg, var(--cyan), var(--violet) 45%, var(--pink) 75%, var(--orange));
  -webkit-background-clip: text; background-clip: text; color: transparent;
}}
.hero-meta {{ display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; margin-top: 6px; }}
.card {{
  background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius);
  padding: 18px; margin: 14px 0; backdrop-filter: blur(18px); -webkit-backdrop-filter: blur(18px);
  box-shadow: 0 8px 32px rgba(0,0,0,0.35);
}}
.stats-grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin: 18px 0; }}
.stat-card {{ padding: 14px 10px; text-align: center; margin: 0; }}
.stat-icon {{ width: 34px; height: 34px; margin: 0 auto 8px; border-radius: 12px; display: flex; align-items: center; justify-content: center; background: linear-gradient(135deg, rgba(124,58,237,0.35), rgba(244,114,182,0.25)); color: #fff; }}
.stat-icon svg {{ width: 18px; height: 18px; }}
.stat-label {{ font-size: 11px; color: var(--fg-muted); text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 4px; }}
.stat-value {{ font-size: 17px; font-weight: 700; overflow-wrap: anywhere; }}
.stat-sub {{ font-size: 11px; color: var(--fg-muted); margin-top: 2px; overflow-wrap: anywhere; }}
.section-title {{ display: flex; align-items: center; gap: 8px; font-size: 13px; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase; color: var(--fg-muted); margin-bottom: 12px; }}
.section-title svg {{ width: 16px; height: 16px; color: var(--pink); }}
.model-row {{ display: flex; justify-content: space-between; align-items: center; gap: 8px; padding: 8px 10px; border-radius: 10px; font-size: 13px; }}
.model-row span {{ min-width: 0; overflow-wrap: anywhere; }}
.model-row--selected {{ background: rgba(124,58,237,0.18); border: 1px solid rgba(124,58,237,0.4); font-weight: 700; }}
.model-name {{ color: var(--fg); }}
.model-metric {{ color: var(--fg-muted); font-variant-numeric: tabular-nums; }}
.selection-note {{ font-size: 12.5px; color: var(--fg-muted); margin-top: 10px; line-height: 1.5; }}
.fair-row {{ display: flex; justify-content: space-between; gap: 8px; padding: 6px 10px; font-size: 13px; color: var(--fg-muted); }}
.fair-row span {{ min-width: 0; overflow-wrap: anywhere; }}
.fair-row span:first-child {{ color: var(--fg); }}
.net-pnl {{ font-size: 22px; font-weight: 800; }}
.net-pnl.pos {{ color: var(--pos); }}
.net-pnl.neg {{ color: var(--neg); }}
.banner {{
  display: flex; gap: 10px; align-items: flex-start; background: rgba(251,146,60,0.1);
  border: 1px solid rgba(251,146,60,0.3); border-radius: var(--radius); padding: 16px; font-size: 12.5px;
  color: #fde0c4; line-height: 1.55; margin-top: 18px;
}}
.banner svg {{ width: 18px; height: 18px; flex-shrink: 0; margin-top: 1px; color: var(--orange); }}
.footer {{ text-align: center; font-size: 11px; color: var(--fg-muted); margin-top: 20px; }}
@media (max-width: 360px) {{ .hero-pick {{ font-size: 44px; }} .stats-grid {{ grid-template-columns: 1fr 1fr; }} }}
@media (prefers-reduced-motion: no-preference) {{ .card, .stat-card {{ transition: transform 200ms ease, box-shadow 200ms ease; }} }}
</style></head>
<body>
<div class="wrap">
  <svg class="deco deco--tri" viewBox="0 0 64 64" fill="none" stroke="rgba(167,139,250,0.55)" stroke-width="1.5"><path d="M32 6 58 54H6Z"/></svg>
  <div class="deco deco--ring"></div>
  <div class="content">
    <div class="topbar">
      <span class="brand">Pick 3 · Any 6</span>
      <span class="pill"><span class="pill-dot"></span>Updated {ctx['generated_at'][11:16]} UTC</span>
    </div>

    <div class="hero">
      <div class="hero-eyebrow">Target draw {ctx['target_draw_id']} · {ctx['target_date']}</div>
      <div class="hero-pick">{ctx['predicted_combo']}</div>
      <div class="hero-meta">
        <span class="pill">Play type: Any 6</span>
        <span class="pill">Stake: AED {config.STAKE_AED}</span>
      </div>
    </div>

    <div class="stats-grid">
      {_stat_card(_ICON_TARGET, "Last Result", last_result_value, last_result_sub)}
      {_stat_card(_ICON_TROPHY, "Record", f"{win['wins']} / {win['days_resolved']}", "wins / resolved")}
      {_stat_card(_ICON_WALLET, "Net P&amp;L", f"AED {pnl['net_pnl']}", f"RTP {pnl['actual_rtp']:.1%}")}
    </div>

    <div class="card">
      <div class="section-title">{_ICON_BRAIN} Model Selection</div>
      {model_rows}
      <div class="selection-note"><strong>Selected: {ctx['selected_model_name']}</strong> — {ctx['selection_reason']}</div>
    </div>

    <div class="card">
      <div class="section-title">{_ICON_SHIELD} Fairness Audit (not a predictor)</div>
      {fairness_rows}
      <div class="fair-row"><span>pattern split</span><span>p = {ctx['fairness_pattern']['p_value']:.4f}</span></div>
    </div>

    <div class="banner">
      {_ICON_INFO}
      <div>{ctx['honesty_banner']}</div>
    </div>

    <div class="footer">Generated {ctx['generated_at']}</div>
  </div>
</div>
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
