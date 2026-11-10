from collections.abc import AsyncGenerator
from datetime import date
import calendar
from typing import Annotated
import httpx
from fastapi import APIRouter, Depends, Query
from app.api.deps import allow
from app.core.config import get_settings
from app.models import Role
from app.schemas.forecast import CalendarMonth, ForecastContext
from app.integrations.context import calendar_for_range
from app.services.forecast_context import forecast_context

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
