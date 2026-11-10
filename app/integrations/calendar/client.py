"""Adapter for Chilean holidays and celebrations from api.restart.cl."""

from datetime import date, timedelta
from typing import Literal
import httpx
from pydantic import BaseModel, Field, ValidationError, field_validator
from app.core.config import Settings
from app.exceptions.external import CalendarAPIError, CalendarAPITimeoutError
from app.integrations.calendar.schemas import CalendarEvent
from app.integrations.http import get_json, invalid_response


class ProviderEvent(BaseModel):
    fecha: date
    fecha_fin: date | None
    pais: str
    nombre: str = Field(min_length=1)
    tipo: Literal["feriado", "conmemoracion"]
    regional: bool = Field(strict=True)
    regiones: list[str]

    @field_validator("pais")
    @classmethod
    def chile_only(cls, value: str) -> str:
        if value != "CL":
            raise ValueError("Unexpected country")
        return value


class CalendarEntry(BaseModel):
    attributes: ProviderEvent


class CalendarMeta(BaseModel):
    total: int = Field(ge=0)


class CalendarPayload(BaseModel):
    data: list[CalendarEntry]
    meta: CalendarMeta


class ChileCalendarProvider:
    source = "api.restart.cl"

    def __init__(self, client: httpx.AsyncClient, settings: Settings):
        self.client, self.settings = client, settings

    async def get_range(
        self, start: date, end: date, region_code: str = "CL-RM"
    ) -> list[dict]:
        base = (self.settings.calendar_api_url or "https://api.restart.cl").rstrip("/")
        url = base if base.endswith("/v1/calendario") else base + "/v1/calendario"
        params = {
            "desde": start.isoformat(),
            "hasta": end.isoformat(),
            "pais": "CL",
            "internacionales": "false",
            "limit": 100,
        }
        headers = (
            {"x-api-key": self.settings.calendar_api_key}
            if self.settings.calendar_api_key
            else None
        )
        raw = await get_json(
            self.client,
            url,
            provider=self.source,
            requested_date=start,
            params=params,
            headers=headers,
            error_type=CalendarAPIError,
            timeout_type=CalendarAPITimeoutError,
        )
        try:
            payload = CalendarPayload.model_validate(raw)
            if payload.meta.total != len(payload.data):
                raise ValueError("Incomplete calendar response")
            entries = [item.attributes for item in payload.data]
            for entry in entries:
                if entry.fecha_fin and entry.fecha_fin < entry.fecha:
                    raise ValueError("Invalid event range")
                if entry.fecha > end or (entry.fecha_fin or entry.fecha) < start:
                    raise ValueError("Unexpected event date")
            relevant = [
                item
                for item in entries
                if not item.regional or region_code in item.regiones
            ]
            days = []
            current = start
            while current <= end:
                events = [
                    CalendarEvent(
                        name=item.nombre,
                        kind=item.tipo,
                        scope="regional" if item.regional else "nacional",
                    ).model_dump()
                    for item in relevant
                    if item.fecha <= current <= (item.fecha_fin or item.fecha)
                ]
                days.append(
                    {
                        "date": current,
                        "is_holiday": any(
                            event["kind"] == "feriado" for event in events
                        ),
                        "events": events,
                    }
                )
                current += timedelta(days=1)
            return days
        except (ValidationError, ValueError, TypeError):
            invalid_response(self.source, start)
            raise CalendarAPIError() from None

    async def get_events(self, day: date) -> list[CalendarEvent]:
        days = await self.get_range(day, day)
        return [CalendarEvent.model_validate(item) for item in days[0]["events"]]
