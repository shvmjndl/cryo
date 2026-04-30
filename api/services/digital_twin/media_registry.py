from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import cobra
from api.services.digital_twin.organism import detect_organism


DATA_DIR = Path(__file__).resolve().parent / "data"
MEDIA_REGISTRY_PATH = DATA_DIR / "media_registry.json"


def load_media_registry() -> dict[str, Any]:
    return json.loads(MEDIA_REGISTRY_PATH.read_text())


def _has_reaction(model: cobra.Model, reaction_id: str) -> bool:
    return any(reaction.id == reaction_id for reaction in model.reactions)


def _close_all_imports(model: cobra.Model) -> int:
    closed_count = 0
    for reaction in model.exchanges:
        if reaction.lower_bound < 0:
            reaction.lower_bound = 0.0
            closed_count += 1
    return closed_count


def _apply_minimal_medium(model: cobra.Model, objective_fraction: float) -> dict[str, float]:
    baseline_solution = model.optimize()
    baseline_objective = float(baseline_solution.objective_value or 0.0)
    target_objective = max(1e-6, baseline_objective * objective_fraction)
    minimal_medium = cobra.medium.minimal_medium(model, target_objective, exports=False)

    if minimal_medium is None:
        return {}

    enabled: dict[str, float] = {}
    for reaction_id, flux_value in minimal_medium.to_dict().items():
        if not _has_reaction(model, reaction_id):
            continue
        reaction = model.reactions.get_by_id(reaction_id)
        reaction.lower_bound = -abs(float(flux_value))
        enabled[reaction_id] = reaction.lower_bound
    return enabled


def _apply_import_overrides(model: cobra.Model, imports: list[dict[str, Any]]) -> dict[str, float]:
    enabled: dict[str, float] = {}
    for import_rule in imports:
        reaction_id = import_rule.get("reaction_id", "")
        if not reaction_id or not _has_reaction(model, reaction_id):
            continue
        reaction = model.reactions.get_by_id(reaction_id)
        reaction.lower_bound = float(import_rule.get("lower_bound", reaction.lower_bound))
        enabled[reaction_id] = reaction.lower_bound
    return enabled


_CANCER_DRUG_KEYWORDS = frozenset({
    "imatinib", "temozolomide", "erlotinib", "gefitinib", "lapatinib",
    "trastuzumab", "paclitaxel", "taxol", "docetaxel", "cisplatin",
    "carboplatin", "oxaliplatin", "doxorubicin", "vincristine", "vemurafenib",
    "sorafenib", "sunitinib", "dasatinib", "nilotinib", "ibrutinib",
    "palbociclib", "ribociclib", "abemaciclib", "olaparib", "rucaparib",
    "pembrolizumab", "nivolumab", "metformin", "rapamycin", "everolimus",
    "bortezomib", "carfilzomib", "lenalidomide", "thalidomide",
    "glucose_inhibitor", "atp_synthase_inhibitor",
})


def select_media_preset(
    model: cobra.Model,
    simulation_context: dict[str, Any] | None = None,
) -> str | None:
    simulation_context = simulation_context or {}
    explicit = simulation_context.get("media_preset")
    if explicit:
        return explicit

    organism = detect_organism(model)
    drug_id = str(simulation_context.get("drug_id", "")).lower()

    # ── Microbial / non-human organisms ───────────────────────────────────────
    if organism == "ecoli":
        # Anaerobic condition for drugs that require it (e.g. metronidazole)
        anaerobic_drugs = {"metronidazole", "tinidazole", "nitrofurantoin"}
        if any(kw in drug_id for kw in anaerobic_drugs):
            return "ecoli_m9_anaerobic"
        return "ecoli_m9_aerobic"

    if organism == "yeast":
        return "yeast_sc_minimal"

    # ── Human models ──────────────────────────────────────────────────────────
    is_human1 = _has_reaction(model, "MAR13082")
    cell_line = str(simulation_context.get("cell_line", "")).strip()
    ccle_available = simulation_context.get("ccle_available", False)

    # Cell line with CCLE data → minimal media; GPR scaling is the contextualization.
    # Warburg + GPR combined is over-constrained in Human1.
    if cell_line and is_human1 and ccle_available:
        return "human1_minimal"

    # Cell line without CCLE, or known cancer drug → Warburg
    if cell_line and is_human1:
        return "cancer_warburg"

    if is_human1 and any(kw in drug_id for kw in _CANCER_DRUG_KEYWORDS):
        return "cancer_warburg"

    if is_human1 and "glucose" in drug_id:
        return "human1_glucose_challenge"

    if is_human1:
        return "human1_minimal"

    return None


def apply_media_preset(
    model: cobra.Model,
    preset_name: str,
) -> dict[str, Any]:
    registry = load_media_registry()
    preset = registry.get("presets", {}).get(preset_name)
    if not preset:
        return {
            "preset": preset_name,
            "description": "",
            "closed_import_exchanges": 0,
            "enabled_import_exchanges": {},
            "error": "Preset not found",
        }

    strategy = preset.get("strategy", "")
    enabled: dict[str, float] = {}

    baseline_model = model.copy()
    closed_count = _close_all_imports(model)

    if strategy in {"minimal_medium", "minimal_medium_with_overrides"}:
        enabled.update(_apply_minimal_medium(baseline_model, float(preset.get("objective_fraction", 0.5))))
        enabled.update(_apply_import_overrides(model, [
            {"reaction_id": reaction_id, "lower_bound": lower_bound}
            for reaction_id, lower_bound in enabled.items()
        ]))

    if strategy in {"named_exchange_medium", "minimal_medium_with_overrides"}:
        enabled.update(_apply_import_overrides(model, preset.get("imports", [])))

    return {
        "preset": preset_name,
        "description": preset.get("description", ""),
        "closed_import_exchanges": closed_count,
        "enabled_import_exchanges": enabled,
        "strategy": strategy,
    }
