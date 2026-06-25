"""Adapter-per-source scraper for UAE Lottery Pick 3 results.

The official site (theuaelottery.ae) is a client-rendered Vue.js SPA with no
server-rendered HTML and no discoverable public API, so it cannot be scraped
with a plain HTTP GET. Per spec, we fall back to two aggregator sources:
goodreturns.in (primary, publishes a recent-results history table) and
theuaelotteryresults.com (secondary, latest-draw-only fallback).
"""
import datetime as dt
import logging
import time
from typing import Optional

import requests
from bs4 import BeautifulSoup

from src import storage

logger = logging.getLogger(__name__)

GOODRETURNS_URL = "https://www.goodreturns.in/uae-lottery-results-pick-3.html"
AGGREGATOR2_URL = "https://theuaelotteryresults.com/"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
REQUEST_TIMEOUT_SECONDS = 15
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 2

SOURCE_PRIORITY = ["goodreturns", "aggregator2"]


class ScrapeError(Exception):
    """Raised when a source fails to fetch or parse cleanly."""


def parse_goodreturns(html: str) -> list[dict]:
    """Parse goodreturns.in's recent-results table into draw records."""
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table", class_="uae-recent-table")
    if table is None:
        raise ScrapeError("goodreturns: results table not found")

    records = []
    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 3:
            continue  # header row
        draw_id = cells[1].get_text(strip=True)
        balls = [span.get_text(strip=True) for span in cells[2].find_all("span", class_="uae-mini-ball")]
        if len(balls) != 3 or not all(b.isdigit() for b in balls):
            logger.warning("goodreturns: skipping row with unexpected ball format, draw_id=%r", draw_id)
            continue
        try:
            draw_date = storage.draw_id_to_date(draw_id)
        except ValueError:
            logger.warning("goodreturns: skipping row with invalid draw_id %r", draw_id)
            continue
        records.append({
            "draw_id": draw_id,
            "draw_date": draw_date,
            "d1": int(balls[0]),
            "d2": int(balls[1]),
            "d3": int(balls[2]),
            "source": "goodreturns.in",
        })
    return records


def parse_aggregator2(html: str) -> list[dict]:
    """Parse theuaelotteryresults.com's latest-Pick-3-result panel into a draw record."""
    soup = BeautifulSoup(html, "lxml")
    panel = soup.find(class_="uaelottery-draw-pick-3")
    if panel is None:
        raise ScrapeError("aggregator2: pick-3 panel not found")

    draw_no_chip = panel.find(string=lambda s: s and s.strip().startswith("Draw No:"))
    if draw_no_chip is None:
        raise ScrapeError("aggregator2: draw number chip not found")
    draw_id = draw_no_chip.strip().split(":", 1)[1].strip()

    balls = [span.get_text(strip=True) for span in panel.find_all(class_="uaelottery-ball--main")]
    if len(balls) != 3 or not all(b.isdigit() for b in balls):
        raise ScrapeError("aggregator2: unexpected ball format")

    try:
        draw_date = storage.draw_id_to_date(draw_id)
    except ValueError as exc:
        raise ScrapeError(f"aggregator2: invalid draw_id {draw_id!r}") from exc

    return [{
        "draw_id": draw_id,
        "draw_date": draw_date,
        "d1": int(balls[0]),
        "d2": int(balls[1]),
        "d3": int(balls[2]),
        "source": "theuaelotteryresults.com",
    }]


_SOURCE_PARSERS = {
    "goodreturns": (GOODRETURNS_URL, parse_goodreturns),
    "aggregator2": (AGGREGATOR2_URL, parse_aggregator2),
}


def validate_record(record: dict) -> bool:
    """Validate a draw record: digits 0-9, draw_id real/non-future, date consistent with draw_id."""
    try:
        for key in ("d1", "d2", "d3"):
            if not (0 <= record[key] <= 9):
                return False
        decoded_date = storage.draw_id_to_date(record["draw_id"])
    except (ValueError, KeyError, TypeError):
        return False
    if decoded_date != record["draw_date"]:
        return False
    return True


def fetch_latest(source: str) -> list[dict]:
    """Fetch and parse the given source, with retries. Raises ScrapeError on persistent failure."""
    url, parser = _SOURCE_PARSERS[source]
    last_error: Optional[Exception] = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()
            records = parser(response.text)
            return [r for r in records if validate_record(r)]
        except (requests.RequestException, ScrapeError) as exc:
            last_error = exc
            logger.warning("fetch_latest(%s) attempt %d/%d failed: %s", source, attempt, MAX_RETRIES, exc)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)
    raise ScrapeError(f"{source} failed after {MAX_RETRIES} attempts: {last_error}")


def fetch_with_fallback() -> tuple[list[dict], Optional[str]]:
    """Try each source in priority order; return (records, source_name_used) from the first success.

    Returns ([], None) if every source fails -- callers should log a warning and
    proceed with existing history rather than treat this as fatal.
    """
    for source in SOURCE_PRIORITY:
        try:
            records = fetch_latest(source)
            return records, source
        except ScrapeError as exc:
            logger.warning("Source %s failed, trying next: %s", source, exc)
    logger.warning("All scrape sources failed; proceeding with existing history only.")
    return [], None
