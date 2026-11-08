"""C — Profile + job ad -> tailored CV + cover letter + notes.

One model call in three steps: requirement_map (requirement -> verbatim evidence) first,
then the CV and the cover letter built from it.

Safety nets in code, on top of the prompt rules:
- every evidence quote must literally exist in the candidate's material, otherwise it is dropped
  (and a requirement left without evidence becomes "missing");
- name, contacts, languages, dates and companies ALWAYS come from the profile, never from the model.
"""

import json
from datetime import date
import logging
import re
from typing import Any

from llm import complete_json
from prompts import TAILOR_SYSTEM, TAILOR_USER
from schemas import ApplicationNotes, DocLanguage, JobOut, Profile, RequirementMatch, Schema, TailoredCV

log = logging.getLogger("tailor")

MAX_DESCRIPTION_CHARS = 12_000
MAX_MISSING_REQUIREMENTS = 6  # more than this does not fit on a card
MIN_WORD_OVERLAP = 0.85  # share of a quote's words that must appear in the material
REASONING_EFFORT = "none"  # no hidden reasoning: ~2x faster (target: < 30 s)
NORWEGIAN_OK_LEVELS = {"native", "c2", "c1", "b2"}
NORWEGIAN_NAMES = {"norwegian", "norsk", "bokmål", "bokmal", "nynorsk"}


class _ModelNotes(Schema):
    keywords_covered: list[str] = []
    changes: list[str] = []


class TailorOutput(Schema):
    # field order matters: the model writes the map first and builds the documents on it
    requirement_map: list[RequirementMatch] = []
    cv: TailoredCV
    cover_letter: str
    notes: _ModelNotes = _ModelNotes()


def _normalize(text: str) -> str:
    """Lowercase, punctuation-insensitive: "English: C1" and "English (C1)" both -> "english c1"."""
    text = re.sub(r"[^\w]+", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for v in value.values() for s in _strings(v)]
    if isinstance(value, list):
        return [s for v in value for s in _strings(v)]
    return []


def candidate_corpus(profile: Profile, extra_text: str) -> str:
    """All the candidate's facts as one normalized string (what evidence quotes are checked against)."""
    return _normalize(" \n ".join(_strings(profile.model_dump(mode="json")) + [extra_text]))


def is_grounded(quote: str, corpus: str, corpus_words: set[str]) -> bool:
    """True if the quote is literally in the material (or nearly: >= 85% of its words, min 3 words)."""
    q = _normalize(quote)
    if len(q) < 2:
        return False
    if f" {q} " in f" {corpus} ":  # whole words only: "Java" must not match "JavaScript"
        return True
    words = [w for w in re.findall(r"[^\W_]+", q) if len(w) >= 3]
    if len(words) < 3:
        return False
    return sum(w in corpus_words for w in words) / len(words) >= MIN_WORD_OVERLAP


def verify_requirement_map(
    items: list[RequirementMatch], profile: Profile, extra_text: str
) -> tuple[list[RequirementMatch], int]:
    """Drops evidence not found in the material; a met/partial item left without evidence becomes missing.
    -> (verified map, number of dropped quotes)."""
    corpus = candidate_corpus(profile, extra_text)
    corpus_words = set(re.findall(r"[^\W_]+", corpus))
    dropped = 0
    verified = []
    for item in items:
        evidence = [q for q in item.evidence if is_grounded(q, corpus, corpus_words)]
        dropped += len(item.evidence) - len(evidence)
        status = item.status if evidence else "missing"
        verified.append(item.model_copy(update={"evidence": evidence if status != "missing" else [], "status": status}))
    return verified, dropped


def _month(value: str | None, end: bool = False) -> str | None:
    """'2026' -> '2026-01' (or '2026-12' for an end date), '2026-08' stays; anything else -> None."""
    if not value:
        return None
    m = re.match(r"(\d{4})(?:-(\d{2}))?", value)
    if not m:
        return None
    return f"{m.group(1)}-{m.group(2) or ('12' if end else '01')}"


def timing(start: str | None, end: str | None, today: date) -> str:
    """'ongoing' | 'completed' | 'upcoming' | 'unknown', computed in code so the tense is always right."""
    now = today.strftime("%Y-%m")
    s, e = _month(start), _month(end, end=True)
    if s and s > now:
        return "upcoming"
    if e and e < now:
        return "completed"
    if s or e:
        return "ongoing"
    return "unknown"


