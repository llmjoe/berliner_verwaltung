"""Load extracted budget data into the database."""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berliner_verwaltung.db.models import BudgetItem as BudgetItemModel
from berliner_verwaltung.db.models import BudgetPlan as BudgetPlanModel
from berliner_verwaltung.ingestion.haushalt.extractor import BudgetPlan, extract_budget_plan

logger = logging.getLogger(__name__)


async def load_budget_plan(session: AsyncSession, plan: BudgetPlan) -> BudgetPlanModel:
    """Store a BudgetPlan and its items in the database."""
    existing = await session.execute(
        select(BudgetPlanModel).where(
            BudgetPlanModel.reference == plan.reference,
            BudgetPlanModel.year1 == plan.year1,
        )
    )
    if existing.scalar_one_or_none():
        logger.info(
            "Budget plan %s (%d/%d) already exists, skipping",
            plan.reference, plan.year1, plan.year2,
        )
        return existing.scalar_one_or_none()  # type: ignore[return-value]

    db_plan = BudgetPlanModel(
        reference=plan.reference,
        file_id=plan.file_id if plan.file_id else None,
        year1=plan.year1,
        year2=plan.year2,
        kapitel_count=len(plan.kapitel_names),
        item_count=len(plan.items),
    )
    session.add(db_plan)
    await session.flush()

    for item in plan.items:
        session.add(BudgetItemModel(
            plan_id=db_plan.id,
            kapitel=item.kapitel,
            titel=item.titel,
            funktion=item.funktion,
            bezeichnung=item.bezeichnung,
            section=item.section,
            kennbuchstabe=item.kennbuchstabe,
            ansatz_year1=item.ansatz_year1,
            ansatz_year2=item.ansatz_year2,
            ansatz_prev=item.ansatz_prev,
            ist_prev=item.ist_prev,
            page=item.page,
            erlaeuterung=item.erlaeuterung,
        ))

    await session.commit()
    logger.info(
        "Loaded budget plan %s (%d/%d): %d items, %d Kapitel",
        plan.reference, plan.year1, plan.year2, len(plan.items), len(plan.kapitel_names),
    )
    return db_plan


BUDGET_PDFS = [
    (11668, "DS/1740/VI"),  # 2026/2027
    (10670, "DS/0830/VI"),  # 2024/2025
    (9830, "DS/0077/VI"),   # 2022/2023
]


async def load_all_budget_plans(
    session: AsyncSession, pdf_dir: Path = Path("data/pdfs")
) -> list[BudgetPlanModel]:
    results = []
    for file_id, reference in BUDGET_PDFS:
        pdf_path = pdf_dir / f"{file_id}.pdf"
        if not pdf_path.exists():
            logger.warning("PDF not found: %s", pdf_path)
            continue
        plan = extract_budget_plan(pdf_path, reference=reference, file_id=file_id)
        db_plan = await load_budget_plan(session, plan)
        results.append(db_plan)
    return results
