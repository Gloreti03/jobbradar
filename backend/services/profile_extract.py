"""A — CV PDF + extra material -> structured Profile.

DeepSeek only accepts text: the PDF is converted to text (pypdf -> pdfminer -> OCR as fallbacks),
then a single call to the fast model.
"""

import io
import json
import logging
import re
import threading
import time
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


MAX_OCR_PAGES = 5
OCR_SCALE = 2.5  # render at ~180 dpi: good accuracy, ~1-3 s per page
OCR_MIN_SCORE = 0.5
# prefix of OCR text: tells the model (and the code) that spaces/characters may be off
OCR_NOTE = "[Text recovered with OCR: words may be joined together and a few characters may be wrong.]"
_ocr_engine = None
_ocr_lock = threading.Lock()


def _get_ocr_engine():
    """Loads RapidOCR once (slow the first time: onnxruntime + opencv imports)."""
    global _ocr_engine
    with _ocr_lock:
        if _ocr_engine is None:
            from rapidocr_onnxruntime import RapidOCR

            _ocr_engine = RapidOCR()
    return _ocr_engine


def warm_up_ocr() -> None:
    """Optional: preload the OCR engine (not done at startup: the heavy imports slow every request
    for ~1 min). The engine is otherwise loaded on the first scanned PDF."""
    start = time.monotonic()
    try:
        _get_ocr_engine()
        log.info("OCR engine ready in %.1fs", time.monotonic() - start)
    except Exception as err:  # OCR is optional
        log.warning("OCR engine not available: %s", err)


def _ocr_lines(items: list) -> list[str]:
    """RapidOCR boxes -> text lines in reading order (top to bottom, then left to right)."""
    boxes = []
    for box, text, score in items:
        if float(score) < OCR_MIN_SCORE or not text.strip():
            continue
        ys = [p[1] for p in box]
        boxes.append((min(ys), max(ys), min(p[0] for p in box), text.strip()))
    boxes.sort()
    lines: list[list[tuple]] = []
    for top, bottom, left, text in boxes:
        middle = (top + bottom) / 2
        if lines and lines[-1][0][0] <= middle <= lines[-1][0][1]:  # same line as the previous box
            lines[-1].append((top, bottom, left, text))
        else:
            lines.append([(top, bottom, left, text)])
    return [" ".join(t for *_, t in sorted(line, key=lambda b: b[2])) for line in lines]


def _ocr_text(data: bytes) -> str:
    """Last resort for scans and PDFs with broken fonts: render the pages and read them with OCR."""
    try:
        import numpy as np
        import pypdfium2 as pdfium
    except ImportError as err:  # OCR is optional: without it we just warn the user
        log.warning("OCR not available: %s", err)
        return ""
    start = time.monotonic()
    try:
        engine = _get_ocr_engine()
        pdf = pdfium.PdfDocument(data)
        pages = []
        for i in range(min(len(pdf), MAX_OCR_PAGES)):
            image = pdf[i].render(scale=OCR_SCALE).to_pil().convert("RGB")
            # no angle classifier: pages are upright, and it flips single digits (6 read as 9)
            result, _ = engine(np.array(image), use_cls=False)
            pages.append("\n".join(_ocr_lines(result or [])))
    except Exception as err:  # never let OCR break an upload
        log.warning("OCR failed: %s", err)
        return ""
    log.info("OCR read %d page(s) in %.1fs", len(pages), time.monotonic() - start)
    text = "\n\n".join(p for p in pages if p.strip())
    return f"{OCR_NOTE}\n{text}" if text else ""


def pdf_to_text(data: bytes) -> str:
    """PDF -> text. Tries pypdf, then pdfminer (different font decoding), then OCR (scans, broken fonts).
    Raises NotAPdf, or GarbledText when nothing gives readable text."""
    text = _pypdf_text(data)
    ok, reason = text_quality(text)
    if ok:
        return text
    alt = _pdfminer_text(data)
    if text_quality(alt)[0]:
        log.info("pypdf text was unusable (%s): using pdfminer", reason)
        return alt
    ocr = _ocr_text(data)
    if text_quality(ocr)[0]:
        log.info("pypdf and pdfminer text unusable (%s): using OCR", reason)
        return ocr
    raise GarbledText(reason)


_MONTHS = (r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|gen|mag|giu|lug|ago|set|ott|dic|mai|okt|des)"
           r"[a-zæøå]*\.?")
