# PITCHIQ — Football Analytics & Performance Intelligence

PITCHIQ is a football analytics application built around the supplied 2025–26 player statistics CSV and original Software Laboratory notebook. The existing Obsidian interface, electric lime accent, 3D football hero, and React/FastAPI stack remain in place.

## Stack and project layout

- Frontend: React, TypeScript, Vite, Tailwind CSS, React Router, Recharts, Framer Motion, GSAP, Three.js, Lucide React
- Backend: FastAPI, Pandas, NumPy, Matplotlib (Agg), Seaborn
- Dataset: `backend/data/players_data_light-2025_2026.csv`
- Original notebook: `FootballStats_Final_Submission/FootballStats_Final.ipynb` (retained)
- Backend tests: `backend/tests/`
- Frontend tests: `frontend/src/App.test.tsx`

## Run locally

### Backend

```bash
cd backend
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

The API is available at `http://localhost:8000`. Interactive docs are enabled in development at `/docs` and hidden when `PITCHIQ_ENV=production`.

Run backend tests from `backend/`:

```bash
python -m pytest
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The Vite server proxies `/api` to `http://localhost:8000` for local development. Set `VITE_API_BASE_URL` in the frontend environment when the API is hosted at a different origin. `PITCHIQ_CORS_ORIGINS` is a comma-separated list of permitted browser origins; its local default is `http://localhost:5173,http://127.0.0.1:5173`.

Run frontend tests and create a production build from `frontend/`:

```bash
npm test
npm run build
```

## API overview

- `GET /api/health` — dataset status and dimensions
- `GET /api/overview` — season summary
- `GET /api/filters` — valid squads, positions, and competitions
- `GET /api/player-options` — compact stable-ID player list for complete comparison selection
- `GET /api/players` — filterable/sortable/paginated player records
- `GET /api/players/{rank}` — one record by stable source `Rk`
- `GET /api/teams` — squad sums from player rows, with methodology disclaimer
- `GET /api/compare?ids=1,2` — compare 1–4 distinct source record IDs
- `GET /api/leaderboards` — per-90 or shooting-accuracy ranking, default minutes floor 450
- `GET /api/analysis/correlation` — Pearson correlation matrix with unavailable values as null
- `GET /api/analysis/positions` — first-listed source position grouping
- `GET /api/analysis/competitions` — player-record competition summaries
- `GET /api/quality` — missing values and duplicate checks
- `GET /api/export/players` — CSV export with active player filters and spreadsheet-formula protection

`/api/players` accepts `search`, `squad`, `position`, `competition`, `min_minutes`, `sort_by`, `order`, `limit` (1–500), and `offset` (non-negative). Invalid sort keys and query parameters return HTTP 422. Search treats the query as plain text.

The existing `/api/teams` and `/api/analysis/positions` routes keep their original array response shape. Each returned row includes a `methodology` field so consumers can show the aggregation caveat without a response-wrapper change.

## Data methodology and limitations

- Goals per 90 = goals × 90 / minutes. Assists per 90 = assists × 90 / minutes. Goal contributions per 90 = (goals + assists) × 90 / minutes. These values remain null when source inputs are absent or minutes are not positive.
- The default per-90 ranking floor is 450 minutes. It can be changed on the Players page and is shown alongside the leaderboard. It limits small-sample distortion; it does not change the raw record or the underlying dataset.
- Shooting accuracy uses the source `SoT%` field when valid. This is shots on target divided by shots, not goals divided by shots. Rows with an unavailable source percentage stay unavailable.
- The supplied file contains 2,839 player records, 96 squads, and five competitions. The source has no duplicate `Rk` IDs or exact duplicate rows. Missing ages and goalkeeper-only observations are retained as null. Invalid numeric strings are coerced to null; impossible ages, negative minutes, and negative counting statistics are treated as invalid observations.
- Goals, assists, minutes, and shots shown at squad or competition level are sums of supplied player rows. They are descriptive dataset aggregates, not independently verified official club or competition totals. Player-level goalkeeper `GA` and saves are not summed as team defense metrics.
- Position analysis groups each record under the first-listed source position. The full multi-position string remains available for player discovery and should not be read as an exclusive capability label.
- Pearson correlation measures linear association. Correlation does not imply causation; no statistical significance is calculated. Constant or insufficient data pairs remain null.

## Production deployment preparation

The repository contains deployment configuration, but this project has **not** been pushed or deployed. No API credentials are needed.

### Vercel frontend

- Set the Vercel project **Root Directory** to `frontend`.
- The checked-in `frontend/vercel.json` sets `npm ci`, `npm run build`, `dist`, and the React Router SPA fallback.
- Add `VITE_API_BASE_URL=https://<your-render-service>.onrender.com` in Vercel's Production (and Preview, if used) environment settings. Production builds now fail clearly if this is missing. Vite embeds this public API URL into the build, so changing it requires a new frontend build.
- `frontend/.env.example` shows the variable's expected format. The API URL is public configuration, not a secret.

### Render backend

