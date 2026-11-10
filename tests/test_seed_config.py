import pytest
from pydantic import ValidationError
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.core.security import verify_password
from app.core.seed_config import SeedSettings
from app.models import User, Role, Sale
from app.seed import seed


def config(**overrides):
    values = {
        "seed_admin_name": "Administrador",
        "seed_admin_email": "admin@test.cl",
        "seed_admin_password": "admin-test-pass",
        "seed_production_name": "Producción",
        "seed_production_email": "production@test.cl",
        "seed_production_password": "production-test-pass",
        "seed_inventory_name": "Inventario",
        "seed_inventory_email": "inventory@test.cl",
        "seed_inventory_password": "inventory-test-pass",
    }
    values.update(overrides)
    return SeedSettings(_env_file=None, **values)


def test_seed_uses_env_credentials_and_preserves_existing_users(connection):
    session_factory = lambda: Session(
        bind=connection, join_transaction_mode="create_savepoint"
    )
    seed(config(), session_factory)
    with session_factory() as db:
        admin = db.scalar(select(User).where(User.email == "admin@test.cl"))
        assert admin.role == Role.ADMIN and verify_password(
            "admin-test-pass", admin.password_hash
        )
        assert admin.password_hash != "admin-test-pass"
        sales_before = db.scalar(select(func.count()).select_from(Sale))
    seed(config(seed_admin_password="different-pass"), session_factory)
    with session_factory() as db:
        admin = db.scalar(select(User).where(User.email == "admin@test.cl"))
        assert verify_password("admin-test-pass", admin.password_hash)
        assert db.scalar(select(func.count()).select_from(User)) == 3
        assert db.scalar(select(func.count()).select_from(Sale)) == sales_before


def test_invalid_configuration_rejected():
    with pytest.raises(ValidationError):
        config(seed_admin_password="short")
    with pytest.raises(ValidationError):
        config(seed_inventory_email="ADMIN@test.cl")
