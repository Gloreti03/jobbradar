"""Regression checks for real Radar/profile integration and ranking boundaries."""

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

import llm
from db import Base, get_db
from fixtures import load_fixture
from main import app
from models import ApplicationRow, JobRow, MatchRow
from radar.liveness import check_jobs
from radar.ranking import RankedJob, RankingBatch, rank_jobs
from schemas import JobOut, MatchOut, Profile, RadarResponse
from services.profile_store import save_profile


def example_match(score=80):
    return MatchOut(score=score, verdict="good", reasons=["Relevant analysis experience"], gaps=[], to_clarify=[])


class RadarApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.engine = create_engine(f"sqlite:///{self.directory.name}/test.db", connect_args={"check_same_thread": False})
        Base.metadata.create_all(self.engine)
        self.session = sessionmaker(self.engine, expire_on_commit=False, autoflush=False)
        self.factory_patch = patch("routers.radar.SessionLocal", self.session)
        self.factory_patch.start()
        self.key_patch = patch("routers.radar.DEEPSEEK_API_KEY", "test-only")
        self.key_patch.start()
        self.profile = Profile.model_validate(load_fixture("profile")["profile"])
        self.now = datetime.now(timezone.utc)
        self.rank = AsyncMock(side_effect=lambda profile, jobs: {job.id: example_match() for job in jobs})
        self.rank_patch = patch("routers.radar.rank_jobs", self.rank)
        self.rank_patch.start()

        def database():
            with self.session() as db:
                yield db

        app.dependency_overrides[get_db] = database
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.rank_patch.stop()
        self.key_patch.stop()
        self.factory_patch.stop()
        self.engine.dispose()
        self.directory.cleanup()

    def add_profile(self):
        with self.session() as db:
            save_profile(db, self.profile)

    def add_job(self, source_id="one", **changes):
        values = dict(source="nav", source_id=source_id, title="Data Analyst", company=f"Company {source_id}",
                      location="Oslo", description="Python and SQL", url=f"https://example.org/{source_id}",
                      posted_at=self.now - timedelta(days=1), expires_at=self.now + timedelta(days=10),
                      language="en", norwegian_required=False, status="active")
        values.update(changes)
        with self.session.begin() as db:
            row = JobRow(**values)
            db.add(row)
            db.flush()
            return row.id

    def test_missing_profile_returns_404_before_refresh_or_ranking(self):
        with patch("routers.radar.scan", new_callable=AsyncMock) as scan:
            response = self.client.post("/radar", json={"refresh": True})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(set(response.json()), {"error"})
        scan.assert_not_awaited()
        self.rank.assert_not_awaited()

    def test_empty_database_returns_real_empty_results(self):
        self.add_profile()
        response = self.client.post("/radar", json={})
        result = RadarResponse.model_validate(response.json())
        self.assertEqual(result.scanned_count, 0)
        self.assertEqual(result.results, [])
        self.rank.assert_not_awaited()
        self.assertEqual(self.client.get("/jobs/1").status_code, 404)

    def test_backend_titles_reach_ai_through_the_real_radar_endpoint(self):
        self.profile = self.profile.model_copy(update={
            "search_terms": ["backend developer", "software developer", "Python", "SQL"],
            "preferences": self.profile.preferences.model_copy(update={"roles": ["Backend Developer"]}),
        })
        self.add_profile()
        cognite = self.add_job("cognite", title="Senior Software Engineer - Backend, Knowledge Graph")
        dintero = self.add_job("dintero", title="Senior Backend Engineer – build payment infrastructure at Dintero")
        self.add_job("unrelated", title="Junior Accountant", description="Bookkeeping and financial reporting")
        response = self.client.post("/radar", json={"days": 7, "english_only": True})
        self.assertEqual(response.status_code, 200, response.text)
        result = RadarResponse.model_validate(response.json())
        self.assertEqual({row.job.id for row in result.results}, {cognite, dintero})
        passed_to_ai = self.rank.call_args.args[1]
        self.assertEqual({job.id for job in passed_to_ai}, {cognite, dintero})

    def test_cache_is_shared_with_job_detail_and_invalidated_by_profile_update(self):
        self.add_profile()
        job_id = self.add_job()
        first = self.client.post("/radar", json={})
        self.assertEqual(first.status_code, 200, first.text)
        result = RadarResponse.model_validate(first.json())
        self.assertEqual(result.results[0].job.id, job_id)
        self.assertTrue(first.json()["results"][0]["job"]["posted_at"].endswith("Z"))
        self.assertEqual(self.client.post("/radar", json={}).status_code, 200)
        self.assertEqual(self.rank.await_count, 1)
        self.assertEqual(self.client.get(f"/jobs/{job_id}").json()["match"]["score"], 80)

        with self.session.begin() as db:
            application = ApplicationRow(job_id=job_id, status="applied", cv={}, cover_letter="", notes={})
            db.add(application)
            db.flush()
            application_id = application.id
        self.assertEqual(self.client.get(f"/jobs/{job_id}").json()["application"],
                         {"id": application_id, "status": "applied"})

        with self.session() as db:
            save_profile(db, self.profile.model_copy(update={"summary": "Updated experience"}))
        self.assertIsNone(self.client.get(f"/jobs/{job_id}").json()["match"])
        self.assertEqual(self.client.post("/radar", json={}).status_code, 200)
        self.assertEqual(self.rank.await_count, 2)

    def test_windows_english_filter_and_unknown_dates(self):
        self.add_profile()
        current = self.add_job("current")
        older = self.add_job("older", posted_at=self.now - timedelta(days=12))
        unknown = self.add_job("unknown", posted_at=None)
        self.add_job("norwegian", norwegian_required=True)
        self.add_job("uncertain", norwegian_required=None)
        self.add_job("expired", expires_at=self.now - timedelta(days=1))
        self.add_job("old", posted_at=self.now - timedelta(days=40))
        senior = self.add_job("senior", title="Senior Data Analyst")
        for days in (3, 7, 14, 30):
            with self.subTest(days=days):
                response = self.client.post("/radar", json={"days": days, "english_only": True})
                self.assertEqual(response.status_code, 200, response.text)
                result = RadarResponse.model_validate(response.json())
                self.assertEqual({row.job.id for row in result.results}, {current, older, unknown, senior})
                self.assertEqual(result.results[-1].job.id, unknown)
                self.assertEqual(result.days_used, 30)
                self.assertEqual(result.widened, days < 30)
        self.assertEqual(self.client.post("/radar", json={"days": 2}).status_code, 422)

    def test_profile_changed_during_ranking_returns_409_without_cached_matches(self):
        self.add_profile()
        self.add_job()

        async def changed(profile, jobs):
            with self.session() as db:
                save_profile(db, profile.model_copy(update={"summary": "Changed while ranking"}))
            return {job.id: example_match() for job in jobs}

        self.rank.side_effect = changed
        response = self.client.post("/radar", json={})
        self.assertEqual(response.status_code, 409)
        with self.session() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(MatchRow)), 0)

    def test_ranking_failure_returns_actionable_error_without_saving_partial_matches(self):
        self.add_profile()
        self.add_job()
        self.rank.side_effect = TimeoutError()
        response = self.client.post("/radar", json={})
        self.assertEqual(response.status_code, 504)
        self.assertEqual(set(response.json()), {"error"})
        with self.session() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(MatchRow)), 0)
        with patch("routers.radar.DEEPSEEK_API_KEY", ""):
            self.assertEqual(self.client.post("/radar", json={}).status_code, 503)


