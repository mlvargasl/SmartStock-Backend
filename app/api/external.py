"""Read-only endpoints exposing normalized external data."""

import asyncio
from datetime import date as Date
from typing import Annotated, Literal
import httpx
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from app.api.deps import allow
from app.api.forecast import external_client
from app.core.config import Settings, get_settings
from app.integrations.calendar.client import ChileCalendarProvider
from app.integrations.calendar.mock import MockCalendarProvider
from app.integrations.calendar.schemas import CalendarData
from app.integrations.weather.client import OpenMeteoProvider
from app.integrations.weather.mock import MockWeatherProvider
from app.integrations.weather.schemas import WeatherData
from app.models import Role
from app.services.calendar_service import CalendarService
from app.services.weather_service import WeatherService

router = APIRouter(
    prefix="/api/external",
    tags=["External Data"],
    dependencies=[
        Depends(allow(Role.ADMIN, Role.PRODUCTION_MANAGER, Role.INVENTORY_MANAGER))
    ],
)
Client = Annotated[httpx.AsyncClient, Depends(external_client)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
Day = Annotated[
    Date,
    Query(alias="date", description="Fecha ISO AAAA-MM-DD", examples=["2026-11-10"]),
]


class ExternalContext(BaseModel):
    date: Date = Field(description="Fecha consultada")
    weather: WeatherData
    calendar: CalendarData
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "date": "2026-09-18",
                "weather": {
                    "date": "2026-09-18",
                    "temperature": 20.0,
                    "min_temperature": 14.0,
                    "max_temperature": 25.0,
                    "precipitation": 0.0,
                    "precipitation_probability": 10,
                    "weather_condition": "clear",
                    "source": "mock-weather",
                },
                "calendar": {
                    "date": "2026-09-18",
                    "day_of_week": 4,
                    "is_weekend": False,
                    "is_holiday": True,
                    "holiday_name": "Independencia Nacional",
                    "is_festivity": False,
                    "festivity_name": None,
                    "source": "mock-calendar",
                },
            }
        }
    )


def weather_service(client: Client, settings: SettingsDep) -> WeatherService:
    provider = (
        MockWeatherProvider()
        if settings.use_mock_weather
        else OpenMeteoProvider(client, settings)
    )
    return WeatherService(provider)


def calendar_service(client: Client, settings: SettingsDep) -> CalendarService:
    provider = (
        MockCalendarProvider()
        if settings.use_mock_calendar
        else ChileCalendarProvider(client, settings)
    )
    return CalendarService(provider)


WeatherDep = Annotated[WeatherService, Depends(weather_service)]
CalendarDep = Annotated[CalendarService, Depends(calendar_service)]


@router.get(
    "/weather",
    response_model=WeatherData,
    summary="Consultar clima normalizado",
    description="Temperaturas diarias en °C y precipitación en mm.",
    responses={503: {"description": "Proveedor meteorológico no disponible"}},
)
async def get_weather(
    day: Day,
    service: WeatherDep,
    client: Client,
    settings: SettingsDep,
    latitude: float | None = Query(default=None, ge=-90, le=90),
    longitude: float | None = Query(default=None, ge=-180, le=180),
    time_zone: (
        Literal["America/Santiago", "America/Punta_Arenas", "America/Coyhaique"] | None
    ) = None,
):
    if (latitude is None) != (longitude is None) or (
        time_zone is not None and latitude is None
    ):
        raise HTTPException(422, "Latitude and longitude must be supplied together")
    if latitude is not None and not settings.use_mock_weather:
        location_settings = settings.model_copy(
            update={
                "smartstock_latitude": latitude,
                "smartstock_longitude": longitude,
                "weather_timezone": time_zone or settings.weather_timezone,
            }
        )
        service = WeatherService(OpenMeteoProvider(client, location_settings))
    return await service.get_weather(day)


@router.get(
    "/calendar",
    response_model=CalendarData,
    summary="Consultar calendario de Chile",
    description="Día de semana: 0 = lunes, 6 = domingo. Los feriados y las conmemoraciones son independientes.",
    responses={503: {"description": "Proveedor de calendario no disponible"}},
)
async def get_calendar(day: Day, service: CalendarDep):
    return await service.get_calendar_info(day)


@router.get(
    "/context",
    response_model=ExternalContext,
    summary="Consultar clima y calendario",
    description="Consulta ambos proveedores concurrentemente; si alguno falla, se devuelve un error controlado.",
    responses={503: {"description": "Alguno de los proveedores no está disponible"}},
)
async def get_external_context(day: Day, weather: WeatherDep, calendar: CalendarDep):
    results = await asyncio.gather(
        weather.get_weather(day),
        calendar.get_calendar_info(day),
        return_exceptions=True,
    )
    for result in results:
        if isinstance(result, BaseException):
            raise result
    weather_data, calendar_data = results
    return ExternalContext(date=day, weather=weather_data, calendar=calendar_data)
