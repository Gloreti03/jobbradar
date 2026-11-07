"""C — Profile + job ad -> tailored CV + cover letter + notes.

On top of the prompt rules, there is a safety net against invention here:
name, contacts, languages, dates and companies ALWAYS come from the profile, never from the model.
"""

import json

from llm import complete_json
from prompts import TAILOR_SYSTEM, TAILOR_USER
from schemas import ApplicationNotes, DocLanguage, JobOut, Profile, Schema, TailoredCV

MAX_DESCRIPTION_CHARS = 12_000
MAX_MISSING_REQUIREMENTS = 6  # more than this does not fit on a card
NORWEGIAN_OK_LEVELS = {"native", "c2", "c1", "b2"}
NORWEGIAN_NAMES = {"norwegian", "norsk", "bokmål", "bokmal", "nynorsk"}


class TailorOutput(Schema):
    cv: TailoredCV
    cover_letter: str
    notes: ApplicationNotes


def choose_language(job: JobOut, profile: Profile) -> DocLanguage:
    """Norwegian only if the ad is in Norwegian AND the candidate has Norwegian >= B2 (BLUEPRINT sec. 8)."""
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


def tailor(profile: Profile, job: JobOut, extra_text: str = "") -> tuple[DocLanguage, TailorOutput]:
    language = choose_language(job, profile)
    system = TAILOR_SYSTEM.replace("{language}", language)
    profile_json = json.dumps(profile.model_dump(exclude={"search_terms", "missing_info"}), ensure_ascii=False)
    if extra_text.strip():
        profile_json += f"\n\nEXTRA MATERIAL FROM THE CANDIDATE (facts usable too):\n{extra_text[:5000]}"
    user = TAILOR_USER.format(
        profile_json=profile_json,
        title=job.title,
        company=job.company or "(unknown)",
        location=job.location or "(unknown)",
        description=(job.description or "(no description available)")[:MAX_DESCRIPTION_CHARS],
    )
    # fast model: ~15 s vs ~60-100 s for the smart one, same quality in tests (BLUEPRINT: < 30 s)
    out = complete_json("fast", system, user, TailorOutput, temperature=0.2, max_tokens=8000)
    out.notes.missing_requirements = out.notes.missing_requirements[:MAX_MISSING_REQUIREMENTS]
    out.cv, removed = enforce_facts(out.cv, profile)
    if removed:
        out.notes.changes.append("Removed items not found in your profile: " + "; ".join(removed))
    return language, out
