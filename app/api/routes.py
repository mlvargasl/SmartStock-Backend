from datetime import date
from typing import Annotated
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    Response as FastAPIResponse,
)
from fastapi.responses import Response
from sqlalchemy import text
from app.api.deps import Db, Svc, allow, current_user
from app.core.security import create_token, verify_password
from app.models import Ingredient, Inventory, Product, Recipe, Role, Sale, User
from app.schemas import (
    Dashboard,
    GeneratedUserCreate,
    GeneratedUserResult,
    PasswordChange,
    ImportResult,
    IngredientIn,
    IngredientOut,
    InventoryOut,
    Login,
    LowStock,
    ProductIn,
    ProductOut,
    ProductImportResult,
    RecipeIn,
    RecipeOut,
    RecipeQuantityUpdate,
    RoleUpdate,
    SaleIn,
    SaleOut,
    StatusUpdate,
    StockAdjust,
    StockUpdate,
    Token,
    UserCreate,
    UserOut,
    UserUpdate,
)

router = APIRouter(prefix="/api")
admin = Depends(allow(Role.ADMIN))
all_roles = Depends(allow(Role.ADMIN, Role.PRODUCTION_MANAGER, Role.INVENTORY_MANAGER))
inventory_roles = Depends(allow(Role.ADMIN, Role.INVENTORY_MANAGER))
sales_roles = Depends(allow(Role.ADMIN, Role.PRODUCTION_MANAGER))
recipe_quantity_roles = Depends(allow(Role.ADMIN, Role.PRODUCTION_MANAGER))


@router.post(
    "/auth/login",
    response_model=Token,
    tags=["Authentication"],
    summary="Sign in with email and password",
)
def login(data: Login, s: Svc):
    user = s.repo.by_email(data.email)
    if (
        not user
        or not user.active
        or not verify_password(data.password, user.password_hash)
    ):
        raise HTTPException(
            401, "Invalid credentials", headers={"WWW-Authenticate": "Bearer"}
        )
    return {"access_token": create_token(user.id, user.password_hash), "user": user}


@router.get(
    "/auth/me",
    response_model=UserOut,
    tags=["Authentication"],
    summary="Get the authenticated user",
)
def me(user: Annotated[User, Depends(current_user)]):
    return user


@router.post(
    "/auth/change-password",
    status_code=204,
    tags=["Authentication"],
    summary="Change your own password",
)
def change_password(
    data: PasswordChange, user: Annotated[User, Depends(current_user)], s: Svc
):
    s.change_password(user.id, data.current_password, data.new_password)
    return FastAPIResponse(status_code=204, headers={"Cache-Control": "no-store"})


@router.post(
    "/users/generated",
    response_model=GeneratedUserResult,
    status_code=201,
    tags=["Users"],
    dependencies=[admin],
    summary="Create a user with a generated initial password",
)
def create_user_generated(data: GeneratedUserCreate, response: FastAPIResponse, s: Svc):
    response.headers["Cache-Control"] = "no-store"
    return s.create_generated_user(data)


@router.get(
    "/users", response_model=list[UserOut], tags=["Users"], dependencies=[admin]
)
def users(s: Svc):
    return s.repo.all(User)


@router.get(
    "/users/{user_id}", response_model=UserOut, tags=["Users"], dependencies=[admin]
)
def user(user_id: int, s: Svc):
    return s.get(User, user_id)


@router.post(
    "/users",
    response_model=UserOut,
    status_code=201,
    tags=["Users"],
    dependencies=[admin],
)
def create_user(data: UserCreate, s: Svc):
    return s.create(User, data)


@router.put(
    "/users/{user_id}", response_model=UserOut, tags=["Users"], dependencies=[admin]
)
def update_user(user_id: int, data: UserUpdate, s: Svc):
    return s.update(User, user_id, data)


@router.patch(
    "/users/{user_id}/role",
    response_model=UserOut,
    tags=["Users"],
    dependencies=[admin],
)
def user_role(user_id: int, data: RoleUpdate, s: Svc):
    return s.update(User, user_id, data)


