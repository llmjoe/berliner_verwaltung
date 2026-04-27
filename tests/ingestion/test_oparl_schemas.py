"""Tests for OParl Pydantic schemas – validates parsing of real-world API shapes."""

from berliner_verwaltung.ingestion.oparl.schemas import (
    OparlBody,
    OparlExternalList,
    OparlMeeting,
    OparlOrganization,
    OparlPaper,
    OparlPerson,
)


def test_parse_body():
    data = {
        "id": "https://example.org/oparl/v1.1/body/1",
        "type": "https://schema.oparl.org/1.1/Body",
        "name": "Bezirksamt Friedrichshain-Kreuzberg",
        "shortName": "BA FHK",
        "website": "https://www.berlin.de/ba-friedrichshain-kreuzberg/",
        "organization": "https://example.org/oparl/v1.1/body/1/organization",
        "person": "https://example.org/oparl/v1.1/body/1/person",
        "meeting": "https://example.org/oparl/v1.1/body/1/meeting",
        "paper": "https://example.org/oparl/v1.1/body/1/paper",
    }
    body = OparlBody.model_validate(data)
    assert body.name == "Bezirksamt Friedrichshain-Kreuzberg"
    assert body.short_name == "BA FHK"
    assert str(body.organization) == "https://example.org/oparl/v1.1/body/1/organization"


def test_parse_person():
    data = {
        "id": "https://example.org/oparl/v1.1/person/42",
        "type": "https://schema.oparl.org/1.1/Person",
        "name": "Max Mustermann",
        "familyName": "Mustermann",
        "givenName": "Max",
        "formOfAddress": "Herr",
        "email": ["max@example.org"],
        "membership": [],
    }
    person = OparlPerson.model_validate(data)
    assert person.family_name == "Mustermann"
    assert person.given_name == "Max"
    assert person.email == ["max@example.org"]


def test_parse_organization():
    data = {
        "id": "https://example.org/oparl/v1.1/organization/5",
        "type": "https://schema.oparl.org/1.1/Organization",
        "name": "Ausschuss fuer Stadtentwicklung",
        "shortName": "StadtE",
        "organizationType": "Ausschuss",
        "startDate": "2021-10-01",
    }
    org = OparlOrganization.model_validate(data)
    assert org.name == "Ausschuss fuer Stadtentwicklung"
    assert org.organization_type == "Ausschuss"
    assert str(org.start_date) == "2021-10-01"


def test_parse_meeting_with_agenda():
    data = {
        "id": "https://example.org/oparl/v1.1/meeting/99",
        "type": "https://schema.oparl.org/1.1/Meeting",
        "name": "42. Sitzung der BVV",
        "start": "2024-03-20T17:00:00+01:00",
        "end": "2024-03-20T21:00:00+01:00",
        "meetingState": "eingeladen",
        "location": {"description": "BVV-Saal, Rathaus Kreuzberg"},
        "agendaItem": [
            {
                "id": "https://example.org/oparl/v1.1/agendaitem/201",
                "type": "https://schema.oparl.org/1.1/AgendaItem",
                "number": "1",
                "name": "Eroeffnung",
                "public": True,
            }
        ],
    }
    meeting = OparlMeeting.model_validate(data)
    assert meeting.name == "42. Sitzung der BVV"
    assert meeting.meeting_state == "eingeladen"
    assert len(meeting.agenda_item) == 1


def test_parse_paper_with_files():
    data = {
        "id": "https://example.org/oparl/v1.1/paper/1234",
        "type": "https://schema.oparl.org/1.1/Paper",
        "name": "Antrag: Spielplatz Wrangelstrasse sanieren",
        "reference": "DS/1234/VI",
        "paperType": "Antrag",
        "date": "2024-02-15",
        "mainFile": {
            "id": "https://example.org/oparl/v1.1/file/5678",
            "type": "https://schema.oparl.org/1.1/File",
            "accessUrl": "https://example.org/files/5678.pdf",
            "mimeType": "application/pdf",
        },
        "auxiliaryFile": [],
        "consultation": [],
    }
    paper = OparlPaper.model_validate(data)
    assert paper.reference == "DS/1234/VI"
    assert paper.paper_type == "Antrag"
    assert paper.main_file is not None


def test_parse_external_list():
    data = {
        "data": [{"id": "https://example.org/1"}, {"id": "https://example.org/2"}],
        "links": {"next": "https://example.org/list?page=2"},
        "pagination": {},
    }
    ext_list = OparlExternalList.model_validate(data)
    assert len(ext_list.data) == 2
    assert ext_list.next_url == "https://example.org/list?page=2"


def test_external_list_no_next():
    data = {"data": [{"id": "https://example.org/1"}], "links": {}, "pagination": {}}
    ext_list = OparlExternalList.model_validate(data)
    assert ext_list.next_url is None


def test_person_extra_fields_allowed():
    data = {
        "id": "https://example.org/oparl/v1.1/person/1",
        "type": "https://schema.oparl.org/1.1/Person",
        "name": "Test Person",
        "customField": "should not raise",
    }
    person = OparlPerson.model_validate(data)
    assert person.name == "Test Person"
