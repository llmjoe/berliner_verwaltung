"""Tests for topic taxonomy and keyword classification."""

from berliner_verwaltung.enrichment.taxonomy import (
    TAXONOMY,
    TOPIC_BY_CODE,
    keyword_classify,
)


def test_taxonomy_has_topics():
    assert len(TAXONOMY) >= 10


def test_all_topics_have_keywords():
    for topic in TAXONOMY:
        assert topic.code
        assert topic.name
        assert len(topic.keywords) >= 3, f"{topic.code} has too few keywords"


def test_topic_codes_unique():
    codes = [t.code for t in TAXONOMY]
    assert len(codes) == len(set(codes))


def test_topic_by_code_lookup():
    assert "VERKEHR" in TOPIC_BY_CODE
    assert TOPIC_BY_CODE["VERKEHR"].name == "Verkehr und Mobilität"


def test_classify_verkehr():
    text = "Antrag: Radweg in der Wrangelstraße einrichten und Verkehrsberuhigung umsetzen"
    results = keyword_classify(text)
    codes = [code for code, _ in results]
    assert "VERKEHR" in codes


def test_classify_schule():
    text = "Schule an der Modersohnstraße: mehr Schulplatz und Schulbau fuer 400 Kinder"
    results = keyword_classify(text)
    codes = [code for code, _ in results]
    assert "SCHULE" in codes


def test_classify_haushalt():
    text = "Bezirkshaushalt 2024/2025: Investitionen und Zuwendungen für Jugendarbeit"
    results = keyword_classify(text)
    codes = [code for code, _ in results]
    assert "HAUSHALT" in codes


def test_classify_empty_text():
    results = keyword_classify("")
    assert results == []


def test_classify_no_match():
    results = keyword_classify("Lorem ipsum dolor sit amet")
    assert results == []


def test_classify_multi_topic():
    text = "Spielplatz Wrangelstraße: Sanierung und barrierefreier Umbau mit Bürgerbeteiligung"
    results = keyword_classify(text)
    codes = [code for code, _ in results]
    assert len(codes) >= 2
