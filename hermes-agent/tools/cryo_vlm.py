"""CRYO VLM (Vision Language Model) Tool — Gemini vision for image analysis."""

import base64
import json
import logging
import os
from pathlib import Path

from tools.registry import registry

logger = logging.getLogger("cryo.vlm")


def _analyze_image(args: dict, **kw) -> str:
    image_path = args.get("image_path", "").strip()
    image_url = args.get("image_url", "").strip()
    prompt = args.get("prompt", "Analyze this image in detail.").strip()

    if not image_path and not image_url:
        return json.dumps({"error": "Provide image_path (local file) or image_url"})

    api_key = os.getenv("GEMINI_API_KEY", "")
    model = os.getenv("HERMES_VLM_MODEL", "gemini-2.5-flash")

    if not api_key:
        return json.dumps({"error": "GEMINI_API_KEY not set"})

    logger.info("VLM analysis: path=%r url=%r prompt=%r model=%s", image_path, image_url, prompt[:50], model)

    try:
        import httpx

        # Build content parts
        parts = [{"text": prompt}]

        if image_path:
            p = Path(image_path)
            if not p.exists():
                return json.dumps({"error": f"Image file not found: {image_path}"})

            mime_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                        ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp"}
            mime = mime_map.get(p.suffix.lower(), "image/png")
            b64 = base64.b64encode(p.read_bytes()).decode()
            parts.append({
                "inline_data": {"mime_type": mime, "data": b64}
            })

        elif image_url:
            parts.append({
                "file_data": {"mime_type": "image/*", "file_uri": image_url}
            })

        # Call Gemini API
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 4096},
        }

        with httpx.Client(timeout=60) as client:
            r = client.post(url, json=payload, params={"key": api_key})
            r.raise_for_status()
            data = r.json()

        # Extract response text
        candidates = data.get("candidates", [])
        if not candidates:
            return json.dumps({"error": "No response from VLM", "raw": data})

        text = ""
        for part in candidates[0].get("content", {}).get("parts", []):
            text += part.get("text", "")

        logger.info("VLM analysis complete: %d chars", len(text))
        return json.dumps({
            "status": "success",
            "analysis": text,
            "model": model,
            "tokens": data.get("usageMetadata", {}),
        })

    except Exception as e:
        logger.error("VLM analysis failed: %s", e, exc_info=True)
        return json.dumps({"error": f"VLM analysis failed: {e}"})


VLM_SCHEMA = {
    "name": "analyze_image_vlm",
    "description": "Analyze images using Gemini Vision Language Model. Can interpret microscopy images, gel electrophoresis, protein structures, charts, diagrams, pathway maps, and any scientific figure. Also useful for analyzing generated charts.",
    "parameters": {
        "type": "object",
        "properties": {
            "image_path": {
                "type": "string",
                "description": "Local file path to the image (PNG, JPG, WebP)"
            },
            "image_url": {
                "type": "string",
                "description": "URL of the image to analyze"
            },
            "prompt": {
                "type": "string",
                "description": "What to analyze or look for in the image (e.g. 'Identify the protein bands in this gel image', 'Describe this pathway diagram')"
            },
        },
        "required": ["prompt"],
    },
}

registry.register(
    name="analyze_image_vlm",
    toolset="cryo_vlm",
    schema=VLM_SCHEMA,
    handler=_analyze_image,
    check_fn=lambda: bool(os.getenv("GEMINI_API_KEY")),
    requires_env=["GEMINI_API_KEY"],
    emoji="👁️",
)
