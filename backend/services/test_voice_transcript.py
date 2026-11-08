"""Voice question alignment regressions; synthetic transcripts and isolated SQLite only."""

import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from openai import OpenAIError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db import Base, get_db
from fixtures import load_fixture
from llm import LLMError
from main import app
from models import ApplicationRow, InterviewRow, JobRow
from routers.interview import VoiceTurn, _assign_questions
from schemas import InterviewFeedback, InterviewQuestion, JobOut, Snapshot, TranscriptTurn
from services import interview as svc


def plan():
    return [InterviewQuestion.model_validate(q) for q in load_fixture("interview")["plan"]]


def turn(role, text):
    return VoiceTurn(role=role, content=text)


def model_map(starts):
    return svc._VoiceQuestionMap(assignments=[
        svc._VoiceQuestionAssignment(turn_index=i, question_id=qid) for i, qid in starts.items()
    ])


DOCKER_QUESTION = "How would you use a Docker lab to move a notebook model into production?"


def changed_topic_turns():
    turns = []
    for q in plan():
        question = DOCKER_QUESTION if q.id == 4 else q.question
        turns += [turn("interviewer", question), turn("candidate", f"My answer for topic {q.id}.")]
    return turns


class VoiceAssignmentTests(unittest.TestCase):
    def test_plan_questions_need_no_model_call(self):
        turns = []
        for q in plan():
            turns += [turn("interviewer", q.question), turn("candidate", f"Answer {q.id}.")]
        with patch.object(svc, "map_voice_questions") as mapper:
            transcript, spoken_plan = _assign_questions(turns, plan())
        mapper.assert_not_called()
        self.assertEqual([t.question_id for t in transcript if t.role == "candidate"], [1, 2, 3, 4, 5, 6])
        self.assertEqual([q.question for q in spoken_plan], [q.question for q in plan()])

    def test_acknowledgement_cannot_jump_to_a_later_question(self):
        questions = plan()
        turns = [turn("interviewer", questions[0].question), turn("candidate", "First answer."),
                 turn("interviewer", "You automated data cleaning of POS exports and built weekly dashboards."),
                 turn("candidate", "The rest of my answer.")]
        with patch.object(svc, "map_voice_questions") as mapper:
            transcript, _ = _assign_questions(turns, questions)
        mapper.assert_not_called()
        self.assertEqual([t.question_id for t in transcript if t.role == "candidate"], [1, 1])

    def test_question_is_matched_without_the_acknowledgement(self):
        questions = plan()
        turns = [turn("interviewer", questions[0].question), turn("candidate", "First answer."),
                 turn("interviewer", "You are interested in energy forecasting and data science. " + questions[1].question),
                 turn("candidate", "Second answer.")]
        with patch.object(svc, "map_voice_questions") as mapper:
            transcript, spoken = _assign_questions(turns, questions)
        mapper.assert_not_called()
        self.assertEqual([t.question_id for t in transcript if t.role == "candidate"], [1, 2])
        self.assertEqual(spoken[1].question, questions[1].question)

    def test_changed_topic_advances_and_preserves_the_actual_question(self):
        questions = plan()
        expected = {i * 2: i + 1 for i in range(6)}
        with patch.object(svc, "complete_json", return_value=model_map(expected)) as model:
            transcript, spoken = _assign_questions(changed_topic_turns(), questions)
        model.assert_called_once()
        self.assertEqual([t.question_id for t in transcript if t.role == "candidate"], [1, 2, 3, 4, 5, 6])
        self.assertEqual(spoken[3].question, DOCKER_QUESTION)
        self.assertEqual(questions[3].question, plan()[3].question)  # input plan is not mutated

    def test_clarification_repeat_and_split_answers_stay_on_the_current_question(self):
        questions = plan()
        turns = [turn("interviewer", questions[0].question), turn("candidate", "First part."),
                 turn("candidate", "Second part."), turn("interviewer", "Could you finish your answer?"),
                 turn("candidate", "Here is the rest."), turn("interviewer", questions[0].question),
                 turn("candidate", "Repeated answer."), turn("interviewer", questions[1].question),
                 turn("candidate", "Next topic.")]
        with patch.object(svc, "complete_json", return_value=model_map({0: 1, 3: 1, 5: 1, 7: 2})):
            transcript, spoken = _assign_questions(turns, questions)
        answers = [t for t in transcript if t.role == "candidate"]
        self.assertEqual([t.question_id for t in answers], [1, 1, 1, 2])
        self.assertEqual(answers[0].content, "First part. Second part.")
        self.assertEqual(spoken[0].question, questions[0].question)

    def test_first_question_may_be_missing_from_the_recording(self):
        questions = plan()
        turns = [turn("candidate", "First answer."), turn("interviewer", questions[1].question),
                 turn("candidate", "Second answer.")]
        transcript, _ = _assign_questions(turns, questions)
        self.assertEqual([t.question_id for t in transcript if t.role == "candidate"], [1, 2])

    def test_a_related_followup_is_not_anchored_to_a_later_question_by_keywords(self):
        questions = plan()
        turns = [turn("interviewer", questions[0].question), turn("candidate", "I enjoy forecasting projects."),
                 turn("interviewer", "How did you validate that forecasting model?"),
                 turn("candidate", "I checked the predictions against later observations."),
                 turn("interviewer", questions[1].question), turn("candidate", "Next core answer.")]
        with patch.object(svc, "complete_json", return_value=model_map({0: 1, 2: 1, 4: 2})):
            transcript, _ = _assign_questions(turns, questions)
        self.assertEqual([t.question_id for t in transcript if t.role == "candidate"], [1, 1, 2])

    def test_early_closing_ignores_later_speech_and_cleans_fillers(self):
        turns = [turn("interviewer", "[warm] " + plan()[0].question), turn("candidate", "Um, Python and SQL."),
                 turn("candidate", "Hmm..."), turn("interviewer", "Thank you, that’s all from my side."),
                 turn("candidate", "Thank you."), turn("interviewer", plan()[1].question)]
        with patch.object(svc, "map_voice_questions") as mapper:
            transcript, _ = _assign_questions(turns, plan())
        mapper.assert_not_called()
        answers = [t for t in transcript if t.role == "candidate"]
        self.assertEqual([(t.question_id, t.content) for t in answers], [(1, "Python and SQL.")])
        self.assertIsNone(transcript[-1].question_id)

    def test_repeat_and_stop_requests_are_not_graded_as_answers(self):
        questions = plan()
        turns = [turn("interviewer", questions[0].question), turn("candidate", "Could you repeat the question?"),
                 turn("interviewer", questions[0].question), turn("candidate", "I enjoy forecasting."),
                 turn("interviewer", questions[1].question), turn("candidate", "I would like to stop the interview now."),
                 turn("interviewer", "Thank you, that's all from my side.")]
        transcript, _ = _assign_questions(turns, questions)
        self.assertEqual([t.question_id for t in transcript if t.role == "candidate"], [None, 1, None])


