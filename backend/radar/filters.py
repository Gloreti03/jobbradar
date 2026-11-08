"""Deterministic language, location, date and title filters."""

import re
from datetime import datetime, timedelta

from radar.providers.base import NormalizedJob, as_utc, canonical_url, clean_description
from schemas import Preferences, Profile, RadarFunnel

OSLO_AREA = ("oslo", "lysaker", "fornebu", "sandvika", "bærum", "asker", "lillestrøm", "lørenskog", "ski", "nordre follo")
SENIORITY_WORDS = {"intern", "junior", "graduate", "nyutdannet", "trainee", "senior", "mid", "lead", "principal", "head", "director", "chief"}
ENTRY_ROLES = {"intern", "graduate", "nyutdannet", "trainee"}
GENERIC_ROLE_WORDS = {"developer", "engineer", "utvikler", "ingeniør", "programmer", "of"}
OPTIONAL_NORWEGIAN = re.compile(
    r"\bnorwegian(?:[- \t]+(?:language|speaking|skills?|proficiency|fluency|knowledge)){0,3}[ \t]+"
    r"(?:(?:is|are|would be|will be|considered|seen as|also|highly|strongly)[ \t]+){0,4}"
    r"\(?(?:not[ \t]+(?:strictly[ \t]+)?(?:required|necessary|mandatory|essential|needed|a requirement)"
    r"|optional|preferred|desirable|desired|nice[- ]to[- ]have"
    r"|(?:an?[ \t]+)?(?:strong[ \t]+)?(?:plus|advantage|asset|bonus|benefit))\b\)?"
    r"|\b(?:nice[- ]to[- ]have|preferred|desirable)\s*[:\-]?\s*"
    r"(?:(?:fluency|proficiency|knowledge|skills?)\s+(?:in|of)\s+)?(?:fluent\s+)?norwegian\b"
    r"|\bno\s+norwegian(?:\s+(?:language|skills?)){0,2}\s+(?:required|necessary|needed)\b"
    r"|\b(?:do not|don't)\s+need\s+to\s+(?:speak|know|understand)\s+norwegian\b"
    r"|\bnorsk(?:kunnskaper|ferdigheter)?[ \t]+(?:(?:er|vil være|også)[ \t]+){0,3}"
    r"(?:ikke[ \t]+(?:et[ \t]+)?(?:absolutt[ \t]+)?(?:krav|påkrevd|nødvendig)"
    r"|ønskelig|valgfritt|(?:en[ \t]+)?(?:fordel|bonus|pluss))\b"
    r"|\btrenger\s+ikke\s+(?:å\s+)?(?:snakke|kunne|beherske)\s+norsk\b"
    r"|\b(?:speak|speaking|fluent|fluency|proficiency|communicate)\b[^.;!?\n]{0,35}"
    r"\b(?:norwegian[ \t]*(?:or|/)[ \t]*english|english[ \t]*(?:or|/)[ \t]*norwegian)\b"
    r"|\b(?:snakke|snakker|beherske|behersker|kommunisere|kommuniserer|forstå|forstått|god|gode)\b[^.;!?\n]{0,35}"
    r"\b(?:norsk[ \t]*(?:eller|/)[ \t]*engelsk|engelsk[ \t]*(?:eller|/)[ \t]*norsk)\b"
)
REQUIRED_NORWEGIAN = re.compile(
    r"\b(?:fluent|fluency|proficien\w*|excellent|good|speak|spoken|written)\b[^.;!?\n]{0,45}\bnorwegian\b"
    r"|\bnorwegian\b(?!\s+(?:work permit|citizenship|law))[^.;!?\n]{0,45}\b(?:required|mandatory|essential|must)\b"
    r"|\bnorwegian(?:\s+language)?\s+(?:fluency|proficiency)\b"
    r"|\bnorwegian[- ]speaking\b"
    r"|\b(?:working|work)\s+language\s+(?:(?:is|will be)\s+)?norwegian\b"
    r"|\bnorwegian\s+is\s+(?:our|the)\s+working\s+language\b"
    r"|\b(?:må\s+(?:kunne|snakke|beherske|forstå)|snakke|snakker|beherske|behersker|flytende|god|gode|godt|kommunisere|kommuniserer|muntlige?|skriftlige?)\b[^.;!?\n]{0,55}\bnorsk\b"
    r"|\bnorsk\b[^.;!?\n]{0,55}\b(?:muntlige?|skriftlige?|[abc][12])\b"
    r"|\bnorsk(?:kunnskaper|ferdigheter)?\s+(?:(?:er|et|absolutt)\s+){0,3}(?:krav|påkrevd|nødvendig)\b"
    r"|\b(?:må|skal)\b[^.;!?\n]{0,25}\b(?:bestå|bestått)\b[^.;!?\n]{0,20}\bnorskprøve(?:n)?\b"
    r"|\barbeidsspråk(?:et)?\s+(?:er\s+)?norsk\b|\bnorsk\s+som\s+arbeidsspråk\b"
)


