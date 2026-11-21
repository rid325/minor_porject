# Scheme Seva prototype API

This is the backend for the government scheme eligibility prototype. When
MongoDB is configured, `SchemeRepository` loads scheme documents from the
`schemes` collection. Without MongoDB, it falls back to the canonical workbook
or checked-in JSON seed.

The importer `backend/scripts/import_scheme_workbook.py` generates the local
normalized seed. `backend/scripts/import_scheme_workbook_to_mongo.py` upserts
the canonical 75 schemes and their linked application-guide, ready-to-apply,
resolution, source, document, and application-route data into Atlas. It also
stores register metrics, category coverage, and the workbook field guide in
`register_metadata`. The importer updates matching scheme IDs and does not
delete other records.

Profiles and sessions are stored separately from the scheme repository. A later
phase can replace `SchemeRepository` with PostgreSQL without changing the HTTP
contract.

Email/password accounts and seven-day browser sessions use MongoDB Atlas.
Applicant questionnaire answers are saved per account in the `profiles`
collection and can be edited from the profile page. The API only returns a
profile to the account that owns it. Profiles are separate from scheme records.

### Configure MongoDB Atlas authentication

1. Create an Atlas cluster and a database user with access to the application
   database. In Network Access, allow the backend host's IP address.
2. Copy `backend/.env.example` to `backend/.env` and set `MONGODB_URI` to the
   Atlas connection string. Keep the `.env` file private; it is ignored by Git.
3. Set `MONGODB_DATABASE` if you want a database name other than
   `yojna_connect`.
4. Start the API. `GET /api/v1/health` reports `database_status` as
   `connected`, `unavailable`, or `not_configured`.
5. Import or refresh the workbook data with
   `python backend/scripts/import_scheme_workbook_to_mongo.py`. The default
   workbook path comes from `SCHEME_WORKBOOK_PATH`; pass `--workbook` to select
   another file.

Authentication endpoints are `POST /api/v1/auth/signup`,
`POST /api/v1/auth/login`, `GET /api/v1/auth/me`, and
`POST /api/v1/auth/logout`. Signed-in profile endpoints are
`GET /api/v1/auth/profile` and `PUT /api/v1/auth/profile`. Signup collects
only email and password. Passwords
are stored as scrypt hashes; random session tokens are stored only as hashes
and returned to the browser in an HTTP-only cookie. Signed-in users can change
their password through `POST /api/v1/auth/change-password`. Local development uses
`AUTH_COOKIE_SECURE=false`; set it to `true` when serving over HTTPS.

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

If MongoDB is unavailable, the API tries the workbook at `SCHEME_WORKBOOK_PATH`
and then `backend/data/schemes.seed.json`. If neither catalogue source is
available, it uses an empty fallback so health and deployment diagnostics
remain available.

## Endpoints

- `GET /api/v1/health`
- `GET /api/v1/schemes`
- `GET /api/v1/schemes/{scheme_id}`
- `GET /api/v1/profile/schema`
- `POST /api/v1/eligibility/check`
- `POST /api/v1/auth/signup`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `POST /api/v1/auth/logout`

The eligibility endpoint accepts the preferred body shape
`{"profile": { ... }}` and also accepts profile sections directly at the top
level. A profile can optionally include `scheme_ids` to evaluate only selected
schemes. Unknown answers are returned as `needs_more_information`; schemes
without reviewed deterministic rules remain `information_only`.
