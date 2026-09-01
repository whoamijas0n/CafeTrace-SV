import json
from typing import Annotated, Any, List, Union
from pydantic import (
    AnyHttpUrl,
    BeforeValidator,
    PostgresDsn,
    computed_field,
)
from pydantic_settings import BaseSettings, SettingsConfigDict


def parse_cors(v: Any) -> list[str]:
    """
    Parses CORS origins from either a JSON string, comma-separated string, or list.
    """
    if isinstance(v, str) and not v.startswith("["):
        return [i.strip() for i in v.split(",") if i.strip()]
    elif isinstance(v, str) and v.startswith("["):
        try:
            parsed = json.loads(v)
            if isinstance(parsed, list):
                return [str(item) for item in parsed]
        except json.JSONDecodeError:
            pass
    elif isinstance(v, (list, tuple)):
        return [str(item) for item in v]
    return ["http://localhost:3000", "http://127.0.0.1:3000"]


class Settings(BaseSettings):
    """
    Global application settings loaded from environment variables and .env file.
    Utilizes Pydantic v2 BaseSettings.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # --- Project Metadata ---
    PROJECT_NAME: str = "CaféTrace SV Backend"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # --- Database Settings ---
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "cafetrace_user"
    POSTGRES_PASSWORD: str = "cafetrace_secure_password_2026"
    POSTGRES_DB: str = "cafetrace_db"

    # --- Security & JWT Settings ---
    SECRET_KEY: str = "cafetrace_super_secret_jwt_key_for_development_purposes_only_change_in_prod_2026!"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # --- CORS Settings ---
    BACKEND_CORS_ORIGINS: Annotated[
        list[str],
        BeforeValidator(parse_cors),
    ] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def async_database_uri(self) -> str:
        """
        Constructs the async PostgreSQL connection URI for asyncpg and GeoAlchemy2.
        """
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def sync_database_uri(self) -> str:
        """
        Constructs the sync PostgreSQL connection URI for migrations or sync drivers.
        """
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"


settings = Settings()