def normalize_terms(value: str) -> str:
    text = re.sub(r"[\u2010-\u2015]", "-", value.casefold())
    text = re.sub(r"\b(back|front)[\s_-]*end", r"\1end", text)
    text = re.sub(r"\bfull[\s_-]*stack", "fullstack", text)
    text = re.sub(r"\b(backend|frontend)(utvikler|developer)\b", r"\1 \2", text)
    return " ".join(re.findall(r"\w+(?:[+#]+)?", text))


def contains_term(text: str, term: str) -> bool:
    return bool(re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text))


NORWEGIAN_WORDS = {
    "og", "som", "til", "søker", "er", "med", "arbeid", "arbeidsoppgaver", "kvalifikasjoner",
    "deg", "du", "vi", "ikke", "erfaring", "stillingen", "å",
}
ENGLISH_WORDS = {"the", "and", "with", "you", "we", "our", "are", "requirements", "experience", "work"}
# Only words that are not also Norwegian; any word with ä/ö counts as Swedish too.
SWEDISH_WORDS = {"och", "att", "inte", "erfarenhet", "arbeta", "inom", "tjänsten", "kunskaper", "vill", "hur", "också"}


def language_flags(title: str, description: str) -> tuple[str | None, bool | None]:
    text = f"{title}\n{description}".casefold()
    words = re.findall(r"[a-zæøåäö]+", text)
    norwegian = sum(word in NORWEGIAN_WORDS for word in words)
    english = sum(word in ENGLISH_WORDS for word in words)
    # Swedish shares many short words with Norwegian ("som", "med", "du", "vi"):
    # an ad with more Swedish markers is neither Norwegian nor English.
    swedish = sum(word in SWEDISH_WORDS or bool(re.search(r"[äö]", word)) for word in words)
    if swedish > norwegian and swedish > english:
        language = None
    else:
        language = "no" if norwegian > english else "en" if english else None
    # Remove optional language phrases before checking the remaining requirements.
    # A separate mandatory clause still wins over an optional one.
    requirement_text, optional_count = OPTIONAL_NORWEGIAN.subn(" ", text)
    if REQUIRED_NORWEGIAN.search(requirement_text):
        return language, True
    if optional_count or language == "en":
        return language, False
    return language, None


def title_terms(profile: Profile) -> tuple[list[str], list[str]]:
    terms = profile.search_terms + profile.preferences.roles
    terms = [term.strip() for term in terms if term.strip()]
    positive = list(dict.fromkeys(normalize_terms(term) for term in terms if not term.startswith(("-", "!"))))
    positive = [term for term in positive if set(term.split()) - (SENIORITY_WORDS - ENTRY_ROLES)]
    negative = [normalize_terms(term[1:]) for term in terms if term.startswith(("-", "!")) and normalize_terms(term[1:])]
    return positive, negative


def role_text(value: str, company: str | None = None) -> str:
    text = normalize_terms(value)
    # Employer names are not skills (e.g. the fashion retailer HIJA BI AS).
    employer = re.sub(r"(?: (?:as|asa|ab|inc|ltd|limited))+$", "", normalize_terms(company or ""))
    if len(employer.split()) > 1:
        text = re.sub(r"(?<!\w)" + re.escape(employer) + r"(?!\w)", " ", text)
    return " ".join(text.split())