@router.patch(
    "/users/{user_id}/status",
    response_model=UserOut,
    tags=["Users"],
    dependencies=[admin],
)
def user_status(user_id: int, data: StatusUpdate, s: Svc):
    return s.update(User, user_id, data)


@router.get(
    "/products",
    response_model=list[ProductOut],
    tags=["Products"],
    dependencies=[all_roles],
)
def products(s: Svc, active: bool | None = None):
    return s.repo.products(active)


@router.post(
    "/products/import",
    response_model=ProductImportResult,
    tags=["Products"],
    dependencies=[admin],
    summary="Import products and recipes from CSV or Excel",
)
async def import_products(s: Svc, file: UploadFile = File(...)):
    content = await file.read(5 * 1024 * 1024 + 1)
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(400, "File exceeds 5 MiB")
    return s.import_products(file.filename or "", content)


@router.get(
    "/products/{product_id}",
    response_model=ProductOut,
    tags=["Products"],
    dependencies=[all_roles],
)
def product(product_id: int, s: Svc):
    return s.get(Product, product_id)


@router.post(
    "/products",
    response_model=ProductOut,
    status_code=201,
    tags=["Products"],
    dependencies=[admin],
)
def create_product(data: ProductIn, s: Svc):
    return s.create(Product, data)


@router.put(
    "/products/{product_id}",
    response_model=ProductOut,
    tags=["Products"],
    dependencies=[admin],
)
def update_product(product_id: int, data: ProductIn, s: Svc):
    return s.update(Product, product_id, data)


@router.patch(
    "/products/{product_id}/status",
    response_model=ProductOut,
    tags=["Products"],
    dependencies=[admin],
)
def product_status(product_id: int, data: StatusUpdate, s: Svc):
    return s.update(Product, product_id, data)


@router.get(
    "/products/{product_id}/recipe",
    response_model=RecipeOut,
    tags=["Recipes"],
    dependencies=[all_roles],
)
def product_recipe(product_id: int, s: Svc):
    return s.recipe_for_product(product_id)


@router.get(
    "/ingredients",
    response_model=list[IngredientOut],
    tags=["Ingredients"],
    dependencies=[all_roles],
)
def ingredients(s: Svc):
    return s.repo.all(Ingredient)


@router.get(
    "/ingredients/{ingredient_id}",
    response_model=IngredientOut,
    tags=["Ingredients"],
    dependencies=[all_roles],
)
def ingredient(ingredient_id: int, s: Svc):
    return s.get(Ingredient, ingredient_id)


@router.post(
    "/ingredients",
    response_model=IngredientOut,
    status_code=201,
    tags=["Ingredients"],
    dependencies=[inventory_roles],
)
def create_ingredient(data: IngredientIn, s: Svc):
    return s.create(Ingredient, data)


@router.put(
    "/ingredients/{ingredient_id}",
    response_model=IngredientOut,
    tags=["Ingredients"],
    dependencies=[inventory_roles],
)
def update_ingredient(ingredient_id: int, data: IngredientIn, s: Svc):
    return s.update(Ingredient, ingredient_id, data)


@router.patch(
    "/ingredients/{ingredient_id}/status",
    response_model=IngredientOut,
    tags=["Ingredients"],
    dependencies=[inventory_roles],
)
def ingredient_status(ingredient_id: int, data: StatusUpdate, s: Svc):
    return s.update(Ingredient, ingredient_id, data)


@router.get(
    "/recipes",
    response_model=list[RecipeOut],
    tags=["Recipes"],
    dependencies=[all_roles],
)
def recipes(s: Svc):
    return s.repo.all(Recipe)


@router.get(
    "/recipes/{recipe_id}",
    response_model=RecipeOut,
    tags=["Recipes"],
    dependencies=[all_roles],
)
def recipe(recipe_id: int, s: Svc):
    return s.get(Recipe, recipe_id)


@router.post(
    "/recipes",
    response_model=RecipeOut,
    status_code=201,
    tags=["Recipes"],
    dependencies=[admin],
)
def create_recipe(data: RecipeIn, s: Svc):
    return s.recipe(data)


