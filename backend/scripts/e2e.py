"""End-to-end check of the full path A -> B -> C -> D against a RUNNING backend.

Usage (from backend/, with the backend running on :8000):
    uv run python scripts/e2e.py                        # uses fixtures/sample_cv.pdf
    uv run python scripts/e2e.py --cv path/to/cv.pdf --api http://localhost:8000

WARNING: it writes to the database the backend is using (replaces the profile,
creates an application and an interview). Do not run it on the demo database.

Exit code 0 = every step passed; 1 = something failed (details printed).
About 8-10 DeepSeek calls (fast model), ~1.5 minutes.
"""

import argparse
import sys
import time
from pathlib import Path

import httpx

REPO_DIR = Path(__file__).resolve().parents[2]
DEFAULT_CV = REPO_DIR / "fixtures" / "sample_cv.pdf"

# BLUEPRINT time budgets (seconds)
LIMITS = {"A upload CV": 30, "B radar": 25, "C application": 30}

ANSWERS = [
    "I'm a developer who moved to Oslo. I have built backend services and I'm looking for my next role here.",
    "In my last job I built and maintained APIs used every day by many users, and I wrote tests for them.",
    "I prepared the change carefully, tested it before switching and checked the results afterwards.",
    "I would start from clear requirements, write tests, and keep the setup reproducible with Docker.",
    "I haven't used that yet, but I learn quickly: I picked up new frameworks on my own for side projects.",
    "I like what the team builds and I want to grow in a company where I can learn from experienced people.",
]


class E2E:
    def __init__(self, api: str):
        self.client = httpx.Client(base_url=api, timeout=180)
        self.rows: list[tuple[str, bool, float, str]] = []

    def call(self, name: str, method: str, path: str, expect: int | None = None, **kw):
        start = time.time()
        try:
            r = self.client.request(method, path, **kw)
            body = r.json()
            ok = r.status_code == expect if expect else r.is_success
            note = "" if ok else f"HTTP {r.status_code}: {body.get('error', body) if isinstance(body, dict) else body}"
        except (httpx.HTTPError, ValueError) as err:
            body, ok, note = None, False, f"{type(err).__name__}: {err}"
        elapsed = time.time() - start
        limit = LIMITS.get(name)
        if ok and limit and elapsed > limit:
            note = f"slow: {elapsed:.1f}s > {limit}s"
        self.rows.append((name, ok, elapsed, note))
        print(f"[{'OK ' if ok else 'ERR'}] {name:<28} {elapsed:6.1f}s  {note}")
        return ok, body

    def check(self, name: str, condition: bool, note: str = ""):
        self.rows.append((name, condition, 0.0, "" if condition else note))
        print(f"[{'OK ' if condition else 'ERR'}] {name:<28} {'':>7}  {'' if condition else note}")
        return condition

    def summary(self) -> int:
        failed = [r for r in self.rows if not r[1]]
        slow = [r for r in self.rows if r[1] and r[3].startswith("slow")]
        print(f"\n{len(self.rows) - len(failed)}/{len(self.rows)} checks passed", end="")
        print(f", {len(slow)} over the time budget" if slow else "")
        for name, _, _, note in failed:
            print(f"  FAILED {name}: {note}")
        return 1 if failed else 0


