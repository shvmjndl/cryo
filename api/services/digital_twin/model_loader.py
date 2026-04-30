from __future__ import annotations

import os

import cobra
from cobra.io import read_sbml_model, load_json_model

from api.services.digital_twin.model_registry import resolve_verified_backbone, normalize_backbone_name


def _build_demo_model() -> cobra.Model:
    """Build a compact feasible demo model used when no SBML backbone is configured."""
    model = cobra.Model("simple_human_metabolic_model")

    atp = cobra.Metabolite("atp", compartment="c")
    adp = cobra.Metabolite("adp", compartment="c")
    pi = cobra.Metabolite("pi", compartment="c")
    glucose = cobra.Metabolite("glucose", compartment="e")
    glucose_c = cobra.Metabolite("glucose_c", compartment="c")
    co2 = cobra.Metabolite("co2", compartment="e")
    biomass = cobra.Metabolite("biomass", compartment="c")

    model.add_metabolites([atp, adp, pi, glucose, glucose_c, co2, biomass])

    r_glucose_uptake = cobra.Reaction("R_GLC_uptake")
    r_glucose_uptake.add_metabolites({glucose: -1, glucose_c: 1})
    r_glucose_uptake.lower_bound = 0
    r_glucose_uptake.upper_bound = 10
    model.add_reactions([r_glucose_uptake])

    r_atp_synthase = cobra.Reaction("R_ATP_synthase")
    r_atp_synthase.add_metabolites({glucose_c: -1, adp: -10, pi: -10, atp: 10, co2: 6})
    r_atp_synthase.lower_bound = 0
    r_atp_synthase.upper_bound = 100
    model.add_reactions([r_atp_synthase])

    r_biomass = cobra.Reaction("R_Biomass")
    r_biomass.add_metabolites({atp: -10, adp: 10, pi: 10, biomass: 1})
    r_biomass.lower_bound = 0
    r_biomass.upper_bound = 1000
    model.add_reactions([r_biomass])

    ex_glucose = model.add_boundary(glucose, type="exchange", reaction_id="EX_glucose(e)")
    ex_glucose.lower_bound = -10
    ex_glucose.upper_bound = 0
    ex_co2 = model.add_boundary(co2, type="exchange", reaction_id="EX_co2(e)")
    ex_co2.lower_bound = 0
    ex_co2.upper_bound = 1000
    dm_biomass = model.add_boundary(biomass, type="demand", reaction_id="DM_biomass")
    dm_biomass.lower_bound = 0
    dm_biomass.upper_bound = 1000
    model.objective = "DM_biomass"

    model.notes["cryo_model_source"] = "demo"
    return model


def _load_model_from_path(path: str) -> cobra.Model:
    """Load SBML (.xml) or BiGG JSON (.json) model. Raises on unknown extension."""
    p = path.lower()
    if p.endswith(".json"):
        return load_json_model(path)
    if p.endswith(".xml") or p.endswith(".sbml"):
        return read_sbml_model(path)
    # Try SBML as default
    return read_sbml_model(path)


def load_backbone_model(backbone_name: str | None = None) -> tuple[cobra.Model, dict]:
    """
    Load a verified or local backbone model.

    backbone_name overrides the CRYO_DIGITAL_TWIN_BACKBONE env var.
    Falls back to the demo model when no path resolves.
    """
    effective_backbone = backbone_name or os.getenv("CRYO_DIGITAL_TWIN_BACKBONE", "")
    resolution = resolve_verified_backbone(
        backbone_name=effective_backbone,
        model_path=os.getenv("CRYO_DIGITAL_TWIN_MODEL_PATH", "") if not backbone_name else "",
        auto_fetch=os.getenv("CRYO_DIGITAL_TWIN_AUTO_FETCH", "true").lower() == "true",
    )

    loaded_model_path = resolution.get("loaded_model_path", "")
    if loaded_model_path:
        model = _load_model_from_path(loaded_model_path)
        model.notes["cryo_model_source"] = resolution.get("source", "sbml")
        model.notes["cryo_model_path"] = loaded_model_path
        model.notes["cryo_backbone"] = normalize_backbone_name(effective_backbone) or "unknown"
        return model, resolution

    metadata = {
        **resolution,
        "source": "demo",
        "loaded_model_path": "",
    }
    return _build_demo_model(), metadata
