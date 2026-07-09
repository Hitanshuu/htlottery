# UAE Pick 3 Any-6 Tracker

A small, honest tool for tracking a fixed AED 5/day "Any 6" play on the UAE
Lottery Pick 3 draw. It does **not** predict anything -- Pick 3 draws are
i.i.d. uniform over 000-999, and no model here claims otherwise. It exists to:

- track real results and a real running P&L (expected RTP ≈ 51%, i.e. ≈49%
  expected loss over time),
- run a genuinely empirical model-selection pipeline that almost always
  (correctly) concludes nothing beats chance, and
- give you a one-glance phone page each evening before the 21:30 draw.

## How it runs

Everything is orchestrated by `run_daily.py`, run **twice a day** by GitHub
Actions (`.github/workflows/daily.yml`) so the pick is always ready before you
buy a ticket and the P&L is never a day stale:

- **19:30 Asia/Dubai (15:30 UTC) -- `--mode predict`**: scrapes/reconciles
  whatever's on file, then generates and upserts **tonight's pick** for
  today's draw. Open the phone page around 20:00-20:30 Dubai time and buy
  your AED 5 ticket for the number shown.
- **22:30 Asia/Dubai (18:30 UTC) -- `--mode reconcile`**: after the 21:30
  draw has landed, scrapes the real result, settles today's prediction
  (win/loss + payout), and refreshes cumulative P&L. It never regenerates or
  overwrites the pick you already played.

The same script works identically locally and in CI -- there's no
GitHub-only code path.

Each **predict** run, in order:

1. Imports `data/history_raw.csv`/`.txt` if present (see format below).
2. Scrapes the latest results (see **Data sources** below), validates them,
   and appends anything new to `data/draws.csv` (deduplicated by draw_id).
3. Reconciles any past predictions in `data/predictions.csv` against real
   results now on file, updating win/loss and cumulative P&L.
4. Re-trains and selects a model via walk-forward validation over the full
   history (almost always: `UniformBaseline -- no candidate beat chance`).
5. Generates tonight's pick (seeded deterministically by the target draw id)
   and upserts the pending row in `data/predictions.csv`.
6. Prints the dashboard to the console and writes `data/last_report.md` and
   the phone page (`docs/index.html` + `docs/today.json`).

Each **reconcile** run does steps 1-3 and 6 only -- it skips model
selection and pick generation entirely, so today's already-placed pick is
left untouched even though the draw result (and thus the win/loss outcome)
has just landed.

You can also trigger either mode manually from the Actions tab
(`workflow_dispatch` → choose `predict` or `reconcile`).

The repo **is** the database: the workflow commits `data/*.csv` and `docs/*`
back to the repo after every run. Git history is the audit trail.

## Data sources & a note on trust

The **official** site, theuaelottery.ae, is a client-rendered Vue.js SPA --
it ships an empty page and builds everything in the browser, so it cannot be
scraped with a plain HTTP request (and there's no documented public API to
anchor on). Per the project's own rules, we don't reverse-engineer an
undocumented API for this.

Instead, results come from two aggregators, tried in order:

1. **goodreturns.in** (primary) -- publishes a recent-results history table,
   anchored on the draw number (YYMMDD) and the three result digits.
2. **theuaelotteryresults.com** (fallback) -- publishes only the single
   latest draw, used when goodreturns is unreachable.

**Caveat:** these are third-party aggregators, not the lottery operator.
Their data looked internally consistent when this was built (draw numbers
increment by exactly 1 day in YYMMDD form matching the dates shown, and
their independently-listed Any-6 prize, AED 425, matches this project's
configured payout exactly) -- but that's a consistency check, not a
guarantee. Spot-check your physical ticket against the operator's own
published result occasionally.

If every source fails on a given run, the run does **not** fail -- it logs a
warning, skips the append, and proceeds to reconcile/predict from existing
history. The dashboard's "last updated" timestamp is your staleness alarm.

## Manual history import

Drop a file at `data/history_raw.csv` (or `.txt`) and the next run will
import it automatically. The importer is tolerant of loosely-formatted,
freeform pasted text -- it scans each line for a date-like token and a
3-digit combo, in any of these shapes:

```
260623,4,2,7              # draw_id,d1,d2,d3
2026-06-23,4-2-7          # ISO date,combo
23 Jun 2026 - 4-2-7       # freeform text with a date and a dashed combo
260623: 427               # draw_id, colon, bare 3-digit run
```

Lines that don't parse, or that decode to an invalid/future date, are
rejected and logged -- never fabricated or guessed. The importer prints a
summary of rows read / added / skipped-as-duplicate / rejected-as-invalid
every time it runs, and re-importing the same file is safe (deduplicated by
draw_id).

## Setting up your own copy

1. **Clone and install:**
   ```bash
   python3.11 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. **Run it locally** (creates `data/` and `docs/` on first run if missing):
   ```bash
   python run_daily.py --mode predict
   python run_daily.py --mode reconcile
   ```
3. **Enable GitHub Pages** so the phone page goes live:
   Settings → Pages → Source: **Deploy from a branch** → Branch: **main**,
   folder: **/docs**. Your phone page will be at
   `https://<your-username>.github.io/<repo-name>/`.
4. **Trigger the first scheduled run manually** (don't wait for the cron):
   Actions tab → "Pick 3 predict + reconcile" → Run workflow → pick `predict`
   → Run workflow. You can also do this from the GitHub mobile app (Actions
   tab → workflow → ▶).
5. After that, it runs itself daily at 19:30 and 22:30 Asia/Dubai (predict,
   then reconcile). Bookmark the Pages URL on your phone.

## Running tests

```bash
pytest
```

## Project structure

```
data/                # draws.csv, predictions.csv, your history_raw.csv, last_report.md
docs/                # index.html + today.json -> served by GitHub Pages
src/
  config.py          # constants (payout, stake, timezone, source URLs)
  storage.py         # atomic + idempotent CSV read/write, dedup, upsert
  scraper.py         # adapter-per-source fetch + validation
  importer.py        # tolerant manual history import
  models.py          # the 5 candidate models
  backtest.py        # walk-forward validation + honest model selection
  predict.py         # deterministic seeded pick generation
  fairness.py        # chi-square randomness audit (not a predictor)
  tracker.py          # reconciliation + P&L ledger
  dashboard.py       # console / markdown / HTML / JSON report builder
run_daily.py         # the single daily entrypoint
.github/workflows/daily.yml
tests/
```
