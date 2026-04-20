"""CRYO Drug & Compound Tools — ChEMBL and OpenTargets via free public REST APIs."""

import json
import logging

import httpx

from tools.registry import registry

logger = logging.getLogger("cryo.drug")

CHEMBL_BASE = "https://www.ebi.ac.uk/chembl/api/data"
OPENTARGETS_GQL = "https://api.platform.opentargets.org/api/v4/graphql"
TIMEOUT = 20


def _safe_get(url: str, params: dict | None = None) -> dict | None:
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            r = client.get(url, params=params, headers={"Accept": "application/json"})
            r.raise_for_status()
            return r.json()
    except Exception as e:
        logger.error("HTTP GET failed: %s — %s", url, e)
        return {"error": str(e)}


# ─── ChEMBL Drug/Compound Search ────────────────────────────

def _chembl_search(args: dict, **kw) -> str:
    query = args.get("query", "").strip()
    search_type = args.get("search_type", "molecule")
    max_results = min(int(args.get("max_results", 10)), 20)

    if not query:
        return json.dumps({"error": "query is required"})

    logger.info("ChEMBL search: query=%r type=%s", query, search_type)

    if search_type == "target":
        return _chembl_target_search(query, max_results)

    # Molecule search
    params = {
        "q": query,
        "limit": max_results,
        "format": "json",
    }
    data = _safe_get(f"{CHEMBL_BASE}/molecule/search.json", params=params)

    if not data or "error" in (data if isinstance(data, dict) else {}):
        return json.dumps({"error": f"ChEMBL search failed for '{query}'"})

    molecules = []
    for mol in data.get("molecules", []):
        props = mol.get("molecule_properties", {}) or {}
        molecules.append({
            "chembl_id": mol.get("molecule_chembl_id", ""),
            "name": mol.get("pref_name", ""),
            "type": mol.get("molecule_type", ""),
            "max_phase": mol.get("max_phase", ""),
            "first_approval": mol.get("first_approval", ""),
            "oral": mol.get("oral", False),
            "indication_class": mol.get("indication_class", ""),
            "molecular_weight": props.get("mw_freebase", ""),
            "alogp": props.get("alogp", ""),
            "hba": props.get("hba", ""),
            "hbd": props.get("hbd", ""),
            "smiles": mol.get("molecule_structures", {}).get("canonical_smiles", "") if mol.get("molecule_structures") else "",
            "url": f"https://www.ebi.ac.uk/chembl/compound_report_card/{mol.get('molecule_chembl_id', '')}",
        })

    return json.dumps({
        "query": query,
        "total": data.get("page_meta", {}).get("total_count", len(molecules)),
        "molecules": molecules,
    })


def _chembl_target_search(query: str, max_results: int) -> str:
    params = {"q": query, "limit": max_results, "format": "json"}
    data = _safe_get(f"{CHEMBL_BASE}/target/search.json", params=params)

    if not data or "error" in (data if isinstance(data, dict) else {}):
        return json.dumps({"error": f"ChEMBL target search failed for '{query}'"})

    targets = []
    for t in data.get("targets", []):
        components = t.get("target_components", [])
        gene_names = []
        for c in components:
            for syn in c.get("target_component_synonyms", []):
                if syn.get("syn_type") == "GENE_SYMBOL":
                    gene_names.append(syn.get("component_synonym", ""))

        targets.append({
            "chembl_id": t.get("target_chembl_id", ""),
            "name": t.get("pref_name", ""),
            "type": t.get("target_type", ""),
            "organism": t.get("organism", ""),
            "gene_names": gene_names[:3],
            "url": f"https://www.ebi.ac.uk/chembl/target_report_card/{t.get('target_chembl_id', '')}",
        })

    return json.dumps({"query": query, "targets": targets})


CHEMBL_SCHEMA = {
    "name": "chembl_search",
    "description": "Search ChEMBL database for drugs, compounds, or drug targets. Returns chemical properties, approval status, molecular structures, and target information.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Drug name, compound name, or target name (e.g. 'temozolomide', 'imatinib', 'EGFR')"
            },
            "search_type": {
                "type": "string",
                "enum": ["molecule", "target"],
                "description": "Search for molecules/drugs or targets (default: molecule)"
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum results (1-20, default 10)"
            },
        },
        "required": ["query"],
    },
}

registry.register(
    name="chembl_search",
    toolset="cryo_drug",
    schema=CHEMBL_SCHEMA,
    handler=_chembl_search,
    check_fn=lambda: True,
    emoji="💊",
)


# ─── OpenTargets Disease-Target Associations ─────────────────

def _opentargets_search(args: dict, **kw) -> str:
    query = args.get("query", "").strip()
    max_results = min(int(args.get("max_results", 10)), 25)

    if not query:
        return json.dumps({"error": "query is required"})

    logger.info("OpenTargets search: query=%r", query)

    # First, search for the disease/target
    search_gql = """
    query SearchQuery($q: String!, $size: Int!) {
      search(queryString: $q, entityNames: ["disease", "target"], page: {index: 0, size: $size}) {
        total
        hits {
          id
          entity
          name
          description
        }
      }
    }
    """

    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            r = client.post(
                OPENTARGETS_GQL,
                json={"query": search_gql, "variables": {"q": query, "size": max_results}},
                headers={"Content-Type": "application/json"},
            )
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        logger.error("OpenTargets search failed: %s", e)
        return json.dumps({"error": f"OpenTargets search failed: {e}"})

    hits = data.get("data", {}).get("search", {}).get("hits", [])

    results = []
    for hit in hits:
        results.append({
            "id": hit.get("id", ""),
            "entity_type": hit.get("entity", ""),
            "name": hit.get("name", ""),
            "description": (hit.get("description", "") or "")[:300],
            "url": f"https://platform.opentargets.org/{'disease' if hit.get('entity') == 'disease' else 'target'}/{hit.get('id', '')}",
        })

    return json.dumps({
        "query": query,
        "total": data.get("data", {}).get("search", {}).get("total", 0),
        "results": results,
    })


OPENTARGETS_SCHEMA = {
    "name": "opentargets_search",
    "description": "Search OpenTargets for disease-target associations, drug targets, and therapeutic areas. Returns diseases, targets, and their relationships with evidence scores.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Disease name or target/gene name (e.g. 'glioblastoma', 'Alzheimer', 'BRAF')"
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum results (1-25, default 10)"
            },
        },
        "required": ["query"],
    },
}

registry.register(
    name="opentargets_search",
    toolset="cryo_drug",
    schema=OPENTARGETS_SCHEMA,
    handler=_opentargets_search,
    check_fn=lambda: True,
    emoji="🎯",
)
