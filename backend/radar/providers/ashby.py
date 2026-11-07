"""Ashby's public, listed job postings."""

import logging
from urllib.parse import quote, urlsplit

import httpx

from radar.filters import prepare_board_job
from radar.providers.base import NormalizedJob, ScanConfig, parse_date, public_url

logger = logging.getLogger(__name__)


class AshbyProvider:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def fetch_jobs(self, config: ScanConfig) -> list[NormalizedJob]:
        jobs = []
        for company in config.companies:
            if company.source != "ashby":
                continue
            try:
                response = await self.client.get(f"https://api.ashbyhq.com/posting-api/job-board/{quote(company.board, safe='')}")
                response.raise_for_status()
                for item in response.json().get("jobs", []):
                    url = public_url(item.get("jobUrl"))
                    if not url or not item.get("title") or item.get("isListed") is False:
                        continue
                    places = [item.get("location")] + [place.get("location") for place in item.get("secondaryLocations") or []]
                    job = prepare_board_job(NormalizedJob(
                        source="ashby", source_id=f"{company.board}:{item.get('id') or urlsplit(url).path.rstrip('/').rsplit('/', 1)[-1]}",
                        title=item["title"], company=company.name,
                        location=" / ".join(place for place in places if place) or None,
                        description=item.get("descriptionPlain") or item.get("descriptionHtml"), url=url,
                        apply_url=public_url(item.get("applyUrl")), posted_at=parse_date(item.get("publishedAt")),
                    ))
                    if job:
                        jobs.append(job)
            except (httpx.HTTPError, ValueError) as error:
                logger.warning("Ashby %s unavailable (%s)", company.name, type(error).__name__)
        return jobs
