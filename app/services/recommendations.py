from __future__ import annotations

from datetime import date
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.recommendation import Recommendation, RecommendationItem, RecommendationChange
from app.repositories.recommendations import RecommendationRepository
from app.schemas.recommendation import RecommendationCreate, RecommendationEdit, RecommendationItemRead, RecommendationRead


class RecommendationService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = RecommendationRepository(db)

    @staticmethod
    def serialize(record: Recommendation) -> RecommendationRead:
        return RecommendationRead(id=record.id, forecast_date=record.forecast_date, created_at=record.created_at, created_by=record.created_by, created_by_name=record.author.name, items=[RecommendationItemRead.model_validate(item) for item in record.items])

    def create(self, data: RecommendationCreate, user_id: int) -> RecommendationRead:
        products = self.repository.products([item.product_id for item in data.items])
        if any(item.product_id not in products or not products[item.product_id].active for item in data.items):
            raise HTTPException(400, "Uno de los productos no existe o está inactivo.")
        record = Recommendation(forecast_date=data.forecast_date, created_by=user_id, items=[RecommendationItem(product_id=item.product_id, product_name=products[item.product_id].name, predicted_units=item.predicted_units, final_units=item.final_units, reason=item.reason) for item in data.items])
        return self.serialize(self.repository.create(record))

    def list(self, day: date | None = None) -> list[RecommendationRead]:
        return [self.serialize(record) for record in self.repository.list(day)]

    def edit(self, ident: int, data: RecommendationEdit, user_id: int) -> RecommendationRead:
        record = self.repository.get_for_update(ident)
        if record is None:
            raise HTTPException(404, "Recomendación no encontrada.")
        current = {item.product_id: item for item in record.items}
        if set(current) != {item.product_id for item in data.items}:
            raise HTTPException(400, "La edición debe incluir exactamente los productos de la recomendación.")
        for update in data.items:
            item = current[update.product_id]
            if item.final_units != update.final_units:
                reason = (update.reason or '').strip()
                if not reason:
                    raise HTTPException(400, f"Indica el motivo del ajuste de {item.product_name}.")
                self.db.add(RecommendationChange(recommendation_item_id=item.id, user_id=user_id, previous_units=item.final_units, new_units=update.final_units, reason=reason))
                item.final_units = update.final_units
                item.reason = reason
        self.repository.commit()
        return self.serialize(record)

    def requirements(self, start: date, end: date) -> dict:
        if start > end:
            raise HTTPException(400, "La fecha inicial no puede ser posterior a la final.")
        records = self.repository.latest_in_range(start, end)
        return self._requirements_for_records(records, start, end)

    def requirements_for_recommendation(self, ident: int) -> dict:
        record = self.repository.get(ident)
        if record is None:
            raise HTTPException(404, "Recomendación no encontrada.")
        return self._requirements_for_records([record], record.forecast_date, record.forecast_date)

    def _requirements_for_records(self, records: list[Recommendation], start: date, end: date) -> dict:
        quantities: dict[int, int] = {}
        names: dict[int, str] = {}
        for record in records:
            for item in record.items:
                quantities[item.product_id] = quantities.get(item.product_id, 0) + item.final_units
                names[item.product_id] = item.product_name
        rows = self.repository.ingredients_for_products(set(quantities))
        ingredients = {}
        products_with_recipe = set()
        for product_id, ingredient_id, name, unit, minimum_stock, per_unit, stock in rows:
            products_with_recipe.add(product_id)
            if ingredient_id not in ingredients:
                ingredients[ingredient_id] = {'ingredient_id': ingredient_id, 'name': name, 'unit': unit, 'required': Decimal('0'), 'current_stock': stock, 'minimum_stock': minimum_stock}
            ingredients[ingredient_id]['required'] += per_unit * quantities[product_id]
        for entry in ingredients.values():
            stock = entry['current_stock']
            entry['remaining'] = stock - entry['required'] if stock is not None else None
            entry['shortage'] = max(Decimal('0'), entry['required'] - stock) if stock is not None else None
            entry['order_to_minimum'] = max(Decimal('0'), entry['required'] + entry['minimum_stock'] - stock) if stock is not None else None
            entry['low_stock'] = stock <= entry['minimum_stock'] if stock is not None else None
            entry['low_after_production'] = entry['remaining'] <= entry['minimum_stock'] if stock is not None else None
        missing = [{'product_id': pid, 'product_name': names[pid]} for pid, quantity in quantities.items() if quantity > 0 and pid not in products_with_recipe]
        missing_stock = [entry['name'] for entry in ingredients.values() if entry['current_stock'] is None]
        return {'start_date': start, 'end_date': end, 'dates': [record.forecast_date for record in records], 'recommendation_ids': [record.id for record in records], 'complete': not missing and not missing_stock, 'products_without_recipe': missing, 'ingredients_without_stock': missing_stock, 'ingredients': sorted(ingredients.values(), key=lambda item: item['name'])}
