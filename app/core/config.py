from functools import lru_cache
from pydantic import Field, field_validator
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = (
        "postgresql+psycopg://smartstock:smartstock@localhost:5432/smartstock"
    )
    jwt_secret_key: str = Field(min_length=32, repr=False)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=60, gt=0)
    cors_origins: str = "http://localhost:5173"
    weather_latitude: float = Field(default=-33.4489, ge=-90, le=90)
    weather_longitude: float = Field(default=-70.6693, ge=-180, le=180)
    weather_location_name: str = "Santiago (ubicación referencial)"
    weather_timezone: str = "America/Santiago"
    open_meteo_api_key: str = Field(default="", repr=False)
    weather_api_url: str = ""
    weather_api_key: str = Field(default="", repr=False)
    calendar_api_url: str = ""
    calendar_api_key: str = Field(default="", repr=False)
    external_api_timeout_seconds: float = Field(default=5.0, gt=0, le=120)
    use_mock_weather: bool = False
    use_mock_calendar: bool = False
    smartstock_latitude: float | None = Field(default=None, ge=-90, le=90)
    smartstock_longitude: float | None = Field(default=None, ge=-180, le=180)
    demand_sales_sources: str = "SYNTHETIC"
    demand_weather_sources: str = "SYNTHETIC"

    @field_validator("weather_timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError:
            raise ValueError("Invalid weather timezone")
        return value

    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", env_ignore_empty=True
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
