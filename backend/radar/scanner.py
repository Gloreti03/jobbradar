"""Scan NAV, persist normalized jobs and exchange portable seed files."""

import os
import asyncio
import logging
from collections import Counter
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import httpx
import yaml
from pydantic import TypeAdapter
from sqlalchemy import delete, select, text

from config import BACKEND_DIR
from db import SessionLocal, init_db
from models import JobRow, MatchRow
from radar.providers.base import NormalizedJob, ScanConfig, as_utc, canonical_url, job_out
from radar.providers.nav import NavProvider
from radar.providers.teamtailor import TeamtailorProvider
from radar.providers.greenhouse import GreenhouseProvider
from radar.providers.lever import LeverProvider
from radar.providers.ashby import AshbyProvider
from schemas import JobOut

SEED_PATH = BACKEND_DIR / "data" / "seed_jobs.json"
logger = logging.getLogger(__name__)
PROVIDERS = {"nav": NavProvider, "teamtailor": TeamtailorProvider,
             "greenhouse": GreenhouseProvider, "lever": LeverProvider, "ashby": AshbyProvider}


def active_jobs(jobs: list[JobRow]) -> list[JobRow]:
    now = datetime.now(timezone.utc)
    unique = []
    urls = set()
    titles = set()
    for job in sorted(jobs, key=lambda row: row.id):
        if job.status != "active" or (job.expires_at and as_utc(job.expires_at) <= now):
            continue
        url = canonical_url(job.url)
        title_key = (job.title.strip().casefold(), (job.company or "").strip().casefold())
        if url in urls or (job.company and title_key in titles):
            continue
        urls.add(url)
        if job.company:
            titles.add(title_key)
        unique.append(job)
    return unique


def save_jobs(jobs: list[NormalizedJob]) -> int:
    """Serialize writes and retain existing IDs used by matches and applications."""
    with SessionLocal.begin() as session:
        session.execute(text("BEGIN IMMEDIATE"))
        rows = list(session.scalars(select(JobRow)))
        by_source = {(row.source, row.source_id): row for row in rows}
        by_url = {canonical_url(row.url): row for row in active_jobs(rows)}
        by_title = {(row.title.strip().casefold(), row.company.strip().casefold()): row
                    for row in active_jobs(rows) if row.company}
        for job in sorted(jobs, key=lambda item: item.status != "inactive"):
            row = by_source.get((job.source, job.source_id))
            if job.status == "inactive":
                if row:
                    row.status = "inactive"
                    row.description = None
                    session.execute(delete(MatchRow).where(MatchRow.job_id == row.id))
                continue
            url_key = canonical_url(job.url)
            title_key = (job.title.strip().casefold(), (job.company or "").strip().casefold())
            if row is None:
                duplicates = [by_url.get(url_key), by_title.get(title_key) if job.company else None]
                if any(duplicate is not None and duplicate.status == "active" for duplicate in duplicates):
                    continue
                row = JobRow(**job.model_dump())
                session.add(row)
                by_source[(job.source, job.source_id)] = row
            else:
                old_url = canonical_url(row.url)
                old_title = (row.title.strip().casefold(), (row.company or "").strip().casefold())
                if by_url.get(old_url) is row:
                    by_url.pop(old_url)
                if by_title.get(old_title) is row:
                    by_title.pop(old_title)
                changed = any(
                    (as_utc(getattr(row, key)) if isinstance(getattr(row, key), datetime) else getattr(row, key)) != value
                    for key, value in job.model_dump().items()
                )
                if changed:
                    session.execute(delete(MatchRow).where(MatchRow.job_id == row.id))
                for key, value in job.model_dump().items():
                    setattr(row, key, value)
            by_url[url_key] = row
            if job.company:
                by_title[title_key] = row
        session.flush()
        return len(active_jobs(list(session.scalars(select(JobRow)))))


async def scan(config: ScanConfig) -> dict:
    init_db()
    with SessionLocal() as session:
        config = config.model_copy(update={"tracked_ids": set(session.scalars(
            select(JobRow.source_id).where(JobRow.source == "nav")
        ))})
    async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
        results = await asyncio.gather(*(PROVIDERS[source](client).fetch_jobs(config) for source in config.sources), return_exceptions=True)
    updates = 0
    warnings = []
    for source, result in zip(config.sources, results):
        if isinstance(result, Exception):
            warnings.append(source)
            logger.warning("%s scan failed (%s)", source, type(result).__name__)
        else:
            updates += len(result)
            save_jobs(result)
    if len(warnings) == len(config.sources):
        raise RuntimeError("All selected providers failed; existing database and seed are retained")
    with SessionLocal() as session:
        count = len(active_jobs(list(session.scalars(select(JobRow)))))
    return {"updates": updates, "active_unique_jobs": count, "failed_sources": warnings}


def default_config(**overrides) -> ScanConfig:
    configuration = yaml.safe_load((Path(__file__).parent / "companies.yml").read_text(encoding="utf-8")) or {}
    values = {"municipalities": configuration.get("municipalities", ScanConfig().municipalities),
              "companies": configuration.get("companies", []), **overrides}
    values["municipalities"] = [city.strip().upper() for city in values["municipalities"]]
    return ScanConfig(**values)


def catalogue_stats() -> dict:
    with SessionLocal() as session:
        jobs = active_jobs(list(session.scalars(select(JobRow))))
    required = sum(job.norwegian_required is True for job in jobs)
    return {
        "active_unique_jobs": len(jobs),
        "sources": dict(Counter(job.source for job in jobs)),
        "norwegian_required": required,
        "norwegian_required_percent": round(required * 100 / len(jobs), 1) if jobs else 0,
        "norwegian_requirement_unknown": sum(job.norwegian_required is None for job in jobs),
        "english_language": sum(job.language == "en" for job in jobs),
    }


def dump_seed(path: Path = SEED_PATH) -> int:
    with SessionLocal() as session:
        jobs = [job_out(job) for job in active_jobs(list(session.scalars(select(JobRow))))]
    payload = TypeAdapter(list[JobOut]).dump_json(jobs, indent=2)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as output:
            temporary = Path(output.name)
            output.write(payload)
            output.write(b"\n")
        os.replace(temporary, path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()
    return len(jobs)


def load_seed(path: Path = SEED_PATH) -> int:
    jobs = TypeAdapter(list[JobOut]).validate_json(path.read_bytes())
    normalized = [NormalizedJob.model_validate(job.model_dump()) for job in jobs]
    init_db()
    return save_jobs(normalized)
