"""Reads jobs/applications from the DB and converts them to the ApplicationOut shape.

Used by routers/applications.py (Gabriele) and routers/tracking.py (Matilde):
    from services.application_store import application_out, get_application_row
"""

from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from fixtures import fixture_job
from models import ApplicationRow, JobRow
from schemas import JobOut


def get_job_row(db: Session, job_id: int) -> JobRow:
    """Job from the DB. Until the Radar has filled the DB (fixtures), an id that exists
    only in fixtures/jobs.json is copied into the DB, so the application has a real job to point to."""
    row = db.get(JobRow, job_id)
    if row is not None:
        return row
    job = JobOut.model_validate(fixture_job(job_id))  # 404 if it does not exist there either
    row = JobRow(**job.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_application_row(db: Session, application_id: int) -> ApplicationRow:
    row = db.get(ApplicationRow, application_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Application {application_id} not found")
    return row


def find_application_for_job(db: Session, job_id: int) -> ApplicationRow | None:
    """Reuse the latest existing row, including databases with historical duplicates."""
    return db.scalar(select(ApplicationRow).where(ApplicationRow.job_id == job_id)
                     .order_by(ApplicationRow.id.desc()).limit(1))


def application_out(db: Session, row: ApplicationRow) -> dict[str, Any]:
    """DB row -> ApplicationOut shape (job included)."""
    job = db.get(JobRow, row.job_id)
    return {
        "id": row.id,
        "job_id": row.job_id,
        "job": JobOut.model_validate(job),
        "status": row.status,
        "language": row.language,
        "cv": row.cv,
        "cover_letter": row.cover_letter,
        "notes": row.notes,
        "snapshot": row.snapshot,
        "created_at": row.created_at,
        "applied_at": row.applied_at,
    }
