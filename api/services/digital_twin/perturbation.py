"""
Apply reaction-level drug perturbations to the metabolic model.

Priority:
1. Use drug_target_info (from ChEMBL/DGIdb lookup) if available — real drug-gene-reaction mapping
2. Fall back to hardcoded patterns for legacy drug IDs (glucose_inhibitor, atp_synthase_inhibitor)
"""
from __future__ import annotations

import logging
from typing import Any

import cobra

from api.services.digital_twin.organism import detect_organism
from api.services.digital_twin.pathogen_targets import lookup_pathogen_targets

logger = logging.getLogger("cryo.perturbation")

_INHIBITION_FRACTION = 0.10  # 90% inhibition → target at 10% capacity


def _has_reaction(model: cobra.Model, reaction_id: str) -> bool:
    return model.reactions.has_id(reaction_id)


def _inhibit_reaction(model: cobra.Model, reaction_id: str, effects: dict[str, str]) -> bool:
    """Apply 90% inhibition to a single reaction. Returns True if applied."""
    if not _has_reaction(model, reaction_id):
        return False
    rxn = model.reactions.get_by_id(reaction_id)

    applied = False
    # Exchange reactions: restrict import (lower_bound is negative for imports)
    if rxn.lower_bound < 0:
        original_lb = rxn.lower_bound
        rxn.lower_bound = original_lb * _INHIBITION_FRACTION
        effects[reaction_id] = f"{rxn.name or reaction_id}: {original_lb:.3f} → {rxn.lower_bound:.3f} (90% inhibition)"
        applied = True

    # Forward reactions: restrict upper_bound
    if rxn.upper_bound > 0:
        original_ub = rxn.upper_bound
        rxn.upper_bound = original_ub * _INHIBITION_FRACTION
        if reaction_id not in effects:
            effects[reaction_id] = f"{rxn.name or reaction_id}: ub {original_ub:.3f} → {rxn.upper_bound:.3f} (90% inhibition)"
        applied = True

    return applied


