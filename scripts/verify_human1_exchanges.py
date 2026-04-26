#!/usr/bin/env python3
"""
Verify Human1 exchange reaction IDs needed for the cancer_warburg media preset.
Run from repo root: python scripts/verify_human1_exchanges.py
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("CRYO_DIGITAL_TWIN_BACKBONE", "human1")
os.environ.setdefault("CRYO_DIGITAL_TWIN_AUTO_FETCH", "true")

print("Loading Human1 model (may take 30-60s)...")
import cobra
model_path = Path("/cryo-data/models/human1/human1.xml")
if not model_path.exists():
    print(f"ERROR: Model not found at {model_path}")
    sys.exit(1)

model = cobra.io.read_sbml_model(str(model_path))
print(f"Loaded: {len(model.reactions)} reactions, {len(model.metabolites)} metabolites, {len(model.genes)} genes\n")

# Find all exchange reactions (those with only 1 metabolite and id starting with MAR or EX_)
exchanges = [r for r in model.reactions if len(r.metabolites) == 1 and r.lower_bound < 0]
print(f"Exchange reactions with import potential (lb < 0): {len(exchanges)}\n")

# Search keywords
KEYWORDS = [
    "glucose", "glc", "lactate", "lact", "lac",
    "oxygen", "o2", "water", "h2o",
    "phosphate", "sulfate", "ammonia", "ammonium", "nh4",
    "proton", "h+",
    "leucine", "leu", "isoleucine", "ile", "valine", "val",
    "lysine", "lys", "methionine", "met", "phenylalanine", "phe",
    "threonine", "thr", "tryptophan", "trp", "histidine", "his",
    "arginine", "arg", "glutamine", "gln", "asparagine", "asn",
    "serine", "ser", "tyrosine", "tyr", "cysteine", "cys",
    "alanine", "ala", "aspartate", "asp", "glutamate", "glu",
    "glycine", "gly", "proline", "pro",
    "biomass",
]

print("=" * 80)
print(f"{'Reaction ID':<15} {'LB':>7} {'UB':>7}  Metabolite / Name")
print("=" * 80)

found = {}
for rxn in sorted(model.reactions, key=lambda r: r.id):
    mets = list(rxn.metabolites.keys())
    met_name = (mets[0].name or mets[0].id).lower() if mets else ""
    rxn_name = (rxn.name or "").lower()

    for kw in KEYWORDS:
        if kw in met_name or kw in rxn_name or kw in rxn.id.lower():
            label = mets[0].name if mets else rxn.name
            print(f"{rxn.id:<15} {rxn.lower_bound:>7.1f} {rxn.upper_bound:>7.1f}  {label}")
            found[kw] = found.get(kw, []) + [rxn.id]
            break

print("\n" + "=" * 80)
print("BIOMASS reaction:")
for rxn in model.reactions:
    if "biomass" in rxn.name.lower() or "biomass" in rxn.id.lower():
        print(f"  {rxn.id}: {rxn.name} (objective: {rxn in [v for v in model.objective.variables]})")

print("\nObjective function reactions:")
for rxn in model.reactions:
    coef = model.objective.get_linear_coefficients([rxn.forward_variable]).get(rxn.forward_variable, 0)
    if abs(coef) > 1e-9:
        print(f"  {rxn.id}: {rxn.name} (coef={coef})")

print("\nDone.")
