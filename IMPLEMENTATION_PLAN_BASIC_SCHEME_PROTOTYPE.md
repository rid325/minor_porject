# Implementation Plan: Basic Government Scheme Eligibility Prototype

## 1. Prototype objective

Build a simple web application where a person can:

1. Browse the complete catalogue of 75 researched schemes.
2. Enter the personal, household, education, employment, income, and location information that affects scheme eligibility.
3. Run a deterministic eligibility check.
4. See schemes grouped into:
   - **Likely eligible to explore**
   - **Needs more information**
   - **Likely not eligible**
   - **Information only**, when the scheme rules or application route are not sufficiently verified
5. Understand exactly why every scheme received its result and where to apply.

This is a pre-screening prototype. It does not approve applications or guarantee selection.

## 2. Core scope decision

The catalogue will contain all 75 schemes from `outputs/scheme_research_register.xlsx`.

The existing workbook records:

- 28 schemes with an application-readiness status of `Yes`
- 24 schemes with an application-readiness status of `Conditional`
- 23 schemes with an application-readiness status of `No`

Application readiness is not the same as user eligibility. These two concepts must remain separate.

Every scheme can be browsed from the first version. A scheme can receive a confident eligibility result only after its eligibility conditions have been converted from narrative text into reviewed machine-readable rules. Unresolved schemes remain visible as `Information only` or `Needs more information`.

## 3. What the first prototype will include

### 3.1 Scheme catalogue

- All 75 schemes imported from the canonical `Scheme Data` worksheet.
- Search by scheme name and description.
- Filters for jurisdiction, category, target group, benefit type, and application readiness.
- Scheme detail page containing:
  - Scheme name and summary
  - Benefit
  - Eligibility description
  - Documents to prepare
  - Application channel and link
  - Application steps
  - Important cautions
  - Official source URLs
  - Last-checked date
  - Research-readiness status

### 3.2 User profile form

The form will be divided into sections instead of one very long page:

1. **Location**
   - State or Union Territory
   - District
   - Rural or urban residence
   - Domicile status, when relevant

2. **Personal details**
   - Date of birth, with age derived by the server
   - Gender only where a scheme requires it
   - Marital, widow, orphan, or dependent status where relevant
   - Disability status and percentage where relevant

3. **Household and income**
   - Household size
   - Applicant income
   - Household or family income
   - Income period and currency unit
   - BPL, ration-card, PPP, or other scheme-relevant household status

4. **Education**
   - Student status
   - Study level and course
   - Institution type or approval status where required

5. **Employment and occupation**
   - Employment status
   - Occupation or worker category
   - Worker-registration status
   - Self-employed, enterprise, or new-business status

6. **Agriculture and assets**
   - Farmer status
   - Landholding or cultivable-land status
   - Housing or other asset conditions used by included schemes

7. **Social and scheme-specific conditions**
   - Social category only where required for matching
   - Existing government-benefit membership
   - Required registration or database inclusion

Each answer supports `Known value`, `I do not know`, and `Prefer not to say` where appropriate. Blank, unknown, zero, and no must never be treated as the same value.

The prototype will not request Aadhaar numbers, bank-account numbers, OTPs, document images, or other identifiers that are unnecessary for pre-screening.

### 3.3 Eligibility results

Each scheme result will show:

- Overall result category
- Conditions that passed
- Conditions that failed
- Missing answers
- Conditions that require an external or departmental check
- Application-readiness warning
- Official source and last-checked date
- Application link or assisted/offline application route

Unknown information must produce `Needs more information`, not automatic rejection.

## 4. Explicitly out of scope for this prototype

- Natural-language chatbot
- RAG or vector database
- OCR and document checking
- Document uploads
- Automatic government-portal submission
- User accounts and authentication
- Permanent server-side storage of personal profiles
- Approval prediction
- Live scraping during a user request
- Automatic conversion of free-text eligibility into rules

These features can be added after the catalogue and deterministic filtering flow is proven.

## 5. Recommended technology stack

| Layer | Choice | Reason |
|---|---|---|
| Frontend | Next.js, React, TypeScript | Fast responsive interface, good form support, and straightforward deployment |
| Backend | Python, FastAPI, Pydantic | Typed profile validation and easy implementation of deterministic rules |
| Database | PostgreSQL | Reliable relational data, JSONB rule storage, migrations, and source/version history |
| Data import | Python importer using the workbook as the source seed | Repeatable and auditable ingestion of all 75 schemes |
| Local development | Docker Compose | One command for frontend, API, and database |
| Testing | Pytest and Playwright | Rule-engine, API, and complete browser-flow testing |

