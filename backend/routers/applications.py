"""C — Applications (owner: Gabriele)."""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from db import get_db
from models import ApplicationRow
from schemas import ApplicationCreate, ApplicationOut, ApplicationPatch, JobOut
from services.application_store import application_out, find_application_for_job, get_application_row, get_job_row
from services.profile_store import get_profile, get_profile_row
from services.tailor import tailor

router = APIRouter(prefix="/applications", tags=["applications"])


@router.get("", response_model=list[ApplicationOut])
def list_applications(db: Session = Depends(get_db)):
    rows = db.scalars(select(ApplicationRow).order_by(ApplicationRow.created_at.desc())).all()
    return [application_out(db, r) for r in rows]


@router.post("", response_model=ApplicationOut, status_code=201,
             responses={200: {"model": ApplicationOut, "description": "Existing application for this job"}})
def create_application(body: ApplicationCreate, response: Response, db: Session = Depends(get_db)):
    """Create one draft per job, or return the existing application without regenerating it."""
    profile = get_profile(db)
    if profile is None:
        raise HTTPException(status_code=404, detail="No profile yet: upload your CV first")
    existing = find_application_for_job(db, body.job_id)
    if existing is not None:
        response.status_code = 200
        return application_out(db, existing)

    job_row = get_job_row(db, body.job_id)
    profile_row = get_profile_row(db)
    profile_data, profile_updated, extra_text = profile_row.data, profile_row.updated_at, profile_row.extra_text

    language, cv, cover_letter, notes = tailor(profile, JobOut.model_validate(job_row), extra_text)

    # Do not hold a database write lock during the model call. Once documents are ready,
    # serialize the final lookup + insert across threads AND backend processes. A second
    # request may have saved this job while this request was generating its documents.
    db.rollback()  # end the read transaction and refresh objects before the locked check
    db.execute(text("BEGIN IMMEDIATE"))
    current_profile = get_profile_row(db)
    if (current_profile is None or current_profile.data != profile_data
            or current_profile.updated_at != profile_updated or current_profile.extra_text != extra_text):
        raise HTTPException(status_code=409, detail="Profile changed while creating the application. Please retry.")
    row = find_application_for_job(db, body.job_id)
    if row is not None:
        response.status_code = 200
    else:
        row = ApplicationRow(
            job_id=body.job_id,
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
