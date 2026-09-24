# Extraction sidecar

GLiNER2 (entities with character spans, chunk tags) and BERTopic (themes) for Groundwork's
ingestion pipeline. Groundwork calls it at `GW_EXTRACT_URL`. See `app.py` for the API.

```bash
docker build -t groundwork-extraction --build-arg PREFETCH_MODEL=true .
docker run -d --gpus all -p 7870:7870 -v extraction_data:/data --name extraction groundwork-extraction
curl localhost:7870/health
```

- `GLINER2_MODEL`: `fastino/gliner2-large-v1` (default; 340M parameters, about 2 GB of VRAM) or
  `fastino/gliner2-base-v1` for CPU-only boxes.
- `DEVICE`: `cuda` (default, falls back to CPU) or `cpu`.
- No authentication: keep it on the private network or the tailnet, like the embedding sidecar.
- It never logs the texts it receives.

Before switching the pipeline on for everyone, measure it on labelled YSH chunks with
`backend/scripts/extract_eval.py`.
