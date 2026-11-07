"""Public Teamtailor RSS, including every location in multi-location posts."""

import logging
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin
from xml.etree import ElementTree

import httpx

from radar.filters import prepare_board_job
from radar.providers.base import NormalizedJob, ScanConfig, public_url

logger = logging.getLogger(__name__)


class TeamtailorProvider:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def fetch_jobs(self, config: ScanConfig) -> list[NormalizedJob]:
        jobs = []
        for company in config.companies:
            if company.source != "teamtailor":
                continue
            try:
                for page in range(config.max_pages):
                    response = await self.client.get(
                        urljoin(company.careers_url.rstrip("/") + "/", "jobs.rss"),
                        params={"offset": page * 100, "per_page": 100}, follow_redirects=True,
                    )
                    response.raise_for_status()
                    root = ElementTree.fromstring(response.content)
                    items = root.findall("./channel/item")
                    for item in items:
                        title = item.findtext("title")
                        url = public_url(item.findtext("link"))
                        if not title or not url:
                            continue
                        places = {node.text.strip() for node in item.iter()
                                  if node.tag.rsplit("}", 1)[-1] == "city" and node.text and node.text.strip()}
                        published = item.findtext("pubDate")
                        try:
                            date = parsedate_to_datetime(published) if published else None
                        except (ValueError, TypeError):
                            date = None
                        job = prepare_board_job(NormalizedJob(
                            source="teamtailor", source_id=f"{company.board}:{item.findtext('guid') or url}",
                            title=title, company=company.name, location=" / ".join(sorted(places)) or None,
                            description=item.findtext("description"), url=url, apply_url=url, posted_at=date,
                        ))
                        if job:
                            jobs.append(job)
                    if len(items) < 100:
                        break
            except (httpx.HTTPError, ElementTree.ParseError) as error:
                logger.warning("Teamtailor %s unavailable (%s)", company.name, type(error).__name__)
        return jobs
