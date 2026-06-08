from __future__ import annotations

from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Macaronys Assignment Backend"
    app_env: Literal["development", "test", "production"] = "development"
    app_timezone: str = "Asia/Seoul"
    auto_create_tables: bool = True

    database_url: str = (
        "postgresql://USER:PASSWORD@HOST/DATABASE?sslmode=require"
    )

    ai_execution_mode: Literal["server", "local"] = "local"
    server_ollama_enabled: bool = False
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "gemma3:4b"
    ollama_auto_pull: bool = False
    ollama_timeout_seconds: int = 300

    worker_token: str = ""
    worker_claim_timeout_seconds: int = 900
    server_base_url: str = "http://localhost:8000"
    ai_job_poll_seconds: float = 2.0
    ai_worker_concurrency: int = 2

    upload_dir: str = "data/uploads"
    max_upload_size_mb: int = 1024

    notification_dispatch_batch_size: int = 20
    discord_webhook_url: str | None = None
    discord_bot_token: str | None = None
    discord_sync_commands: bool = True
    # NEIS 학교 정보 API
    neis_api_key: str = ""
    neis_atpt_code: str = "R10"          # 경상북도교육청
    neis_school_code: str = "8750829"    # 경북소프트웨어마이스터고등학교

    @model_validator(mode="after")
    def normalize_neis_school_codes(self) -> Settings:
        # 이전 설정값은 대구교육청 코드라 경북소프트웨어마이스터고가 조회되지 않는다.
        if self.neis_atpt_code == "D10" and self.neis_school_code == "7890292":
            self.neis_atpt_code = "R10"
            self.neis_school_code = "8750829"
        if self.ai_worker_concurrency < 1:
            self.ai_worker_concurrency = 1
        return self

    log_level: str = "INFO"
    host: str = "0.0.0.0"
    port: int = 8000


settings = Settings()
