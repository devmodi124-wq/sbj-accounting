"""FastAPI application entrypoint.

Phase 0: serves the SPA shell + static assets and a health endpoint. DB unlock,
auth, and feature routers are added in later phases.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.config import get_settings
from app.routers import auth as auth_router
from app.routers import cash as cash_router
from app.routers import dashboard as dashboard_router
from app.routers import customers as customers_router
from app.routers import import_ as import_router
from app.routers import ledgers as ledgers_router
from app.routers import lookups as lookups_router
from app.routers import orders as orders_router
from app.routers import parties as parties_router
from app.routers import purchases as purchases_router
from app.routers import reports as reports_router
from app.routers import settings as settings_router
from app.routers import system as system_router
from app.routers import users as users_router

APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"
TEMPLATES_DIR = APP_DIR / "templates"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Ensure the external data dir exists; DB init/unlock happens in later phases.
    get_settings().ensure_data_dir()
    yield


app = FastAPI(title="Khata", version=__version__, lifespan=lifespan)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

app.include_router(auth_router.router)
app.include_router(customers_router.router)
app.include_router(parties_router.router)
app.include_router(orders_router.router)
app.include_router(cash_router.router)
app.include_router(purchases_router.router)
app.include_router(dashboard_router.router)
app.include_router(reports_router.router)
app.include_router(ledgers_router.router)
app.include_router(import_router.router)
app.include_router(system_router.router)
app.include_router(lookups_router.component_types)
app.include_router(lookups_router.purity_types)
app.include_router(users_router.router)
app.include_router(settings_router.router)


@app.get("/health")
def health() -> JSONResponse:
    return JSONResponse({"status": "ok", "version": __version__})


@app.get("/")
def index() -> FileResponse:
    return FileResponse(TEMPLATES_DIR / "index.html")
