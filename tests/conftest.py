"""Shared test fixtures for berliner_verwaltung tests."""

from __future__ import annotations

from typing import Any

import pytest


@pytest.fixture
def sample_system() -> dict[str, Any]:
    return {
        "id": "https://www.sitzungsdienst-friedrichshain-kreuzberg.de/oi/oparl/1.0/system.asp",
        "type": "https://schema.oparl.org/1.0/System",
        "oparlVersion": "https://schema.oparl.org/1.0/",
        "name": "BVV Friedrichshain-Kreuzberg",
        "body": "https://www.sitzungsdienst-friedrichshain-kreuzberg.de/oi/oparl/1.0/bodies.asp",
    }


@pytest.fixture
def sample_body() -> dict[str, Any]:
    return {
        "id": "https://www.sitzungsdienst-friedrichshain-kreuzberg.de/oi/oparl/1.0/bodies.asp?id=22",
        "type": "https://schema.oparl.org/1.0/Body",
        "name": "BVV Friedrichshain-Kreuzberg",
        "shortName": "BVV",
        "organization": "https://example.org/organizations.asp?body=22",
        "person": "https://example.org/persons.asp?body=22",
        "meeting": "https://example.org/meetings.asp?body=22",
        "paper": "https://example.org/papers.asp?body=22",
        "legislativeTerm": [
            {
                "id": "https://example.org/legislativeterm/6",
                "type": "https://schema.oparl.org/1.0/LegislativeTerm",
                "name": "VI. Wahlperiode",
                "startDate": "2021-11-04",
                "endDate": "2026-10-31",
            }
        ],
        "created": "2001-11-27T12:00:00+01:00",
        "modified": "2025-10-28T15:29:09+01:00",
    }


@pytest.fixture
def sample_organization() -> dict[str, Any]:
    return {
        "id": "https://example.org/organizations.asp?typ=gr&id=69",
        "type": "https://schema.oparl.org/1.0/Organization",
        "body": "https://example.org/bodies.asp?id=22",
        "name": "Aeltestenrat",
        "shortName": "AeR",
        "organizationType": "Gremium",
        "startDate": "2001-11-27",
        "endDate": "",
        "membership": ["https://example.org/memberships.asp?typ=mg&id=1050"],
        "created": "2001-11-27T12:00:00+01:00",
        "modified": "2025-10-28T15:29:09+01:00",
    }


@pytest.fixture
def sample_person() -> dict[str, Any]:
    return {
        "id": "https://example.org/persons.asp?typ=kp&id=9",
        "type": "https://schema.oparl.org/1.0/Person",
        "name": "Claudia Richter",
        "familyName": "Richter",
        "givenName": "Claudia",
        "formOfAddress": "Frau",
        "phone": ["030-4262687"],
        "membership": [
            {
                "id": "https://example.org/memberships.asp?typ=mg&id=256",
                "type": "https://schema.oparl.org/1.0/Membership",
                "person": "https://example.org/persons.asp?typ=kp&id=9",
                "organization": "https://example.org/organizations.asp?typ=gr&id=25",
                "role": "BV",
                "votingRight": True,
                "startDate": "2001-11-30",
                "endDate": "2021-11-03",
            }
        ],
        "created": "2022-02-23T12:00:00+01:00",
        "modified": "2024-10-22T17:09:29+02:00",
    }


@pytest.fixture
def sample_meeting() -> dict[str, Any]:
    return {
        "id": "https://example.org/meetings.asp?id=11936",
        "type": "https://schema.oparl.org/1.0/Meeting",
        "name": "42. Sitzung der BVV",
        "start": "2024-03-20T17:00:00+01:00",
        "end": "2024-03-20T21:00:00+01:00",
        "meetingState": "eingeladen",
        "location": {"description": "BVV-Saal, Rathaus Kreuzberg"},
        "organization": ["https://example.org/organizations.asp?typ=gr&id=25"],
        "agendaItem": [
            {
                "id": "https://example.org/agendaitems.asp?id=201",
                "type": "https://schema.oparl.org/1.0/AgendaItem",
                "number": "1",
                "name": "Eroeffnung",
                "public": True,
                "consultation": "https://example.org/consultations.asp?typ=i&id=63964",
            },
            {
                "id": "https://example.org/agendaitems.asp?id=202",
                "type": "https://schema.oparl.org/1.0/AgendaItem",
                "number": "2",
                "name": "Genehmigung der Tagesordnung",
                "public": True,
            },
        ],
        "created": "2024-03-01T12:00:00+01:00",
        "modified": "2024-03-20T12:00:00+01:00",
    }


@pytest.fixture
def sample_paper() -> dict[str, Any]:
    return {
        "id": "https://example.org/papers.asp?id=16",
        "type": "https://schema.oparl.org/1.0/Paper",
        "body": "https://example.org/bodies.asp?id=22",
        "name": "Antrag: Spielplatz Wrangelstrasse sanieren",
        "reference": "DS/0016/2002",
        "paperType": "Antrag",
        "date": "2003-03-24",
        "mainFile": {
            "id": "https://example.org/files.asp?id=5678",
            "type": "https://schema.oparl.org/1.0/File",
            "accessUrl": "https://example.org/files/5678.pdf",
            "mimeType": "application/pdf",
            "fileName": "DS_0016_2002.pdf",
        },
        "auxiliaryFile": [],
        "consultation": [
            {
                "id": "https://example.org/consultations.asp?typ=s&id=17",
                "type": "https://schema.oparl.org/1.0/Consultation",
                "organization": ["https://example.org/organizations.asp?typ=gr&id=25"],
                "role": "Vorberatung",
                "paper": "https://example.org/papers.asp?id=16",
            }
        ],
        "created": "2002-07-03T12:00:00+02:00",
        "modified": "2003-03-24T12:00:00+01:00",
    }
