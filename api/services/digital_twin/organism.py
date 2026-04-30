"""
Organism detection and organism-specific metadata for multi-model digital twin.

Supported organisms:
  human      — Human-GEM / Recon3D / HMR2 (any human metabolic model)
  ecoli      — iJO1366 (E. coli K-12 MG1655)
  yeast      — Yeast8 (S. cerevisiae S288C)
  unknown    — fallback for unrecognised models
"""
from __future__ import annotations

import cobra


# Canonical model ID substrings → organism
_MODEL_ID_MAP: dict[str, str] = {
    "human-gem": "human",
    "human1":    "human",
    "recon3d":   "human",
    "recon2":    "human",
    "hmr":       "human",
    "ijo1366":   "ecoli",
    "ijo_1366":  "ecoli",
    "yeast-gem": "yeast",
    "yeast8":    "yeast",
    "sce":       "yeast",
}

# Marker reaction IDs unique to each organism
_MARKER_REACTIONS: dict[str, str] = {
    "MAR13082":   "human",   # Human-GEM biomass
    "MAR09034":   "human",   # Human-GEM glucose exchange
    "GLCptspp":   "ecoli",   # E. coli glucose phosphotransferase
    "ATPM":       "_ecoli_candidate",  # Also in Yeast; disambiguate with gene IDs
    "r_4046":     "yeast",   # Yeast8 biomass pseudo-reaction
    "r_1714":     "yeast",   # Yeast8 D-glucose exchange
}

_ECOLI_MARKER_GENES = frozenset({"b0025", "b0720", "b1241"})  # known iJO1366 gene IDs


def detect_organism(model: cobra.Model) -> str:
    """Return 'human' | 'ecoli' | 'yeast' | 'unknown'. Fast — scans first 300 reactions."""
    # 1. Model ID is the most reliable signal
    mid = (model.id or "").lower().replace("_", "-")
    for fragment, org in _MODEL_ID_MAP.items():
        if fragment in mid:
            return org

    # 2. Reaction-signature scan (O(300) iterations max)
    rxn_ids: set[str] = set()
    for i, rxn in enumerate(model.reactions):
        if i >= 300:
            break
        rxn_ids.add(rxn.id)

    for rxn_id, org in _MARKER_REACTIONS.items():
        if rxn_id in rxn_ids:
            if org == "_ecoli_candidate":
                # ATPM appears in both E. coli and Yeast8; use gene IDs to disambiguate
                gene_ids = {g.id for g in model.genes}
                if gene_ids & _ECOLI_MARKER_GENES:
                    return "ecoli"
                if any(g.startswith("Y") and len(g) <= 8 for g in gene_ids):
                    return "yeast"
                return "ecoli"  # ATPM without yeast genes → assume ecoli
            return org

    # 3. Gene naming convention as last resort
    gene_ids = {g.id for g in list(model.genes)[:50]}
    if any(g.startswith("b") and g[1:].isdigit() for g in gene_ids):
        return "ecoli"
    if any(g.startswith("Y") and len(g) <= 8 for g in gene_ids):
        return "yeast"

    return "unknown"


def organism_display(organism: str) -> str:
    return {
        "human":  "Homo sapiens (Human)",
        "ecoli":  "Escherichia coli K-12",
        "yeast":  "Saccharomyces cerevisiae S288C",
        "unknown": "Unknown organism",
    }.get(organism, organism)


def is_human_model(model: cobra.Model) -> bool:
    return detect_organism(model) == "human"


def get_biomass_reaction_id(model: cobra.Model, organism: str | None = None) -> str:
    """Return the likely biomass reaction ID for a given model/organism."""
    org = organism or detect_organism(model)
    rxn_ids = {r.id for r in model.reactions}

    if org == "human":
        for candidate in ("MAR13082", "biomass_human", "Biomass_Human"):
            if candidate in rxn_ids:
                return candidate

    if org == "ecoli":
        for candidate in (
            "Ec_biomass_iJO1366_core_53p95M",
            "Ec_biomass_iJO1366_WT_53p95M",
            "BIOMASS_Ec_iJO1366_core_53p95M",
        ):
            if candidate in rxn_ids:
                return candidate

    if org == "yeast":
        for candidate in ("r_4046", "r_4047", "BIOMASS_SC5_notrace"):
            if candidate in rxn_ids:
                return candidate

    # Generic fallback: look for any reaction whose ID contains "biomass" (case-insensitive)
    for rxn in model.reactions:
        if "biomass" in rxn.id.lower() and rxn.upper_bound > 0:
            return rxn.id

    return str(model.objective.to_json()["expression"]["args"][0]["args"][0]["name"])
