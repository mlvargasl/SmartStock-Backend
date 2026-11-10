import asyncio
import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
import httpx
import pytest
from app.api.external import calendar_service, weather_service
from app.api.forecast import external_client
from app.core.config import Settings, get_settings
from app.integrations.calendar.schemas import CalendarData
from app.integrations.weather.schemas import WeatherData
from app.main import app


def day_now():
    return datetime.now(ZoneInfo("America/Santiago")).date()


def setup_http(handler, settings=None):
    async def provider():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler), timeout=5
        ) as client:
            yield client

    app.dependency_overrides[external_client] = provider
    if settings is not None:
        app.dependency_overrides[get_settings] = lambda: settings


def clear_overrides():
    for key in (external_client, get_settings, weather_service, calendar_service):
        app.dependency_overrides.pop(key, None)


def weather_payload(day):
    return {
        "daily": {
            "time": [day.isoformat()],
            "temperature_2m_mean": [19.5],
            "temperature_2m_min": [12],
            "temperature_2m_max": [24],
            "precipitation_sum": [1.2],
            "precipitation_probability_max": [40],
            "weather_code": [3],
        }
    }


def calendar_payload(day, entries=None):
    items = entries or []
    return {
        "data": [
            {
                "attributes": {
                    "fecha": day.isoformat(),
                    "fecha_fin": None,
                    "pais": "CL",
                    "nombre": name,
                    "tipo": kind,
                    "regional": regional,
                    "regiones": regions,
                }
            }
            for name, kind, regional, regions in items
        ],
        "meta": {"total": len(items)},
    }


def test_explicit_mocks_roles_and_chilean_holiday(client, auth):
    settings = get_settings().model_copy(
        update={"use_mock_weather": True, "use_mock_calendar": True}
    )

    def no_network(request):
        raise AssertionError("Mocks must not call the network")

    setup_http(no_network, settings)
    try:
        query = "?date=2026-09-18"
        assert client.get("/api/external/context" + query).status_code == 401
        for role in ("ADMIN", "PRODUCTION_MANAGER", "INVENTORY_MANAGER"):
            headers = auth(role)
            response = client.get("/api/external/context" + query, headers=headers)
            assert response.status_code == 200, response.text
            data = response.json()
            assert (
                data["weather"]["source"] == "mock-weather"
                and data["weather"]["temperature"] == 20
            )
            assert (
                data["calendar"]["is_holiday"] is True
                and data["calendar"]["holiday_name"] == "Independencia Nacional"
            )
            assert (
                data["calendar"]["day_of_week"] == 4
                and data["calendar"]["is_weekend"] is False
            )
        assert (
            client.get(
                "/api/external/weather?date=not-a-date", headers=auth()
            ).status_code
            == 422
        )
        assert (
            client.get(
                "/api/external/calendar?date=2026-02-30", headers=auth()
            ).status_code
            == 422
        )
        assert (
            client.get("/api/external/calendar?date=2026-09-19", headers=auth()).json()[
                "is_weekend"
            ]
            is True
        )
    finally:
        clear_overrides()


def test_real_weather_normalization_and_configuration(client, auth):
    day = day_now()
    settings = get_settings().model_copy(
        update={
            "weather_api_url": "https://weather.example",
            "weather_api_key": "do-not-log-me",
            "smartstock_latitude": -33.5,
            "smartstock_longitude": -70.7,
        }
    )

    def handler(request):
        assert request.url.host == "weather.example"
        assert request.url.params["apikey"] == "do-not-log-me"
        assert (
            float(request.url.params["latitude"]) == -33.5
            and float(request.url.params["longitude"]) == -70.7
        )
        return httpx.Response(200, json=weather_payload(day))

    setup_http(handler, settings)
    try:
        r = client.get(f"/api/external/weather?date={day}", headers=auth())
        assert r.status_code == 200
        assert r.json() == {
            "date": str(day),
            "temperature": 19.5,
            "min_temperature": 12.0,
            "max_temperature": 24.0,
            "precipitation": 1.2,
            "precipitation_probability": 40.0,
            "weather_condition": "cloudy",
            "source": "Open-Meteo",
        }
    finally:
        clear_overrides()


@pytest.mark.parametrize(
    "failure",
    ["timeout", "http500", "http401", "json", "empty", "missing", "bad_probability"],
)
def test_weather_failures_are_controlled_without_fallback(
    client, auth, failure, caplog
):
    day = day_now()
    settings = get_settings().model_copy(
        update={"weather_api_key": "super-secret-token", "use_mock_weather": False}
    )

    def handler(request):
        if failure == "timeout":
            raise httpx.ReadTimeout(
                "https://server?apikey=super-secret-token", request=request
            )
        if failure in ("http500", "http401"):
            return httpx.Response(500 if failure == "http500" else 401)
        if failure == "json":
            return httpx.Response(200, content=b"{invalid")
        if failure == "empty":
            return httpx.Response(200, content=b"")
        if failure == "missing":
            return httpx.Response(200, json={"daily": {"time": [str(day)]}})
        result = weather_payload(day)
        result["daily"]["precipitation_probability_max"] = [101]
        return httpx.Response(200, json=result)

    setup_http(handler, settings)
    try:
        with caplog.at_level(logging.INFO):
            r = client.get(f"/api/external/weather?date={day}", headers=auth())
        assert r.status_code == 503 and r.json() == {
            "detail": "Weather service temporarily unavailable"
        }
        assert (
            "super-secret-token" not in caplog.text
            and "super-secret-token" not in r.text
        )
        assert "provider=Open-Meteo" in caplog.text
    finally:
        clear_overrides()


