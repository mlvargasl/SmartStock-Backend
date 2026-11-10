from datetime import date
from typing import Protocol
from app.integrations.calendar.schemas import CalendarEvent


class CalendarProvider(Protocol):
    source: str

    async def get_events(self, day: date) -> list[CalendarEvent]: ...
