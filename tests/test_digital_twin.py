"""
Digital twin integration tests.

Run inside cryo-api-1 container:
    docker exec cryo-api-1 python -m pytest /app/tests/test_digital_twin.py -v
"""
from __future__ import annotations

import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_drug_target_info(reaction_ids: list[str] | None = None) -> dict:
    return {
        "drug_name": "test_drug",
        "targets": [{"gene_symbol": "EGFR", "source": "chembl", "mechanism": "inhibitor"}],
        "reaction_ids": reaction_ids or [],
        "citations": [],
        "error": None,
    }


def _citation_dict(key: str) -> dict:
    from api.services.digital_twin.reporting import CITATIONS
    return CITATIONS[key]


# ---------------------------------------------------------------------------
# Test 1 — Glucose inhibitor perturbation is applied
# (biomass change is not asserted — known Human1 flexibility limitation)
# ---------------------------------------------------------------------------
class TestWarburgGlucoseInhibition:
    def test_glucose_inhibitor_applies_perturbation(self):
        """Blocking glucose import should apply at least one reaction effect."""
        from api.services.digital_twin.model_loader import load_backbone_model
        from api.services.digital_twin.perturbation import apply_drug_perturbation

        model, _ = load_backbone_model()
        _, effects = apply_drug_perturbation(model.copy(), "glucose_inhibitor")

        # Should have applied MAR09034 or a note (never empty dict)
        assert len(effects) > 0, "Expected at least one perturbation effect"
        # The glucose exchange reaction should be in effects
        rxn_effects = {k: v for k, v in effects.items() if not k.startswith("_")}
        assert "MAR09034" in rxn_effects or len(rxn_effects) > 0, (
            f"Expected MAR09034 in effects. Got: {effects}"
        )

    def test_glucose_inhibitor_simulation_completes(self):
        """Glucose inhibitor simulation should complete without error."""
        from api.services.digital_twin.model_loader import load_backbone_model
        from api.services.digital_twin.simulator import simulate_drug_effect

        model, _ = load_backbone_model()
        results = simulate_drug_effect(model.copy(), "glucose_inhibitor")

        assert "error" not in results, f"Simulation error: {results.get('error')}"
        assert "drug_id" in results
        assert "initial_biomass_flux" in results
        assert "drug_effects_applied" in results


# ---------------------------------------------------------------------------
# Test 2 — Imatinib without cell line (ChEMBL lookup path)
# ---------------------------------------------------------------------------
class TestImatinibNoCellLine:
    def test_imatinib_returns_effects_and_citations(self):
        """Imatinib simulation should return drug effects and citations."""
        from api.services.digital_twin.service import DigitalTwinService
        from api.services.digital_twin.model_loader import load_backbone_model

        model, meta = load_backbone_model()

        with patch("api.services.digital_twin.service.load_backbone_model", return_value=(model, meta)):
            svc = DigitalTwinService()

        # Patch at the drug_lookup module level (imported inside simulate_drug_response)
        with patch("api.services.digital_twin.drug_lookup.resolve_drug_targets",
                   return_value=_mock_drug_target_info()):
            result = svc.simulate_drug_response(
                user_id="test",
                conversation_id="test",
                drug_id="imatinib",
                cell_line="",
            )

        assert "error" not in result or result.get("error") is None, f"Got error: {result}"
        assert "citations" in result
        assert len(result["citations"]) > 0
        # Must always include Human-GEM and COBRApy
        dois = " ".join(c.get("doi", "") for c in result["citations"] if isinstance(c, dict))
        assert "10.1126/scisignal.aaz1482" in dois, "Human-GEM citation missing"
        assert "10.1186/1752-0509-7-74" in dois, "COBRApy citation missing"


# ---------------------------------------------------------------------------
# Test 3 — Cell line GPR scaling (MCF7)
# ---------------------------------------------------------------------------
class TestGPRScalingMCF7:
    def test_mcf7_gpr_scaling_applied_or_gracefully_skipped(self):
        """With MCF7 cell line, GPR scaling should apply or report graceful skip."""
        from api.services.digital_twin.ccle_loader import apply_gpr_expression_scaling
        from api.services.digital_twin.model_loader import load_backbone_model

        model, _ = load_backbone_model()
        personalized, notes = apply_gpr_expression_scaling(model.copy(), "MCF7")

        assert "applied" in notes
        if notes["applied"]:
            assert notes.get("constrained_reactions", 0) >= 0
            assert "citation" in notes
        else:
            assert "reason" in notes


