# Groundwork: architecture and rollout

Groundwork is YSH's knowledge-gathering portal. Staff use it to hand over the files they work
from and to map how their work actually flows. It exists to serve one principle from the
discovery research: understand the work before digitising it, simplify it before automating it,
and structure it before adding AI.

Groundwork builds nothing that runs the business. It collects evidence about how the business
runs today, so that later decisions rest on that evidence.

## 1. What it does

Two jobs, in order of rollout.

**Evidence intake.** Anyone with a company email address signs in with a link and uploads
spreadsheets, procedures, templates, reports, email exports and photos. Each upload carries a
short description, the process it belongs to, which layer of the work it shows, and whether it
holds personal information. Files stay on premises. A worker checks each one for malware and
gives it a first read; with the ingestion pipeline on, it also becomes searchable Markdown and
entries in a knowledge graph.

**Process mapping.** A shared canvas with BPMN elements, context elements (people, applications,
workarounds, issues, risks and the like), sticky notes, text and images. A mapping session can be
recorded and transcribed. AI turns the map, transcript and linked files into a draft SOP,
suggested map changes, or the questions to ask next. People accept or discard every draft.

### The four evidence layers

The upload form asks one question that does most of the analytical work later: what does this
file show?

| Layer | Form label | Why it matters |
|---|---|---|
| declared | How it's meant to be done | The official version. Often out of date. |
| system | What a system produces or needs | What software forces or reports. |
| actual | How I actually do it | The real sequence, including judgement calls. |
| workaround | A workaround we built | Shadow process. Each one points at a missing capability. |

A workaround is a requirement in disguise. The weekly arrears spreadsheet tells you the rent
system lacks a queue. The forwarded Monday email tells you a report doesn't reach the person
who needs it. The coverage view compares layers per process to show where the
official story and the real one diverge.

## 2. System view

```
 Staff browser (desktop, tablet, phone)
        |  HTTPS
        v
 +----------------+      +-----------------------------------------------+
 | Caddy          | ---> | app (FastAPI, serves the built React app)     |
 | TLS, headers   |      |  /api/auth       magic-link sign-in           |
 +----------------+      |  /api/artifacts  uploads + metadata           |
                         |  /api/processes  process catalogue            |
                         |  /api/boards     maps, recordings, AI drafts, |
                         |                  live mapping, rules, SOPs    |
                         |  /api/ontology   proposed terms               |
                         |  /api/admin      coverage, retention, audit,  |
                         |                  people, pipeline             |
                         +-----------------------------------------------+
                                |                 |
                     SQLite (WAL)          object storage: local /data, or self-hosted
                     users, sessions,      Supabase Storage or MinIO (S3)
                     artifacts, boards,      artifacts/<id>/original.<ext>, metadata.json,
                     jobs, drafts,              extracted.txt, v<n>/document.md, blocks.json, images/
                     documents, chunks,      recordings/<id>/00000.webm, transcript/v<n>/...
                     entities, relations,
                     proposals, audit_events
                                |
                                v
                         +-------------+
                         | workers     |  poll the jobs table, each for its own job kinds
                         |  worker     |  ClamAV (clamd) check, then first read: spreadsheets,
                         |             |  PDFs, Word, text; retention; hourly upkeep
                         | transcriber |  session audio: Parakeet, faster-whisper or a Whisper server
                         |  converter  |  ingestion: MinerU, Gotenberg, native readers, Parakeet
                         |  indexer    |  chunk, embed, Qdrant; extract; Neo4j; topics; purges
                         +-------------+
                                |
             ingestion (on-prem, docs/INGESTION.md): MinerU, Parakeet, embedding and extraction
                        sidecars and Laya on the inference box (RTX 3090); Qdrant, Neo4j,
                        Gotenberg on the host
             optional:  Jev through OpenRouter (live mapping and extraction decisions, hosted)
                        Laya on the inference box (local decision model, suggested for extraction)
                        OpenAI (drafting and session review, hosted)
                        Ollama on the inference box (local AI, the choice for personal info)
                        Anthropic API (cloud AI, blocked for personal info by default)
```

### Components