def title_relevance(title: str, profile: Profile, company: str | None = None) -> int:
    positive, _ = title_terms(profile)
    text = role_text(title, company)
    location_words = set(normalize_terms(" ".join(profile.preferences.cities or ["Oslo"])).split())
    score = 0
    for term in positive:
        if term in ENTRY_ROLES and contains_term(text, term):
            score += 2
            continue
        term_words = set(term.split()) - SENIORITY_WORDS - location_words
        if not term_words:
            continue
        if contains_term(text, term):
            score += 2
            continue
        words = term_words - GENERIC_ROLE_WORDS
        # A fragment such as BI from "BI analyst" or R from "R analyst"
        # cannot select a job alone. Keep reordered technical titles such as
        # "ML Software Engineer" by requiring the rest of "ML engineer" too.
        if words and all(len(word) <= 2 for word in words):
            score += int(all(contains_term(text, word) for word in term_words))
        else:
            score += sum(contains_term(text, word) for word in words if len(word) > 2)
    return score


def industry_relevance(job, profile: Profile) -> int:
    """Interests break ties between relevant roles; they never admit or reject a job."""
    text = normalize_terms(f"{job.title}\n{job.company or ''}\n{job.description or ''}")
    interests = {normalize_terms(value) for value in profile.preferences.industries}
    return sum(contains_term(text, term) for term in interests if term)


def location_matches(location: str | None, profile: Profile) -> bool:
    if not location:
        return True
    text = location.casefold()
    cities = [city.casefold() for city in profile.preferences.cities] or ["oslo"]
    allowed = cities + ["remote", "norway", "norge"]
    if any(city in {"oslo", "oslo area"} for city in cities):
        allowed += list(OSLO_AREA)
    return any(re.search(r"(?<!\w)" + re.escape(city) + r"(?!\w)", text) for city in allowed)


def prepare_board_job(job: NormalizedJob) -> NormalizedJob | None:
    area = Profile(name="", preferences=Preferences(cities=["Oslo"]))
    if not location_matches(job.location, area):
        return None
    description = clean_description(job.description or "")
    language, required = language_flags(job.title, description)
    return job.model_copy(update={
        "description": description or None, "language": language, "norwegian_required": required,
    })


def filter_jobs_with_funnel(jobs: list, profile: Profile, days: int, english_only: bool,
                          now: datetime) -> tuple[list, RadarFunnel]:
    cutoff = now - timedelta(days=days)
    positive, negative = title_terms(profile)
    selected = []
    urls = set()
    titles = set()
    counts = dict.fromkeys(("total", "recent", "location", "language", "keywords", "deduplicated", "live", "ranked"), 0)
    for job in jobs:
        if job.status != "active" or (job.expires_at and as_utc(job.expires_at) <= now):
            continue
        counts["total"] += 1
        if job.posted_at and not cutoff <= as_utc(job.posted_at) <= now:
            continue
        counts["recent"] += 1
        if not location_matches(job.location, profile):
            continue
        counts["location"] += 1
        if english_only and (job.language != "en" or job.norwegian_required is not False):
            continue
        counts["language"] += 1
        title = normalize_terms(job.title)
        if any(contains_term(title, term) for term in negative):
            continue
        if positive and not title_relevance(job.title, profile, job.company):
            description = role_text(job.description or "", job.company)
            if not any(contains_term(description, term) for term in positive):
                continue
        counts["keywords"] += 1
        url = canonical_url(job.url)
        title_key = (title, (job.company or "").strip().casefold())
        if url in urls or (job.company and title_key in titles):
            continue
        urls.add(url)
        if job.company:
            titles.add(title_key)
        selected.append(job)
    counts["deduplicated"] = len(selected)
    ordered = sorted(selected, key=lambda job: (
        job.posted_at is None,
        -title_relevance(job.title, profile, job.company),
        -industry_relevance(job, profile),
        -as_utc(job.posted_at).timestamp() if job.posted_at else 0,
        job.id,
    ))
    return ordered, RadarFunnel(**counts)


def filter_jobs(jobs: list, profile: Profile, days: int, english_only: bool, now: datetime) -> list:
    return filter_jobs_with_funnel(jobs, profile, days, english_only, now)[0]
