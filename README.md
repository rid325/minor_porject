# Government Scheme Eligibility Prototype

This repository contains the first working prototype described in
`IMPLEMENTATION_PLAN_BASIC_SCHEME_PROTOTYPE.md`.

It includes:

- A catalogue of all 75 researched schemes.
- Search and filters by location, category, and application-readiness status.
- Scheme detail pages with benefits, eligibility text, documents, application routes, sources, and cautions.
- A multi-section profile form stored locally in the browser.
- Deterministic eligibility results grouped into likely eligible, needs more information, likely not eligible, and information only.
- Reviewed rule coverage for a representative 15-scheme pilot. Other schemes remain visible but are marked information only until their criteria are reviewed and encoded.

## Start the backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

The API is available at `http://127.0.0.1:8000`. Interactive documentation is
at `http://127.0.0.1:8000/docs`.

## Start the frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

The frontend works with the FastAPI API when it is running. If the API is not
available, it uses the checked-in local catalogue and a clearly simplified
offline eligibility preview so the UI can still be demonstrated.

If the backend is running on another port, create `frontend/.env.local`:

```bash
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8002
```

## Verify the scheme data

From the repository root:

```bash
backend/.venv/bin/python backend/scripts/import_scheme_workbook.py --check
backend/.venv/bin/pytest -q
```

The importer validates 75 unique scheme IDs and the expected readiness totals:
28 `YES`, 24 `CONDITIONAL`, and 23 `NO`.

## Main routes

- `/` — landing page
- `/schemes` — full catalogue
- `/schemes/[id]` — scheme detail
- `/profile` — profile form
- `/results` — eligibility results

This is a pre-screening tool. It does not authenticate documents, submit an
application, or guarantee a government decision.
