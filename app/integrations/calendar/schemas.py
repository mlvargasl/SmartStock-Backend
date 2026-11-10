from datetime import date as Date
from pydantic import BaseModel, ConfigDict, Field


class CalendarData(BaseModel):
    date: Date = Field(examples=["2026-09-18"])
    day_of_week: int = Field(ge=0, le=6, description="0 = lunes, 6 = domingo")
    is_weekend: bool
    is_holiday: bool
    holiday_name: str | None = None
    is_festivity: bool = False
    festivity_name: str | None = None
    source: str
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "date": "2026-09-18",
                "day_of_week": 4,
                "is_weekend": False,
                "is_holiday": True,
                "holiday_name": "Independencia Nacional",
                "is_festivity": False,
                "festivity_name": None,
                "source": "api.restart.cl",
            }
        }
    )


class CalendarEvent(BaseModel):
    name: str
    kind: str
    scope: str
