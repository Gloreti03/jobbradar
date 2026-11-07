"""Regression checks. From backend/: uv run python -m unittest radar.test_pipeline"""

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import httpx
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from db import Base
from models import JobRow
from radar.filters import filter_jobs
from radar.providers.base import NormalizedJob, ScanConfig, canonical_url
from radar.providers.nav import NavProvider
from radar.scanner import dump_seed, load_seed, save_jobs
from schemas import JobOut, Profile


class SeedTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.engine = create_engine(f"sqlite:///{self.directory.name}/test.db")
        Base.metadata.create_all(self.engine)
        self.session = sessionmaker(self.engine, expire_on_commit=False, autoflush=False)
        self.factory_patch = patch("radar.scanner.SessionLocal", self.session)
        self.init_patch = patch("radar.scanner.init_db")
        self.factory_patch.start()
        self.init_patch.start()

    def tearDown(self):
        self.factory_patch.stop()
        self.init_patch.stop()
        self.engine.dispose()
        self.directory.cleanup()

    def test_seed_reload_preserves_ids_and_query_based_job_urls(self):
        jobs = [NormalizedJob(source="nav", source_id=str(index), title=f"Analyst {index}",
                              company="Company", url=f"https://example.org/jobs?gh_jid={index}")
                for index in (1, 2)]
        self.assertEqual(save_jobs(jobs), 2)
        with self.session() as db:
            before = {job.source_id: job.id for job in db.scalars(select(JobRow))}
        path = Path(self.directory.name) / "seed.json"
        self.assertEqual(dump_seed(path), 2)
        load_seed(path)
        load_seed(path)
        with self.session() as db:
            self.assertEqual(before, {job.source_id: job.id for job in db.scalars(select(JobRow))})
        self.assertEqual(canonical_url("https://example.org/jobs?gh_jid=1&utm_source=test"),
                         "https://example.org/jobs?gh_jid=1")

    def test_title_change_does_not_hide_new_job_with_previous_title(self):
        first = NormalizedJob(source="nav", source_id="first", title="Analyst", company="Company", url="https://example.org/1")
        save_jobs([first])
        second = first.model_copy(update={"source_id": "second", "url": "https://example.org/2"})
        self.assertEqual(save_jobs([first.model_copy(update={"title": "Engineer"}), second]), 2)


class FeedTests(unittest.IsolatedAsyncioTestCase):
    async def test_details_override_stale_feed_status_and_location(self):
        async def transport(request):
            if request.url.path == "/api/publicToken":
                return httpx.Response(200, text="Current public token: eyJtest.public.signature")
            if request.url.path == "/api/v1/feed":
                return httpx.Response(200, json={"items": [
                    {"url": f"/api/v1/feedentry/{identity}", "_feed_entry": {
                        "uuid": identity, "status": "ACTIVE", "municipal": "OSLO"}}
                    for identity in ("closed", "moved", "open")
                ], "next_url": None})
            identity = request.url.path.rsplit("/", 1)[-1]
            return httpx.Response(200, json={"uuid": identity,
                "status": "INACTIVE" if identity == "closed" else "ACTIVE",
                "json": {"title": "Analyst", "description": "Contact Jane Example at jane@example.org",
                         "contactList": [{"name": "Jane Example", "email": "jane@example.org"}],
                         "workLocations": [{"municipal": "KRISTIANSAND" if identity == "moved" else "OSLO"}]}})

        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
            results = await NavProvider(client).fetch_jobs(ScanConfig(latest_only=True))
        jobs = {job.source_id: job for job in results}
        self.assertEqual(jobs["closed"].status, "inactive")
        self.assertEqual(jobs["moved"].status, "inactive")
        self.assertEqual(jobs["open"].status, "active")
        self.assertIsNone(jobs["open"].posted_at)
        self.assertNotIn("Jane Example", jobs["open"].description)
        self.assertNotIn("jane@example.org", jobs["open"].description)

    def test_unknown_dates_follow_recent_jobs_without_becoming_recent(self):
        now = datetime.now(timezone.utc)
        base = dict(source="nav", source_id="test", title="Analyst", url="https://example.org/1",
                    discovered_at=now, location="Oslo")
        recent = JobOut(id=1, **base, posted_at=now - timedelta(days=1))
        old = recent.model_copy(update={"id": 2, "url": "https://example.org/2", "posted_at": now - timedelta(days=10)})
        unknown = recent.model_copy(update={"id": 3, "url": "https://example.org/3", "posted_at": None})
        result = filter_jobs([unknown, old, recent], Profile(name="Test"), 7, False, now)
        self.assertEqual([job.id for job in result], [1, 3])


if __name__ == "__main__":
    unittest.main()
