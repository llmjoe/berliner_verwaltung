"""Tests for budget recipient extraction."""

from berliner_verwaltung.ingestion.haushalt.extractor import _parse_amount


def test_parse_amount_normal():
    assert _parse_amount("1.000") == 1000.0


def test_parse_amount_decimal():
    assert _parse_amount("18.726,32") == 18726.32


def test_parse_amount_large():
    assert _parse_amount("156.705.000") == 156705000.0


def test_parse_amount_dash():
    assert _parse_amount("—") is None


def test_parse_amount_empty():
    assert _parse_amount("") is None


def test_parse_amount_none():
    assert _parse_amount(None) is None
