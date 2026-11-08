# JobbRadar

Web app + browser extension for people job hunting in Oslo. Built at the Oslo hackathon, 7–8 Nov 2026.

1. **Profile** – upload your CV (PDF) and anything else about you. JobbRadar turns it into a structured profile.
2. **Radar** – one click finds the recently published, still open jobs that fit you best, each with reasons, gaps and a "Norwegian probably required" badge.
3. **Apply** – pick a job: JobbRadar writes a tailored CV and cover letter that **never invent anything**
   (missing requirements are shown as gaps). You edit them, export a PDF and apply on the company's own site.
4. **Practise** – after "I applied", a mock interview unlocks, by **text or voice**, based on the job ad and on
   the exact documents you sent. At the end you get a score, strengths, what to improve and a stronger answer
   for every question you answered.

The **browser extension** saves any job page you find yourself into JobbRadar with one click.

Out of scope: login, automatic submission of applications, mobile app, scraping LinkedIn or Finn.no.
One demo user, no authentication; the demo runs locally on one laptop.

```
jobbradar/
├─ backend/     FastAPI + SQLite + DeepSeek (Python, uv)
├─ frontend/    React + Vite + TanStack Router (built with Lovable) — imported copy, see below
├─ extension/   Chrome/Opera extension (Manifest V3) that saves a job page into JobbRadar
└─ fixtures/    sample data = the official shape of every API response
```

## How it works

```
 Extension ──POST /jobs/import──┐
                                ▼
 Frontend (:8080) ◀── JSON ──▶ Backend FastAPI (:8000) ──▶ SQLite (radar.db)
                                   │        │
                                   │        ├──▶ DeepSeek (profile, ranking, CV, interview)
                                   │        └──▶ ElevenLabs (signed URL for the voice interview)
                                   ▼
                         Radar: one provider per source
                         NAV · Teamtailor · Greenhouse · Lever · Ashby
```

Flow: CV PDF → structured profile → Radar (scan without AI → filters → AI ranking of the best ~40) →
tailored application → **"I applied"** (a *snapshot* of the job ad and of the documents actually sent is saved) →
mock interview → feedback.

### Radar

- **One provider per source** in `backend/radar/providers/`, all with the same contract: they return normalised
  job ads. Adding a source = adding a file. Companies to follow are in `backend/radar/companies.yml`.
- **No AI while scanning**: providers use only public APIs and feeds, no login.
- **Filters before AI**: published in the last N days → location (Oslo area, Norway, remote; no location = passes)
  → keywords from the profile → deduplication → liveness (the ad is still open).
- **AI only at the end**: ranking of ~40 candidates in parallel groups of 10. Each result has a score 0–100, a
  verdict, up to 3 reasons, 3 gaps and 2 things to clarify. Few recent results → the window widens to 14, then 30 days.
- "Recent" means the **publication date** (`posted_at`), never when we found the ad. A source without a date shows
  "Date unknown" and goes last.
- For every ad we detect the language (no/en) and whether Norwegian is probably required: it becomes a badge and an
  "English-friendly only" filter.
- **NAV** is the official feed of Norwegian job ads (public token from `pam-stilling-feed.nav.no/api/publicToken`;
  it rotates, a 401 means "get a new one"). Only `ACTIVE` ads are kept; contact details of people are never stored.

### Mock interview

- **6 questions**: 1 intro, 2 behavioural (about the sent CV), 2 technical (about the ad), 1 motivation. A technical
  question becomes a "gap" question when the ad asks for something the CV does not show.
- **Text**: `POST /interview/{id}/start` → `/turn` for each answer → `/feedback`.
- **Voice**: ElevenLabs Agent. The backend creates a short-lived signed URL (the API key never reaches the
  browser); the frontend starts the call with the same 6 questions as dynamic variables; when the call ends the
  transcript is saved with `POST /interview/{id}/voice-transcript` and the feedback works exactly as in text mode.
  If the microphone is blocked or voice is unavailable, the user can always continue in text mode.
- **Feedback** evaluates only the questions that were answered (you can stop early) and never adds facts the
  candidate did not say.