class RankingTests(unittest.IsolatedAsyncioTestCase):
    async def test_forty_jobs_use_four_validated_batches_and_disable_thinking(self):
        now = datetime.now(timezone.utc)
        jobs = [JobOut(id=index, source="nav", source_id=str(index), title="Data Analyst",
                       url=f"https://example.org/{index}", discovered_at=now) for index in range(40)]

        async def completion(kind, system, user, schema, **options):
            payload = json.loads(user)
            self.assertEqual(kind, "fast")
            self.assertEqual(options["reasoning_effort"], "none")
            self.assertEqual(options["retries"], 1)
            self.assertLessEqual(len(payload["jobs"]), 10)
            self.assertNotIn("contacts", payload["profile"])
            return RankingBatch(results=[RankedJob(job_id=job["job_id"], match=example_match()) for job in payload["jobs"]])

        with patch("radar.ranking.acomplete_json", side_effect=completion) as call:
            matches = await rank_jobs(Profile(name="Test"), jobs)
        self.assertEqual(len(matches), 40)
        self.assertEqual(call.call_count, 4)

    async def test_unknown_or_missing_ranking_ids_are_rejected(self):
        job = JobOut(id=1, source="nav", source_id="one", title="Analyst", url="https://example.org/1",
                     discovered_at=datetime.now(timezone.utc))
        invalid = RankingBatch(results=[RankedJob(job_id=999, match=example_match())])
        with patch("radar.ranking.acomplete_json", return_value=invalid):
            with self.assertRaises(llm.LLMError):
                await rank_jobs(Profile(name="Test"), [job])

    async def test_shared_llm_parameter_is_opt_in(self):
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"results": []}'), finish_reason="stop")],
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=10),
        )
        create = AsyncMock(return_value=response)
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with patch("llm._aclient", return_value=client):
            await llm.acomplete_json("fast", system="Test", user="Test", schema=RankingBatch)
            self.assertNotIn("reasoning_effort", create.call_args.kwargs)
            await llm.acomplete_json("fast", system="Test", user="Test", schema=RankingBatch, reasoning_effort="none")
            self.assertEqual(create.call_args.kwargs["reasoning_effort"], "none")

    async def test_invalid_model_json_can_be_retried_within_ranking_budget(self):
        def response(content):
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=content), finish_reason="stop")],
                usage=SimpleNamespace(prompt_tokens=10, completion_tokens=10),
            )
        create = AsyncMock(side_effect=[response('{"results":[}'), response('{"results":[]}')])
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with patch("llm._aclient", return_value=client):
            result = await llm.acomplete_json("fast", system="Test", user="Test", schema=RankingBatch,
                                             retries=1, reasoning_effort="none")
        self.assertEqual(result.results, [])
        self.assertEqual(create.await_count, 2)


class LivenessTests(unittest.IsolatedAsyncioTestCase):
    async def test_greenhouse_checks_the_public_posting_endpoint(self):
        job = JobOut(id=353, source="greenhouse", source_id="cognite:5020904101",
                     title="Senior Software Engineer - Backend", discovered_at=datetime.now(timezone.utc),
                     url="https://job-boards.eu.greenhouse.io/cognite/jobs/5020904101")

        def transport(request):
            self.assertEqual(str(request.url), "https://boards-api.greenhouse.io/v1/boards/cognite/jobs/5020904101")
            return httpx.Response(200, json={"id": 5020904101})

        client = httpx.AsyncClient(transport=httpx.MockTransport(transport))
        with patch("radar.liveness.httpx.AsyncClient", return_value=client):
            alive, closed = await check_jobs([job])
        self.assertEqual([row.id for row in alive], [353])
        self.assertEqual(closed, [])


if __name__ == "__main__":
    unittest.main()
