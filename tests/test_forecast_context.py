from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import httpx
import pytest
from app.api.forecast import external_client
from app.core.config import get_settings
from app.main import app


def today():
    return datetime.now(ZoneInfo(get_settings().weather_timezone)).date()


def mock_response(request):
    day = today().isoformat()
    if request.url.host == "api.open-meteo.com":
        assert request.url.params["timezone"] == "America/Santiago"
        return httpx.Response(
            200,
            json={
                "daily": {
                    "time": [day],
                    "temperature_2m_max": [23.0],
                    "temperature_2m_min": [12.5],
                    "precipitation_sum": [0],
                    "precipitation_probability_max": [10],
                    "weather_code": [0],
                }
            },
        )
    return httpx.Response(
        200,
        json={
            "data": [
                {
                    "attributes": {
                        "fecha": day,
                        "fecha_fin": None,
                        "nombre": "Fiesta nacional",
                        "pais": "CL",
                        "tipo": "feriado",
                        "regional": False,
                        "regiones": [],
                    }
                },
                {
                    "attributes": {
                        "fecha": day,
                        "fecha_fin": None,
                        "nombre": "Otra región",
                        "pais": "CL",
                        "tipo": "feriado",
                        "regional": True,
                        "regiones": ["CL-AP"],
                    }
                },
                {
                    "attributes": {
                        "fecha": day,
                        "fecha_fin": None,
                        "nombre": "Celebración",
                        "pais": "CL",
                        "tipo": "conmemoracion",
                        "regional": False,
                        "regiones": [],
                    }
                },
            ],
            "meta": {"total": 3},
        },
    )


def override_client(handler):
    async def provide():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            yield c

    app.dependency_overrides[external_client] = provide


def test_context_auth_roles_and_sources(client, auth):
    override_client(mock_response)
    try:
        query = f"/api/forecast/context?day={today()}"
        assert client.get(query).status_code == 401
        assert client.get(query, headers=auth("INVENTORY_MANAGER")).status_code == 403
        for role in ("ADMIN", "PRODUCTION_MANAGER"):
            r = client.get(query, headers=auth(role))
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["weather"]["data"]["temperature_max_c"] == 23
            assert body["calendar"]["is_holiday"] is True
            assert [event["name"] for event in body["calendar"]["events"]] == [
                "Fiesta nacional",
                "Celebración",
            ]
            assert body["weekday"] == today().weekday()
    finally:
        app.dependency_overrides.pop(external_client, None)


def test_context_partial_failure_and_dates(client, auth):
    def weather_down(request):
        if request.url.host == "api.open-meteo.com":
            raise httpx.ConnectError("offline", request=request)
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "attributes": {
                            "fecha": today().isoformat(),
                            "fecha_fin": None,
                            "nombre": "Regional",
                            "pais": "CL",
                            "tipo": "feriado",
                            "regional": True,
                            "regiones": ["CL-RM"],
                        }
                    }
                ],
                "meta": {"total": 1},
            },
        )

    override_client(weather_down)
    try:
        h = auth()
        body = client.get(f"/api/forecast/context?day={today()}", headers=h).json()
        assert (
            body["weather"]["status"] == "unavailable"
            and body["weather"]["data"] is None
        )
        assert body["calendar"]["is_holiday"] is True
        assert (
            client.get(
                f"/api/forecast/context?day={today()+timedelta(days=16)}", headers=h
            ).status_code
            == 400
        )
        assert (
            client.get(
                f"/api/forecast/context?day={today()-timedelta(days=1)}", headers=h
            ).status_code
            == 400
        )
    finally:
        app.dependency_overrides.pop(external_client, None)


def test_calendar_failure_is_unknown_not_false(client, auth):
    def calendar_down(request):
        if request.url.host == "api.restart.cl":
            return httpx.Response(500)
        return mock_response(request)

    override_client(calendar_down)
    try:
        body = client.get(f"/api/forecast/context?day={today()}", headers=auth()).json()
        assert body["weather"]["status"] == "available"
        assert (
            body["calendar"]["status"] == "unavailable"
            and body["calendar"]["is_holiday"] is None
        )
    finally:
        app.dependency_overrides.pop(external_client, None)


