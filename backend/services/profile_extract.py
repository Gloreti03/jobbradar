"""A — CV PDF + extra material -> structured Profile.

DeepSeek only accepts text: the PDF is converted with pypdf, then a single call to the fast model.
"""

import io
import json
import logging

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from llm import complete_json
from prompts import PROFILE_ANSWERS_SYSTEM, PROFILE_ANSWERS_USER, PROFILE_EXTRACT_SYSTEM, PROFILE_EXTRACT_USER
from schemas import MissingInfoAnswer, Profile

log = logging.getLogger(__name__)

MAX_CV_CHARS = 30_000
MAX_EXTRA_CHARS = 15_000
MAX_MISSING_INFO = 5
MAX_SEARCH_TERMS = 30
TEXT_EXTENSIONS = (".txt", ".md")


class UnreadableDocument(ValueError):
    """The file has no extractable text (e.g. a scanned PDF)."""


def pdf_to_text(data: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [page.extract_text() or "" for page in reader.pages]
    except (PdfReadError, ValueError, KeyError) as err:
        raise UnreadableDocument(f"Not a readable PDF: {err}") from err
    return "\n\n".join(p.strip() for p in pages if p.strip())


def file_to_text(filename: str, data: bytes) -> str:
    """Text from an extra file (PDF, .txt, .md). Other formats -> empty string."""
    name = (filename or "").lower()
    if name.endswith(".pdf"):
        try:
            return pdf_to_text(data)
        except UnreadableDocument:
            log.warning("Skipping unreadable extra PDF %s", filename)
            return ""
    if name.endswith(TEXT_EXTENSIONS):
        return data.decode("utf-8", errors="ignore")
    log.warning("Skipping unsupported extra file %s", filename)
    return ""


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out = []
    for item in items:
        key = item.strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append(item.strip())
    return out


def extract_profile(cv_text: str, extra_text: str = "") -> Profile:
    """Calls the model and cleans up the output (blueprint limits)."""
    if not cv_text.strip() and not extra_text.strip():
        raise UnreadableDocument("No CV text to analyse")
    user = PROFILE_EXTRACT_USER.format(
        cv_text=cv_text[:MAX_CV_CHARS] or "(no CV text: use the extra material)",
        extra_text=extra_text[:MAX_EXTRA_CHARS] or "(none)",
    )
    # fast model: the smart one takes ~45 s even on a one-page CV (BLUEPRINT: < 30 s)
    profile = complete_json("fast", PROFILE_EXTRACT_SYSTEM, user, Profile, temperature=0.1, max_tokens=8000)
    profile.search_terms = _dedupe(profile.search_terms)[:MAX_SEARCH_TERMS]
    profile.missing_info = _dedupe(profile.missing_info)[:MAX_MISSING_INFO]
    profile.skills = _dedupe(profile.skills)
    profile.tools = _dedupe(profile.tools)
    return profile


def format_answers(answers: list[MissingInfoAnswer]) -> str:
    return "\n".join(f"Q: {a.question.strip()}\nA: {a.answer.strip()}" for a in answers)


def apply_answers(profile: Profile, answers: list[MissingInfoAnswer]) -> Profile:
    """Updates the profile with the answers; answered questions leave missing_info."""
    user = PROFILE_ANSWERS_USER.format(
        profile_json=json.dumps(profile.model_dump(mode="json"), ensure_ascii=False),
        answers=format_answers(answers),
    )
    updated = complete_json("fast", PROFILE_ANSWERS_SYSTEM, user, Profile, temperature=0.1, max_tokens=8000)
    # identity and question list are never left to the model
    updated.name = profile.name
    updated.contacts = profile.contacts
    answered = {a.question.strip().lower() for a in answers}
    updated.missing_info = [q for q in profile.missing_info if q.strip().lower() not in answered]
    updated.search_terms = _dedupe(updated.search_terms or profile.search_terms)[:MAX_SEARCH_TERMS]
    updated.skills = _dedupe(updated.skills)
    updated.tools = _dedupe(updated.tools)
    return updated