- `render.yaml` describes a Python web service rooted at `backend`, installs `requirements.txt`, runs `bash start.sh`, and checks `/api/v2/health`.
- Set `PITCHIQ_CORS_ORIGINS` in Render to the exact Vercel production origin (and any preview/custom origins that should be allowed). Use comma-separated origins without paths or a wildcard.
- `PITCHIQ_ENV=production` disables the interactive FastAPI docs. Render provides `PORT`; the start script binds Uvicorn to `0.0.0.0:$PORT` without development reload.
- `backend/.env.example` documents the production variables. It contains placeholders only.

### SQLite persistence and first start

- Configure `PITCHIQ_DATABASE_PATH=/var/data/pitchiq_v2.sqlite3`; `render.yaml` mounts the Render persistent disk at `/var/data`.
- On startup, `backend/start.sh` runs `app.ingestion.bootstrap`: it applies migrations and imports the bundled tracked CSV only when the database contains no player-stat records. Existing data is left in place.
- The seed inputs required by both APIs are tracked under `backend/data/`: `players_data_light-2025_2026.csv`, `source_data_with_derived_metrics.csv`, and `player_master.csv`. SQLite files, generated import reports, caches, and local exports are excluded by `.gitignore` and can be regenerated from those source files.
- Render persistent disks require a paid web-service instance. A disk is available at runtime, not in build/pre-deploy commands; it also limits the service to one instance and causes a short interruption on redeploy. These constraints fit this small single-instance SQLite application. Keep regular off-service backups using the CLI backup command below.

To start the backend locally (the default database path is `backend/data/pitchiq_v2.sqlite3`):

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
bash start.sh
```

The first start initializes the database from the bundled source CSVs. Run backend tests with `python -m pytest -q` from `backend/`.

For Vercel, set the API URL in the project settings before building. To build locally against a chosen API URL:

```bash
cd frontend
npm ci
VITE_API_BASE_URL=https://<your-render-service>.onrender.com npm run build
```

For local Vite development, leave `VITE_API_BASE_URL` unset to use the existing `/api` proxy to `http://localhost:8000`; start Vite with `npm run dev` in `frontend/`.

## PITCHIQ v2 database workspace

PITCHIQ v2 adds a normalized, source-aware SQLite database and a separate `/api/v2` API while keeping the original CSV-backed `/api/*` routes and v1 pages available. Open **Database v2** in the top navigation to use canonical player discovery, profiles, club/competition/season directories, comparison, leaderboards, shooting, Data Lab, and coverage views.

The initial v2 scope is the supplied 2025–26 dataset only: 2,839 player-stat records, 2,690 source-local player identities, 96 clubs, and five competition labels. It is not a global database. The dataset's license/redistribution terms have not been verified. No external football provider is connected, and unsupported fields such as xG/xA and passing totals are not fabricated or shown.

### Initialize and import v2 data

From the repository root:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m app.ingestion.cli inspect --file data/source_data_with_derived_metrics.csv
python -m app.ingestion.cli validate --file data/source_data_with_derived_metrics.csv
python -m app.ingestion.cli preview --file data/source_data_with_derived_metrics.csv
python -m app.ingestion.cli init
python -m app.ingestion.cli import --file data/source_data_with_derived_metrics.csv --json
```

Windows PowerShell activation: `.venv\Scripts\Activate.ps1`. The v2 database defaults to `backend/data/pitchiq_v2.sqlite3`; override it with `PITCHIQ_DATABASE_PATH`. The v1 starter databases remain separate. Imports retain missing data as null, record source checksums/provenance, reject invalid rows with a report, and are idempotent for the same release.

For production, configure `PITCHIQ_ENV=production` and `PITCHIQ_CORS_ORIGINS` as a comma-separated allowlist of exact frontend origins. Keep the SQLite database and backups outside public static hosting.

### Start the backend and frontend

Backend, from `backend/` with its virtual environment activated:

```bash
uvicorn app.main:app --reload --port 8000
```

Frontend, in a second terminal from `frontend/`:

```bash
npm ci
npm run dev
```

The Vite development server runs at `http://localhost:5173` and proxies `/api` to `http://localhost:8000`. The v2 health endpoint is `http://localhost:8000/api/v2/health`.

### Tests and production build

```bash
cd backend
python -m pytest -q
```

```bash
cd frontend
npm test
npm run build
```

The production build currently succeeds with a Vite advisory that the Three.js chunk is larger than 500 kB minified.

### Backup and recovery

Create a consistent SQLite online backup from `backend/`:

```bash
python -m app.ingestion.cli --database data/pitchiq_v2.sqlite3 backup --output /safe/path/pitchiq-v2-backup.sqlite3
```

To recover, stop the backend, preserve the current database file for investigation, restore the selected backup to the configured database path, restart the backend, and verify `PRAGMA integrity_check`, `PRAGMA foreign_key_check`, and `/api/v2/health`. Migrations are forward-only; restoring a backup is the documented recovery path.

### v2 API and methodology documentation

The v2 API routes and typed request/response models are maintained in `backend/app/api_v2.py` and `backend/app/v2_schemas.py`; the versioned database schema is in `backend/app/migrations/`. `G+A-PK` is a per-90 source field; the normalized non-penalty contribution count is `G-PK + Ast`. Club and competition totals are dataset player-record aggregates, not verified official totals.
