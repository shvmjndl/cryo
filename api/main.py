import os
import re
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from sqlalchemy import select

from api.core.auth import hash_password
from api.core.config import settings
from api.core.database import Base, async_session, engine
from api.core.logging_config import setup_logging
from api.models.user import User
from api.routers import auth, chat, workspace, digital_twin, uploads, gem, collections

setup_logging(os.getenv("LOG_LEVEL", "INFO"))

def _get_data_dir() -> Path:
    """Resolve data directory from env or project root."""
    env_dir = os.getenv("CRYO_DATA_DIR", "").strip()
    if env_dir:
        p = Path(env_dir)
        if p.is_absolute():
            return p
        return (Path(__file__).parent.parent / env_dir).resolve()
    return (Path(__file__).parent.parent / "cryo-data").resolve()

REPORTS_DIR = _get_data_dir() / "reports"
ALLOWED_EXTENSIONS = {".html", ".pdf", ".xlsx", ".png", ".jpg", ".csv", ".md"}
MEDIA_TYPES = {
    ".html": "text/html",
    ".pdf": "application/pdf",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".csv": "text/csv",
    ".md": "text/markdown; charset=utf-8",
}


async def ensure_default_superuser() -> None:
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.email == settings.DEFAULT_SUPERUSER_EMAIL)
        )
        if result.scalar_one_or_none():
            return

        session.add(
            User(
                email=settings.DEFAULT_SUPERUSER_EMAIL,
                username=settings.DEFAULT_SUPERUSER_USERNAME,
                password_hash=hash_password(settings.DEFAULT_SUPERUSER_PASSWORD),
                full_name=settings.DEFAULT_SUPERUSER_FULL_NAME,
                role="admin",
            )
        )
        await session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await ensure_default_superuser()
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
app.include_router(workspace.router, prefix="/api")
app.include_router(digital_twin.router, prefix="/api")
app.include_router(uploads.router, prefix="/api")
app.include_router(gem.router, prefix="/api")
app.include_router(collections.router, prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "cryo"}


@app.get("/api/reports/{file_path:path}")
async def download_report(file_path: str):
    requested = Path(file_path)
    if requested.is_absolute() or ".." in requested.parts or not requested.name:
        raise HTTPException(status_code=400, detail="Invalid filename")

    ext = requested.suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="File type not allowed")

    filename = requested.name
    data_dir = _get_data_dir()
    filepath = data_dir / requested
    if not filepath.exists():
        filepath = REPORTS_DIR / requested
    if not filepath.exists():
        filepath = REPORTS_DIR / filename
    if not filepath.exists():
        matches = list(data_dir.glob(f"**/reports/{filename}"))
        if matches:
            filepath = matches[0]

    if not filepath.exists() or not filepath.is_file():
        raise HTTPException(status_code=404, detail="Report not found")

    media_type = MEDIA_TYPES.get(filepath.suffix.lower(), "application/octet-stream")
    # HTML served inline so iframes can render it; other types as attachment (download)
    disposition = "inline" if filepath.suffix.lower() == ".html" else "attachment"
    return FileResponse(filepath, filename=filename, media_type=media_type,
                        content_disposition_type=disposition)


_PDB_ID_RE = re.compile(r'^[0-9][A-Z0-9]{3}$')

@app.get("/api/structure/{pdb_id}")
async def proxy_structure(pdb_id: str):
    """Proxy mmCIF file from RCSB to avoid browser CORS issues."""
    pdb_id = pdb_id.upper().strip()
    if not _PDB_ID_RE.match(pdb_id):
        raise HTTPException(status_code=400, detail="Invalid PDB ID")
    url = f"https://files.rcsb.org/download/{pdb_id}.cif"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(url)
            if r.status_code == 404:
                raise HTTPException(status_code=404, detail=f"Structure {pdb_id} not found")
            r.raise_for_status()
            return Response(
                content=r.content,
                media_type="chemical/x-mmcif",
                headers={"Content-Disposition": f"inline; filename={pdb_id}.cif"},
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch structure: {e}")
