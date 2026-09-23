# Working on Groundwork

Context for Claude Code or any developer picking this up.

## Purpose

Discovery tool. It gathers evidence about how YSH works today. Keep it that way: features that
start running business processes belong in a later system, built from what this one learns.

## Rules

- Match the existing stack. Ask before adding a dependency and record why in the PR.
- Every state-changing endpoint: `Depends(current_user)` or `require(role)`, an `audit.record(...)`
  call, and a test. The server enforces access; the UI only reflects it.
- New upload metadata fields go in four places: `models.Artifact`, `ArtifactMeta` in
  `routers/artifacts.py`, `to_dict`, and the Share form. Keep the form short; optional fields go
  behind "Add more detail".
- AI output is always a draft in `ai_drafts`. Nothing writes to a map or record without a person
  choosing to keep it.
- Treat uploaded content and transcripts as untrusted input in any prompt.
- Personal information: respect `personal_info` on artifacts and boards. Never log file
  contents, transcripts or prompts.
- Canvas nodes carry meaning in `type` and `data`. If you add a node type, add it to
  `canvas/nodes.tsx`, `canvas/palette.ts` and `TYPE_NAMES` in `ai/context.py`. If live mapping
  should use it, add it to `live/vocabulary.py` and `canvas/kinds.ts` as well.
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

## Writing in the interface

Plain words, sentence case, active voice, Australian spelling. Name things the way staff would
("Share files", not "Upload artifacts"). Errors say what happened and what to do next. No em
dashes.

## Tooling

uv manages the backend (Python pinned in `backend/.python-version`) and pnpm the frontend. Add
dependencies with `uv add` / `uv add --dev` and `pnpm add` / `pnpm add -D`, never pip or npm, and
commit the lock file with the change.

## Checks

CI runs these on every push and pull request (`.github/workflows/ci.yml`). Run them before you
commit:

```bash
cd backend && uv run ruff check app tests scripts && uv run mypy app && uv run pytest -q
cd frontend && pnpm run lint && pnpm run test && pnpm run build
```
