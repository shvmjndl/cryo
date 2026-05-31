"""CRYO Collections Tool — query document collections (PDF/image → VLM markdown).

Auto-discovers the collection for the current chat session via CRYO_CONVERSATION_ID.
"""

import json
import logging
import os
from pathlib import Path

import httpx

from tools.registry import registry

logger = logging.getLogger("cryo.collections")

API_BASE = os.getenv("CRYO_API_BASE", "http://localhost:8000/api")
TIMEOUT = 30


def _api(method: str, path: str, token: str, **kwargs):
    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(timeout=TIMEOUT) as client:
        resp = getattr(client, method)(f"{API_BASE}{path}", headers=headers, **kwargs)
        resp.raise_for_status()
        return resp.json()


def _resolve_collection_id(inputs: dict, token: str) -> str | None:
    col_id = inputs.get("collection_id")
    if col_id:
        return col_id

    conversation_id = os.getenv("CRYO_CONVERSATION_ID", "").strip()
    if conversation_id:
        cols = _api("get", "/collections", token, params={"conversation_id": conversation_id})
        if cols:
            return cols[0]["id"]

    all_cols = _api("get", "/collections", token)
    if all_cols:
        return all_cols[0]["id"]

    return None


def _collections_handler(args: dict, **kw) -> str:
    token = os.getenv("CRYO_USER_TOKEN", "")
    if not token:
        return json.dumps({"error": "No auth token available (CRYO_USER_TOKEN not set)"})

    action = args.get("action", "list")

    try:
        # ── list ──────────────────────────────────────────────────────────
        if action == "list":
            conversation_id = os.getenv("CRYO_CONVERSATION_ID", "").strip()
            params = {"conversation_id": conversation_id} if conversation_id else {}
            cols = _api("get", "/collections", token, params=params)
            if not cols:
                return "No documents found for this chat session. Upload a PDF or image to get started."
            lines = ["**Documents in this chat:**\n"]
            for c in cols:
                lines.append(f"**Collection: {c['name']}** (id: `{c['id']}`), {c['file_count']} file(s)")
            if cols:
                col = _api("get", f"/collections/{cols[0]['id']}", token)
                for f in col.get("files", []):
                    badge = {"done": "✓", "processing": "⏳", "pending": "⏳", "error": "✗"}.get(f["status"], "?")
                    lines.append(f"  {badge} {f['original_filename']} (status: {f['status']}, id: `{f['id']}`)")
            return "\n".join(lines)

        # ── get ───────────────────────────────────────────────────────────
        if action == "get":
            col_id = _resolve_collection_id(args, token)
            if not col_id:
                return "No collection found for this chat. Upload a PDF or image first."
            col = _api("get", f"/collections/{col_id}", token)
            lines = [
                f"**Collection: {col['name']}**",
                f"ID: `{col['id']}`",
                f"Files: {col['file_count']}\n",
                "**Files:**",
            ]
            for f in col.get("files", []):
                badge = {"done": "✓", "processing": "⏳", "pending": "⏳", "error": "✗"}.get(f["status"], "?")
                lines.append(f"  {badge} `{f['id']}` — {f['original_filename']} ({f['status']})")
            return "\n".join(lines)

        # ── read_file ─────────────────────────────────────────────────────
        if action == "read_file":
            col_id = _resolve_collection_id(args, token)
            file_id = args.get("file_id")
            if not col_id:
                return "No collection found for this chat. Upload a PDF or image first."
            if not file_id:
                return "Error: file_id is required for 'read_file' action."
            data = _api("get", f"/collections/{col_id}/files/{file_id}", token)
            if data.get("status") != "done":
                return (
                    f"File '{data['original_filename']}' is not yet ready "
                    f"(status: {data['status']}). Try again in a moment."
                )
            md = data.get("markdown", "")
            if not md:
                # Try reading from path directly
                md_path = data.get("markdown_path", "")
                if md_path and Path(md_path).exists():
                    md = Path(md_path).read_text(encoding="utf-8")
            if not md:
                return f"Markdown not available for '{data['original_filename']}'."
            preview = md[:8000] + ("\n\n... [truncated]" if len(md) > 8000 else "")
            return f"**{data['original_filename']}** (parsed markdown):\n\n{preview}"

        # ── search ────────────────────────────────────────────────────────
        if action == "search":
            col_id = _resolve_collection_id(args, token)
            query = args.get("query", "").strip()
            if not col_id:
                return "No collection found for this chat. Upload a PDF or image first."
            if not query:
                return "Error: query is required for 'search' action."
            limit = args.get("limit", 10)
            data = _api("get", f"/collections/{col_id}/search", token, params={"q": query, "limit": limit})
            matches = data.get("matches", [])
            if not matches:
                return f"No matches found for '{query}' in the documents for this chat."
            lines = [f"**Search results for '{query}':**\n"]
            for m in matches:
                lines.append(f"**{m['filename']}** (file_id: `{m['file_id']}`):")
                for snip in m["snippets"]:
                    lines.append(f"  > {snip}")
                lines.append("")
            return "\n".join(lines)

        # ── status ────────────────────────────────────────────────────────
        if action == "status":
            col_id = _resolve_collection_id(args, token)
            file_id = args.get("file_id")
            if not col_id:
                return "No collection found for this chat."
            if not file_id:
                return "Error: file_id is required for 'status' action."
            data = _api("get", f"/collections/{col_id}/files/{file_id}", token)
            return (
                f"**{data['original_filename']}**: status={data['status']}, "
                f"processed_at={data.get('processed_at') or 'pending'}"
                + (f"\nError: {data['error_message']}" if data.get("error_message") else "")
            )

        return f"Unknown action: {action}"

    except Exception as e:
        logger.error("collections tool error: %s", e)
        return json.dumps({"error": str(e)})


COLLECTIONS_SCHEMA = {
    "name": "collections",
    "description": (
        "Query the user's document collections. "
        "Documents (PDFs, images) uploaded in this chat are parsed to Markdown via VLM OCR. "
        "Auto-resolves the collection from the current chat session — no collection_id needed. "
        "Use to list, read, or search uploaded documents."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "get", "read_file", "search", "status"],
                "description": (
                    "list=list documents in this chat's collection; "
                    "get=collection details + file list; "
                    "read_file=full markdown of a specific file; "
                    "search=search across all documents; "
                    "status=check processing status of a file"
                ),
            },
            "collection_id": {
                "type": "string",
                "description": "Collection UUID. Optional — auto-resolved from current chat session.",
            },
            "file_id": {
                "type": "string",
                "description": "CollectionFile UUID (required for read_file and status actions)",
            },
            "query": {
                "type": "string",
                "description": "Search query string (required for search action)",
            },
            "limit": {
                "type": "integer",
                "description": "Max results to return for search (default 10)",
                "default": 10,
            },
        },
        "required": ["action"],
    },
}

registry.register(
    name="collections",
    toolset="cryo_collections",
    schema=COLLECTIONS_SCHEMA,
    handler=_collections_handler,
    check_fn=lambda: True,
    emoji="📄",
)