@router.patch(
    "/recipes/{recipe_id}/ingredients/{ingredient_id}",
    response_model=RecipeOut,
    tags=["Recipes"],
    dependencies=[recipe_quantity_roles],
    summary="Update an ingredient quantity in a recipe",
)
def update_recipe_quantity(
    recipe_id: int, ingredient_id: int, data: RecipeQuantityUpdate, s: Svc
):
    return s.update_recipe_quantity(recipe_id, ingredient_id, data.quantity_per_unit)


@router.put(
    "/recipes/{recipe_id}",
    response_model=RecipeOut,
    tags=["Recipes"],
    dependencies=[admin],
)
def update_recipe(recipe_id: int, data: RecipeIn, s: Svc):
    return s.recipe(data, recipe_id)


@router.get(
    "/inventory",
    response_model=list[InventoryOut],
    tags=["Inventory"],
    dependencies=[all_roles],
)
def inventories(s: Svc):
    return s.repo.all(Inventory)


@router.get(
    "/inventory/low-stock",
    response_model=list[LowStock],
    tags=["Inventory"],
    dependencies=[all_roles],
)
def low_stock(s: Svc):
    return s.low_stock()


@router.get(
    "/inventory/{ingredient_id}",
    response_model=InventoryOut,
    tags=["Inventory"],
    dependencies=[all_roles],
)
def inventory(ingredient_id: int, s: Svc):
    return s.stock(ingredient_id)


@router.put(
    "/inventory/{ingredient_id}",
    response_model=InventoryOut,
    tags=["Inventory"],
    dependencies=[inventory_roles],
)
def set_stock(ingredient_id: int, data: StockUpdate, s: Svc):
    return s.stock(ingredient_id, data.current_stock)


@router.post(
    "/inventory/{ingredient_id}/adjust",
    response_model=InventoryOut,
    tags=["Inventory"],
    dependencies=[inventory_roles],
)
def adjust_stock(ingredient_id: int, data: StockAdjust, s: Svc):
    return s.stock(ingredient_id, data.quantity, True)


@router.get(
    "/sales", response_model=list[SaleOut], tags=["Sales"], dependencies=[sales_roles]
)
def sales(
    s: Svc,
    product_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(400, "Start date must not be after end date")
    return s.repo.sales(product_id, start_date, end_date)


@router.post(
    "/sales/import",
    response_model=ImportResult,
    tags=["Sales"],
    dependencies=[sales_roles],
)
async def import_sales(
    s: Svc, user: Annotated[User, Depends(current_user)], file: UploadFile = File(...)
):
    content = await file.read(5 * 1024 * 1024 + 1)
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(400, "File exceeds 5 MiB")
    return s.import_sales(
        file.filename or "", content, can_create_products=user.role == Role.ADMIN
    )


@router.get(
    "/sales/export",
    tags=["Sales"],
    dependencies=[sales_roles],
    summary="Export sales to CSV",
)
def export_sales(
    s: Svc,
    product_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
):
    return Response(
        content=s.export_sales(product_id, start_date, end_date),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="ventas.csv"'},
    )


@router.get(
    "/sales/{sale_id}",
    response_model=SaleOut,
    tags=["Sales"],
    dependencies=[sales_roles],
)
def sale(sale_id: int, s: Svc):
    return s.get(Sale, sale_id)


@router.post(
    "/sales",
    response_model=SaleOut,
    status_code=201,
    tags=["Sales"],
    dependencies=[sales_roles],
)
def create_sale(data: SaleIn, s: Svc):
    return s.sale(data)


@router.get(
    "/dashboard", response_model=Dashboard, tags=["Dashboard"], dependencies=[all_roles]
)
def dashboard(s: Svc):
    return s.dashboard()


@router.get(
    "/dashboard/sales-trend",
    tags=["Dashboard"],
    dependencies=[all_roles],
    summary="Daily units sold over 7 or 30 days",
)
def sales_trend(s: Svc, days: int = 7):
    if days not in (7, 30):
        raise HTTPException(422, "Days must be 7 or 30")
    return s.sales_trend(days)


@router.get("/health", tags=["System"], summary="Check API and database connectivity")
def health(db: Db):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}
