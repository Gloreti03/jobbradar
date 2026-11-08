"""C — Applications (owner: Gabriele)."""

import threading
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db import get_db
from models import ApplicationRow
from schemas import ApplicationCreate, ApplicationOut, ApplicationPatch, JobOut
from services.application_store import application_out, get_application_row, get_job_row
from services.profile_store import get_profile, get_profile_row
from services.tailor import tailor

router = APIRouter(prefix="/applications", tags=["applications"])

# One generation at a time per job, so a double click does not create two identical drafts.
_job_locks: defaultdict[int, threading.Lock] = defaultdict(threading.Lock)


@router.get("", response_model=list[ApplicationOut])
def list_applications(db: Session = Depends(get_db)):
    rows = db.scalars(select(ApplicationRow).order_by(ApplicationRow.created_at.desc())).all()
    return [application_out(db, r) for r in rows]


@router.post("", response_model=ApplicationOut, status_code=201)
def create_application(body: ApplicationCreate, db: Session = Depends(get_db)):
    """Generate a tailored CV + cover letter for the job (~20 s). Initial status: draft."""
    profile = get_profile(db)
    if profile is None:
        raise HTTPException(status_code=404, detail="No profile yet: upload your CV first")
    job_row = get_job_row(db, body.job_id)
    extra_text = get_profile_row(db).extra_text

    # A draft for this job committed after this request arrived means the same request is
    # already being served (double click): return that draft instead of generating another.
    last_id = db.scalar(select(func.max(ApplicationRow.id))) or 0
    with _job_locks[job_row.id]:
        db.commit()  # end the read transaction so drafts committed meanwhile are visible
        duplicate = db.scalar(select(ApplicationRow).where(
            ApplicationRow.job_id == job_row.id, ApplicationRow.id > last_id,
        ).order_by(ApplicationRow.id))
        if duplicate is not None:
            return application_out(db, duplicate)
        return _create_draft(db, profile, job_row, extra_text)


def _create_draft(db: Session, profile, job_row, extra_text) -> ApplicationOut:
    language, cv, cover_letter, notes = tailor(profile, JobOut.model_validate(job_row), extra_text)

    row = ApplicationRow(
        job_id=job_row.id,
        status="draft",
        language=language,
        cv=cv.model_dump(mode="json"),
        cover_letter=cover_letter,
        notes=notes.model_dump(mode="json"),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return application_out(db, row)


@router.get("/{application_id}", response_model=ApplicationOut)
def get_application(application_id: int, db: Session = Depends(get_db)):
    return application_out(db, get_application_row(db, application_id))


@router.patch("/{application_id}", response_model=ApplicationOut)
def patch_application(application_id: int, body: ApplicationPatch, db: Session = Depends(get_db)):
    """Save the user's edits to CV / letter / status (tracker).
    For "I applied" use POST /applications/{id}/applied, which also saves the snapshot."""
    row = get_application_row(db, application_id)
    if body.cv is not None:
        row.cv = body.cv.model_dump(mode="json")
    if body.cover_letter is not None:
        row.cover_letter = body.cover_letter
    if body.status is not None:
        row.status = body.status
    db.commit()
    db.refresh(row)
    return application_out(db, row)
