"""CRYO Protein & Gene Tools — UniProt, PDB, InterPro via free public REST APIs."""

import json
import logging

import httpx

from tools.registry import registry

logger = logging.getLogger("cryo.protein")

UNIPROT_BASE = "https://rest.uniprot.org"
PDB_BASE = "https://data.rcsb.org/rest/v1"
INTERPRO_BASE = "https://www.ebi.ac.uk/interpro/api"
TIMEOUT = 20


def _safe_get(url: str, params: dict | None = None, headers: dict | None = None) -> dict | list | None:
    try:
        h = {"Accept": "application/json", **(headers or {})}
        with httpx.Client(timeout=TIMEOUT) as client:
            r = client.get(url, params=params, headers=h)
            r.raise_for_status()
            return r.json()
    except Exception as e:
        logger.error("HTTP GET failed: %s — %s", url, e)
        return {"error": str(e)}


# ─── UniProt Lookup ──────────────────────────────────────────

def _uniprot_lookup(args: dict, **kw) -> str:
    query = args.get("query", "").strip()
    organism = args.get("organism", "human")

    if not query:
        return json.dumps({"error": "query is required"})

    logger.info("UniProt lookup: query=%r organism=%s", query, organism)

    # Determine if it's an accession (P04637) or gene name (TP53)
    is_accession = len(query) == 6 and query[0].isalpha() and query[1:].replace("_", "").isalnum()

    if is_accession:
        data = _safe_get(f"{UNIPROT_BASE}/uniprotkb/{query}")
        if not data or "error" in (data if isinstance(data, dict) else {}):
            return json.dumps({"error": f"UniProt accession {query} not found"})
        return _format_uniprot_entry(data)

    # Search by gene name
    organism_id = "9606" if organism.lower() in ("human", "homo sapiens") else organism
    search_query = f"(gene:{query}) AND (organism_id:{organism_id})"
    params = {
        "query": search_query,
        "format": "json",
        "size": "5",
        "fields": "accession,id,gene_names,protein_name,organism_name,length,sequence,cc_function,cc_subcellular_location,cc_disease,ft_domain,xref_pdb,go,cc_pathway",
    }
    data = _safe_get(f"{UNIPROT_BASE}/uniprotkb/search", params=params)

    if not data or "error" in (data if isinstance(data, dict) else {}):
        return json.dumps({"error": f"No UniProt results for '{query}'"})

    results = data.get("results", []) if isinstance(data, dict) else []
    if not results:
        return json.dumps({"error": f"No UniProt results for gene '{query}' in {organism}"})

    # Return first (best) match with full details
    entry = results[0]
    return _format_uniprot_entry(entry)


def _format_uniprot_entry(entry: dict) -> str:
    genes = entry.get("genes", [])
    gene_names = []
    for g in genes:
        if "geneName" in g:
            gene_names.append(g["geneName"].get("value", ""))

    protein_name = ""
    pn = entry.get("proteinDescription", {})
    rec = pn.get("recommendedName", pn.get("submittedName", [{}]))
    if isinstance(rec, dict):
        protein_name = rec.get("fullName", {}).get("value", "")
    elif isinstance(rec, list) and rec:
        protein_name = rec[0].get("fullName", {}).get("value", "")

    # Extract function comments
    functions = []
    for comment in entry.get("comments", []):
        if comment.get("commentType") == "FUNCTION":
            for text in comment.get("texts", []):
                functions.append(text.get("value", ""))
        elif comment.get("commentType") == "DISEASE":
            disease = comment.get("disease", {})
            if disease:
                functions.append(f"Disease: {disease.get('diseaseId', '')} — {disease.get('description', '')[:200]}")

    # Extract domains
    domains = []
    for feat in entry.get("features", []):
        if feat.get("type") in ("Domain", "Region", "Motif", "Zinc finger"):
            loc = feat.get("location", {})
            start = loc.get("start", {}).get("value", "?")
            end = loc.get("end", {}).get("value", "?")
            domains.append({
                "type": feat["type"],
                "description": feat.get("description", ""),
                "start": start,
                "end": end,
            })

    # GO terms
    go_terms = []
    for xref in entry.get("uniProtKBCrossReferences", []):
        if xref.get("database") == "GO":
            props = {p["key"]: p["value"] for p in xref.get("properties", [])}
            go_terms.append({
                "id": xref.get("id", ""),
                "term": props.get("GoTerm", ""),
                "evidence": props.get("GoEvidenceType", ""),
            })

    # PDB structures
    pdb_ids = [
        xref.get("id", "")
        for xref in entry.get("uniProtKBCrossReferences", [])
        if xref.get("database") == "PDB"
    ]

    result = {
        "accession": entry.get("primaryAccession", ""),
        "entry_name": entry.get("uniProtkbId", ""),
        "gene_names": gene_names,
        "protein_name": protein_name,
        "organism": entry.get("organism", {}).get("scientificName", ""),
        "length": entry.get("sequence", {}).get("length", 0),
        "function": functions[:3],
        "domains": domains[:10],
        "go_terms": go_terms[:15],
        "pdb_structures": pdb_ids[:10],
        "url": f"https://www.uniprot.org/uniprotkb/{entry.get('primaryAccession', '')}",
    }

    return json.dumps(result)


