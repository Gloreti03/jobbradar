"""Prepare the DEMO database from scratch: jobs + demo profile + a first Radar run.

The demo uses its own database (backend/demo.db), so e2e tests and dev work never touch it.
The demo CV lives in demo/ at the repo root (gitignored: it is personal data).

Usage (from backend/):
    uv run python scripts/reset_demo.py              # jobs from data/seed_jobs.json
    uv run python scripts/reset_demo.py --scan       # fresh scan (Sunday morning), seed as fallback
    uv run python scripts/reset_demo.py --cv ../demo/other_cv.pdf

Then start the backend on the demo database:
    PowerShell:  $env:DATABASE_URL="sqlite:///./demo.db"; uv run uvicorn main:app --port 8000
    bash:        DATABASE_URL=sqlite:///./demo.db uv run uvicorn main:app --port 8000
"""

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
DEMO_DIR = BACKEND_DIR.parent / "demo"
DEMO_DB = BACKEND_DIR / "demo.db"

# must happen before importing config/db
os.environ["DATABASE_URL"] = "sqlite:///./demo.db"
sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient  # noqa: E402

from db import SessionLocal, init_db  # noqa: E402
from main import app  # noqa: E402
from radar.scanner import catalogue_stats, default_config, load_seed, scan  # noqa: E402
from services.profile_extract import extract_profile, pdf_to_text  # noqa: E402
from services.profile_store import save_profile  # noqa: E402


def find_cv(cv: Path | None) -> Path:
    if cv:
        return cv
    pdfs = sorted(DEMO_DIR.glob("*.pdf"))
    if len(pdfs) != 1:
        sys.exit(f"Put exactly one CV PDF in {DEMO_DIR} (found {len(pdfs)}) or pass --cv")
    return pdfs[0]


def extra_material() -> str:
    """Every .txt / .md in demo/ is used as extra material about the candidate."""
    parts = [f"--- {p.name} ---\n{p.read_text(encoding='utf-8').strip()}"
             for p in sorted(DEMO_DIR.glob("*")) if p.suffix in (".txt", ".md")]
    return "\n\n".join(parts)


def step(msg: str) -> float:
    print(f"\n== {msg}")
    return time.time()


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset the demo database")
    parser.add_argument("--cv", type=Path, help="CV PDF (default: the only PDF in demo/)")
    parser.add_argument("--scan", action="store_true", help="fresh scan of the sources instead of the seed")
    parser.add_argument("--days", type=int, default=7, choices=[3, 7, 14, 30], help="Radar window for the warm-up run")
    args = parser.parse_args()
    cv = find_cv(args.cv)

    t = step(f"Wiping {DEMO_DB.name}")
    DEMO_DB.unlink(missing_ok=True)
    init_db()

    t = step("Loading jobs")
    if args.scan:
        try:
            result = asyncio.run(scan(default_config(days=14)))
            print(f"   fresh scan: {result['active_unique_jobs']} active jobs")
        except Exception as err:  # network down at the venue -> seed
            print(f"   scan failed ({err}); falling back to the seed")
            load_seed()
    else:
        load_seed()
    stats = catalogue_stats()
    print(f"   {stats['active_unique_jobs']} active jobs | sources {stats['sources']} "
          f"| Norwegian required {stats['norwegian_required_percent']}%  ({time.time() - t:.1f}s)")

    t = step(f"Profile from {cv.name}")
    extra = extra_material()
    profile = extract_profile(pdf_to_text(cv.read_bytes()), extra)
    with SessionLocal() as db:
        save_profile(db, profile, extra)
    print(f"   {profile.name} | {profile.headline}")
    print(f"   languages {[(l.language, l.level) for l in profile.languages]} | {len(profile.search_terms)} search terms")
    print(f"   missing info: {profile.missing_info}  ({time.time() - t:.1f}s)")

    t = step(f"Warm-up Radar ({args.days} days)")
    with TestClient(app) as client:
        r = client.post("/radar", json={"days": args.days, "english_only": False, "refresh": False})
    if r.status_code != 200:
        sys.exit(f"   Radar failed: {r.status_code} {r.json()}")
    radar = r.json()
    print(f"   window {radar['days_requested']}->{radar['days_used']} | {radar['candidates_count']} candidates "
          f"| {len(radar['results'])} results  ({time.time() - t:.1f}s)")
    for res in radar["results"][:10]:
        job, match = res["job"], res["match"]
        flag = {True: "NO required", False: "English ok", None: "NO unknown"}[job["norwegian_required"]]
        print(f"   {match['score']:>3} {match['verdict']:<8} [{flag}] {job['title'][:60]} - {job['company']}")

    print(f"\nDemo database ready: {DEMO_DB}")
    print('Start the backend on it:  $env:DATABASE_URL="sqlite:///./demo.db"; uv run uvicorn main:app --port 8000')


if __name__ == "__main__":
    main()
