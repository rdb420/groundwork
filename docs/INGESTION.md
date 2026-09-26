# Ingestion pipeline

Every file staff share, and every recorded mapping session, becomes:

- clean Markdown, kept with the original in object storage,
- small chunks with three embeddings each, in Qdrant, for search and AI drafts,
- entities and relationships typed against YSH's property ontology, in a Neo4j knowledge graph,
- proposals for terms the ontology doesn't have yet, for an analyst to decide.

Everything runs on-prem. The only hosted call is the Jev decision model (on OpenRouter, or TypeSafe
directly), and it never sees files marked as holding personal information (or not sure) unless that
is explicitly allowed (`GW_AI_ALLOW_CLOUD_FOR_PERSONAL_INFO`).

## Flow

```
share a file ─ malware check ─ first read ─┐
                                           ▼
                                   convert_artifact ── pdf, images, docx, pptx ─▶ MinerU (mineru-api)
                                           │           doc, ppt, odt, rtf, xls, ods ─▶ Gotenberg ─▶ PDF ─▶ MinerU
                                           │           xlsx, xlsm, csv, tsv ─▶ native tables · txt, md ─▶ as is
                                           │           eml ─▶ body + attachments · svg ─▶ its text
                                           │           audio, video ─▶ transcribe_artifact (Parakeet)
record a session ─ parts transcribed (Parakeet) ─ ended ─▶ ingest_recording
                                           ▼
                                   document: document.md, blocks.json, images ─▶ object storage
                                           ▼
                                   index_chunks ─ chunker (≤128 tokens) ─ embedding sidecar ×3 ─▶ Qdrant
                                           ▼
                                   extract_entities ─ GLiNER2 spans and tags ─ Jev relationships ─▶ SQL
                                           ▼
                                   project_graph ─▶ Neo4j
```

Each arrow is a job on Groundwork's existing queue (`STAGES` in `app/ingest/pipeline.py`). Stages are
idempotent: they skip work whose inputs haven't changed (the file's hash, the Markdown's hash, the
chunker version and chunk size, the ontology version and extraction thresholds). Images placed on a
map's canvas aren't put through the pipeline.
The SQL tables (`documents`, `chunks`, `entity_mentions`, `relation_assertions`, `chunk_tags`,
`ontology_candidates`, `topics`, `chunk_topics`) are the source of truth; Qdrant and Neo4j are rebuilt
from them with **Index again** and **Rebuild the graph** under "Reprocess everything" on the Pipeline
page.

## Services

| Service | Where | What | Setting |
|---|---|---|---|
| Object storage | Office host | Self-hosted Supabase Storage, S3 endpoint (`deploy/supabase/README.md`) | `GW_STORAGE_BACKEND=s3`, `GW_S3_*` |
| MinerU | Inference box | `mineru-api`; `hybrid-engine` on the 3090, `pipeline` on CPU | `GW_MINERU_URL`, `GW_MINERU_BACKEND` |
| Gotenberg | Office host | LibreOffice behind HTTP, older Office formats to PDF | `GW_GOTENBERG_URL` |
| Parakeet | Inference box | `rdb420/parakeet-transcription-app`, Gradio HTTP API | `GW_TRANSCRIPTION_PROVIDER=parakeet`, `GW_PARAKEET_URL` |
| Embedding sidecar | Inference box | `rdb420/embedding-sidecar`: MiniLM dense, SPLADE sparse, ColBERT | `GW_EMBED_URL` |
| Qdrant | Office host | 1.18.2, TLS, API key (`deploy/qdrant/README.md`) | `GW_QDRANT_*` |
| Extraction sidecar | Inference box | `deploy/extraction-sidecar`: GLiNER2 and BERTopic | `GW_EXTRACT_URL` |
| Jev | OpenRouter | Close calls between classes, relationship choices | `GW_DECISION_*` |
| Laya | Inference box | `laya` in `deploy/inference-compose.yml`: the local decision model, Jev's API | `GW_EXTRACT_DECISION_*` |
| Neo4j | Office host | The graph, Query API | `GW_NEO4J_*` |

Start the office-host services with `docker compose --profile pipeline up -d`, and the GPU services
on the inference box with `docker compose -f deploy/inference-compose.yml up -d --build` (after cloning
the sources listed at the top of that file). Check them
with `cd backend && uv run python -m scripts.check_providers`, then set `GW_PIPELINE_ENABLED=true`
and use **Queue files shared before the pipeline** on the Pipeline page.

