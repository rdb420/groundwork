# Audit, September 2026

A review of the whole repository before the pilot. Each finding has an id, the place it lives,
and a status. Work runs in the order below: gaps against our own rules first, then high, medium
and low. Update the status here in the same commit as the fix.

## Gaps against our own rules and plan

| Id | Gap | Status |
|---|---|---|
| G1 | No git history, no CI, no linter, no backend type checks. | Fixed: repo on GitHub; CI runs ruff, mypy, pytest, eslint, vitest, the build and the image |
| G2 | CLAUDE.md asks for a test on every state-changing endpoint; withdraw, process edits, admin, parking, document, recording chunks and board-image visibility have none. The frontend has no tests. | Fixed: `tests/test_endpoints.py` covers every state-changing endpoint; vitest covers the op engine, markdown and kinds; each later fix adds its own test |
| G3 | Every state-changing endpoint should write an audit event; `parking_add`, `PUT /me`, chunk upload and logout do not. | Fixed: all four now audit; `live.heard` records sentences that changed nothing; a test fails if any mutating route skips `audit.record` |
| G4 | Rollout depends on roadmap items not yet built: coverage view (phase 3 exit), catalogue admin (phase 0), retention and purge, malware scanning before public exposure. | Fixed: Coverage page and `/api/admin/coverage`; Process list page with validated edits and merge; retention settings, daily purge and admin delete-now; ClamAV scanning with quarantine |
| G5 | Privacy impact assessment and retention period are required before inviting staff; neither exists. | Drafted: `docs/PRIVACY.md` assesses each APP, proposes a retention schedule (now in config), a recording consent procedure, risks, open legal questions and actions. Needs review and sign-off by YSH |
| G6 | Live mapping should run Jev through OpenRouter, and the reviewer through OpenAI. | Fixed: `GW_DECISION_PROVIDER=openrouter` and `GW_AI_PROVIDER=openai` are the defaults in `.env.example`; `scripts/check_providers.py` confirms both answer |

## High

| Id | Finding | Where | Status |
|---|---|---|---|
| H1 | Stored XSS: the browser-declared type decides inline display, board images are visible to everyone, and there is no Content-Security-Policy. An SVG with a script runs in the portal's origin. | `routers/artifacts.py`, `deploy/Caddyfile` | Fixed: type comes from the extension; only raster images display inline; file downloads carry a sandbox CSP; the app sends a CSP and security headers on every response (`app/main.py`); map images must be images on a real map. Since 819ff4a fonts are self-hosted and the CSP allows fonts only from the app's own origin |
| H2 | One bad map breaks a board: saves accept any node shape; a node without an id, a `parentId` loop, or a chain of about 1,000 steps makes checks, generate and review fail with a 500. | `routers/boards.py::save_board`, `ai/context.py` | Fixed: `app/canvas.py` validates every map the server saves or reads from the browser (ids, positions, parents without loops, size limits) and drops dangling connections; both walks are iterative and loop-safe; maps damaged before this give a clear message |
| H3 | Files marked "unsure" for personal information are sent to cloud models. | `ai/generate.py::_evidence` | Fixed: any linked file not marked No keeps the map away from hosted models for drafts and reviews (`ai/generate.py::_evidence`, `live/review.py`); the Share form says so. Combining views checks only each map's own tick, and sends maps, not file contents. The ingestion pipeline treats not sure as personal too (`ingest/pipeline.py::personal`) |
| H4 | The last recording chunk is lost: `/end` is sent before the final chunk uploads. Reusing a `seq` overwrites audio on disk, then fails. Anyone can end anyone's recording. | `canvas/SessionPanel.tsx`, `routers/boards.py` | Fixed: Stop waits for every part to upload (with retries) before ending, leaving the map finishes the same way, and the page warns before closing mid-recording; the server accepts parts for two minutes after the end, keeps the first copy of a repeated part, and only lets the person recording (or an admin) add parts or stop |

