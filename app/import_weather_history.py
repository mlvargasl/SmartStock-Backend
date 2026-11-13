"""Load historical daily weather from Open-Meteo Archive into the training table."""

import argparse
from datetime import date, timedelta

import httpx
from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import WeatherObservation


def import_history(start: date, end: date) -> int:
    if start > end:
        raise ValueError("La fecha inicial debe ser anterior o igual a la final.")
    settings = get_settings()
    params = {
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
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,weather_code",
        "timezone": settings.weather_timezone,
    }
    response = httpx.get(
        "https://archive-api.open-meteo.com/v1/archive",
        params=params,
        timeout=settings.external_api_timeout_seconds,
    )
    response.raise_for_status()
    daily = response.json().get("daily", {})
    days = daily.get("time", [])
    fields = (
        "temperature_2m_max",
        "temperature_2m_min",
        "precipitation_sum",
        "weather_code",
    )
    if any(len(daily.get(field, [])) != len(days) for field in fields):
        raise ValueError("Open-Meteo devolvió un historial incompleto.")

    updated = 0
    with SessionLocal() as db:
        for index, iso_day in enumerate(days):
            observation_day = date.fromisoformat(iso_day)
            values = {
                "temperature_max_c": daily["temperature_2m_max"][index],
                "temperature_min_c": daily["temperature_2m_min"][index],
                "precipitation_mm": daily["precipitation_sum"][index],
                "precipitation_probability_percent": None,
                "weather_code": daily["weather_code"][index],
                "source": "Open-Meteo",
            }
            observation = db.scalar(
                select(WeatherObservation).where(
                    WeatherObservation.observation_date == observation_day
                )
            )
            if observation is None:
                db.add(
                    WeatherObservation(observation_date=observation_day, **values)
                )
            else:
                for field, value in values.items():
                    setattr(observation, field, value)
            updated += 1
        db.commit()
    return updated


def main():
    parser = argparse.ArgumentParser(
        description="Importa clima histórico diario desde Open-Meteo Archive."
    )
    parser.add_argument("--start-date", type=date.fromisoformat)
    parser.add_argument("--end-date", type=date.fromisoformat)
    parser.add_argument("--days", type=int, default=365)
    args = parser.parse_args()
    end = args.end_date or date.today() - timedelta(days=5)
    start = args.start_date or end - timedelta(days=args.days - 1)
    count = import_history(start, end)
    print(f"Importados/actualizados {count} días de clima real desde Open-Meteo.")


if __name__ == "__main__":
    main()
