"""Compatibility wrappers for the existing context endpoints.

The public response shape is preserved while using the shared providers.
"""

from datetime import date, timedelta
from typing import Any
import httpx
from app.core.config import Settings, get_settings
from app.exceptions.external import CalendarAPIError, WeatherAPIError
from app.integrations.calendar.client import ChileCalendarProvider
from app.integrations.calendar.mock import MockCalendarProvider
from app.integrations.weather.client import OpenMeteoProvider
from app.integrations.weather.mock import MockWeatherProvider


async def weather_for_day(
    client: httpx.AsyncClient, settings: Settings, day: date
) -> dict[str, Any]:
    try:
        if settings.use_mock_weather:
            weather = await MockWeatherProvider().get_weather(day)
            data = {
                "temperature_max_c": weather.max_temperature,
                "temperature_min_c": weather.min_temperature,
                "precipitation_mm": weather.precipitation,
                "precipitation_probability_percent": weather.precipitation_probability,
                "weather_code": 0,
            }
            source = weather.source
        else:
            daily = await OpenMeteoProvider(client, settings).fetch_daily(day)
            data = {
                "temperature_max_c": (
                    daily.temperature_2m_max[0]
                    if daily.temperature_2m_max is not None
                    else None
                ),
                "temperature_min_c": (
                    daily.temperature_2m_min[0]
                    if daily.temperature_2m_min is not None
                    else None
                ),
                "precipitation_mm": daily.precipitation_sum[0],
                "precipitation_probability_percent": (
                    daily.precipitation_probability_max[0]
                    if daily.precipitation_probability_max is not None
                    else None
                ),
                "weather_code": (
                    daily.weather_code[0] if daily.weather_code is not None else None
                ),
            }
            source = "Open-Meteo"
        return {"status": "available", "source": source, "data": data, "message": None}
    except WeatherAPIError:
        return {
            "status": "unavailable",
            "source": "Open-Meteo",
            "data": None,
            "message": "No fue posible consultar el clima para esta fecha.",
        }


async def calendar_for_range(
    client: httpx.AsyncClient, start: date, end: date, region_code: str = "CL-RM"
) -> dict[str, Any]:
    settings = get_settings()
    try:
        if settings.use_mock_calendar:
            provider = MockCalendarProvider()
            days = []
            day = start
            while day <= end:
                events = [
                    event.model_dump() for event in await provider.get_events(day)
                ]
                days.append(
                    {
                        "date": day,
                        "is_holiday": any(
                            event["kind"] == "feriado" for event in events
                        ),
                        "events": events,
                    }
                )
                day += timedelta(days=1)
        else:
            provider = ChileCalendarProvider(client, settings)
            days = await provider.get_range(start, end, region_code=region_code)
        return {
            "status": "available",
            "source": provider.source,
            "days": days,
            "message": None,
        }
    except CalendarAPIError:
        return {
            "status": "unavailable",
            "source": "api.restart.cl",
            "days": [],
            "message": "No fue posible consultar los feriados y festividades de Chile.",
        }


async def holidays_for_day(client: httpx.AsyncClient, day: date) -> dict[str, Any]:
    result = await calendar_for_range(client, day, day)
    if result["status"] == "unavailable":
        return {
            "status": "unavailable",
            "source": result["source"],
            "is_holiday": None,
            "events": [],
            "message": result["message"],
        }
    return {
        "status": "available",
        "source": result["source"],
        **{key: result["days"][0][key] for key in ("is_holiday", "events")},
        "message": None,
    }
