"""Runtime configuration. Every value can be set in .env or the environment (prefix GW_)."""
import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# The repo-root .env (shared with docker compose) is read first; a backend/.env overrides it.
# GW_ENV_FILES replaces the list (comma separated); the tests set it empty to ignore local files.
ENV_FILES = tuple(f for f in os.environ.get("GW_ENV_FILES", "../.env,.env").split(",") if f) or None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILES, env_prefix="GW_", extra="ignore")

    # Identity
    org_name: str = "YSH"
    app_name: str = "Groundwork"
    public_base_url: str = "http://localhost:5173"  # where staff open the portal; used in magic links

    # Storage
    data_dir: Path = Path("../data")
    database_url: str = ""  # defaults to sqlite in data_dir
    max_upload_mb: int = 100
    backup_keep_days: int = 30
    # age public keys (age1...), comma separated. Set them and every backup is encrypted to them.
    backup_age_recipients: str = ""
    # Optional private key file for checking encrypted backups on this host. Better kept elsewhere.
    backup_age_identity_file: str = ""

    # Retention (see docs/PRIVACY.md). 0 keeps forever. With retention_auto the worker purges what is
    # due once a day; otherwise an admin runs it from the Retention page.
    retention_withdrawn_days: int = 30  # files withdrawn by their contributor
    retention_audio_days: int = 90  # session audio, counted from the end of the recording
    retention_auto: bool = False

    # Where files live: local (under data_dir) or s3 (self-hosted Supabase Storage's S3 endpoint, or MinIO)
    storage_backend: str = "local"
    s3_endpoint: str = ""  # e.g. http://supabase-host:8000/storage/v1/s3
    s3_region: str = "local"
    s3_bucket: str = "groundwork"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_ca_file: str = ""

    # Ingestion pipeline: convert to Markdown, chunk, embed, index, extract, graph (docs/INGESTION.md)
    pipeline_enabled: bool = False
    mineru_url: str = ""  # mineru-api, e.g. http://inference:8000
    mineru_backend: str = "pipeline"  # pipeline (CPU or GPU) | hybrid-engine | vlm-engine (GPU)
    mineru_lang: str = "en"
    mineru_page_batch: int = 50  # pages per MinerU task for long PDFs
    mineru_timeout_s: int = 1800
    gotenberg_url: str = ""  # converts doc, ppt, odt, rtf to PDF
    embed_url: str = ""  # the embedding sidecar; empty stops the pipeline after conversion
    chunk_tokens: int = 128  # the smallest window of the three embedding models
    qdrant_url: str = ""  # e.g. https://inference:6333
    qdrant_api_key: str = ""
    qdrant_ca_file: str = ""  # the CA for Qdrant's own TLS certificate
    qdrant_collection: str = "gw_chunks"  # an alias; the physical collection is <alias>_v<layout>
    extract_url: str = ""  # the extraction sidecar (GLiNER2); empty stops the pipeline after indexing
    ontology_version: str = "0.1.0"  # vendored under backend/ontology/pbo-<version>/
    extract_threshold: float = 0.5  # GLiNER2 confidence for entity spans and chunk tags
    extract_relation_threshold: float = 0.5  # Jev confidence to keep a relationship
    extract_max_pairs: int = 12  # mention pairs asked about per chunk, nearest first
    # Extraction can use its own Jev-compatible server (e.g. a local Laya or OpenJev for files with
    # personal information); empty uses the live-mapping decision model.
    extract_decision_url: str = ""
    extract_decision_api_key: str = ""
    extract_decision_is_local: bool = False
    topics_min_chunks: int = 500  # BERTopic needs enough text to find stable themes
    neo4j_url: str = ""  # e.g. http://neo4j:7474 (the Query API); empty stops the pipeline after extraction
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""
    neo4j_database: str = "neo4j"

    # Malware scanning of uploads with ClamAV (clamd over TCP). Empty host switches scanning off.
    clamav_host: str = ""
    clamav_port: int = 3310

    # Auth
    allowed_email_domains: str = ""  # comma separated; empty accepts any domain (dev only)
    admin_emails: str = ""  # comma separated; admin role
    analyst_emails: str = ""  # comma separated; can see every upload and board
    magic_link_minutes: int = 15
    session_days: int = 14
    cookie_secure: bool = False  # true behind HTTPS
    dev_log_magic_links: bool = True  # print links to the console when SMTP is not configured

    # Email
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_starttls: bool = True
    mail_from: str = "groundwork@localhost"

    # AI
    ai_provider: str = "none"  # none | ollama | anthropic | openai
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:14b"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5"
    ai_allow_cloud_for_personal_info: bool = False

    # Extra provider for the session reviewer (any OpenAI-compatible chat endpoint)
    openai_url: str = "https://api.openai.com/v1/chat/completions"
    openai_api_key: str = ""
    openai_model: str = ""  # set explicitly, e.g. the GPT model you have access to
    openai_is_local: bool = False  # true if openai_url points at a model on your own hardware

    # Live mapping: a System One decision model. openrouter runs TypeSafe Jev through OpenRouter's
    # System One API; jev calls TypeSafe directly or a Jev-compatible server you run (Laya, OpenJev).
    decision_provider: str = "none"  # none | openrouter | jev
    decision_url: str = "https://api.typesafe.ai/v1/systemone"  # used by the jev provider
    decision_api_key: str = ""  # used by the jev provider
    openrouter_url: str = "https://openrouter.ai/api/v1/systemone"
    openrouter_api_key: str = ""
    decision_model: str = "jev-latest"  # OpenRouter routes this to ~typesafe/jev-latest
    decision_is_local: bool = False  # true when decision_url is a server you run
    decision_max_options: int = 20  # keep Choice questions portable to Laya and OpenJev
    live_auto_threshold: float = 0.75  # at or above this confidence, changes apply without a click
    review_minutes: int = 5

    # Transcription
    transcription_provider: str = "none"  # none | parakeet | faster_whisper | openai_compatible
    parakeet_url: str = ""  # rdb420/parakeet-transcription-app, e.g. http://inference:7861
    recording_chunk_seconds: int = 30  # length of each recorded part (SessionPanel CHUNK_MS)
    whisper_model: str = "small.en"
    transcription_url: str = ""  # openai_compatible endpoint, e.g. http://inference:8000/v1/audio/transcriptions
    transcription_api_key: str = ""

    @property
    def decision_local(self) -> bool:
        """OpenRouter is always hosted; only a jev URL on your own hardware counts as local."""
        return self.decision_provider == "jev" and self.decision_is_local

    @property
    def db_url(self) -> str:
        return self.database_url or f"sqlite:///{(self.data_dir / 'groundwork.db').resolve()}"

    @staticmethod
    def _csv(v: str) -> set[str]:
        return {x.strip().lower() for x in v.split(",") if x.strip()}

    @property
    def domains(self) -> set[str]:
        return self._csv(self.allowed_email_domains)

    @property
    def admins(self) -> set[str]:
        return self._csv(self.admin_emails)

    @property
    def analysts(self) -> set[str]:
        return self._csv(self.analyst_emails)


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.data_dir.mkdir(parents=True, exist_ok=True)
    return s
