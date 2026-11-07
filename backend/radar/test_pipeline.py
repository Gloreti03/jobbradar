"""Regression checks. From backend/: uv run python -m unittest radar.test_pipeline"""

import os
import subprocess
import sys
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
from schemas import JobOut, Preferences, Profile


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


class TitleFilterTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.profile = Profile(name="Backend regression", preferences=Preferences(
            roles=["Backend Developer"], cities=["Oslo"], seniority="junior"),
            search_terms=["backend developer", "software developer", "Python", "FastAPI", "SQL"])

    def job(self, job_id, title, **changes):
        values = dict(id=job_id, source="nav", source_id=str(job_id), title=title,
                      company=f"Company {job_id}", location="Oslo", url=f"https://example.org/{job_id}",
                      posted_at=self.now - timedelta(days=1), discovered_at=self.now,
                      language="en", norwegian_required=False)
        values.update(changes)
        return JobOut(**values)

    def selected(self, jobs, profile=None):
        return filter_jobs(jobs, profile or self.profile, 7, True, self.now)

    def test_reported_backend_titles_reach_ranking_for_junior_profile(self):
        jobs = [self.job(353, "Senior Software Engineer - Backend, Knowledge Graph"),
                self.job(195, "Senior Backend Engineer – build payment infrastructure at Dintero")]
        self.assertEqual({job.id for job in self.selected(jobs)}, {353, 195})

    def test_word_order_punctuation_and_compound_titles(self):
        titles = ["Backend Software Engineer", "Back-end Engineer", "Back‑end Engineer", "Backendutvikler",
                  "Software Engineer (Backend)", "Senior Backend Engineer"]
        jobs = [self.job(index, title) for index, title in enumerate(titles)]
        self.assertEqual(len(self.selected(jobs)), len(titles))

    def test_description_supplies_missing_title_context(self):
        job = self.job(1, "Platform Specialist", description="Build backend developer tooling with Python and FastAPI.")
        self.assertEqual([row.id for row in self.selected([job])], [1])

    def test_explicit_negative_terms_still_exclude_senior_titles(self):
        profile = self.profile.model_copy(update={"search_terms": self.profile.search_terms + ["  -Senior  "]})
        jobs = [self.job(1, "Senior Backend Engineer"), self.job(2, "Backend Engineer")]
        self.assertEqual([job.id for job in self.selected(jobs, profile)], [2])

    def test_short_keywords_do_not_match_inside_unrelated_words(self):
        profile = Profile(name="ML regression", search_terms=["ML", "R", ".NET"])
        jobs = [self.job(1, "HTML Designer"), self.job(2, "Network Operator"),
                self.job(3, "ML Engineer"), self.job(4, "C#/.NET Developer")]
        self.assertEqual({job.id for job in self.selected(jobs, profile)}, {3, 4})

    def test_seniority_alone_does_not_select_unrelated_roles(self):
        profile = self.profile.model_copy(update={"search_terms": ["junior", "backend developer"]})
        jobs = [self.job(1, "Junior Accountant"), self.job(2, "Senior Backend Engineer")]
        self.assertEqual([job.id for job in self.selected(jobs, profile)], [2])


class DateTimezoneTests(unittest.TestCase):
    def test_oslo_dates_use_bundled_timezone_data_when_system_data_is_absent(self):
        code = """
from datetime import datetime, timezone
from zoneinfo import TZPATH
from radar.providers.base import parse_date

assert not TZPATH
assert parse_date('2026-11-07T10:00:00') == datetime(2026, 11, 7, 9, tzinfo=timezone.utc)
assert parse_date('2026-07-07T10:00:00') == datetime(2026, 7, 7, 8, tzinfo=timezone.utc)
assert parse_date('2026-11-07T10:00:00+02:00') == datetime(2026, 11, 7, 8, tzinfo=timezone.utc)
assert parse_date('2026-11-07T10:00:00Z') == datetime(2026, 11, 7, 10, tzinfo=timezone.utc)
assert parse_date('invalid') is None
assert parse_date(None) is None
"""
        result = subprocess.run(
            [sys.executable, "-c", code], cwd=Path(__file__).resolve().parents[1],
            env={**os.environ, "PYTHONTZPATH": ""}, capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
