"""HTTP client for the VLM OCR service (runs at VLM_SERVICE_URL)."""

import logging
import os

import httpx

logger = logging.getLogger(__name__)

VLM_SERVICE_URL = os.getenv("VLM_SERVICE_URL", "http://vlm:8100")
_TIMEOUT = httpx.Timeout(600.0, connect=10.0)  # VLM can be slow for large PDFs


async def process_file(file_path: str, output_path: str | None = None) -> dict:
    """Send a file to the VLM service for OCR. Returns {output_path, content}."""
    payload = {"file_path": file_path}
    if output_path:
        payload["output_path"] = output_path

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(f"{VLM_SERVICE_URL}/process", json=payload)
        resp.raise_for_status()
        return resp.json()


async def health() -> bool:
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
            resp = await client.get(f"{VLM_SERVICE_URL}/health")
            return resp.status_code == 200
    except Exception:
        return False