A stage whose service isn't set up ends the pipeline there: without `GW_EMBED_URL` files stop after
conversion, without `GW_EXTRACT_URL` after indexing, without `GW_NEO4J_URL` after extraction.

The `pipeline` profile adds two workers. `converter` runs `convert_artifact` and
`transcribe_artifact`, which wait on MinerU and Parakeet. `indexer` runs `ingest_recording`,
`index_chunks`, `extract_entities`, `project_graph`, `purge_external` and `topics_batch`. Within a
worker, jobs run in the order of `PRIORITY` in `app/worker.py`: removals before conversion, then the
stages in pipeline order, topics last. A failed job tries again after 30 seconds, then 2 minutes, and
fails for good after three tries; the Pipeline page lists those under "Failed for good".

## Conversion

MinerU gets PDFs in windows of `GW_MINERU_PAGE_BATCH` (50) pages. Its `content_list` (headings with
levels, paragraphs, lists, HTML tables, image captions, each with a page) becomes Groundwork's
**blocks** (`app/ingest/blocks.py`), the one format every converter produces. Page headers, footers
and numbers are dropped. Spreadsheets and CSV files are read natively so every row survives (up to
5,000 rows and 40 columns a sheet, hidden sheets marked). An email's attachments are converted one
level deep. Anything that can't be converted is recorded as skipped, with the reason.

## Chunking

At most `GW_CHUNK_TOKENS` (128) tokens, counted with the BERT uncased tokenizer all three
embedding models share. It is committed with the code
(`backend/app/ingest/data/bert-base-uncased-tokenizer.json`), so counting needs no download:

- a new heading always starts a new chunk;
- each chunk's embedded text begins with its heading breadcrumb ("Head lease > Rent > Arrears"),
  capped at 24 tokens;
- paragraphs split on line breaks, then sentences, then token boundaries;
- tables pack by row, with the header row repeated in every chunk (a header too wide to repeat is
  dropped, and long rows become "column: value" lines);
- images get chunks of their own, and text and transcript lines never share one;
- pages (files) and start and end times (transcripts) carry through;
- a short last chunk joins the one before it in the same section.

## Search

`app/ingest/retrieve.py::search` takes dense and sparse candidates (50 each) and reranks them
together with ColBERT MaxSim. Contributors find only their own files and shared sessions; withdrawn,
blocked and deleted files never come back. Nothing in the interface uses it yet; AI drafts and a search
page come next.

## Extraction

Closed to the pinned ontology (`backend/ontology/pbo-<version>/`, from `rdb420/property_ontology`):

1. **Entities.** GLiNER2 looks for the ontology's concrete classes, with their definitions as label
   descriptions, in groups of up to 15, plus one catch-all label.
2. **Close calls.** When two classes are nearly tied for one span, Jev picks between just those.
3. **Tags.** GLiNER2's classifier tags each chunk with SKOS concepts (lease types, risk categories
   and so on).
4. **Relationships.** For mention pairs in the same chunk, nearest first (up to
   `GW_EXTRACT_MAX_PAIRS`, 12, a chunk), Jev chooses from only the ontology properties whose domain
   and range fit the two classes, plus the roles a party can hold in an agreement, asset, project or
   business (the Participation pattern), plus "none" and "another relationship". More than 18
   options become two questions (which group, then which option), so none has more than 20. With the
   `laya` flavour the groups hold at most 8, because Laya's options share a 192-token budget.
5. **Resolution.** Same class plus same normalised name is the same entity. Legal suffixes and
   honorifics are dropped for parties.

GLiNER2 keeps spans and tags at or above `GW_EXTRACT_THRESHOLD` (0.5); a relationship needs Jev's
confidence at or above `GW_EXTRACT_RELATION_THRESHOLD` (0.5).

