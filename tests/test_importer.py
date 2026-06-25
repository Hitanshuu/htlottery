import datetime as dt

import pytest

from src import importer, storage


def test_parse_line_draw_id_csv_shape():
    record = importer.parse_line("260623,4,2,7")
    assert record["draw_id"] == "260623"
    assert (record["d1"], record["d2"], record["d3"]) == (4, 2, 7)
    assert record["draw_date"] == "2026-06-23"
    assert record["pattern"] == "ABC"
    assert record["source"] == "manual"


def test_parse_line_date_combo_csv_shape():
    record = importer.parse_line("2026-06-23,4-2-7")
    assert record["draw_id"] == "260623"
    assert (record["d1"], record["d2"], record["d3"]) == (4, 2, 7)


def test_parse_line_freeform_text_with_dashes():
    record = importer.parse_line("23 Jun 2026 - 4-2-7")
    assert record["draw_id"] == "260623"
    assert (record["d1"], record["d2"], record["d3"]) == (4, 2, 7)


def test_parse_line_draw_id_colon_bare_digits():
    record = importer.parse_line("260623: 427")
    assert record["draw_id"] == "260623"
    assert (record["d1"], record["d2"], record["d3"]) == (4, 2, 7)


def test_parse_line_rejects_unparseable_garbage():
    assert importer.parse_line("hello world, nothing here") is None


def test_parse_line_rejects_blank_line():
    assert importer.parse_line("   ") is None


def test_parse_line_rejects_comment_line():
    assert importer.parse_line("# this is a comment") is None


def test_parse_line_rejects_future_date():
    assert importer.parse_line("991231,4,2,7") is None


def test_parse_line_rejects_invalid_calendar_date():
    assert importer.parse_line("260230,4,2,7") is None


def test_import_history_text_summary_counts(tmp_path):
    draws_path = tmp_path / "draws.csv"
    raw_text = (
        "260621,4,2,7\n"
        "260622,1,1,1\n"
        "not a real line at all\n"
        "260621,4,2,7\n"  # duplicate of first
    )
    summary = importer.import_history_text(raw_text, draws_path)
    assert summary["rows_read"] == 4
    assert summary["added"] == 2
    assert summary["skipped_duplicate"] == 1
    assert summary["rejected_invalid"] == 1


def test_import_history_text_merges_into_draws_csv(tmp_path):
    from src import config
    draws_path = tmp_path / "draws.csv"
    importer.import_history_text("260621,4,2,7\n260622,1,1,1\n", draws_path)
    rows = storage.read_rows(draws_path, config.DRAWS_FIELDNAMES)
    assert {r["draw_id"] for r in rows} == {"260621", "260622"}
