from datetime import date, timedelta


def test_authentication_and_roles(client, auth):
    h = auth()
    assert client.get("/api/auth/me", headers=h).json()["role"] == "ADMIN"
    assert (
        client.post(
            "/api/auth/login", json={"email": "admin@example.cl", "password": "bad"}
        ).status_code
        == 401
    )
    r = client.post(
        "/api/users",
        headers=h,
        json={
            "name": "User",
            "email": "new@example.cl",
            "password": "password123",
            "role": "INVENTORY_MANAGER",
        },
    )
    assert r.status_code == 201
    assert (
        client.post(
            "/api/users",
            headers=h,
            json={
                "name": "User",
                "email": "new@example.cl",
                "password": "password123",
                "role": "ADMIN",
            },
        ).status_code
        == 409
    )
    assert (
        client.get("/api/users", headers=auth("PRODUCTION_MANAGER")).status_code == 403
    )
    assert (
        client.post(
            "/api/sales",
            headers=auth("INVENTORY_MANAGER"),
            json={"product_id": 1, "quantity": 1, "sale_date": "2026-10-01"},
        ).status_code
        == 403
    )
    assert (
        client.patch(
            f"/api/users/{r.json()['id']}/status", headers=h, json={"active": False}
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/auth/login",
            json={"email": "new@example.cl", "password": "password123"},
        ).status_code
        == 401
    )


def test_catalog_recipes_inventory(client, auth):
    h = auth()
    p = client.post("/api/products", headers=h, json={"name": "Pan"})
    assert p.status_code == 201
    pid = p.json()["id"]
    assert len(client.get("/api/products", headers=h).json()) == 1
    assert (
        client.put(
            f"/api/products/{pid}", headers=h, json={"name": "Pan integral"}
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"/api/products/{pid}/status", headers=h, json={"active": False}
        ).status_code
        == 200
    )
    assert client.get("/api/products?active=true", headers=h).json() == []
    client.patch(f"/api/products/{pid}/status", headers=h, json={"active": True})
    i = client.post(
        "/api/ingredients",
        headers=auth("INVENTORY_MANAGER"),
        json={"name": "Harina", "unit": "g", "minimum_stock": 10},
    )
    assert i.status_code == 201
    iid = i.json()["id"]
    assert (
        client.put(
            f"/api/ingredients/{iid}",
            headers=h,
            json={"name": "Harina integral", "unit": "g", "minimum_stock": 10},
        ).status_code
        == 200
    )
    recipe = {
        "product_id": pid,
        "ingredients": [{"ingredient_id": iid, "quantity_per_unit": 5}],
    }
    assert client.post("/api/recipes", headers=h, json=recipe).status_code == 201
    assert (
        client.get(f"/api/products/{pid}/recipe", headers=h).json()["ingredients"][0][
            "ingredient_id"
        ]
        == iid
    )
    recipe["ingredients"].append(recipe["ingredients"][0])
    assert client.post("/api/recipes", headers=h, json=recipe).status_code == 422
    assert (
        client.put(
            f"/api/inventory/{iid}", headers=h, json={"current_stock": 20}
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/inventory/{iid}/adjust", headers=h, json={"quantity": -10}
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/inventory/{iid}/adjust", headers=h, json={"quantity": -11}
        ).status_code
        == 400
    )
    assert len(client.get("/api/inventory/low-stock", headers=h).json()) == 1


