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

    args = parser.parse_args()
    setup_logging(args.verbose)

    commands = {
        "crawl-oparl": cmd_crawl_oparl,
        "download-pdfs": cmd_download_pdfs,
        "extract-text": cmd_extract_text,
        "index-search": cmd_index_search,
        "search": cmd_search,
    }

    if args.command in commands:
        asyncio.run(commands[args.command](args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
