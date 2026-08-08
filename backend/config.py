from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment configuration. Values come from backend/.env or the shell."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "models/gemma-4-31b-it"
    DATABASE_URL: str = "sqlite:///./careeros.db"
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    @field_validator("DATABASE_URL")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        """Hosted Postgres providers (Neon, Vercel Postgres, etc.) hand out
        postgres:// or postgresql:// connection strings. SQLAlchemy accepts
        both but defaults an unqualified scheme to psycopg2, which isn't a
        dependency here — rewrite either to name the psycopg3 driver
        explicitly so pasting a provider's URL in as-is just works."""
        if value.startswith("postgres://"):
            return "postgresql+psycopg://" + value[len("postgres://") :]
        if value.startswith("postgresql://"):
            return "postgresql+psycopg://" + value[len("postgresql://") :]
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()
