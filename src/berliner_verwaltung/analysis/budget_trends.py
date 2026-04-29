"""Budget time series analysis across Doppelhaushalte.

Compares budget items across multiple plans to detect:
- Growth/decline trends per Kapitel and Titel
- Inflation-adjusted changes
- New and discontinued budget items
- Largest absolute and relative changes
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berliner_verwaltung.db.models import BudgetItem, BudgetPlan

logger = logging.getLogger(__name__)

INFLATION_RATES = {
    2022: 1.00,
    2023: 1.059,
    2024: 1.059 * 1.025,
    2025: 1.059 * 1.025 * 1.022,
    2026: 1.059 * 1.025 * 1.022 * 1.020,
    2027: 1.059 * 1.025 * 1.022 * 1.020 * 1.020,
}


def _inflate(amount: float, from_year: int, to_year: int = 2026) -> float:
    if from_year not in INFLATION_RATES or to_year not in INFLATION_RATES:
        return amount
    return amount * INFLATION_RATES[to_year] / INFLATION_RATES[from_year]


@dataclass
class BudgetChange:
    kapitel: str
    titel: str
    bezeichnung: str
    year_from: int
    year_to: int
    amount_from: float
    amount_to: float
    change_abs: float
    change_pct: float
    change_real_pct: float
    section: str = ""


@dataclass
class KapitelTrend:
    kapitel: str
    name: str
    totals: dict[int, float]
    change_pct: float
    change_real_pct: float


@dataclass
class PatternReport:
    biggest_increases: list[BudgetChange]
    biggest_decreases: list[BudgetChange]
    new_items: list[dict]
    discontinued_items: list[dict]
    kapitel_trends: list[KapitelTrend]


async def analyze_budget_trends(session: AsyncSession, limit: int = 20) -> PatternReport:
    """Compare budget items across all loaded plans."""

    plans_result = await session.execute(
        select(BudgetPlan).order_by(BudgetPlan.year1)
    )
    plans = list(plans_result.scalars().all())

    if len(plans) < 2:
        logger.warning("Need at least 2 budget plans for trend analysis")
        return PatternReport([], [], [], [], [])

    oldest = plans[0]
    newest = plans[-1]

    # Load items for oldest and newest plan
    old_result = await session.execute(
        select(BudgetItem).where(BudgetItem.plan_id == oldest.id)
    )
    new_result = await session.execute(
        select(BudgetItem).where(BudgetItem.plan_id == newest.id)
    )

    old_items = {f"{i.kapitel}/{i.titel}": i for i in old_result.scalars().all()}
    new_items = {f"{i.kapitel}/{i.titel}": i for i in new_result.scalars().all()}

    # Calculate changes for items present in both plans
    changes: list[BudgetChange] = []
    common_keys = set(old_items.keys()) & set(new_items.keys())

    for key in common_keys:
        old = old_items[key]
        new = new_items[key]
        if old.ansatz_year1 and new.ansatz_year1 and old.ansatz_year1 > 0:
            change_abs = new.ansatz_year1 - old.ansatz_year1
            change_pct = (change_abs / old.ansatz_year1) * 100
            inflated_old = _inflate(old.ansatz_year1, oldest.year1, newest.year1)
            change_real_pct = ((new.ansatz_year1 - inflated_old) / inflated_old) * 100

            changes.append(BudgetChange(
                kapitel=new.kapitel,
                titel=new.titel,
                bezeichnung=new.bezeichnung,
                year_from=oldest.year1,
                year_to=newest.year1,
                amount_from=old.ansatz_year1,
                amount_to=new.ansatz_year1,
                change_abs=change_abs,
                change_pct=change_pct,
                change_real_pct=change_real_pct,
                section=new.section,
            ))

    changes_sorted = sorted(changes, key=lambda c: c.change_abs, reverse=True)
    biggest_increases = changes_sorted[:limit]
    biggest_decreases = changes_sorted[-limit:][::-1]

    # New items (in newest but not oldest)
    new_only_keys = set(new_items.keys()) - set(old_items.keys())
    new_only = [
        {
            "key": k,
            "bezeichnung": new_items[k].bezeichnung,
            "ansatz": new_items[k].ansatz_year1,
            "section": new_items[k].section,
        }
        for k in sorted(new_only_keys)
        if new_items[k].ansatz_year1 and new_items[k].ansatz_year1 > 0
    ]
    new_only.sort(key=lambda x: x["ansatz"] or 0, reverse=True)

    # Discontinued items (in oldest but not newest)
    disc_keys = set(old_items.keys()) - set(new_items.keys())
    discontinued = [
        {
            "key": k,
            "bezeichnung": old_items[k].bezeichnung,
            "ansatz": old_items[k].ansatz_year1,
            "section": old_items[k].section,
        }
        for k in sorted(disc_keys)
        if old_items[k].ansatz_year1 and old_items[k].ansatz_year1 > 0
    ]
    discontinued.sort(key=lambda x: x["ansatz"] or 0, reverse=True)

    # Kapitel-level trends
    kapitel_totals: dict[str, dict[int, float]] = {}
    for plan in plans:
        items_result = await session.execute(
            select(BudgetItem).where(BudgetItem.plan_id == plan.id)
        )
        for item in items_result.scalars().all():
            if item.ansatz_year1 and item.ansatz_year1 > 0:
                if item.kapitel not in kapitel_totals:
                    kapitel_totals[item.kapitel] = {}
                kapitel_totals[item.kapitel].setdefault(plan.year1, 0)
                kapitel_totals[item.kapitel][plan.year1] += item.ansatz_year1

    kapitel_trends: list[KapitelTrend] = []
    for kap, totals in kapitel_totals.items():
        if oldest.year1 in totals and newest.year1 in totals and totals[oldest.year1] > 0:
            old_total = totals[oldest.year1]
            new_total = totals[newest.year1]
            change_pct = ((new_total - old_total) / old_total) * 100
            inflated = _inflate(old_total, oldest.year1, newest.year1)
            change_real = ((new_total - inflated) / inflated) * 100
            kapitel_trends.append(KapitelTrend(
                kapitel=kap,
                name=kap,
                totals=totals,
                change_pct=change_pct,
                change_real_pct=change_real,
            ))

    kapitel_trends.sort(key=lambda t: t.change_real_pct, reverse=True)

    logger.info(
        "Budget analysis: %d changes, %d new items, %d discontinued, %d kapitel trends",
        len(changes), len(new_only), len(discontinued), len(kapitel_trends),
    )

    return PatternReport(
        biggest_increases=biggest_increases,
        biggest_decreases=biggest_decreases,
        new_items=new_only[:limit],
        discontinued_items=discontinued[:limit],
        kapitel_trends=kapitel_trends,
    )
