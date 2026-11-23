from app.main import app
from app.openapi_docs import DOCS


def test_all_operations_have_spanish_documentation_and_roles():
    schema = app.openapi()
    operations = {
        (method, path): data
        for path, methods in schema["paths"].items()
        for method, data in methods.items()
        if method in {"get", "post", "put", "patch", "delete"}
    }
    assert set(operations) == set(DOCS)
    for key, operation in operations.items():
        assert operation["summary"] == DOCS[key][0]
        assert (
            "Roles permitidos" in operation["description"]
            or "Acceso" in operation["description"]
        )
        if DOCS[key][2]:
            assert operation["security"] and "401" in operation["responses"]


def test_openapi_examples_auth_and_upload_docs(client):
    assert client.get("/docs").status_code == 200
    spec = client.get("/openapi.json").json()
    assert spec["components"]["securitySchemes"]["HTTPBearer"]["scheme"] == "bearer"
    create = spec["paths"]["/api/sale-transactions"]["post"]
    assert (
        len(create["requestBody"]["content"]["application/json"]["example"]["items"])
        == 2
    )
    upload = spec["paths"]["/api/sales/import"]["post"]
    assert "multipart/form-data" in upload["requestBody"]["content"]
    assert "hora" in upload["description"]
    assert (
        "regresión lineal Ridge"
        in spec["paths"]["/api/forecast/demand"]["get"]["description"]
    )
