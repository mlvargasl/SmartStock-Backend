from datetime import date
from app.integrations.calendar.schemas import CalendarEvent


class MockCalendarProvider:
    source = "mock-calendar"

    async def get_events(self, day: date) -> list[CalendarEvent]:
        if (day.month, day.day) == (9, 18):
            return [
                CalendarEvent(
                    name="Independencia Nacional", kind="feriado", scope="nacional"
                )
            ]
        return []
