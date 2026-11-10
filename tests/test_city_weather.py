from datetime import date, datetime
from zoneinfo import ZoneInfo
import httpx
from app.api.forecast import external_client
from app.main import app


def test_weather_coordinates_and_calendar_region(client, auth):
    day = datetime.now(ZoneInfo("America/Santiago")).date()

    def handler(request):
        if request.url.host == "api.open-meteo.com":
            assert float(request.url.params["latitude"]) == -33.05
            assert float(request.url.params["longitude"]) == -71.62
            return httpx.Response(
                200,
                json={
                    "daily": {
                        "time": [str(day)],
                        "temperature_2m_mean": [18],
                        "precipitation_sum": [0],
                    }
                },
            )
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "attributes": {
                            "fecha": str(day),
                            "fecha_fin": None,
                            "pais": "CL",
                            "nombre": "Feriado regional",
                            "tipo": "feriado",
                            "regional": True,
                            "regiones": ["CL-VS"],
                        }
                    }
                ],
                "meta": {"total": 1},
            },
        )

    async def provide():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            yield c

    app.dependency_overrides[external_client] = provide
    headers = auth()
    response = client.get(
        f"/api/external/weather?date={day}&latitude=-33.05&longitude=-71.62",
        headers=headers,
    )
    assert response.status_code == 200 and response.json()["temperature"] == 18
    assert (
        client.get(
            f"/api/external/weather?date={day}&latitude=-33", headers=headers
        ).status_code
        == 422
    )
    valpo = client.get(
        f"/api/calendar/month?year={day.year}&month={day.month}&region=CL-VS",
        headers=headers,
    ).json()
    santiago = client.get(
        f"/api/calendar/month?year={day.year}&month={day.month}&region=CL-RM",
        headers=headers,
    ).json()
    assert next(item for item in valpo["days"] if item["date"] == str(day))[
        "is_holiday"
    ]
    assert not next(item for item in santiago["days"] if item["date"] == str(day))[
        "is_holiday"
    ]
    assert (
        client.get(
            f"/api/calendar/month?year={day.year}&month={day.month}&region=invalid",
            headers=headers,
        ).status_code
        == 422
    )
