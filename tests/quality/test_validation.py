"""Tests for reference pattern detection in validation module."""

from berliner_verwaltung.quality.validation import OPARL_ID_PATTERN, REFERENCE_PATTERN


def test_reference_pattern_matches():
    assert REFERENCE_PATTERN.findall("Siehe DS/1234/VI und DS/0016/II") == [
        "DS/1234/VI",
        "DS/0016/II",
    ]


def test_reference_pattern_with_suffix():
    assert REFERENCE_PATTERN.findall("DS/0039-03/VI") == ["DS/0039-03/VI"]


def test_reference_pattern_no_match():
    assert REFERENCE_PATTERN.findall("Keine Referenz hier") == []


def test_oparl_id_pattern_matches():
    url = "https://www.sitzungsdienst-friedrichshain-kreuzberg.de/oi/oparl/1.0/papers.asp?id=16"
    assert OPARL_ID_PATTERN.findall(f"Quelle: {url}") == [url]


def test_oparl_id_pattern_no_match():
    assert OPARL_ID_PATTERN.findall("https://example.com/not-oparl") == []
