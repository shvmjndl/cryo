"""CRYO Scientific Skills Integration — Loads domain-specific skills from scientific-agent-skills.

Provides specialized tools for:
- Biopython (sequence analysis, BLAST, phylogenetics)
- Bioservices (UniProt, KEGG, Reactome, STRING via API)
- DeepChem (molecular ML, drug discovery)
- Clinical decision support & clinical reports
- Medchem (medicinal chemistry)
- ESM (protein language models)

Each skill is a markdown instruction file. We expose them as a tool that
reads the skill file and returns the instructions + code templates
the agent can then execute.
"""

import json
import logging
import os
from pathlib import Path

from tools.registry import registry

logger = logging.getLogger("cryo.scientific_skills")

SKILLS_BASE = Path(__file__).resolve().parent.parent.parent / "integrations" / "scientific-agent-skills" / "scientific-skills"

# Map of biology-relevant skill categories
BIO_SKILLS = {
    "biopython": "Sequence analysis, BLAST searches, phylogenetics, PDB parsing, GenBank access",
    "bioservices": "Programmatic access to UniProt, KEGG, Reactome, STRING, ChEBI, BioModels via Python",
    "cellxgene-census": "Single-cell RNA-seq data access (Census API for 50M+ cells)",
    "clinical-decision-support": "Clinical reasoning, differential diagnosis, treatment guidelines",
    "clinical-reports": "Generate clinical-grade patient reports, lab interpretations",
    "deepchem": "Molecular machine learning, molecular featurization, drug property prediction",
    "medchem": "Medicinal chemistry workflows, ADMET prediction, lead optimization",
    "esm": "ESM protein language model — structure prediction, embeddings, fitness prediction",
    "cobrapy": "Metabolic modeling, flux balance analysis, genome-scale models",
    "datamol": "Molecular manipulation, SMILES processing, molecular descriptors",
    "torchdrug": "Drug discovery ML — molecular generation, property prediction, retrosynthesis",
    "scikit-bio": "Bioinformatics algorithms — alignment, diversity metrics, ordination",
    "polars-bio": "High-performance bioinformatics data processing with Polars",
    "depmap": "Cancer dependency map — gene essentiality, drug sensitivity data",
}


def _load_skill(args: dict, **kw) -> str:
    skill_name = args.get("skill_name", "").strip().lower()
    action = args.get("action", "instructions")

    if not skill_name:
        # List available skills
        available = {}
        for name, desc in BIO_SKILLS.items():
            skill_dir = SKILLS_BASE / name
            if skill_dir.exists():
                available[name] = desc
        return json.dumps({
            "available_skills": available,
            "total": len(available),
            "usage": "Call with skill_name to get instructions and code templates",
        })

    logger.info("Loading scientific skill: %s action=%s", skill_name, action)

    # Find the skill directory
    skill_dir = SKILLS_BASE / skill_name
    if not skill_dir.exists():
        # Try fuzzy match
        matches = [d.name for d in SKILLS_BASE.iterdir() if d.is_dir() and skill_name in d.name.lower()]
        if matches:
            skill_dir = SKILLS_BASE / matches[0]
            skill_name = matches[0]
        else:
            return json.dumps({"error": f"Skill '{skill_name}' not found. Available: {list(BIO_SKILLS.keys())}"})

    # Read the skill file (usually SKILL.md or similar)
    skill_content = ""
    for fname in ["SKILL.md", "skill.md", "README.md", "instructions.md"]:
        skill_file = skill_dir / fname
        if skill_file.exists():
            skill_content = skill_file.read_text()[:6000]
            break

    if not skill_content:
        # Try to read any .md file
        md_files = list(skill_dir.glob("*.md"))
        if md_files:
            skill_content = md_files[0].read_text()[:6000]
        else:
            # Read any .py or .yaml file
            for ext in ["*.py", "*.yaml", "*.yml", "*.json"]:
                files = list(skill_dir.glob(ext))
                if files:
                    skill_content = files[0].read_text()[:4000]
                    break

    if not skill_content:
        return json.dumps({"error": f"No readable content in skill '{skill_name}'"})

    return json.dumps({
        "skill_name": skill_name,
        "description": BIO_SKILLS.get(skill_name, "Scientific skill"),
        "instructions": skill_content,
        "files": [f.name for f in skill_dir.iterdir() if f.is_file()][:20],
    })


SKILL_SCHEMA = {
    "name": "scientific_skill",
    "description": "Access specialized scientific skills with code templates and instructions. Covers: biopython (sequences, BLAST), bioservices (UniProt/KEGG/Reactome APIs), deepchem (molecular ML), clinical-reports, medchem, ESM (protein models), depmap (cancer dependencies), and more. Call without skill_name to list all available skills.",
    "parameters": {
        "type": "object",
        "properties": {
            "skill_name": {
                "type": "string",
                "description": "Skill to load: biopython, bioservices, deepchem, clinical-reports, medchem, esm, depmap, cellxgene-census, cobrapy, datamol, torchdrug, scikit-bio, polars-bio. Leave empty to list all."
            },
            "action": {
                "type": "string",
                "enum": ["instructions", "code_template"],
                "description": "What to return: instructions (default) or code_template"
            },
        },
    },
}

registry.register(
    name="scientific_skill",
    toolset="cryo_scientific_skills",
    schema=SKILL_SCHEMA,
    handler=_load_skill,
    check_fn=lambda: SKILLS_BASE.exists(),
    emoji="🧫",
)
