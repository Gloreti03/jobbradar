"""Application creation: one draft per double click, a new draft on a later request."""

import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Event
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

    def test_new_draft_request_keeps_the_edited_draft(self):
        with patch("routers.applications.tailor", return_value=generated_documents()) as generate:
            first = self.client.post("/applications", json={"job_id": 2})
            self.assertEqual(first.status_code, 201, first.text)
            application_id = first.json()["id"]
            edited = self.client.patch(f"/applications/{application_id}", json={"cover_letter": "My edited letter."})
            self.assertEqual(edited.status_code, 200)
            again = self.client.post("/applications", json={"job_id": 2})  # "Generate new draft"
        self.assertEqual(again.status_code, 201, again.text)
        self.assertNotEqual(again.json()["id"], application_id)
        self.assertEqual(self.client.get(f"/applications/{application_id}").json()["cover_letter"], "My edited letter.")
        self.assertEqual(self.client.get("/jobs/2").json()["application"]["id"], again.json()["id"])
        self.assertEqual(self.count(), 2)
        self.assertEqual(generate.call_count, 2)

    def test_existing_applied_application_and_snapshot_are_preserved(self):
        fixture = load_fixture("application")
        with self.factory.begin() as db:
            db.add(ApplicationRow(id=1, job_id=2, status="applied", language="en", cv=fixture["cv"],
                                  cover_letter=fixture["cover_letter"], notes=fixture["notes"],
                                  snapshot=fixture["snapshot"]))
        before = self.client.get("/applications/1").json()
        with patch("routers.applications.tailor", return_value=generated_documents()):
            response = self.client.post("/applications", json={"job_id": 2})
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["status"], "draft")
        self.assertEqual(self.client.get("/applications/1").json(), before)

    def test_double_click_returns_the_draft_being_generated(self):
        started = Event()

        def generate(*args):
            started.set()
            time.sleep(0.5)  # the second request arrives while documents are being written
            return generated_documents()

        with patch("routers.applications.tailor", side_effect=generate) as tailor:
            with ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(self.client.post, "/applications", json={"job_id": 2})
                self.assertTrue(started.wait(10))
                second = pool.submit(self.client.post, "/applications", json={"job_id": 2})
                responses = [first.result(timeout=15), second.result(timeout=15)]
        self.assertEqual([response.status_code for response in responses], [201, 201], [r.text for r in responses])
        self.assertEqual(len({response.json()["id"] for response in responses}), 1)
        self.assertEqual(self.count(), 1)
        tailor.assert_called_once()

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
