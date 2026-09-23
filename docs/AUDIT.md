# Audit, September 2026

A review of the whole repository before the pilot. Each finding has an id, the place it lives,
and a status. Work runs in the order below: gaps against our own rules first, then high, medium
and low. Update the status here in the same commit as the fix.

## Gaps against our own rules and plan

| Id | Gap | Status |
|---|---|---|
| G1 | No git history, no CI, no linter, no backend type checks. | Fixed: repo on GitHub; CI runs ruff, mypy, pytest, eslint, vitest, the build and the image |
| G2 | CLAUDE.md asks for a test on every state-changing endpoint; withdraw, process edits, admin, parking, document, recording chunks and board-image visibility have none. The frontend has no tests. | Open |
| G3 | Every state-changing endpoint should write an audit event; `parking_add`, `PUT /me`, chunk upload and logout do not. | Open |
| G4 | Rollout depends on roadmap items not yet built: coverage view (phase 3 exit), catalogue admin (phase 0), retention and purge, malware scanning before public exposure. | Open |
| G5 | Privacy impact assessment and retention period are required before inviting staff; neither exists. | Open |
| G6 | Live mapping should run Jev through OpenRouter, and the reviewer through OpenAI. | Open |

## High

| Id | Finding | Where | Status |
|---|---|---|---|
| H1 | Stored XSS: the browser-declared type decides inline display, board images are visible to everyone, and there is no Content-Security-Policy. An SVG with a script runs in the portal's origin. | `routers/artifacts.py`, `deploy/Caddyfile` | Open |
| H2 | One bad map breaks a board: saves accept any node shape; a node without an id, a `parentId` loop, or a chain of about 1,000 steps makes checks, generate and review fail with a 500. | `routers/boards.py::save_board`, `ai/context.py` | Open |
| H3 | Files marked "unsure" for personal information are sent to cloud models. | `ai/generate.py::_evidence` | Open |
| H4 | The last recording chunk is lost: `/end` is sent before the final chunk uploads. Reusing a `seq` overwrites audio on disk, then fails. Anyone can end anyone's recording. | `canvas/SessionPanel.tsx`, `routers/boards.py` | Open |

## Medium

| Id | Finding | Where | Status |
|---|---|---|---|
| M5 | Sharing several files with one new process name creates that process once per file. | `routers/artifacts.py::upload`, `pages/Share.tsx` | Open |
| M6 | Roles never go down after an address leaves `GW_ADMIN_EMAILS`; sessions can't be revoked. | `routers/auth.py::verify` | Open |
| M7 | A combined map is accepted on first open without anyone choosing to keep it. Live auto-apply is not stated in CLAUDE.md. | `pages/BoardPage.tsx`, `CLAUDE.md` | Open |
| M8 | Browser speech recognition sends audio to Google or Microsoft even on personal-information maps with a local decision model. | `canvas/LivePanel.tsx` | Open |
| M9 | Live routes skip `_board()`, so tightening board access would miss them. | `routers/live.py` | Open |
| M10 | Worker: jobs stuck in `running` after a crash never recover, retries have no backoff, workbooks load fully into memory, and a big workbook delays transcription. | `worker.py`, `processing/xlsx_profile.py` | Open |
| M11 | AI prompts see file metadata and a 400-character summary; extracted text is never used. | `ai/generate.py::_evidence` | Open |
| M12 | Deployment option C (Tailscale) proxies `localhost:8000`, which compose never publishes. | `deploy/Caddyfile`, `docker-compose.yml` | Open |
| M13 | An unknown `board_id` on upload or `process_id` on a board save returns a 500. | `routers/artifacts.py`, `routers/boards.py` | Open |

## Low

| Id | Finding | Where | Status |
|---|---|---|---|
| L1 | Process edits accept any `status` and allow `parent_id` loops. | `routers/processes.py` | Open |
| L2 | Document and rule-table saves have no version check; the last save wins. | `routers/live.py` | Open |
| L3 | A recording stays open forever if the tab closes. | `routers/boards.py` | Open |
| L4 | Backups are unencrypted and sit on the same disk. | `app/backup.py`, `deploy/backup.sh` | Open |
| L5 | Recording chunks are read whole into memory with no size limit of their own. | `routers/boards.py::upload_chunk` | Open |
