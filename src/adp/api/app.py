"""ADP Platform API — FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI

from adp.api.routers import documents, export_router, layouts, render, theme


def create_app() -> FastAPI:
    app = FastAPI(
        title="ADP Platform API",
        version="1.0.0",
        docs_url=None,
        redoc_url=None,
    )
    app.include_router(layouts.router)
    app.include_router(theme.router)
    app.include_router(render.router)
    app.include_router(documents.router)
    app.include_router(export_router.router)
    return app


app = create_app()
