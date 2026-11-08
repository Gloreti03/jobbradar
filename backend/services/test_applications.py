"""Application creation must reuse a draft/applied row, even across backend workers."""

import multiprocessing
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from db import Base, get_db
from fixtures import load_fixture
from llm import LLMError
from main import app
from models import ApplicationRow, JobRow, ProfileRow
from schemas import ApplicationNotes, JobOut, Profile, TailoredCV
from services.profile_store import save_profile


def generated_documents():
    fixture = load_fixture("application")
    return ("en", TailoredCV.model_validate(fixture["cv"]), fixture["cover_letter"],
            ApplicationNotes.model_validate(fixture["notes"]))


def worker_request(database_url, barrier, results):
    """Each process has its own engine, sessions and application instance."""
    engine = create_engine(database_url, connect_args={"check_same_thread": False})
    factory = sessionmaker(engine, expire_on_commit=False)

    def database():
        with factory() as db:
            yield db

    def generate(*args):
        barrier.wait(timeout=10)  # both workers have passed the initial existing-row check
        return generated_documents()

    app.dependency_overrides[get_db] = database
    try:
        with patch("routers.applications.tailor", side_effect=generate):
            client = TestClient(app)
            try:
                response = client.post("/applications", json={"job_id": 2})
                results.put((response.status_code, response.json().get("id")))
            finally:
                client.close()
    except Exception as error:
        results.put(("error", type(error).__name__))
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


class ApplicationCreationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.url = f"sqlite:///{self.directory.name}/applications.db"
        self.engine = create_engine(self.url, connect_args={"check_same_thread": False})
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(self.engine, expire_on_commit=False)
        self.profile = Profile.model_validate(load_fixture("profile")["profile"])
        with self.factory() as db:
            save_profile(db, self.profile)
            db.add(JobRow(**JobOut.model_validate(load_fixture("application")["job"]).model_dump()))
            db.commit()

        def database():
            with self.factory() as db:
                yield db

        app.dependency_overrides[get_db] = database
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.engine.dispose()
        self.directory.cleanup()

    def count(self):
        with self.factory() as db:
            return db.scalar(select(func.count()).select_from(ApplicationRow))

    def test_first_request_creates_and_repeat_reuses_the_edited_draft(self):
        with patch("routers.applications.tailor", return_value=generated_documents()) as generate:
            first = self.client.post("/applications", json={"job_id": 2})
            self.assertEqual(first.status_code, 201, first.text)
            application_id = first.json()["id"]
            edited = self.client.patch(f"/applications/{application_id}", json={"cover_letter": "My edited letter."})
            self.assertEqual(edited.status_code, 200)
            repeat = self.client.post("/applications", json={"job_id": 2})
        self.assertEqual(repeat.status_code, 200, repeat.text)
        self.assertEqual(repeat.json()["id"], application_id)
        self.assertEqual(repeat.json()["cover_letter"], "My edited letter.")
        self.assertEqual(self.count(), 1)
        generate.assert_called_once()

    def test_existing_applied_application_and_snapshot_are_preserved(self):
        fixture = load_fixture("application")
        with self.factory.begin() as db:
            db.add(ApplicationRow(id=1, job_id=2, status="applied", language="en", cv=fixture["cv"],
                                  cover_letter=fixture["cover_letter"], notes=fixture["notes"],
                                  snapshot=fixture["snapshot"]))
        with patch("routers.applications.tailor") as generate:
            response = self.client.post("/applications", json={"job_id": 2})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["id"], 1)
        self.assertEqual(response.json()["status"], "applied")
        self.assertEqual(response.json()["snapshot"], self.client.get("/applications/1").json()["snapshot"])
        generate.assert_not_called()

    def test_legacy_duplicates_reuse_the_same_latest_row_as_job_detail(self):
        fixture = load_fixture("application")
        with self.factory.begin() as db:
            for application_id in (1, 2):
                db.add(ApplicationRow(id=application_id, job_id=2, cv=fixture["cv"],
                                      cover_letter=f"Saved letter {application_id}.", notes=fixture["notes"]))
        with patch("routers.applications.tailor") as generate:
            response = self.client.post("/applications", json={"job_id": 2})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["id"], self.client.get("/jobs/2").json()["application"]["id"])
        self.assertEqual(response.json()["cover_letter"], "Saved letter 2.")
        self.assertEqual(self.count(), 2)
        generate.assert_not_called()

    def test_simultaneous_requests_return_the_same_application(self):
        barrier = Barrier(2)

        def generate(*args):
            barrier.wait(timeout=10)
            return generated_documents()

        with patch("routers.applications.tailor", side_effect=generate):
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(self.client.post, "/applications", json={"job_id": 2}) for _ in range(2)]
                responses = [future.result(timeout=15) for future in futures]
        self.assertEqual(sorted(response.status_code for response in responses), [200, 201])
        self.assertEqual(len({response.json()["id"] for response in responses}), 1)
        self.assertEqual(self.count(), 1)

    def test_separate_backend_processes_cannot_create_duplicates(self):
        context = multiprocessing.get_context("spawn")
        barrier, results = context.Barrier(2), context.Queue()
        processes = [context.Process(target=worker_request, args=(self.url, barrier, results)) for _ in range(2)]
        try:
            for process in processes:
                process.start()
            responses = [results.get(timeout=20) for _ in processes]
            for process in processes:
                process.join(timeout=5)
                self.assertEqual(process.exitcode, 0)
            self.assertEqual(sorted(status for status, _ in responses), [200, 201], responses)
            self.assertEqual(len({application_id for _, application_id in responses}), 1)
            self.assertEqual(self.count(), 1)
        finally:
            for process in processes:
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=5)
            results.close()
            results.join_thread()

    def test_generation_failure_does_not_leave_a_draft_and_retry_can_succeed(self):
        with patch("routers.applications.tailor", side_effect=LLMError("Generation failed")):
            response = self.client.post("/applications", json={"job_id": 2})
        self.assertEqual(response.status_code, 502)
        self.assertEqual(self.count(), 0)
        with patch("routers.applications.tailor", return_value=generated_documents()):
            retry = self.client.post("/applications", json={"job_id": 2})
        self.assertEqual(retry.status_code, 201, retry.text)
        self.assertEqual(self.count(), 1)

    def test_a_profile_change_during_generation_does_not_save_stale_documents(self):
        def generate(*args):
            with self.factory() as db:
                save_profile(db, self.profile.model_copy(update={"name": "Different Test Candidate"}))
            return generated_documents()

        with patch("routers.applications.tailor", side_effect=generate):
            response = self.client.post("/applications", json={"job_id": 2})
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(self.count(), 0)

    def test_missing_profile_or_job_does_not_generate_documents(self):
        with patch("routers.applications.tailor") as generate:
            missing_job = self.client.post("/applications", json={"job_id": 999999})
            self.assertEqual(missing_job.status_code, 404)
            with self.factory.begin() as db:
                db.delete(db.get(ProfileRow, 1))
            missing_profile = self.client.post("/applications", json={"job_id": 2})
            self.assertEqual(missing_profile.status_code, 404)
        self.assertEqual(self.count(), 0)
        generate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
