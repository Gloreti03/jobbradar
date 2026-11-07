"""C — Candidature (owner: Gabriele)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import get_db
from models import ApplicationRow
from schemas import ApplicationCreate, ApplicationOut, ApplicationPatch, JobOut
from services.application_store import application_out, get_application_row, get_job_row
from services.profile_store import get_profile, get_profile_row
from services.tailor import tailor

router = APIRouter(prefix="/applications", tags=["applications"])


@router.get("", response_model=list[ApplicationOut])
def list_applications(db: Session = Depends(get_db)):
    rows = db.scalars(select(ApplicationRow).order_by(ApplicationRow.created_at.desc())).all()
    return [application_out(db, r) for r in rows]


@router.post("", response_model=ApplicationOut, status_code=201)
def create_application(body: ApplicationCreate, db: Session = Depends(get_db)):
    """Genera CV + cover letter su misura per l'annuncio (10-30 s). Stato iniziale: draft."""
    profile = get_profile(db)
    if profile is None:
        raise HTTPException(status_code=404, detail="No profile yet: upload your CV first")
    job_row = get_job_row(db, body.job_id)
    extra_text = get_profile_row(db).extra_text

    language, out = tailor(profile, JobOut.model_validate(job_row), extra_text)

    row = ApplicationRow(
        job_id=job_row.id,
        status="draft",
        language=language,
        cv=out.cv.model_dump(mode="json"),
        cover_letter=out.cover_letter,
        notes=out.notes.model_dump(mode="json"),
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
    """Salva le modifiche dell'utente a CV / lettera / stato (tracker).
    Per "I applied" usare POST /applications/{id}/applied, che salva anche lo snapshot."""
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
