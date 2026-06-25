"""Tolerant importer for manually-pasted freeform Pick 3 history."""
import datetime as dt
import logging
import re
from pathlib import Path
from typing import Optional

from dateutil import parser as dateutil_parser

from src import config, storage

logger = logging.getLogger(__name__)

_COMBO_PATTERNS = [
    re.compile(r"(?<!\d)(\d)-(\d)-(\d)(?!\d)"),
    re.compile(r"(?<!\d)(\d),\s*(\d),\s*(\d)(?!\d)"),
    re.compile(r"(?<!\d)(\d)(\d)(\d)(?!\d)"),
]
_ISO_DATE_PATTERN = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_SIX_DIGIT_PATTERN = re.compile(r"\b(\d{6})\b")


def _extract_combo(line: str):
    for pattern in _COMBO_PATTERNS:
        match = pattern.search(line)
        if match:
            return tuple(int(g) for g in match.groups()), match.span()
    return None, None


def _extract_draw_id(remainder: str) -> Optional[str]:
    match = _ISO_DATE_PATTERN.search(remainder)
    if match:
        year, month, day = (int(g) for g in match.groups())
        try:
            return storage.date_to_draw_id(dt.date(year, month, day))
        except ValueError:
            return None
    match = _SIX_DIGIT_PATTERN.search(remainder)
    if match:
        return match.group(1)
    try:
        parsed = dateutil_parser.parse(remainder, fuzzy=True, dayfirst=True)
        return storage.date_to_draw_id(parsed.date())
    except (ValueError, OverflowError, TypeError):
        return None


def parse_line(line: str) -> Optional[dict]:
    """Parse a freeform history line into a draws.csv-shaped record, or None if unparseable/invalid."""
    line = line.strip()
    if not line or line.startswith("#"):
        return None

    digits, span = _extract_combo(line)
    if digits is None or any(d > 9 for d in digits):
        return None

    remainder = line[: span[0]] + " " + line[span[1] :]
    draw_id = _extract_draw_id(remainder)
    if draw_id is None:
        return None

    try:
        date = storage.draw_id_to_date(draw_id)
    except ValueError:
        return None

    d1, d2, d3 = digits
    return {
        "draw_id": draw_id,
        "draw_date": date.isoformat(),
        "d1": d1,
        "d2": d2,
        "d3": d3,
        "combo": f"{d1}-{d2}-{d3}",
        "pattern": storage.classify_pattern(d1, d2, d3),
        "source": "manual",
        "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }


def import_history_text(raw_text: str, draws_path: Path = config.DRAWS_CSV) -> dict:
    """Parse freeform history text, merge valid records into draws.csv, and return a summary."""
    lines = [line for line in raw_text.splitlines() if line.strip()]
    parsed = []
    rejected = 0
    for line in lines:
        record = parse_line(line)
        if record is None:
            rejected += 1
        else:
            parsed.append(record)

    added = storage.append_draws(draws_path, config.DRAWS_FIELDNAMES, parsed)
    skipped_duplicate = len(parsed) - added

    summary = {
        "rows_read": len(lines),
        "added": added,
        "skipped_duplicate": skipped_duplicate,
        "rejected_invalid": rejected,
    }
    logger.info(
        "Import summary: %d read, %d added, %d duplicate, %d rejected",
        summary["rows_read"], summary["added"], summary["skipped_duplicate"], summary["rejected_invalid"],
    )
    return summary
