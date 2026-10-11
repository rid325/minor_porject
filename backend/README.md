# Scheme Seva prototype API

This is the first backend slice for the government scheme eligibility
prototype. It is intentionally small and uses an in-memory repository loaded
from the canonical workbook at:

`outputs/scheme_research_register.xlsx`

The repeatable, dependency-free importer at
`backend/scripts/import_scheme_workbook.py` generates the normalized seed at
`backend/data/schemes.seed.json`. Run
`python3 backend/scripts/import_scheme_workbook.py --check` after changing the
workbook to verify all 75 IDs and the 28/24/23 readiness split. The current API
repository remains workbook-backed; the seed is ready for a later database or
packaged-data loader.

No profile data is written to the repository or a database. A later phase can
replace `SchemeRepository` with PostgreSQL without changing the HTTP contract.

## Run locally

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

From the repository root, the equivalent command is
`uvicorn backend.app.main:app --reload`.

The API is then available at `http://127.0.0.1:8000`; interactive docs are at
`/docs`.

If the workbook is mounted somewhere else, set `SCHEME_WORKBOOK_PATH` to its
absolute path before starting the server. Without the workbook the API still
boots from `backend/data/schemes.seed.json` when that checked-in seed is
available. If neither catalogue artifact is present, it uses an empty fallback
so health and deployment diagnostics remain available.

## Endpoints

- `GET /api/v1/health`
- `GET /api/v1/schemes`
- `GET /api/v1/schemes/{scheme_id}`
- `GET /api/v1/profile/schema`
- `POST /api/v1/eligibility/check`

The eligibility endpoint accepts the preferred body shape
`{"profile": { ... }}` and also accepts profile sections directly at the top
level. A profile can optionally include `scheme_ids` to evaluate only selected
schemes. Unknown answers are returned as `needs_more_information`; schemes
without reviewed deterministic rules remain `information_only`.
