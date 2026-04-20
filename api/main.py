import os
import re
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from api.core.config import settings
from api.core.database import engine, Base
from api.core.logging_config import setup_logging
from api.routers import auth, chat

setup_logging(os.getenv("LOG_LEVEL", "INFO"))

REPORTS_DIR = Path(os.getenv("CRYO_DATA_DIR", "/cryo-data")) / "reports"
ALLOWED_EXTENSIONS = {".html", ".pdf", ".xlsx", ".png", ".jpg", ".csv"}
MEDIA_TYPES = {
    ".html": "text/html",
    ".pdf": "application/pdf",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".csv": "text/csv",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title="CRYO",
    description="Comprehensive Research Yielding Outcomes — Biology Research Platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(chat.router, prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "cryo"}


@app.get("/api/reports/{filename}")
async def download_report(filename: str):
    # Path traversal protection
    if not re.match(r"^[a-zA-Z0-9_\-]+\.[a-z]+$", filename):
        raise HTTPException(status_code=400, detail="Invalid filename")

    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="File type not allowed")

    # Search in fallback dir first, then across all user/conversation dirs
    filepath = REPORTS_DIR / filename
    if not filepath.exists():
        data_dir = Path(os.getenv("CRYO_DATA_DIR", "/cryo-data"))
        matches = list(data_dir.glob(f"**/reports/{filename}"))
        if matches:
            filepath = matches[0]

    if not filepath.exists() or not filepath.is_file():
        raise HTTPException(status_code=404, detail="Report not found")

    media_type = MEDIA_TYPES.get(filepath.suffix.lower(), "application/octet-stream")
    return FileResponse(filepath, filename=filename, media_type=media_type)
