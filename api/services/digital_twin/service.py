from __future__ import annotations

import logging
import os
import threading
from typing import Any

import cobra

from api.services.digital_twin.model_loader import load_backbone_model
from api.services.digital_twin.model_registry import (
    infer_backbone_from_query,
    normalize_backbone_name,
    VERIFIED_BACKBONES,
)
from api.services.digital_twin.omics_parser import load_omics_payload
from api.services.digital_twin.organism import detect_organism, organism_display
from api.services.digital_twin.personalizer import personalize_model
from api.services.digital_twin.reporting import generate_digital_twin_report
from api.services.digital_twin.simulator import simulate_drug_effect

logger = logging.getLogger("cryo.digital_twin_service")


class DigitalTwinService:
    """
    Orchestrator for digital twin model loading, personalization, simulation, and reporting.

    Maintains an in-memory model pool keyed by backbone name so that frequently used
    models (human1, ijo1366) are not reloaded on every request.
    Thread-safe — pool access is guarded by a reentrant lock.
    """

    def __init__(self) -> None:
        self._pool: dict[str, tuple[cobra.Model, dict]] = {}
        self._lock = threading.RLock()
        # Load default model on startup
        default_model, default_meta = load_backbone_model()
        backbone_key = (
            default_meta.get("configured_backbone")
            or normalize_backbone_name(os.getenv("CRYO_DIGITAL_TWIN_BACKBONE", ""))
            or "human1"
        )
        with self._lock:
            self._pool[backbone_key] = (default_model, default_meta)
        # Backward-compat aliases
        self.model = default_model
        self.model_metadata = default_meta
        self.reports_dir = "digital_twin"

    def get_model_for_backbone(self, backbone: str) -> tuple[cobra.Model, dict]:
        """Return (model, metadata) for the requested backbone, loading and caching if needed."""
        canonical = normalize_backbone_name(backbone) if backbone else ""

        if not canonical:
            return self.model, self.model_metadata

        with self._lock:
            if canonical in self._pool:
                return self._pool[canonical]

        logger.info("Loading backbone '%s' — not in pool", canonical)
        model, meta = load_backbone_model(backbone_name=canonical)
        with self._lock:
            self._pool[canonical] = (model, meta)
            # Also update primary aliases for backward compat
            if canonical == list(self._pool.keys())[0]:
                self.model = model
                self.model_metadata = meta
        return model, meta

    def available_backbones(self) -> list[dict]:
        """List all VERIFIED_BACKBONES with loaded status."""
        with self._lock:
            loaded_keys = set(self._pool.keys())
        return [
            {
                "key": bb.key,
                "display_name": bb.display_name,
                "description": bb.description,
                "loaded": bb.key in loaded_keys,
            }
            for bb in VERIFIED_BACKBONES.values()
        ]

    def reload_model(self) -> dict[str, Any]:
        self.model, self.model_metadata = load_backbone_model()
        return self.model_metadata

    def reload_model_for_query(self, query: str) -> dict[str, Any]:
        inferred_backbone = infer_backbone_from_query(query)
        if inferred_backbone:
            os.environ["CRYO_DIGITAL_TWIN_BACKBONE"] = inferred_backbone
        return self.reload_model()

    def load_omics_payload(self, patient_omics_profile_path: str | None) -> dict[str, Any]:
        return load_omics_payload(patient_omics_profile_path)

    def personalize_model(
        self,
        model,
        omics_data: dict[str, Any] | None,
        simulation_context: dict[str, Any] | None = None,
    ):
        return personalize_model(model, omics_data, simulation_context)

    def simulate_drug_effect(
        self,
        model,
        drug_id: str,
        drug_target_info: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return simulate_drug_effect(model, drug_id, drug_target_info=drug_target_info)

    def generate_report(
        self,
        simulation_results: dict[str, Any],
        user_id: str,
        conversation_id: str,
        personalization_notes: dict[str, Any] | None = None,
        gdsc_validation: dict[str, Any] | None = None,
        drug_target_info: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        return generate_digital_twin_report(
            simulation_results,
            user_id,
            conversation_id,
            personalization_notes=personalization_notes,
            model_metadata=self.model_metadata,
            gdsc_validation=gdsc_validation,
            drug_target_info=drug_target_info,
        )

    def simulate_drug_response(
        self,
        *,
        user_id: str,
        conversation_id: str,
        drug_id: str,
        cell_line: str = "",
        backbone: str = "",
        patient_omics_profile_path: str | None = None,
    ) -> dict[str, Any]:
        from api.services.digital_twin.drug_lookup import resolve_drug_targets
        from api.services.digital_twin.gdsc_validator import lookup_gdsc
        from api.services.digital_twin.pathogen_targets import lookup_pathogen_targets

        # Select model — default to pool's primary model
        model, model_meta = self.get_model_for_backbone(backbone)
        organism = detect_organism(model)
        logger.info("simulate_drug_response: drug=%s cell_line=%s backbone=%s organism=%s",
                    drug_id, cell_line, backbone or "default", organism)

        # Drug target resolution:
        # - Human models: ChEMBL → DGIdb → SQLite cache
        # - Pathogen models: curated pathogen DB first, then ChEMBL fallback
        if organism in ("ecoli", "yeast"):
            drug_target_info = lookup_pathogen_targets(organism, drug_id) or {}
            if not drug_target_info:
                drug_target_info = resolve_drug_targets(model, drug_id)
        else:
            drug_target_info = resolve_drug_targets(model, drug_id)

        omics_data = self.load_omics_payload(patient_omics_profile_path)
        personalized_model, personalization_notes = self.personalize_model(
            model.copy(),
            omics_data,
            {
                "drug_id": drug_id,
                "cell_line": cell_line,
                "configured_backbone": model_meta.get("configured_backbone", backbone),
            },
        )

        simulation_results = self.simulate_drug_effect(
            personalized_model,
            drug_id,
            drug_target_info=drug_target_info,
        )
        if "error" in simulation_results:
            return simulation_results

        # GDSC2 validation is only meaningful for human cancer cell lines
        gdsc_validation: dict = {}
        if cell_line and organism == "human":
            gdsc_validation = lookup_gdsc(drug_id, cell_line)

        report_output = self.generate_report(
            simulation_results,
            user_id,
            conversation_id,
            personalization_notes=personalization_notes,
            gdsc_validation=gdsc_validation,
            drug_target_info=drug_target_info,
        )

        return {
            **simulation_results,
            "personalization_notes": personalization_notes,
            "drug_target_info": drug_target_info,
            "gdsc_validation": gdsc_validation,
            "cell_line": cell_line,
            "backbone": backbone or model_meta.get("configured_backbone", ""),
            "organism": organism,
            "organism_display": organism_display(organism),
            "report_path": report_output.get("report_path", ""),
            "plot_path": report_output.get("plot_path", ""),
            "summary": report_output.get("summary", ""),
            "citations": report_output.get("citations", []),
        }


digital_twin_service = DigitalTwinService()
