import os
import uuid
from fastapi import APIRouter, Depends, HTTPException

MAX_WORKSPACES = int(os.getenv("CRYO_MAX_WORKSPACES_PER_USER", "10"))
MAX_NODES = int(os.getenv("CRYO_MAX_NODES_PER_WORKSPACE", "50"))
from pydantic import BaseModel
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.core.auth import get_current_user
from api.core.database import get_db
from api.models.user import User
from api.models.workspace import Workspace, WorkspaceNode, WorkspaceEdge

router = APIRouter(prefix="/workspace", tags=["workspace"])


class NodeData(BaseModel):
    id: str
    title: str = "New Research"
    conversation_id: str | None = None
    parent_node_id: str | None = None
    position_x: float = 0
    position_y: float = 0
    width: float = 400
    minimized: bool = False
    branch_context: str | None = None


class EdgeData(BaseModel):
    id: str
    source_node_id: str
    target_node_id: str
    label: str | None = None


class WorkspaceSaveRequest(BaseModel):
    nodes: list[NodeData]
    edges: list[EdgeData]


def _ws_to_dict(ws: Workspace) -> dict:
    return {
        "id": str(ws.id),
        "name": ws.name,
        "nodes": [{
            "id": n.id, "title": n.title,
            "conversation_id": str(n.conversation_id) if n.conversation_id else None,
            "parent_node_id": n.parent_node_id,
            "position_x": n.position_x, "position_y": n.position_y,
            "width": n.width, "minimized": n.minimized,
            "branch_context": n.branch_context,
        } for n in ws.nodes],
        "edges": [{
            "id": e.id,
            "source_node_id": e.source_node_id,
            "target_node_id": e.target_node_id,
            "label": e.label,
        } for e in ws.edges],
    }


# ─── List all workspaces ──────────────────────────────────

@router.get("/list")
async def list_workspaces(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Workspace)
        .where(Workspace.user_id == user.id, Workspace.is_active == True)
        .order_by(Workspace.updated_at.desc())
    )
    wss = result.scalars().all()

    # Auto-create first workspace if user has none
    if not wss:
        ws = Workspace(user_id=user.id, name="Research 1")
        db.add(ws)
        await db.flush()
        wss = [ws]

    return [{"id": str(w.id), "name": w.name} for w in wss]


# ─── Get specific workspace ───────────────────────────────

@router.get("/{workspace_id}")
async def get_workspace(
    workspace_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Workspace)
        .where(Workspace.id == uuid.UUID(workspace_id), Workspace.user_id == user.id)
        .options(selectinload(Workspace.nodes), selectinload(Workspace.edges))
    )
    ws = result.scalar_one_or_none()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return _ws_to_dict(ws)


# ─── Create new workspace ─────────────────────────────────

@router.post("/create")
async def create_workspace(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    existing = (await db.execute(
        select(Workspace).where(Workspace.user_id == user.id, Workspace.is_active == True)
    )).scalars().all()

    if len(existing) >= MAX_WORKSPACES:
        raise HTTPException(status_code=400, detail=f"Maximum {MAX_WORKSPACES} workspaces per user")

    ws = Workspace(user_id=user.id, name=f"Research {len(existing) + 1}")
    db.add(ws)
    await db.flush()
    return {"id": str(ws.id), "name": ws.name}


# ─── Rename workspace ─────────────────────────────────────

@router.patch("/{workspace_id}")
async def rename_workspace(
    workspace_id: str,
    name: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Workspace).where(Workspace.id == uuid.UUID(workspace_id), Workspace.user_id == user.id)
    )
    ws = result.scalar_one_or_none()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    ws.name = name
    return {"ok": True}


# ─── Delete workspace ─────────────────────────────────────

@router.delete("/{workspace_id}")
async def delete_workspace(
    workspace_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Workspace).where(Workspace.id == uuid.UUID(workspace_id), Workspace.user_id == user.id)
    )
    ws = result.scalar_one_or_none()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")

    await db.execute(delete(WorkspaceEdge).where(WorkspaceEdge.workspace_id == ws.id))
    await db.execute(delete(WorkspaceNode).where(WorkspaceNode.workspace_id == ws.id))
    await db.delete(ws)
    return {"ok": True}


# ─── Save workspace state ─────────────────────────────────

@router.post("/{workspace_id}/save")
async def save_workspace(
    workspace_id: str,
    req: WorkspaceSaveRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Workspace).where(Workspace.id == uuid.UUID(workspace_id), Workspace.user_id == user.id)
    )
    ws = result.scalar_one_or_none()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")

    if len(req.nodes) > MAX_NODES:
        raise HTTPException(status_code=400, detail=f"Maximum {MAX_NODES} nodes per workspace")

    await db.execute(delete(WorkspaceEdge).where(WorkspaceEdge.workspace_id == ws.id))
    await db.execute(delete(WorkspaceNode).where(WorkspaceNode.workspace_id == ws.id))

    for n in req.nodes:
        db.add(WorkspaceNode(
            id=n.id, workspace_id=ws.id,
            conversation_id=n.conversation_id if n.conversation_id else None,
            parent_node_id=n.parent_node_id, title=n.title,
            position_x=n.position_x, position_y=n.position_y,
            width=n.width, minimized=n.minimized, branch_context=n.branch_context,
        ))

    for e in req.edges:
        db.add(WorkspaceEdge(
            id=e.id, workspace_id=ws.id,
            source_node_id=e.source_node_id, target_node_id=e.target_node_id, label=e.label,
        ))

    return {"ok": True, "nodes": len(req.nodes), "edges": len(req.edges)}
