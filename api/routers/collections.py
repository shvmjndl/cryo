"""Document collection router — upload PDF/images, VLM→MD, queryable by agent."""

import asyncio
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.auth import get_current_user
from api.core.database import get_db
from api.models.collection import Collection, CollectionFile
from api.models.user import User
from api.services import vlm_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/collections", tags=["collections"])

COLLECTION_ROOT = Path(os.getenv("CRYO_UPLOAD_DIR", "/cryo-data/uploads")).parent / "collections"
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500 MB

DOCUMENT_EXTENSIONS = {
    ".pdf",
    ".png", ".jpg", ".jpeg",
    ".tiff", ".tif", ".bmp", ".webp", ".gif",
}


# ─── Helpers ────────────────────────────────────────────────


def _collection_dir(user_id: str, collection_id: str) -> Path:
    return COLLECTION_ROOT / str(user_id) / str(collection_id)


# Standard assets symlinked into every collection workspace so the agent
# has a single self-contained directory with everything it needs.
_WORKSPACE_ASSETS: list[tuple[str, str]] = [
    # (target_inside_container, link_name_in_collection_dir)
    ("/app/SOUL.md",                                              "SOUL.md"),
    ("/cryo-data/models/human1/human1.xml",                      "human1.xml"),
    ("/cryo-data/models/ijo1366/iJO1366.xml.gz",                 "iJO1366.xml.gz"),
    ("/cryo-data/models/yeast8/yeast-GEM.xml",                   "yeast-GEM.xml"),
    ("/cryo-data/models/registry.json",                           "model_registry.json"),
    ("/cryo-data/ccle/ccle_expression_human1.parquet",            "ccle_expression_human1.parquet"),
    ("/cryo-data/ccle/OmicsExpressionTPMLogp1HumanProteinCodingGenes.csv", "ccle_tpm.csv"),
    ("/cryo-data/gdsc/gdsc2_sensitivity.csv",                     "gdsc2_sensitivity.csv"),
]


def _setup_collection_workspace(col_dir: Path) -> None:
    """Create the collection directory and populate it with symlinks to standard assets."""
    col_dir.mkdir(parents=True, exist_ok=True)
    for target, link_name in _WORKSPACE_ASSETS:
        target_path = Path(target)
        link_path = col_dir / link_name
        if target_path.exists() and not link_path.exists():
            link_path.symlink_to(target_path)


def _chat_dir(user_id: str, collection_id: str, conversation_id: str) -> Path:
    return _collection_dir(user_id, collection_id) / "chats" / str(conversation_id)


def _add_chat_symlinks(
    col_dir: Path, conversation_id: str | None,
    orig_dest: Path, md_path: str, original_filename: str,
) -> None:
    """Create symlinks inside chats/{conversation_id}/ pointing at the real files."""
    if not conversation_id:
        return
    chat_dir = col_dir / "chats" / conversation_id
    chat_dir.mkdir(parents=True, exist_ok=True)

    # Symlink to original file using the human-readable name
    orig_link = chat_dir / original_filename
    if not orig_link.exists():
        orig_link.symlink_to(orig_dest)

    # Symlink to markdown using human-readable name
    md_link = chat_dir / (Path(original_filename).stem + ".md")
    if not md_link.exists():
        md_link.symlink_to(md_path)


def _fmt_collection(c: Collection) -> dict:
    return {
        "id": str(c.id),
        "name": c.name,
        "description": c.description,
        "file_count": c.file_count,
        "conversation_id": str(c.conversation_id) if c.conversation_id else None,
        "created_at": c.created_at.isoformat(),
    }


def _fmt_file(f: CollectionFile) -> dict:
    return {
        "id": str(f.id),
        "collection_id": str(f.collection_id),
        "original_filename": f.original_filename,
        "original_path": f.original_path,
        "markdown_path": f.markdown_path,
        "file_size": f.file_size,
        "file_ext": f.file_ext,
        "status": f.status,
        "error_message": f.error_message,
        "created_at": f.created_at.isoformat(),
        "processed_at": f.processed_at.isoformat() if f.processed_at else None,
    }


