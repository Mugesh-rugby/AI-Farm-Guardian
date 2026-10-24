import logging
import os
from contextlib import asynccontextmanager
from sqlalchemy import text
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from database import engine, Base
from config import ALLOWED_ORIGINS
from services.vision_service import model_status
import models
from routers import (
    auth_router,
    farms_router,
    fields_router,
    scans_router,
    priority_router,
    rescue_router,
    weather_router,
    economic_router,
    chat_router,
    treatments_router,
    notifications_router,
    dashboard_router,
)

Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(_app: FastAPI):
    from services.vision_service import initialize_model

    if not initialize_model():
        app_logger.warning("Crop scanner unavailable: install a trained model or configure GROQ_API_KEY.")
    else:
        app_logger.info("Crop scanner provider ready: %s", model_status())
    yield


app_logger = logging.getLogger(__name__)
app = FastAPI(title="AI Farm Guardian API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def verify_request_origin(request, call_next):
    origin = request.headers.get("origin")
    if (
        request.method in {"POST", "PUT", "PATCH", "DELETE"}
        and origin
        and origin not in ALLOWED_ORIGINS
    ):
        return JSONResponse(status_code=403, content={"detail": "Request origin is not allowed."})
    return await call_next(request)

try:
    from config import UPLOAD_DIR
except ImportError:
    from backend.config import UPLOAD_DIR

os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

app.include_router(auth_router.router)
app.include_router(farms_router.router)
app.include_router(fields_router.router)
app.include_router(scans_router.router)
app.include_router(priority_router.router)
app.include_router(rescue_router.router)
app.include_router(weather_router.router)
app.include_router(economic_router.router)
app.include_router(chat_router.router)
app.include_router(treatments_router.router)
app.include_router(notifications_router.router)
app.include_router(dashboard_router.router)

@app.get("/")
def root():
    return {"name": "AI Farm Guardian API", "status": "running"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def readiness():
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {
        "status": "ready",
        "database": "connected",
        "crop_model": model_status(),
    }
