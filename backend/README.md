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

### Document uploads

Sign in and open the application document checker on the Punjab or Haryana
old-age pension scheme page. Select an evidence type, give consent, and upload
a PDF, PNG, or JPEG. The API accepts up to 8 MB per file and five PDF pages.
It reads labeled fields from a PDF text layer or uses local RapidOCR for scanned
pages and photos. For Hindi or Punjabi scans, select Hindi, Punjabi, or the
mixed-language option. Install Tesseract with the eng, hin, and pan language
packs on the backend host. Use TESSERACT_CMD if it is not on PATH and
TESSDATA_PREFIX if the language files are in a separate directory. The checker
recognizes common field labels across the three languages. Nearby transliterations
of names are flagged for review, and common place names are normalized for comparison.
Review the suggested fields against the original and fill in any fields the
reader missed before running the check.

Install the dependencies in `requirements.txt` and restart the API after
upgrading. One-off uploads are processed in memory. The check report omits submitted
field values.

To save a file, open Document Mismatch Checker → Saved documents and select a specific document
type. Set DOCUMENT_STORAGE_KEY in backend/.env to enable encrypted MongoDB
storage. Generate a Fernet key using the command in .env.example and keep the
key in a secret store or the local environment. Aadhaar storage requires a
masked copy. Saved files can be downloaded or deleted. To compare saved files, select them explicitly in the checker.


### Document correction guides

After a cross-document mismatch, open **How to Fix This Mismatch?** in the
scheme report. Confirm each document type and whether an issuing authority
has established one value as correct. The detailed pilot covers Aadhaar and
birth certificate date-of-birth corrections. Other document and field pairs
receive general instructions for contacting their issuers.

Set GEMINI_API_KEY on the backend to enable Gemini personalization.
GEMINI_RESOLUTION_MODEL overrides the default Gemini model. Set OPENAI_API_KEY
instead if you want to use OpenAI.
DOCUMENT_RESOLUTION_MODEL optionally selects a model that supports strict
structured output on the OpenAI Responses API. The official guidance is still
available without the key. With the user's consent the provider receives
document types, field, date difference in days when applicable, scheme and
jurisdiction, and the user's confirmation status. It does not receive the
documents, original values, identifiers or account credentials. The guide is
generated on request and is not saved to the user's account.



# Optional OCR.space Engine 3

Set `OCR_SPACE_API_KEY` in `backend/.env` and restart the backend.
In Document Checker, select **Use OCR.space Engine 3 for difficult scans**.
For an already-read document, use **Read again with OCR.space**.
The backend sends a rendered image per page to OCR.space only when opted in.
The default reader runs locally.

## Cloudinary document storage

Set `CLOUDINARY_URL` in `backend/.env` using your Cloudinary API Environment
Variable from the Cloudinary console, then restart the backend. Set
`DOCUMENT_STORAGE_PROVIDER=cloudinary` to require Cloudinary for new uploads
even when credentials are missing. Keep the existing `DOCUMENT_STORAGE_KEY`
to preserve access to saved documents.

New uploads are encrypted by the backend and sent as authenticated raw assets.
MongoDB keeps ownership and file metadata. Existing MongoDB documents remain
available in the same account. Downloads, OCR and deletion still use the app's
authenticated endpoints.
## Scheme alerts

Signed-in users can verify their registered email and opt in under
**Account → Scheme alerts**. Set `BREVO_API_KEY` and
`NOTIFICATION_EMAIL_FROM` using a sender verified in Brevo.
The demo inbox previews the same matching rules without provider credentials.

Set `NOTIFICATION_APP_URL` to the public frontend origin. Add independently
confirmed application closing dates to `SCHEME_NOTIFICATION_DEADLINES` as a
JSON object mapping catalogue scheme IDs to ISO dates (YYYY-MM-DD). Update
this setting when an official deadline changes. Free-form catalogue notes
are skipped for deadline alerts.

Set `SCHEME_NOTIFICATIONS_ENABLED=true` and restart the backend. It checks at
startup and hourly thereafter, using India dates and the same eligibility
rules as the results page. It sends one alert for the first likely match
per account and scheme, and one reminder per closing date within
seven days. Existing matches qualify for the first scan after opt-in.
Delivery claims in MongoDB suppress duplicates across workers. An uncertain
provider result is retained as `unconfirmed` for operator review.