def test_sales_import_and_dashboard(client, auth):
    h = auth()
    pid = client.post("/api/products", headers=h, json={"name": "Pan"}).json()["id"]
    today = date.today()
    assert (
        client.post(
            "/api/sales",
            headers=h,
            json={"product_id": pid, "quantity": 0, "sale_date": str(today)},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/sales",
            headers=h,
            json={"product_id": pid, "quantity": 5, "sale_date": str(today)},
        ).status_code
        == 201
    )
    csv = f"date,product,quantity\n{today},Pan,3\n{today},Missing,0\n{today},Pan,-1\n"
    r = client.post(
        "/api/sales/import", headers=h, files={"file": ("sales.csv", csv, "text/csv")}
    )
    assert r.status_code == 200
    assert (
        r.json()["total_rows"],
        r.json()["imported_rows"],
        r.json()["rejected_rows"],
    ) == (3, 1, 2)
    assert (
        client.post(
            "/api/sales/import",
            headers=h,
            files={"file": ("sales.txt", csv, "text/plain")},
        ).status_code
        == 400
    )
    r = client.get(
        f"/api/sales?product_id={pid}&start_date={today}&end_date={today}", headers=h
    )
    assert len(r.json()) == 2
    assert (
        client.get(f"/api/sales?start_date={today+timedelta(days=1)}", headers=h).json()
        == []
    )
    dashboard = client.get("/api/dashboard", headers=h).json()
    assert (
        dashboard["active_products"] == 1
        and dashboard["sales_today"] == 8
        and dashboard["sales_last_7_days"] == 8
    )


def test_docs_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_validation_and_inactive_token(client, auth):
    h = auth()
    assert client.get("/api/users").status_code == 401
    assert (
        client.post(
            "/api/users",
            headers=h,
            json={
                "name": "Bad",
                "email": "bad@example.cl",
                "password": "password123",
                "role": "INVALID",
            },
        ).status_code
        == 422
    )
    assert client.get("/api/products/99999", headers=h).status_code == 404
    assert (
        client.post(
            "/api/ingredients",
            headers=h,
            json={"name": "x", "unit": "oz", "minimum_stock": 0},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/ingredients",
            headers=h,
            json={"name": "x", "unit": "g", "minimum_stock": -1},
        ).status_code
        == 422
    )
    p = client.post("/api/products", headers=h, json={"name": "Pie"}).json()
    assert (
        client.post(
            "/api/recipes",
            headers=h,
            json={
                "product_id": p["id"],
                "ingredients": [{"ingredient_id": 9999, "quantity_per_unit": 1}],
            },
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/api/sales",
            headers=h,
            json={"product_id": p["id"], "quantity": 1, "sale_date": "bad"},
        ).status_code
        == 422
    )
    client.patch(f"/api/products/{p['id']}/status", headers=h, json={"active": False})
    assert (
        client.post(
            "/api/sales",
            headers=h,
            json={"product_id": p["id"], "quantity": 1, "sale_date": "2026-10-01"},
        ).status_code
        == 400
    )
    for name, content in [
        ("x.csv", "missing,columns\na,b\n"),
        ("x.xlsx", "date,product,quantity\n"),
        ("x.csv", b"\xff"),
    ]:
        assert (
            client.post(
                "/api/sales/import", headers=h, files={"file": (name, content)}
            ).status_code
            == 400
        )
    prod = auth("PRODUCTION_MANAGER")
    uid = client.get("/api/auth/me", headers=prod).json()["id"]
    assert (
        client.patch(
            f"/api/users/{uid}/status", headers=h, json={"active": False}
        ).status_code
        == 200
    )
    assert client.get("/api/auth/me", headers=prod).status_code == 401


def test_recipe_update_and_unique_product(client, auth):
    h = auth()
    pid = client.post("/api/products", headers=h, json={"name": "Pan"}).json()["id"]
    iid = client.post(
        "/api/ingredients", headers=h, json={"name": "Sal", "unit": "g"}
    ).json()["id"]
    body = {
        "product_id": pid,
        "ingredients": [{"ingredient_id": iid, "quantity_per_unit": 3}],
    }
    r = client.post("/api/recipes", headers=h, json=body)
    assert r.status_code == 201
    assert client.post("/api/recipes", headers=h, json=body).status_code == 409
    body["ingredients"][0]["quantity_per_unit"] = 6
    r = client.put(f"/api/recipes/{r.json()['id']}", headers=h, json=body)
    assert (
        r.status_code == 200
        and float(r.json()["ingredients"][0]["quantity_per_unit"]) == 6
    )