Chunk text reaches Jev only as data in `state`. Files marked as personal (or not sure) keep their
entities but wait for a local decision model (`GW_EXTRACT_DECISION_URL` with
`GW_EXTRACT_DECISION_IS_LOCAL=true`, or a live-mapping model with `GW_DECISION_PROVIDER=jev` and
`GW_DECISION_IS_LOCAL=true`) for relationships; they show as "Partly read" ("Partly done" on the
Pipeline page, where **Try again** extracts them again). A session counts as personal if its map is
marked so, or any file on its process isn't marked "no". Laya on the
inference box is that local model: on the relationship sample it scored 13 to 14 of 17 against
Jev's 15 (see LIVE_MAPPING.md, "Laya, the local decision model"). With no decision model set up at
all, every file keeps its entities and tags and its relationships wait the same way. Names are
kept as found and flagged `personal_info` in the graph.

Extraction uses its own `GW_EXTRACT_DECISION_*` settings when `GW_EXTRACT_DECISION_URL` is set, and
the live-mapping decision model otherwise. `GW_EXTRACT_DECISION_MODEL` falls back to
`GW_DECISION_MODEL`. `GW_EXTRACT_DECISION_FLAVOUR` (`jev` or `laya`) sets how questions are phrased;
left empty it is `jev` for extraction's own URL, or `GW_DECISION_FLAVOUR` for the live-mapping model.
For Laya, set it to `laya` explicitly.

Measure extraction on labelled YSH chunks before switching it on for everyone:
`uv run python -m scripts.extract_eval scripts/eval/extract_sample.jsonl`. To compare decision models
on the relationship questions alone, without the extraction sidecar, add `--gold-mentions` and use
`scripts/eval/relations_sample.jsonl`.

## The ontology and proposals

The ontology is never edited from Groundwork. Each snapshot is checked against its
`model.json.sha256`, and one that doesn't match is refused. Catch-all spans, "another relationship"
answers and topics that match no concept become **proposals** on the Terms page, with the text they
came from. An analyst accepts, merges into an existing term, or rejects each, and can reopen a
decision until it is exported. **Export accepted terms for the ontology** (shown under Accepted or
Merged) produces a Markdown summary and YAML term entries for `build/build_model.py` in
`property_ontology`, and marks those proposals exported. Once a new version is built and released
there:

```bash
cd backend
gh api "repos/rdb420/property_ontology/contents/property-ontology/model.yaml?ref=<commit>" --jq .content \
  | base64 -d > /tmp/model.yaml
uv run --with pyyaml python -m scripts.vendor_ontology /tmp/model.yaml --version <version> --ref <commit>
```

Then set `GW_ONTOLOGY_VERSION` and use **Extract again** on the Pipeline page.

## Topics

`POST /api/admin/pipeline/topics` (admins only; the Pipeline page has no button for it yet) fits
BERTopic on everything indexed (at least `GW_TOPICS_MIN_CHUNKS`, 500, chunks), guided by seed words
from the SKOS concepts. Each run replaces the topics before it. A topic that matches a concept is
linked to it; one that matches nothing becomes a proposal. The published arXiv and Wikipedia topic
models don't know property work, so they aren't used.

## The graph

```
(:OntClass)-[:SUBCLASS_OF]->(:OntClass), (:OntProperty), (:Concept {scheme}), (:OntologyVersion)
(:Source)-[:HAS_CHUNK]->(:Chunk)<-[:MENTIONED_IN]-(:Entity:<Class>)-[:INSTANCE_OF]->(:OntClass)
(:Entity)-[:<property> {sources, confidence, model, status: 'draft', ontology_version}]->(:Entity)
(ctx)-[:hasParticipation]->(:Entity:Participation)-[:participant]->(party), -[:inRole]->(:Concept)
(:Chunk)-[:TAGGED]->(:Concept)
```

No chunk text is copied into the graph. Every relationship lists the chunks that support it. The
ontology's classes, properties and concepts are loaded once per pinned version.

## Removal

Withdrawing a file takes it out of Qdrant and the graph at once. The retention purge (or an admin's
**Delete now**) then removes everything else:

- the stored files and conversions;
- the SQL documents, chunks, entities, relationships, tags and topic links;
- its evidence on open proposals, deleting any proposal left with no evidence;
- through the `purge_external` job, retried like every job (see Services) and listed under
  "Failed for good" on the Pipeline page if it never succeeds:
  - its Qdrant points,
  - its part of the graph, including relationships left with no supporting chunk and entities
    nothing mentions any more,
  - its stored files, if the purge couldn't delete them at the time.

Deleting a session's audio keeps its transcript and chunks, as before.
