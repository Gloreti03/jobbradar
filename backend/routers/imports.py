"""Import from the browser extension (owner: Matilde).

POST /jobs/import: the extension sends the page URL, the schema.org JobPosting JSON-LD (if the
page has one) and the visible text. The job is saved with source="extension" and
source_id = canonical URL; if the same URL is already in the DB (from any source) that job_id
is returned with created=false. No AI here.

Note: this router must be included in main.py BEFORE routers/jobs.py
(POST /jobs/import must not end up on /jobs/{job_id}).
"""

from datetime import datetime, timezone
from html import escape
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from db import get_db
from models import JobRow
from radar.filters import language_flags
from radar.providers.base import canonical_url, clean_description, public_url
from schemas import JobImportRequest, JobImportResponse

router = APIRouter(prefix="/jobs", tags=["imports"])

TEXT_MAX_CHARS = 20000


def _first(value: Any) -> Any:
    return value[0] if isinstance(value, list) and value else value


def _find_job_posting(data: Any) -> dict[str, Any] | None:
    """JobPosting inside a JSON-LD blob (object, list or @graph)."""
    if isinstance(data, list):
        for item in data:
            found = _find_job_posting(item)
            if found:
                return found
        return None
    if not isinstance(data, dict):
        return None
    kind = data.get("@type")
    if kind == "JobPosting" or (isinstance(kind, list) and "JobPosting" in kind):
        return data
    if "@graph" in data:
        return _find_job_posting(data["@graph"])
    return None


def _name(value: Any) -> str | None:
    value = _first(value)
    if isinstance(value, dict):
        value = value.get("name")
    return value.strip() if isinstance(value, str) and value.strip() else None


def _location(posting: dict[str, Any]) -> str | None:
    loc = _first(posting.get("jobLocation"))
    if isinstance(loc, dict):
        address = loc.get("address")
        if isinstance(address, dict):
            parts = [address.get("addressLocality"), address.get("addressRegion"), address.get("addressCountry")]
            parts = [_name(p) for p in parts]
            text = ", ".join(dict.fromkeys(p for p in parts if p))
            if text:
                return text
        elif isinstance(address, str) and address.strip():
            return address.strip()
    if str(posting.get("jobLocationType", "")).upper() == "TELECOMMUTE":
        return "Remote"
    return None


def _date(value: Any) -> datetime | None:
    """ISO date of the JSON-LD -> UTC. A date without time zone is read as UTC.
    (Not radar.providers.base.parse_date: its ZoneInfo needs the tzdata package on Windows.)"""
    text = _str(value)
    if not text:
        return None
    try:
        date = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if date.tzinfo is None:
        date = date.replace(tzinfo=timezone.utc)
    return date.astimezone(timezone.utc)


def _str(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


@router.post("/import", response_model=JobImportResponse)
def import_job(body: JobImportRequest, db: Session = Depends(get_db)):
    page_url = public_url(body.url)
    if not page_url:
        raise HTTPException(status_code=422, detail="Invalid request: url must be a public http(s) address")
    source_id = canonical_url(page_url)

    posting = _find_job_posting(body.json_ld) or {}

    title = _str(posting.get("title")) or _str(body.title)
    if not title:
        raise HTTPException(status_code=422, detail="Could not find the job title on this page")
    company = _name(posting.get("hiringOrganization")) or _str(body.company)
    location = _location(posting) or _str(body.location)

    description = clean_description(posting["description"]) if _str(posting.get("description")) else None
    if not description and body.text:
        description = clean_description(escape(body.text[:TEXT_MAX_CHARS])) or None  # also strips emails/phones

    apply_url = public_url(_str(posting.get("url"))) or page_url
    language, norwegian_required = language_flags(title, description or "")

    existing = db.scalar(
        select(JobRow)
        .where(or_(
            (JobRow.source == "extension") & (JobRow.source_id == source_id),
            JobRow.url == page_url,
            JobRow.url == source_id,
        ))
        .limit(1)
    )
    if existing is not None:
        return {"job_id": existing.id, "created": False}

    row = JobRow(
        source="extension",
        source_id=source_id,
        title=title[:500],
        company=company,
        location=location,
        description=description,
        url=page_url,
        apply_url=apply_url,
        posted_at=_date(posting.get("datePosted")),  # unknown date stays null (never discovered_at)
        expires_at=_date(posting.get("validThrough")),
        status="active",
        language=language,
        norwegian_required=norwegian_required,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"job_id": row.id, "created": True}
