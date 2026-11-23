from datetime import date
from typing import Annotated
from fastapi import APIRouter, Depends
from app.api.deps import Db, allow
from app.models import Role, User
from app.schemas.recommendation import RecommendationCreate, RecommendationEdit, RecommendationRead
from app.services.recommendations import RecommendationService

router = APIRouter(prefix="/api/recommendations", tags=["Recommendations"])
AuthorizedUser = Annotated[User, Depends(allow(Role.ADMIN, Role.PRODUCTION_MANAGER))]
ReaderUser = Annotated[User, Depends(allow(Role.ADMIN, Role.PRODUCTION_MANAGER, Role.INVENTORY_MANAGER))]


@router.post("", response_model=RecommendationRead, status_code=201)
def create_recommendation(data: RecommendationCreate, db: Db, user: AuthorizedUser):
    return RecommendationService(db).create(data, user.id)


@router.get("", response_model=list[RecommendationRead])
def list_recommendations(db: Db, user: ReaderUser, day: date | None = None):
    return RecommendationService(db).list(day)


@router.get('/ingredients')
def ingredient_requirements(start_date: date, end_date: date, db: Db, user: ReaderUser):
    return RecommendationService(db).requirements(start_date, end_date)


@router.get('/{recommendation_id}/ingredients')
def recommendation_ingredients(recommendation_id: int, db: Db, user: ReaderUser):
    return RecommendationService(db).requirements_for_recommendation(recommendation_id)


@router.put('/{recommendation_id}', response_model=RecommendationRead)
def edit_recommendation(recommendation_id: int, data: RecommendationEdit, db: Db, user: AuthorizedUser):
    return RecommendationService(db).edit(recommendation_id, data, user.id)
