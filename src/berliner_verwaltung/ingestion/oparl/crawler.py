"""OParl crawler: fetches all entities from a BVV OParl endpoint into the database.

Implements incremental crawling via content hashing — only inserts/updates
objects whose content has actually changed since the last crawl.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berliner_verwaltung.db.models import (
    AgendaItem,
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
from berliner_verwaltung.ingestion.oparl.client import OparlClient
from berliner_verwaltung.ingestion.oparl.schemas import (
    OparlAgendaItem,
    OparlBody,
    OparlConsultation,
    OparlFile,
    OparlMeeting,
    OparlMembership,
    OparlOrganization,
    OparlPaper,
    OparlPerson,
)

logger = logging.getLogger(__name__)


def _content_hash(data: dict[str, Any]) -> str:
    canonical = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


class OparlCrawler:
    def __init__(self, client: OparlClient, session: AsyncSession) -> None:
        self.client = client
        self.session = session
        self.stats = {"fetched": 0, "new": 0, "updated": 0, "unchanged": 0, "errors": 0}

    async def _upsert_raw(self, oparl_id: str, oparl_type: str, data: dict[str, Any]) -> bool:
        """Store raw JSON. Returns True if the object is new or changed."""
        content_hash = _content_hash(data)

        result = await self.session.execute(
            select(RawOparlObject).where(RawOparlObject.oparl_id == oparl_id)
        )
        existing = result.scalar_one_or_none()

        if existing:
            if existing.content_hash == content_hash:
                self.stats["unchanged"] += 1
                return False
            existing.data = data
            existing.content_hash = content_hash
            existing.fetched_at = dt.datetime.now(dt.UTC)
            self.stats["updated"] += 1
            return True

        raw_obj = RawOparlObject(
            oparl_id=oparl_id,
            oparl_type=oparl_type,
            data=data,
            content_hash=content_hash,
        )
        self.session.add(raw_obj)
        self.stats["new"] += 1
        return True

    async def _get_or_create_body(self, oparl_body: OparlBody) -> Body:
        result = await self.session.execute(
            select(Body).where(Body.oparl_id == str(oparl_body.id))
        )
        body = result.scalar_one_or_none()
        if body:
            body.name = oparl_body.name
            body.short_name = oparl_body.short_name
            body.website = str(oparl_body.website) if oparl_body.website else None
            return body

        body = Body(
            oparl_id=str(oparl_body.id),
            name=oparl_body.name,
            short_name=oparl_body.short_name,
            website=str(oparl_body.website) if oparl_body.website else None,
        )
        self.session.add(body)
        await self.session.flush()
        return body

    async def _normalize_organization(
        self, data: dict[str, Any], body_id: int
    ) -> None:
        parsed = OparlOrganization.model_validate(data)
        result = await self.session.execute(
            select(Organization).where(Organization.oparl_id == str(parsed.id))
        )
        org = result.scalar_one_or_none()
        if org:
            org.name = parsed.name
            org.short_name = parsed.short_name
            org.organization_type = parsed.organization_type
            org.start_date = parsed.start_date
            org.end_date = parsed.end_date
            org.data = data
        else:
            self.session.add(
                Organization(
                    oparl_id=str(parsed.id),
                    body_id=body_id,
                    name=parsed.name,
                    short_name=parsed.short_name,
                    organization_type=parsed.organization_type,
                    start_date=parsed.start_date,
                    end_date=parsed.end_date,
                    data=data,
                )
            )

    async def _normalize_person(self, data: dict[str, Any], body_id: int) -> None:
        parsed = OparlPerson.model_validate(data)
        result = await self.session.execute(
            select(Person).where(Person.oparl_id == str(parsed.id))
        )
        person = result.scalar_one_or_none()
        emails = parsed.email[0] if parsed.email else None
        if person:
            person.name = parsed.name
            person.family_name = parsed.family_name
            person.given_name = parsed.given_name
            person.form_of_address = parsed.form_of_address
            person.title = parsed.title[0] if parsed.title else None
            person.email = emails
            person.data = data
        else:
            self.session.add(
                Person(
                    oparl_id=str(parsed.id),
                    body_id=body_id,
                    name=parsed.name,
                    family_name=parsed.family_name,
                    given_name=parsed.given_name,
                    form_of_address=parsed.form_of_address,
                    title=parsed.title[0] if parsed.title else None,
                    email=emails,
                    data=data,
                )
            )

    async def _normalize_meeting(self, data: dict[str, Any], body_id: int) -> None:
        parsed = OparlMeeting.model_validate(data)
        result = await self.session.execute(
            select(Meeting).where(Meeting.oparl_id == str(parsed.id))
        )
        location_name = None
        if parsed.location and isinstance(parsed.location, dict):
            location_name = parsed.location.get("description") or parsed.location.get("name")

        meeting = result.scalar_one_or_none()
        if meeting:
            meeting.name = parsed.name
            meeting.meeting_state = parsed.meeting_state
            meeting.start = parsed.start
            meeting.end = parsed.end
            meeting.location_name = location_name
            meeting.cancelled = parsed.cancelled
            meeting.data = data
        else:
            meeting = Meeting(
                oparl_id=str(parsed.id),
                body_id=body_id,
                name=parsed.name,
                meeting_state=parsed.meeting_state,
                start=parsed.start,
                end=parsed.end,
                location_name=location_name,
                cancelled=parsed.cancelled,
                data=data,
            )
            self.session.add(meeting)
            await self.session.flush()

        for ai_data in parsed.agenda_item:
            ai_parsed = OparlAgendaItem.model_validate(ai_data)
            ai_result = await self.session.execute(
                select(AgendaItem).where(AgendaItem.oparl_id == str(ai_parsed.id))
            )
            ai = ai_result.scalar_one_or_none()
            if ai:
                ai.number = ai_parsed.number
                ai.name = ai_parsed.name
                ai.public = ai_parsed.public
                ai.result = ai_parsed.result
                ai.resolution_text = ai_parsed.resolution_text
                ai.data = ai_data
            else:
                self.session.add(
                    AgendaItem(
                        oparl_id=str(ai_parsed.id),
                        meeting_id=meeting.id,
                        number=ai_parsed.number,
                        name=ai_parsed.name,
                        public=ai_parsed.public,
                        result=ai_parsed.result,
                        resolution_text=ai_parsed.resolution_text,
                        data=ai_data,
                    )
                )

    async def _normalize_paper(self, data: dict[str, Any], body_id: int) -> None:
        parsed = OparlPaper.model_validate(data)
        result = await self.session.execute(
            select(Paper).where(Paper.oparl_id == str(parsed.id))
        )
        main_file_url = None
        if parsed.main_file:
            main_file_url = parsed.main_file.get("accessUrl") or parsed.main_file.get(
                "downloadUrl"
            )

        paper = result.scalar_one_or_none()
        if paper:
            paper.name = parsed.name
            paper.reference = parsed.reference
            paper.paper_type = parsed.paper_type
            paper.date = parsed.date
            paper.main_file_url = main_file_url
            paper.data = data
        else:
            paper = Paper(
                oparl_id=str(parsed.id),
                body_id=body_id,
                name=parsed.name,
                reference=parsed.reference,
                paper_type=parsed.paper_type,
                date=parsed.date,
                main_file_url=main_file_url,
                data=data,
            )
            self.session.add(paper)
            await self.session.flush()

        all_files = []
        if parsed.main_file:
            all_files.append(parsed.main_file)
        all_files.extend(parsed.auxiliary_file)

        for file_data in all_files:
            file_parsed = OparlFile.model_validate(file_data)
            file_result = await self.session.execute(
                select(File).where(File.oparl_id == str(file_parsed.id))
            )
            existing_file = file_result.scalar_one_or_none()
            if not existing_file:
                self.session.add(
                    File(
                        oparl_id=str(file_parsed.id),
                        paper_id=paper.id,
                        name=file_parsed.name,
                        file_name=file_parsed.file_name,
                        mime_type=file_parsed.mime_type,
                        access_url=str(file_parsed.access_url) if file_parsed.access_url else None,
                        download_url=(
                            str(file_parsed.download_url) if file_parsed.download_url else None
                        ),
                        text=file_parsed.text,
                        data=file_data,
                    )
                )

    async def crawl(self) -> CrawlLog:
        log = CrawlLog(source="oparl_fhk", status="running")
        self.session.add(log)
        await self.session.flush()

        try:
            body_data = await self.client.get_body()
            await self._upsert_raw(str(body_data["id"]), "Body", body_data)
            oparl_body = OparlBody.model_validate(body_data)
            body = await self._get_or_create_body(oparl_body)

            entity_lists = [
                ("organization", self._normalize_organization),
                ("person", self._normalize_person),
                ("meeting", self._normalize_meeting),
                ("paper", self._normalize_paper),
            ]

            for entity_name, normalizer in entity_lists:
                list_url = getattr(oparl_body, entity_name, None)
                if not list_url:
                    logger.warning("No %s list URL found in body", entity_name)
                    continue

                logger.info("Crawling %s from %s", entity_name, list_url)
                async for item in self.client.get_all_of_type(str(list_url)):
                    self.stats["fetched"] += 1
                    oparl_id = item.get("id", "")
                    oparl_type = item.get("type", "")

                    changed = await self._upsert_raw(oparl_id, oparl_type, item)
                    if changed:
                        try:
                            await normalizer(item, body.id)
                        except Exception as e:
                            self.stats["errors"] += 1
                            logger.warning(
                                "Failed to normalize %s %s: %s", entity_name, oparl_id, e
                            )

                    if self.stats["fetched"] % 100 == 0:
                        await self.session.flush()
                        logger.info("Progress: %s objects fetched", self.stats["fetched"])

                await self.session.flush()

            log.finished_at = dt.datetime.now(dt.UTC)
            log.objects_fetched = self.stats["fetched"]
            log.objects_new = self.stats["new"]
            log.objects_updated = self.stats["updated"]
            log.status = "completed"
            await self.session.commit()

            logger.info(
                "Crawl completed: %d fetched, %d new, %d updated, %d unchanged, %d errors",
                self.stats["fetched"],
                self.stats["new"],
                self.stats["updated"],
                self.stats["unchanged"],
                self.stats["errors"],
            )

        except Exception:
            log.status = "failed"
            import traceback

            log.error_message = traceback.format_exc()
            await self.session.commit()
            raise

        return log
