import datetime as dt
from pathlib import Path

import pytest

from src import scraper

FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(name):
    return (FIXTURES / name).read_text()


def test_parse_goodreturns_extracts_all_rows():
    records = scraper.parse_goodreturns(_fixture("goodreturns_sample.html"))
    assert len(records) == 3
    assert records[0]["draw_id"] == "260625"
    assert (records[0]["d1"], records[0]["d2"], records[0]["d3"]) == (1, 9, 2)
    assert records[0]["source"] == "goodreturns.in"


def test_parse_goodreturns_cross_checks_date_against_draw_id():
    records = scraper.parse_goodreturns(_fixture("goodreturns_sample.html"))
    rec = next(r for r in records if r["draw_id"] == "260623")
    assert rec["draw_date"] == dt.date(2026, 6, 23)


def test_parse_aggregator2_extracts_latest_only():
    records = scraper.parse_aggregator2(_fixture("aggregator2_sample.html"))
    assert len(records) == 1
    rec = records[0]
    assert rec["draw_id"] == "260624"
    assert (rec["d1"], rec["d2"], rec["d3"]) == (8, 5, 2)
    assert rec["source"] == "theuaelotteryresults.com"


def test_validate_record_accepts_valid_record():
    record = {"draw_id": "260623", "draw_date": dt.date(2026, 6, 23), "d1": 4, "d2": 1, "d3": 0, "source": "manual"}
    assert scraper.validate_record(record) is True


def test_validate_record_rejects_out_of_range_digit():
    record = {"draw_id": "260623", "draw_date": dt.date(2026, 6, 23), "d1": 14, "d2": 1, "d3": 0, "source": "manual"}
    assert scraper.validate_record(record) is False


def test_validate_record_rejects_date_mismatch_with_draw_id():
    record = {"draw_id": "260623", "draw_date": dt.date(2026, 6, 24), "d1": 4, "d2": 1, "d3": 0, "source": "manual"}
    assert scraper.validate_record(record) is False


def test_validate_record_rejects_future_draw_id():
    record = {"draw_id": "991231", "draw_date": dt.date(2099, 12, 31), "d1": 4, "d2": 1, "d3": 0, "source": "manual"}
    assert scraper.validate_record(record) is False


def test_validate_record_rejects_malformed_draw_id():
    record = {"draw_id": "abc123", "draw_date": dt.date(2026, 6, 23), "d1": 4, "d2": 1, "d3": 0, "source": "manual"}
    assert scraper.validate_record(record) is False


def test_fetch_with_fallback_tries_next_source_on_failure(monkeypatch):
    calls = []

    def fake_fetch_latest(source):
        calls.append(source)
        if source == "goodreturns":
            raise scraper.ScrapeError("goodreturns down")
        return [{"draw_id": "260624", "draw_date": dt.date(2026, 6, 24), "d1": 8, "d2": 5, "d3": 2, "source": "theuaelotteryresults.com"}]

    monkeypatch.setattr(scraper, "fetch_latest", fake_fetch_latest)

    records, source_used = scraper.fetch_with_fallback()

    assert calls == ["goodreturns", "aggregator2"]
    assert source_used == "aggregator2"
    assert len(records) == 1


def test_fetch_with_fallback_returns_empty_when_all_sources_fail(monkeypatch):
    def fake_fetch_latest(source):
        raise scraper.ScrapeError(f"{source} down")

    monkeypatch.setattr(scraper, "fetch_latest", fake_fetch_latest)

    records, source_used = scraper.fetch_with_fallback()

    assert records == []
    assert source_used is None
