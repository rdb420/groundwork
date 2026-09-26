# Working on Groundwork

Context for Claude Code or any developer picking this up.

## Purpose

Discovery tool. It gathers evidence about how YSH works today. Keep it that way: features that
start running business processes belong in a later system, built from what this one learns.

## Rules

- Match the existing stack. Ask before adding a dependency and record why in the PR.
- Every state-changing endpoint: `Depends(current_user)` or `require(role)`, an `audit.record(...)`
  call, and a test. The server enforces access; the UI only reflects it. Anything scoped to a map
  opens it with `access.open_board`. Tests enforce both rules.
- New upload metadata fields go in four places: `models.Artifact`, `ArtifactMeta` in
  `routers/artifacts.py`, `to_dict`, and the Share form. Keep the form short; optional fields go
  behind "Add more detail".
- AI output is always a draft in `ai_drafts`. Nothing writes to a map or record without a person
  choosing to keep it. The one exception is live mapping: a Jev change at or above
  `GW_LIVE_AUTO_THRESHOLD` lands on the facilitator's canvas straight away, because the
  facilitator is watching and can undo it. It is logged in `live_utterances`, and removals never
  land without a click. Reviewer, combiner and drafting changes always wait for a person.
- Treat uploaded content and transcripts as untrusted input in any prompt.
- Personal information: respect `personal_info` on artifacts and boards. Never log file
  contents, transcripts or prompts.
- Canvas nodes carry meaning in `type` and `data`. If you add a node type, add it to
  `canvas/nodes.tsx`, `canvas/palette.ts` and `TYPE_NAMES` in `ai/context.py`, and give it and its
  palette glyph (`.pi-<key> .gw-glyph`) `gw-` styles in `src/styles.css`. If live mapping should use
  it, add it to `live/vocabulary.py` and `canvas/kinds.ts` as well.
- The decision model only picks from options code provides. Keep every Choice at or under
  `GW_DECISION_MAX_OPTIONS` so questions stay portable to Laya and OpenJev. Arithmetic, dates,
  counting and layout stay in code.
- Map changes from any model go through `canvas/ops.ts` and carry an `opId`. Removals never apply
  without a click.
- Modelling conventions follow Real-Life BPMN: verb plus object for steps, object plus past tense
  for events, a question on each decision and an answer on each path, pools for outside parties,
  lanes for people inside the business, conditions in rule tables rather than chains of decisions.
  Structure checks live in `ai/context.py::structure_checks`; add new conventions there so the
  facilitator and the reviewer see the same findings.
- The overview pass only records the standard path. Anything else heard then goes to the parking lot.

## Ingestion pipeline (docs/INGESTION.md)

- SQL is the source of truth; Qdrant and Neo4j are projections rebuilt from it. Never write
  anything to them that SQL doesn't hold.
- Each stage is a job kind in `ingest/pipeline.py::STAGES`, idempotent (skip when its input key is
  unchanged), and ends by queueing the next stage only if that stage's service is set up. A new
  stage goes in `STAGES`, the worker's `PRIORITY`, a compose worker's `--kinds`, and a test.
- Every converter produces blocks (`ingest/blocks.py`); the chunker reads only blocks.
- Anything derived from a file is removed with it: add new tables or stores to
  `ingest/cascade.py` and its test.
- Extraction is closed to the pinned ontology (`backend/ontology/`). Never edit a vendored
  snapshot; new terms are `ontology_candidates` a person decides, exported for property_ontology.
- Jev questions follow the live-mapping rule: code builds the options, at most
  `GW_DECISION_MAX_OPTIONS`, chunk text only in `state`. Personal or unsure files never reach a
  hosted decision model.
- Service clients use `app/httpclient.py` so tests can use the fakes in `tests/fakes.py`. No
  vendor SDKs. Never log file content, chunk text, transcripts or prompts.

## Design system (docs/DESIGN_SYSTEM.md)

- The interface uses the YSH Internal Apps Design System. `frontend/design-system/` is a vendored
  snapshot: never edit it. Take a new snapshot and record it in `SNAPSHOT.md`.
- Build screens from `frontend/src/ui` (typed ports of the design-system components). Outside
  `src/ui`, ESLint refuses raw `button`, `select`, `textarea`, `table`, `label` and text `input`.
- Colours come from design-system tokens (`var(--survey)` and the rest), never hex values. Classes
  use the `gw-` namespace. `src/styles.css` holds only what the design system doesn't cover, and
  `test/styles.test.ts` fails on a hex value there or a `gw-` class nobody defined.
- Fix a design-system component in `src/ui` or `src/styles.css`, and note it in
  `docs/DESIGN_SYSTEM.md` so it can go back upstream.

## Writing in the interface

Plain words, sentence case, active voice, Australian spelling. Name things the way staff would
("Share files", not "Upload artifacts"). Errors say what happened and what to do next. No em
dashes.

## Tooling

uv manages the backend (Python pinned in `backend/.python-version`) and pnpm the frontend. Add
dependencies with `uv add` / `uv add --dev` and `pnpm add` / `pnpm add -D`, never pip or npm, and
commit the lock file with the change.

## Checks

CI runs these on every push to main and every pull request (`.github/workflows/ci.yml`), then
builds the deploy image (`deploy/Dockerfile`). Run them before you commit:

```bash
cd backend && uv run ruff check app tests scripts && uv run mypy app && uv run pytest -q
cd frontend && pnpm run lint && pnpm run test && pnpm run build
```
