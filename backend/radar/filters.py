"""Deterministic language, location, date and title filters."""

import re
from datetime import datetime, timedelta

from radar.providers.base import NormalizedJob, as_utc, canonical_url, clean_description
from schemas import Preferences, Profile

OSLO_AREA = ("oslo", "lysaker", "fornebu", "sandvika", "bærum", "asker", "lillestrøm", "lørenskog", "ski", "nordre follo")


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
    positive = [term.strip().casefold() for term in terms if term.strip() and not term.startswith(("-", "!"))]
    negative = [term[1:].strip().casefold() for term in terms if term.startswith(("-", "!")) and term[1:].strip()]
    if profile.preferences.seniority in {"intern", "junior", "graduate"}:
        negative += ["senior", "principal", "head of", "director", "chief"]
    return positive, negative


def title_relevance(title: str, profile: Profile) -> int:
    positive, _ = title_terms(profile)
    return sum(term in title.casefold() for term in positive)


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
        title = job.title.casefold()
        if any(re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", title) for term in negative):
            continue
        if positive and not any(term in title for term in positive):
            continue
        url = canonical_url(job.url)
        title_key = (title.strip(), (job.company or "").strip().casefold())
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
