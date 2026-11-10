from io import BytesIO
from openpyxl import Workbook


def upload(client, headers, content, name="sales.csv"):
    return client.post(
        "/api/sales/import",
        headers=headers,
        files={"file": (name, content, "text/csv")},
    )


def test_grouped_csv_is_atomic_and_deduplicated(client, auth):
    h = auth()
    content = "fecha,hora,id_venta,producto,cantidad\n2026-10-01,10:15-03:00,S001,Pan,2\n2026-10-01,10:15-03:00,S001,Torta,3\n2026-10-02,11:30-03:00,S002,Pan,4\n"
    r = upload(client, h, content)
    assert (
        r.status_code == 200
        and r.json()["imported_rows"] == 3
        and len(r.json()["created_products"]) == 2
    )
    sales = client.get("/api/sale-transactions", headers=h).json()
    assert len(sales) == 2 and sorted(len(s["items"]) for s in sales) == [1, 2]
    assert all(s["sold_at"] is not None for s in sales)
    again = upload(client, h, content).json()
    assert again["imported_rows"] == 0 and again["rejected_rows"] == 3
    assert len(client.get("/api/sale-transactions", headers=h).json()) == 2


def test_bad_group_rejected_without_creating_product(client, auth):
    h = auth()
    content = "fecha,hora,id_venta,producto,cantidad\n2026-10-01,10:15-03:00,X001,Nuevo,2\n2026-10-01,10:15-03:00,X001,Otro,0\n2026-10-01,10:15-03:00,X002,Valido,3\n"
    r = upload(client, h, content).json()
    assert r["imported_rows"] == 1 and r["rejected_rows"] == 2
    assert {x["name"] for x in client.get("/api/products", headers=h).json()} == {
        "Valido"
    }


def test_partial_columns_rejected_and_old_format_still_works(client, auth):
    h = auth()
    assert (
        upload(
            client, h, "fecha,id_venta,producto,cantidad\n2026-10-01,1,Pan,3\n"
        ).status_code
        == 400
    )
    r = upload(client, h, "fecha,producto,cantidad\n2026-10-01,Pan,3\n").json()
    assert r["imported_rows"] == 1
    assert client.get("/api/sale-transactions", headers=h).json()[0]["sold_at"] is None


def test_grouped_excel_and_role(client, auth):
    h = auth()
    client.post("/api/products", headers=h, json={"name": "Pan"})
    wb = Workbook()
    ws = wb.active
    ws.append(["fecha", "hora", "id_venta", "producto", "cantidad"])
    ws.append(["2026-10-01", "10:15-03:00", "B002", "Pan", 2])
    buf = BytesIO()
    wb.save(buf)
    r = upload(client, auth("PRODUCTION_MANAGER"), buf.getvalue(), "sales.xlsx")
    assert r.status_code == 200 and r.json()["imported_rows"] == 1


def test_semicolon_csv_import(client, auth):
    data = "fecha;hora;id_venta;producto;cantidad\n2026-10-01;10:15-03:00;X1;Pan;3\n"
    response = upload(client, auth(), data).json()
    assert response["imported_rows"] == 1 and response["rejected_rows"] == 0
