from __future__ import annotations

from datetime import date
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.models import Ingredient, Inventory, Product, Recipe, RecipeIngredient
from app.models.recommendation import Recommendation, RecommendationItem


class RecommendationRepository:
    def __init__(self, db: Session):
        self.db = db

    def products(self, ids: list[int]) -> dict[int, Product]:
        return {product.id: product for product in self.db.scalars(select(Product).where(Product.id.in_(ids)))}

    def create(self, recommendation: Recommendation) -> Recommendation:
        self.db.add(recommendation)
        self.db.commit()
        self.db.refresh(recommendation)
        return recommendation

    def get(self, ident: int) -> Recommendation | None:
        return self.db.scalar(select(Recommendation).where(Recommendation.id == ident))

    def get_for_update(self, ident: int) -> Recommendation | None:
        return self.db.scalar(select(Recommendation).where(Recommendation.id == ident).with_for_update(of=Recommendation))

    def list(self, day: date | None = None) -> list[Recommendation]:
        query = select(Recommendation)
        if day is not None:
            query = query.where(Recommendation.forecast_date == day)
        return list(self.db.scalars(query.order_by(Recommendation.forecast_date.desc(), Recommendation.id.desc())).unique())

    def latest_in_range(self, start: date, end: date) -> list[Recommendation]:
        latest = (select(func.max(Recommendation.id).label('id')).where(Recommendation.forecast_date.between(start, end)).group_by(Recommendation.forecast_date).subquery())
        return list(self.db.scalars(select(Recommendation).where(Recommendation.id.in_(select(latest.c.id))).order_by(Recommendation.forecast_date)).unique())

    def ingredients_for_products(self, ids: set[int]):
        if not ids:
            return []
        return list(self.db.execute(select(Recipe.product_id, Ingredient.id, Ingredient.name, Ingredient.unit, Ingredient.minimum_stock, RecipeIngredient.quantity_per_unit, Inventory.current_stock).join(RecipeIngredient, RecipeIngredient.recipe_id == Recipe.id).join(Ingredient, Ingredient.id == RecipeIngredient.ingredient_id).outerjoin(Inventory, Inventory.ingredient_id == Ingredient.id).where(Recipe.product_id.in_(ids))))

    def commit(self):
        self.db.commit()
