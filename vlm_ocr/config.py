import os
from dataclasses import dataclass, field
from typing import Dict, Optional

from dotenv import load_dotenv

load_dotenv()

PROVIDER_MODELS = {
    "openai": "gpt-4o",
    "gemini": "gemini/gemini-2.0-flash",
    "claude": "anthropic/claude-sonnet-4-20250514",
}


@dataclass
class OCRConfig:
    """Configuration for the VLM OCR pipeline."""

    model: str = "gemini/gemini-2.0-flash"
    dpi: int = 200
    max_concurrency: int = 5
    temperature: float = 0.0
    max_tokens: int = 16384
    output_dir: Optional[str] = None
    image_detail: str = "high"
    system_prompt: Optional[str] = None
    max_retries: int = 3
    retry_delay: float = 1.0

    # Batch size for page-by-page PDF processing (limits peak memory usage).
    # 50 pages × ~12MB/page ≈ 600MB — safe within a 4GB container.
    page_batch_size: int = 50

    # Native PDF passthrough is used only for small PDFs (<=native_pdf_max_pages).
    # Larger PDFs are processed page-by-page as images for guaranteed accuracy.
    native_pdf: bool = False
    native_pdf_max_pages: int = 0

    # Logical → actual model name mapping. Mirrors kgwizard.providers.llm's
    # OpenAIAdapter.model_mapping. Env var OPENAI_MODEL_MAPPING (JSON) overrides
    # this at pipeline init. Exact-string match: the key is whatever the caller
    # passes as `model` (prefixed like "gemini/gemini-2.0-flash" or bare like
    # "gpt-4o"), the value is what actually gets sent to litellm.acompletion.
    model_name_mapping: Dict[str, str] = field(default_factory=dict)

    @property
    def provider(self) -> str:
        m = self.model.lower()
        if m.startswith("gemini/") or m.startswith("google/"):
            return "gemini"
        if m.startswith("anthropic/") or "claude" in m:
            return "claude"
        return "openai"

    @property
    def supports_native_pdf(self) -> bool:
        # OpenAI gpt-4o+ supports PDF input via Chat Completions' `file` content
        # type, same as Gemini. See frameworks/vlm_ocr/ocr_pipeline.py for the
        # provider-specific message builders.
        return self.native_pdf and self.provider in ("openai", "gemini", "claude")

    @classmethod
    def for_provider(cls, provider: str, **overrides) -> "OCRConfig":
        model = PROVIDER_MODELS.get(provider)
        if not model:
            raise ValueError(
                f"Unknown provider '{provider}'. "
                f"Choose from: {list(PROVIDER_MODELS.keys())}"
            )
        return cls(model=model, **overrides)
