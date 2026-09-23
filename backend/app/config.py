"""Runtime configuration. Every value can be set in .env or the environment (prefix GW_)."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="GW_", extra="ignore")

    # Identity
    org_name: str = "YSH"
    app_name: str = "Groundwork"
    public_base_url: str = "http://localhost:5173"  # where staff open the portal; used in magic links

    # Storage
    data_dir: Path = Path("../data")
    database_url: str = ""  # defaults to sqlite in data_dir
    max_upload_mb: int = 100
    backup_keep_days: int = 30

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
    ai_provider: str = "none"  # none | ollama | anthropic
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

    # Live mapping: a System One decision model (TypeSafe Jev, or a Jev-compatible server
    # such as Laya or OpenJev running on your own hardware)
    decision_provider: str = "none"  # none | jev
    decision_url: str = "https://api.typesafe.ai/v1/systemone"
    decision_api_key: str = ""
    decision_model: str = "jev-latest"
    decision_is_local: bool = False  # true when decision_url is a server you run
    decision_max_options: int = 20  # keep Choice questions portable to Laya and OpenJev
    live_auto_threshold: float = 0.75  # at or above this confidence, changes apply without a click
    review_minutes: int = 5

    # Transcription
    transcription_provider: str = "none"  # none | faster_whisper | openai_compatible
    whisper_model: str = "small.en"
    transcription_url: str = ""  # openai_compatible endpoint, e.g. http://inference:8000/v1/audio/transcriptions
    transcription_api_key: str = ""

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
