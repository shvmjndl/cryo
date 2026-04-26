from __future__ import annotations

from typing import Any

import cobra

from api.services.digital_twin.perturbation import apply_drug_perturbation


def _extract_fluxes(model: cobra.Model, solution: Any) -> dict[str, float]:
    return {
        reaction.id: float(solution.fluxes.get(reaction.id, 0.0))
        for reaction in model.reactions
    }


def _objective_reaction_id(model: cobra.Model) -> str:
    expression = str(model.objective.expression)
    for reaction in model.reactions:
        if reaction.id in expression:
            return reaction.id
    return ""


def _biomass_flux(model: cobra.Model, solution: Any, fluxes: dict[str, float]) -> tuple[float, str]:
    objective_reaction_id = _objective_reaction_id(model)
    if objective_reaction_id:
        return float(fluxes.get(objective_reaction_id, 0.0)), objective_reaction_id
    return float(getattr(solution, "objective_value", 0.0) or 0.0), ""


def simulate_drug_effect(
    model: cobra.Model,
    drug_id: str,
    drug_target_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run a baseline solve, apply a perturbation, and compare flux shifts."""
    try:
        baseline_solution = model.optimize()
        baseline_fluxes = _extract_fluxes(model, baseline_solution)
    except Exception as exc:
        return {"error": f"Initial model optimization failed: {exc}"}

    perturbed_model, drug_effects = apply_drug_perturbation(model, drug_id, drug_target_info=drug_target_info)

    try:
        perturbed_solution = perturbed_model.optimize()
    except Exception as exc:
        return {"error": f"Drug simulation failed for {drug_id}: {exc}"}

    perturbed_fluxes = _extract_fluxes(perturbed_model, perturbed_solution)
    initial_biomass_flux, biomass_reaction_id = _biomass_flux(model, baseline_solution, baseline_fluxes)
    drug_biomass_flux, _ = _biomass_flux(perturbed_model, perturbed_solution, perturbed_fluxes)
    changed_fluxes = {
        reaction_id: perturbed_fluxes[reaction_id] - baseline_fluxes.get(reaction_id, 0.0)
        for reaction_id in perturbed_fluxes
        if abs(perturbed_fluxes[reaction_id] - baseline_fluxes.get(reaction_id, 0.0)) > 1e-6
    }

    return {
        "drug_id": drug_id,
        "initial_biomass_flux": initial_biomass_flux,
        "drug_biomass_flux": drug_biomass_flux,
        "biomass_reaction_id": biomass_reaction_id,
        "drug_effects_applied": drug_effects,
        "changed_fluxes": changed_fluxes,
        "full_solution": perturbed_fluxes,
    }
