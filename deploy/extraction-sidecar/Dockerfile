# Groundwork extraction sidecar (GLiNER2 + BERTopic). GPU image; runs on CPU too (DEVICE=cpu).
FROM pytorch/pytorch:2.8.0-cuda12.8-cudnn9-runtime
COPY --from=ghcr.io/astral-sh/uv:0.12.18 /uv /bin/
ENV PYTHONUNBUFFERED=1 HF_HOME=/data/huggingface UV_LINK_MODE=copy UV_SYSTEM_PYTHON=1
WORKDIR /app
COPY pyproject.toml ./
RUN uv pip install --system -r pyproject.toml
COPY app.py ./
ARG PREFETCH_MODEL=false
RUN if [ "$PREFETCH_MODEL" = "true" ]; then python -c "import app; app.gliner()"; fi
RUN useradd --system --uid 1001 sidecar && mkdir -p /data && chown sidecar /data
USER sidecar
EXPOSE 7870
HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:7870/health')"
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7870", "--workers", "1"]