def test_weather_future_or_missing_historical_date(client, auth):
    def no_network(request):
        raise AssertionError("out-of-range date should not be requested")

    setup_http(no_network)
    try:
        headers = auth()
        for day in (day_now() + timedelta(days=16), day_now() - timedelta(days=93)):
            r = client.get(f"/api/external/weather?date={day}", headers=headers)
            assert r.status_code == 422 and "unavailable" in r.json()["detail"]
    finally:
        clear_overrides()


def test_calendar_normal_weekend_holiday_festivity_and_region(client, auth):
    def handler(request):
        assert (
            request.url.params["pais"] == "CL"
            and request.url.params["internacionales"] == "false"
        )
        day = date.fromisoformat(request.url.params["desde"])
        items = (
            []
            if day.day == 19
            else [
                ("Independencia Nacional", "feriado", False, []),
                ("Otra región", "feriado", True, ["CL-AP"]),
                ("Celebración", "conmemoracion", False, []),
            ]
        )
        return httpx.Response(200, json=calendar_payload(day, items))

    setup_http(handler)
    try:
        headers = auth()
        r = client.get("/api/external/calendar?date=2026-09-18", headers=headers)
        assert r.status_code == 200 and r.json() == {
            "date": "2026-09-18",
            "day_of_week": 4,
            "is_weekend": False,
            "is_holiday": True,
            "holiday_name": "Independencia Nacional",
            "is_festivity": True,
            "festivity_name": "Celebración",
            "source": "api.restart.cl",
        }
        saturday = client.get(
            "/api/external/calendar?date=2026-09-19", headers=headers
        ).json()
        assert (
            saturday["day_of_week"] == 5
            and saturday["is_weekend"]
            and not saturday["is_holiday"]
            and saturday["holiday_name"] is None
        )
    finally:
        clear_overrides()


@pytest.mark.parametrize("failure", ["timeout", "http500", "json", "missing"])
def test_calendar_failures_controlled(client, auth, failure):
    def handler(request):
        if failure == "timeout":
            raise httpx.ConnectTimeout("timeout", request=request)
        if failure == "http500":
            return httpx.Response(500)
        if failure == "json":
            return httpx.Response(200, content=b"bad")
        return httpx.Response(200, json={"data": []})

    setup_http(handler)
    try:
        response = client.get("/api/external/calendar?date=2026-09-18", headers=auth())
        assert response.status_code == 503 and response.json() == {
            "detail": "Calendar service temporarily unavailable"
        }
    finally:
        clear_overrides()


def test_context_uses_concurrent_injected_services(client, auth):
    class Shared:
        first = None

        async def rendezvous(self):
            if self.first is None:
                self.first = asyncio.Event()
                await asyncio.wait_for(self.first.wait(), timeout=1)
            else:
                self.first.set()

    gate = Shared()

    class Weather:
        async def get_weather(self, day):
            await gate.rendezvous()
            return WeatherData(
                date=day, temperature=20, precipitation=0, source="fake-weather"
            )

    class Calendar:
        async def get_calendar_info(self, day):
            await gate.rendezvous()
            return CalendarData(
                date=day,
                day_of_week=day.weekday(),
                is_weekend=False,
                is_holiday=False,
                source="fake-calendar",
            )

    app.dependency_overrides[weather_service] = lambda: Weather()
    app.dependency_overrides[calendar_service] = lambda: Calendar()
    try:
        r = client.get("/api/external/context?date=2026-09-18", headers=auth())
        assert (
            r.status_code == 200
            and r.json()["weather"]["source"] == "fake-weather"
            and r.json()["calendar"]["source"] == "fake-calendar"
        )
    finally:
        clear_overrides()


@pytest.mark.parametrize("fail_host", ["api.open-meteo.com", "api.restart.cl"])
def test_context_provider_failures_return_503(client, auth, fail_host):
    day = day_now()

    def handler(request):
        if request.url.host == fail_host:
            return httpx.Response(503)
        return httpx.Response(
            200,
            json=(
                weather_payload(day)
                if request.url.host == "api.open-meteo.com"
                else calendar_payload(day)
            ),
        )

    setup_http(handler)
    try:
        r = client.get(f"/api/external/context?date={day}", headers=auth())
        assert r.status_code == 503
        assert r.json()["detail"] == (
            "Weather service temporarily unavailable"
            if fail_host == "api.open-meteo.com"
            else "Calendar service temporarily unavailable"
        )
    finally:
        clear_overrides()