UNIPROT_SCHEMA = {
    "name": "uniprot_lookup",
    "description": "Look up protein/gene information from UniProt. Provides function, domains, GO terms, disease associations, PDB structures, and pathways. Use for any protein or gene query.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Gene symbol (e.g. TP53, EGFR, BRCA1) or UniProt accession (e.g. P04637)"
            },
            "organism": {
                "type": "string",
                "description": "Organism name or NCBI taxonomy ID (default: human)"
            },
        },
        "required": ["query"],
    },
}

registry.register(
    name="uniprot_lookup",
    toolset="cryo_protein",
    schema=UNIPROT_SCHEMA,
    handler=_uniprot_lookup,
    check_fn=lambda: True,
    emoji="🧬",
)


# ─── PDB Structure Search ──────────────────────────────────

def _pdb_search(args: dict, **kw) -> str:
    query = args.get("query", "").strip()
    max_results = min(int(args.get("max_results", 5)), 15)

    if not query:
        return json.dumps({"error": "query is required"})

    logger.info("PDB search: query=%r", query)

    # Check if it's a direct PDB ID (4 chars)
    if len(query) == 4 and query.isalnum():
        data = _safe_get(f"{PDB_BASE}/core/entry/{query.upper()}")
        if data and "error" not in (data if isinstance(data, dict) else {}):
            return _format_pdb_entry(data, query.upper())

    # Search PDB
    search_payload = {
        "query": {
            "type": "terminal",
            "service": "full_text",
            "parameters": {"value": query}
        },
        "return_type": "entry",
        "request_options": {"paginate": {"start": 0, "rows": max_results}},
    }

    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            r = client.post(
                "https://search.rcsb.org/rcsbsearch/v2/query",
                json=search_payload,
                headers={"Content-Type": "application/json"},
            )
            r.raise_for_status()
            result = r.json()
    except Exception as e:
        logger.error("PDB search failed: %s", e)
        return json.dumps({"error": f"PDB search failed: {e}"})

    pdb_ids = [hit["identifier"] for hit in result.get("result_set", [])]
    if not pdb_ids:
        return json.dumps({"query": query, "total": 0, "structures": []})

    structures = []
    for pdb_id in pdb_ids[:max_results]:
        data = _safe_get(f"{PDB_BASE}/core/entry/{pdb_id}")
        if data and isinstance(data, dict) and "error" not in data:
            struct = data.get("struct", {})
            structures.append({
                "pdb_id": pdb_id,
                "title": struct.get("title", ""),
                "method": data.get("exptl", [{}])[0].get("method", "") if data.get("exptl") else "",
                "resolution": data.get("rcsb_entry_info", {}).get("resolution_combined", [None])[0] if data.get("rcsb_entry_info", {}).get("resolution_combined") else None,
                "release_date": data.get("rcsb_accession_info", {}).get("initial_release_date", ""),
                "url": f"https://www.rcsb.org/structure/{pdb_id}",
            })

    return json.dumps({
        "query": query,
        "total": result.get("total_count", len(structures)),
        "structures": structures,
    })


def _format_pdb_entry(data: dict, pdb_id: str) -> str:
    struct = data.get("struct", {})
    return json.dumps({
        "pdb_id": pdb_id,
        "title": struct.get("title", ""),
        "method": data.get("exptl", [{}])[0].get("method", "") if data.get("exptl") else "",
        "resolution": data.get("rcsb_entry_info", {}).get("resolution_combined", [None])[0] if data.get("rcsb_entry_info", {}).get("resolution_combined") else None,
        "release_date": data.get("rcsb_accession_info", {}).get("initial_release_date", ""),
        "polymer_entities": data.get("rcsb_entry_info", {}).get("polymer_entity_count_protein", 0) or 0,
        "url": f"https://www.rcsb.org/structure/{pdb_id}",
    })


PDB_SCHEMA = {
    "name": "pdb_search",
    "description": "Search the Protein Data Bank (PDB) for 3D protein structures. Returns PDB IDs, titles, experimental methods, and resolution. Use for structural biology queries.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search term (gene name, protein name) or direct PDB ID (e.g. 1TUP, 6LU7)"
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum structures to return (1-15, default 5)"
            },
        },
        "required": ["query"],
    },
}

registry.register(
    name="pdb_search",
    toolset="cryo_protein",
    schema=PDB_SCHEMA,
    handler=_pdb_search,
    check_fn=lambda: True,
    emoji="🔬",
)
