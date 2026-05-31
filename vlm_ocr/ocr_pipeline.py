"""VLM OCR Pipeline — converts PDFs and images to structured Markdown using Vision LLMs.

Processing strategy:
  - Small PDFs (<=native_pdf_max_pages): Native PDF passthrough (Gemini/Claude)
  - Large PDFs: Page-by-page image processing for guaranteed per-page accuracy
  - Images: Direct image processing

All file I/O is offloaded to threads to keep the event loop non-blocking.
"""

import asyncio
import base64
import gc
import io
import json
import logging
import os
import re
import time
import uuid
from functools import partial
from pathlib import Path
from typing import Optional

import litellm
from PIL import Image

from .config import OCRConfig
from .prompts import PAGE_PROMPT, PDF_PROMPT, SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# Suppress litellm's verbose debug/info logging
litellm.suppress_debug_info = True

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp", ".gif"}
PDF_EXTENSIONS = {".pdf"}
SUPPORTED_EXTENSIONS = IMAGE_EXTENSIONS | PDF_EXTENSIONS


# ---------------------------------------------------------------------------
# Post-processing helpers
# ---------------------------------------------------------------------------

def _strip_code_fences(text: str) -> str:
    """Remove code fences the model sometimes adds despite instructions."""
    text = re.sub(r"^```(?:markdown|html|md)?\s*\n?", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n?```\s*$", "", text, flags=re.MULTILINE)
    return text.strip()


def _fix_plain_label_value_pairs(text: str) -> str:
    """Wrap consecutive plain-text label:value lines in <table> rows."""
    _single_line_lv = re.compile(r"^([^<!\-#|*:][^:]{1,50}?)\s*:\s*(.+)$")

    lines = text.split("\n")
    result: list[str] = []
    i = 0
    in_table = False

    def _is_plain_text(s: str) -> bool:
        return bool(s) and not s.startswith(("<", "!", "#", "|", "*", "---", "<!--"))

    while i < len(lines):
        stripped = lines[i].strip()

        if "<table" in stripped.lower():
            in_table = True
        if "</table" in stripped.lower():
            in_table = False
        if stripped.startswith("<!--") or stripped == "---":
            in_table = False

        if in_table or stripped.startswith("<!--") or stripped.startswith("---"):
            result.append(lines[i])
            i += 1
            continue

        pairs: list[tuple[str, str]] = []
        skipped: list[str] = []
        j = i
        while j < len(lines):
            s = lines[j].strip()
            if not _is_plain_text(s):
                break
            if j + 1 < len(lines) and lines[j + 1].strip().startswith(":"):
                pairs.append((s, lines[j + 1].strip().lstrip(":").strip()))
                j += 2
                continue
            m = _single_line_lv.match(s)
            if m:
                pairs.append((m.group(1).strip(), m.group(2).strip()))
                j += 1
                continue
            if not pairs:
                skipped.append(lines[j])
                j += 1
                continue
            break

        if len(pairs) >= 2:
            result.extend(skipped)
            result.append("<table>")
            for label, value in pairs:
                result.append(
                    f"<tr><td><strong>{label}</strong></td><td>{value}</td></tr>"
                )
            result.append("</table>")
            i = j
            continue

        result.append(lines[i])
        i += 1

    return "\n".join(result)


# ---------------------------------------------------------------------------
# Sync I/O helpers (run via asyncio.to_thread in async context)
# ---------------------------------------------------------------------------

def _image_to_base64(img: Image.Image, fmt: str = "PNG") -> str:
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    mime = "image/png" if fmt == "PNG" else f"image/{fmt.lower()}"
    return f"data:{mime};base64,{b64}"


def _read_file_base64(file_path: str) -> str:
    with open(file_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _pdf_to_images(pdf_path: str, dpi: int = 200) -> list[Image.Image]:
    import fitz

    doc = fitz.open(pdf_path)
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)
    images = []
    for page in doc:
        pix = page.get_pixmap(matrix=matrix)
        images.append(Image.frombytes("RGB", [pix.width, pix.height], pix.samples))
    doc.close()
    return images


def _pdf_page_to_image(pdf_path: str, page_num: int, dpi: int = 200) -> Image.Image:
    """Render a single PDF page to an image, keeping memory usage bounded."""
    import fitz

    doc = fitz.open(pdf_path)
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)
    page = doc.load_page(page_num)
    pix = page.get_pixmap(matrix=matrix)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    doc.close()
    return img


def _load_image_file(file_path: str) -> list[Image.Image]:
    img = Image.open(file_path)
    if img.mode != "RGB":
        img = img.convert("RGB")
    return [img]


def _count_pdf_pages(pdf_path: str) -> int:
    import fitz

    doc = fitz.open(pdf_path)
    n = len(doc)
    doc.close()
    return n


def _write_file(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


# ---------------------------------------------------------------------------
# Provider-specific message builders
# ---------------------------------------------------------------------------

def _build_gemini_pdf_messages(pdf_b64: str, system_prompt: str) -> list[dict]:
    return [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": [
                {
                    "type": "file",
                    "file": {
                        "file_data": f"data:application/pdf;base64,{pdf_b64}",
                        "filename": "document.pdf",
                    },
                },
                {"type": "text", "text": PDF_PROMPT},
            ],
        },
    ]


def _build_openai_pdf_messages(pdf_b64: str, system_prompt: str) -> list[dict]:
    """OpenAI PDF input via Chat Completions `file` content type.

    Same wire format as Gemini's `_build_gemini_pdf_messages` — both providers
    accept `{"type": "file", "file": {"file_data": "data:application/pdf;base64,...",
    "filename": "..."}}`. Kept as a separate builder so a future divergence
    (e.g. OpenAI adding options like `file_id` references) doesn't require
    touching the Gemini path.
    """
    return [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": [
                {
                    "type": "file",
                    "file": {
                        "file_data": f"data:application/pdf;base64,{pdf_b64}",
                        "filename": "document.pdf",
                    },
                },
                {"type": "text", "text": PDF_PROMPT},
            ],
        },
    ]


def _build_claude_pdf_messages(pdf_b64: str, system_prompt: str) -> list[dict]:
    return [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": [
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": pdf_b64,
                    },
                },
                {"type": "text", "text": PDF_PROMPT},
            ],
        },
    ]


def _build_image_messages(
    b64_image: str, system_prompt: str, detail: str = "high"
) -> list[dict]:
    return [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": b64_image, "detail": detail},
                },
                {"type": "text", "text": PAGE_PROMPT},
            ],
        },
    ]


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class VLMOCRPipeline:
    """OCR pipeline using Vision Language Models via LiteLLM.

    Processing strategy:
      - Small PDFs (<=native_pdf_max_pages): Native PDF passthrough
      - Large PDFs (>native_pdf_max_pages): Page-by-page as images
      - Images: Direct processing

    Usage::

        from frameworks.vlm_ocr import VLMOCRPipeline, OCRConfig

        pipeline = VLMOCRPipeline(OCRConfig.for_provider("gemini"))
        output = pipeline.process_file("invoice.pdf")
    """

    def __init__(self, config: Optional[OCRConfig] = None):
        self.config = config or OCRConfig()

        # Logical → actual model name mapping. Mirrors the pattern in
        # src/kgwizard/providers/llm/providers/openai.py: config-level dict
        # seeds the mapping, and OPENAI_MODEL_MAPPING (JSON env var) overrides
        # it at startup. Keeps prod routing consistent between the main app
        # and the VLM OCR service — one SSM value drives both.
        self._model_mapping = dict(self.config.model_name_mapping or {})
        env_mapping = os.getenv("OPENAI_MODEL_MAPPING")
        if env_mapping:
            try:
                self._model_mapping = json.loads(env_mapping)
            except json.JSONDecodeError:
                logger.warning(
                    "Invalid JSON in OPENAI_MODEL_MAPPING, keeping config mapping"
                )

    def _get_model_name(self, model: str) -> str:
        """Map logical model name to the actual upstream model name.

        Returns the input unchanged when no mapping matches, so unprefixed and
        provider-prefixed strings (e.g. `gpt-4o`, `openai/gpt-4o`,
        `gemini/gemini-2.0-flash`) pass through litellm correctly.
        """
        mapped = self._model_mapping.get(model, model)
        if mapped != model:
            logger.debug(f"Mapped VLM OCR model '{model}' → '{mapped}'")
        return mapped

    def _extra_kwargs(self) -> dict:
        kwargs = {}
        if self.config.provider == "claude":
            kwargs["extra_headers"] = {"anthropic-beta": "pdfs-2024-09-25"}
        return kwargs

    def _uses_openai_sdk(self, model: str) -> bool:
        """True when we should bypass litellm and call the OpenAI SDK directly.

        Rationale: litellm strips provider prefixes (`azure/`, `openai/`) when
        dispatching, so model `azure/gpt-5.2` becomes `gpt-5.2` on the wire.
        The titan gateway (ai.titan.in/gateway) rejects bare names and wants
        the full qualified id. Going through openai.AsyncOpenAI preserves the
        exact string we pass in the request body and routes via OPENAI_BASE_URL,
        which the gateway accepts for both `openai/*` and `azure/*` models.
        """
        m = model.lower()
        # Everything that's not Gemini/Claude goes through OpenAI SDK.
        # Gemini/Claude keep litellm (native multimodal handling).
        return not (m.startswith(("gemini/", "google/", "anthropic/")) or "claude" in m)

    async def _call_openai_sdk(self, messages: list) -> str:
        """Direct openai.AsyncOpenAI call. Sends `model` verbatim — no prefix
        stripping — to OPENAI_BASE_URL (the gateway in prod). Returns assistant
        content.

        Parameters come from the same config knobs as the litellm path so
        callers don't need to distinguish.
        """
        from openai import AsyncOpenAI

        model = self._get_model_name(self.config.model)
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("AZURE_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL")
        # OPENAI_BASE_URL must point to something OpenAI-API-compatible. For
        # the titan gateway it's `https://ai.titan.in/gateway` → the SDK
        # appends `/v1/chat/completions` on its own.
        client = AsyncOpenAI(api_key=api_key, base_url=base_url)

        # Reasoning-family detection — matches `gpt-5`, `openai/gpt-5.2`,
        # `azure/gpt-5.2-chat`, `o1`, `o3`, `openai/o3`, etc. These reject
        # `temperature` and want `max_completion_tokens` instead of `max_tokens`.
        ml = model.lower()
        is_reasoning = any(
            ml.startswith(p) or f"/{p}" in ml
            for p in ("o1", "o3", "o4", "gpt-5")
        )

        kwargs = dict(model=model, messages=messages)
        if self.config.max_tokens:
            if is_reasoning:
                kwargs["max_completion_tokens"] = self.config.max_tokens
            else:
                kwargs["max_tokens"] = self.config.max_tokens
        if not is_reasoning:
            kwargs["temperature"] = self.config.temperature

        resp = await client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content

    # ------ Native PDF (small files only) ------

    async def _process_pdf_native(self, pdf_path: str) -> str:
        """Process a small PDF natively — sends raw bytes to the provider."""
        pdf_b64 = await asyncio.to_thread(_read_file_base64, pdf_path)
        system_prompt = self.config.system_prompt or SYSTEM_PROMPT
        provider = self.config.provider

        if provider == "gemini":
            messages = _build_gemini_pdf_messages(pdf_b64, system_prompt)
        elif provider == "claude":
            messages = _build_claude_pdf_messages(pdf_b64, system_prompt)
        elif provider == "openai":
            messages = _build_openai_pdf_messages(pdf_b64, system_prompt)
        else:
            raise ValueError(f"Native PDF not supported for provider: {provider}")

        for attempt in range(1, self.config.max_retries + 1):
            try:
                if self._uses_openai_sdk(self.config.model):
                    # Direct OpenAI SDK — preserves full model string (no
                    # litellm prefix stripping). Routes to OPENAI_BASE_URL.
                    content = await self._call_openai_sdk(messages)
                else:
                    response = await litellm.acompletion(
                        model=self._get_model_name(self.config.model),
                        messages=messages,
                        temperature=self.config.temperature,
                        max_tokens=self.config.max_tokens,
                        **self._extra_kwargs(),
                    )
                    content = response.choices[0].message.content
                return _strip_code_fences(content)
            except Exception as e:
                if attempt < self.config.max_retries:
                    wait = self.config.retry_delay * attempt
                    logger.warning(
                        f"Native PDF attempt {attempt} failed: {e}. Retrying in {wait}s..."
                    )
                    await asyncio.sleep(wait)
                else:
                    raise

    # ------ Page-by-page image processing ------

    async def _process_page(
        self,
        page_img: Image.Image,
        page_num: int,
        semaphore: asyncio.Semaphore,
    ) -> tuple[int, str]:
        async with semaphore:
            # Offload CPU-bound image encoding to thread
            b64_image = await asyncio.to_thread(_image_to_base64, page_img)
            system_prompt = self.config.system_prompt or SYSTEM_PROMPT
            messages = _build_image_messages(
                b64_image, system_prompt, self.config.image_detail
            )

            for attempt in range(1, self.config.max_retries + 1):
                try:
                    if self._uses_openai_sdk(self.config.model):
                        content = await self._call_openai_sdk(messages)
                    else:
                        response = await litellm.acompletion(
                            model=self._get_model_name(self.config.model),
                            messages=messages,
                            temperature=self.config.temperature,
                            max_tokens=self.config.max_tokens,
                            **self._extra_kwargs(),
                        )
                        content = response.choices[0].message.content
                    content = _strip_code_fences(content)
                    logger.info(f"Page {page_num + 1} processed successfully")
                    return (page_num, content)
                except Exception as e:
                    if attempt < self.config.max_retries:
                        wait = self.config.retry_delay * attempt
                        logger.warning(
                            f"Page {page_num + 1} attempt {attempt} failed: {e}. "
                            f"Retrying in {wait}s..."
                        )
                        await asyncio.sleep(wait)
                    else:
                        logger.error(
                            f"Page {page_num + 1} failed after "
                            f"{self.config.max_retries} attempts: {e}"
                        )
                        return (
                            page_num,
                            f"<!-- OCR FAILED for page {page_num + 1}: {e} -->",
                        )

    async def _process_pages_as_images(self, file_path: str, ext: str) -> str:
        if ext in PDF_EXTENSIONS:
            total_pages = await asyncio.to_thread(_count_pdf_pages, file_path)
        else:
            total_pages = 1

        logger.info(
            f"Processing {total_pages} page(s) as images with model={self.config.model}"
        )

        semaphore = asyncio.Semaphore(self.config.max_concurrency)
        batch_size = int(os.environ.get("VLM_OCR_PAGE_BATCH_SIZE", "50"))

        if ext not in PDF_EXTENSIONS:
            pages = await asyncio.to_thread(_load_image_file, file_path)
            tasks = [self._process_page(pages[0], 0, semaphore)]
            results = await asyncio.gather(*tasks)
        else:
            results = []
            for batch_start in range(0, total_pages, batch_size):
                batch_end = min(batch_start + batch_size, total_pages)
                batch_pages = []
                for page_num in range(batch_start, batch_end):
                    img = await asyncio.to_thread(
                        _pdf_page_to_image, file_path, page_num, self.config.dpi
                    )
                    batch_pages.append((page_num, img))

                batch_tasks = [
                    self._process_page(img, page_num, semaphore)
                    for page_num, img in batch_pages
                ]
                batch_results = await asyncio.gather(*batch_tasks)
                results.extend(batch_results)

                del batch_pages, batch_tasks
                gc.collect()
                logger.info(
                    f"Batch complete: pages {batch_start + 1}-{batch_end}/{total_pages}"
                )

        results.sort(key=lambda x: x[0])

        md_parts = []
        for page_num, content in results:
            md_parts.append(f"<!-- Page {page_num + 1} -->\n")
            md_parts.append(content.strip())
            md_parts.append("\n\n---\n")

        return "\n".join(md_parts).rstrip("\n---\n").rstrip()

    # ------ Public API ------

    async def process_file_async(
        self,
        file_path: str,
        output_path: Optional[str] = None,
    ) -> str:
        """Process a file (PDF or image) and write structured Markdown output.

        Args:
            file_path: Path to the input PDF or image file.
            output_path: Optional output .md file path. Auto-generated if None.

        Returns:
            Path to the generated Markdown file.
        """
        file_path = os.path.abspath(file_path)
        ext = Path(file_path).suffix.lower()

        if ext not in SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file type '{ext}'. "
                f"Supported: {sorted(SUPPORTED_EXTENSIONS)}"
            )

        filename = Path(file_path).name
        logger.info(
            f"Processing: {filename} | model={self.config.model} "
            f"| provider={self.config.provider}"
        )
        start = time.time()

        # Routing: small PDFs -> native passthrough, everything else -> page-by-page
        use_native = False
        if ext in PDF_EXTENSIONS and self.config.supports_native_pdf:
            page_count = await asyncio.to_thread(_count_pdf_pages, file_path)
            if page_count <= self.config.native_pdf_max_pages:
                use_native = True
                logger.info(f"Using native PDF passthrough ({page_count} pages)")
            else:
                logger.info(
                    f"Using page-by-page image processing ({page_count} pages)"
                )

        if use_native:
            content = await self._process_pdf_native(file_path)
        else:
            content = await self._process_pages_as_images(file_path, ext)

        markdown = f"filename='{filename}'\n\n{content.strip()}"

        # Post-process: fix plain-text label:value pairs the model missed
        markdown = _fix_plain_label_value_pairs(markdown)

        # Write output (non-blocking)
        if not output_path:
            out_dir = self.config.output_dir or str(Path(file_path).parent)
            output_path = os.path.join(out_dir, f"{uuid.uuid4()}.md")

        await asyncio.to_thread(_write_file, output_path, markdown)

        elapsed = time.time() - start
        logger.info(f"Done in {elapsed:.1f}s -> {output_path}")
        return output_path

    def process_file(
        self,
        file_path: str,
        output_path: Optional[str] = None,
    ) -> str:
        """Synchronous wrapper around process_file_async."""
        return asyncio.run(self.process_file_async(file_path, output_path))
