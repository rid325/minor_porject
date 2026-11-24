# Yojana Connect implementation and issue log

## Local verification on 24 November 2026

| Issue | Change | Verification or remaining work |
|---|---|---|
| The catalogue fell back to five examples when FastAPI was unavailable. | The Next.js catalogue and detail routes read the checked-in 75-record seed. Empty searches remain empty. Network failures have a retry state on the catalogue. | The browser catalogue and the standalone Next.js catalogue endpoint both returned 75 records. |
| The detail screen dropped FastAPI source objects and sometimes represented third-party mirrors as official government websites. | Source normalization accepts strings and objects, retains secondary links, and uses the source host to label references. Conditional routes have a guidance button. | Checked the detail page in Chrome with the official reference and the document checklist visible. |
| Guest results disappeared on reload. A failed account-profile read could trigger an immediate save. | Guest storage survives navigation, account-owned results require an identity check, and the form syncs on edits. The backend is required for a new eligibility assessment. | Exercised confirmation, profile handoff, reload and results in Chrome. |
| Offline estimates and unreviewed rules could yield a confident match. | Removed the browser heuristic. Unreviewed rules return an information-only verdict. The backend serves normalized eligibility conditions on the detail route. | 17 records now have a built-in reviewed rule set. Three additions cover the Haryana Ladli allowance and the national and Chandigarh records for post-matric disability scholarships. Removed arbitrary fixed income choices from result follow-up forms. |
| The scripted chat had no model, evidence or profile confirmation. | FastAPI uses local Ollama for multilingual intent extraction. Nomic embeddings and weighted keyword matches rank catalogue records. Replies display the relevant catalogue field and source. A private, expiring conversation holds proposed facts and confirmed corrections. Users explicitly transfer confirmed facts to the profile for matching. | English intake tested in Chrome. Hindi Haryana pension and Punjabi PM-KISAN are regression cases. Source excerpts retain the original catalogue language. A free-form generated paraphrase invented a date during testing, so policy details are quoted from the record. |
| The document checker was hidden outside two records. | All 75 records expose versioned instructions, conditional items and an interactive checklist. User-reported missing items appear in the report. Nine records also check selected evidence categories automatically. Conflicts appear with eligibility recheck information. | Checked all 75 checklist endpoints. Tested a stale checklist answer, consent, missing evidence, OCR, correction guidance, and account isolation. The nine mappings cover categories within the larger source checklist. |
| Catalogue updates depended on manual discovery. | Weekly GitHub Actions workflow fingerprints sources and application destinations and collects district scheme links for review. It saves a baseline and publishes the review queue as an artifact. | Local baseline attempted 311 distinct references. 160 fetched successfully, 151 need investigation. Two directory links were queued. A changed response, redirect or fetch error requires editorial inspection. GitHub scheduling starts after the workflow is on the default branch. |
| Workbook mode lost supporting sheets and displayed Excel date serials. | Restored the exact source workbook identified by the seed checksum. Runtime workbook reads reuse the canonical importer. | Import tests compare the regenerated data with the committed seed byte for byte. |

## Verification

Run the backend suite from the repository root with the backend virtual environment. Run the frontend production build from the frontend directory. The source monitor runs with the backend Python interpreter using `python -m backend.scripts.monitor_sources <baseline-directory>`. Keep that directory between checks.

The labelled extraction evaluator runs with `python -m backend.scripts.evaluate_document_extraction manifest.json`. It reports exact, incorrect, missed and unexpected fields by language. A three-document synthetic English sample yielded three exact names and two exact dates. The partial-year example yielded no birth date. The backend suite also exercises scanned PNG, JPEG and PDF inputs.

A real loopback MongoDB integration exercise covered sign-up, encrypted PDF storage, byte-for-byte download, saved-file extraction and deletion. The browser demo uses temporary local storage for accounts and files. Use synthetic examples. The shared online database, cloud storage and external messaging providers were excluded from this test.

## Items requiring further evidence

- Review the failed fetches in `outputs/source_review_2026-11-24.json`. DNS, TLS, bot protection, timeouts and HTTP errors require different follow-ups. A successful web response alone cannot verify an open application window or a particular eligibility threshold.
- Review the remaining 58 scheme records before enabling definitive automated recommendations. The discovery queue contains candidate links. New catalogue entries still require extraction and editorial acceptance. Coverage of discovery is limited to the configured directories.
- Conversational intake currently proposes six common fields. The structured form and per-scheme questions cover additional facts. Chat state is per process with a 30-minute idle expiry. Multi-worker hosting requires shared session storage. Evaluate relevance and comprehension on representative user questions in all three languages before claiming population-level accuracy.
- The checklist for each scheme retains the source wording. For the remaining 66 records, document readiness is self-reported and evidence can be compared. Further issuer-specific mappings and an independently labelled, de-identified multilingual scan set are needed to measure field accuracy on real documents.
- Verify the deployment-specific upload lifecycle using a designated staging account, replacement secrets, the intended retention settings and installed OCR languages. Online storage and encryption key rotation require a migration plan for previously encrypted files.

