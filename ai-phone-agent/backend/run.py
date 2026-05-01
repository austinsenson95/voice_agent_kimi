#!/usr/bin/env python3
"""
Entry point for the AI Phone Agent backend.

Usage:
    python run.py

This is a thin wrapper around uvicorn. In production, you would run
uvicorn directly with more workers (e.g. gunicorn + uvicorn.workers.UvicornWorker).

Production deployment:
    gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
"""

import uvicorn

from app.config import get_settings

if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info",
    )
