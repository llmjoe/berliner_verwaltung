"""Pydantic models for OParl 1.0 entities (Berlin sitzungsdienst).

Validates API responses and provides typed access to OParl data.
Field names follow the OParl 1.0 specification exactly.
The API returns empty strings for missing values — the base validator coerces them to None.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from pydantic import BaseModel, Field, HttpUrl, model_validator


class OparlBase(BaseModel, extra="allow"):
    id: HttpUrl
    type: str
    created: dt.datetime | None = None
    modified: dt.datetime | None = None
    deleted: bool = False
    keyword: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def empty_strings_to_none(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return {k: (None if v == "" else v) for k, v in data.items()}
        return data
    web: HttpUrl | None = None


class OparlBody(OparlBase):
    name: str
    short_name: str | None = Field(None, alias="shortName")
    website: HttpUrl | None = None
    organization: HttpUrl | None = None
    person: HttpUrl | None = None
    meeting: HttpUrl | None = None
    paper: HttpUrl | None = None
    legislative_term: list[dict] | None = Field(None, alias="legislativeTerm")
    system: HttpUrl | None = None


class OparlOrganization(OparlBase):
    body: HttpUrl | None = None
    name: str = ""
    short_name: str | None = Field(None, alias="shortName")
    organization_type: str | None = Field(None, alias="organizationType")
    start_date: dt.date | None = Field(None, alias="startDate")
    end_date: dt.date | None = Field(None, alias="endDate")
    membership: list[HttpUrl] = Field(default_factory=list)


class OparlPerson(OparlBase):
    body: HttpUrl | None = None
    name: str = ""
    family_name: str | None = Field(None, alias="familyName")
    given_name: str | None = Field(None, alias="givenName")
    form_of_address: str | None = Field(None, alias="formOfAddress")
    title: list[str] | None = None
    email: list[str] | None = None
    membership: list[dict] = Field(default_factory=list)


class OparlMembership(OparlBase):
    person: HttpUrl | None = None
    organization: HttpUrl | None = None
    role: str | None = None
    start_date: dt.date | None = Field(None, alias="startDate")
    end_date: dt.date | None = Field(None, alias="endDate")


class OparlMeeting(OparlBase):
    name: str | None = None
    meeting_state: str | None = Field(None, alias="meetingState")
    cancelled: bool = False
    start: dt.datetime | None = None
    end: dt.datetime | None = None
    location: dict | None = None
    organization: list[HttpUrl] = Field(default_factory=list)
    agenda_item: list[dict] = Field(default_factory=list, alias="agendaItem")
    invitation: dict | None = None
    results_protocol: dict | None = Field(None, alias="resultsProtocol")


class OparlAgendaItem(OparlBase):
    meeting: HttpUrl | None = None
    number: str | None = None
    name: str | None = None
    public: bool | None = None
    consultation: HttpUrl | dict | None = None
    result: str | None = None
    resolution_text: str | None = Field(None, alias="resolutionText")
    resolution_file: dict | None = Field(None, alias="resolutionFile")


class OparlPaper(OparlBase):
    body: HttpUrl | None = None
    name: str | None = None
    reference: str | None = None
    date: dt.date | None = None
    paper_type: str | None = Field(None, alias="paperType")
    main_file: dict | None = Field(None, alias="mainFile")
    auxiliary_file: list[dict] = Field(default_factory=list, alias="auxiliaryFile")
    consultation: list[dict] = Field(default_factory=list)
    originator_person: list[HttpUrl] = Field(default_factory=list, alias="originatorPerson")
    originator_organization: list[HttpUrl] = Field(
        default_factory=list, alias="originatorOrganization"
    )


class OparlFile(OparlBase):
    name: str | None = None
    file_name: str | None = Field(None, alias="fileName")
    mime_type: str | None = Field(None, alias="mimeType")
    size: int | None = None
    access_url: HttpUrl | None = Field(None, alias="accessUrl")
    download_url: HttpUrl | None = Field(None, alias="downloadUrl")
    text: str | None = None


class OparlConsultation(OparlBase):
    paper: HttpUrl | None = None
    agenda_item: HttpUrl | None = Field(None, alias="agendaItem")
    organization: list[HttpUrl] = Field(default_factory=list)
    role: str | None = None
    authoritative: bool | None = None


class OparlExternalList(BaseModel):
    """Paginated list response from OParl API."""

    data: list[dict] = Field(default_factory=list)
    links: dict = Field(default_factory=dict)
    pagination: dict = Field(default_factory=dict)

    @property
    def next_url(self) -> str | None:
        return self.links.get("next") or self.pagination.get("next")