The user's profile will initially remain in browser memory or local storage. It will be sent to the eligibility endpoint for evaluation but will not be persisted in the database.

## 6. Proposed architecture

```text
Browser
  ├── Scheme catalogue and scheme details
  ├── Multi-section profile form
  └── Eligibility results and explanations
          │
          ▼
FastAPI
  ├── Scheme query service
  ├── Profile validation service
  └── Deterministic eligibility engine
          │
          ▼
PostgreSQL
  ├── schemes
  ├── scheme_sources
  ├── scheme_rule_sets
  ├── eligibility_rules
  └── import_runs
```

## 7. Data model

### 7.1 Scheme

- `scheme_id`: immutable ID from the workbook
- `name`
- `jurisdiction`
- `category`
- `administering_authority`
- `summary`
- `benefit`
- `eligibility_text`
- `documents_text`
- `application_mode`
- `application_url`
- `application_steps`
- `deadline_or_timing`
- `tracking_method`
- `important_caution`
- `application_readiness`: `YES`, `CONDITIONAL`, or `NO`
- `research_status`
- `last_checked`

### 7.2 Source

- `source_id`
- `scheme_id`
- `url`
- `authority`
- `last_checked`
- `source_risk`: `LOW`, `MEDIUM`, or `HIGH`
- `unresolved_issue`
- `required_next_action`

### 7.3 Rule set

- `rule_set_id`
- `scheme_id`
- `version`
- `effective_from`
- `review_state`: `DRAFT`, `REVIEWED`, or `UNRESOLVED`
- `reviewed_at`
- `source_ids`

### 7.4 Eligibility rule

Rules will be represented as a small JSON expression tree using:

- `all`
- `any`
- `not`
- `equals`
- `in`
- `greater_than_or_equal`
- `less_than_or_equal`
- `exists`

Example:

```json
{
  "all": [
    { "field": "location.state", "operator": "equals", "value": "Punjab" },
    { "field": "age", "operator": "greater_than_or_equal", "value": 18 },
    { "field": "household.annual_income", "operator": "less_than_or_equal", "value": 300000 }
  ]
}
```

Every rule must include a source reference, unit where applicable, inclusive or exclusive boundary behavior, and failure or missing-information explanation.

## 8. Deterministic matching logic

Every atomic rule returns one of:

- `PASS`
- `FAIL`
- `UNKNOWN`
- `EXTERNAL_CHECK`

Scheme-level results are calculated as follows:

1. **Likely eligible to explore**
   - Every reviewed hard rule passes.
   - No required fact is unknown.
   - Any remaining external checks are clearly displayed.

2. **Needs more information**
   - No reviewed hard rule fails.
   - At least one required profile fact is unknown, or a necessary scheme condition remains unresolved.

3. **Likely not eligible**
   - At least one known and reviewed hard rule fails.
   - The failed condition is shown in plain language.

4. **Information only**
   - The scheme does not yet have a sufficiently reviewed rule set or usable application route.

The same profile and same rule version must always produce the same result.

## 9. Initial API contract

### Catalogue

- `GET /api/v1/schemes`
  - Search, pagination, jurisdiction, category, and readiness filters
- `GET /api/v1/schemes/{scheme_id}`
  - Complete scheme details, sources, cautions, and rule coverage

### Eligibility

- `GET /api/v1/profile/schema`
  - Supported profile fields, labels, options, and explanations
- `POST /api/v1/eligibility/check`
  - Input: normalized profile
  - Output: all scheme results with passed, failed, unknown, and external-check conditions

### Operations

- `GET /api/v1/health`

## 10. User-interface screens

1. **Scheme catalogue**
   - Browse without completing a profile
   - Search and filter
   - Open a scheme detail page

2. **Scheme detail**
   - Show benefit, eligibility narrative, documents, application route, sources, and cautions

3. **Profile form**
   - Section navigation and progress indicator
   - Clear explanations for sensitive questions
   - Save locally, edit, reset, and review before submission

4. **Eligibility results**
   - Tabs or sections for likely eligible, needs information, likely not eligible, and information only
   - Explain every result
   - Edit profile and rerun without starting over

5. **Profile summary**
   - Show all known, unknown, and withheld fields before evaluation

## 11. Repository structure

```text
frontend/
  app/
    schemes/
    profile/
    results/
  components/
  lib/api.ts

backend/
  app/
    api/
    models/
    schemas/
    services/
      scheme_service.py
      eligibility_engine.py
  scripts/
    import_scheme_workbook.py
  tests/

infra/
  compose.yaml
```

## 12. Build sequence

### Phase 1: Freeze the prototype contract

**Duration:** 1 day

