import json
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.auth import get_current_user
from api.core.database import get_db
from api.models.conversation import Conversation, Message
from api.models.user import User
from api.services.hermes_bridge import HermesBridge

router = APIRouter(prefix="/chat", tags=["chat"])

bridge = HermesBridge()


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None


class ConversationOut(BaseModel):
    id: str
    title: str | None
    model: str
    message_count: int
    created_at: str
    updated_at: str


class MessageOut(BaseModel):
    id: str
    role: str
    content: str | None
    tool_calls: dict | None = None
    created_at: str


# ─── Conversations CRUD ──────────────────────────────────

@router.get("/conversations", response_model=list[ConversationOut])
async def list_conversations(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == user.id, Conversation.status == "active")
        .order_by(Conversation.updated_at.desc())
        .limit(50)
    )
    convos = result.scalars().all()
    return [
        ConversationOut(
            id=str(c.id), title=c.title, model=c.model,
            message_count=c.message_count,
            created_at=c.created_at.isoformat(), updated_at=c.updated_at.isoformat(),
        )
        for c in convos
    ]


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageOut])
async def get_messages(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    convo = await _get_user_conversation(db, user.id, conversation_id)
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == convo.id)
        .order_by(Message.created_at)
    )
    msgs = result.scalars().all()
    return [
        MessageOut(
            id=str(m.id), role=m.role, content=m.content,
            tool_calls=m.tool_calls, created_at=m.created_at.isoformat(),
        )
        for m in msgs
    ]


@router.delete("/conversations/{conversation_id}")
async def archive_conversation(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    convo = await _get_user_conversation(db, user.id, conversation_id)
    convo.status = "archived"
    return {"ok": True}


# ─── Chat (streaming SSE) ────────────────────────────────

@router.post("/send")
async def send_message(
    req: ChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Get or create conversation
    if req.conversation_id:
        convo = await _get_user_conversation(db, user.id, req.conversation_id)
    else:
        convo = Conversation(user_id=user.id, title=req.message[:80])
        db.add(convo)
        await db.flush()

    # Save user message
    user_msg = Message(conversation_id=convo.id, role="user", content=req.message)
    db.add(user_msg)
    convo.message_count += 1
    await db.flush()

    # Build conversation history for Hermes
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == convo.id)
        .order_by(Message.created_at)
    )
    history = [
        {"role": m.role, "content": m.content}
        for m in result.scalars().all()
        if m.content
    ]

    # Stream response via SSE
    async def event_stream() -> AsyncGenerator[str, None]:
        full_response = []

        async for event in bridge.chat_stream(req.message, history):
            event_type = event.get("type", "delta")

            if event_type == "delta":
                text = event.get("text", "")
                full_response.append(text)
                yield f"data: {json.dumps({'type': 'delta', 'text': text})}\n\n"

            elif event_type == "tool_start":
                yield f"data: {json.dumps({'type': 'tool_start', 'name': event.get('name'), 'args': event.get('args')})}\n\n"

            elif event_type == "tool_result":
                yield f"data: {json.dumps({'type': 'tool_result', 'name': event.get('name'), 'result': event.get('result')})}\n\n"

        # Save assistant message
        final_text = "".join(full_response)
        async with db.begin_nested():
            assistant_msg = Message(conversation_id=convo.id, role="assistant", content=final_text)
            db.add(assistant_msg)
            convo.message_count += 1

        yield f"data: {json.dumps({'type': 'done', 'conversation_id': str(convo.id)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ─── Tools / Slash commands ──────────────────────────────

@router.get("/tools")
async def list_tools(user: User = Depends(get_current_user)):
    """Return available tools and slash commands for the UI autocomplete."""
    return bridge.get_available_tools()


# ─── Helpers ──────────────────────────────────────────────

async def _get_user_conversation(db: AsyncSession, user_id: uuid.UUID, convo_id: str) -> Conversation:
    try:
        convo_uuid = uuid.UUID(convo_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid conversation ID format")

    result = await db.execute(
        select(Conversation).where(
            Conversation.id == convo_uuid,
            Conversation.user_id == user_id,
        )
    )
    convo = result.scalar_one_or_none()
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return convo