async def _find_or_create_collection(
    db: AsyncSession,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID | None,
    name: str | None,
) -> Collection:
    """Return the one collection for this session, creating it only when needed.

    Rule: one collection per conversation session.
    - conversation_id set   → find exact match, OR claim the most recent unlinked
                              collection and link it (handles pre-chat uploads).
    - conversation_id None  → reuse the most recent unlinked collection so all
                              pre-chat uploads land in the same bucket.
    """
    if conversation_id:
        # 1. Exact match — already linked to this conversation
        result = await db.execute(
            select(Collection).where(
                Collection.user_id == user_id,
                Collection.conversation_id == conversation_id,
            ).limit(1)
        )
        existing = result.scalar_one_or_none()
        if existing:
            return existing

        # 2. Claim the most recent unlinked collection (files uploaded pre-chat),
        #    but only if it was created recently (same session, not a stale one).
        session_cutoff = datetime.now(timezone.utc) - timedelta(hours=2)
        result = await db.execute(
            select(Collection).where(
                Collection.user_id == user_id,
                Collection.conversation_id.is_(None),
                Collection.created_at >= session_cutoff,
            ).order_by(Collection.created_at.desc()).limit(1)
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.conversation_id = conversation_id
            await db.flush()
            return existing

        # 3. Nothing exists — create linked collection
        collection = Collection(
            user_id=user_id,
            conversation_id=conversation_id,
            name=name or f"Documents {datetime.now(timezone.utc).strftime('%b %d')}",
        )
    else:
        # 1. Reuse most recent unlinked collection created in the last 2 hours
        #    (same session). Older unlinked collections belong to abandoned sessions.
        session_cutoff = datetime.now(timezone.utc) - timedelta(hours=2)
        result = await db.execute(
            select(Collection).where(
                Collection.user_id == user_id,
                Collection.conversation_id.is_(None),
                Collection.created_at >= session_cutoff,
            ).order_by(Collection.created_at.desc()).limit(1)
        )
        existing = result.scalar_one_or_none()
        if existing:
            return existing

        # 2. Nothing exists — create unlinked collection
        collection = Collection(
            user_id=user_id,
            conversation_id=None,
            name=name or f"Documents {datetime.now(timezone.utc).strftime('%b %d')}",
        )

    db.add(collection)
    await db.flush()

    col_dir = _collection_dir(str(user_id), str(collection.id))
    _setup_collection_workspace(col_dir)

    return collection


async def _run_vlm(
    db_url: str, file_id: str, file_path: str, output_path: str,
    col_dir: Path | None = None, conversation_id: str | None = None,
    original_filename: str | None = None,
) -> None:
    """Background task: call VLM service, update DB record, refresh symlinks."""
    from api.core.database import async_session

    async with async_session() as db:
        try:
            await db.execute(
                update(CollectionFile)
                .where(CollectionFile.id == uuid.UUID(file_id))
                .values(status="processing")
            )
            await db.commit()

            result = await vlm_client.process_file(file_path, output_path)

            await db.execute(
                update(CollectionFile)
                .where(CollectionFile.id == uuid.UUID(file_id))
                .values(
                    status="done",
                    markdown_path=result["output_path"],
                    processed_at=datetime.now(timezone.utc),
                )
            )
            await db.commit()
            logger.info(f"VLM done: {file_id} → {result['output_path']}")

            # Re-create symlinks now that the markdown file exists
            if col_dir and conversation_id and original_filename:
                _add_chat_symlinks(
                    col_dir, conversation_id,
                    Path(file_path), result["output_path"], original_filename,
                )

        except Exception as e:
            logger.error(f"VLM failed for {file_id}: {e}")
            await db.execute(
                update(CollectionFile)
                .where(CollectionFile.id == uuid.UUID(file_id))
                .values(status="error", error_message=str(e))
            )
            await db.commit()


# ─── Endpoints ──────────────────────────────────────────────


@router.post("")
async def create_collection(
    name: str = Query(...),
    description: str | None = Query(default=None),
    conversation_id: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conv_id = uuid.UUID(conversation_id) if conversation_id else None
    collection = Collection(
        user_id=current_user.id,
        conversation_id=conv_id,
        name=name,
        description=description,
    )
    db.add(collection)
    await db.commit()
    await db.refresh(collection)

    col_dir = _collection_dir(str(current_user.id), str(collection.id))
    await asyncio.to_thread(_setup_collection_workspace, col_dir)

    return _fmt_collection(collection)


@router.get("")
async def list_collections(
    conversation_id: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Collection).where(Collection.user_id == current_user.id)
    if conversation_id:
        stmt = stmt.where(Collection.conversation_id == uuid.UUID(conversation_id))
    stmt = stmt.order_by(Collection.created_at.desc()).limit(100)
    result = await db.execute(stmt)
    return [_fmt_collection(c) for c in result.scalars().all()]


@router.get("/{collection_id}")
async def get_collection(
    collection_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Collection).where(
            Collection.id == uuid.UUID(collection_id),
            Collection.user_id == current_user.id,
        )
    )
    col = result.scalar_one_or_none()
    if not col:
        raise HTTPException(status_code=404, detail="Collection not found")

    files_result = await db.execute(
        select(CollectionFile)
        .where(CollectionFile.collection_id == uuid.UUID(collection_id))
        .order_by(CollectionFile.created_at.desc())
    )
    files = [_fmt_file(f) for f in files_result.scalars().all()]
    return {**_fmt_collection(col), "files": files}


@router.delete("/{collection_id}")
async def delete_collection(
    collection_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Collection).where(
            Collection.id == uuid.UUID(collection_id),
            Collection.user_id == current_user.id,
        )
    )
    col = result.scalar_one_or_none()
    if not col:
        raise HTTPException(status_code=404, detail="Collection not found")

    col_dir = _collection_dir(str(current_user.id), collection_id)
    import shutil
    if col_dir.exists():
        await asyncio.to_thread(shutil.rmtree, str(col_dir), ignore_errors=True)

    await db.delete(col)
    await db.commit()
    return {"deleted": collection_id}


