"""Greenhouse's public Job Board API; first_published is the posting date."""

import logging
from urllib.parse import quote

import httpx

from radar.filters import prepare_board_job
from radar.providers.base import NormalizedJob, ScanConfig, parse_date, public_url

logger = logging.getLogger(__name__)


class GreenhouseProvider:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def fetch_jobs(self, config: ScanConfig) -> list[NormalizedJob]:
        jobs = []
        for company in config.companies:
            if company.source != "greenhouse":
                continue
            try:
                response = await self.client.get(f"https://boards-api.greenhouse.io/v1/boards/{quote(company.board, safe='')}/jobs", params={"content": "true"})
                response.raise_for_status()
                for item in response.json().get("jobs", []):
                    url = public_url(item.get("absolute_url"))
                    if not url or not item.get("title"):
                        continue
                    job = prepare_board_job(NormalizedJob(
                        source="greenhouse", source_id=f"{company.board}:{item['id']}",
                        title=item["title"], company=company.name, location=(item.get("location") or {}).get("name"),
                        description=item.get("content"), url=url, apply_url=url,
                        posted_at=parse_date(item.get("first_published")), expires_at=parse_date(item.get("application_deadline")),
                    ))
                    if job:
                        jobs.append(job)
            except (httpx.HTTPError, ValueError) as error:
                logger.warning("Greenhouse %s unavailable (%s)", company.name, type(error).__name__)
        return jobs
