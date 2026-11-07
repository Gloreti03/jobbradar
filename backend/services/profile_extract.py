"""A — CV PDF + extra material -> structured Profile.

DeepSeek only accepts text: the PDF is converted with pypdf, then a single call to the fast model.
"""

import io
import json
import logging
import re
import unicodedata

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
    """The file has no usable text."""


class NotAPdf(UnreadableDocument):
    """The bytes are not a PDF at all."""


class GarbledText(UnreadableDocument):
    """The PDF opens, but its text comes out empty or corrupted (scans, broken font encodings)."""


VOWELS = set("aeiouyæøå")


def text_quality(text: str) -> tuple[bool, str]:
    """Heuristic check that extracted text is real language and not font garbage.
    -> (ok, reason when not ok)."""
    sample = text[:20_000]
    if len(sample.strip()) < 50:
        return False, "almost no text (scanned PDF?)"
    bad = sum(
        1 for ch in sample
        if ch == "�" or 0xE000 <= ord(ch) <= 0xF8FF or (unicodedata.category(ch) == "Cc" and ch not in "\n\r\t")
    ) + 5 * sample.count("(cid:")
    if bad / len(sample) > 0.02:
        return False, "unreadable characters"
    latin = [unicodedata.normalize("NFD", ch)[0].lower() for ch in sample if ch.isalpha()]
    latin = [ch for ch in latin if "a" <= ch <= "z" or ch in "æøå"]
    if len(latin) > 100:
        vowel_ratio = sum(ch in VOWELS for ch in latin) / len(latin)
        if not 0.22 <= vowel_ratio <= 0.62:
            return False, "letters do not form words (broken font encoding)"
    tokens = sample.split()
    wordlike = sum(1 for t in tokens if re.fullmatch(r"[(\"'“]?[^\W\d_]{2,}[)\"'”.,;:!?%-]*", t))
    if tokens and wordlike / len(tokens) < 0.35:
        return False, "too few real words"
    return True, ""


def _pypdf_text(data: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [page.extract_text() or "" for page in reader.pages]
    except (PdfReadError, ValueError, KeyError) as err:
        raise NotAPdf(f"Not a readable PDF: {err}") from err
    return "\n\n".join(p.strip() for p in pages if p.strip())


def _pdfminer_text(data: bytes) -> str:
    try:
        from pdfminer.high_level import extract_text

        return extract_text(io.BytesIO(data)) or ""
    except Exception as err:  # pdfminer raises many different errors on odd PDFs
        log.warning("pdfminer failed: %s", err)
        return ""


def pdf_to_text(data: bytes) -> str:
    """PDF -> text. Tries pypdf, then pdfminer (different font decoding) if the text looks corrupted.
    Raises NotAPdf, or GarbledText when neither gives readable text."""
    text = _pypdf_text(data)
    ok, reason = text_quality(text)
    if ok:
        return text
    alt = _pdfminer_text(data)
    if text_quality(alt)[0]:
        log.info("pypdf text was unusable (%s): using pdfminer", reason)
        return alt
    raise GarbledText(reason)


def file_to_text(filename: str, data: bytes) -> tuple[str, str | None]:
    """Text from an extra file (PDF, .txt, .md) -> (text, warning for the user or None)."""
    name = (filename or "").lower()
    if name.endswith(".pdf"):
        try:
            return pdf_to_text(data), None
        except UnreadableDocument as err:
            log.warning("Skipping extra PDF %s: %s", filename, err)
            return "", f"{filename}: the text could not be read ({err}). Paste its content in 'More about you'."
    if name.endswith(TEXT_EXTENSIONS):
        return data.decode("utf-8", errors="ignore"), None
    return "", f"{filename}: unsupported file type (use PDF, .txt or .md)."


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
    # fast model without hidden reasoning: ~8 s vs ~30-40 s with it, same quality in tests (BLUEPRINT: < 30 s)
    profile = complete_json(
        "fast", PROFILE_EXTRACT_SYSTEM, user, Profile, temperature=0.1, max_tokens=8000, reasoning_effort="none"
    )
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
    updated = complete_json(
        "fast", PROFILE_ANSWERS_SYSTEM, user, Profile, temperature=0.1, max_tokens=8000, reasoning_effort="none"
    )
    # identity and question list are never left to the model
    updated.name = profile.name
    updated.contacts = profile.contacts
    answered = {a.question.strip().lower() for a in answers}
    updated.missing_info = [q for q in profile.missing_info if q.strip().lower() not in answered]
    updated.search_terms = _dedupe(updated.search_terms or profile.search_terms)[:MAX_SEARCH_TERMS]
    updated.skills = _dedupe(updated.skills)
    updated.tools = _dedupe(updated.tools)
    return updated