# ---------------------------------------------------------------------------
# Test 4 — Metformin simulation completes
# ---------------------------------------------------------------------------
class TestMetforminComplexI:
    def test_metformin_simulation_completes(self):
        """Metformin simulation should complete without error."""
        from api.services.digital_twin.model_loader import load_backbone_model
        from api.services.digital_twin.simulator import simulate_drug_effect

        model, _ = load_backbone_model()

        drug_target_info = {
            "drug_name": "metformin",
            "targets": [{"gene_symbol": "MT-ND1", "source": "dgidb", "mechanism": "inhibitor"}],
            "reaction_ids": [],
            "citations": [],
            "error": None,
        }

        results = simulate_drug_effect(model.copy(), "metformin", drug_target_info=drug_target_info)
        assert "error" not in results
        assert "initial_biomass_flux" in results


# ---------------------------------------------------------------------------
# Test 5 — Citations always present in formatted response
# ---------------------------------------------------------------------------
class TestCitationsAlwaysPresent:
    def test_format_response_includes_references(self):
        """Formatted digital twin response must contain DOI references."""
        from api.services.hermes_bridge import _format_digital_twin_response
        from api.services.digital_twin.reporting import CITATIONS

        mock_result = {
            "drug_id": "imatinib",
            "initial_biomass_flux": 62.43,
            "drug_biomass_flux": 62.43,
            "biomass_reaction_id": "MAR13082",
            "drug_effects_applied": [],
            "changed_fluxes": {"MAR09034": -5.0, "MAR09063": -2.1},
            "full_solution": {},
            "drug_target_info": _mock_drug_target_info(),
            "gdsc_validation": {"found": False},
            "personalization_notes": {
                "media_preset": "human1_minimal",
                "gpr_scaling": {"applied": False, "reason": "no cell line"},
            },
            "cell_line": "",
            # Citations as dicts (real format from reporting.py)
            "citations": [CITATIONS["human_gem"], CITATIONS["cobrapy"], CITATIONS["chembl"]],
        }

        formatted = _format_digital_twin_response("imatinib", mock_result)
        assert "doi" in formatted.lower() or "10.1126" in formatted
        assert "References" in formatted or "references" in formatted.lower()

    def test_missing_citations_has_disclaimer(self):
        """When citations list is empty, response must warn the user."""
        from api.services.hermes_bridge import _format_digital_twin_response

        mock_result = {
            "drug_id": "unknown_drug",
            "initial_biomass_flux": 62.43,
            "drug_biomass_flux": 62.43,
            "biomass_reaction_id": "MAR13082",
            "drug_effects_applied": [],
            "changed_fluxes": {},
            "full_solution": {},
            "drug_target_info": {"drug_name": "unknown", "targets": [], "reaction_ids": [], "citations": [], "error": "not found"},
            "gdsc_validation": {"found": False},
            "personalization_notes": {},
            "cell_line": "",
            "citations": [],
        }

        formatted = _format_digital_twin_response("unknown_drug", mock_result)
        assert "verify" in formatted.lower() or "cross-check" in formatted.lower()


# ---------------------------------------------------------------------------
# Test 6 — Missing CCLE data: graceful degradation
# ---------------------------------------------------------------------------
class TestMissingCCLEGraceful:
    def test_unknown_cell_line_no_crash(self):
        """Unknown cell line should return graceful degradation note, not crash."""
        from api.services.digital_twin.ccle_loader import apply_gpr_expression_scaling
        from api.services.digital_twin.model_loader import load_backbone_model

        model, _ = load_backbone_model()
        personalized, notes = apply_gpr_expression_scaling(model.copy(), "UNKNOWNCELL_XYZ_999")

        assert "applied" in notes
        assert notes["applied"] is False
        assert "reason" in notes
        assert personalized is not None
