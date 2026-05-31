"""File upload router — accepts multipart uploads, saves to disk, records in DB."""

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.auth import get_current_user
from api.core.database import get_db
from api.models.upload import Upload
from api.models.user import User

router = APIRouter(prefix="/uploads", tags=["uploads"])

UPLOAD_DIR = Path(os.getenv("CRYO_UPLOAD_DIR", "/cryo-data/uploads"))
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2 GB
ALLOWED_EXTENSIONS = {
    ".csv", ".tsv", ".txt",
    ".h5ad", ".h5", ".hdf5",
    ".bam", ".bai",
    ".fastq", ".fastq.gz", ".fq", ".fq.gz",
    ".vcf", ".vcf.gz",
    ".bed", ".narrowpeak", ".broadpeak",
    ".xlsx", ".xls",
    ".parquet", ".feather",
    ".json", ".yaml", ".yml",
    ".fa", ".fasta", ".fna",
    # Documents — PDF + all image formats (routed to VLM collections)
    ".pdf",
    ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp", ".gif",
}

# Map extension → data type + suggested command
EXT_HINTS: dict[str, tuple[str, str]] = {
    ".h5ad":    ("scrna",           "/scrna"),
    ".bam":     ("bam",             "/atac"),
    ".fastq":   ("fastq",           "/meta"),
    ".fastq.gz":("fastq",           "/meta"),
    ".fq":      ("fastq",           "/meta"),
    ".fq.gz":   ("fastq",           "/meta"),
    # Documents — hint to collections command
    ".pdf":     ("document",        "/collections"),
    ".png":     ("document",        "/collections"),
    ".jpg":     ("document",        "/collections"),
    ".jpeg":    ("document",        "/collections"),
    ".tiff":    ("document",        "/collections"),
    ".tif":     ("document",        "/collections"),
    ".bmp":     ("document",        "/collections"),
    ".webp":    ("document",        "/collections"),
    ".gif":     ("document",        "/collections"),
}

NAME_HINTS: dict[str, tuple[str, str]] = {
    "proteingroups":  ("ms_proteomics", "/ms"),
    "protein_groups": ("ms_proteomics", "/ms"),
    "peptides":       ("ms_proteomics", "/ms"),
    "report.tsv":     ("ms_proteomics", "/ms"),
    "counts":         ("rnaseq_counts", "/deseq"),
    "count_matrix":   ("rnaseq_counts", "/deseq"),
    "rawcounts":      ("rnaseq_counts", "/deseq"),
    "metadata":       ("metadata",      ""),
    "sec":            ("sec",           "/sec"),
    "chromatogram":   ("sec",           "/sec"),
}


def _classify(filename: str, ext: str) -> tuple[str, str]:
    """Return (data_type, suggested_command) based on filename and extension."""
    lower = filename.lower()
    for hint_key, (dtype, cmd) in NAME_HINTS.items():
        if hint_key in lower:
            return dtype, cmd
    return EXT_HINTS.get(ext.lower(), ("other", ""))


def _format_upload(u: Upload) -> dict:
    return {
        "id": str(u.id),
        "original_filename": u.original_filename,
        "server_path": u.server_path,
        "file_size": u.file_size,
        "mime_type": u.mime_type,
        "file_ext": u.file_ext,
        "data_type": u.data_type,
        "suggested_command": u.suggested_command,
        "times_used": u.times_used,
        "created_at": u.created_at.isoformat(),
    }


@router.post("")
async def upload_file(
    file: UploadFile = File(...),
    conversation_id: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    original_name = file.filename or "upload"
    # Derive extension — handle double extensions like .fastq.gz
    name_lower = original_name.lower()
    ext = ""
    for double_ext in (".fastq.gz", ".fq.gz", ".vcf.gz", ".tar.gz"):
        if name_lower.endswith(double_ext):
            ext = double_ext
            break
    if not ext:
        ext = Path(original_name).suffix.lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File type '{ext}' not allowed")

    # Per-user directory
    user_dir = UPLOAD_DIR / str(current_user.id)
    user_dir.mkdir(parents=True, exist_ok=True)

    stored_name = f"{uuid.uuid4().hex}_{original_name}"
    dest = user_dir / stored_name

    # Stream to disk, enforce size limit
    size = 0
    try:
        with dest.open("wb") as f:
            while chunk := await file.read(1024 * 1024):  # 1 MB chunks
                size += len(chunk)
                if size > MAX_FILE_SIZE:
                    dest.unlink(missing_ok=True)
                    raise HTTPException(status_code=413, detail="File exceeds 2 GB limit")
                f.write(chunk)
    except HTTPException:
        raise
    except Exception as e:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")

    data_type, suggested_cmd = _classify(original_name, ext)

    record = Upload(
        user_id=current_user.id,
        original_filename=original_name,
        stored_filename=stored_name,
        server_path=str(dest),
        file_size=size,
        mime_type=file.content_type,
        file_ext=ext,
        data_type=data_type,
        suggested_command=suggested_cmd,
        conversation_id=uuid.UUID(conversation_id) if conversation_id else None,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)

    return _format_upload(record)


@router.get("")
async def list_uploads(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Upload)
        .where(Upload.user_id == current_user.id)
        .order_by(Upload.created_at.desc())
        .limit(100)
    )
    return [_format_upload(u) for u in result.scalars().all()]


@router.delete("/{upload_id}")
async def delete_upload(
    upload_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Upload).where(
            Upload.id == uuid.UUID(upload_id),
            Upload.user_id == current_user.id,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Upload not found")

    Path(record.server_path).unlink(missing_ok=True)
    await db.execute(delete(Upload).where(Upload.id == record.id))
    await db.commit()
    return {"deleted": upload_id}
