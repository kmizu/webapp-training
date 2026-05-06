import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .routers import pages, todos


logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger("todo-app")


app = FastAPI(title="ToDo App", version="0.1.0")

_BASE = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=_BASE / "static"), name="static")

app.include_router(pages.router)
app.include_router(todos.router, prefix="/api")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    response = await call_next(request)
    logger.info("%s %s -> %s", request.method, request.url.path, response.status_code)
    return response


@app.exception_handler(Exception)
async def fallback_handler(request: Request, exc: Exception):
    logger.exception("unhandled error: %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "internal server error"},
    )
