from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx


@dataclass(frozen=True)
class VerifiedBackbone:
    key: str
    display_name: str
    filename: str
    urls: tuple[str, ...]
    allowed_domains: tuple[str, ...]
    description: str


VERIFIED_BACKBONES: dict[str, VerifiedBackbone] = {
    "human1": VerifiedBackbone(
        key="human1",
        display_name="Human1",
        filename="human1.xml",
        urls=(
            "https://raw.githubusercontent.com/SysBioChalmers/Human-GEM/main/model/Human-GEM.xml",
        ),
        allowed_domains=("raw.githubusercontent.com",),
        description="Consensus human genome-scale metabolic model from the verified Human-GEM repository.",
    ),
    "recon3d": VerifiedBackbone(
        key="recon3d",
        display_name="Recon3D",
        filename="Recon3D.zip",
        urls=(
            "https://www.vmh.life/files/reconstructions/Recon/3D/Recon3D.zip",
        ),
        allowed_domains=("vmh.life",),
        description="Recon3D human metabolic reconstruction distributed by VMH.",
    ),
}

BACKBONE_ALIASES = {
    "human1": "human1",
    "human-gem": "human1",
    "human_gem": "human1",
    "human gem": "human1",
    "recon3d": "recon3d",
    "recon-3d": "recon3d",
    "recon_3d": "recon3d",
    "recon": "recon3d",
}


def _models_root() -> Path:
    root = Path(os.getenv("CRYO_DATA_DIR", "/cryo-data")) / "models"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _registry_path() -> Path:
    return _models_root() / "registry.json"


def _load_registry() -> dict:
    path = _registry_path()
    if not path.exists():
        return {"models": {}}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {"models": {}}


def _save_registry(registry: dict) -> None:
    _registry_path().write_text(json.dumps(registry, indent=2, sort_keys=True))


def _sha256(filepath: Path) -> str:
    digest = hashlib.sha256()
    with filepath.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_allowed_url(url: str, allowed_domains: tuple[str, ...]) -> bool:
    hostname = (urlparse(url).hostname or "").lower()
    return any(hostname == domain or hostname.endswith(f".{domain}") for domain in allowed_domains)


def normalize_backbone_name(name: str | None) -> str:
    if not name:
        return ""
    lowered = name.strip().lower()
    return BACKBONE_ALIASES.get(lowered, lowered)


def infer_backbone_from_query(query: str | None) -> str:
    if not query:
        return ""
    lowered = query.lower()
    for alias, canonical in BACKBONE_ALIASES.items():
        if alias in lowered:
            return canonical
    return ""


def get_cached_backbone_path(backbone_name: str) -> str:
    canonical = normalize_backbone_name(backbone_name)
    if canonical not in VERIFIED_BACKBONES:
        return ""

    registry = _load_registry()
    cached = registry.get("models", {}).get(canonical, {})
    cached_path = cached.get("cached_path", "")
    if cached_path and Path(cached_path).exists():
        return cached_path
    return ""


def resolve_verified_backbone(
    *,
    backbone_name: str | None = None,
    model_path: str | None = None,
    auto_fetch: bool = True,
) -> dict:
    """Resolve a local model path from either an explicit file path or a named verified backbone."""
    configured_model_path = (model_path or "").strip()
    configured_backbone = normalize_backbone_name(backbone_name)
    metadata = {
        "configured_model_path": configured_model_path,
        "configured_backbone": configured_backbone,
        "source": "unresolved",
        "loaded_model_path": "",
        "remote_url": "",
        "checksum_sha256": "",
        "retrieved_at": "",
        "cache_hit": False,
        "auto_fetch_attempted": False,
    }

    if configured_model_path:
        path = Path(configured_model_path)
        if path.exists():
            metadata["source"] = "local_path"
            metadata["loaded_model_path"] = str(path)
            metadata["checksum_sha256"] = _sha256(path)
        return metadata

    if configured_backbone not in VERIFIED_BACKBONES:
        return metadata

    cached_path = get_cached_backbone_path(configured_backbone)
    if cached_path:
        metadata["source"] = "verified_cache"
        metadata["loaded_model_path"] = cached_path
        metadata["checksum_sha256"] = _sha256(Path(cached_path))
        metadata["cache_hit"] = True
        registry = _load_registry()
        cached = registry.get("models", {}).get(configured_backbone, {})
        metadata["remote_url"] = cached.get("remote_url", "")
        metadata["retrieved_at"] = cached.get("retrieved_at", "")
        return metadata

    if not auto_fetch:
        return metadata

    metadata["auto_fetch_attempted"] = True
    backbone = VERIFIED_BACKBONES[configured_backbone]
    download_dir = _models_root() / configured_backbone
    download_dir.mkdir(parents=True, exist_ok=True)
    destination = download_dir / backbone.filename

    with httpx.Client(follow_redirects=True, timeout=60) as client:
        for url in backbone.urls:
            if not _is_allowed_url(url, backbone.allowed_domains):
                continue
            response = client.get(url)
            response.raise_for_status()

            final_url = str(response.url)
            if not _is_allowed_url(final_url, backbone.allowed_domains):
                raise ValueError(f"Resolved URL is outside allowlist: {final_url}")

            destination.write_bytes(response.content)
            checksum = _sha256(destination)
            retrieved_at = datetime.now(timezone.utc).isoformat()

            registry = _load_registry()
            registry.setdefault("models", {})[configured_backbone] = {
                "display_name": backbone.display_name,
                "cached_path": str(destination),
                "remote_url": final_url,
                "checksum_sha256": checksum,
                "retrieved_at": retrieved_at,
                "description": backbone.description,
            }
            _save_registry(registry)

            metadata["source"] = "verified_download"
            metadata["loaded_model_path"] = str(destination)
            metadata["remote_url"] = final_url
            metadata["checksum_sha256"] = checksum
            metadata["retrieved_at"] = retrieved_at
            return metadata

    return metadata
