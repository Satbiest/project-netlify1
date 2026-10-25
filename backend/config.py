"""Server-side configuration; secrets never reach the frontend."""
from pathlib import Path
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / '.env', extra='ignore')
    gemini_api_key: SecretStr = SecretStr('')
    gemini_model: str = 'gemini-3.5-flash-lite'
    embedding_model: str = 'sentence-transformers/all-MiniLM-L6-v2'
    max_upload_mb: int = Field(default=5, ge=1, le=20)
    max_pdf_pages: int = Field(default=10, ge=1, le=50)
    max_resume_chars: int = Field(default=40000, ge=1000, le=100000)
    max_job_chars: int = Field(default=12000, ge=100, le=30000)
    ai_timeout_seconds: int = Field(default=90, ge=5, le=180)
    analysis_timeout_seconds: int = Field(default=210, ge=10, le=600)
    max_concurrent_analyses: int = Field(default=1, ge=1, le=8)
    enable_demo: bool = True
    allowed_origins: list[str] = Field(default_factory=list)

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

