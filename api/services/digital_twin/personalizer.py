from __future__ import annotations

from typing import Any

import cobra

from api.services.digital_twin.media_registry import apply_media_preset, select_media_preset


def personalize_model(
    model: cobra.Model,
    omics_data: dict[str, Any] | None,
    simulation_context: dict[str, Any] | None = None,
) -> tuple[cobra.Model, dict[str, Any]]:
    """Apply context presets and preserve omics metadata for future personalization."""
    personalized = model.copy()
    notes: dict[str, Any] = {
        "personalization_applied": False,
        "omics_summary": {},
        "environment_context": {},
    }

    if omics_data:
        notes["omics_summary"] = {
            "format": omics_data.get("format", "unknown"),
            "path": omics_data.get("path", ""),
            "row_count": omics_data.get("row_count", 0),
            "columns": omics_data.get("columns", []),
            "error": omics_data.get("error", ""),
        }

    preset_name = select_media_preset(personalized, simulation_context)
    if preset_name:
        notes["personalization_applied"] = True
        notes["environment_context"] = apply_media_preset(personalized, preset_name)

    return personalized, notes
