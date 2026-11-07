"""A — Profilo (owner: Gabriele)."""

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from db import get_db
from schemas import ProfileOut, ProfileUpdate
from services.profile_extract import UnreadableDocument, extract_profile, file_to_text, pdf_to_text
from services.profile_store import get_profile_row, save_profile, to_out

router = APIRouter(prefix="/profile", tags=["profile"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024


@router.get("", response_model=ProfileOut)
def get_profile(db: Session = Depends(get_db)):
    row = get_profile_row(db)
    if row is None:
        raise HTTPException(status_code=404, detail="No profile yet: upload your CV")
    return to_out(row)


@router.put("", response_model=ProfileOut)
def update_profile(body: ProfileUpdate, db: Session = Depends(get_db)):
    return to_out(save_profile(db, body.profile, body.extra_text))


@router.post("/upload", response_model=ProfileOut)
def upload_profile(
    cv: UploadFile | None = File(default=None, description="CV in PDF"),
    extra_files: list[UploadFile] = File(default=[]),
    extra_text: str = Form(default=""),
    db: Session = Depends(get_db),
):
    """CV PDF + file extra (PDF/.txt/.md) + testo libero → profilo (10-30 s)."""
    cv_text = ""
    if cv is not None and cv.filename:
        data = cv.file.read(MAX_UPLOAD_BYTES + 1)
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="CV file is larger than 10 MB")
        try:
            cv_text = pdf_to_text(data)
        except UnreadableDocument:
            raise HTTPException(status_code=400, detail="The CV must be a PDF file")

    extra_parts = [extra_text.strip()] if extra_text.strip() else []
    for f in extra_files:
        text = file_to_text(f.filename or "", f.file.read(MAX_UPLOAD_BYTES))
        if text.strip():
            extra_parts.append(f"--- {f.filename} ---\n{text.strip()}")
    extra = "\n\n".join(extra_parts)

    if not cv_text.strip() and not extra:
        raise HTTPException(
            status_code=422,
            detail="Could not read any text from the CV. Paste your CV text in the 'more about you' field.",
        )

    profile = extract_profile(cv_text, extra)
    return to_out(save_profile(db, profile, extra))
