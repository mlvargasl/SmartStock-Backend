from datetime import datetime, timezone


def test_multi_item_transaction_cancel_and_dashboard(client, auth):
    h = auth()
    a = client.post(
        "/api/products", headers=h, json={"name": "Pastel", "external_code": "POS-1"}
    ).json()
    b = client.post(
        "/api/products", headers=h, json={"name": "Galleta", "external_code": "POS-2"}
    ).json()
    stamp = datetime.now(timezone.utc).isoformat()
    body = {
        "sold_at": stamp,
        "items": [
            {"product_id": a["id"], "quantity": 2},
            {"product_id": b["id"], "quantity": 3},
        ],
    }
    assert client.post("/api/sale-transactions", json=body).status_code == 401
    assert (
        client.post(
            "/api/sale-transactions", headers=auth("INVENTORY_MANAGER"), json=body
        ).status_code
        == 403
    )
    response = client.post("/api/sale-transactions", headers=h, json=body)
    assert response.status_code == 201, response.text
    sale = response.json()
    assert len(sale["items"]) == 2 and sale["status"] == "COMPLETED"
    assert (
        len(
            client.get(
                "/api/sale-transactions", headers=h, params={"product_id": a["id"]}
            ).json()
        )
        == 1
    )
    assert len(client.get("/api/sales", headers=h).json()) == 2
    assert client.get("/api/dashboard", headers=h).json()["sales_today"] == 5
    assert (
        client.patch(f"/api/sale-transactions/{sale['id']}/cancel", headers=h).json()[
            "status"
        ]
        == "CANCELLED"
    )
    assert client.get("/api/sales", headers=h).json() == []
    assert client.get("/api/dashboard", headers=h).json()["sales_today"] == 0
    assert (
        client.patch(
            f"/api/sale-transactions/{sale['id']}/cancel", headers=h
        ).status_code
        == 409
    )


def test_external_id_deduplication_and_validation(client, auth):
    h = auth()
    p = client.post("/api/products", headers=h, json={"name": "Pan"}).json()
    body = {
        "source": "EXTERNAL",
        "external_id": "POS-44",
        "sold_at": "2026-11-10T15:00:00-03:00",
        "items": [{"product_id": p["id"], "quantity": 1}],
    }
    assert (
        client.post("/api/sale-transactions", headers=h, json=body).status_code == 201
    )
    assert (
        client.post("/api/sale-transactions", headers=h, json=body).status_code == 409
    )
    assert len(client.get("/api/sale-transactions", headers=h).json()) == 1
    body["external_id"] = None
    assert (
        client.post("/api/sale-transactions", headers=h, json=body).status_code == 422
    )
    body["source"] = "MANUAL"
    body["items"].append(body["items"][0])
    assert (
        client.post("/api/sale-transactions", headers=h, json=body).status_code == 422
    )
    body["items"] = body["items"][:1]
    body["sold_at"] = "2026-11-10T15:00:00"
    assert (
        client.post("/api/sale-transactions", headers=h, json=body).status_code == 422
    )
