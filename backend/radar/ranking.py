"""Validated AI matching in parallel batches of ten through llm.py."""

import asyncio
import json

from pydantic import BaseModel, Field

from llm import LLMError, acomplete_json
from prompts import NO_INVENTION_RULES, RANKING_SYSTEM
from schemas import JobOut, MatchOut, Profile


class RankedJob(BaseModel):
    job_id: int
    match: MatchOut


class RankingBatch(BaseModel):
    results: list[RankedJob] = Field(max_length=10)


async def rank_jobs(profile: Profile, jobs: list[JobOut]) -> dict[int, MatchOut]:
    async def rank_batch(batch: list[JobOut]):
        payload = {
            "profile": profile.model_dump(mode="json", exclude={"contacts", "missing_info", "search_terms"}),
            "jobs": [{
                "job_id": job.id, "title": job.title, "company": job.company,
                "location": job.location, "description": (job.description or "")[:6500],
                "language": job.language, "norwegian_required": job.norwegian_required,
            } for job in batch],
        }
        result = await acomplete_json(
            "fast", system=f"{RANKING_SYSTEM}\n\n{NO_INVENTION_RULES}",
            user=json.dumps(payload, ensure_ascii=False), schema=RankingBatch,
            temperature=0, max_tokens=4500, retries=0, reasoning_effort="none",
        )
        expected = {job.id for job in batch}
        returned = [entry.job_id for entry in result.results]
        if set(returned) != expected or len(returned) != len(expected):
            raise LLMError("Ranking must return each supplied job_id exactly once")
        return {entry.job_id: entry.match for entry in result.results}

    async with asyncio.timeout(18):
        batches = await asyncio.gather(*(rank_batch(jobs[start:start + 10]) for start in range(0, len(jobs), 10)))
    return {job_id: match for batch in batches for job_id, match in batch.items()}
