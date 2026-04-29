"""Streamlit search UI for BVV Friedrichshain-Kreuzberg Drucksachen.

Run with: streamlit run app.py
"""

from __future__ import annotations

import asyncio

import streamlit as st
from sqlalchemy import func, select, text

from berliner_verwaltung.db.connection import async_session_factory
from berliner_verwaltung.db.models import (
    Meeting,
    Organization,
    Paper,
    Person,
)


def run_async(coro):  # type: ignore[no-untyped-def]
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def get_stats() -> dict:
    async with async_session_factory() as session:
        stats = {}
        for label, model in [
            ("Drucksachen", Paper),
            ("Sitzungen", Meeting),
            ("Personen", Person),
            ("Organisationen", Organization),
        ]:
            r = await session.execute(select(func.count()).select_from(model))
            stats[label] = r.scalar() or 0
        return stats


async def search_papers(
    query: str,
    paper_type: str | None = None,
    term: str | None = None,
    limit: int = 50,
) -> list[dict]:
    async with async_session_factory() as session:
        conditions = []

        if query:
            conditions.append(
                Paper.search_vector.op("@@")(func.plainto_tsquery(text("'german'"), query))
            )

        if paper_type and paper_type != "Alle":
            conditions.append(Paper.paper_type == paper_type)

        if term and term != "Alle":
            conditions.append(Paper.reference.like(f"%/{term}"))

        stmt = select(Paper)
        for cond in conditions:
            stmt = stmt.where(cond)
        stmt = stmt.order_by(Paper.date.desc().nullslast()).limit(limit)

        result = await session.execute(stmt)
        papers = result.scalars().all()

        return [
            {
                "reference": p.reference,
                "name": p.name,
                "type": p.paper_type,
                "date": str(p.date) if p.date else "–",
                "oparl_url": p.data.get("web", "") if p.data else "",
                "topics": (
                    p.data.get("classification", {}).get("topics", [])
                    if p.data
                    else []
                ),
            }
            for p in papers
        ]


async def get_paper_types() -> list[str]:
    async with async_session_factory() as session:
        result = await session.execute(
            select(Paper.paper_type)
            .where(Paper.paper_type.isnot(None))
            .distinct()
            .order_by(Paper.paper_type)
        )
        return [row[0] for row in result.all()]


async def get_recent_meetings(limit: int = 10) -> list[dict]:
    async with async_session_factory() as session:
        result = await session.execute(
            select(Meeting)
            .where(Meeting.start.isnot(None))
            .order_by(Meeting.start.desc())
            .limit(limit)
        )
        meetings = result.scalars().all()
        return [
            {
                "name": m.name or "–",
                "date": m.start.strftime("%d.%m.%Y %H:%M") if m.start else "–",
                "state": m.meeting_state or "–",
                "location": m.location_name or "–",
            }
            for m in meetings
        ]


# --- Streamlit UI ---

st.set_page_config(
    page_title="BVV Friedrichshain-Kreuzberg – Recherche",
    page_icon="🏛️",
    layout="wide",
)

st.title("BVV Friedrichshain-Kreuzberg")
st.caption("Durchsuchbare Datenbank der Bezirksverordnetenversammlung")

# Sidebar
with st.sidebar:
    st.header("Filter")
    paper_types = run_async(get_paper_types())
    selected_type = st.selectbox("Drucksachen-Typ", ["Alle"] + paper_types)
    selected_term = st.selectbox(
        "Wahlperiode",
        ["Alle", "VI", "V", "IV", "III", "II"],
        help="VI = aktuell (2021–), V = 2016–2021, etc.",
    )

    st.divider()
    stats = run_async(get_stats())
    st.metric("Drucksachen", f"{stats['Drucksachen']:,}")
    st.metric("Sitzungen", f"{stats['Sitzungen']:,}")
    st.metric("Personen", f"{stats['Personen']:,}")
    st.metric("Organisationen", f"{stats['Organisationen']:,}")

# Search
tab_search, tab_meetings = st.tabs(["Drucksachen-Suche", "Letzte Sitzungen"])

with tab_search:
    query = st.text_input(
        "Volltextsuche",
        placeholder="z.B. Spielplatz, Radweg, Haushalt, Schulbau...",
    )

    if query or selected_type != "Alle" or selected_term != "Alle":
        results = run_async(search_papers(
            query=query,
            paper_type=selected_type if selected_type != "Alle" else None,
            term=selected_term if selected_term != "Alle" else None,
        ))

        st.info(f"{len(results)} Ergebnisse")

        for r in results:
            col1, col2 = st.columns([4, 1])
            with col1:
                label = f"**[{r['reference']}]** {r['name']}"
                st.markdown(label)
                if r["topics"]:
                    topic_tags = " ".join(
                        f"`{t['code']}`" for t in r["topics"][:3]
                    )
                    st.caption(f"Themen: {topic_tags}")
            with col2:
                st.caption(f"{r['type']} | {r['date']}")
                if r["oparl_url"]:
                    st.link_button("Original", r["oparl_url"], use_container_width=True)
            st.divider()
    else:
        st.info("Suchbegriff eingeben oder Filter setzen.")

with tab_meetings:
    meetings = run_async(get_recent_meetings(20))
    for m in meetings:
        st.markdown(f"**{m['name']}** — {m['date']}")
        st.caption(f"{m['state']} | {m['location']}")
        st.divider()
