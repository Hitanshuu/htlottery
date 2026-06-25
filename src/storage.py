"""Atomic, idempotent CSV storage for draws.csv and predictions.csv."""
import csv
import datetime as dt
import logging
import os
import tempfile
from pathlib import Path
from typing import Iterable, Sequence

logger = logging.getLogger(__name__)


def atomic_write_csv(path: Path, fieldnames: Sequence[str], rows: Iterable[dict]) -> None:
    """Write rows to path as CSV atomically (temp file in same dir, then os.replace)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        os.replace(tmp_name, path)
    except BaseException:
        if os.path.exists(tmp_name):
            os.remove(tmp_name)
        raise


def draw_id_to_date(draw_id: str) -> dt.date:
    """Decode a 6-char YYMMDD draw_id into a date. Raises ValueError if invalid or future."""
    if not isinstance(draw_id, str) or len(draw_id) != 6 or not draw_id.isdigit():
        raise ValueError(f"draw_id must be 6 digits, got {draw_id!r}")
    yy, mm, dd = int(draw_id[0:2]), int(draw_id[2:4]), int(draw_id[4:6])
    year = 2000 + yy
    try:
        date = dt.date(year, mm, dd)
    except ValueError as exc:
        raise ValueError(f"draw_id {draw_id!r} does not decode to a real date") from exc
    today = dt.datetime.now(dt.timezone.utc).date()
    if date > today:
        raise ValueError(f"draw_id {draw_id!r} decodes to a future date {date}")
    return date


def date_to_draw_id(date: dt.date) -> str:
    """Encode a date into a 6-char YYMMDD draw_id."""
    return date.strftime("%y%m%d")


def read_rows(path: Path, fieldnames: Sequence[str]) -> list[dict]:
    """Read all rows from a CSV file. Returns [] if the file doesn't exist yet."""
    path = Path(path)
    if not path.exists():
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def append_draws(path: Path, fieldnames: Sequence[str], new_rows: Iterable[dict]) -> int:
    """Append draw rows, deduplicated by draw_id. Returns count of rows actually added."""
    existing = read_rows(path, fieldnames)
    existing_ids = {row["draw_id"] for row in existing}
    to_add = [row for row in new_rows if row["draw_id"] not in existing_ids]
    if not to_add:
        return 0
    seen = set()
    deduped_new = []
    for row in to_add:
        if row["draw_id"] not in seen:
            seen.add(row["draw_id"])
            deduped_new.append(row)
    atomic_write_csv(path, fieldnames, existing + deduped_new)
    return len(deduped_new)


def upsert_prediction(path: Path, fieldnames: Sequence[str], row: dict) -> None:
    """Insert or replace a prediction row, keyed by target_draw_id."""
    existing = read_rows(path, fieldnames)
    target_id = row["target_draw_id"]
    replaced = False
    updated_rows = []
    for existing_row in existing:
        if existing_row["target_draw_id"] == target_id:
            updated_rows.append(row)
            replaced = True
        else:
            updated_rows.append(existing_row)
    if not replaced:
        updated_rows.append(row)
    atomic_write_csv(path, fieldnames, updated_rows)


def classify_pattern(d1: int, d2: int, d3: int) -> str:
    """Classify a draw as AAA (all same), AAB (one pair), or ABC (all distinct)."""
    distinct = len({d1, d2, d3})
    if distinct == 1:
        return "AAA"
    if distinct == 2:
        return "AAB"
    return "ABC"
