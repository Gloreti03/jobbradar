"""Lever's public postings API, with explicit unknown publication dates."""

import logging
from urllib.parse import quote

import httpx

from radar.filters import prepare_board_job
from radar.providers.base import NormalizedJob, ScanConfig, parse_date, public_url

logger = logging.getLogger(__name__)


class LeverProvider:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def fetch_jobs(self, config: ScanConfig) -> list[NormalizedJob]:
        jobs = []
        for company in config.companies:
            if company.source != "lever":
                continue
            host = "api.eu.lever.co" if company.region == "eu" else "api.lever.co"
            try:
                for page in range(config.max_pages):
                    response = await self.client.get(f"https://{host}/v0/postings/{quote(company.board, safe='')}", params={"mode": "json", "skip": page * 100, "limit": 100})
                    response.raise_for_status()
                    items = response.json()
                    for item in items:
                        url = public_url(item.get("hostedUrl"))
                        if not url or not item.get("text"):
                            continue
                        categories = item.get("categories") or {}
                        places = categories.get("allLocations") or [categories.get("location")]
                        description = [item.get("descriptionPlain") or item.get("description") or ""]
                        description += [f"{section.get('text', '')}\n{section.get('content', '')}" for section in item.get("lists", [])]
                        description.append(item.get("additionalPlain") or item.get("additional") or "")
                        job = prepare_board_job(NormalizedJob(
                            source="lever", source_id=f"{company.board}:{item['id']}", title=item["text"], company=company.name,
                            location=" / ".join(place for place in places if place) or None,
                            description="\n".join(description), url=url, apply_url=public_url(item.get("applyUrl")),
                            posted_at=parse_date(item.get("publishedAt")),
                        ))
                        if job:
                            jobs.append(job)
                    if len(items) < 100:
                        break
            except (httpx.HTTPError, ValueError) as error:
                logger.warning("Lever %s unavailable (%s)", company.name, type(error).__name__)
        return jobs