def test_settings_environment_and_timeout(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "x" * 40)
    monkeypatch.setenv("WEATHER_API_URL", "https://weather.example")
    monkeypatch.setenv("CALENDAR_API_URL", "https://calendar.example")
    monkeypatch.setenv("WEATHER_API_KEY", "weather-test")
    monkeypatch.setenv("CALENDAR_API_KEY", "calendar-test")
    monkeypatch.setenv("SMARTSTOCK_LATITUDE", "-33.6")
    monkeypatch.setenv("SMARTSTOCK_LONGITUDE", "-70.8")
    monkeypatch.setenv("EXTERNAL_API_TIMEOUT_SECONDS", "3")
    monkeypatch.setenv("USE_MOCK_WEATHER", "true")
    monkeypatch.setenv("USE_MOCK_CALENDAR", "true")
    s = Settings(_env_file=None)
    assert (
        s.weather_api_url,
        s.calendar_api_url,
        s.weather_api_key,
        s.calendar_api_key,
    ) == (
        "https://weather.example",
        "https://calendar.example",
        "weather-test",
        "calendar-test",
    )
    assert (
        s.smartstock_latitude,
        s.smartstock_longitude,
        s.external_api_timeout_seconds,
    ) == (-33.6, -70.8, 3)
    assert s.use_mock_weather and s.use_mock_calendar
    monkeypatch.setenv("SMARTSTOCK_LATITUDE", "")
    assert Settings(_env_file=None).smartstock_latitude is None


def test_optional_weather_fields_may_be_missing(client, auth):
    day = day_now()

    def handler(request):
        return httpx.Response(
            200,
            json={
                "daily": {
                    "time": [str(day)],
                    "temperature_2m_mean": [18.5],
                    "precipitation_sum": [0],
                }
            },
        )

    setup_http(handler)
    try:
        r = client.get(f"/api/external/weather?date={day}", headers=auth())
        assert r.status_code == 200
        assert r.json()["temperature"] == 18.5 and r.json()["min_temperature"] is None
        assert (
            r.json()["weather_condition"] is None
            and r.json()["precipitation_probability"] is None
        )
    finally:
        clear_overrides()


def test_mock_flags_are_independent(client, auth):
    settings = get_settings().model_copy(
        update={"use_mock_weather": True, "use_mock_calendar": False}
    )

    def handler(request):
        assert request.url.host == "api.restart.cl"
        requested = date.fromisoformat(request.url.params["desde"])
        return httpx.Response(200, json=calendar_payload(requested))

    setup_http(handler, settings)
    try:
        r = client.get(f"/api/external/context?date={day_now()}", headers=auth())
        assert r.status_code == 200
        assert r.json()["weather"]["source"] == "mock-weather"
        assert r.json()["calendar"]["source"] == "api.restart.cl"
    finally:
        clear_overrides()


def test_calendar_api_key_header_and_settings_repr(client, auth):
    settings = get_settings().model_copy(
        update={
            "calendar_api_url": "https://calendar.example",
            "calendar_api_key": "calendar-secret",
        }
    )

    def handler(request):
        assert request.url.host == "calendar.example"
        assert request.headers["x-api-key"] == "calendar-secret"
        return httpx.Response(
            200, json=calendar_payload(date.fromisoformat(request.url.params["desde"]))
        )

    setup_http(handler, settings)
    try:
        assert "calendar-secret" not in repr(settings)
        assert (
            client.get(
                "/api/external/calendar?date=2026-09-18", headers=auth()
            ).status_code
            == 200
        )
    finally:
        clear_overrides()


def test_mock_flags_apply_to_legacy_endpoints_and_timeout(client, auth, monkeypatch):
    monkeypatch.setenv("USE_MOCK_WEATHER", "true")
    monkeypatch.setenv("USE_MOCK_CALENDAR", "true")
    monkeypatch.setenv("EXTERNAL_API_TIMEOUT_SECONDS", "3")
    get_settings.cache_clear()
    try:

        async def check_timeout():
            async for http_client in external_client():
                assert (
                    http_client.timeout.connect == 3 and http_client.timeout.read == 3
                )

        asyncio.run(check_timeout())

        def no_network(request):
            raise AssertionError("Legacy mock endpoints must not call external APIs")

        setup_http(no_network)
        headers = auth()
        d = day_now()
        context = client.get(f"/api/forecast/context?day={d}", headers=headers)
        assert context.status_code == 200
        assert (
            context.json()["weather"]["source"] == "mock-weather"
            and context.json()["calendar"]["source"] == "mock-calendar"
        )
        month = client.get(
            f"/api/calendar/month?year={d.year}&month={d.month}", headers=headers
        )
        assert month.status_code == 200 and month.json()["source"] == "mock-calendar"
    finally:
        clear_overrides()
        get_settings.cache_clear()
