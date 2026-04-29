"""CLI entry point for berliner-verwaltung pipeline commands."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


async def cmd_crawl_oparl(args: argparse.Namespace) -> None:
    from berliner_verwaltung.db.connection import async_session_factory
    from berliner_verwaltung.ingestion.oparl.client import OparlClient
    from berliner_verwaltung.ingestion.oparl.crawler import OparlCrawler

    async with OparlClient() as client, async_session_factory() as session:
        crawler = OparlCrawler(client, session)
        log = await crawler.crawl()
        print(
            f"Crawl {log.status}: "
            f"{log.objects_fetched} fetched, "
            f"{log.objects_new} new, "
            f"{log.objects_updated} updated"
        )


async def cmd_download_pdfs(args: argparse.Namespace) -> None:
    from berliner_verwaltung.db.connection import async_session_factory
    from berliner_verwaltung.ingestion.pdf.downloader import PdfDownloader

    async with (
        async_session_factory() as session,
        PdfDownloader(session, legislative_term=args.term) as downloader,
    ):
        stats = await downloader.download_batch(limit=args.limit)
        print(
            f"Download: {stats['downloaded']} new, "
            f"{stats['skipped']} skipped, "
            f"{stats['errors']} errors"
        )


async def cmd_extract_text(args: argparse.Namespace) -> None:
    from berliner_verwaltung.db.connection import async_session_factory
    from berliner_verwaltung.ingestion.pdf.extractor import PdfExtractor

    async with async_session_factory() as session:
        extractor = PdfExtractor(session, legislative_term=args.term)
        stats = await extractor.extract_batch(limit=args.limit)
        await session.commit()
        print(
            f"Extraction: {stats['extracted']} extracted, "
            f"{stats['empty']} empty, "
            f"{stats['needs_ocr']} need OCR, "
            f"{stats['errors']} errors"
        )


async def cmd_index_search(args: argparse.Namespace) -> None:
    from berliner_verwaltung.db.connection import async_session_factory
    from berliner_verwaltung.ingestion.pdf.indexer import SearchIndexer

    async with async_session_factory() as session:
        indexer = SearchIndexer(session)
        stats = await indexer.index_all(limit=args.limit)
        await session.commit()
        print(f"Indexed: {stats['indexed']} papers, {stats['skipped']} skipped")


async def cmd_search(args: argparse.Namespace) -> None:
    from berliner_verwaltung.db.connection import async_session_factory
    from berliner_verwaltung.ingestion.pdf.indexer import SearchIndexer

    async with async_session_factory() as session:
        indexer = SearchIndexer(session)
        results = await indexer.search(args.query, limit=args.limit)
        if not results:
            print("Keine Ergebnisse.")
            return
        for r in results:
            print(f"[{r['reference']}] {r['name']} ({r['paper_type']}, {r['date']})")
            if r["headline"]:
                print(f"  {r['headline']}")
            print()


async def cmd_classify(args: argparse.Namespace) -> None:
    from berliner_verwaltung.db.connection import async_session_factory
    from berliner_verwaltung.enrichment.classifier import PaperClassifier
    from berliner_verwaltung.llm.client import get_llm_client

    async with async_session_factory() as session:
        if args.method == "llm":
            llm = get_llm_client(args.provider, model=args.model)
            classifier = PaperClassifier(session, llm_client=llm)
            stats = await classifier.classify_batch_llm(
                legislative_term=args.term, limit=args.limit
            )
        else:
            classifier = PaperClassifier(session)
            stats = await classifier.classify_batch_keywords(
                legislative_term=args.term, limit=args.limit
            )
        await session.commit()
        print(
            f"Classification ({args.method}): {stats['classified']} classified, "
            f"{stats['skipped']} skipped, "
            f"{stats['errors']} errors"
        )


async def cmd_embed(args: argparse.Namespace) -> None:
    from berliner_verwaltung.db.connection import async_session_factory
    from berliner_verwaltung.enrichment.embeddings import EmbeddingPipeline

    async with async_session_factory() as session:
        pipeline = EmbeddingPipeline(session, model=args.model)
        stats = await pipeline.embed_batch(
            legislative_term=args.term, limit=args.limit
        )
        await session.commit()
        print(
            f"Embedding: {stats['embedded']} embedded, "
            f"{stats['skipped']} skipped, "
            f"{stats['errors']} errors"
        )


async def cmd_load_budgets(args: argparse.Namespace) -> None:
    from berliner_verwaltung.db.connection import async_session_factory
    from berliner_verwaltung.ingestion.haushalt.loader import load_all_budget_plans

    async with async_session_factory() as session:
        plans = await load_all_budget_plans(session)
        for p in plans:
            print(f"  {p.reference} ({p.year1}/{p.year2}): {p.item_count} items")


async def cmd_extract_recipients(args: argparse.Namespace) -> None:
    import json
    from pathlib import Path

    from berliner_verwaltung.ingestion.haushalt.recipients import (
        extract_explanations_from_pdf,
        extract_recipients_with_llm,
    )
    from berliner_verwaltung.llm.client import get_llm_client

    llm = get_llm_client(args.provider, model=args.model)

    pdf_files = [
        (11668, "DS/1740/VI"),
        (10670, "DS/0830/VI"),
        (9830, "DS/0077/VI"),
    ]

    all_recipients = []
    for file_id, reference in pdf_files:
        pdf_path = Path(f"data/pdfs/{file_id}.pdf")
        if not pdf_path.exists():
            continue
        print(f"Extracting from {reference}...")
        explanations = extract_explanations_from_pdf(pdf_path)
        recipients = await extract_recipients_with_llm(llm, explanations)
        all_recipients.extend(recipients)
        print(f"  {len(recipients)} recipients from {len(explanations)} explanations")

    print(f"\nTotal: {len(all_recipients)} recipients")

    output = Path("data/recipients.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(
        [
            {
                "kapitel": r.kapitel,
                "titel": r.titel,
                "bezeichnung": r.bezeichnung,
                "recipient": r.recipient_name,
                "amount_year1": r.amount_year1,
                "amount_year2": r.amount_year2,
                "purpose": r.purpose,
                "type": r.recipient_type,
                "plan": f"{r.plan_year1}/{r.plan_year2}",
            }
            for r in all_recipients
        ],
        indent=2,
        ensure_ascii=False,
    ))
    print(f"Saved to {output}")


async def cmd_scrape_tenders(args: argparse.Namespace) -> None:
    from berliner_verwaltung.db.connection import async_session_factory
    from berliner_verwaltung.ingestion.vergabe.scraper import VergabeScraper

    async with async_session_factory() as session, VergabeScraper(session) as scraper:
        stats = await scraper.scrape(max_pages=args.pages)
        print(
            f"Vergabe: {stats['new']} new, "
            f"{stats['skipped']} skipped, "
            f"{stats['errors']} errors"
        )


async def cmd_analyze(args: argparse.Namespace) -> None:
    from berliner_verwaltung.analysis.anomalies import detect_budget_anomalies
    from berliner_verwaltung.analysis.budget_trends import analyze_budget_trends
    from berliner_verwaltung.analysis.topic_trends import analyze_topic_trends
    from berliner_verwaltung.db.connection import async_session_factory

    async with async_session_factory() as session:
        print("=== Haushalts-Trends ===\n")
        budget = await analyze_budget_trends(session, limit=args.limit)

        print("Top Steigerungen (nominal):")
        for c in budget.biggest_increases[:10]:
            print(
                f"  {c.kapitel}/{c.titel}: {c.change_pct:+.1f}% "
                f"({c.amount_from:,.0f} -> {c.amount_to:,.0f})  {c.bezeichnung[:50]}"
            )

        print("\nTop Kuerzungen (nominal):")
        for c in budget.biggest_decreases[:10]:
            print(
                f"  {c.kapitel}/{c.titel}: {c.change_pct:+.1f}% "
                f"({c.amount_from:,.0f} -> {c.amount_to:,.0f})  {c.bezeichnung[:50]}"
            )

        print(f"\nNeue Posten: {len(budget.new_items)}")
        for item in budget.new_items[:5]:
            print(f"  {item['key']}: {item['ansatz']:,.0f} EUR  {item['bezeichnung'][:50]}")

        print(f"\nEntfallene Posten: {len(budget.discontinued_items)}")
        for item in budget.discontinued_items[:5]:
            print(f"  {item['key']}: {item['ansatz']:,.0f} EUR  {item['bezeichnung'][:50]}")

        print("\nKapitel-Trends (real, inflationsbereinigt):")
        for t in budget.kapitel_trends[:10]:
            print(f"  {t.kapitel}: {t.change_real_pct:+.1f}% real")
        print("  ...")
        for t in budget.kapitel_trends[-5:]:
            print(f"  {t.kapitel}: {t.change_real_pct:+.1f}% real")

        print("\n=== Themen-Trends (VI. WP) ===\n")
        topics = await analyze_topic_trends(session)
        print(f"Klassifiziert: {topics.total_classified}, Offen: {topics.unclassified_count}")
        for t in topics.topic_trends:
            arrow = {"rising": "^", "declining": "v", "stable": "="}[t.trend]
            print(f"  [{arrow}] {t.code:15s} {t.total:>4}  {t.recent_share:.1%}  {t.by_year}")

        if topics.top_cooccurrences:
            print("\nHaeufige Themen-Kombinationen:")
            for co in topics.top_cooccurrences[:10]:
                print(f"  {co.topic_a} + {co.topic_b}: {co.count}")

        print("\n=== Anomalien ===\n")
        anomalies = await detect_budget_anomalies(session)
        for a in anomalies[:15]:
            print(f"  [{a.severity:6s}] z={a.z_score:+.1f}  {a.description[:70]}")


async def cmd_stats(args: argparse.Namespace) -> None:
    from sqlalchemy import text as sql_text

    from berliner_verwaltung.db.connection import engine

    async with engine.connect() as conn:
        for table in [
            "bodies", "organizations", "persons", "meetings",
            "agenda_items", "papers", "files", "crawl_log",
        ]:
            r = await conn.execute(sql_text(f"SELECT count(*) FROM {table}"))
            print(f"  {table:25s} {r.scalar():>8,}")

        r2 = await conn.execute(sql_text(
            "SELECT pg_size_pretty(pg_database_size(current_database()))"
        ))
        print(f"\n  DB size: {r2.scalar()}")
    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="bv",
        description="Berliner Verwaltungsdaten – Pipeline CLI",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("crawl-oparl", help="Crawl OParl FHK endpoint")

    dl_parser = subparsers.add_parser("download-pdfs", help="Download PDF files from OParl")
    dl_parser.add_argument("-n", "--limit", type=int, default=100)
    dl_parser.add_argument("-t", "--term", default=None, help="Legislative term filter (e.g. VI)")

    ex_parser = subparsers.add_parser("extract-text", help="Extract text from downloaded PDFs")
    ex_parser.add_argument("-n", "--limit", type=int, default=100)
    ex_parser.add_argument("-t", "--term", default=None, help="Legislative term filter (e.g. VI)")

    ix_parser = subparsers.add_parser("index-search", help="Build full-text search index")
    ix_parser.add_argument("-n", "--limit", type=int, default=500)

    search_parser = subparsers.add_parser("search", help="Search papers by text")
    search_parser.add_argument("query", help="Search query (German)")
    search_parser.add_argument("-n", "--limit", type=int, default=20)

    cl_parser = subparsers.add_parser("classify", help="Classify papers by topic")
    cl_parser.add_argument("-n", "--limit", type=int, default=500)
    cl_parser.add_argument("-t", "--term", default=None, help="Legislative term filter (e.g. VI)")
    cl_parser.add_argument(
        "-m", "--method", choices=["keyword", "llm"], default="keyword",
        help="Classification method (default: keyword)",
    )
    cl_parser.add_argument("--provider", default="ollama", help="LLM provider (default: ollama)")
    cl_parser.add_argument("--model", default=None, help="LLM model override")

    em_parser = subparsers.add_parser("embed", help="Generate embeddings for semantic search")
    em_parser.add_argument("-n", "--limit", type=int, default=500)
    em_parser.add_argument("-t", "--term", default=None, help="Legislative term filter (e.g. VI)")
    em_parser.add_argument("--model", default="bge-m3", help="Embedding model (default: bge-m3)")

    subparsers.add_parser("load-budgets", help="Extract and load Haushaltspläne into DB")

    rc_parser = subparsers.add_parser("extract-recipients", help="Extract Zuwendungsempfaenger")
    rc_parser.add_argument("--provider", default="ollama", help="LLM provider")
    rc_parser.add_argument("--model", default=None, help="LLM model override")

    vg_parser = subparsers.add_parser("scrape-tenders", help="Scrape Vergabeplattform Berlin")
    vg_parser.add_argument("--pages", type=int, default=33, help="Max pages to scrape")

    an_parser = subparsers.add_parser("analyze", help="Run pattern detection and trend analysis")
    an_parser.add_argument("-n", "--limit", type=int, default=20)

    subparsers.add_parser("stats", help="Show database statistics")

    args = parser.parse_args()
    setup_logging(args.verbose)

    commands = {
        "crawl-oparl": cmd_crawl_oparl,
        "download-pdfs": cmd_download_pdfs,
        "extract-text": cmd_extract_text,
        "index-search": cmd_index_search,
        "search": cmd_search,
        "classify": cmd_classify,
        "embed": cmd_embed,
        "load-budgets": cmd_load_budgets,
        "extract-recipients": cmd_extract_recipients,
        "scrape-tenders": cmd_scrape_tenders,
        "analyze": cmd_analyze,
        "stats": cmd_stats,
    }

    if args.command in commands:
        asyncio.run(commands[args.command](args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