class VoiceMapValidationTests(unittest.TestCase):
    def test_invalid_references_and_changed_anchors_are_rejected(self):
        transcript = [TranscriptTurn(role=t.role, content=t.content) for t in changed_topic_turns()]
        transcript.append(TranscriptTurn(role="interviewer", content="That's all from my side."))
        transcript.append(TranscriptTurn(role="interviewer", content=plan()[5].question))
        invalid = [
            {0: 1, 1: 2},  # candidate turn
            {0: 1, 99: 2},  # nonexistent turn
            {0: 1, 12: 2},  # closing line
            {0: 1, 13: 2},  # after closing
            {0: 2, 2: 1},  # backwards question ids
            {2: 2, 0: 1},  # backwards turn indices
            {0: 1},  # incomplete mapping
            {0: 1, 2: 3},  # changes a known question
        ]
        for starts in invalid:
            with self.subTest(starts=starts), patch.object(svc, "complete_json", return_value=model_map(starts)):
                with self.assertRaises(LLMError):
                    svc.map_voice_questions(plan(), transcript, {0: 1, 2: 2},
                                            {0: plan()[0].question, 2: plan()[1].question})


class FeedbackConsistencyTests(unittest.TestCase):
    def feedback(self):
        data = load_fixture("interview")["feedback"]
        data["overall_score"] = 42
        for question, score in zip(data["questions"], [2, 3, 3, 5, 4, 5]):
            question["score"] = score
        return svc._Feedback.model_validate(data)

    def test_overall_score_is_proportional_to_the_visible_question_scores(self):
        feedback = self.feedback()
        self.assertEqual(svc.normalize_feedback_score(feedback).overall_score, 73)
        self.assertEqual(feedback.overall_score, 42)  # caller's data is not mutated
        for score in (1, 3, 5):
            with self.subTest(score=score):
                questions = [q.model_copy(update={"score": score}) for q in feedback.questions]
                self.assertEqual(svc.normalize_feedback_score(feedback.model_copy(update={"questions": questions})).overall_score,
                                 score * 20)

    def test_new_feedback_cannot_apply_a_separate_overall_penalty(self):
        snapshot = Snapshot.model_validate(load_fixture("application")["snapshot"])
        transcript = [TranscriptTurn.model_validate(t) for t in load_fixture("interview")["transcript"]]
        with patch.object(svc, "complete_json", return_value=self.feedback()):
            feedback = svc.make_feedback(snapshot, plan(), transcript, "en")
        self.assertEqual(feedback.overall_score, 73)
        self.assertEqual(len(feedback.questions), 6)

    def test_early_stop_and_followups_do_not_add_unanswered_questions_or_extra_weight(self):
        snapshot = Snapshot.model_validate(load_fixture("application")["snapshot"])
        transcript = [TranscriptTurn.model_validate(t) for t in load_fixture("interview")["transcript"][:4]]
        transcript.append(TranscriptTurn(role="candidate", content="More detail about my second answer.", question_id=2))
        feedback = self.feedback().model_copy(update={"questions": self.feedback().questions[:2]})
        with patch.object(svc, "complete_json", return_value=feedback):
            result = svc.make_feedback(snapshot, plan(), transcript, "en")
        self.assertEqual(result.overall_score, 50)
        self.assertEqual([q.question_id for q in result.questions], [1, 2])

    def test_missing_or_duplicate_question_scores_are_rejected(self):
        snapshot = Snapshot.model_validate(load_fixture("application")["snapshot"])
        transcript = [TranscriptTurn.model_validate(t) for t in load_fixture("interview")["transcript"]]
        original = self.feedback()
        for questions in (original.questions[:-1], original.questions[:-1] + [original.questions[0]]):
            with self.subTest(ids=[q.question_id for q in questions]), \
                 patch.object(svc, "complete_json", return_value=original.model_copy(update={"questions": questions})):
                with self.assertRaises(LLMError):
                    svc.make_feedback(snapshot, plan(), transcript, "en")


class VoiceEndpointTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.engine = create_engine(f"sqlite:///{self.directory.name}/voice.db",
                                    connect_args={"check_same_thread": False})
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(self.engine, expire_on_commit=False)
        application = load_fixture("application")
        recorded = load_fixture("interview")
        with self.factory.begin() as db:
            db.add(JobRow(**JobOut.model_validate(application["job"]).model_dump()))
            db.add(ApplicationRow(id=1, job_id=application["job_id"], status="applied", language="en",
                                  cv=application["cv"], cover_letter=application["cover_letter"],
                                  notes=application["notes"], snapshot=application["snapshot"]))
            db.add(InterviewRow(id=1, application_id=1, mode="voice", plan=recorded["plan"],
                                transcript=recorded["transcript"], feedback=recorded["feedback"]))

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

    def test_save_and_feedback_evaluate_all_six_actual_questions(self):
        mapping = model_map({i * 2: i + 1 for i in range(6)})
        feedback = svc._Feedback.model_validate(load_fixture("interview")["feedback"])
        with patch.object(svc, "complete_json", side_effect=[mapping, feedback]) as model:
            saved = self.client.post("/interview/1/voice-transcript", json={
                "transcript": [t.model_dump() for t in changed_topic_turns()],
            })
            self.assertEqual(saved.status_code, 200, saved.text)
            self.assertIsNone(saved.json()["feedback"])
            self.assertEqual(saved.json()["plan"][3]["question"], DOCKER_QUESTION)
            result = self.client.post("/interview/1/feedback")
            self.assertEqual(result.status_code, 200, result.text)
            self.assertEqual([q["question_id"] for q in result.json()["questions"]], [1, 2, 3, 4, 5, 6])
            self.assertEqual(result.json()["questions"][3]["question"], DOCKER_QUESTION)
            cached = self.client.post("/interview/1/feedback")
            self.assertEqual(cached.json(), result.json())
            self.assertEqual(model.call_count, 2)
        self.assertEqual(self.client.get("/interview/1").json()["feedback"], result.json())

    def test_cached_feedback_uses_the_same_formula_without_another_model_call(self):
        feedback = FeedbackConsistencyTests().feedback().model_dump(mode="json")
        with self.factory.begin() as db:
            db.get(InterviewRow, 1).feedback = feedback
        with patch.object(svc, "complete_json") as model:
            shown = self.client.get("/interview/1").json()["feedback"]
            returned = self.client.post("/interview/1/feedback").json()
        self.assertEqual(shown["overall_score"], 73)
        self.assertEqual(returned["overall_score"], 73)
        self.assertEqual(shown["questions"], returned["questions"])
        model.assert_not_called()

    def test_failed_alignment_leaves_the_saved_interview_and_feedback_untouched(self):
        before = self.client.get("/interview/1").json()
        for error in (LLMError("Invalid mapping"), OpenAIError("Provider unavailable")):
            with self.subTest(error=type(error).__name__), patch.object(svc, "complete_json", side_effect=error):
                response = self.client.post("/interview/1/voice-transcript", json={
                    "transcript": [t.model_dump() for t in changed_topic_turns()],
                })
            self.assertEqual(response.status_code, 502, response.text)
            self.assertEqual(self.client.get("/interview/1").json(), before)

    def test_empty_or_filler_only_answers_are_rejected_without_erasing_feedback(self):
        before = self.client.get("/interview/1").json()
        for turns in ([], [turn("candidate", "Um...")], [turn("candidate", "Please repeat the question.")]):
            response = self.client.post("/interview/1/voice-transcript", json={
                "transcript": [t.model_dump() for t in turns],
            })
            self.assertEqual(response.status_code, 422)
            self.assertEqual(self.client.get("/interview/1").json(), before)


if __name__ == "__main__":
    unittest.main()