## Mentor review for the morning of 24 November 2026

1. **Answer language.** Reproduce the reported English answer to Hindi and Punjabi questions. Check the answer body, conditional documents, confirmation buttons, eligibility explanations, errors and next question. Keep the original official wording available beside a clearly labelled translation. Compare names, amounts, dates, exceptions and required versus conditional evidence against the cited record.
2. **Follow-up continuity.** In each language ask about a scheme, then ask “Which documents?” without repeating its name. Correct the state, dismiss an incorrect suggestion and ask how to apply. Verify the assistant remembers the intended scheme and language, requests only missing information, and carries only confirmed facts into the profile.
3. **Walk the implementation plan as a mentor.** Use a synthetic applicant to go from chat to profile, explained shortlist, source, document checklist and application route. Repeat with missing information, a failed eligibility condition and a document conflict. Trace each displayed decision to the profile field, versioned rule or catalogue source that produced it.
4. **Record the verdict.** For each planned module list its acceptance criterion, observed result, reproducible evidence and open defect. Distinguish the 75 browseable records, reviewed eligibility coverage and automated document coverage. Check the demo claims against those results before presenting.

### Morning review results, 24 November

| Acceptance check | Observed result |
|---|---|
| Answer and follow-up language | Chrome at 390 px showed Hindi PM-KISAN document text. Chrome at 1280 px showed Punjabi. In both sessions a second document question retrieved the same scheme. In the Punjabi session the short English follow-up retained Punjabi. Source wording remains expandable. |
| Evidence preservation | The two tested document lists and their conditional clauses have source-text-keyed translations. Other excerpts use local machine translation with script, digit and URL checks. If a translation fails those checks the user can open the original. Independent language review is outstanding for machine translations. |
| Core plan criteria 1–3 | All 75 detail responses contained source metadata, recorded check date, route steps, a route URL and readiness. Seventeen catalogue entries have reviewed rule sets. The presence of a URL does not establish that applications are currently open. |
| Criteria 4–7 | In Chrome, a guest confirmed Punjab and farmer status, opened the profile, reloaded, and reached results covering 75 records. The suite checks income boundaries, unknown answers, corrections and token isolation. A separate mobile detail-page check verified that the document checklist and route-readiness label rendered. |
| Criterion 8, profile storage | The project scope evolved. Guest form answers use browser storage and chat keeps temporary session facts. Signed-in saving uses MongoDB when configured. The local chat backend currently runs without an account database. |
| Criteria 9–10 | Desktop guest journey, mobile detail navigation and mobile/desktop chat checks passed. TypeScript passed and 71 backend tests passed. The browser checks ran locally; adding the browser suite to CI and testing the entire form at multiple phone sizes remain open. |
| Document module and release limits | Existing regression tests cover inconsistent evidence, missing documents, and stale checklist selections. Automatic category checks cover nine schemes. Production upload verification, broader human review of rules, real-document OCR benchmarking and investigation of flagged sources remain open. |

The local frontend now points both catalogue/eligibility and chat requests to the updated backend on port 8010. No GitHub push or hosted deployment was performed.

### Follow-up verification on 24 November

| Check | Latest result |
|---|---|
| Catalogue | Queried every scheme detail and checklist through FastAPI. All 75 had sources, a recorded date, route instructions, readiness and checklist items. Seventeen have reviewed rules; nine have automatic document-category checks. |
| Personalised filtering | Fixed a state-filter bug that hid national programmes whose jurisdiction includes an implementation note, such as PMUY. Added a matching regression and a browser assertion for a Punjab guest. |
| Chat | Chrome verified Hindi and Punjabi document answers, citations, and a second question about the same scheme. A separate correction test caught the assistant switching schemes when the user changed state. The fix preserves the scheme through a correction, confirmation or dismissal and the subsequent application question. |
| Guest journey | Production frontend at 360, 390 and 1280 px. Entered state, birth date and income, completed all form steps, assessed 75 records, reloaded results, inspected a source and checklist, and returned to chat. Added a repeatable test and a GitHub Actions workflow. The workflow awaits a future push. |
| Documents | Repeated sign-up, encrypted storage, download, date extraction and deletion against an isolated MongoDB using a synthetic PDF. The labelled English sample returned three exact names and two exact dates. Hosted storage and real multilingual scan accuracy remain unverified. |
| Build and dependencies | Patched Next.js from 16.4.0 to 16.4.6 after npm reported a critical advisory. Production build, TypeScript and dependency audit passed. Replaced the obsolete Next lint command with ESLint. It reports one performance warning for the browser-local document preview. Pytest emits a TestClient deprecation warning. |
| Sources | A full scan after the rural-employment correction reached 159 of 310 distinct references. Of the 151 failed fetches, 30 returned HTTP 404. The JSON report identifies which failed references serve as primary sources and application links. The HIMCARE application link was then replaced with the state society's enrolment form and independently fetched with HTTP 200. Remaining failures require editorial follow-up. |

