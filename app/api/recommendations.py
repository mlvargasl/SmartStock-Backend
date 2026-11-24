from datetime import date
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from typing import Literal
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel
from decimal import Decimal
from app.api.deps import Db, allow
from app.models import Role, User
from app.schemas.recommendation import RecommendationCreate, RecommendationEdit, RecommendationRead
from app.services.recommendations import RecommendationService
from app.services.planning_export import export_rows, render_export
from app.models import Inventory, ProductionConfirmation

router = APIRouter(prefix="/api/recommendations", tags=["Recommendations"])
AuthorizedUser = Annotated[User, Depends(allow(Role.ADMIN, Role.PRODUCTION_MANAGER))]
ReaderUser = Annotated[User, Depends(allow(Role.ADMIN, Role.PRODUCTION_MANAGER, Role.INVENTORY_MANAGER))]


class ProductionRequest(BaseModel):
    start_date: date
    end_date: date
    recommendation_ids: list[int]
    ingredients: dict[int, Decimal]


@router.post("", response_model=RecommendationRead, status_code=201)
def create_recommendation(data: RecommendationCreate, db: Db, user: AuthorizedUser):
    return RecommendationService(db).create(data, user.id)


@router.get("", response_model=list[RecommendationRead])
def list_recommendations(db: Db, user: ReaderUser, day: date | None = None):
    return RecommendationService(db).list(day)


@router.get('/ingredients')
def ingredient_requirements(start_date: date, end_date: date, db: Db, user: ReaderUser):
    return RecommendationService(db).requirements(start_date, end_date)


@router.get('/ingredients/export')
def export_planning(start_date: date, end_date: date, format: Literal['csv', 'xlsx', 'pdf'], db: Db, user: ReaderUser):
    service = RecommendationService(db)
    requirements = service.requirements(start_date, end_date)
    records = service.repository.latest_in_range(start_date, end_date)
    if not records:
        raise HTTPException(404, 'No hay recomendaciones guardadas en este rango.')
    data = render_export(export_rows(records, requirements, start_date, end_date), format)
    mime = {'csv': 'text/csv; charset=utf-8', 'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'pdf': 'application/pdf'}[format]
    return Response(data, media_type=mime, headers={'Content-Disposition': f'attachment; filename="planificacion_{start_date}_{end_date}.{format}"'})


@router.post('/production/confirm')
def confirm_production(data: ProductionRequest, db: Db, user: AuthorizedUser, format: Literal['csv', 'xlsx', 'pdf'] = 'pdf'):
    if data.start_date > data.end_date:
        raise HTTPException(400, 'La fecha inicial no puede ser posterior a la final.')
    service = RecommendationService(db)
    records = service.repository.latest_in_range(data.start_date, data.end_date)
    if not records:
        raise HTTPException(400, 'No hay recomendaciones guardadas en este rango.')
    if set(data.recommendation_ids) != {record.id for record in records}:
        raise HTTPException(409, 'Las recomendaciones cambiaron. Vuelve a calcular los ingredientes.')
    dates = [record.forecast_date for record in records]
    previous = list(db.scalars(select(ProductionConfirmation.production_date).where(ProductionConfirmation.production_date.in_(dates))))
    if previous:
        raise HTTPException(409, 'Ya se confirmó producción para estas fechas: ' + ', '.join(str(day) for day in previous))
    requirements = service._requirements_for_records(records, data.start_date, data.end_date)
    if not requirements['complete']:
        raise HTTPException(400, 'Faltan recetas o datos de inventario. Completa la información antes de confirmar.')
    if data.ingredients != {item['ingredient_id']: item['required'] for item in requirements['ingredients']}:
        raise HTTPException(409, 'Las cantidades cambiaron. Vuelve a calcular los ingredientes.')
    ids = [item['ingredient_id'] for item in requirements['ingredients']]
    stocks = {item.ingredient_id: item for item in db.scalars(select(Inventory).where(Inventory.ingredient_id.in_(ids)).order_by(Inventory.ingredient_id).with_for_update(of=Inventory))}
    if len(stocks) != len(ids):
        raise HTTPException(409, 'El inventario cambió. Vuelve a calcular los ingredientes.')
    short = [item['name'] for item in requirements['ingredients'] if stocks[item['ingredient_id']].current_stock < item['required']]
    if short:
        raise HTTPException(400, 'Stock insuficiente para: ' + ', '.join(short))
    # Build the file before committing, so a rendering error cannot deduct stock.
    output = render_export(export_rows(records, requirements, data.start_date, data.end_date), format)
    for record in records:
        daily = service._requirements_for_records([record], record.forecast_date, record.forecast_date)
        snapshot = [{'ingredient_id': item['ingredient_id'], 'name': item['name'], 'unit': item['unit'], 'quantity': str(item['required'])} for item in daily['ingredients']]
        products = [{'product_id': item.product_id, 'product_name': item.product_name, 'quantity': item.final_units} for item in record.items]
        db.add(ProductionConfirmation(production_date=record.forecast_date, recommendation_id=record.id, confirmed_by=user.id, ingredients=snapshot, products=products))
    for item in requirements['ingredients']:
        stocks[item['ingredient_id']].current_stock -= item['required']
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Una fecha ya fue confirmada. Vuelve a calcular los ingredientes.')
    mime = {'csv': 'text/csv; charset=utf-8', 'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'pdf': 'application/pdf'}[format]
    return Response(output, media_type=mime, headers={'Content-Disposition': f'attachment; filename="produccion_{data.start_date}_{data.end_date}.{format}"'})


@router.get('/production/confirmed/{day}')
def confirmed_production(day: date, db: Db, user: ReaderUser):
    confirmation = db.scalar(select(ProductionConfirmation).where(ProductionConfirmation.production_date == day))
    if confirmation is None:
        raise HTTPException(404, 'No hay producción confirmada para esta fecha.')
    if confirmation.products is None:
        raise HTTPException(409, 'Esta producción se confirmó antes de guardar el detalle de productos. Actualiza el stock manualmente.')
    return {'date': confirmation.production_date, 'products': confirmation.products}


@router.get('/{recommendation_id}/ingredients')
def recommendation_ingredients(recommendation_id: int, db: Db, user: ReaderUser):
    return RecommendationService(db).requirements_for_recommendation(recommendation_id)


@router.put('/{recommendation_id}', response_model=RecommendationRead)
def edit_recommendation(recommendation_id: int, data: RecommendationEdit, db: Db, user: AuthorizedUser):
    return RecommendationService(db).edit(recommendation_id, data, user.id)
