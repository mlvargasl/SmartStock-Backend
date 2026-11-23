"""Cache historical Chilean holidays and festivities for demand training."""

import argparse
import asyncio
from datetime import date, timedelta

import httpx
from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.integrations.calendar.client import ChileCalendarProvider
from app.models import CalendarObservation


async def fetch_calendar(start: date, end: date):
    settings = get_settings()
    async with httpx.AsyncClient(
        timeout=settings.external_api_timeout_seconds, follow_redirects=False
    ) as client:
        provider = ChileCalendarProvider(client, settings)
        return await provider.get_range(start, end, region_code="CL-RM")


def import_history(start: date, end: date) -> int:
    if start > end:
        raise ValueError("La fecha inicial debe ser anterior o igual a la final.")
    days = asyncio.run(fetch_calendar(start, end))
    updated = 0
    with SessionLocal() as db:
        for item in days:
            observation_day = item["date"]
            events = item["events"]
            values = {
                "is_holiday": item["is_holiday"],
                "is_festivity": any(
                    event["kind"] == "conmemoracion" for event in events
                ),
                "source": "api.restart.cl",
            }
            observation = db.scalar(
                select(CalendarObservation).where(
                    CalendarObservation.observation_date == observation_day
                )
            )
            if observation is None:
                db.add(
                    CalendarObservation(observation_date=observation_day, **values)
                )
            else:
                for field, value in values.items():
                    setattr(observation, field, value)
            updated += 1
        db.commit()
    return updated


def main():
    parser = argparse.ArgumentParser(
        description="Importa feriados y festividades históricos para el modelo."
    )
    parser.add_argument("--start-date", type=date.fromisoformat)
    parser.add_argument("--end-date", type=date.fromisoformat)
    parser.add_argument("--days", type=int, default=365)
    args = parser.parse_args()
    end = args.end_date or date.today()
    start = args.start_date or end - timedelta(days=args.days - 1)
    count = import_history(start, end)
    print(f"Importados/actualizados {count} días desde api.restart.cl.")


if __name__ == "__main__":
    main()
