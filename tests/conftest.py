import os
import uuid
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

os.environ.setdefault("JWT_SECRET_KEY", "test-only-secret-key-at-least-32-characters")
url = os.environ.get("TEST_DATABASE_URL")
if (
    not url
    or "test" not in (make_url(url).database or "").lower()
    or make_url(url).get_backend_name() != "postgresql"
):
    raise RuntimeError(
        "Set TEST_DATABASE_URL to a dedicated PostgreSQL database whose name includes test"
    )
os.environ["DATABASE_URL"] = url
from app.core.database import get_db
from app.main import app


@pytest.fixture(scope="session")
def connection():
    engine = create_engine(url)
    schema = "test_" + uuid.uuid4().hex
    with engine.connect() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
        conn.execute(text(f'SET search_path TO "{schema}"'))
        conn.commit()
        cfg = Config("alembic.ini")
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "head")
        conn.commit()
        yield conn
        conn.rollback()
        conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        conn.commit()
    engine.dispose()


@pytest.fixture
def client(connection):
    transaction = connection.begin()

    def override():
        with Session(
            bind=connection,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        ) as session:
            yield session

    app.dependency_overrides[get_db] = override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    transaction.rollback()


@pytest.fixture
def auth(client, connection):
    from app.core.security import hash_password
    from app.models import Role, User

    with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
        for role in Role:
            session.add(
                User(
                    name=role.value,
                    email=f"{role.value.lower()}@example.cl",
                    role=role,
                    password_hash=hash_password("password123"),
                )
            )
        session.commit()

    def login(role="ADMIN"):
        r = client.post(
            "/api/auth/login",
            json={"email": f"{role.lower()}@example.cl", "password": "password123"},
        )
        assert r.status_code == 200, r.text
        return {"Authorization": "Bearer " + r.json()["access_token"]}

    return login
