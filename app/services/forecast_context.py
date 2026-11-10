"""Compose independent external services without inventing demand predictions."""

import asyncio
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
import httpx
from fastapi import HTTPException
from app.core.config import Settings
from app.integrations.context import holidays_for_day, weather_for_day


def valid_forecast_day(day: date, settings: Settings) -> None:
    today = datetime.now(ZoneInfo(settings.weather_timezone)).date()
    if not today <= day <= today + timedelta(days=15):
        raise HTTPException(
            400, "La fecha debe estar entre hoy y los próximos 15 días."
        )


async def forecast_context(
    day: date, settings: Settings, client: httpx.AsyncClient
) -> dict:
    valid_forecast_day(day, settings)
    weather, calendar = await asyncio.gather(
        weather_for_day(client, settings, day), holidays_for_day(client, day)
    )
    return {
        "date": day,
        "location": {
            "name": settings.weather_location_name,
            "latitude": (
                settings.smartstock_latitude
                if settings.smartstock_latitude is not None
                else settings.weather_latitude
            ),
            "longitude": (
                settings.smartstock_longitude
                if settings.smartstock_longitude is not None
                else settings.weather_longitude
            ),
            "timezone": settings.weather_timezone,
        },
        "weekday": day.weekday(),
        "weather": weather,
        "calendar": calendar,
    }
