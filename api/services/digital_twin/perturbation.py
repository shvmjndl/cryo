from __future__ import annotations

import cobra


def _has_reaction(model: cobra.Model, reaction_id: str) -> bool:
    return any(reaction.id == reaction_id for reaction in model.reactions)


def apply_drug_perturbation(model: cobra.Model, drug_id: str) -> tuple[cobra.Model, dict[str, str]]:
    """Apply reaction-level perturbations for drug simulations."""
    perturbed = model.copy()
    effects: dict[str, str] = {}
    normalized = drug_id.lower()

    if "glucose_inhibitor" in normalized:
        # Block glucose exchange uptake: reduce to 10% of current capacity
        if _has_reaction(perturbed, "MAR09034"):
            rxn = perturbed.reactions.get_by_id("MAR09034")
            original_lb = rxn.lower_bound
            rxn.lower_bound = original_lb * 0.1  # 90% inhibition
            effects["MAR09034"] = f"glucose exchange: {original_lb:.2f} → {rxn.lower_bound:.2f} (90% inhibition)"

        # Block glucose transporter
        if _has_reaction(perturbed, "MAR01378"):
            rxn = perturbed.reactions.get_by_id("MAR01378")
            original_lb = rxn.lower_bound
            original_ub = rxn.upper_bound
            rxn.lower_bound = original_lb * 0.1
            rxn.upper_bound = original_ub * 0.1
            effects["MAR01378"] = f"glucose transporter: scaled to 10% capacity"

        # Fallback for demo model
        if not effects and _has_reaction(perturbed, "R_GLC_uptake"):
            rxn = perturbed.reactions.R_GLC_uptake
            original_ub = rxn.upper_bound
            rxn.upper_bound = original_ub * 0.1
            effects["R_GLC_uptake"] = f"glucose uptake: {original_ub:.2f} → {rxn.upper_bound:.2f} (90% inhibition)"

    elif "atp_synthase_inhibitor" in normalized:
        if _has_reaction(perturbed, "MAR04137"):  # Human1 ATP synthase
            rxn = perturbed.reactions.get_by_id("MAR04137")
            original_ub = rxn.upper_bound
            rxn.upper_bound = original_ub * 0.1
            effects["MAR04137"] = f"ATP synthase: {original_ub:.2f} → {rxn.upper_bound:.2f} (90% inhibition)"

        if not effects and _has_reaction(perturbed, "R_ATP_synthase"):
            rxn = perturbed.reactions.R_ATP_synthase
            original_ub = rxn.upper_bound
            rxn.upper_bound = original_ub * 0.2
            effects["R_ATP_synthase"] = f"ATP synthase: inhibited (80%)"

    return perturbed, effects
