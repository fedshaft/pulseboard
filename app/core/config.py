from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    database_url: str = Field(
        default="postgresql+psycopg://pulseboard:pulseboard@localhost:5433/pulseboard",
        validation_alias="DATABASE_URL",
    )
    session_ttl_days: int = Field(
        default=7,
        validation_alias="SESSION_TTL_DAYS",
    )
    session_cookie_name: str = Field(
        default="pb_session",
        validation_alias="SESSION_COOKIE_NAME",
    )
    cookie_secure: bool = Field(
        default=False,
        validation_alias="COOKIE_SECURE",
    )

settings = Settings()