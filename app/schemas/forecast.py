from datetime import date
from typing import Literal
from pydantic import BaseModel


class ForecastLocation(BaseModel):
    name: str
    latitude: float
    longitude: float
    timezone: str


class WeatherData(BaseModel):
    temperature_max_c: float | None
    temperature_min_c: float | None
    precipitation_mm: float | None
    precipitation_probability_percent: float | None
    weather_code: int | None


class WeatherResult(BaseModel):
    status: Literal["available", "unavailable"]
    source: str
    data: WeatherData | None
    message: str | None


class HolidayEvent(BaseModel):
    name: str
    scope: Literal["nacional", "regional"]
    kind: Literal["feriado", "conmemoracion"]


class CalendarResult(BaseModel):
    status: Literal["available", "unavailable"]
    source: str
    is_holiday: bool | None
    events: list[HolidayEvent]
    message: str | None


class ForecastContext(BaseModel):
    date: date
    location: ForecastLocation
    weekday: int
    weather: WeatherResult
    calendar: CalendarResult


class CalendarDay(BaseModel):
    date: date
    is_holiday: bool
    events: list[HolidayEvent]


class CalendarMonth(BaseModel):
    status: Literal["available", "unavailable"]
    source: str
    days: list[CalendarDay]
    message: str | None
