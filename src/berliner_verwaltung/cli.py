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

    async with OparlClient() as client:
        async with async_session_factory() as session:
            crawler = OparlCrawler(client, session)
            log = await crawler.crawl()
            print(
                f"Crawl {log.status}: "
                f"{log.objects_fetched} fetched, "
                f"{log.objects_new} new, "
                f"{log.objects_updated} updated"
            )


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="bv",
        description="Berliner Verwaltungsdaten – Pipeline CLI",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("crawl-oparl", help="Crawl OParl FHK endpoint")

    args = parser.parse_args()
    setup_logging(args.verbose)

    if args.command == "crawl-oparl":
        asyncio.run(cmd_crawl_oparl(args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
