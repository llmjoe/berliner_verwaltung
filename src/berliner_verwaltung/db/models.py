"""SQLAlchemy models for OParl entities and pipeline metadata.

Two-layer design:
  - raw_* tables store the unmodified JSON from OParl (single source of truth)
  - Normalized tables derive structured, queryable data from the raw layer
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    type_annotation_map = {
        dict[str, Any]: JSONB,
    }


# ---------------------------------------------------------------------------
# Raw layer – unmodified OParl JSON
# ---------------------------------------------------------------------------


class RawOparlObject(Base):
    __tablename__ = "raw_oparl_objects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    oparl_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    oparl_type: Mapped[str] = mapped_column(String, index=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    fetched_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (Index("ix_raw_oparl_type_fetched", "oparl_type", "fetched_at"),)


# ---------------------------------------------------------------------------
# Normalized layer – structured, queryable entities
# ---------------------------------------------------------------------------


class Body(Base):
    __tablename__ = "bodies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    oparl_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    short_name: Mapped[str | None] = mapped_column(String)
    website: Mapped[str | None] = mapped_column(String)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    organizations: Mapped[list[Organization]] = relationship(back_populates="body")
    persons: Mapped[list[Person]] = relationship(back_populates="body")
    meetings: Mapped[list[Meeting]] = relationship(back_populates="body")
    papers: Mapped[list[Paper]] = relationship(back_populates="body")


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    oparl_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    body_id: Mapped[int] = mapped_column(ForeignKey("bodies.id"), index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    short_name: Mapped[str | None] = mapped_column(String)
    organization_type: Mapped[str | None] = mapped_column(String)
    start_date: Mapped[dt.date | None] = mapped_column()
    end_date: Mapped[dt.date | None] = mapped_column()
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    body: Mapped[Body] = relationship(back_populates="organizations")
    memberships: Mapped[list[Membership]] = relationship(back_populates="organization")


class Person(Base):
    __tablename__ = "persons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    oparl_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    body_id: Mapped[int] = mapped_column(ForeignKey("bodies.id"), index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    family_name: Mapped[str | None] = mapped_column(String)
    given_name: Mapped[str | None] = mapped_column(String)
    form_of_address: Mapped[str | None] = mapped_column(String)
    title: Mapped[str | None] = mapped_column(String)
    email: Mapped[str | None] = mapped_column(String)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    body: Mapped[Body] = relationship(back_populates="persons")
    memberships: Mapped[list[Membership]] = relationship(back_populates="person")


class Membership(Base):
    __tablename__ = "memberships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    oparl_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("persons.id"), index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    role: Mapped[str | None] = mapped_column(String)
    start_date: Mapped[dt.date | None] = mapped_column()
    end_date: Mapped[dt.date | None] = mapped_column()
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    person: Mapped[Person] = relationship(back_populates="memberships")
    organization: Mapped[Organization] = relationship(back_populates="memberships")


class Meeting(Base):
    __tablename__ = "meetings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    oparl_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    body_id: Mapped[int] = mapped_column(ForeignKey("bodies.id"), index=True)
    name: Mapped[str | None] = mapped_column(String)
    meeting_state: Mapped[str | None] = mapped_column(String)
    start: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    end: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    location_name: Mapped[str | None] = mapped_column(String)
    cancelled: Mapped[bool | None] = mapped_column()
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    body: Mapped[Body] = relationship(back_populates="meetings")
    agenda_items: Mapped[list[AgendaItem]] = relationship(back_populates="meeting")

    __table_args__ = (Index("ix_meetings_start", "start"),)


class AgendaItem(Base):
    __tablename__ = "agenda_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    oparl_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    meeting_id: Mapped[int] = mapped_column(ForeignKey("meetings.id"), index=True)
    number: Mapped[str | None] = mapped_column(String)
    name: Mapped[str | None] = mapped_column(String)
    public: Mapped[bool | None] = mapped_column()
    result: Mapped[str | None] = mapped_column(Text)
    resolution_text: Mapped[str | None] = mapped_column(Text)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    meeting: Mapped[Meeting] = relationship(back_populates="agenda_items")
    consultation: Mapped[Consultation | None] = relationship(back_populates="agenda_item")


class Paper(Base):
    __tablename__ = "papers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    oparl_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    body_id: Mapped[int] = mapped_column(ForeignKey("bodies.id"), index=True)
    name: Mapped[str | None] = mapped_column(String)
    reference: Mapped[str | None] = mapped_column(String, index=True)
    paper_type: Mapped[str | None] = mapped_column(String, index=True)
    date: Mapped[dt.date | None] = mapped_column(index=True)
    main_file_url: Mapped[str | None] = mapped_column(String)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    # Full-text search
    search_vector: Mapped[Any | None] = mapped_column(TSVECTOR)

    # Semantic search
    embedding: Mapped[Any | None] = mapped_column(Vector(1024))

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    body: Mapped[Body] = relationship(back_populates="papers")
    files: Mapped[list[File]] = relationship(back_populates="paper")
    consultations: Mapped[list[Consultation]] = relationship(back_populates="paper")

    __table_args__ = (
        Index("ix_papers_search_vector", "search_vector", postgresql_using="gin"),
        Index("ix_papers_date", "date"),
    )


class File(Base):
    __tablename__ = "files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    oparl_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    paper_id: Mapped[int | None] = mapped_column(ForeignKey("papers.id"), index=True)
    name: Mapped[str | None] = mapped_column(String)
    file_name: Mapped[str | None] = mapped_column(String)
    mime_type: Mapped[str | None] = mapped_column(String)
    access_url: Mapped[str | None] = mapped_column(String)
    download_url: Mapped[str | None] = mapped_column(String)
    text: Mapped[str | None] = mapped_column(Text)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    paper: Mapped[Paper | None] = relationship(back_populates="files")


class Consultation(Base):
    __tablename__ = "consultations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    oparl_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id"), index=True)
    agenda_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("agenda_items.id"), index=True
    )
    role: Mapped[str | None] = mapped_column(String)
    authoritative: Mapped[bool | None] = mapped_column()
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    paper: Mapped[Paper] = relationship(back_populates="consultations")
    agenda_item: Mapped[AgendaItem | None] = relationship(back_populates="consultation")


# ---------------------------------------------------------------------------
# Pipeline metadata
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Budget data (Bezirkshaushaltsplan)
# ---------------------------------------------------------------------------


class BudgetPlan(Base):
    __tablename__ = "budget_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reference: Mapped[str] = mapped_column(String, index=True)
    file_id: Mapped[int | None] = mapped_column(ForeignKey("files.id"))
    year1: Mapped[int] = mapped_column(Integer, nullable=False)
    year2: Mapped[int] = mapped_column(Integer, nullable=False)
    kapitel_count: Mapped[int] = mapped_column(Integer, default=0)
    item_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    items: Mapped[list[BudgetItem]] = relationship(back_populates="plan")


class BudgetItem(Base):
    __tablename__ = "budget_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("budget_plans.id"), index=True)
    kapitel: Mapped[str] = mapped_column(String(4), nullable=False, index=True)
    titel: Mapped[str] = mapped_column(String(5), nullable=False, index=True)
    funktion: Mapped[str] = mapped_column(String(3), default="")
    bezeichnung: Mapped[str] = mapped_column(String, nullable=False)
    section: Mapped[str] = mapped_column(String(10), default="")
    kennbuchstabe: Mapped[str] = mapped_column(String(3), default="")
    ansatz_year1: Mapped[float | None] = mapped_column()
    ansatz_year2: Mapped[float | None] = mapped_column()
    ansatz_prev: Mapped[float | None] = mapped_column()
    ist_prev: Mapped[float | None] = mapped_column()
    page: Mapped[int] = mapped_column(Integer, default=0)
    erlaeuterung: Mapped[str] = mapped_column(Text, default="")

    plan: Mapped[BudgetPlan] = relationship(back_populates="items")

    __table_args__ = (
        Index("ix_budget_items_kapitel_titel", "kapitel", "titel"),
    )


# ---------------------------------------------------------------------------
# Procurement data (Vergabedaten)
# ---------------------------------------------------------------------------


class Tender(Base):
    """Public procurement notice (Vergabebekanntmachung)."""

    __tablename__ = "tenders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String, nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    contracting_authority: Mapped[str | None] = mapped_column(String, index=True)
    tender_type: Mapped[str | None] = mapped_column(String, index=True)
    procedure_type: Mapped[str | None] = mapped_column(String)
    cpv_codes: Mapped[list | None] = mapped_column(JSONB)
    estimated_value: Mapped[float | None] = mapped_column()
    awarded_value: Mapped[float | None] = mapped_column()
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    winner: Mapped[str | None] = mapped_column(String)
    publication_date: Mapped[dt.date | None] = mapped_column(index=True)
    deadline_date: Mapped[dt.date | None] = mapped_column()
    award_date: Mapped[dt.date | None] = mapped_column()
    status: Mapped[str | None] = mapped_column(String)
    url: Mapped[str | None] = mapped_column(String)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_tenders_authority_date", "contracting_authority", "publication_date"),
    )


class CrawlLog(Base):
    __tablename__ = "crawl_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String, nullable=False)
    started_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    objects_fetched: Mapped[int] = mapped_column(Integer, default=0)
    objects_new: Mapped[int] = mapped_column(Integer, default=0)
    objects_updated: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String, default="running")
    error_message: Mapped[str | None] = mapped_column(Text)
