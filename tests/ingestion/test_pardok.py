"""Tests for PARDOK XML parsing."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

from berliner_verwaltung.ingestion.pardok.crawler import parse_pardok_xml


def test_parse_pardok_xml(tmp_path: Path) -> None:
    xml = dedent("""\
    <?xml version="1.0" encoding="utf-8" ?>
    <Export aktualisiert="2026-01-01T00:00:00">
        <Vorgang>
            <VNr>V-100</VNr>
            <VFunktion>delete</VFunktion>
            <VID>V-100</VID>
        </Vorgang>
        <Vorgang>
            <VID>V-100</VID>
            <VNr>V-100</VNr>
            <VTyp>Anfrage</VTyp>
            <VTypL>Anfrage</VTypL>
            <VSys>2800</VSys>
            <VSysL>Bauwesen</VSysL>
            <Nebeneintrag>
                <Desk>Friedrichshain-Kreuzberg</Desk>
            </Nebeneintrag>
            <Dokument>
                <DBID>D-101</DBID>
                <DokArt>Drs</DokArt>
                <DokTyp>SchrAnfr</DokTyp>
                <DokNr>19/1234</DokNr>
                <Titel>Spielplatz am Kotti</Titel>
                <DokDat>01.03.2024</DokDat>
                <Urheber>Test, Person (SPD)</Urheber>
            </Dokument>
        </Vorgang>
        <Vorgang>
            <VID>V-200</VID>
            <VNr>V-200</VNr>
            <VTyp>Gesetzgebung</VTyp>
            <Nebeneintrag>
                <Desk>Steuer</Desk>
            </Nebeneintrag>
        </Vorgang>
    </Export>
    """)
    xml_path = tmp_path / "test.xml"
    xml_path.write_text(xml)

    vorgaenge, dokumente = parse_pardok_xml(xml_path)

    assert len(vorgaenge) == 2
    assert vorgaenge[0]["vorgang_id"] == "V-100"
    assert vorgaenge[0]["is_fhk"] is True
    assert vorgaenge[0]["vorgang_typ"] == "Anfrage"
    assert vorgaenge[1]["is_fhk"] is False

    assert len(dokumente) == 1
    assert dokumente[0]["dok_nr"] == "19/1234"
    assert dokumente[0]["titel"] == "Spielplatz am Kotti"
    assert dokumente[0]["urheber"] == "Test, Person (SPD)"