| Component | Choice | Reason |
|---|---|---|
| API | FastAPI, Python 3.12 | The processing work (openpyxl, PDF text, Whisper) is Python. One language for API and worker. |
| Database | SQLite in WAL mode | One office, one host, tens of users. No database server to run. SQLAlchemy keeps Postgres a config change away. |
| Files | Local disk or self-hosted Supabase Storage (S3, or MinIO), a JSON sidecar per file | Files stay on premises. Each folder describes itself if the database is ever lost. One interface (`app/storage.py`, `GW_STORAGE_BACKEND=local` or `s3`); the S3 client (`app/s3.py`) signs requests with SigV4 itself, no SDK. |
| Ingestion | Job stages on the same queue; SQL as the source of truth | Each stage is idempotent and can be rerun. Qdrant and Neo4j are projections rebuilt from SQL. See [INGESTION.md](INGESTION.md). |
| Vectors | Qdrant: dense (MiniLM), sparse (SPLADE), ColBERT rerank | Hybrid search that works for exact terms (SPLADE) and paraphrase (dense), reranked token by token. |
| Graph | Neo4j, typed by the pinned property ontology | Entities and relationships closed to the ontology; new terms are proposals a person decides. |
| Queue | `jobs` table polled by workers, each started with `--kinds` for its own job kinds | No broker to install. A single UPDATE claims a job. One worker reads files, one transcribes, so a large workbook never delays a live transcript; the pipeline adds a converter and an indexer. Failed jobs back off (30 seconds, then 2 minutes) and fail for good after three tries; jobs a crashed worker left running are picked up again. |
| Frontend | React, Vite, React Flow (MIT), the YSH Internal Apps Design System | React Flow gives typed nodes and edges, so the server reads the map as a process. The design system gives shared tokens, fonts and `gw-` components (see Frontend below). |
| Canvas model | Typed BPMN nodes in JSON | Chosen over a freehand whiteboard (Excalidraw) because AI and later BPMN export need semantics. Chosen over bpmn-js because staff need sticky notes and photos beside the notation. |
| TLS | Caddy | Automatic certificates, internal or public, in five lines. |
| AI | Plain HTTP to OpenAI (or any OpenAI-compatible endpoint), Ollama or Anthropic | No vendor SDK. Switching provider is an environment variable (`GW_AI_PROVIDER`). |
| Decision model | A System One model: TypeSafe Jev through OpenRouter or directly, or a Jev-compatible server you run (Laya, OpenJev) | One request format for all of them (`app/live/jev.py`), so switching is configuration: `GW_DECISION_*` for live mapping, `GW_EXTRACT_DECISION_*` for extraction. The model only picks from options code gives it. |
| Email | SMTP with a password, or OAuth 2.0 (SASL XOAUTH2) for Gmail and Google Workspace | Sign-in links only. See Deployment, Email. |

### Live mapping

