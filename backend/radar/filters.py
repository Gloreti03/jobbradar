"""Deterministic language, location, date and title filters."""

import re
from datetime import datetime, timedelta

from radar.providers.base import NormalizedJob, as_utc, canonical_url, clean_description
from schemas import Preferences, Profile

OSLO_AREA = ("oslo", "lysaker", "fornebu", "sandvika", "bærum", "asker", "lillestrøm", "lørenskog", "ski", "nordre follo")
SENIORITY_WORDS = {"intern", "junior", "graduate", "nyutdannet", "trainee", "senior", "mid", "lead", "principal", "head", "director", "chief"}
GENERIC_ROLE_WORDS = {"developer", "engineer", "utvikler", "ingeniør", "programmer", "of"}


def normalize_terms(value: str) -> str:
    text = re.sub(r"[\u2010-\u2015]", "-", value.casefold())
    text = re.sub(r"\b(back|front)[\s_-]*end", r"\1end", text)
    text = re.sub(r"\bfull[\s_-]*stack", "fullstack", text)
    text = re.sub(r"\b(backend|frontend)(utvikler|developer)\b", r"\1 \2", text)
    return " ".join(re.findall(r"\w+(?:[+#]+)?", text))


def contains_term(text: str, term: str) -> bool:
    return bool(re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text))


def language_flags(title: str, description: str) -> tuple[str | None, bool | None]:
    text = f"{title}\n{description}".casefold()
    words = re.findall(r"[a-zæøå]+", text)
    norwegian = sum(word in {"og", "som", "til", "søker", "er", "med", "arbeid", "arbeidsoppgaver", "kvalifikasjoner", "deg", "du", "vi"} for word in words)
    english = sum(word in {"the", "and", "with", "you", "we", "our", "are", "requirements", "experience", "work"} for word in words)
    language = "no" if norwegian > english else "en" if english else None
    explicit_optional = re.search(r"norwegian\s+(?:is\s+)?not\s+(?:required|necessary)|no norwegian required", text)
    required = re.search(
        r"(?:fluent|fluency|proficien\w*|excellent|good|speak|spoken|written).{0,45}\bnorwegian\b"
        r"|\bnorwegian\b.{0,45}(?:required|mandatory|essential|must)"
        r"|(?:må|beherske|behersker|flytende|god|gode|godt|kommunisere|muntlig|skriftlig).{0,55}\bnorsk\b"
        r"|\bnorsk\b.{0,55}(?:muntlig|skriftlig|krav)",
        text,
    )
    if required and not explicit_optional:
        return language, True
    if explicit_optional or language == "en":
        return language, False
    return language, None


def title_terms(profile: Profile) -> tuple[list[str], list[str]]:
    terms = profile.search_terms + profile.preferences.roles
    terms = [term.strip() for term in terms if term.strip()]
    positive = list(dict.fromkeys(normalize_terms(term) for term in terms if not term.startswith(("-", "!"))))
    positive = [term for term in positive if set(term.split()) - SENIORITY_WORDS]
    negative = [normalize_terms(term[1:]) for term in terms if term.startswith(("-", "!")) and normalize_terms(term[1:])]
    return positive, negative


def title_relevance(title: str, profile: Profile) -> int:
    positive, _ = title_terms(profile)
    text = normalize_terms(title)
    score = 0
    for term in positive:
        if contains_term(text, term):
            score += 2
            continue
        words = set(term.split()) - SENIORITY_WORDS - GENERIC_ROLE_WORDS
        score += sum(contains_term(text, word) for word in words)
    return score


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


def filter_jobs(jobs: list, profile: Profile, days: int, english_only: bool, now: datetime) -> list:
    cutoff = now - timedelta(days=days)
    positive, negative = title_terms(profile)
    selected = []
    urls = set()
    titles = set()
    for job in jobs:
        if job.status != "active" or (job.expires_at and as_utc(job.expires_at) <= now):
            continue
        if job.posted_at and not cutoff <= as_utc(job.posted_at) <= now:
            continue
        if not location_matches(job.location, profile):
            continue
        if english_only and (job.language != "en" or job.norwegian_required is not False):
            continue
        title = normalize_terms(job.title)
        if any(contains_term(title, term) for term in negative):
            continue
        if positive and not title_relevance(job.title, profile):
            description = normalize_terms(job.description or "")
            if not any(contains_term(description, term) for term in positive):
                continue
        url = canonical_url(job.url)
        title_key = (title, (job.company or "").strip().casefold())
        if url in urls or (job.company and title_key in titles):
            continue
        urls.add(url)
        if job.company:
            titles.add(title_key)
        selected.append(job)
    return sorted(selected, key=lambda job: (
        job.posted_at is None,
        -title_relevance(job.title, profile),
        -as_utc(job.posted_at).timestamp() if job.posted_at else 0,
        job.id,
    ))
