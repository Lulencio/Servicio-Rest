from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes.ventas import router as ventas_router
from app.core.config import Settings
from app.core.errors import register_exception_handlers
from app.services.data_loader import DataLoader
from app.services.data_store import DataStore


def create_app(settings: Settings | None = None) -> FastAPI:
    active_settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        manifest = DataLoader(active_settings).prepare()
        app.state.data_manifest = manifest
        app.state.store = DataStore(
            active_settings.processed_dir,
            query_threads=active_settings.query_threads,
        )
        yield

    app = FastAPI(
        title="Cruz Morada - Resumen estadístico de ventas",
        version="1.0.0",
        description=(
            "API REST que carga ventas de forma desatendida y calcula siete "
            "métricas sobre la columna MONTO APLICADO."
        ),
        lifespan=lifespan,
    )
    register_exception_handlers(app)
    app.include_router(ventas_router)
    return app


app = create_app()
