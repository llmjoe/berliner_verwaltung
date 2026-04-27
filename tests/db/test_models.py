"""Smoke tests for SQLAlchemy model definitions."""

from berliner_verwaltung.db.models import (
    AgendaItem,
    Base,
    Body,
    Consultation,
    CrawlLog,
    File,
    Meeting,
    Membership,
    Organization,
    Paper,
    Person,
    RawOparlObject,
)


def test_all_models_have_tablename():
    models = [
        RawOparlObject,
        Body,
        Organization,
        Person,
        Membership,
        Meeting,
        AgendaItem,
        Paper,
        File,
        Consultation,
        CrawlLog,
    ]
    for model in models:
        assert hasattr(model, "__tablename__")
        assert isinstance(model.__tablename__, str)


def test_base_metadata_has_tables():
    table_names = set(Base.metadata.tables.keys())
    expected = {
        "raw_oparl_objects",
        "bodies",
        "organizations",
        "persons",
        "memberships",
        "meetings",
        "agenda_items",
        "papers",
        "files",
        "consultations",
        "crawl_log",
    }
    assert expected.issubset(table_names)