def test_import_spanish_csv_headers(client, auth):
    h = auth()
    pid = client.post("/api/products", headers=h, json={"name": "Pan"}).json()["id"]
    content = "fecha,producto,cantidad\n2026-10-01,Pan,5\n2026-10-02,Desconocido,0\n"
    r = client.post(
        "/api/sales/import",
        headers=h,
        files={"file": ("ventas.csv", content, "text/csv")},
    )
    assert r.status_code == 200
    assert (
        r.json()["total_rows"],
        r.json()["imported_rows"],
        r.json()["rejected_rows"],
    ) == (2, 1, 1)
    assert (
        client.get(f"/api/sales?product_id={pid}", headers=h).json()[0]["quantity"] == 5
    )
    bad = "fecha,producto,cantidad,cantidad\n2026-10-01,Pan,2,3\n"
    assert (
        client.post(
            "/api/sales/import",
            headers=h,
            files={"file": ("ventas.csv", bad, "text/csv")},
        ).status_code
        == 400
    )


def test_excel_import_and_export(client, auth):
    import csv
    import io
    from datetime import datetime
    from openpyxl import Workbook

    h = auth()
    pid = client.post(
        "/api/products", headers=h, json={"name": "Torta, chocolate"}
    ).json()["id"]
    book = Workbook()
    sheet = book.active
    sheet.append(["fecha", "producto", "cantidad"])
    sheet.append([datetime(2026, 10, 1), "Torta, chocolate", 5])
    sheet.append(["2026-10-02", "Desconocido", 0])
    sheet.append(["2026-10-03", "Torta, chocolate", "=1+2"])
    data = io.BytesIO()
    book.save(data)
    book.close()
    r = client.post(
        "/api/sales/import", headers=h, files={"file": ("ventas.xlsx", data.getvalue())}
    )
    assert r.status_code == 200, r.text
    assert (
        r.json()["total_rows"],
        r.json()["imported_rows"],
        r.json()["rejected_rows"],
    ) == (3, 1, 2)
    r = client.get(
        f"/api/sales/export?product_id={pid}&start_date=2026-10-01&end_date=2026-10-01",
        headers=h,
    )
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    rows = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig"))))
    assert rows == [
        ["fecha", "producto", "cantidad"],
        ["2026-10-01", "Torta, chocolate", "5"],
    ]
    assert (
        client.get(
            "/api/sales/export?start_date=2026-11-01&end_date=2026-10-01", headers=h
        ).status_code
        == 400
    )
    assert (
        client.get("/api/sales/export", headers=auth("INVENTORY_MANAGER")).status_code
        == 403
    )
    assert (
        client.post(
            "/api/sales/import", headers=h, files={"file": ("ventas.xlsx", b"invalid")}
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/sales/import", headers=h, files={"file": ("ventas.xls", b"invalid")}
        ).status_code
        == 400
    )


def test_export_formula_name_and_reimport(client, auth):
    import csv
    import io

    h = auth()
    pid = client.post("/api/products", headers=h, json={"name": "=Producto"}).json()[
        "id"
    ]
    assert (
        client.post(
            "/api/sales",
            headers=h,
            json={"product_id": pid, "quantity": 1, "sale_date": "2026-10-01"},
        ).status_code
        == 201
    )
    r = client.get("/api/sales/export", headers=h)
    rows = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig"))))
    assert rows[1][1] == "'=Producto"
    result = client.post(
        "/api/sales/import", headers=h, files={"file": ("ventas.csv", r.content)}
    )
    assert result.json()["imported_rows"] == 1


