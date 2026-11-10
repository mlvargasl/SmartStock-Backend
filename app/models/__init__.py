from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class Role(str, Enum):
    ADMIN = "ADMIN"
    PRODUCTION_MANAGER = "PRODUCTION_MANAGER"
    INVENTORY_MANAGER = "INVENTORY_MANAGER"


class Unit(str, Enum):
    g = "g"
    kg = "kg"
    ml = "ml"
    l = "l"
    unidad = "unidad"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('ADMIN', 'PRODUCTION_MANAGER', 'INVENTORY_MANAGER')",
            name="ck_user_role",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class Product(TimestampMixin, Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(String(1000))
    external_code: Mapped[str | None] = mapped_column(String(100), unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class Ingredient(TimestampMixin, Base):
    __tablename__ = "ingredients"
    __table_args__ = (
        CheckConstraint("minimum_stock >= 0", name="ck_ingredient_minimum_stock"),
        CheckConstraint(
            "unit IN ('g', 'kg', 'ml', 'l', 'unidad')", name="ck_ingredient_unit"
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    unit: Mapped[str] = mapped_column(String(10))
    minimum_stock: Mapped[Decimal] = mapped_column(
        Numeric(18, 3), default=0, server_default="0"
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    inventory: Mapped["Inventory"] = relationship(
        back_populates="ingredient", uselist=False, cascade="all, delete-orphan"
    )


class Recipe(TimestampMixin, Base):
    __tablename__ = "recipes"
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id"), unique=True, index=True
    )
    ingredients: Mapped[list["RecipeIngredient"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin"
    )


class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredients"
    __table_args__ = (
        UniqueConstraint("recipe_id", "ingredient_id", name="uq_recipe_ingredient"),
        CheckConstraint("quantity_per_unit > 0", name="ck_recipe_quantity"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    recipe_id: Mapped[int] = mapped_column(
        ForeignKey("recipes.id", ondelete="CASCADE"), index=True
    )
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredients.id"), index=True)
    quantity_per_unit: Mapped[Decimal] = mapped_column(Numeric(18, 3))


class Inventory(Base):
    __tablename__ = "inventory"
    __table_args__ = (
        CheckConstraint("current_stock >= 0", name="ck_inventory_nonnegative"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    ingredient_id: Mapped[int] = mapped_column(
        ForeignKey("ingredients.id"), unique=True, index=True
    )
    current_stock: Mapped[Decimal] = mapped_column(
        Numeric(18, 3), default=0, server_default="0"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    ingredient: Mapped[Ingredient] = relationship(
        back_populates="inventory", lazy="joined"
    )


class SaleTransaction(Base):
    __tablename__ = "sale_transactions"
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_sale_source_external_id"),
        CheckConstraint(
            "source IN ('MANUAL', 'IMPORT', 'EXTERNAL', 'LEGACY')",
            name="ck_transaction_source",
        ),
        CheckConstraint(
            "status IN ('COMPLETED', 'CANCELLED')", name="ck_transaction_status"
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(16))
    external_id: Mapped[str | None] = mapped_column(String(150))
    sold_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sale_date: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(
        String(16), default="COMPLETED", server_default="COMPLETED"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    items: Mapped[list["Sale"]] = relationship(
        back_populates="transaction", lazy="selectin"
    )


class Sale(Base):
    __tablename__ = "sales"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_sale_quantity"),
        Index("ix_sales_date_product", "sale_date", "product_id"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("sale_transactions.id"), index=True
    )
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    sale_date: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    transaction: Mapped[SaleTransaction] = relationship(back_populates="items")
    product: Mapped[Product] = relationship(lazy="joined")
