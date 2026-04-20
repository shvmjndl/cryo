import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from api.core.config import settings
from api.core.database import engine, Base
from api.core.logging_config import setup_logging
from api.routers import auth, chat

# Initialize logging before anything else
setup_logging(os.getenv("LOG_LEVEL", "INFO"))


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
    """Serve generated reports (PDF, Excel, PNG charts)."""
    reports_dir = Path(os.getenv("CRYO_REPORTS_DIR", "/tmp/cryo-reports"))
    filepath = reports_dir / filename

    if not filepath.exists() or not filepath.is_file():
        return {"error": "Report not found"}

    # Determine media type
    ext = filepath.suffix.lower()
    media_types = {
        ".pdf": "application/pdf",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".csv": "text/csv",
    }
    media_type = media_types.get(ext, "application/octet-stream")

    return FileResponse(filepath, filename=filename, media_type=media_type)