def test_import_creates_products_only_for_valid_rows_and_admin(client, auth):
    admin = auth()
    csv = (
        "fecha,producto,cantidad\n"
        "2026-10-01,Producto nuevo,5\n"
        "2026-10-02,Producto nuevo,3\n"
        "fecha-mal,No crear,3\n"
        "2026-10-02,Sin cantidad,0\n"
        "2026-10-02,   ,2\n"
    )
    r = client.post(
        "/api/sales/import", headers=admin, files={"file": ("ventas.csv", csv)}
    )
    assert r.status_code == 200, r.text
    result = r.json()
    assert (result["imported_rows"], result["rejected_rows"]) == (2, 3)
    assert len(result["created_products"]) == 1
    product = result["created_products"][0]
    assert product["name"] == "Producto nuevo"
    assert (
        len(client.get(f"/api/sales?product_id={product['id']}", headers=admin).json())
        == 2
    )
    names = [p["name"] for p in client.get("/api/products", headers=admin).json()]
    assert names == ["Producto nuevo"]
    again = client.post(
        "/api/sales/import",
        headers=admin,
        files={
            "file": (
                "ventas.csv",
                "fecha,producto,cantidad\n2026-10-01,Producto nuevo,1\n",
            )
        },
    )
    assert again.json()["created_products"] == []
    ingredient = client.post(
        "/api/ingredients",
        headers=admin,
        json={"name": "Nuevo ingrediente", "unit": "g", "minimum_stock": 10},
    )
    assert ingredient.status_code == 201
    iid = ingredient.json()["id"]
    assert (
        float(
            client.get(f"/api/inventory/{iid}", headers=admin).json()["current_stock"]
        )
        == 0
    )
    assert (
        client.post(
            "/api/recipes",
            headers=admin,
            json={
                "product_id": product["id"],
                "ingredients": [{"ingredient_id": iid, "quantity_per_unit": 2}],
            },
        ).status_code
        == 201
    )


def test_import_does_not_expand_production_manager_permissions(client, auth):
    production = auth("PRODUCTION_MANAGER")
    csv = "fecha,producto,cantidad\n2026-10-01,No existe,1\n"
    r = client.post(
        "/api/sales/import", headers=production, files={"file": ("ventas.csv", csv)}
    )
    assert r.status_code == 200
    assert r.json()["imported_rows"] == 0 and r.json()["created_products"] == []
    assert "administrador" in r.json()["errors"][0]["detail"]
    assert client.get("/api/products", headers=production).json() == []
    assert (
        client.post(
            "/api/products", headers=production, json={"name": "No existe"}
        ).status_code
        == 403
    )


def test_excel_creates_new_product(client, auth):
    import io
    from openpyxl import Workbook

    h = auth()
    book = Workbook()
    book.active.append(["fecha", "producto", "cantidad"])
    book.active.append(["2026-10-01", "Nuevo de Excel", 2])
    output = io.BytesIO()
    book.save(output)
    book.close()
    r = client.post(
        "/api/sales/import",
        headers=h,
        files={"file": ("ventas.xlsx", output.getvalue())},
    )
    assert (
        r.status_code == 200
        and r.json()["created_products"][0]["name"] == "Nuevo de Excel"
    )


def test_import_product_recipes_csv(client, auth):
    h = auth()
    existing = client.post(
        "/api/ingredients",
        headers=h,
        json={"name": "Harina", "unit": "g", "minimum_stock": 7},
    ).json()
    text = (
        "producto,ingrediente,cantidad,unidad,stock_minimo\n"
        "Torta,Harina,150,g,3\n"
        "Torta,Azúcar,20,g,10\n"
        "Pan,Azúcar,5,g,10\n"
    )
    r = client.post(
        "/api/products/import",
        headers=h,
        files={"file": ("productos.csv", text, "text/csv")},
    )
    assert r.status_code == 200, r.text
    result = r.json()
    assert (result["total_rows"], result["imported_rows"], result["rejected_rows"]) == (
        3,
        3,
        0,
    )
    assert {p["name"] for p in result["imported_products"]} == {"Torta", "Pan"}
    products = {p["name"]: p["id"] for p in result["imported_products"]}
    recipe = client.get(f"/api/products/{products['Torta']}/recipe", headers=h).json()
    assert len(recipe["ingredients"]) == 2
    ingredients = {
        i["name"]: i for i in client.get("/api/ingredients", headers=h).json()
    }
    assert (
        ingredients["Harina"]["id"] == existing["id"]
        and float(ingredients["Harina"]["minimum_stock"]) == 7
    )
    assert float(ingredients["Azúcar"]["minimum_stock"]) == 10
    assert (
        float(
            client.get(
                f"/api/inventory/{ingredients['Azúcar']['id']}", headers=h
            ).json()["current_stock"]
        )
        == 0
    )
    assert (
        client.get(f"/api/products/{products['Pan']}/recipe", headers=h).status_code
        == 200
    )