def profile_for_prompt(profile: Profile, today: date) -> dict[str, Any]:
    """Profile dict for the model, with a computed `timing` on every experience and education entry."""
    data = profile.model_dump(mode="json", exclude={"search_terms", "missing_info"})
    for key in ("experiences", "education"):
        for item in data.get(key, []):
            item["timing"] = timing(item.get("start_date"), item.get("end_date"), today)
    return data


def missing_from_map(items: list[RequirementMatch]) -> list[str]:
    missing = [i for i in items if i.status == "missing"]
    missing.sort(key=lambda i: i.importance != "required")  # required first, order kept otherwise
    return [i.requirement for i in missing][:MAX_MISSING_REQUIREMENTS]


def choose_language(job: JobOut, profile: Profile) -> DocLanguage:
    """Norwegian only if the ad is in Norwegian AND the candidate has Norwegian >= B2 (README, "Rules for everyone")."""
    if job.language != "no":
        return "en"
    for lang in profile.languages:
        if lang.language.strip().lower() in NORWEGIAN_NAMES and lang.level.strip().lower() in NORWEGIAN_OK_LEVELS:
            return "no"
    return "en"


def _key(*parts: str | None) -> str:
    return "|".join((p or "").strip().lower() for p in parts)


def enforce_facts(cv: TailoredCV, profile: Profile) -> tuple[TailoredCV, list[str]]:
    """Removes from the CV whatever does not exist in the profile. Returns the clean CV and what was removed."""
    removed: list[str] = []

    cv.name = profile.name
    cv.contacts = profile.contacts
    cv.languages = profile.languages

    by_exp = {_key(e.company, e.role): e for e in profile.experiences}
    by_company = {_key(e.company): e for e in profile.experiences}
    experiences = []
    for exp in cv.experiences:
        original = by_exp.get(_key(exp.company, exp.role)) or by_company.get(_key(exp.company))
        if original is None:
            removed.append(f"experience '{exp.role} at {exp.company}'")
            continue
        exp.company, exp.location = original.company, original.location
        exp.start_date, exp.end_date = original.start_date, original.end_date
        experiences.append(exp)
    cv.experiences = experiences

    by_edu = {_key(e.institution): e for e in profile.education}
    education = []
    for edu in cv.education:
        original = by_edu.get(_key(edu.institution))
        if original is None:
            removed.append(f"education '{edu.degree} at {edu.institution}'")
            continue
        education.append(original)  # degrees and dates are never rewritten
    cv.education = education

    by_project = {_key(p.name): p for p in profile.projects}
    projects = []
    for proj in cv.projects:
        original = by_project.get(_key(proj.name))
        if original is None:
            removed.append(f"project '{proj.name}'")
            continue
        proj.url = original.url
        projects.append(proj)
    cv.projects = projects

    return cv, removed


def tailor(
    profile: Profile, job: JobOut, extra_text: str = "", reasoning_effort: str | None = REASONING_EFFORT
) -> tuple[DocLanguage, TailoredCV, str, ApplicationNotes]:
    """-> (document language, tailored CV, cover letter, notes with the verified requirement map)."""
    language = choose_language(job, profile)
    system = TAILOR_SYSTEM.replace("{language}", language)
    today = date.today()
    profile_json = json.dumps(profile_for_prompt(profile, today), ensure_ascii=False)
    if extra_text.strip():
        profile_json += f"\n\nEXTRA MATERIAL FROM THE CANDIDATE (facts usable too):\n{extra_text[:5000]}"
    user = TAILOR_USER.format(
        today=today.isoformat(),
        profile_json=profile_json,
        title=job.title,
        company=job.company or "(unknown)",
        location=job.location or "(unknown)",
        description=(job.description or "(no description available)")[:MAX_DESCRIPTION_CHARS],
    )
    # fast model: ~15-20 s vs ~60-100 s for the smart one, same quality in tests (target: < 30 s)
    out = complete_json(
        "fast", system, user, TailorOutput, temperature=0.2, max_tokens=10000, reasoning_effort=reasoning_effort
    )

    requirement_map, dropped = verify_requirement_map(out.requirement_map, profile, extra_text)
    if dropped:
        log.warning("Dropped %d evidence quote(s) not found in the candidate's material", dropped)
    cv, removed = enforce_facts(out.cv, profile)
    changes = list(out.notes.changes)
    if removed:
        changes.append("Removed items not found in your profile: " + "; ".join(removed))
    notes = ApplicationNotes(
        keywords_covered=out.notes.keywords_covered,
        missing_requirements=missing_from_map(requirement_map),
        changes=changes,
        requirement_map=requirement_map,
    )
    return language, cv, out.cover_letter, notes