## Rules for everyone (people, Claude Code, Lovable)

- **Never invent** experience, companies, dates, numbers, tools or certificates in the CV, the cover letter or the
  interview feedback. Missing requirements are shown as gaps, never claimed.
- Documents are in Norwegian only if the ad is in Norwegian **and** the candidate has Norwegian ≥ B2; otherwise English.
- Every call to DeepSeek goes through `backend/llm.py`, always with JSON output validated by Pydantic
  (on a validation error it retries with the error in the prompt).
- Secrets only in `backend/.env` (never committed, never in the frontend or the extension). The frontend and the
  extension talk only to our own backend.
- Every AI wait (10–30 s) must show in the UI what is happening. UI text is in English.
- Code, comments, commit messages and this README are in English.
- `backend/schemas.py` (Pydantic models) is the **contract** with the frontend. Whoever changes it, `models.py`,
  `frontend/src/api.ts`, `frontend/src/types.ts` or `fixtures/` tells the group. Real responses must have exactly
  the shape of the files in `fixtures/`; all JSON fields are `snake_case`.

## Quick start (everything on one machine)

You need [uv](https://docs.astral.sh/uv/) (installs Python 3.12 by itself) and Node.js 20+.

**1. Backend** (http://localhost:8000, API docs at `/docs`)
```bash
cd backend
uv sync                      # same .venv for everyone (from uv.lock)
cp .env.example .env         # then fill in the keys, see "Environment" below
uv run python scripts/scan.py --load-seed     # ~400 real Oslo-area jobs into your local DB
uv run uvicorn main:app --port 8000
```

**2. Frontend** (http://localhost:8080)
```bash
cd frontend
npm ci
printf 'VITE_USE_MOCKS=false\nVITE_API_URL=http://localhost:8000\n' > .env.local   # use the real backend
npm run dev
```
Without `.env.local` the frontend runs on mock data (`VITE_USE_MOCKS=true` in `.env`).
On Windows PowerShell, create `.env.local` with those two lines in any editor.

**3. Extension**: open `chrome://extensions` (or `opera://extensions`), enable Developer mode, "Load unpacked"
→ select the `extension/` folder. On a job page click the extension icon, then the save button: the job is
imported and opened in the app. The popup has two settings, Backend URL (default `http://localhost:8000`) and
App URL (default `http://localhost:8080`). It reads the page's JSON-LD `JobPosting` when present, otherwise the
visible text; emails and phone numbers are stripped.

The voice interview needs the microphone, which browsers allow only on `localhost`: run frontend and backend on
the same machine.

### Environment (`backend/.env`)

| Variable | What |
|---|---|
| `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL` | DeepSeek (OpenAI-compatible API) |
| `MODEL_SMART`, `MODEL_FAST` | `deepseek-v4-pro` (slow) and `deepseek-flash`; almost everything uses the fast one |
| `ELEVENLABS_API_KEY`, `ELEVENLABS_AGENT_ID` | only for the voice interview; without them voice returns a clear error and text still works |
| `DATABASE_URL` | default `sqlite:///./radar.db` |
| `FRONTEND_ORIGIN` | default `http://localhost:8080` |

Keys are passed privately, never in the group chat and never on GitHub.

## API

Errors are always `{ "error": "message" }`. Interactive docs: http://localhost:8000/docs.

| Method | Endpoint | What |
|---|---|---|
| GET / PUT | `/profile` | read / save profile and preferences |
| POST | `/profile/upload` | CV PDF + extra files + text → profile |
| POST | `/profile/answers` | answers to the questions about missing info |
| POST | `/radar` | `days` (3/7/14/30), `english_only`, `refresh` → the 15 best jobs with score, reasons, gaps |
| GET | `/jobs/{id}` | job + match + existing application |
| POST | `/jobs/import` | job captured by the extension (URL, text, JSON-LD) → `{job_id, created}` |
| GET / POST | `/applications` | list / create an application from a `job_id` (generates CV + cover letter) |
| GET / PATCH | `/applications/{id}` | read / save changes to CV, letter, status |
| POST | `/applications/{id}/applied` | mark as sent and save the snapshot |
| POST | `/interview/{id}/start` | `mode` text/voice → plan of 6 questions + first message |
| POST | `/interview/{id}/turn` | candidate's answer → next question (or closing message) |
| POST | `/interview/{id}/voice-transcript` | save the ElevenLabs call, mapped to the plan questions |
| POST | `/interview/{id}/feedback` | final evaluation (cached) |
| GET | `/interview/{id}` | the latest interview, to resume it |
| GET | `/voice/signed-url` | signed ElevenLabs URL |

Application status: `draft` when created → `applied` with "I applied" → `interviewing`, `rejected`, `offer`
changed by hand in the tracker. The interview unlocks from `applied` on.

Data lives in SQLite (`profiles`, `jobs`, `matches`, `applications`, `interviews`; see `backend/models.py`).
Every member has a local `radar.db`; `scan.py --load-seed` gives everybody the same jobs.

## Voice agent (ElevenLabs)

The agent is configured **from code**, not by hand in the ElevenLabs website:
```bash
cd backend
uv run python scripts/voice_agent.py --show   # only prints the current settings
uv run python scripts/voice_agent.py          # updates the agent (prompt, first message, turn settings)
```
The prompt is `INTERVIEW_VOICE_SYSTEM` in `backend/prompts.py`. The agent has authentication on (signed URLs only).

## Backend notes

- Sample profile (to work without uploading a CV): `uv run python scripts/load_fixture_profile.py`
- New library: `uv add <package>`, then commit `pyproject.toml` + `uv.lock` (tell the group).
- If you change a fixture: `uv run python scripts/check_fixtures.py`.
- Full path check A → B → C → D against the running backend: `uv run python scripts/e2e.py`
  (~1.5 min, uses `fixtures/sample_cv.pdf`; it writes to your DB, so never run it on the demo DB).
- Demo database: `uv run python scripts/reset_demo.py` (CV in `demo/`, gitignored) builds `backend/demo.db`;
  start the backend on it with `DATABASE_URL=sqlite:///./demo.db`.
- If the tables change (`models.py`): delete `backend/radar.db` and restart.
- Tests: `uv run python -m unittest discover -s . -p "test_*.py"` in `backend/`; frontend: `npm test` and
  `npm run build` in `frontend/`.

## Frontend: where to change it

`frontend/` is a copy of the Lovable repo
[andreamammano89-maker/JobbRadar](https://github.com/andreamammano89-maker/JobbRadar), imported with
`git subtree` (its history is kept). **Develop the frontend there** (Lovable or a branch of that repo), never
directly in `frontend/` here. The copy is updated by the merge captain with:
```bash
git remote add frontend https://github.com/andreamammano89-maker/JobbRadar.git   # once
git subtree pull --prefix=frontend frontend main
```
Running `npm run dev` or `npm run build` regenerates `frontend/src/routeTree.gen.ts` (line endings only):
**do not commit that change** (`git checkout -- frontend/src/routeTree.gen.ts`).

## Git

One branch per person (`git switch -c <name>`), kept up to date with `git pull --no-edit origin main`. Gabriele
merges into `main` of this repo, Andrea into the frontend repo. No force pushes. `backend/.env` is never committed.

## If something goes wrong

| Problem | What to do |
|---|---|
| NAV feed empty or token rejected | get a new token; otherwise `scan.py --load-seed` gives the saved real ads |
| Few English ads | the Radar widens to 14/30 days; the Norwegian badge is an insight in itself |
| AI slow | the fast model is the default; run the Radar before the demo |
| CV PDF unreadable | paste the CV text in the "more about you" field |
| Voice does not start | use text mode, always available; check the two `ELEVENLABS_*` keys and the microphone permission |
| Frontend page empty or errors | `VITE_API_URL` must be the backend address and the backend must be running |
| Weak Wi-Fi | phone hotspot + the backup video |

## Team

Gabriele (foundations, profile, tailored CV, merge captain) · Stefano (Radar) · Andrea (frontend, design) ·
Matilde (extension, "I applied", mock interview, voice).