def test_import_products_invalid_groups_are_atomic_and_existing_recipe_is_preserved(
    client, auth
):
    h = auth()
    p = client.post("/api/products", headers=h, json={"name": "Ya existe"}).json()
    ing = client.post(
        "/api/ingredients", headers=h, json={"name": "Sal", "unit": "g"}
    ).json()
    client.post(
        "/api/recipes",
        headers=h,
        json={
            "product_id": p["id"],
            "ingredients": [{"ingredient_id": ing["id"], "quantity_per_unit": 2}],
        },
    )
    content = (
        "producto,ingrediente,cantidad,unidad\n"
        "Ya existe,Harina,1,g\n"
        "Inválido,Nuevo,2,g\n"
        "Inválido,Sal,3,kg\n"
        "Duplicado,Sal,1,g\n"
        "Duplicado,Sal,2,g\n"
        "Cantidad cero,Sal,0,g\n"
        "Correcto,Sal,4,g\n"
    )
    result = client.post(
        "/api/products/import", headers=h, files={"file": ("productos.csv", content)}
    ).json()
    assert (result["imported_rows"], result["rejected_rows"]) == (1, 6)
    assert any("ya tiene receta" in e["detail"] for e in result["errors"])
    names = {p["name"] for p in client.get("/api/products", headers=h).json()}
    assert names == {"Ya existe", "Correcto"}
    ingredients = {i["name"] for i in client.get("/api/ingredients", headers=h).json()}
    assert ingredients == {"Sal"}
    recipe = client.get(f"/api/products/{p['id']}/recipe", headers=h).json()
    assert float(recipe["ingredients"][0]["quantity_per_unit"]) == 2


def test_import_product_excel_and_roles(client, auth):
    import io
    from openpyxl import Workbook

    h = auth()
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["producto", "ingrediente", "cantidad", "unidad"])
    sheet.append(["Tarta Excel", "Queso", 3, "kg"])
    out = io.BytesIO()
    workbook.save(out)
    workbook.close()
    for role in ("PRODUCTION_MANAGER", "INVENTORY_MANAGER"):
        denied = client.post(
            "/api/products/import",
            headers=auth(role),
            files={"file": ("x.xlsx", out.getvalue())},
        )
        assert denied.status_code == 403
    r = client.post(
        "/api/products/import", headers=h, files={"file": ("x.xlsx", out.getvalue())}
    )
    assert r.status_code == 200 and r.json()["imported_rows"] == 1
    assert (
        client.post(
            "/api/products/import",
            headers=h,
            files={"file": ("x.csv", "producto,ingrediente\na,b\n")},
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/products/import", headers=h, files={"file": ("x.xlsx", b"invalido")}
        ).status_code
        == 400
    )