def test_calendar_month_chilean_holidays_and_festivities(client, auth):
    override_client(mock_response)
    try:
        day = today()
        url = f"/api/calendar/month?year={day.year}&month={day.month}"
        assert client.get(url).status_code == 401
        assert client.get(url, headers=auth("INVENTORY_MANAGER")).status_code == 403
        result = client.get(url, headers=auth("PRODUCTION_MANAGER"))
        assert result.status_code == 200
        body = result.json()
        actual = next(item for item in body["days"] if item["date"] == day.isoformat())
        assert actual["is_holiday"] and {e["kind"] for e in actual["events"]} == {
            "feriado",
            "conmemoracion",
        }
        assert all(e["name"] != "Otra región" for e in actual["events"])
        assert (
            client.get(
                "/api/calendar/month?year=2026&month=13", headers=auth()
            ).status_code
            == 422
        )
    finally:
        app.dependency_overrides.pop(external_client, None)


def test_calendar_rejects_incomplete_provider_page(client, auth):
    def incomplete(request):
        return httpx.Response(200, json={"data": [], "meta": {"total": 3}})

    override_client(incomplete)
    try:
        day = today()
        body = client.get(
            f"/api/calendar/month?year={day.year}&month={day.month}", headers=auth()
        ).json()
        assert body["status"] == "unavailable" and body["days"] == []
    finally:
        app.dependency_overrides.pop(external_client, None)


def test_chilean_celebration_is_not_automatically_a_holiday(client, auth):
    def celebrations(request):
        if request.url.host == "api.open-meteo.com":
            return mock_response(request)
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "attributes": {
                            "fecha": today().isoformat(),
                            "fecha_fin": None,
                            "nombre": "Día de la Madre",
                            "pais": "CL",
                            "tipo": "conmemoracion",
                            "regional": False,
                            "regiones": [],
                        }
                    }
                ],
                "meta": {"total": 1},
            },
        )

    override_client(celebrations)
    try:
        result = client.get(
            f"/api/forecast/context?day={today()}", headers=auth()
        ).json()
        assert result["calendar"]["is_holiday"] is False
        assert result["calendar"]["events"][0]["kind"] == "conmemoracion"
        assert result["calendar"]["events"][0]["name"] == "Día de la Madre"
    finally:
        app.dependency_overrides.pop(external_client, None)


def test_no_chilean_events_is_valid(client, auth):
    def none(request):
        if request.url.host == "api.open-meteo.com":
            return mock_response(request)
        return httpx.Response(200, json={"data": [], "meta": {"total": 0}})

    override_client(none)
    try:
        result = client.get(
            f"/api/forecast/context?day={today()}", headers=auth()
        ).json()
        assert result["calendar"]["status"] == "available"
        assert (
            result["calendar"]["is_holiday"] is False
            and result["calendar"]["events"] == []
        )
    finally:
        app.dependency_overrides.pop(external_client, None)


def test_weather_paid_provider_uses_key_without_returning_it():
    import asyncio
    from app.integrations.context import weather_for_day

    settings = get_settings().model_copy(update={"open_meteo_api_key": "test-secret"})

    def handler(request):
        assert request.url.host == "customer-api.open-meteo.com"
        assert request.url.params["apikey"] == "test-secret"
        return httpx.Response(
            200,
            json={
                "daily": {
                    "time": [today().isoformat()],
                    "temperature_2m_max": [20],
                    "temperature_2m_min": [10],
                    "precipitation_sum": [0],
                    "precipitation_probability_max": [0],
                    "weather_code": [0],
                }
            },
        )

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            return await weather_for_day(c, settings, today())

    result = asyncio.run(run())
    assert result["status"] == "available" and "test-secret" not in str(result)
