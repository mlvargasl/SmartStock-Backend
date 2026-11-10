from datetime import date, datetime
from decimal import Decimal
from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    field_validator,
)
from typing import Annotated
from app.models import Role, Unit

Name = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)
]
Amount = Annotated[
    Decimal, Field(ge=0, max_digits=18, decimal_places=3, allow_inf_nan=False)
]
PositiveAmount = Annotated[
    Decimal, Field(gt=0, max_digits=18, decimal_places=3, allow_inf_nan=False)
]
SignedAmount = Annotated[
    Decimal, Field(max_digits=18, decimal_places=3, allow_inf_nan=False)
]


class Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Login(BaseModel):
    email: EmailStr
    password: str


class UserCreate(BaseModel):
    name: Name
    email: EmailStr
    password: Annotated[str, StringConstraints(min_length=8, max_length=128)]
    role: Role
    active: bool = True


class GeneratedUserCreate(BaseModel):
    name: Name
    email: EmailStr
    role: Role


class PasswordChange(BaseModel):
    current_password: str
    new_password: Annotated[str, StringConstraints(min_length=8, max_length=128)]


class UserUpdate(BaseModel):
    name: Name
    email: EmailStr
    password: Annotated[str, StringConstraints(min_length=8, max_length=128)] | None = (
        None
    )


class UserOut(Out):
    id: int
    name: str
    email: str
    role: Role
    active: bool
    created_at: datetime
    updated_at: datetime


class GeneratedUserResult(BaseModel):
    user: UserOut
    initial_password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class RoleUpdate(BaseModel):
    role: Role


class StatusUpdate(BaseModel):
    active: bool


class ProductIn(BaseModel):
    name: Name
    description: Annotated[str, StringConstraints(max_length=1000)] | None = None
    external_code: (
        Annotated[
            str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
        ]
        | None
    ) = None
    active: bool = True


class ProductOut(ProductIn, Out):
    id: int
    created_at: datetime
    updated_at: datetime


class IngredientIn(BaseModel):
    name: Name
    unit: Unit
    minimum_stock: Amount = Decimal("0")
    active: bool = True


class IngredientOut(IngredientIn, Out):
    id: int
    created_at: datetime
    updated_at: datetime


class RecipeItem(BaseModel):
    ingredient_id: int = Field(gt=0)
    quantity_per_unit: PositiveAmount


class RecipeIn(BaseModel):
    product_id: int = Field(gt=0)
    ingredients: list[RecipeItem] = Field(min_length=1)

    @field_validator("ingredients")
    @classmethod
    def unique_items(cls, value: list[RecipeItem]) -> list[RecipeItem]:
        ids = [item.ingredient_id for item in value]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate ingredients are not allowed")
        return value


class RecipeQuantityUpdate(BaseModel):
    quantity_per_unit: PositiveAmount


class RecipeItemOut(RecipeItem, Out):
    id: int
    recipe_id: int


class RecipeOut(Out):
    id: int
    product_id: int
    ingredients: list[RecipeItemOut]
    created_at: datetime
    updated_at: datetime


class StockUpdate(BaseModel):
    current_stock: Amount


class StockAdjust(BaseModel):
    quantity: SignedAmount


class InventoryOut(Out):
    id: int
    ingredient_id: int
    current_stock: Decimal
    updated_at: datetime


class LowStock(BaseModel):
    ingredient_id: int
    name: str
    current_stock: Decimal
    minimum_stock: Decimal
    unit: Unit


class SaleIn(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0, le=2147483647, strict=True)
    sale_date: date


class SaleOut(SaleIn, Out):
    id: int
    created_at: datetime


class ImportErrorRow(BaseModel):
    row: int
    detail: str


class ImportedProduct(BaseModel):
    id: int
    name: str


class ImportResult(BaseModel):
    total_rows: int
    imported_rows: int
    rejected_rows: int
    errors: list[ImportErrorRow]
    created_products: list[ImportedProduct]


class ProductImportResult(BaseModel):
    total_rows: int
    imported_rows: int
    rejected_rows: int
    imported_products: list[ImportedProduct]
    errors: list[ImportErrorRow]


class Dashboard(BaseModel):
    active_products: int
    active_ingredients: int
    low_stock_ingredients: int
    sales_today: int
    sales_last_7_days: int
