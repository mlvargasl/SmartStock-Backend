from collections.abc import AsyncGenerator
from datetime import date
import calendar
from typing import Annotated
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from app.api.deps import Db, allow
from app.core.config import get_settings
from app.models import Role
from app.schemas.forecast import CalendarMonth, DemandForecast, ForecastContext
from app.integrations.context import calendar_for_range, weather_for_day
from app.services.forecast_context import forecast_context, valid_forecast_day
from app.services.demand_forecast import predict_demand

router = APIRouter(prefix="/api", tags=["Forecast"])


async def external_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(get_settings().external_api_timeout_seconds),
        follow_redirects=False,
    ) as client:
        yield client


@router.get(
    "/forecast/context",
    response_model=ForecastContext,
    dependencies=[Depends(allow(Role.ADMIN, Role.PRODUCTION_MANAGER))],
    summary="Get weather and holidays for a forecast date",
)
async def get_forecast_context(
    day: date, client: Annotated[httpx.AsyncClient, Depends(external_client)]
):
    return await forecast_context(day, get_settings(), client)


@router.get(
    "/forecast/demand",
    response_model=DemandForecast,
    dependencies=[Depends(allow(Role.ADMIN, Role.PRODUCTION_MANAGER))],
    summary="Forecast daily product demand using sales and weather history",
)
async def get_demand_forecast(
    day: date,
    db: Db,
    client: Annotated[httpx.AsyncClient, Depends(external_client)],
    product_id: Annotated[int | None, Query(gt=0)] = None,
):
    settings = get_settings()
    valid_forecast_day(day, settings)
    weather = await weather_for_day(client, settings, day)
    if weather["status"] != "available" or weather["data"] is None:
        raise HTTPException(503, weather["message"] or "Weather data unavailable")
    values = weather["data"]
    target_weather = {
        "temperature_max_c": values["temperature_max_c"] or 0,
        "temperature_min_c": values["temperature_min_c"] or 0,
        "precipitation_mm": values["precipitation_mm"] or 0,
        "precipitation_probability_percent": (
            values["precipitation_probability_percent"] or 0
        ),
    }
    result = predict_demand(
        db,
        day,
        target_weather,
        sales_sources=[
            value.strip()
            for value in settings.demand_sales_sources.split(",")
            if value.strip()
        ],
        weather_sources=[
            value.strip()
            for value in settings.demand_weather_sources.split(",")
            if value.strip()
        ],
        product_id=product_id,
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
        "weather": weather,
        **result,
    }


@router.get(
    "/calendar/month",
    response_model=CalendarMonth,
    dependencies=[Depends(allow(Role.ADMIN, Role.PRODUCTION_MANAGER))],
    summary="Get Chilean holidays and festivities for a month",
)
async def get_calendar_month(
    client: Annotated[httpx.AsyncClient, Depends(external_client)],
    year: Annotated[int, Query(ge=2000, le=2100)],
    month: Annotated[int, Query(ge=1, le=12)],
    region: Annotated[str, Query(pattern=r"^CL-[A-Z]{2}$")] = "CL-RM",
):
    return await calendar_for_range(
        client,
        date(year, month, 1),
        date(year, month, calendar.monthrange(year, month)[1]),
        region_code=region,
    )