def run(api: str, cv: Path) -> int:
    t = E2E(api)
    ok, _ = t.call("health", "GET", "/health")
    if not ok:
        print(f"Backend not reachable at {api}: start it with `uv run uvicorn main:app --port 8000`")
        return 1

    # A — profile
    ok, prof = t.call("A upload CV", "POST", "/profile/upload",
                      files={"cv": (cv.name, cv.read_bytes(), "application/pdf")},
                      data={"extra_text": "EU citizen, I can work in Norway. Looking for roles in Oslo."})
    if not ok:
        return t.summary()
    profile = prof["profile"]
    t.check("A profile has data", bool(profile["name"] and profile["experiences"] and profile["search_terms"]),
            "name, experiences or search_terms empty")
    if profile["missing_info"]:
        question = profile["missing_info"][0]
        ok, upd = t.call("A answer missing info", "POST", "/profile/answers",
                         json={"answers": [{"question": question, "answer": "Full-time, from January 2027."}]})
        if ok:
            t.check("A answered question removed", question not in upd["profile"]["missing_info"], "still in missing_info")

    # B — radar
    ok, radar = t.call("B radar", "POST", "/radar", json={"days": 7, "english_only": False, "refresh": False})
    if not ok:
        return t.summary()
    results = radar["results"]
    if not t.check("B radar has results", bool(results), f"0 results ({radar['candidates_count']} candidates)"):
        return t.summary()
    scores = [r["match"]["score"] for r in results]
    t.check("B sorted by score", scores == sorted(scores, reverse=True), f"scores {scores}")
    print(f"      {radar['candidates_count']} candidates, top: {results[0]['match']['score']} "
          f"{results[0]['job']['title'][:60]} - {results[0]['job']['company']}")
    job_id = results[0]["job"]["id"]
    ok, detail = t.call("B job detail", "GET", f"/jobs/{job_id}")
    if ok:
        t.check("B job detail has match", detail["match"] is not None, "match is null")

    # C — application
    ok, app = t.call("C application", "POST", "/applications", json={"job_id": job_id})
    if not ok:
        return t.summary()
    aid = app["id"]
    t.check("C draft with documents", app["status"] == "draft" and len(app["cover_letter"].split()) > 50
            and bool(app["cv"]["experiences"]), "not draft, short letter or empty CV")
    t.check("C missing requirements <= 6", len(app["notes"]["missing_requirements"]) <= 6,
            f"{len(app['notes']['missing_requirements'])} items")
    t.check("C CV identity from profile", app["cv"]["name"] == profile["name"], "name differs from profile")
    t.call("C edit letter", "PATCH", f"/applications/{aid}", json={"cover_letter": app["cover_letter"]})
    t.call("D interview locked", "POST", f"/interview/{aid}/start", expect=409, json={"mode": "text"})

    # D — applied + interview
    ok, applied = t.call("D I applied", "POST", f"/applications/{aid}/applied")
    if ok:
        t.check("D snapshot of this job", bool(applied["snapshot"]) and applied["snapshot"]["job"]["id"] == job_id,
                "snapshot missing or of another job (stub?)")
    ok, start = t.call("D interview start", "POST", f"/interview/{aid}/start", json={"mode": "text"})
    if not ok:
        return t.summary()
    t.check("D plan has 6 questions", len(start["plan"]) == 6, f"{len(start['plan'])} questions")
    done = False
    for i, answer in enumerate(ANSWERS, 1):
        ok, turn = t.call(f"D turn {i}", "POST", f"/interview/{aid}/turn", json={"answer": answer})
        if not ok:
            break
        done = turn["done"]
        if done:
            break
    t.check("D interview finished", done, "done never became true")
    ok, fb = t.call("D feedback", "POST", f"/interview/{aid}/feedback")
    if ok:
        t.check("D feedback per question", len(fb["questions"]) == 6, f"{len(fb['questions'])} questions")
        empty = [q["question_id"] for q in fb["questions"] if len(q["better_answer"].strip()) < 20]
        t.check("D better answers filled", not empty, f"empty/too short better_answer for {empty}")

    ok, apps = t.call("tracker list", "GET", "/applications")
    if ok:
        status = next((a["status"] for a in apps if a["id"] == aid), None)
        t.check("tracker shows applied", status == "applied", f"status {status}")
    return t.summary()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--cv", type=Path, default=DEFAULT_CV)
    args = parser.parse_args()
    if not args.cv.exists():
        sys.exit(f"CV not found: {args.cv}")
    sys.exit(run(args.api, args.cv))
