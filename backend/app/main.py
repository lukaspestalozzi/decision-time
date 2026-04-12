"""FastAPI application setup."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError

from app.config import load_config
from app.exceptions import ConflictError, DecisionTimeError, InvalidStateError, NotFoundError
from app.exceptions import ValidationError as AppValidationError
from app.routers import health, options, tournaments

config = load_config()

app = FastAPI(
    title="decision-time",
    docs_url="/docs",
    openapi_url="/api/v1/openapi.json",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Error mapping
_ERROR_MAP: dict[type[DecisionTimeError], tuple[int, str]] = {
    NotFoundError: (404, "NOT_FOUND"),
    AppValidationError: (422, "VALIDATION_ERROR"),
    InvalidStateError: (409, "INVALID_STATE"),
    ConflictError: (409, "CONFLICT"),
}


@app.exception_handler(DecisionTimeError)
async def handle_domain_error(request: Request, exc: DecisionTimeError) -> JSONResponse:
    status_code, code = _ERROR_MAP.get(type(exc), (500, "INTERNAL_ERROR"))
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": exc.message}},
    )


@app.exception_handler(RequestValidationError)
async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "VALIDATION_ERROR", "message": str(exc)}},
    )


@app.exception_handler(PydanticValidationError)
async def handle_pydantic_error(request: Request, exc: PydanticValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "VALIDATION_ERROR", "message": str(exc)}},
    )


# Routers
app.include_router(health.router, prefix="/api/v1")
app.include_router(options.router, prefix="/api/v1")
app.include_router(tournaments.router, prefix="/api/v1")
