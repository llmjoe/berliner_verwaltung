"""Anomaly detection in budget and paper data.

Identifies statistically unusual patterns:
- Budget items with outsized growth/decline
- Kapitel where spending diverges from district average
- Unusual paper activity spikes on specific topics
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berliner_verwaltung.db.models import BudgetItem, BudgetPlan

logger = logging.getLogger(__name__)


@dataclass
class Anomaly:
    type: str
    description: str
    kapitel: str
    titel: str
    metric: str
    value: float
    expected: float
    z_score: float
    severity: str  # "low", "medium", "high"


async def detect_budget_anomalies(session: AsyncSession) -> list[Anomaly]:
    """Detect anomalies in budget changes between oldest and newest plan."""
    plans_result = await session.execute(
        select(BudgetPlan).order_by(BudgetPlan.year1)
    )
    plans = list(plans_result.scalars().all())
    if len(plans) < 2:
        return []

    oldest, newest = plans[0], plans[-1]

    old_result = await session.execute(
        select(BudgetItem).where(BudgetItem.plan_id == oldest.id)
    )
    new_result = await session.execute(
        select(BudgetItem).where(BudgetItem.plan_id == newest.id)
    )

    old_items = {f"{i.kapitel}/{i.titel}": i for i in old_result.scalars().all()}
    new_items = {f"{i.kapitel}/{i.titel}": i for i in new_result.scalars().all()}

    # Calculate percentage changes for all common items
    pct_changes: list[tuple[str, float, BudgetItem, BudgetItem]] = []
    common_keys = set(old_items.keys()) & set(new_items.keys())

    for key in common_keys:
        old = old_items[key]
        new = new_items[key]
        if old.ansatz_year1 and new.ansatz_year1 and old.ansatz_year1 > 1000:
            pct = ((new.ansatz_year1 - old.ansatz_year1) / old.ansatz_year1) * 100
            pct_changes.append((key, pct, old, new))

    if not pct_changes:
        return []

    # Calculate mean and std of percentage changes
    values = [p[1] for p in pct_changes]
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    std = math.sqrt(variance) if variance > 0 else 1.0

    anomalies: list[Anomaly] = []
    for _key, pct, old, new in pct_changes:
        z = (pct - mean) / std
        if abs(z) < 2.0:
            continue

        severity = "low"
        if abs(z) > 3.0:
            severity = "high"
        elif abs(z) > 2.5:
            severity = "medium"

        direction = "increase" if pct > 0 else "decrease"
        anomalies.append(Anomaly(
            type=f"budget_{direction}",
            description=(
                f"{new.bezeichnung}: {pct:+.1f}% "
                f"({old.ansatz_year1:,.0f} -> {new.ansatz_year1:,.0f} EUR)"
            ),
            kapitel=new.kapitel,
            titel=new.titel,
            metric="change_pct",
            value=pct,
            expected=mean,
            z_score=z,
            severity=severity,
        ))

    anomalies.sort(key=lambda a: abs(a.z_score), reverse=True)

    logger.info(
        "Found %d budget anomalies (mean change: %.1f%%, std: %.1f%%)",
        len(anomalies), mean, std,
    )
    return anomalies
