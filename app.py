"""Streamlit search UI for BVV Friedrichshain-Kreuzberg Drucksachen.

Run with: streamlit run app.py
"""

from __future__ import annotations

import asyncio

import streamlit as st
from sqlalchemy import func, select, text

from berliner_verwaltung.db.connection import async_session_factory
from berliner_verwaltung.db.models import (
    BudgetItem,
    BudgetPlan,
    Meeting,
    Organization,
    Paper,
    PardokDokument,
    PardokVorgang,
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


async def get_budget_plans() -> list[dict]:
    async with async_session_factory() as session:
        result = await session.execute(
            select(BudgetPlan).order_by(BudgetPlan.year1.desc())
        )
        return [
            {"id": p.id, "reference": p.reference, "year1": p.year1, "year2": p.year2,
             "item_count": p.item_count}
            for p in result.scalars().all()
        ]


async def search_budget(
    query: str = "",
    kapitel: str = "",
    plan_id: int | None = None,
    section: str = "",
    limit: int = 100,
) -> list[dict]:
    async with async_session_factory() as session:
        stmt = select(BudgetItem, BudgetPlan.year1, BudgetPlan.year2).join(
            BudgetPlan, BudgetItem.plan_id == BudgetPlan.id
        )
        if plan_id:
            stmt = stmt.where(BudgetItem.plan_id == plan_id)
        if kapitel:
            stmt = stmt.where(BudgetItem.kapitel == kapitel)
        if section and section != "Alle":
            stmt = stmt.where(BudgetItem.section == section)
        if query:
            stmt = stmt.where(BudgetItem.bezeichnung.ilike(f"%{query}%"))
        stmt = stmt.order_by(BudgetItem.ansatz_year1.desc().nullslast()).limit(limit)
        result = await session.execute(stmt)
        return [
            {
                "kapitel": r[0].kapitel,
                "titel": r[0].titel,
                "bezeichnung": r[0].bezeichnung,
                "section": r[0].section,
                "ansatz_year1": r[0].ansatz_year1,
                "ansatz_year2": r[0].ansatz_year2,
                "year1": r[1],
                "year2": r[2],
            }
            for r in result.all()
        ]


async def get_kapitel_list(plan_id: int) -> list[str]:
    async with async_session_factory() as session:
        result = await session.execute(
            select(BudgetItem.kapitel)
            .where(BudgetItem.plan_id == plan_id)
            .distinct()
            .order_by(BudgetItem.kapitel)
        )
        return [row[0] for row in result.all()]


async def get_pardok_fhk(limit: int = 50) -> list[dict]:
    async with async_session_factory() as session:
        result = await session.execute(
            select(PardokDokument, PardokVorgang.systematik_label)
            .join(PardokVorgang, PardokDokument.vorgang_id == PardokVorgang.id)
            .where(PardokVorgang.is_fhk.is_(True))
            .where(PardokDokument.titel.isnot(None))
            .order_by(PardokDokument.datum.desc().nullslast())
            .limit(limit)
        )
        return [
            {
                "dok_nr": r[0].dok_nr,
                "titel": r[0].titel,
                "dok_typ": r[0].dok_typ,
                "datum": str(r[0].datum) if r[0].datum else None,
                "urheber": r[0].urheber,
                "systematik": r[1],
                "pdf_url": r[0].pdf_url,
            }
            for r in result.all()
        ]


async def search_pardok(query: str, limit: int = 30) -> list[dict]:
    async with async_session_factory() as session:
        result = await session.execute(
            select(PardokDokument, PardokVorgang.systematik_label)
            .join(PardokVorgang, PardokDokument.vorgang_id == PardokVorgang.id)
            .where(PardokDokument.titel.ilike(f"%{query}%"))
            .order_by(PardokDokument.datum.desc().nullslast())
            .limit(limit)
        )
        return [
            {
                "dok_nr": r[0].dok_nr,
                "titel": r[0].titel,
                "dok_typ": r[0].dok_typ,
                "datum": str(r[0].datum) if r[0].datum else None,
                "urheber": r[0].urheber,
                "systematik": r[1],
                "pdf_url": r[0].pdf_url,
            }
            for r in result.all()
        ]


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

# Tabs
tab_search, tab_budget, tab_pardok, tab_analysis, tab_meetings = st.tabs([
    "Drucksachen-Suche", "Haushalt", "Abgeordnetenhaus", "Analyse",
    "Letzte Sitzungen",
])

with tab_search:
    col_q, col_mode = st.columns([4, 1])
    with col_q:
        query = st.text_input(
            "Suche",
            placeholder="z.B. Spielplatz, Radweg, Haushalt, Schulbau...",
        )
    with col_mode:
        search_mode = st.radio("Modus", ["Volltext", "Semantisch"], horizontal=True)

    if query or selected_type != "Alle" or selected_term != "Alle":
        if search_mode == "Semantisch" and query:
            from berliner_verwaltung.enrichment.embeddings import EmbeddingPipeline

            async def _semantic_search():  # type: ignore[no-redef]
                async with async_session_factory() as s:
                    pipeline = EmbeddingPipeline(s)
                    return await pipeline.semantic_search(query, limit=30)

            results_raw = run_async(_semantic_search())
            results = [
                {
                    "reference": r["reference"],
                    "name": r["name"],
                    "type": r["paper_type"],
                    "date": r["date"] or "–",
                    "oparl_url": "",
                    "topics": [],
                    "similarity": r.get("similarity", 0),
                }
                for r in results_raw
            ]
        else:
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
                meta = f"{r['type']} | {r['date']}"
                if r.get("similarity"):
                    meta += f" | {r['similarity']:.0%}"
                st.caption(meta)
                if r["oparl_url"]:
                    st.link_button("Original", r["oparl_url"], use_container_width=True)
            st.divider()
    else:
        st.info("Suchbegriff eingeben oder Filter setzen.")

with tab_budget:
    plans = run_async(get_budget_plans())
    if plans:
        plan_options = {
            f"{p['year1']}/{p['year2']} ({p['item_count']} Posten)": p["id"]
            for p in plans
        }
        selected_plan_label = st.selectbox("Haushaltsplan", list(plan_options.keys()))
        selected_plan_id = plan_options[selected_plan_label]

        col_a, col_b, col_c = st.columns(3)
        with col_a:
            kapitel_list = run_async(get_kapitel_list(selected_plan_id))
            selected_kapitel = st.selectbox("Kapitel", [""] + kapitel_list)
        with col_b:
            selected_section = st.selectbox("Typ", ["Alle", "Einnahmen", "Ausgaben"])
        with col_c:
            budget_query = st.text_input("Suche in Bezeichnung", key="budget_search")

        results = run_async(search_budget(
            query=budget_query,
            kapitel=selected_kapitel,
            plan_id=selected_plan_id,
            section=selected_section,
        ))
        st.info(f"{len(results)} Posten")

        if results:
            import pandas as pd
            df = pd.DataFrame(results)
            df["ansatz_year1"] = df["ansatz_year1"].apply(
                lambda x: f"{x:,.0f}" if x is not None else "—"
            )
            df["ansatz_year2"] = df["ansatz_year2"].apply(
                lambda x: f"{x:,.0f}" if x is not None else "—"
            )
            year1 = results[0]["year1"]
            year2 = results[0]["year2"]
            st.dataframe(
                df[["kapitel", "titel", "bezeichnung", "section",
                    "ansatz_year1", "ansatz_year2"]].rename(
                    columns={
                        "kapitel": "Kapitel",
                        "titel": "Titel",
                        "bezeichnung": "Bezeichnung",
                        "section": "Typ",
                        "ansatz_year1": f"Ansatz {year1}",
                        "ansatz_year2": f"Ansatz {year2}",
                    }
                ),
                use_container_width=True,
                hide_index=True,
            )
    else:
        st.info("Noch keine Haushaltsdaten geladen. Starte: bv load-budgets")

with tab_pardok:
    st.subheader("Abgeordnetenhaus Berlin — FHK-relevante Vorgaenge")
    pardok_query = st.text_input(
        "Suche in AGH-Dokumenten",
        placeholder="z.B. Kottbusser Tor, Schulbau, Milieuschutz...",
        key="pardok_search",
    )
    if pardok_query:
        pardok_results = run_async(search_pardok(pardok_query))
    else:
        pardok_results = run_async(get_pardok_fhk(50))

    st.info(f"{len(pardok_results)} Dokumente")
    for r in pardok_results:
        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown(f"**[{r['dok_nr']}]** {r['titel']}")
            meta = f"{r['dok_typ'] or ''} | {r['systematik'] or ''}"
            if r["urheber"]:
                meta += f" | {r['urheber']}"
            st.caption(meta)
        with col2:
            st.caption(r["datum"] or "")
            if r["pdf_url"]:
                st.link_button("PDF", r["pdf_url"], use_container_width=True)
        st.divider()

with tab_analysis:
    st.subheader("Themen-Verteilung (VI. Wahlperiode)")

    from berliner_verwaltung.analysis.anomalies import detect_budget_anomalies
    from berliner_verwaltung.analysis.budget_trends import analyze_budget_trends
    from berliner_verwaltung.analysis.topic_trends import analyze_topic_trends

    async def _run_analysis():  # type: ignore[no-redef]
        async with async_session_factory() as s:
            t = await analyze_topic_trends(s)
            b = await analyze_budget_trends(s)
            a = await detect_budget_anomalies(s)
            return t, b, a

    topics, budget, anomalies = run_async(_run_analysis())

    # Topic chart
    if topics and topics.topic_trends:
        import pandas as pd
        topic_df = pd.DataFrame([
            {"Thema": t.code, "Anzahl": t.total, "Trend": t.trend,
             "Anteil": f"{t.recent_share:.1%}"}
            for t in topics.topic_trends
        ])
        st.bar_chart(topic_df.set_index("Thema")["Anzahl"])
        st.dataframe(topic_df, use_container_width=True, hide_index=True)

        if topics.top_cooccurrences:
            st.subheader("Haeufige Themen-Kombinationen")
            cooc_df = pd.DataFrame([
                {"Thema A": c.topic_a, "Thema B": c.topic_b, "Anzahl": c.count}
                for c in topics.top_cooccurrences[:10]
            ])
            st.dataframe(cooc_df, use_container_width=True, hide_index=True)

    # Budget anomalies
    if anomalies:
        st.subheader("Haushalts-Anomalien")
        st.caption("Budgetposten mit statistisch auffaelliger Veraenderung (z-Score)")
        import pandas as pd
        anom_df = pd.DataFrame([
            {
                "Schwere": a.severity,
                "z-Score": f"{a.z_score:+.1f}",
                "Beschreibung": a.description[:80],
            }
            for a in anomalies[:15]
        ])
        st.dataframe(anom_df, use_container_width=True, hide_index=True)

    # Kapitel trends
    if budget and budget.kapitel_trends:
        st.subheader("Kapitel-Trends (inflationsbereinigt)")
        import pandas as pd
        kap_df = pd.DataFrame([
            {
                "Kapitel": t.kapitel,
                "Veraenderung (real)": f"{t.change_real_pct:+.1f}%",
                "real_pct": t.change_real_pct,
            }
            for t in budget.kapitel_trends
        ])
        st.bar_chart(kap_df.set_index("Kapitel")["real_pct"])

with tab_meetings:
    meetings = run_async(get_recent_meetings(20))
    for m in meetings:
        st.markdown(f"**{m['name']}** — {m['date']}")
        st.caption(f"{m['state']} | {m['location']}")
        st.divider()