- Finalize profile fields and controlled values.
- Finalize rule operators and result categories.
- Confirm workbook-to-database mapping.
- Create representative test profiles.

**Exit condition:** Approved data contract and eligibility behavior.

### Phase 2: Import the catalogue

**Duration:** 1–2 days

- Create database migrations.
- Build an idempotent importer for the canonical `Scheme Data` sheet.
- Import all 75 schemes, sources, readiness status, unresolved issues, and dates.
- Reconcile the imported counts against 75 unique IDs and the 28/24/23 readiness totals.

**Exit condition:** All 75 schemes can be queried reliably through the API.

### Phase 3: Curate the first rule set

**Duration:** 3–5 days for 10–15 schemes

- Select representative, application-ready schemes.
- Convert reviewed criteria into structured rules.
- Preserve unresolved and external conditions.
- Write boundary tests for age, income, residence, category, student, worker, and farmer rules.

**Exit condition:** The first 10–15 schemes are safely machine-evaluable.

### Phase 4: Build the backend

**Duration:** 2–3 days

- Implement catalogue endpoints.
- Implement Pydantic profile validation.
- Implement pass, fail, unknown, and external-check evaluation.
- Return human-readable reasons and source metadata.

**Exit condition:** API produces stable explained results for approved test profiles.

### Phase 5: Build the frontend

**Duration:** 3–4 days

- Build catalogue and scheme-detail pages.
- Build the multi-section profile form.
- Build profile review and local save/reset controls.
- Build grouped eligibility results and explanation views.
- Make the core flow responsive and keyboard-accessible.

**Exit condition:** A person can complete the full journey in the browser.

### Phase 6: Integration, verification, and deployment

**Duration:** 2–3 days

- Run rule, API, import, and browser-flow tests.
- Test unknown values and exact boundary conditions.
- Validate that the profile is not persisted server-side.
- Deploy the frontend, API, and managed PostgreSQL database.

**Exit condition:** Shareable prototype with a tested end-to-end flow.

### Phase 7: Expand rule coverage

- Expand from the 10–15-scheme pilot to all 28 `Yes` readiness schemes.
- Resolve cautions before adding the 24 `Conditional` schemes.
- Keep the 23 incomplete schemes visible as information until their sources and application paths are resolved.

## 13. Testing requirements

### Import tests

- Exactly 75 unique scheme IDs are imported.
- The importer can be rerun without duplicates.
- Source URLs, readiness, risk, unresolved issues, and last-checked dates are preserved.
- The 28/24/23 readiness counts match the workbook.

### Rule-engine tests

- Age and income boundary values are correct.
- Unknown never becomes `No` or zero.
- A failed hard rule never returns likely eligible.
- An unresolved required rule never returns a confident positive result.
- Rule groups using `all`, `any`, and `not` behave predictably.
- Results record the exact rule-set version used.

### API tests

- Invalid profile types are rejected with useful field errors.
- Scheme search and filters are stable and paginated.
- Eligibility responses contain explanations and sources.

### User-interface tests

- Catalogue browsing works without a profile.
- A user can complete, edit, reset, and rerun a profile.
- Results remain understandable on mobile.
- Core actions work using a keyboard and screen reader labels.

## 14. Prototype acceptance criteria

The prototype is complete when:

1. All 75 schemes are visible in the catalogue.
2. Every catalogue record shows its source, last-checked date, application route, and readiness status.
3. At least 10–15 representative schemes have reviewed structured eligibility rules.
4. A user can enter and review all supported profile information without creating an account.
5. The system deterministically groups schemes and explains every result.
6. Missing information produces a specific question or action, not an assumed failure.
7. Eligibility and application readiness are displayed separately.
8. The profile is not stored by the backend.
9. The complete flow works on desktop and mobile.
10. Automated tests cover imports, rule boundaries, unknown handling, APIs, and the main browser journey.

## 15. Estimated effort

- **First demonstrable prototype with all 75 catalogue entries and 10–15 evaluated schemes:** approximately 10–14 engineering days.
- **Coverage of all 28 currently ready schemes:** approximately 3–4 calendar weeks for one developer, including review and testing.
- **Reliable filtering for all 75 schemes:** likely 5–8 weeks because conditional and incomplete schemes require source resolution and rule review, not only coding.

## 16. First coding milestone

The first coding milestone will be:

1. Create the frontend, backend, and infrastructure folders.
2. Start PostgreSQL locally.
3. Define the database and Pydantic models.
4. Import all 75 schemes from `Scheme Data`.
5. Implement `GET /api/v1/schemes` and a basic catalogue screen.

Eligibility coding should begin only after the profile-field dictionary and rule contract are fixed.
