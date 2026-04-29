"""Data quality validation for pipeline outputs.

Validates LLM-generated references against the actual database,
detects hallucinated IDs, and scores output quality.
"""

from __future__ import annotations

import logging
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berliner_verwaltung.db.models import File, Meeting, Organization, Paper, Person

logger = logging.getLogger(__name__)

REFERENCE_PATTERN = re.compile(r"DS/\d{4}(?:-\d+)?/[IVX]+")
OPARL_ID_PATTERN = re.compile(
    r"https?://www\.sitzungsdienst[^/]+/oi/oparl/[\d.]+/\w+\.asp\?[^\s\"']+"
)


async def validate_paper_reference(session: AsyncSession, reference: str) -> bool:
    result = await session.execute(select(Paper.id).where(Paper.reference == reference).limit(1))
    return result.scalar() is not None


async def validate_oparl_id(session: AsyncSession, oparl_id: str) -> bool:
    for model in [Paper, Meeting, Organization, Person, File]:
        result = await session.execute(
            select(model.id).where(model.oparl_id == oparl_id).limit(1)  # type: ignore[attr-defined]
        )
        if result.scalar() is not None:
            return True
    return False


async def check_references_in_text(session: AsyncSession, text: str) -> dict:
    """Find and validate all DS/ references and OParl IDs in a text.

    Returns {"valid": [...], "invalid": [...], "score": 0.0-1.0}
    """
    ds_refs = REFERENCE_PATTERN.findall(text)
    oparl_ids = OPARL_ID_PATTERN.findall(text)

    valid = []
    invalid = []

    for ref in ds_refs:
        if await validate_paper_reference(session, ref):
            valid.append(ref)
        else:
            invalid.append(ref)

    for oid in oparl_ids:
        if await validate_oparl_id(session, oid):
            valid.append(oid)
        else:
            invalid.append(oid)

    total = len(valid) + len(invalid)
    score = len(valid) / total if total > 0 else 1.0

    if invalid:
        logger.warning("Hallucinated references found: %s", invalid)

    return {"valid": valid, "invalid": invalid, "score": score}


async def validate_classification(session: AsyncSession, paper_id: int) -> dict:
    """Validate that a paper's classification data is consistent."""
    result = await session.execute(select(Paper).where(Paper.id == paper_id))
    paper = result.scalar_one_or_none()
    if not paper:
        return {"valid": False, "reason": "paper not found"}

    if not paper.data or "classification" not in paper.data:
        return {"valid": False, "reason": "no classification"}

    classification = paper.data["classification"]
    issues = []

    if "topics" not in classification:
        issues.append("missing topics list")
    elif not classification["topics"]:
        issues.append("empty topics list")

    if "method" not in classification:
        issues.append("missing method attribution")

    if "confidence" not in classification:
        issues.append("missing confidence score")
    elif not 0.0 <= classification.get("confidence", 0) <= 1.0:
        issues.append("confidence out of range")

    return {"valid": len(issues) == 0, "issues": issues}
