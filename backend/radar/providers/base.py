"""Common provider output and normalization of public job data."""

import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from html import unescape
from typing import Literal, Protocol
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

from pydantic import BaseModel, field_validator

from schemas import JobLanguage, JobOut, JobSource, JobStatus


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def job_out(value) -> JobOut:
    job = JobOut.model_validate(value)
    return job.model_copy(update={
        field: as_utc(getattr(job, field)) if getattr(job, field) else None
        for field in ("posted_at", "expires_at", "discovered_at")
    })


def parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        date = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    if date.tzinfo is None:
        date = date.replace(tzinfo=ZoneInfo("Europe/Oslo"))
    return date.astimezone(timezone.utc)


def public_url(value: str | None) -> str | None:
    if not value:
        return None
    parts = urlsplit(value.strip())
    if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username:
        return None
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))


def canonical_url(value: str) -> str:
    parts = urlsplit(value)
    query = urlencode(sorted(
        (key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in {"gclid", "fbclid"}
    ))
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), query, ""))


class _TextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden += 1
        if tag in {"p", "br", "div", "li", "h1", "h2", "h3", "h4"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)
        if tag in {"p", "div", "li", "h1", "h2", "h3", "h4"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def clean_description(html: str, contacts: list[dict] | None = None) -> str:
    parser = _TextParser()
    parser.feed(unescape(html))
    text = "".join(parser.parts)
    for contact in contacts or []:
        for field in ("name", "email", "phone"):
            value = contact.get(field)
            if value and len(str(value).strip()) >= 3:
                text = re.sub(re.escape(str(value)), "[contact removed]", text, flags=re.I)
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[email removed]", text)
    text = re.sub(r"(?<!\w)(?:\+47[ .-]?)?(?:\d[ .-]?){8}(?!\w)", "[phone removed]", text)
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


class NormalizedJob(BaseModel):
    source: JobSource
    source_id: str
    title: str
    company: str | None = None
    location: str | None = None
    description: str | None = None
    url: str
    apply_url: str | None = None
    posted_at: datetime | None = None
    expires_at: datetime | None = None
    status: JobStatus = "active"
    language: JobLanguage | None = None
    norwegian_required: bool | None = None

    @field_validator("posted_at", "expires_at")
    @classmethod
    def utc_dates(cls, value: datetime | None) -> datetime | None:
        return as_utc(value) if value else None


class Company(BaseModel):
    name: str
    source: Literal["teamtailor", "greenhouse", "lever", "ashby"]
    careers_url: str
    board: str
    region: Literal["global", "eu"] = "global"


class ScanConfig(BaseModel):
    days: int = 14
    limit: int = 250
    max_pages: int = 30
    latest_only: bool = False
    municipalities: list[str] = ["OSLO", "BÆRUM", "ASKER", "LILLESTRØM", "LØRENSKOG", "NORDRE FOLLO"]
    tracked_ids: set[str] = set()
    companies: list[Company] = []
    sources: list[str] = ["nav", "teamtailor", "greenhouse", "lever", "ashby"]


class Provider(Protocol):
    async def fetch_jobs(self, config: ScanConfig) -> list[NormalizedJob]: ...
