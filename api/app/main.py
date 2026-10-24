from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import Depends, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.core.production_settings import is_production, validate_production_settings
from app.core.rate_limits import rule_for_path
from app.db.pool import engine
from app.ml.registry import ModelRegistry
from app.rate_limit import retry_after_seconds
from app.routers import tennis, props, admin, nfl, nba, nhl
from app.security import require_api_key

MODELS_DIR = Path(__file__).parent.parent / "models"


@asynccontextmanager
async def lifespan(app: FastAPI):
    problems = validate_production_settings(
        settings.api_env, settings.admin_api_key, settings.cors_origins
    )
    if problems:
        raise RuntimeError("Refusing to start in production: " + "; ".join(problems))
    # Startup — load ML models once
    app.state.registry = ModelRegistry(MODELS_DIR)
    yield
    # Shutdown
    await engine.dispose()


app = FastAPI(title=settings.api_title, lifespan=lifespan)


# Registered before CORS so CORS wraps it: a 429 still carries the CORS headers
# the browser needs to read it.
@app.middleware("http")
async def rate_limit(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    rule = rule_for_path(request.url.path, settings.rate_limit_default, settings.rate_limit_heavy)
    if rule is not None:
        client = request.client.host if request.client else "unknown"
        retry_after = retry_after_seconds(client, rule)
        if retry_after is not None:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Try again shortly."},
                headers={"Retry-After": str(retry_after)},
            )
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if is_production(settings.api_env):
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


app.include_router(tennis.router, prefix="/tennis", tags=["tennis"])
app.include_router(props.router, prefix="/tennis/props", tags=["props"])
app.include_router(
    admin.router, prefix="/admin", tags=["admin"], dependencies=[Depends(require_api_key)]
)
app.include_router(nfl.router, prefix="/nfl", tags=["nfl"])
app.include_router(nba.router, prefix="/nba", tags=["nba"])
app.include_router(nhl.router, prefix="/nhl", tags=["nhl"])


@app.get("/health")
async def health():
    return {"status": "ok", "env": settings.api_env}
