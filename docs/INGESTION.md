# Ingestion pipeline

Every file staff share, and every recorded mapping session, becomes:

- clean Markdown, kept with the original in object storage,
- small chunks with three embeddings each, in Qdrant, for search and AI drafts,
- entities and relationships typed against YSH's property ontology, in a Neo4j knowledge graph,
- proposals for terms the ontology doesn't have yet, for an analyst to decide.

Everything runs on-prem. The only hosted call is the Jev decision model on OpenRouter, and it never
sees files marked as holding personal information (or not sure) unless that is explicitly allowed.

## Flow

```
share a file ─ malware check ─ first read ─┐
                                           ▼
                                   convert_artifact ── pdf, images, docx, pptx ─▶ MinerU (mineru-api)
                                           │           doc, ppt, odt, rtf, xls, ods ─▶ Gotenberg ─▶ PDF ─▶ MinerU
                                           │           xlsx, csv ─▶ native tables · txt, md ─▶ as is
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

Each arrow is a job on Groundwork's existing queue. Stages are idempotent: they skip work whose
inputs haven't changed (the file's hash, the Markdown's hash, the chunker and ontology versions).
The SQL tables (`documents`, `chunks`, `entity_mentions`, `relation_assertions`, `chunk_tags`,
`ontology_candidates`, `topics`) are the source of truth; Qdrant and Neo4j are rebuilt from them with
**Reprocess** on the Pipeline page.

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
| Jev | OpenRouter, or local | Relationship choices | `GW_DECISION_*`, `GW_EXTRACT_DECISION_*` |
| Neo4j | Office host | The graph, Query API | `GW_NEO4J_*` |

Start the office-host services with `docker compose --profile pipeline up -d`, and the GPU services
on the inference box with `docker compose -f deploy/inference-compose.yml up -d --build`. Check them
with `cd backend && uv run python -m scripts.check_providers`, then set `GW_PIPELINE_ENABLED=true`
and use **Queue files shared before the pipeline** on the Pipeline page.

A stage whose service isn't set up ends the pipeline there: without `GW_EMBED_URL` files stop after
conversion, without `GW_EXTRACT_URL` after indexing, without `GW_NEO4J_URL` after extraction.

## Conversion

MinerU gets PDFs in windows of `GW_MINERU_PAGE_BATCH` pages. Its `content_list` (headings with
levels, paragraphs, lists, HTML tables, image captions, each with a page) becomes Groundwork's
**blocks**, the one format every converter produces. Page headers, footers and numbers are dropped.
Spreadsheets are read natively so every row survives (up to 5,000 rows and 40 columns a sheet,
hidden sheets marked). Anything that can't be converted is recorded as skipped, with the reason.

## Chunking

At most `GW_CHUNK_TOKENS` (128) tokens, counted with the BERT uncased tokenizer all three
embedding models share:

- a new heading always starts a new chunk;
- each chunk's embedded text begins with its heading breadcrumb ("Head lease > Rent > Arrears"),
  capped at 24 tokens;
- paragraphs split on line breaks, then sentences, then token boundaries;
- tables pack by row, with the header row repeated in every chunk;
- pages (files) and start and end times (transcripts) carry through;
- a short last chunk joins the one before it in the same section.

## Search

`app/ingest/retrieve.py::search` takes dense and sparse candidates (50 each) and reranks them
together with ColBERT MaxSim. Contributors find only their own files and shared sessions; withdrawn
and deleted files never come back. Nothing in the interface uses it yet; AI drafts and a search
page come next.

## Extraction

Closed to the pinned ontology (`backend/ontology/pbo-<version>/`, from `rdb420/property_ontology`):

1. **Entities.** GLiNER2 looks for the ontology's concrete classes, with their definitions as label
   descriptions, in groups of up to 15, plus one catch-all label.
2. **Close calls.** When two classes are nearly tied for one span, Jev picks between just those.
3. **Tags.** GLiNER2's classifier tags each chunk with SKOS concepts (lease types, risk categories
   and so on).
4. **Relationships.** For mention pairs in the same chunk, nearest first, Jev chooses from only the
   ontology properties whose domain and range fit the two classes, plus the roles a party can hold
   in an agreement, asset, project or business (the Participation pattern), plus "none" and "another
   relationship". More than 18 options become two questions, so none has more than 20.
5. **Resolution.** Same class plus same normalised name is the same entity. Legal suffixes and
   honorifics are dropped for parties.

Chunk text reaches Jev only as data in `state`. Files marked as personal (or not sure) keep their
entities but wait for a local decision model (`GW_EXTRACT_DECISION_URL` with
`GW_EXTRACT_DECISION_IS_LOCAL=true`) for relationships; they show as "Partly read". Laya on the
inference box is that local model: on the relationship sample it scored 13 to 14 of 17 against
Jev's 15 (see LIVE_MAPPING.md, "Laya, the local decision model"). Names are
kept as found and flagged `personal_info` in the graph.

Measure extraction on labelled YSH chunks before switching it on for everyone:
`uv run python -m scripts.extract_eval scripts/eval/extract_sample.jsonl`.

## The ontology and proposals

The ontology is never edited from Groundwork. Catch-all spans, "another relationship" answers and
topics that match no concept become **proposals** on the Terms page, with the text they came from.
An analyst accepts, merges into an existing term, or rejects each. **Export** produces a Markdown
summary and YAML term entries for `build/build_model.py` in `property_ontology`. Once a new version
is built and released there:

```bash
cd backend
gh api "repos/rdb420/property_ontology/contents/property-ontology/model.yaml?ref=<commit>" --jq .content \
  | base64 -d > /tmp/model.yaml
uv run --with pyyaml python -m scripts.vendor_ontology /tmp/model.yaml --version <version> --ref <commit>
```

Then set `GW_ONTOLOGY_VERSION` and use **Extract again** on the Pipeline page.

## Topics

**Pipeline > Find topics** fits BERTopic on everything indexed (at least `GW_TOPICS_MIN_CHUNKS`
chunks), guided by seed words from the SKOS concepts. The published arXiv and Wikipedia topic models
don't know property work, so they aren't used.

## The graph

```
(:Source)-[:HAS_CHUNK]->(:Chunk)<-[:MENTIONED_IN]-(:Entity:<Class>)-[:INSTANCE_OF]->(:OntClass)
(:Entity)-[:<property> {sources, confidence, model, status: 'draft'}]->(:Entity)
(ctx)-[:hasParticipation]->(:Entity:Participation)-[:participant]->(party), -[:inRole]->(:Concept)
(:Chunk)-[:TAGGED]->(:Concept)
```

No chunk text is copied into the graph. Every relationship lists the chunks that support it.

## Removal

Withdrawing a file takes it out of Qdrant and the graph at once. The retention purge (or an admin's
**Delete now**) then removes everything else:

- the stored files and conversions;
- the SQL documents, chunks, entities, relationships and tags;
- its evidence on open proposals, deleting any proposal left with no evidence;
- through the `purge_external` job, which retries until each store has answered:
  - its Qdrant points,
  - its part of the graph, including relationships left with no supporting chunk and entities
    nothing mentions any more.

Deleting a session's audio keeps its transcript and chunks, as before.
