"""A — Profile (owner: Gabriele)."""

import re

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from db import get_db
from schemas import MissingInfoAnswer, ProfileAnswers, ProfileOut, ProfileUpdate
from services.profile_extract import (
    GarbledText,
    NotAPdf,
    apply_answers,
    extract_profile,
    file_to_text,
    format_answers,
    pdf_to_text,
)
from services.profile_store import get_profile as load_profile
from services.profile_store import get_profile_row, reset_user_data, same_person, save_profile, to_out

router = APIRouter(prefix="/profile", tags=["profile"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024


@router.get("", response_model=ProfileOut)
def get_profile(db: Session = Depends(get_db)):
    row = get_profile_row(db)
    if row is None:
        raise HTTPException(status_code=404, detail="No profile yet: upload your CV")
    return to_out(row)


NOTES_QUESTION = "More about you (free notes written by the candidate on the profile page)"
_SECTION = re.compile(r"(?:^|\n)--- [^\n]+ ---\r?\n")


def _notes(extra_text: str | None) -> str:
    """The candidate's free notes: the part of extra_text before the first '--- file ---' section
    (document text and earlier answers follow; same split as the frontend)."""
    text = extra_text or ""
    marker = _SECTION.search(text)
    return (text[: marker.start()] if marker else text).strip()


@router.put("", response_model=ProfileOut)
def update_profile(body: ProfileUpdate, db: Session = Depends(get_db)):
    """Manual edits are saved as they are. If the free notes changed, the model also reads them
    and updates the profile (skills, preferences, search terms), so the notes reach the Radar
    and not only the tailored applications (~5-10 s in that case)."""
    profile = body.profile
    row = get_profile_row(db)
    new_notes = _notes(body.extra_text)
    if body.extra_text is not None and new_notes and new_notes != _notes(row.extra_text if row else ""):
        profile = apply_answers(profile, [MissingInfoAnswer(question=NOTES_QUESTION, answer=new_notes)])
    return to_out(save_profile(db, profile, body.extra_text))


@router.post("/answers", response_model=ProfileOut)
def answer_missing_info(body: ProfileAnswers, db: Session = Depends(get_db)):
    """Answers to profile.missing_info -> updated profile (~5-10 s).
    Answered questions disappear from missing_info; the Q&A is also kept in extra_text for tailoring."""
    answers = [a for a in body.answers if a.answer.strip()]
    if not answers:
        raise HTTPException(status_code=422, detail="Write at least one answer")
    profile = load_profile(db)
    if profile is None:
        raise HTTPException(status_code=404, detail="No profile yet: upload your CV")
    updated = apply_answers(profile, answers)
    extra = get_profile_row(db).extra_text.strip()
    extra = f"{extra}\n\n--- Answers to profile questions ---\n{format_answers(answers)}".strip()
    return to_out(save_profile(db, updated, extra))


@router.post("/upload", response_model=ProfileOut)
def upload_profile(
    cv: UploadFile | None = File(default=None, description="CV in PDF"),
    extra_files: list[UploadFile] = File(default=[]),
    extra_text: str = Form(default=""),
    db: Session = Depends(get_db),
):
    """CV PDF + extra files (PDF/.txt/.md) + free text -> profile (~10-20 s).
    Files whose text cannot be read are skipped and listed in `warnings`.
    A CV of a different person (other name) deletes the previous candidate's matches,
    applications and interviews (`reset: true`)."""
    cv_text = ""
    warnings: list[str] = []
    if cv is not None and cv.filename:
        data = cv.file.read(MAX_UPLOAD_BYTES + 1)
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="CV file is larger than 10 MB")
        try:
            cv_text = pdf_to_text(data)  # OCR, when needed, is silent: no warning if it worked
        except NotAPdf:
            raise HTTPException(status_code=400, detail="The CV must be a PDF file")
        except GarbledText as err:
            warnings.append(f"{cv.filename}: the text could not be read ({err}). Paste your CV text in 'More about you'.")

    extra_parts = [extra_text.strip()] if extra_text.strip() else []
    for f in extra_files:
        text, warning = file_to_text(f.filename or "", f.file.read(MAX_UPLOAD_BYTES))
        if warning:
            warnings.append(warning)
        if text.strip():
            extra_parts.append(f"--- {f.filename} ---\n{text.strip()}")
    extra = "\n\n".join(extra_parts)

    if not cv_text.strip() and not extra:
        raise HTTPException(
            status_code=422,
            detail=(warnings[0] if warnings else "Could not read any text from the CV.")
            + " Paste your CV text in the 'More about you' field.",
        )

    profile = extract_profile(cv_text, extra)
    # a CV of a different person starts from zero: no Radar matches, applications or interviews
    # of the previous candidate (same person re-uploading keeps everything)
    previous = load_profile(db)
    reset = previous is not None and not same_person(previous.name, profile.name)
    if reset:
        reset_user_data(db)  # committed together with the new profile in save_profile
    return to_out(save_profile(db, profile, extra), warnings, reset=reset)
