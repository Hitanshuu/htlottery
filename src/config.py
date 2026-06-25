"""Constants and paths shared across the Pick 3 tracker."""
from pathlib import Path
from zoneinfo import ZoneInfo

PAYOUT_AED = 425
STAKE_AED = 5
PLAY_TYPE = "Any 6"

TIMEZONE = ZoneInfo("Asia/Dubai")

OFFICIAL_SOURCE_URL = "https://www.theuaelottery.ae"
AGGREGATOR_SOURCE_URLS = [
    "https://www.goodreturns.in/uae-lottery-results-pick-3.html",
    "https://theuaelotteryresults.com/",
]

ML_LAG_DRAWS = 5

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DOCS_DIR = PROJECT_ROOT / "docs"

DRAWS_CSV = DATA_DIR / "draws.csv"
PREDICTIONS_CSV = DATA_DIR / "predictions.csv"
HISTORY_RAW_PATH_CANDIDATES = [DATA_DIR / "history_raw.csv", DATA_DIR / "history_raw.txt"]
LAST_REPORT_MD = DATA_DIR / "last_report.md"

DOCS_INDEX_HTML = DOCS_DIR / "index.html"
DOCS_TODAY_JSON = DOCS_DIR / "today.json"

DRAWS_FIELDNAMES = [
    "draw_id", "draw_date", "d1", "d2", "d3", "combo", "pattern", "source", "fetched_at",
]
PREDICTIONS_FIELDNAMES = [
    "target_draw_id", "target_date", "predicted_combo", "predicted_digits_sorted",
    "play_type", "model_used", "model_logloss", "baseline_logloss", "stake",
    "generated_at", "actual_combo", "won", "payout", "cum_stake", "cum_payout", "cum_pnl",
]
