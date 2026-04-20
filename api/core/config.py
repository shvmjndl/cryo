import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")


class Settings:
    # Postgres
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", "5432"))
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "cryo")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "cryo")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "cryo_secret_change_me")

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def DATABASE_URL_SYNC(self) -> str:
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # API
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    API_SECRET_KEY: str = os.getenv("API_SECRET_KEY", "change-me")
    CORS_ORIGINS: list[str] = os.getenv(
        "API_CORS_ORIGINS", "http://localhost:3000,http://localhost:5173"
    ).split(",")

    # JWT
    JWT_SECRET: str = os.getenv("JWT_SECRET", "change-me-jwt")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_EXPIRE_MINUTES: int = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))

    # Hermes
    HERMES_MODEL: str = os.getenv("HERMES_MODEL", "gemini-2.5-flash")
    HERMES_PROVIDER: str = os.getenv("HERMES_PROVIDER", "gemini")
    HERMES_MAX_ITERATIONS: int = int(os.getenv("HERMES_MAX_ITERATIONS", "90"))

    # Gemini
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")


settings = Settings()
