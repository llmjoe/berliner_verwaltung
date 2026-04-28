"""Tests that real-world OParl data structures parse correctly through schemas.

Uses fixtures based on actual API responses from sitzungsdienst-friedrichshain-kreuzberg.de.
Catches edge cases: empty strings, consultation as URL, missing optional fields.
"""

from __future__ import annotations

from typing import Any

from berliner_verwaltung.ingestion.oparl.schemas import (
    OparlAgendaItem,
    OparlBody,
    OparlMeeting,
    OparlOrganization,
    OparlPaper,
    OparlPerson,
)


def test_body_with_legislative_terms(sample_body: dict[str, Any]) -> None:
    body = OparlBody.model_validate(sample_body)
    assert body.name == "BVV Friedrichshain-Kreuzberg"
    assert body.short_name == "BVV"
    assert body.legislative_term is not None
    assert len(body.legislative_term) == 1


def test_organization_empty_end_date(sample_organization: dict[str, Any]) -> None:
    """API returns '' for endDate on active organizations."""
    org = OparlOrganization.model_validate(sample_organization)
    assert org.name == "Aeltestenrat"
    assert org.end_date is None
    assert org.organization_type == "Gremium"


def test_person_with_memberships(sample_person: dict[str, Any]) -> None:
    person = OparlPerson.model_validate(sample_person)
    assert person.family_name == "Richter"
    assert person.given_name == "Claudia"
    assert len(person.membership) == 1
    assert person.membership[0]["role"] == "BV"


def test_meeting_with_agenda_items(sample_meeting: dict[str, Any]) -> None:
    meeting = OparlMeeting.model_validate(sample_meeting)
    assert meeting.name == "42. Sitzung der BVV"
    assert meeting.meeting_state == "eingeladen"
    assert len(meeting.agenda_item) == 2


def test_agenda_item_consultation_as_url(sample_meeting: dict[str, Any]) -> None:
    """Real API sends consultation as URL string, not dict."""
    ai_data = sample_meeting["agendaItem"][0]
    ai = OparlAgendaItem.model_validate(ai_data)
    assert ai.name == "Eroeffnung"
    assert ai.consultation is not None


def test_agenda_item_no_consultation(sample_meeting: dict[str, Any]) -> None:
    ai_data = sample_meeting["agendaItem"][1]
    ai = OparlAgendaItem.model_validate(ai_data)
    assert ai.name == "Genehmigung der Tagesordnung"
    assert ai.consultation is None


def test_paper_with_main_file(sample_paper: dict[str, Any]) -> None:
    paper = OparlPaper.model_validate(sample_paper)
    assert paper.reference == "DS/0016/2002"
    assert paper.paper_type == "Antrag"
    assert paper.main_file is not None
    assert paper.main_file["mimeType"] == "application/pdf"


def test_paper_with_consultation(sample_paper: dict[str, Any]) -> None:
    paper = OparlPaper.model_validate(sample_paper)
    assert len(paper.consultation) == 1
    assert paper.consultation[0]["role"] == "Vorberatung"


def test_meeting_with_broken_date() -> None:
    """API contains meetings with truncated year like '200-10-03'."""
    data = {
        "id": "https://example.org/meetings.asp?id=999",
        "type": "https://schema.oparl.org/1.0/Meeting",
        "name": "Alte Sitzung mit kaputtem Datum",
        "start": "200-10-03T18:00:00+02:00",
        "end": "200-10-03T20:30:00+02:00",
    }
    try:
        OparlMeeting.model_validate(data)
        validated = True
    except Exception:
        validated = False
    assert not validated, "Broken dates should fail validation (crawler handles via try/except)"


def test_organization_all_empty_strings() -> None:
    """Defensive: all optional fields as empty string."""
    data = {
        "id": "https://example.org/organizations.asp?id=1",
        "type": "https://schema.oparl.org/1.0/Organization",
        "name": "Test",
        "shortName": "",
        "organizationType": "",
        "startDate": "",
        "endDate": "",
    }
    org = OparlOrganization.model_validate(data)
    assert org.short_name is None
    assert org.organization_type is None
    assert org.start_date is None
    assert org.end_date is None