Sessions can build the map as people talk. A System One decision model (TypeSafe Jev through
OpenRouter by default; Laya or OpenJev can stand in with `GW_DECISION_PROVIDER=jev`) reads each
finished sentence and picks one change from options code gives it, at most
`GW_DECISION_MAX_OPTIONS` (20) to a question; a reasoning model reviews the whole session every
`GW_REVIEW_MINUTES` (five) minutes if anything new was said, on the facilitator's browser timer, and
keeps the map, the rule tables and the written SOP or work instruction aligned. A live change at
or above `GW_LIVE_AUTO_THRESHOLD` (0.75, a little lower for
direct instructions to the map) lands on the facilitator's canvas straight away, where they can
undo it; removals, and every reviewer, combiner and drafting change, wait for a click. Sessions run
in two passes (overview, then one person's view in detail), following Real-Life BPMN. See
[LIVE_MAPPING.md](LIVE_MAPPING.md).

### Ingestion pipeline

With `GW_PIPELINE_ENABLED=true`, every file that passes the malware check and first read (except
images placed on a map), and every ended recording, goes through job stages on the same queue
(`app/ingest/pipeline.py::STAGES`):

1. **Convert** (`convert_artifact`): MinerU, Gotenberg for older Office formats, or a native reader
   turns the file into blocks and Markdown. Audio and video files go to `transcribe_artifact`
   (Parakeet); a session's transcript goes to `ingest_recording`.
2. **Index** (`index_chunks`): chunks of at most `GW_CHUNK_TOKENS` (128), three embeddings each, in
   Qdrant.
3. **Extract** (`extract_entities`): GLiNER2 in the extraction sidecar finds entities typed by the
   pinned ontology; a decision model picks relationships from only the properties the ontology
   allows. New terms become proposals on the Terms page.
4. **Graph** (`project_graph`): mentions and relationships into Neo4j.

`topics_batch` (BERTopic) runs when an admin calls `POST /api/admin/pipeline/topics`; no screen
offers it yet. Withdrawing or purging
a file removes everything built from it (`app/ingest/cascade.py`, the `purge_external` job). A stage
whose service isn't set up ends the pipeline there. Files marked as holding personal information,
or not sure, keep their entities, but their relationships wait for a local decision model. The
search index isn't used by the interface yet. See [INGESTION.md](INGESTION.md).

### Frontend

`frontend/src` holds `pages/` (one per route in `main.tsx`), `canvas/` (React Flow nodes, the
palette, the op engine in `ops.ts` and the board's side panels), `ui/` (typed ports of the design
system's components, which screens import from `../ui`), `components/` (the shell and shared
pickers) and `lib/` (API client, session, labels, Markdown). Contributors see Share files, My files
and Process maps; for analysts My files becomes Library (every file), and they add Coverage,
Process list and Terms; admins add Pipeline, People and Retention. The router only keeps people off
pages the server would refuse.

Styles come from `frontend/design-system/`, a vendored, read-only snapshot of the YSH Internal Apps
Design System (tokens, fonts, `gw-` component classes), then `frontend/src/styles.css` for what it
doesn't cover. Fonts are self-hosted, so the app's Content-Security-Policy allows fonts from its own
origin only. See [DESIGN_SYSTEM.md](DESIGN_SYSTEM.md).

## 3. Data model

```
users ──< sessions          users: role (from settings on every request), blocked
users ──< artifacts >──< processes (artifact_processes, with step_note)
artifacts >── board          (board_id, set only for images placed on a map)
processes ── parent_id ──> processes           value chain > process
boards >── process
boards ──< recordings ──< transcript_segments
boards ──< ai_drafts
boards ──< live_utterances   (sentence, decisions, proposed changes, model, latency)
boards: version, document_version, rules_version   (a save from an older version is refused)
boards: document_markdown, document_kind   (living SOP or work instruction)
boards: session_pass, perspective, rules    (overview | detail; whose view; rule tables)
boards ──< parking_items     (problems, exceptions, workarounds, rules held for the detail pass)
artifacts | recordings ──< documents ──< chunks ──< entity_mentions, relation_assertions, chunk_tags
ontology_candidates  (proposed classes, relationships and category values, with evidence chunks)
topics ──< chunk_topics >── chunks
jobs          (profile_artifact | transcribe_segment | convert_artifact | transcribe_artifact |
               ingest_recording | index_chunks | extract_entities | project_graph |
               topics_batch | purge_external), with attempts and run_after for backoff
audit_events  (who, what, which record, when, from where)
magic_tokens  (hashed, single use, 15 minutes)
```

Artifact metadata captured at upload maps to the process evidence ledger in the research:
title and description (action), kind, layer, process links and step note (where in the
process), frequency, source system, maintainer (actor), personal information flag, whether it
is the current version, and "what would break if this disappeared tomorrow" (risk and
dependency).

## 4. Key flows

### Sign-in

1. Staff enter their work email. The API answers the same way for every address, so the form
   cannot be used to test which addresses exist.
2. If the domain is allowed and an admin hasn't removed the person's access, the API stores a
   SHA-256 hash of a random token and emails a link that lasts `GW_MAGIC_LINK_MINUTES` (15). If the
   email can't be sent, the API says so and audits the failure.
3. The link opens a page with a Continue button. The click sends a POST that consumes the token.
   Microsoft Safe Links and similar scanners open every link in an email; a link that signed
   people in on GET would be used up before they saw it.
4. The API sets an HttpOnly, SameSite=Lax session cookie for `GW_SESSION_DAYS` (14) days.
5. Every signed-in state-changing request must carry `X-Requested-With: groundwork`, which a
   cross-site form cannot send (`security.py::current_user`).

### Upload and first read

1. The browser posts each file with a JSON metadata field.
2. The API checks the extension against an allow list, streams to a temporary file with a size cap
   (`GW_MAX_UPLOAD_MB`), hashes it and hands it to storage, flags exact duplicates, links processes
   (reusing a live process with the same name, or creating the name as "proposed"), queues a
   `profile_artifact` job and writes the sidecar. Unknown processes or maps answer 404.
3. The worker checks the file with ClamAV, then profiles it. Workbooks get the outside-in review
   from the spreadsheet research: sheets and visibility, used ranges, tables, defined names, formula
   counts, merged cells, validations, conditional formats, external links, macros and data
   connections. It never modifies the file. PDFs, Word documents and plain text get text
   extraction, saved as `extracted.txt`; near-empty PDFs are flagged as likely scans.
4. With the pipeline on, the file then goes to `convert_artifact` (see Ingestion pipeline).

### Mapping session

1. The facilitator opens a map linked to a process and records who agreed to be recorded.
   Recording cannot start without that note, and the note is written to the audit log.
2. The browser records 30-second files, each from a fresh recorder so each decodes on its own,
   and uploads them as the session continues. Only the person recording (or an admin) can add
   parts or stop. Stop waits for every part to upload before it ends the recording, and the server
   accepts parts for two minutes after the end. Hourly upkeep ends a recording after 15 minutes
   without audio.
3. The transcriber worker transcribes each file. The panel polls every five seconds. With the
   pipeline on, an ended recording's transcript is ingested like a file.
4. The map autosaves 1.2 seconds after each change, with the version number it loaded. The server
   validates every map it saves (`app/canvas.py`). If someone else saved first, the save is refused
   and the person reloads. The document and the rule tables carry versions the same way.

### AI drafting

1. The server turns the canvas into structured text. It resolves which lane each element sits
   in from its position, lists connections with their labels, attaches each sticky note to the
   nearest element, and adds the findings of `ai/context.py::structure_checks`, the Real-Life BPMN
   conventions: missing start or end events, unconnected elements, decisions without a question or
   answers on their paths, parallel splits without a join, and more.
2. It adds the transcript (last 60,000 characters) and, for each file linked to the board's
   process, its metadata, first-read summary and what it says: extracted text for documents, sheet
   names and column headings for workbooks (up to 4,000 characters a file and 40,000 in all).
3. The prompt instructs the model to describe only what staff said, mark gaps as
   `[TO CONFIRM: ...]`, cite its evidence, and treat the map, transcript and files as data,
   never as instructions.
4. Three modes: SOP draft, map suggestions, next questions. Suggestions land on the canvas as
   dashed elements with Keep and Drop buttons.
5. Every draft records the provider, model and the map version it was generated from.

## 5. Security and privacy

YSH holds tenant and borrower records: identity documents, bank details, rent and repayment
history. Staff will upload them, whatever the form says. The design assumes this.

- Files stay on premises: on the host, in self-hosted object storage, and on the inference box.
  Nothing leaves the building unless a hosted AI or decision model is configured. Browser speech
  recognition in live mapping sends audio to Google or Microsoft, so it is off on maps marked as
  holding personal information.
- The personal information flag travels with each file and board, and a file marked "not sure"
  counts as personal. AI drafting and the session reviewer refuse a hosted model when the map is
  marked or any file linked to its process isn't marked "no"; the combiner, when any map it combines
  is marked; live mapping, when the map is marked; extraction holds back relationships for such
  files. `GW_AI_ALLOW_CLOUD_FOR_PERSONAL_INFO=true` lifts all of these.
- Contributors see only their own uploads. Analysts and admins see everything. Deny by default
  on the server; the UI hides nothing the server would allow. Every route that touches a map goes
  through `app/access.py::open_board` (see Decisions and known limits).
- Withdrawn files disappear from use at once, including from the search index and the graph, and
  are deleted, with everything built from them, after `GW_RETENTION_WITHDRAWN_DAYS` (30); session
  audio after `GW_RETENTION_AUDIO_DAYS` (90), keeping its transcript. The worker runs this daily
  when `GW_RETENTION_AUTO=true`; otherwise an admin runs it from the Retention page.
  Admins can also delete one file at once, with a reason (Library, "Delete now"). A purge keeps the
  database row, marked deleted, so the audit trail still shows what was shared and when it went.
- Every upload is checked by ClamAV (`clamav` service, `GW_CLAMAV_HOST`) before its first read. A
  flagged file is quarantined and can't be downloaded. While scanning is on, a file can't be
  downloaded until it has been checked.
- Audit events cover every state-changing request (a test enforces it): sign-in and out, uploads,
  downloads, withdrawals and purges, process changes and merges, board saves, recordings, live
  sentences, every AI draft decision, term decisions and pipeline runs.
- Tokens and session secrets are stored only as hashes. Roles follow `GW_ADMIN_EMAILS` and
  `GW_ANALYST_EMAILS` on every request. Admins can sign someone out everywhere or remove their access
  (People page). The worker clears expired sessions and sign-in links hourly.
- The app sends a Content-Security-Policy (scripts, fonts and connections from its own origin
  only, inline styles allowed; the API explorer at `/api/docs` is exempt), nosniff, no-referrer,
  frame denial and a microphone-only permissions policy on every response (`app/main.py`); Caddy
  adds HSTS. File types come from the extension, never the browser's claim. Only raster images
  display inline; everything else downloads, under a sandbox policy.

Before inviting all staff, complete the privacy impact assessment in
[PRIVACY.md](PRIVACY.md) against the Australian Privacy Principles: what is collected, why, who can
see it, how long it is kept, and how it is deleted. Confirm the retention periods it proposes.
Take legal advice on recording consent and on whether the lending side has additional obligations.

## 6. Deployment

One Linux host with Docker. The app, the worker and the transcriber run from one image, with
ClamAV and Caddy beside them:

```
docker compose up -d --build
```

`docker compose --profile pipeline up -d` adds the ingestion services on the host: the `converter`
and `indexer` workers (same image), Gotenberg, Qdrant and Neo4j. `--profile dev` adds Mailpit to
catch sign-in emails. The GPU services (MinerU, Parakeet, the embedding and extraction sidecars,
Laya) run on the inference box from `deploy/inference-compose.yml`, on the private network or the
tailnet only. Files move to object storage with `GW_STORAGE_BACKEND=s3`
(`deploy/supabase/README.md`). `cd backend && uv run python -m scripts.check_providers` confirms each
configured service answers.

The host must be reachable at `GW_PUBLIC_BASE_URL` from wherever staff read email, or sign-in
links will fail. Three options, set in `deploy/Caddyfile`:

| Option | When | Trade-off |
|---|---|---|
| A. Office LAN, Caddy internal certificate | Everyone works in the Salisbury office | Install Caddy's root certificate on office PCs once |
| B. Public subdomain, real certificate | Staff work from phones or home | Host must be reachable from the internet; review firewall and rate limits |
| C. Tailscale serve | Small team, some remote work | Every user needs the Tailscale app. Run `docker compose up -d app worker transcriber clamav` (no Caddy), then `tailscale serve --bg http://127.0.0.1:8000` on the host |

For a small team with some remote work, C is the safest start. Move to B when the portal
opens to everyone.

**Email.** Any SMTP service works. For Gmail and Google Workspace, Groundwork signs in with OAuth
2.0 (SASL XOAUTH2, `GW_SMTP_AUTH=xoauth2`): `backend/scripts/gmail_oauth.py` gets the refresh token
once, and the API exchanges it for short-lived access tokens. An app password also works
(`GW_SMTP_AUTH=password`) where the Workspace allows them. TLS is verified in both cases. If a
sign-in email can't be sent, the person is told to try again and the failure is audited. For
Microsoft 365, check current Microsoft guidance on SMTP authentication before relying on it.

**Backups.** `deploy/backup.sh` runs `app/backup.py`: a consistent SQLite snapshot and the local
files (`artifacts/` and `recordings/` under `GW_DATA_DIR`) in one archive, kept for
`GW_BACKUP_KEEP_DAYS` (30) in `data/backups/`. It then opens the archive to confirm the database
reads. With `GW_BACKUP_AGE_RECIPIENTS` set, the archive is encrypted with age as it is written, to
public keys whose private halves live off the host; it can only be checked on the host if
`GW_BACKUP_AGE_IDENTITY_FILE` is set, so test restores where the key is kept. `GW_BACKUP_COPY_TO`
copies backups elsewhere with rsync, and the script refuses to copy them unencrypted. With
`GW_STORAGE_BACKEND=s3` the files live in Supabase Storage, so back up its volume separately.
Qdrant and Neo4j are rebuilt from the database. Schedule it nightly. See the README.

## 7. Rollout plan

The portal is a change tool as much as a technical one. It builds familiarity with AI tooling in
a setting where nothing breaks if someone gets it wrong.

| Phase | Weeks | Scope | Exit evidence |
|---|---|---|---|
| 0. Private | 1 | You and Dean. Seed and rename the process catalogue. Load your own interview notes. | Catalogue confirmed by Dean |
| 1. Pilot | 2 to 3 | Three to five staff from different roles. Uploads only. Watch them use it. | Each pilot user shares at least three files without help |
| 2. Mapping | 3 to 6 | Run facilitated sessions per process, recorded, with AI drafts reviewed live. | One SOP per core process confirmed by its doer |
| 3. Everyone | 6+ | Open to all staff. Weekly reminder of what's been learnt. | Coverage view shows evidence for every core process |

Measure contribution, not logins: files per process, share of workaround-layer files, processes
with at least one map, drafts accepted versus discarded, and the open `[TO CONFIRM]` count.

## 8. Roadmap

Ordered by value to the discovery work.

Done: the coverage view (processes by evidence layer, contributor and map status), the process
list (rename, merge, confirm, retire, assign owner), retention and purge, malware scanning, and
the ingestion pipeline (Markdown with OCR for scans and photos, hybrid index, ontology-typed
knowledge graph, term proposals, topics, purges that reach every store), object storage over S3,
encrypted off-host backups, sign-in email through Gmail with OAuth 2.0, Laya as a local decision
model, the YSH Internal Apps Design System, and the pre-pilot audit fixes ([AUDIT.md](AUDIT.md)).

1. Use the index: retrieval for AI drafts and reviews in place of the first 4,000 characters of
   each file, and a search page.
2. A graph view per process: entities, relationships and the chunks behind them.
3. Evidence ledger view per process, combining artifacts, map elements and transcript quotes.
4. BPMN 2.0 XML export, so maps open in other tools.
5. Deeper workbook review: formula-pattern anomalies, hard-coded values inside formula ranges,
   lookup chains across files.
6. Real-time co-editing (Yjs) if facilitated sessions outgrow autosave with conflict detection.
7. Speaker labels in transcripts.
8. Local streaming speech recognition for live mapping, replacing the browser's cloud service.
9. Run the session reviewer on the server so it continues when the facilitator's tab closes.
10. Compound sentences: split with an LLM and interpret each part, as in TypeSafe's smart-home demo.

## 9. Decisions and known limits

- **Boards are shared.** Any signed-in person with a board's link can open it, and so can see its
  images; the map list still shows contributors only the maps they started. Tighten in
  `app/access.py::can_open_board` if a board ever holds material only some staff should see; every
  map route goes through `open_board`, which calls it, and a test checks that.
- **Near-live transcription.** Text appears about 30 to 60 seconds behind speech. True streaming
  needs a WebSocket and a streaming speech model; not worth it for mapping sessions.
- **AI generation is synchronous.** A local 14B model can take a minute. Move it to the job
  queue if that becomes a problem.
- **Several workers, one database file.** One reads files and one transcribes; with the pipeline,
  a converter and an indexer join them. SQLite serialises writes and each waits up to 30 seconds
  for a lock, which is plenty for an office. Long stages send a heartbeat so a slow MinerU or
  Parakeet job isn't taken for a crashed one. Very large workbooks get a lighter read, and Office
  files that expand to an unusual size aren't opened.
- **In-memory rate limit** on sign-in requests. Resets on restart. Adequate behind Tailscale or a
  LAN; add Caddy rate limiting if the portal is exposed publicly.
- **Malware scanning needs memory.** The ClamAV container wants about 2 GB. On a small host, set
  `GW_CLAMAV_HOST` empty during the private pilot and switch it on before opening the portal wider.
