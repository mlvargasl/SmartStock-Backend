from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from app.core.config import get_settings


def test_sales_trend_counts_days_and_excludes_cancelled(client, auth):
    headers = auth()
    product = client.post(
        "/api/products", headers=headers, json={"name": "Pan diario"}
    ).json()["id"]
    now = datetime.now(ZoneInfo(get_settings().weather_timezone))

    def create(day, quantity):
        response = client.post(
            "/api/sale-transactions",
            headers=headers,
            json={
                "sold_at": day.isoformat(),
                "items": [{"product_id": product, "quantity": quantity}],
            },
        )
        assert response.status_code == 201, response.text
        return response.json()["id"]

    create(now, 4)
    create(now - timedelta(days=2), 3)
    cancelled = create(now, 8)
    assert (
        client.patch(
            f"/api/sale-transactions/{cancelled}/cancel", headers=headers
        ).status_code
        == 200
    )
    assert client.get("/api/dashboard/sales-trend").status_code == 401
    for role in ("ADMIN", "PRODUCTION_MANAGER", "INVENTORY_MANAGER"):
        values = client.get(
            "/api/dashboard/sales-trend?days=7", headers=auth(role)
        ).json()
        assert (
            len(values) == 7
            and values[-1]["quantity"] == 4
            and values[-3]["quantity"] == 3
            and values[-2]["quantity"] == 0
        )
    assert (
        len(client.get("/api/dashboard/sales-trend?days=30", headers=headers).json())
        == 30
    )
    assert (
        client.get("/api/dashboard/sales-trend?days=10", headers=headers).status_code
        == 422
    )
