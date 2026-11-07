"""Lettura annunci/candidature dal DB e conversione nella forma di ApplicationOut.

Usato da routers/applications.py (Gabriele) e routers/tracking.py (Matilde):
    from services.application_store import application_out, get_application_row
"""

from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from fixtures import fixture_job
from models import ApplicationRow, JobRow
from schemas import JobOut


def get_job_row(db: Session, job_id: int) -> JobRow:
    """Annuncio dal DB. Finché il Radar non ha riempito il DB (BLUEPRINT sez. 9) un id che esiste
    solo in fixtures/jobs.json viene copiato nel DB, così la candidatura ha un annuncio vero a cui puntare."""
    row = db.get(JobRow, job_id)
    if row is not None:
        return row
    job = JobOut.model_validate(fixture_job(job_id))  # 404 se non esiste neanche lì
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


def application_out(db: Session, row: ApplicationRow) -> dict[str, Any]:
    """Riga DB → forma di ApplicationOut (con l'annuncio incluso)."""
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