**Catalogue corrections.** The workbook and seed now describe the VB–G RAM G rural employment guarantee under the existing record identifier. The original 100-day MGNREGA wording was obsolete. HIMCARE's enrolment link also changed. Compared the other 73 scheme records with the original seed. Sources: [Ministry FAQ](https://www.pib.gov.in/FaqDetails.aspx?ModuleId=4&NoteId=158511&lang=1&reg=3), [commencement notification](https://static.pib.gov.in/WriteReadData/specificdocs/documents/2026/may/doc2026511867901.pdf), [HIMCARE enrolment form](https://app.hpsbys.in/website/AddBeneficiaryInfo.aspx).

To repeat the browser test with both local services running, run `TEST_BROWSER_CHANNEL=chrome npm run test:journey` in the frontend directory. The local preview is http://127.0.0.1:3000. Its backend currently serves guest journeys and has no configured account database. The MongoDB verification used a separate temporary database. Release gates still open include authoritative review of the 58 outstanding rule sets, the remaining source queue, independently evaluated multilingual translations and OCR, and hosted upload verification.

### Additional regression checks, 24 November

* Chat now computes its relevance threshold among schemes available in the requested jurisdiction. An exact match from another state could previously hide a relevant local pension. Reaffirming an already confirmed profile fact also clears a contradictory pending suggestion. The API rejects a later attempt to confirm that obsolete suggestion.
* The source monitor records individual discovery feeds that fail or return no scheme links, even when another feed succeeds. Previously discovered links are retained across partial outages.
* Updated six primary references in the workbook and regenerated the seed. The PMAY-G portal, PM Vishwakarma PIB guidance and national old-age pension PIB notice returned HTTP 200 locally. The KVIC PMEGP PDF and two Himachal service pages were identified via indexed official content. Local DNS or TLS errors still prevent confirming direct access to those three pages. The Shagun link establishes its listing only. See the follow-up entries in outputs/source_review_2026-11-24.json. The original full-scan counts refer to the pre-correction snapshot.
* The October 14 Cabinet announcement approves updated pension and family benefit programme names. Four affected catalogue records retain their earlier names alongside the approved names. Scheme IDs, readiness counts and existing application routes were preserved. Source: https://www.pib.gov.in/PressReleasePage.aspx?PRID=2323266&lang=1&reg=3
* After the changes, all 77 backend tests passed. Chrome passed the guest journeys at 360, 390 and 1280 px and the Hindi and Punjabi document follow-ups. TypeScript passed. ESLint reported one existing performance warning for a private browser-local image preview.

### Synthetic applicant walkthrough, 24 November

Ran Chrome against a separate local copy of the frontend, the project FastAPI server, an isolated MongoDB instance and local encrypted document storage. The usual preview on port 3000 was tested separately for guest journeys and Hindi/Punjabi chat.

| Step | Observed outcome |
|---|---|
| Account and profile | Signed up, confirmed Punjab and farmer status in chat, transferred confirmed facts into the form, saved DOB 17 May 1990 and household income ₹50,000. Signed out and back in, saw the saved state and changed the password. |
| Chat and matching | Live local model and hybrid retrieval returned PM-KISAN. The partial profile produced 13 needing more information, four likely ineligible and 58 information-only records. Demo inbox had zero messages. A separate live API scenario with DOB and a savings account produced a likely-eligible PMJJBY result. |
| Document workflow | Uploaded two synthetic text PDFs, selected both in the checker, detected a DOB conflict (3 October 2006 versus 17 May 1990), opened the correction guide and downloaded a report containing both dates. Downloaded both original files byte-for-byte and deleted them. Chrome recorded zero page errors on the completed run. |
| OCR and checklist | Separate live API checks refused a PNG without consent (422), recovered the exact name and DOB from the consented English image, and returned the PM-KISAN land-record checklist item marked missing. |
| Additional checks | All 77 backend tests passed. Guest browser journey passed at 360, 390 and 1280 px. Hindi and Punjabi document follow-ups passed. External email delivery, hosted storage, external Gemini generation, and government application submission were outside this local run. |
