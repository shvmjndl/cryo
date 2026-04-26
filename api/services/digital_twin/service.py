from __future__ import annotations

import os
from typing import Any

from api.services.digital_twin.model_loader import load_backbone_model
from api.services.digital_twin.model_registry import infer_backbone_from_query
from api.services.digital_twin.omics_parser import load_omics_payload
from api.services.digital_twin.personalizer import personalize_model
from api.services.digital_twin.reporting import generate_digital_twin_report
from api.services.digital_twin.simulator import simulate_drug_effect


class DigitalTwinService:
    """Orchestrator for digital twin model loading, personalization, simulation, and reporting."""

    def __init__(self) -> None:
        self.model, self.model_metadata = load_backbone_model()
        self.reports_dir = "digital_twin"

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
        patient_omics_profile_path: str | None = None,
    ) -> dict[str, Any]:
        from api.services.digital_twin.drug_lookup import resolve_drug_targets
        from api.services.digital_twin.gdsc_validator import lookup_gdsc

        # Resolve drug targets (ChEMBL → DGIdb → cache)
        drug_target_info = resolve_drug_targets(self.model, drug_id)

        omics_data = self.load_omics_payload(patient_omics_profile_path)
        personalized_model, personalization_notes = self.personalize_model(
            self.model.copy(),
            omics_data,
            {
                "drug_id": drug_id,
                "cell_line": cell_line,
                "configured_backbone": self.model_metadata.get("configured_backbone", ""),
            },
        )

        simulation_results = self.simulate_drug_effect(
            personalized_model,
            drug_id,
            drug_target_info=drug_target_info,
        )
        if "error" in simulation_results:
            return simulation_results

        # Experimental validation from GDSC2
        gdsc_validation = lookup_gdsc(drug_id, cell_line) if cell_line else {}

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
            "report_path": report_output.get("report_path", ""),
            "plot_path": report_output.get("plot_path", ""),
            "summary": report_output.get("summary", ""),
            "citations": report_output.get("citations", []),
        }


digital_twin_service = DigitalTwinService()
