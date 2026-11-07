"""B — Current job, profile match and latest application (owner: Stefano)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import get_db
from models import ApplicationRow, JobRow, MatchRow
from radar.providers.base import as_utc, job_out
from schemas import JobDetail
from services.profile_store import get_profile_row

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobDetail)
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.get(JobRow, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    profile = get_profile_row(db)
    match = db.get(MatchRow, (profile.id, job_id)) if profile else None
    if match and as_utc(match.created_at) < as_utc(profile.updated_at):
        match = None
    application = db.scalar(select(ApplicationRow).where(ApplicationRow.job_id == job_id).order_by(ApplicationRow.id.desc()).limit(1))
    return {"job": job_out(job), "match": match, "application": application}
