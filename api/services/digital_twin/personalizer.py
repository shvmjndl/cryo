from __future__ import annotations

from typing import Any

import cobra

from api.services.digital_twin.ccle_loader import apply_gpr_expression_scaling
from api.services.digital_twin.media_registry import apply_media_preset, select_media_preset


def personalize_model(
    model: cobra.Model,
    omics_data: dict[str, Any] | None,
    simulation_context: dict[str, Any] | None = None,
) -> tuple[cobra.Model, dict[str, Any]]:
    """
    Apply media preset and optional CCLE GPR expression scaling.

    Personalization pipeline:
    1. Select media preset based on context (drug type, cell line, explicit override)
    2. Apply media preset to restrict/open exchange reactions
    3. If cell_line provided: apply GPR-based expression scaling via CCLE data
       (constrains reactions where all associated genes have TPM < threshold)

    Always operates on a copy — singleton model is never mutated.
    """
    personalized = model.copy()
    simulation_context = simulation_context or {}
    notes: dict[str, Any] = {
        "personalization_applied": False,
        "omics_summary": {},
        "environment_context": {},
        "gpr_scaling": {"applied": False},
    }

    # Legacy omics file path metadata (not yet applied to bounds)
    if omics_data:
        notes["omics_summary"] = {
            "format": omics_data.get("format", "unknown"),
            "path": omics_data.get("path", ""),
            "row_count": omics_data.get("row_count", 0),
            "columns": omics_data.get("columns", []),
            "error": omics_data.get("error", ""),
        }

    # Step 3: GPR expression scaling (CCLE-based) — must run BEFORE media preset
    # so we know whether CCLE data is available for this cell line.
    # This affects media preset selection (CCLE available → minimal media, not Warburg).
    cell_line = simulation_context.get("cell_line", "").strip()
    ccle_available = False
    if cell_line:
        personalized, gpr_notes = apply_gpr_expression_scaling(personalized, cell_line)
        notes["gpr_scaling"] = gpr_notes
        ccle_available = bool(gpr_notes.get("applied"))
        if ccle_available:
            notes["personalization_applied"] = True

    # Step 1 + 2: Media preset (after GPR so ccle_available is known)
    ctx_with_ccle = {**simulation_context, "ccle_available": ccle_available}
    preset_name = select_media_preset(personalized, ctx_with_ccle)
    if preset_name:
        notes["personalization_applied"] = True
        notes["environment_context"] = apply_media_preset(personalized, preset_name)
    notes["media_preset"] = preset_name

    return personalized, notes
