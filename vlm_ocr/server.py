"""Thin FastAPI wrapper around VLMOCRPipeline — runs as a separate Docker service."""

import logging
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .config import OCRConfig
from .ocr_pipeline import VLMOCRPipeline

app = FastAPI(title="CRYO VLM OCR Service")
logger = logging.getLogger(__name__)

_pipeline: VLMOCRPipeline | None = None


def _get_pipeline() -> VLMOCRPipeline:
    global _pipeline
    if _pipeline is None:
        model = os.getenv("VLM_MODEL", "gemini/gemini-2.0-flash")
        _pipeline = VLMOCRPipeline(OCRConfig(model=model))
    return _pipeline


class ProcessRequest(BaseModel):
    file_path: str
    output_path: str | None = None


class ProcessResponse(BaseModel):
    output_path: str
    content: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/process", response_model=ProcessResponse)
async def process_file(req: ProcessRequest):
    path = Path(req.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {req.file_path}")
    try:
        pipeline = _get_pipeline()
        output_path = await pipeline.process_file_async(req.file_path, req.output_path)
        content = Path(output_path).read_text(encoding="utf-8")
        return ProcessResponse(output_path=output_path, content=content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"VLM processing failed for {req.file_path}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
