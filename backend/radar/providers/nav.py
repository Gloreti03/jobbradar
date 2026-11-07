"""Official NAV feed, including current-detail checks and token rotation."""

import asyncio
import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from urllib.parse import urljoin, urlsplit

import httpx

from radar.filters import language_flags
from radar.providers.base import NormalizedJob, ScanConfig, clean_description, parse_date, public_url

logger = logging.getLogger(__name__)
BASE_URL = "https://pam-stilling-feed.nav.no/"


class NavProvider:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client
        self.token = os.getenv("NAV_TOKEN", "").strip()
        self.token_lock = asyncio.Lock()

    async def _public_token(self, previous: str) -> None:
        async with self.token_lock:
            if self.token and self.token != previous:
                return
            response = await self.client.get(urljoin(BASE_URL, "api/publicToken"))
            response.raise_for_status()
            match = re.search(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", response.text)
            if not match:
                raise ValueError("NAV public token response did not contain a JWT")
            self.token = match.group()

    async def _get(self, path: str, *, headers: dict | None = None) -> httpx.Response:
        url = urljoin(BASE_URL, path)
        if urlsplit(url).netloc != urlsplit(BASE_URL).netloc:
            raise ValueError("NAV returned a URL outside the feed host")
        if not self.token:
            await self._public_token("")
        for attempt in range(3):
            token = self.token
            response = await self.client.get(url, headers={
                "Accept": "application/json", "Authorization": f"Bearer {token}", **(headers or {}),
            })
            if response.status_code == 401 and attempt < 2:
                await self._public_token(token)
                continue
            if response.status_code in {429, 500, 502, 503, 504} and attempt < 2:
                await asyncio.sleep(attempt + 1)
                continue
            if response.status_code == 304:
                return response
            response.raise_for_status()
            return response
        raise RuntimeError("NAV request exhausted retries")

    async def _detail(self, item: dict, config: ScanConfig) -> NormalizedJob | None:
        entry = item.get("_feed_entry") or {}
        source_id = str(entry.get("uuid") or "")
        try:
            response = await self._get(item["url"])
        except httpx.HTTPStatusError as error:
            if error.response.status_code in {404, 410} and source_id:
                return NormalizedJob(source="nav", source_id=source_id, title="", url=BASE_URL, status="inactive")
            raise
        detail = response.json()
        source_id = str(detail.get("uuid") or source_id)
        if not source_id:
            return None
        content = detail.get("json") or detail.get("ad_content") or {}
        if isinstance(content, str):
            content = json.loads(content)
        expires = parse_date(content.get("expires"))
        places = content.get("workLocations") or []
        municipalities = {(place.get("municipal") or "").strip().upper() for place in places}
        active = detail.get("status") == "ACTIVE" and (expires is None or expires > datetime.now(timezone.utc))
        in_area = bool(municipalities.intersection(config.municipalities))
        if not active or not in_area:
            return NormalizedJob(source="nav", source_id=source_id, title="", url=BASE_URL, status="inactive")
        title = (content.get("title") or item.get("title") or "").strip()
        if not title:
            return None
        description = clean_description(content.get("description") or "", content.get("contactList"))
        language, required = language_flags(title, description)
        location = " / ".join(sorted({
            (place.get("municipal") or place.get("city") or "").strip().title() for place in places
        } - {""}))
        url = public_url(content.get("sourceurl")) or public_url(content.get("link"))
        return NormalizedJob(
            source="nav", source_id=source_id, title=title,
            company=(content.get("employer") or {}).get("name") or entry.get("businessName"),
            location=location or None, description=description or None,
            url=url or f"https://arbeidsplassen.nav.no/stillinger/stilling/{source_id}",
            apply_url=public_url(content.get("applicationUrl")),
            posted_at=parse_date(content.get("published")), expires_at=expires,
            language=language, norwegian_required=required,
        )

    async def fetch_jobs(self, config: ScanConfig) -> list[NormalizedJob]:
        since = datetime.now(timezone.utc) - timedelta(days=config.days)
        path = "api/v1/feed?last=true"
        backfill = not config.latest_only
        seen = set()
        updates: list[NormalizedJob] = []
        active_count = 0
        for page_number in range(1, config.max_pages + 1):
            headers = {"If-Modified-Since": format_datetime(since, usegmt=True)} if path == "api/v1/feed" else None
            response = await self._get(path, headers=headers)
            page = response.json() if response.status_code != 304 else {}
            pending = []
            for item in page.get("items", []):
                entry = item.get("_feed_entry") or {}
                source_id = str(entry.get("uuid") or "")
                identity = source_id or item.get("url")
                municipal = (entry.get("municipal") or "").strip().upper()
                relevant = entry.get("status") == "ACTIVE" and municipal in config.municipalities
                if not item.get("url") or identity in seen or not (relevant or source_id in config.tracked_ids):
                    continue
                seen.add(identity)
                pending.append(item)
            for start in range(0, len(pending), 8):
                results = await asyncio.gather(*(self._detail(item, config) for item in pending[start:start + 8]))
                for result in results:
                    if result:
                        updates.append(result)
                        active_count += result.status == "active"
                if active_count >= config.limit:
                    break
            logger.info("NAV page %s: %s current active jobs, %s details", page_number, active_count, len(updates))
            path = "api/v1/feed" if backfill else page.get("next_url")
            backfill = False
            if not path or active_count >= config.limit:
                break
        return updates
