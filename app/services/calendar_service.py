from datetime import date
from app.integrations.calendar.base import CalendarProvider
from app.integrations.calendar.schemas import CalendarData


class CalendarService:
    def __init__(self, provider: CalendarProvider):
        self.provider = provider

    async def get_calendar_info(self, day: date) -> CalendarData:
        events = await self.provider.get_events(day)
        holidays = [item.name for item in events if item.kind == "feriado"]
        festivities = [item.name for item in events if item.kind == "conmemoracion"]
        return CalendarData(
            date=day,
            day_of_week=day.weekday(),
            is_weekend=day.weekday() >= 5,
            is_holiday=bool(holidays),
            holiday_name=", ".join(holidays) or None,
            is_festivity=bool(festivities),
            festivity_name=", ".join(festivities) or None,
            source=self.provider.source,
        )
