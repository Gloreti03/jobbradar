"""A — Profilo (owner: Gabriele). STUB: restituisce fixtures/profile.json."""

from datetime import datetime, timezone

from fastapi import APIRouter, File, Form, UploadFile

from fixtures import load_fixture
from schemas import ProfileOut, ProfileUpdate

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("", response_model=ProfileOut)
def get_profile():
    return load_fixture("profile")


@router.put("", response_model=ProfileOut)
def update_profile(body: ProfileUpdate):
    current = load_fixture("profile")
    return {
        "id": current["id"],
        "profile": body.profile,
        "extra_text": body.extra_text if body.extra_text is not None else current["extra_text"],
        "updated_at": datetime.now(timezone.utc),
    }


@router.post("/upload", response_model=ProfileOut)
def upload_profile(
    cv: UploadFile = File(..., description="CV in PDF"),
    extra_files: list[UploadFile] = File(default=[]),
    extra_text: str = Form(default=""),
):
    return load_fixture("profile")