## Medium

| Id | Finding | Where | Status |
|---|---|---|---|
| M5 | Sharing several files with one new process name creates that process once per file. | `routers/artifacts.py::upload`, `pages/Share.tsx` | Fixed: uploads reuse a live process with the same name in any case (`find_or_propose`) |
| M6 | Roles never go down after an address leaves `GW_ADMIN_EMAILS`; sessions can't be revoked. | `routers/auth.py::verify` | Fixed: roles follow the settings on every request; admins can sign someone out everywhere or remove access (People page); the worker clears expired sessions and links hourly |
| M7 | A combined map is accepted on first open without anyone choosing to keep it. Live auto-apply is not stated in CLAUDE.md. | `pages/BoardPage.tsx`, `CLAUDE.md` | Fixed: combined maps open as suggestions with Keep all and Discard all, and are laid out once; CLAUDE.md states the live auto-apply exception |
| M8 | Browser speech recognition sends audio to Google or Microsoft even on personal-information maps with a local decision model. | `canvas/LivePanel.tsx` | Fixed: on maps marked as holding personal information, listening is off and the Live tab says to type instead, whatever the decision model |
| M9 | Live routes skip `_board()`, so tightening board access would miss them. | `routers/live.py` | Fixed: `app/access.py::open_board` is the single check for every map, recording, draft, parking, rules, document and map-image route; a test denies access and expects every one to refuse |
| M10 | Worker: jobs stuck in `running` after a crash never recover, retries have no backoff, workbooks load fully into memory, and a big workbook delays transcription. | `worker.py`, `processing/xlsx_profile.py` | Fixed: jobs left running are reclaimed at start-up and hourly; failures back off (30 s, 2 min) before the third and last try; workbooks over 150 MB expanded get a streaming read and zip bombs aren't opened; a separate transcriber worker, and transcription first when one worker runs everything |
| M11 | AI prompts see file metadata and a 400-character summary; extracted text is never used. | `ai/generate.py::_evidence` | Fixed: drafts and reviews get each linked file's extracted text or workbook structure, up to 4,000 characters a file and 40,000 in all, fenced as data |
| M12 | Deployment option C (Tailscale) proxies `localhost:8000`, which compose never publishes. | `deploy/Caddyfile`, `docker-compose.yml` | Fixed: compose publishes the app on 127.0.0.1:8000 only; the Caddyfile and ARCHITECTURE give the exact option C commands and settings |
| M13 | An unknown `board_id` on upload or `process_id` on a board save returns a 500. | `routers/artifacts.py`, `routers/boards.py` | Fixed: uploads check the map and processes, boards check the process on create and save, new processes check their parent; each answers 404 |

## Low

| Id | Finding | Where | Status |
|---|---|---|---|
| L1 | Process edits accept any `status` and allow `parent_id` loops. | `routers/processes.py` | Fixed with G4: status must be proposed, confirmed or retired; parents must exist and can't loop; names stay unique; owner must be an email |
| L2 | Document and rule-table saves have no version check; the last save wins. | `routers/live.py` | Fixed: both carry a version; a save from an older version is refused with a way to reload (and copy your text first, for the document) |
| L3 | A recording stays open forever if the tab closes. | `routers/boards.py` | Fixed: hourly housekeeping ends a recording after 15 minutes without audio, and leaving the map ends it straight away (H4) |
| L4 | Backups are unencrypted and sit on the same disk. | `app/backup.py`, `deploy/backup.sh` | Fixed: with `GW_BACKUP_AGE_RECIPIENTS` the archive is encrypted with age as it is written (the image includes age); `backup.sh` copies to `GW_BACKUP_COPY_TO` and refuses to copy unencrypted backups; README explains keys and restore tests |
| L5 | Recording chunks are read whole into memory with no size limit of their own. | `routers/boards.py::upload_chunk` | Fixed with H4: parts stream to disk with a 25 MB limit and only audio extensions |
