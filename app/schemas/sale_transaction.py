from datetime import date, datetime
from typing import Literal
from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)
from typing import Annotated


class SaleItemIn(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0, le=2147483647, strict=True)


class TransactionIn(BaseModel):
    sold_at: AwareDatetime
    source: Literal["MANUAL", "EXTERNAL"] = "MANUAL"
    external_id: (
        Annotated[
            str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)
        ]
        | None
    ) = None
    items: list[SaleItemIn] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_items(self):
        ids = [item.product_id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("Repeated products are not allowed")
        if (self.source == "EXTERNAL") != (self.external_id is not None):
            raise ValueError("An external ID is required only for external sales")
        return self


class SaleItemOut(BaseModel):
    id: int
    product_id: int
    product_name: str
    quantity: int


class TransactionOut(BaseModel):
    id: int
    source: str
    external_id: str | None
    sold_at: datetime | None
    sale_date: date
    status: str
    created_at: datetime
    cancelled_at: datetime | None
    items: list[SaleItemOut]
    model_config = ConfigDict(from_attributes=True)