def apply_drug_perturbation(
    model: cobra.Model,
    drug_id: str,
    drug_target_info: dict[str, Any] | None = None,
) -> tuple[cobra.Model, dict[str, str]]:
    """
    Apply reaction-level perturbations for drug simulations.

    Args:
        model: Personalized model (already a copy — will be copied again internally).
        drug_id: Drug identifier (name or legacy keyword).
        drug_target_info: Pre-resolved drug target info from drug_lookup.resolve_drug_targets().
                          If provided and has reaction_ids, these are used instead of hardcoded patterns.

    Returns:
        (perturbed_model, effects_dict)
    """
    perturbed = model.copy()
    effects: dict[str, str] = {}
    normalized = drug_id.lower()

    # ── Path 1: Real drug-target mapping (ChEMBL / DGIdb) ──────────────────────
    if drug_target_info and drug_target_info.get("reaction_ids"):
        reaction_ids = drug_target_info["reaction_ids"]
        targets = drug_target_info.get("targets", [])
        target_genes = [t["gene_symbol"] for t in targets]
        mechanism = targets[0]["mechanism"] if targets else ""

        logger.info("Applying drug perturbation via gene-target lookup: %s → genes=%s reactions=%d",
                    drug_id, target_genes[:3], len(reaction_ids))

        applied_count = 0
        for rxn_id in reaction_ids:
            if _inhibit_reaction(perturbed, rxn_id, effects):
                applied_count += 1

        if applied_count > 0:
            # Annotate effects with gene target context
            gene_str = ", ".join(target_genes[:3])
            if len(target_genes) > 3:
                gene_str += f" +{len(target_genes)-3} more"
            mech_note = f" [{mechanism}]" if mechanism else ""
            effects["_summary"] = (
                f"{drug_id}: targets {gene_str}{mech_note}. "
                f"{applied_count} reactions inhibited (90%)."
            )
            return perturbed, effects

        logger.info("No Human1 reactions found for drug targets of %s — falling back to hardcoded patterns", drug_id)

    # ── Path 1b: Pathogen-specific curated targets (ecoli / yeast) ───────────
    organism = detect_organism(perturbed)
    if organism in ("ecoli", "yeast"):
        pathogen_info = lookup_pathogen_targets(organism, drug_id)
        if pathogen_info and pathogen_info.get("reaction_ids"):
            logger.info("Using pathogen target DB for %s (%s): reactions=%s",
                        drug_id, organism, pathogen_info["reaction_ids"])
            applied_count = 0
            for rxn_id in pathogen_info["reaction_ids"]:
                if _inhibit_reaction(perturbed, rxn_id, effects):
                    applied_count += 1
            if applied_count > 0:
                gene_str = pathogen_info["targets"][0]["gene_symbol"] if pathogen_info.get("targets") else "?"
                mech = pathogen_info["targets"][0].get("mechanism", "") if pathogen_info.get("targets") else ""
                effects["_summary"] = (
                    f"{drug_id}: target gene={gene_str}. "
                    f"{mech}. "
                    f"{applied_count} reactions inhibited (90%) — pathogen target DB."
                )
                return perturbed, effects
            else:
                note = pathogen_info.get("note", "")
                effects["_note"] = (
                    f"{drug_id} targets {pathogen_info['targets'][0]['gene_symbol'] if pathogen_info.get('targets') else '?'} "
                    f"but its reactions are not in this model. {note}"
                )
                logger.info("Pathogen target found but no model reactions for %s", drug_id)
                return perturbed, effects

    # ── Path 2: Legacy hardcoded patterns (backward compat) ───────────────────

    if "glucose_inhibitor" in normalized:
        # Block glucose exchange uptake (MAR09034) — reduce to 10% capacity
        if _has_reaction(perturbed, "MAR09034"):
            rxn = perturbed.reactions.get_by_id("MAR09034")
            original_lb = rxn.lower_bound
            rxn.lower_bound = original_lb * _INHIBITION_FRACTION
            effects["MAR09034"] = f"glucose exchange: {original_lb:.2f} → {rxn.lower_bound:.2f} (90% inhibition)"

        # Block glucose transporter (MAR01378)
        if _has_reaction(perturbed, "MAR01378"):
            rxn = perturbed.reactions.get_by_id("MAR01378")
            original_lb = rxn.lower_bound
            original_ub = rxn.upper_bound
            rxn.lower_bound = original_lb * _INHIBITION_FRACTION
            rxn.upper_bound = original_ub * _INHIBITION_FRACTION
            effects["MAR01378"] = "glucose transporter: scaled to 10% capacity"

        # Fallback for demo 3-reaction model
        if not effects and _has_reaction(perturbed, "R_GLC_uptake"):
            rxn = perturbed.reactions.get_by_id("R_GLC_uptake")
            original_ub = rxn.upper_bound
            rxn.upper_bound = original_ub * _INHIBITION_FRACTION
            effects["R_GLC_uptake"] = f"glucose uptake: {original_ub:.2f} → {rxn.upper_bound:.2f} (90% inhibition)"

        if not effects:
            effects["_note"] = "glucose_inhibitor: no glucose reactions found in model"

    elif "atp_synthase_inhibitor" in normalized:
        if _has_reaction(perturbed, "MAR04137"):
            rxn = perturbed.reactions.get_by_id("MAR04137")
            original_ub = rxn.upper_bound
            rxn.upper_bound = original_ub * _INHIBITION_FRACTION
            effects["MAR04137"] = f"ATP synthase: {original_ub:.2f} → {rxn.upper_bound:.2f} (90% inhibition)"

        if not effects and _has_reaction(perturbed, "R_ATP_synthase"):
            rxn = perturbed.reactions.get_by_id("R_ATP_synthase")
            original_ub = rxn.upper_bound
            rxn.upper_bound = original_ub * 0.2
            effects["R_ATP_synthase"] = "ATP synthase: inhibited (80%)"

        if not effects:
            effects["_note"] = "atp_synthase_inhibitor: no ATP synthase reactions found in model"

    else:
        effects["_note"] = (
            f"No drug-target mapping available for '{drug_id}'. "
            "ChEMBL/DGIdb lookup returned no Human1-mapped reactions. "
            "Simulation shows baseline flux rewiring only."
        )
        logger.info("No perturbation applied for drug: %s", drug_id)

    return perturbed, effects
