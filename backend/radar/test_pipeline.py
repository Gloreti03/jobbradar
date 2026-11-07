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
from models import JobRow, MatchRow, ProfileRow
from radar.filters import filter_jobs, language_flags
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

    def test_legacy_seed_language_flags_are_corrected_and_cached_matches_invalidated(self):
        job = NormalizedJob(source="nav", source_id="optional-norwegian", title="Software Engineer",
                            company="Company", url="https://example.org/optional",
                            description="We build software. Good English communication skills; Norwegian is a plus.",
                            language="en", norwegian_required=True)
        save_jobs([job])
        with self.session.begin() as db:
            row = db.scalar(select(JobRow))
            job_id = row.id
            db.add(ProfileRow(id=1, data=Profile(name="Test").model_dump()))
            db.add(MatchRow(profile_id=1, job_id=job_id, score=30, verdict="poor", reasons=[], gaps=[], to_clarify=[]))
        path = Path(self.directory.name) / "legacy-seed.json"
        dump_seed(path)
        load_seed(path)
        with self.session() as db:
            row = db.get(JobRow, job_id)
            self.assertEqual(row.source_id, "optional-norwegian")
            self.assertEqual(row.language, "en")
            self.assertIs(row.norwegian_required, False)
            self.assertIsNone(db.get(MatchRow, (1, job_id)))


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

    def test_short_keywords_use_whole_words_in_titles_and_descriptions(self):
        profile = Profile(name="Acronyms", search_terms=["BI", "ML", "AI"])
        jobs = [self.job(1, "Retail assistant", description="We sell HTML email templates and bicycles."),
                self.job(2, "BI Analyst"), self.job(3, "ML Engineer"), self.job(4, "AI Researcher"),
                self.job(5, "Researcher", description="Develop ML models.")]
        self.assertEqual({job.id for job in self.selected(jobs, profile)}, {2, 3, 4, 5})

    def test_employer_bi_is_not_a_business_intelligence_skill(self):
        profile = Profile(name="Andrea regression", search_terms=["BI", "BI analyst", "internship Oslo"])
        jobs = [self.job(26, "HIJA BI søker butikkmedarbeider - Oslo", company="Hija Bi As",
                         description="Vi i HIJA BI søker en butikkmedarbeider med interesse for mote."),
                self.job(2, "BI Analyst - Oslo")]
        self.assertEqual([job.id for job in self.selected(jobs, profile)], [2])

    def test_short_fragments_of_multiword_terms_need_role_context(self):
        profile = Profile(name="Acronyms", search_terms=["BI analyst", "ML engineer", "AI engineer", "R analyst"])
        jobs = [self.job(1, "HIJA BI søker butikkmedarbeider"),
                self.job(2, "Account Executive (R-20081)"),
                self.job(3, "AI Customer Support"),
                self.job(4, "ML Software Engineer"), self.job(5, "Senior AI Platform Engineer"),
                self.job(6, "Senior BI Analyst")]
        self.assertEqual({job.id for job in self.selected(jobs, profile)}, {4, 5, 6})

    def test_location_in_search_phrase_cannot_select_unrelated_jobs(self):
        profile = Profile(name="Andrea regression", search_terms=["data analyst", "internship Oslo"],
                          preferences=Preferences(cities=["Oslo"]))
        jobs = [self.job(1, "Frisør jobb i Oslo"), self.job(2, "Tilkallingsvikar i barnehage, Oslo"),
                self.job(3, "Summer Internship in Oslo"), self.job(4, "Data Analyst - Oslo")]
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


class LanguageRequirementTests(unittest.TestCase):
    def test_optional_norwegian_is_not_a_requirement(self):
        examples = [
            "Good English communication skills; Norwegian is a plus.",
            "Fluent English. Norwegian is an advantage.",
            "Fluency in Norwegian is a plus.",
            "Nice to have: Fluency in Norwegian.",
            "Nice to have:\nFluency in Norwegian.",
            "Norwegian language skills would be an asset.",
            "Proficiency in Norwegian is desirable.",
            "Fluent Norwegian is preferred.",
            "Norwegian (preferred).",
            "Norwegian is not required.",
            "Norwegian is not mandatory.",
            "No Norwegian required.",
            "You do not need to speak Norwegian.",
            "Norsk er en fordel.",
            "Gode norskkunnskaper er en fordel.",
            "Norsk er ønskelig, men ikke et krav.",
            "Norsk er ikke påkrevd.",
            "Du trenger ikke å snakke norsk.",
            "You must be fluent in Norwegian or English.",
            "Du må beherske norsk eller engelsk.",
            "Du må kunne gjøre deg selv forstått på norsk/engelsk.",
        ]
        for text in examples:
            with self.subTest(text=text):
                self.assertIs(language_flags("Engineer", text)[1], False)

    def test_mandatory_norwegian_is_kept(self):
        examples = [
            "Fluent Norwegian is required.",
            "Fluency in English and Norwegian is essential for this role.",
            "Norwegian language proficiency at C1 level.",
            "Norwegian language fluency.",
            "We need a Norwegian-speaking engineer.",
            "The working language is Norwegian.",
            "Norwegian is our working language.",
            "Du må beherske norsk muntlig og skriftlig.",
            "Norsk er et absolutt krav.",
            "Du må ha bestått norskprøve B2 muntlig og skriftlig.",
            "Arbeidsspråket er norsk.",
            "Behersker norsk som arbeidsspråk.",
            "Kommuniserer tydelig og presist, både på norsk og engelsk.",
            "Sterke skriftlige kommunikasjonsevner på norsk.",
            "Språkferdigheter på norsk – tilsvarende C1.",
            "Norsk eller annet skandinavisk språk: både muntlige og skriftlige ferdigheter er nødvendig.",
            "God muntlig og skriftlig fremstillingsevne på norsk\nØnskelig:\nVidereutdanning i ledelse.",
        ]
        for text in examples:
            with self.subTest(text=text):
                self.assertIs(language_flags("Engineer", text)[1], True)

    def test_an_optional_clause_does_not_hide_a_separate_mandatory_requirement(self):
        examples = [
            "Norwegian is not required for interns. Fluent Norwegian is required for this senior role.",
            "Nice to have: Norwegian. Norwegian is mandatory for client meetings.",
            "Norwegian is required. English is a plus.",
        ]
        for text in examples:
            with self.subTest(text=text):
                self.assertIs(language_flags("Engineer", text)[1], True)

    def test_non_language_mentions_do_not_become_mandatory_language_requirements(self):
        self.assertIs(language_flags("Engineer", "We require a Norwegian work permit.")[1], False)
        self.assertIsNone(language_flags("Forsker", "Vitnemålet må være på engelsk eller norsk.")[1])
        self.assertIsNone(language_flags("Forsker", "Dersom vitnemålet ikke er på engelsk eller norsk, er det et krav om godkjenning fra NOKUT.")[1])


if __name__ == "__main__":
    unittest.main()
