"""A — CV PDF + materiale extra → Profile strutturato.

DeepSeek accetta solo testo: il PDF si converte con pypdf, poi un'unica chiamata al modello smart.
"""

import io
import logging

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from llm import complete_json
from prompts import PROFILE_EXTRACT_SYSTEM, PROFILE_EXTRACT_USER
from schemas import Profile

log = logging.getLogger(__name__)

MAX_CV_CHARS = 30_000
MAX_EXTRA_CHARS = 15_000
MAX_MISSING_INFO = 5
MAX_SEARCH_TERMS = 30
TEXT_EXTENSIONS = (".txt", ".md")


class UnreadableDocument(ValueError):
    """Il file non contiene testo estraibile (es. PDF scansionato)."""


def pdf_to_text(data: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [page.extract_text() or "" for page in reader.pages]
    except (PdfReadError, ValueError, KeyError) as err:
        raise UnreadableDocument(f"Not a readable PDF: {err}") from err
    return "\n\n".join(p.strip() for p in pages if p.strip())


def file_to_text(filename: str, data: bytes) -> str:
    """Testo da un file extra (PDF, .txt, .md). Altri formati → stringa vuota."""
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
    """Chiama il modello e ripulisce l'output (limiti del blueprint)."""
    if not cv_text.strip() and not extra_text.strip():
        raise UnreadableDocument("No CV text to analyse")
    user = PROFILE_EXTRACT_USER.format(
        cv_text=cv_text[:MAX_CV_CHARS] or "(no CV text: use the extra material)",
        extra_text=extra_text[:MAX_EXTRA_CHARS] or "(none)",
    )
    # modello veloce: lo smart impiega ~45 s anche su un CV di una pagina (BLUEPRINT: < 30 s)
    profile = complete_json("fast", PROFILE_EXTRACT_SYSTEM, user, Profile, temperature=0.1, max_tokens=8000)
    profile.search_terms = _dedupe(profile.search_terms)[:MAX_SEARCH_TERMS]
    profile.missing_info = _dedupe(profile.missing_info)[:MAX_MISSING_INFO]
    profile.skills = _dedupe(profile.skills)
    profile.tools = _dedupe(profile.tools)
    return profile
