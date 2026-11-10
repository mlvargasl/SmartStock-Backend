from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import IntegrityError, OperationalError
from app.api.routes import router
from app.api.sale_transactions import router as sale_transactions_router
from app.api.forecast import router as forecast_router
from app.api.external import router as external_router
from app.exceptions.external import ExternalAPIError
from app.core.config import get_settings

app = FastAPI(
    title="SmartStock API",
    version="1.0.0",
    description="Core data management for Mellow Bakery.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        s.strip() for s in get_settings().cors_origins.split(",") if s.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
app.include_router(sale_transactions_router)
app.include_router(forecast_router)
app.include_router(external_router)


@app.exception_handler(IntegrityError)
def integrity_error(request: Request, exc: IntegrityError):
    return JSONResponse(
        status_code=409,
        content={
            "detail": "A record conflicts with an existing record or database constraint"
        },
    )


@app.exception_handler(OperationalError)
def database_error(request: Request, exc: OperationalError):
    return JSONResponse(status_code=503, content={"detail": "Database unavailable"})


@app.exception_handler(ExternalAPIError)
def external_api_error(request: Request, exc: ExternalAPIError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