def test_recipe_quantity_permissions_and_validation(client, auth):
    admin = auth()
    product = client.post("/api/products", headers=admin, json={"name": "Pan"}).json()
    ingredient = client.post(
        "/api/ingredients", headers=admin, json={"name": "Harina", "unit": "g"}
    ).json()
    recipe = client.post(
        "/api/recipes",
        headers=admin,
        json={
            "product_id": product["id"],
            "ingredients": [
                {"ingredient_id": ingredient["id"], "quantity_per_unit": 10}
            ],
        },
    ).json()
    url = f"/api/recipes/{recipe['id']}/ingredients/{ingredient['id']}"
    production = auth("PRODUCTION_MANAGER")
    result = client.patch(url, headers=production, json={"quantity_per_unit": "15.250"})
    assert result.status_code == 200
    assert float(result.json()["ingredients"][0]["quantity_per_unit"]) == 15.25
    assert result.json()["ingredients"][0]["id"] == recipe["ingredients"][0]["id"]
    assert (
        client.patch(url, headers=admin, json={"quantity_per_unit": "30"}).status_code
        == 200
    )
    assert (
        client.patch(url, headers=production, json={"quantity_per_unit": 0}).status_code
        == 422
    )
    assert (
        client.patch(
            url, headers=auth("INVENTORY_MANAGER"), json={"quantity_per_unit": 2}
        ).status_code
        == 403
    )
    assert (
        client.patch(
            f"/api/recipes/{recipe['id']}/ingredients/9999",
            headers=production,
            json={"quantity_per_unit": 2},
        ).status_code
        == 404
    )
    assert (
        client.patch(
            "/api/recipes/9999/ingredients/9999",
            headers=production,
            json={"quantity_per_unit": 2},
        ).status_code
        == 404
    )
    assert (
        client.put(
            f"/api/recipes/{recipe['id']}",
            headers=production,
            json={
                "product_id": product["id"],
                "ingredients": [
                    {"ingredient_id": ingredient["id"], "quantity_per_unit": 3}
                ],
            },
        ).status_code
        == 403
    )
    assert (
        float(
            client.get(f"/api/recipes/{recipe['id']}", headers=admin).json()[
                "ingredients"
            ][0]["quantity_per_unit"]
        )
        == 30
    )


def test_generated_user_password_and_authorization(client, auth, connection):
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from app.models import User

    admin = auth()
    payload = {
        "name": "Nuevo Usuario",
        "email": "new@example.cl",
        "role": "PRODUCTION_MANAGER",
    }
    for role in ("PRODUCTION_MANAGER", "INVENTORY_MANAGER"):
        assert (
            client.post(
                "/api/users/generated", headers=auth(role), json=payload
            ).status_code
            == 403
        )
    response = client.post("/api/users/generated", headers=admin, json=payload)
    assert (
        response.status_code == 201 and response.headers["cache-control"] == "no-store"
    )
    user = response.json()["user"]
    password = response.json()["initial_password"]
    assert len(password) >= 16 and "password_hash" not in user
    with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
        stored = session.scalar(select(User).where(User.email == "new@example.cl"))
        assert stored.password_hash != password and stored.password_hash.startswith(
            "$argon2"
        )
    assert (
        client.post(
            "/api/auth/login", json={"email": payload["email"], "password": password}
        ).status_code
        == 200
    )
    assert (
        client.post("/api/users/generated", headers=admin, json=payload).status_code
        == 409
    )
    assert (
        client.post(
            "/api/users/generated",
            headers=admin,
            json={**payload, "email": "other@example.cl", "role": "WRONG"},
        ).status_code
        == 422
    )


def test_change_password_invalidates_existing_sessions(client, auth):
    for role in ("ADMIN", "PRODUCTION_MANAGER", "INVENTORY_MANAGER"):
        h = auth(role)
        other = auth(role)
        url = "/api/auth/change-password"
        assert (
            client.post(
                url,
                headers=h,
                json={"current_password": "bad", "new_password": "newpassword123"},
            ).status_code
            == 400
        )
        assert client.get("/api/auth/me", headers=h).status_code == 200
        assert (
            client.post(
                url,
                headers=h,
                json={"current_password": "password123", "new_password": "short"},
            ).status_code
            == 422
        )
        assert (
            client.post(
                url,
                headers=h,
                json={"current_password": "password123", "new_password": "password123"},
            ).status_code
            == 400
        )
        assert (
            client.post(
                url,
                headers=h,
                json={
                    "current_password": "password123",
                    "new_password": "newpassword123",
                },
            ).status_code
            == 204
        )
        assert client.get("/api/auth/me", headers=h).status_code == 401
        assert client.get("/api/auth/me", headers=other).status_code == 401
        email = f"{role.lower()}@example.cl"
        assert (
            client.post(
                "/api/auth/login", json={"email": email, "password": "password123"}
            ).status_code
            == 401
        )
        assert (
            client.post(
                "/api/auth/login", json={"email": email, "password": "newpassword123"}
            ).status_code
            == 200
        )
