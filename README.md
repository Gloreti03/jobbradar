# JobbRadar

Web app + browser extension for people job hunting in Oslo: upload your CV, let the Radar find
recent jobs that fit you (with reasons and gaps), get a tailored CV and cover letter that never
invent anything, then practise with a mock interview (text or voice) based on what you sent.
The whole project is described in [BLUEPRINT.md](BLUEPRINT.md) (in Italian).

```
jobbradar/
├─ backend/     FastAPI + SQLite + DeepSeek (Python, uv)
├─ frontend/    React + Vite + TanStack (built with Lovable) — imported copy, see below
├─ extension/   Opera/Chrome extension (Manifest V3) that saves a job page into JobbRadar
└─ fixtures/    sample data = the official API shapes
```

## Quick start (everything on one machine)

You need [uv](https://docs.astral.sh/uv/) (installs Python 3.12 by itself) and Node.js 20+.

**1. Backend** (http://localhost:8000, docs at `/docs`)
```bash
cd backend
uv sync                      # same .venv for everyone (from uv.lock)
cp .env.example .env         # set DEEPSEEK_API_KEY (and ELEVENLABS_* for the voice interview)
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

**3. Extension**: in Opera/Chrome open `opera://extensions` (or `chrome://extensions`), enable
Developer mode, "Load unpacked" → select the `extension/` folder. On a job page, click
"JobbRadar – Save job": the job is imported and opened in the app.

The voice interview needs the microphone, which browsers allow only on `localhost`:
run frontend and backend on the same machine.

## Backend notes

- Sample profile (to work without uploading a CV): `uv run python scripts/load_fixture_profile.py`
- New library: `uv add <package>`, then commit `pyproject.toml` + `uv.lock` (tell the group).
- If you change a fixture: `uv run python scripts/check_fixtures.py`.
- Full path check A -> B -> C -> D against the running backend: `uv run python scripts/e2e.py`
  (~1.5 min, uses `fixtures/sample_cv.pdf`; it writes to your DB, so never run it on the demo DB).
- Demo database: `uv run python scripts/reset_demo.py` (CV in `demo/`, gitignored) builds
  `backend/demo.db`; start the backend on it with `DATABASE_URL=sqlite:///./demo.db`.
- If the tables change (`models.py`): delete `backend/radar.db` and restart.

## Frontend: where to change it

`frontend/` is a copy of the Lovable repo
[andreamammano89-maker/JobbRadar](https://github.com/andreamammano89-maker/JobbRadar), imported with
`git subtree` (its history is kept). **Develop the frontend there** (Lovable or a branch of that repo),
never directly in `frontend/` here. The copy is updated by the merge captain with:
```bash
git remote add frontend https://github.com/andreamammano89-maker/JobbRadar.git   # once
git subtree pull --prefix=frontend frontend main
```
Running `npm run dev` may regenerate `frontend/src/routeTree.gen.ts`: do not commit that change.

## Git

One branch per person (`git switch -c <name>`), kept up to date with `git pull origin main`.
Gabriele merges into `main`.

## Language

Code, comments, docstrings, commit messages and this README are in English.
Only `BLUEPRINT.md` stays in Italian.
