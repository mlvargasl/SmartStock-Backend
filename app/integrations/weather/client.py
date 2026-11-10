"""Open-Meteo adapter: HTTP payload validation and normalized daily data."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from app.core.config import Settings
from app.exceptions.external import (
    WeatherAPIError,
    WeatherAPITimeoutError,
    WeatherDateUnavailable,
)
from app.integrations.http import get_json, invalid_response
from app.integrations.weather.schemas import WeatherData


class WeatherDaily(BaseModel):
    time: list[date]
    temperature_2m_mean: list[float | None] | None = None
    temperature_2m_max: list[float | None] | None = None
    temperature_2m_min: list[float | None] | None = None
    precipitation_sum: list[float | None]
    precipitation_probability_max: list[float | None] | None = None
    weather_code: list[int | None] | None = None
    model_config = ConfigDict(allow_inf_nan=False)


class WeatherPayload(BaseModel):
    daily: WeatherDaily


def condition(code: int | None) -> str | None:
    if code is None:
        return None
    if code == 0:
        return "clear"
    if code in (1, 2, 3):
        return "cloudy"
    if code in (45, 48):
        return "fog"
    if code in (51, 53, 55, 56, 57):
        return "drizzle"
    if code in (61, 63, 65, 66, 67, 80, 81, 82):
        return "rain"
    if code in (71, 73, 75, 77, 85, 86):
        return "snow"
    if code in (95, 96, 99):
        return "thunderstorm"
    return "unknown"


class OpenMeteoProvider:
    def __init__(self, client: httpx.AsyncClient, settings: Settings):
        self.client, self.settings = client, settings

    async def fetch_daily(self, day: date) -> WeatherDaily:
        key = self.settings.weather_api_key or self.settings.open_meteo_api_key
        base = self.settings.weather_api_url.rstrip("/")
        if not base:
            base = (
                "https://customer-api.open-meteo.com"
                if key
                else "https://api.open-meteo.com"
            )
        url = base if base.endswith("/v1/forecast") else base + "/v1/forecast"
        params = {
            "latitude": (
                self.settings.smartstock_latitude
                if self.settings.smartstock_latitude is not None
                else self.settings.weather_latitude
            ),
            "longitude": (
                self.settings.smartstock_longitude
                if self.settings.smartstock_longitude is not None
                else self.settings.weather_longitude
            ),
            "timezone": self.settings.weather_timezone,
            "start_date": day.isoformat(),
            "end_date": day.isoformat(),
            "daily": "temperature_2m_mean,temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,weather_code",
        }
        if key:
            params["apikey"] = key
        payload = await get_json(
            self.client,
            url,
            provider="Open-Meteo",
            requested_date=day,
            params=params,
            headers=None,
            error_type=WeatherAPIError,
            timeout_type=WeatherAPITimeoutError,
        )
        try:
            daily = WeatherPayload.model_validate(payload).daily
            arrays = [
                daily.temperature_2m_max,
                daily.temperature_2m_min,
                daily.precipitation_sum,
                daily.precipitation_probability_max,
                daily.weather_code,
            ]
            if daily.time != [day] or any(
                len(values) != 1 for values in arrays if values is not None
            ):
                raise ValueError("Unexpected daily data")
            if (
                daily.temperature_2m_mean is not None
                and len(daily.temperature_2m_mean) != 1
            ):
                raise ValueError("Unexpected mean data")
            if (
                daily.precipitation_sum[0] is not None
                and daily.precipitation_sum[0] < 0
            ):
                raise ValueError("Negative precipitation")
            probability = (
                daily.precipitation_probability_max[0]
                if daily.precipitation_probability_max is not None
                else None
            )
            if probability is not None and not 0 <= probability <= 100:
                raise ValueError("Invalid probability")
            return daily
        except (ValidationError, ValueError, TypeError):
            invalid_response("Open-Meteo", day)
            raise WeatherAPIError() from None

    async def get_weather(self, day: date) -> WeatherData:
        today = datetime.now(ZoneInfo(self.settings.weather_timezone)).date()
        if not today - timedelta(days=92) <= day <= today + timedelta(days=15):
            raise WeatherDateUnavailable()
        daily = await self.fetch_daily(day)
        if (
            not daily.temperature_2m_mean
            or daily.temperature_2m_mean[0] is None
            or daily.precipitation_sum[0] is None
        ):
            invalid_response("Open-Meteo", day)
            raise WeatherAPIError()
        return WeatherData(
            date=day,
            temperature=daily.temperature_2m_mean[0],
            min_temperature=(
                daily.temperature_2m_min[0]
                if daily.temperature_2m_min is not None
                else None
            ),
            max_temperature=(
                daily.temperature_2m_max[0]
                if daily.temperature_2m_max is not None
                else None
            ),
            precipitation=daily.precipitation_sum[0],
            precipitation_probability=(
                daily.precipitation_probability_max[0]
                if daily.precipitation_probability_max is not None
                else None
            ),
            weather_condition=condition(
                daily.weather_code[0] if daily.weather_code is not None else None
            ),
            source="Open-Meteo",
        )
