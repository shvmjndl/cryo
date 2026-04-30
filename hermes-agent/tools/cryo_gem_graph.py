"""
GEM graph tool — query the metabolite–reaction–gene knowledge graph of any loaded metabolic model.

Supports: Human1, iJO1366 (E. coli), Yeast8, Recon3D.
"""
import json
import os

import requests
from tools.registry import registry

_API_BASE = os.getenv("CRYO_API_URL", "http://localhost:8000")


def _gem_graph(args: dict, **_kw) -> str:
    action = args.get("action", "query")
    backbone = args.get("backbone", "human1")
    query = args.get("query", "")
    gene_id = args.get("gene_id", "")
    reaction_id = args.get("reaction_id", "")
    metabolite_id = args.get("metabolite_id", "")
    subsystem = args.get("subsystem", "")
    limit = int(args.get("limit", 25))
    compute_essential = bool(args.get("compute_essential_genes", False))

    base = f"{_API_BASE}/api/gem"

    try:
        if action == "stats":
            r = requests.get(f"{base}/stats", params={"backbone": backbone}, timeout=30)
            r.raise_for_status()
            data = r.json()
            return json.dumps({
                "model_id": data.get("model_id"),
                "organism": data.get("organism_display"),
                "reactions": data.get("reactions"),
                "metabolites": data.get("metabolites"),
                "genes": data.get("genes"),
                "subsystems": data.get("subsystems"),
                "exchanges": data.get("exchanges"),
                "compartments": data.get("compartments"),
            })

        elif action == "query":
            if not query:
                return json.dumps({"error": "'query' field required for action='query'"})
            r = requests.get(f"{base}/query",
                             params={"q": query, "backbone": backbone, "limit": limit},
                             timeout=30)
            r.raise_for_status()
            return r.text

        elif action == "gene":
            if not gene_id:
                return json.dumps({"error": "'gene_id' required for action='gene'"})
            depth = int(args.get("depth", 1))
            r = requests.get(f"{base}/gene/{gene_id}",
                             params={"backbone": backbone, "depth": depth}, timeout=30)
            r.raise_for_status()
            return r.text

        elif action == "reaction":
            if not reaction_id:
                return json.dumps({"error": "'reaction_id' required for action='reaction'"})
            r = requests.get(f"{base}/reaction/{reaction_id}",
                             params={"backbone": backbone}, timeout=30)
            r.raise_for_status()
            return r.text

        elif action == "metabolite":
            if not metabolite_id:
                return json.dumps({"error": "'metabolite_id' required for action='metabolite'"})
            r = requests.get(f"{base}/metabolite/{metabolite_id}",
                             params={"backbone": backbone}, timeout=30)
            r.raise_for_status()
            return r.text

        elif action == "subsystem":
            if not subsystem:
                return json.dumps({"error": "'subsystem' required for action='subsystem'"})
            r = requests.get(f"{base}/subsystem",
                             params={"name": subsystem, "backbone": backbone, "limit": limit},
                             timeout=30)
            r.raise_for_status()
            return r.text

        elif action == "essential_genes":
            r = requests.get(f"{base}/essential_genes",
                             params={"backbone": backbone, "compute": str(compute_essential).lower()},
                             timeout=120)
            r.raise_for_status()
            return r.text

        elif action == "backbones":
            r = requests.get(f"{base}/backbones", timeout=10)
            r.raise_for_status()
            return r.text

        else:
            return json.dumps({"error": f"Unknown action: {action}. Use: stats, query, gene, reaction, metabolite, subsystem, essential_genes, backbones"})

    except requests.exceptions.RequestException as exc:
        return json.dumps({"error": f"API request failed: {exc}"})


GEM_GRAPH_SCHEMA = {
    "name": "gem_graph",
    "description": (
        "Query the metabolite–reaction–gene knowledge graph of a genome-scale metabolic model (GEM). "
        "Supports Human1 (human), iJO1366 (E. coli), Yeast8 (S. cerevisiae), Recon3D. "
        "Use this to: search metabolites/reactions/genes, explore gene neighborhoods, "
        "get reaction details, find pathway reactions, list essential genes."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["stats", "query", "gene", "reaction", "metabolite", "subsystem", "essential_genes", "backbones"],
                "description": (
                    "stats: model statistics (reactions/metabolites/genes counts). "
                    "query: full-text search across all node types. "
                    "gene: get all reactions catalysed by a gene + their metabolites. "
                    "reaction: full details of one reaction. "
                    "metabolite: producing and consuming reactions for a metabolite. "
                    "subsystem: all reactions in a metabolic pathway/subsystem. "
                    "essential_genes: computationally identified essential genes (cached). "
                    "backbones: list available models."
                ),
            },
            "backbone": {
                "type": "string",
                "description": (
                    "Model backbone to query. Options: 'human1' (default, H. sapiens), "
                    "'ijo1366' (E. coli K-12), 'yeast8' (S. cerevisiae), 'recon3d' (human). "
                    "For antibiotic target research use 'ijo1366'."
                ),
            },
            "query": {
                "type": "string",
                "description": "Search term for action='query' (metabolite name, reaction ID, gene name, etc.)",
            },
            "gene_id": {
                "type": "string",
                "description": "Gene ID for action='gene' (e.g. 'TP53' for human, 'b0048' for E. coli folA)",
            },
            "reaction_id": {
                "type": "string",
                "description": "Reaction ID for action='reaction' (e.g. 'MAR09034' for human glucose, 'GLCptspp' for E. coli)",
            },
            "metabolite_id": {
                "type": "string",
                "description": "Metabolite ID for action='metabolite' (e.g. 'glc__D_e' for D-glucose extracellular)",
            },
            "subsystem": {
                "type": "string",
                "description": "Subsystem/pathway name for action='subsystem' (e.g. 'Glycolysis', 'Folate metabolism', 'Ergosterol biosynthesis')",
            },
            "limit": {
                "type": "integer",
                "description": "Max results to return (default 25, max 100)",
            },
            "depth": {
                "type": "integer",
                "description": "Neighbourhood depth for action='gene'. 1=direct reactions, 2=also connected reactions (default 1)",
            },
            "compute_essential_genes": {
                "type": "boolean",
                "description": "For action='essential_genes': set true to compute (slow). Default false returns cached only.",
            },
        },
        "required": ["action"],
    },
}

registry.register(
    name="gem_graph",
    toolset="cryo_gem_graph",
    schema=GEM_GRAPH_SCHEMA,
    handler=_gem_graph,
    check_fn=lambda: True,
    emoji="🕸️",
)
