from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field, model_validator


class RecommendationItemInput(BaseModel):
    product_id: int = Field(gt=0)
    predicted_units: int = Field(ge=0, le=1_000_000_000, strict=True)
    final_units: int = Field(ge=0, le=1_000_000_000, strict=True)
    reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_reason(self):
        self.reason = self.reason.strip() if self.reason else None
        if self.final_units != self.predicted_units and not self.reason:
            raise ValueError("Indica el motivo cuando cambies la cantidad pronosticada.")
        if self.final_units == self.predicted_units:
            self.reason = None
        return self


class RecommendationCreate(BaseModel):
    forecast_date: date
    items: list[RecommendationItemInput] = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def distinct_products(self):
        if len({item.product_id for item in self.items}) != len(self.items):
            raise ValueError("No se puede repetir un producto.")
        return self


class RecommendationItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    product_id: int
    product_name: str
    predicted_units: int
    final_units: int
    reason: str | None


class RecommendationRead(BaseModel):
    id: int
    forecast_date: date
    created_at: datetime
    created_by: int
    created_by_name: str
    items: list[RecommendationItemRead]


class RecommendationEditItem(BaseModel):
    product_id: int = Field(gt=0)
    final_units: int = Field(ge=0, le=1_000_000_000, strict=True)
    reason: str | None = Field(default=None, max_length=500)


class RecommendationEdit(BaseModel):
    items: list[RecommendationEditItem] = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def distinct_products(self):
        if len({item.product_id for item in self.items}) != len(self.items):
            raise ValueError("No se puede repetir un producto.")
        return self
