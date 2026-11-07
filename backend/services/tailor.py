"""C — Profilo + annuncio → CV su misura + cover letter + note.

Oltre alle regole nel prompt, qui c'è una rete di sicurezza contro le invenzioni:
nome, contatti, lingue, date e aziende vengono SEMPRE dal profilo, mai dal modello.
"""

import json

from llm import complete_json
from prompts import TAILOR_SYSTEM, TAILOR_USER
from schemas import ApplicationNotes, DocLanguage, JobOut, Profile, Schema, TailoredCV

MAX_DESCRIPTION_CHARS = 12_000
NORWEGIAN_OK_LEVELS = {"native", "c2", "c1", "b2"}
NORWEGIAN_NAMES = {"norwegian", "norsk", "bokmål", "bokmal", "nynorsk"}


class TailorOutput(Schema):
    cv: TailoredCV
    cover_letter: str
    notes: ApplicationNotes


def choose_language(job: JobOut, profile: Profile) -> DocLanguage:
    """Norvegese solo se l'annuncio è in norvegese E il candidato ha norvegese ≥ B2 (BLUEPRINT sez. 8)."""
    if job.language != "no":
        return "en"
    for lang in profile.languages:
        if lang.language.strip().lower() in NORWEGIAN_NAMES and lang.level.strip().lower() in NORWEGIAN_OK_LEVELS:
            return "no"
    return "en"


def _key(*parts: str | None) -> str:
    return "|".join((p or "").strip().lower() for p in parts)


def enforce_facts(cv: TailoredCV, profile: Profile) -> tuple[TailoredCV, list[str]]:
    """Rimuove dal CV ciò che non esiste nel profilo. Restituisce il CV pulito e cosa è stato tolto."""
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
        education.append(original)  # titoli e date non si riscrivono
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
    # modello veloce: ~15 s contro ~60-100 s di quello smart, stessa qualità nei test (BLUEPRINT: < 30 s)
    out = complete_json("fast", system, user, TailorOutput, temperature=0.4, max_tokens=8000)
    out.cv, removed = enforce_facts(out.cv, profile)
    if removed:
        out.notes.changes.append("Removed items not found in your profile: " + "; ".join(removed))
    return language, out
