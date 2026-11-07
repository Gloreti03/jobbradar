"""B — Filter the local catalogue and rank its best candidates (owner: Stefano)."""

import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from openai import OpenAIError
from sqlalchemy import delete, select, text, update
from sqlalchemy.dialects.sqlite import insert

from config import DEEPSEEK_API_KEY
from db import SessionLocal
from llm import LLMError
from models import JobRow, MatchRow
from radar.filters import filter_jobs_with_funnel
from radar.liveness import check_jobs
from radar.providers.base import as_utc, job_out
from radar.ranking import rank_jobs
from radar.scanner import default_config, scan
from schemas import MatchOut, RadarRequest, RadarResponse, RadarResult
from services.profile_store import get_profile, get_profile_row

router = APIRouter(prefix="/radar", tags=["radar"])
logger = logging.getLogger(__name__)


@router.post("", response_model=RadarResponse)
async def run_radar(body: RadarRequest):
    """Funnel counts use days_used. ranked counts returned results, including cache hits."""
    with SessionLocal() as db:
        profile = get_profile(db)
        profile_row = get_profile_row(db)
        if profile is None or profile_row is None:
            raise HTTPException(status_code=404, detail="No profile yet: upload your CV before running Radar")
        profile_id = profile_row.id
        profile_data = profile_row.data
        profile_updated = as_utc(profile_row.updated_at)

    if body.refresh:
        try:
            async with asyncio.timeout(3):
                await scan(default_config(days=1, limit=12, max_pages=1, latest_only=True, sources=["nav"]))
        except (TimeoutError, OSError, ValueError, RuntimeError) as error:
            logger.warning("Light refresh unavailable; using saved catalogue (%s)", type(error).__name__)
        except Exception:
            logger.exception("Light refresh failed; using saved catalogue")

    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        jobs = list(db.scalars(select(JobRow).order_by(JobRow.id)))
        cached = list(db.scalars(select(MatchRow).where(MatchRow.profile_id == profile_id)))

    days_used = body.days
    candidates, funnel = filter_jobs_with_funnel(jobs, profile, days_used, body.english_only, now)
    for days in (14, 30):
        if days > days_used and sum(job.posted_at is not None for job in candidates) < 15:
            days_used = days
            candidates, funnel = filter_jobs_with_funnel(jobs, profile, days_used, body.english_only, now)
    candidates, closed_ids = await check_jobs(candidates)
    funnel.live = len(candidates)
    # Count the liveness outcome before limiting AI work to forty candidates.
    candidates = candidates[:40]
    if closed_ids:
        with SessionLocal.begin() as db:
            db.execute(update(JobRow).where(JobRow.id.in_(closed_ids)).values(status="inactive"))
            db.execute(delete(MatchRow).where(MatchRow.job_id.in_(closed_ids)))

    matches = {match.job_id: MatchOut.model_validate(match) for match in cached
               if profile_updated and as_utc(match.created_at) >= profile_updated}
    job_models = [job_out(job) for job in candidates]
    missing = [job for job in job_models if job.id not in matches]
    if missing:
        if not DEEPSEEK_API_KEY:
            raise HTTPException(status_code=503, detail="Set DEEPSEEK_API_KEY in backend/.env to rank real jobs")
        try:
            matches.update(await rank_jobs(profile, missing))
        except TimeoutError:
            raise HTTPException(status_code=504, detail="Ranking timed out. Retry with refresh disabled.") from None
        except (LLMError, OpenAIError) as error:
            logger.warning("Ranking failed (%s)", type(error).__name__)
            raise HTTPException(status_code=502, detail="Ranking unavailable. Please retry.") from None

    with SessionLocal.begin() as db:
        db.execute(text("BEGIN IMMEDIATE"))
        current_profile = get_profile_row(db)
        if current_profile is None or current_profile.data != profile_data or as_utc(current_profile.updated_at) != profile_updated:
            raise HTTPException(status_code=409, detail="Profile changed during ranking. Please retry.")
        for job in job_models:
            current_job = db.get(JobRow, job.id)
            if current_job is None or job_out(current_job) != job:
                raise HTTPException(status_code=409, detail="Jobs changed during ranking. Please retry.")
            values = dict(profile_id=profile_id, job_id=job.id, **matches[job.id].model_dump(), created_at=now)
            db.execute(insert(MatchRow).values(**values).on_conflict_do_update(
                index_elements=["profile_id", "job_id"], set_=values,
            ))

    ordered = sorted(job_models, key=lambda job: (job.posted_at is None, -matches[job.id].score, job.id))
    results = [RadarResult(job=job, match=matches[job.id]) for job in ordered[:15]]
    funnel.ranked = len(results)
    return RadarResponse(
        days_requested=body.days, days_used=days_used, widened=days_used > body.days,
        scanned_count=len(jobs), candidates_count=len(job_models),
        results=results,
        generated_at=datetime.now(timezone.utc),
        funnel=funnel,
    )