# 01/02/2000, 01.02.2000, 1 February 2000, 1February2000, February 1, 2000
_DATE = rf"(\d{{1,2}}[/.-]\d{{1,2}}[/.-]\d{{2,4}}|\d{{1,2}}\s*{_MONTHS}\s*\d{{4}}|{_MONTHS}\s*\d{{1,2}},?\s*\d{{4}})"

_SENSITIVE_PATTERNS = [
    # Italian codice fiscale (also when preceded by its label)
    (re.compile(r"(?i)(codice\s+fiscale\s*:?\s*)?\b[A-Z]{6}\d{2}[A-EHLMPR-T]\d{2}[A-Z]\d{3}[A-Z]\b"), "[tax id removed]"),
    # place + date of birth, Italian and English, also with OCR-joined words:
    # "nato a CITTÀ (XX), ITALIA il 01/02/2000", "born inCITY(XX)on1February 2000", "born in Oslo on 1 February 2000"
    (re.compile(rf"(?i)\bnat[oa]\s*a\s*[^\n]{{1,80}}?\bil\s*{_DATE}"), "[birth data removed]"),
    (re.compile(rf"(?i)\bborn\s*in\s*[^\n]{{1,80}}?\bon\s*{_DATE}"), "[birth data removed]"),
    (re.compile(rf"(?i)\b(born(\s*on)?|date\s*of\s*birth|birth\s*date|data\s*di\s*nascita|fødselsdato)\s*:?\s*{_DATE}"),
     "[birth date removed]"),
    # student ID numbers ("Student Identification No.: 000000", "matricola 0000000", "Studentnummer 123456")
    (re.compile(r"(?i)\b(matricola|student\s*(identification|id)?\s*(no\.?|number|n\.)?|studentnummer)\s*:?\s*[A-Z]?\d{4,}\b"),
     "[student id removed]"),
    # IBAN and Norwegian national identity number (11 digits)
    (re.compile(r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]){11,30}\b"), "[iban removed]"),
    (re.compile(r"(?i)\b(fødselsnummer|personnummer)\s*:?\s*\d{6}\s?\d{5}\b"), "[national id removed]"),
]


def redact_personal_ids(text: str) -> str:
    """Removes identifiers a profile never needs (tax code, birth data, student/national IDs, IBAN)
    from extra documents before they are stored or sent to the model."""
    for pattern, replacement in _SENSITIVE_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def file_to_text(filename: str, data: bytes) -> tuple[str, str | None]:
    """Text from an extra file (PDF, .txt, .md) -> (text, warning for the user or None).
    Personal identifiers (tax code, birth data, student IDs...) are removed here."""
    name = (filename or "").lower()
    if name.endswith(".pdf"):
        try:
            text = redact_personal_ids(pdf_to_text(data))
            if text.startswith(OCR_NOTE):
                return text, f"{filename}: read with OCR (scan or unreadable fonts). Check courses and grades in your profile."
            return text, None
        except UnreadableDocument as err:
            log.warning("Skipping extra PDF %s: %s", filename, err)
            return "", f"{filename}: the text could not be read ({err}). Paste its content in 'More about you'."
    if name.endswith(TEXT_EXTENSIONS):
        return redact_personal_ids(data.decode("utf-8", errors="ignore")), None
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


# words that describe a contract or level, not a role ("Internship" alone is not a target role)
_LEVEL_WORDS = {
    "intern": "intern", "interns": "intern", "internship": "intern", "internships": "intern",
    "trainee": "intern", "traineeship": "intern", "praksis": "intern", "sommerjobb": "intern",
    "summer": "intern", "graduate": "junior", "nyutdannet": "junior", "junior": "junior",
    "entry": "junior", "level": None, "job": None, "jobs": None, "position": None, "role": None,
    "program": None, "programme": None, "student": None, "part": None, "full": None, "time": None,
    "deltid": None, "heltid": None, "any": None, "opportunity": None, "opportunities": None,
}


def clean_preferences(profile: Profile) -> Profile:
    """Keeps only real job titles in preferences.roles: a role made only of level/contract words
    ("Internship", "Graduate program", "Part-time job") is dropped and becomes the seniority."""
    prefs = profile.preferences
    roles, level = [], None
    for role in _dedupe(prefs.roles):
        words = re.findall(r"[a-zæøå]+", role.lower())
        if words and all(w in _LEVEL_WORDS for w in words):
            level = level or next((_LEVEL_WORDS[w] for w in words if _LEVEL_WORDS[w]), None)
        else:
            roles.append(role)
    prefs.roles = roles
    if level and not prefs.seniority:
        prefs.seniority = level
    return profile


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
    return clean_preferences(profile)


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
    return clean_preferences(updated)