@router.post("/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    collection_id: str | None = Query(default=None),
    collection_name: str | None = Query(default=None),
    conversation_id: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    original_name = file.filename or "upload"
    ext = Path(original_name).suffix.lower()
    if ext not in DOCUMENT_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported document type '{ext}'. Allowed: PDF and images.",
        )

    # Resolve collection
    if collection_id:
        result = await db.execute(
            select(Collection).where(
                Collection.id == uuid.UUID(collection_id),
                Collection.user_id == current_user.id,
            )
        )
        col = result.scalar_one_or_none()
        if not col:
            raise HTTPException(status_code=404, detail="Collection not found")
    else:
        conv_id = uuid.UUID(conversation_id) if conversation_id else None
        col_name = collection_name or Path(original_name).stem
        col = await _find_or_create_collection(db, current_user.id, conv_id, col_name)

    # Prepare directories
    col_dir = _collection_dir(str(current_user.id), str(col.id))
    orig_dir = col_dir / ".original"
    await asyncio.to_thread(orig_dir.mkdir, parents=True, exist_ok=True)

    stored_name = f"{uuid.uuid4().hex}_{original_name}"
    dest = orig_dir / stored_name

    # Stream to disk
    size = 0
    try:
        with dest.open("wb") as f:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_FILE_SIZE:
                    dest.unlink(missing_ok=True)
                    raise HTTPException(status_code=413, detail="File exceeds 500 MB limit")
                f.write(chunk)
    except HTTPException:
        raise
    except Exception as e:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")

    # Output markdown path
    md_name = Path(stored_name).stem + ".md"
    md_path = str(col_dir / md_name)

    # Create DB record
    file_record = CollectionFile(
        collection_id=col.id,
        user_id=current_user.id,
        original_filename=original_name,
        original_path=str(dest),
        file_size=size,
        file_ext=ext,
        status="pending",
    )
    db.add(file_record)

    # Increment collection file_count
    col.file_count = (col.file_count or 0) + 1
    col.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(file_record)

    # Create chat-scoped symlinks immediately (orig file exists; md will be added after VLM)
    conv_id_str = str(col.conversation_id) if col.conversation_id else None
    await asyncio.to_thread(
        _add_chat_symlinks, col_dir, conv_id_str, dest, md_path, original_name
    )

    # Kick off VLM processing in background
    background_tasks.add_task(
        _run_vlm, "", str(file_record.id), str(dest), md_path, col_dir, conv_id_str, original_name
    )

    return {
        **_fmt_file(file_record),
        "collection": _fmt_collection(col),
    }


@router.get("/{collection_id}/files/{file_id}")
async def get_file_status(
    collection_id: str,
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CollectionFile).where(
            CollectionFile.id == uuid.UUID(file_id),
            CollectionFile.collection_id == uuid.UUID(collection_id),
            CollectionFile.user_id == current_user.id,
        )
    )
    f = result.scalar_one_or_none()
    if not f:
        raise HTTPException(status_code=404, detail="File not found")

    data = _fmt_file(f)
    # Include markdown content if done
    if f.status == "done" and f.markdown_path and Path(f.markdown_path).exists():
        data["markdown"] = Path(f.markdown_path).read_text(encoding="utf-8")
    return data


@router.get("/{collection_id}/search")
async def search_collection(
    collection_id: str,
    q: str = Query(..., min_length=1),
    limit: int = Query(default=10, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Collection).where(
            Collection.id == uuid.UUID(collection_id),
            Collection.user_id == current_user.id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Collection not found")

    files_result = await db.execute(
        select(CollectionFile).where(
            CollectionFile.collection_id == uuid.UUID(collection_id),
            CollectionFile.status == "done",
        )
    )
    files = files_result.scalars().all()

    q_lower = q.lower()
    matches = []
    for f in files:
        if not f.markdown_path or not Path(f.markdown_path).exists():
            continue
        text = Path(f.markdown_path).read_text(encoding="utf-8")
        lines = text.split("\n")
        snippets = [
            ln.strip() for ln in lines
            if q_lower in ln.lower() and ln.strip()
        ]
        if snippets:
            matches.append({
                "file_id": str(f.id),
                "filename": f.original_filename,
                "snippets": snippets[:5],
            })
        if len(matches) >= limit:
            break

    return {"query": q, "collection_id": collection_id, "matches": matches}
