"""CRYO Omics Database Tools — StringDB, KEGG, Reactome direct REST API wrappers."""

import json
import logging
from urllib.parse import quote

import httpx

from tools.registry import registry

logger = logging.getLogger("cryo.omics_db")

TIMEOUT = 25
STRINGDB_BASE = "https://string-db.org/api"
KEGG_BASE = "https://rest.kegg.jp"
REACTOME_BASE = "https://reactome.org/ContentService"
REACTOME_ANALYSIS = "https://reactome.org/AnalysisService"


def _get(url: str, params: dict | None = None, headers: dict | None = None) -> dict | list | str:
    try:
        h = {"Accept": "application/json", **(headers or {})}
        with httpx.Client(timeout=TIMEOUT) as c:
            r = c.get(url, params=params, headers=h)
            r.raise_for_status()
            ct = r.headers.get("content-type", "")
            if "json" in ct:
                return r.json()
            return r.text
    except Exception as e:
        logger.error("GET %s failed: %s", url, e)
        return {"error": str(e)}


def _post(url: str, data: dict | None = None, headers: dict | None = None) -> dict | str:
    try:
        h = {"Accept": "application/json", **(headers or {})}
        with httpx.Client(timeout=TIMEOUT) as c:
            r = c.post(url, data=data, headers=h)
            r.raise_for_status()
            ct = r.headers.get("content-type", "")
            if "json" in ct:
                return r.json()
            return r.text
    except Exception as e:
        logger.error("POST %s failed: %s", url, e)
        return {"error": str(e)}


# ─── StringDB — Protein-Protein Interactions ───────────────────────────────

def _stringdb_ppi(args: dict, **_kw) -> str:
    genes = args.get("genes", "")
    species = int(args.get("species", 9606))  # 9606 = human
    confidence = int(args.get("confidence", 700))  # 0-1000
    limit = min(int(args.get("limit", 20)), 50)

    if not genes:
        return json.dumps({"error": "genes is required (comma-separated or single gene)"})

    gene_list = [g.strip() for g in str(genes).split(",")]
    logger.info("StringDB PPI: genes=%s confidence=%d", gene_list, confidence)

    # Map identifiers first
    map_url = f"{STRINGDB_BASE}/json/get_string_ids"
    map_resp = _post(map_url, {
        "identifiers": "\r".join(gene_list),
        "species": species,
        "limit": 1,
        "echo_query": 1,
    })
    if isinstance(map_resp, dict) and "error" in map_resp:
        return json.dumps(map_resp)

    if not map_resp:
        return json.dumps({"error": f"Genes not found in STRING: {gene_list}"})

    string_ids = [item["stringId"] for item in map_resp if "stringId" in item]
    if not string_ids:
        return json.dumps({"error": "Could not resolve any gene to STRING identifiers"})

    # Fetch interaction partners
    net_url = f"{STRINGDB_BASE}/json/network"
    net_resp = _post(net_url, {
        "identifiers": "\r".join(string_ids),
        "species": species,
        "required_score": confidence,
        "add_nodes": limit,
    })
    if isinstance(net_resp, dict) and "error" in net_resp:
        return json.dumps(net_resp)

    interactions = net_resp if isinstance(net_resp, list) else []

    # Functional enrichment
    enrich_url = f"{STRINGDB_BASE}/json/enrichment"
    enrich_resp = _post(enrich_url, {
        "identifiers": "\r".join(string_ids),
        "species": species,
    })
    enrichment = []
    if isinstance(enrich_resp, list):
        # Top GO/KEGG enrichment terms
        enrichment = [
            {
                "category": e.get("category"),
                "term": e.get("term"),
                "description": e.get("description"),
                "fdr": e.get("fdr"),
                "genes": e.get("preferredNames", [])[:5],
            }
            for e in enrich_resp[:10]
            if e.get("fdr", 1) < 0.05
        ]

    # Network image URL (for display)
    img_url = (
        f"https://string-db.org/api/image/network?"
        f"identifiers={'%0d'.join(string_ids)}&species={species}&required_score={confidence}"
    )

    return json.dumps({
        "genes_queried": gene_list,
        "string_ids": string_ids,
        "interactions": [
            {
                "gene_a": i.get("preferredName_A"),
                "gene_b": i.get("preferredName_B"),
                "score": i.get("score"),
                "experimental": i.get("experimentally_determined_interaction"),
                "database": i.get("database_annotated"),
            }
            for i in interactions[:30]
        ],
        "total_interactions": len(interactions),
        "enrichment_top10": enrichment,
        "network_image": img_url,
        "view_url": f"https://string-db.org/network/{string_ids[0]}",
    })


STRINGDB_SCHEMA = {
    "name": "stringdb_ppi",
    "description": "Query STRING database for protein-protein interaction networks and functional enrichment. Returns interaction partners, confidence scores, and top GO/KEGG enrichment terms. Also returns a network image URL.",
    "parameters": {
        "type": "object",
        "properties": {
            "genes": {"type": "string", "description": "Gene symbol(s) to query, comma-separated (e.g. 'TP53' or 'BRCA1,BRCA2,ATM')"},
            "species": {"type": "integer", "description": "NCBI taxon ID (default 9606=human, 10090=mouse)", "default": 9606},
            "confidence": {"type": "integer", "description": "Min interaction score 0-1000 (700=high, 400=medium, 150=low)", "default": 700},
            "limit": {"type": "integer", "description": "Max interaction partners to return (default 20, max 50)", "default": 20},
        },
        "required": ["genes"],
    },
}

registry.register(
    name="stringdb_ppi",
    toolset="cryo_omics_databases",
    schema=STRINGDB_SCHEMA,
    handler=_stringdb_ppi,
    check_fn=lambda: True,
    emoji="🕸️",
)


# ─── KEGG — Pathway Search & Details ───────────────────────────────────────

def _kegg_pathway(args: dict, **_kw) -> str:
    query = args.get("query", "").strip()
    action = args.get("action", "search")  # search | details | genes
    pathway_id = args.get("pathway_id", "").strip()
    organism = args.get("organism", "hsa")  # hsa=human

    logger.info("KEGG %s: query=%r pathway_id=%r", action, query, pathway_id)

    if action == "search":
        if not query:
            return json.dumps({"error": "query required for search"})
        url = f"{KEGG_BASE}/find/pathway/{quote(query)}"
        raw = _get(url, headers={"Accept": "text/plain"})
        if isinstance(raw, dict) and "error" in raw:
            return json.dumps(raw)
        if not isinstance(raw, str) or not raw.strip():
            return json.dumps({"pathways": [], "message": f"No KEGG pathways found for '{query}'"})
        pathways = []
        for line in raw.strip().split("\n"):
            if "\t" in line:
                pid, name = line.split("\t", 1)
                pathways.append({"id": pid.strip(), "name": name.strip(),
                                  "url": f"https://www.genome.jp/kegg-bin/show_pathway?{pid.strip()}"})
        return json.dumps({"query": query, "pathways": pathways[:20], "total": len(pathways)})

    elif action == "details":
        pid = pathway_id or query
        if not pid:
            return json.dumps({"error": "pathway_id required for details"})
        if not pid.startswith("path:"):
            pid = f"path:{organism}{pid.lstrip('hsa').lstrip('mmu').lstrip('path:')}" if not any(c.isalpha() for c in pid[:-1]) else f"path:{pid}"
        raw = _get(f"{KEGG_BASE}/get/{pid}", headers={"Accept": "text/plain"})
        if isinstance(raw, dict) and "error" in raw:
            return json.dumps(raw)
        if not isinstance(raw, str):
            return json.dumps({"error": "Unexpected KEGG response"})
        sections: dict = {}
        current = None
        for line in raw.split("\n"):
            if not line:
                continue
            if line[0] != " " and line[0] != "\t":
                current = line.split()[0]
                sections[current] = line[len(current):].strip()
            elif current:
                sections[current] = sections.get(current, "") + " " + line.strip()
        return json.dumps({
            "id": pid,
            "name": sections.get("NAME", ""),
            "description": sections.get("DESCRIPTION", ""),
            "class": sections.get("CLASS", ""),
            "genes_preview": sections.get("GENE", "")[:500],
            "compounds": sections.get("COMPOUND", "")[:300],
            "url": f"https://www.genome.jp/kegg-bin/show_pathway?{pid}",
        })

    elif action == "genes":
        pid = pathway_id or query
        if not pid:
            return json.dumps({"error": "pathway_id required"})
        if ":" not in pid:
            pid = f"{organism}{pid}"
        raw = _get(f"{KEGG_BASE}/link/genes/{pid}", headers={"Accept": "text/plain"})
        if isinstance(raw, dict) and "error" in raw:
            return json.dumps(raw)
        genes = []
        if isinstance(raw, str):
            for line in raw.strip().split("\n"):
                if "\t" in line:
                    _, gene = line.split("\t", 1)
                    genes.append(gene.strip())
        return json.dumps({"pathway_id": pid, "gene_count": len(genes), "genes": genes[:50]})

    return json.dumps({"error": f"Unknown action: {action}. Use: search, details, genes"})


KEGG_SCHEMA = {
    "name": "kegg_pathway",
    "description": "Query KEGG for biological pathway information. Search pathways by keyword, get pathway details, or list all genes in a pathway. Human pathways use prefix 'hsa' (e.g. hsa04110 for Cell cycle).",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Keyword to search (e.g. 'cell cycle', 'apoptosis') or pathway ID for details/genes"},
            "action": {"type": "string", "enum": ["search", "details", "genes"], "description": "search=find pathways, details=get pathway info, genes=list genes in pathway", "default": "search"},
            "pathway_id": {"type": "string", "description": "KEGG pathway ID (e.g. 'hsa04110', 'map04110') — used for details and genes actions"},
            "organism": {"type": "string", "description": "Organism code (hsa=human, mmu=mouse, rno=rat)", "default": "hsa"},
        },
        "required": ["query"],
    },
}

registry.register(
    name="kegg_pathway",
    toolset="cryo_omics_databases",
    schema=KEGG_SCHEMA,
    handler=_kegg_pathway,
    check_fn=lambda: True,
    emoji="🗺️",
)


# ─── Reactome — Pathway Enrichment & Details ───────────────────────────────

def _reactome(args: dict, **_kw) -> str:
    action = args.get("action", "search")
    query = args.get("query", "").strip()
    gene_list = args.get("gene_list", "")
    pathway_id = args.get("pathway_id", "").strip()
    species = args.get("species", "Homo sapiens")

    logger.info("Reactome %s: query=%r genes=%r", action, query, gene_list[:50] if gene_list else "")

    if action == "search":
        if not query:
            return json.dumps({"error": "query required"})
        url = f"{REACTOME_BASE}/search/query"
        resp = _get(url, params={"query": query, "species": species, "types": "Pathway", "Start": 0, "rows": 15})
        if isinstance(resp, dict) and "error" in resp:
            return json.dumps(resp)
        results = resp.get("results", []) if isinstance(resp, dict) else []
        pathways = []
        for group in results:
            for entry in group.get("entries", []):
                pathways.append({
                    "stId": entry.get("stId"),
                    "name": entry.get("name"),
                    "species": entry.get("species", [species])[0] if entry.get("species") else species,
                    "url": f"https://reactome.org/PathwayBrowser/#/{entry.get('stId')}",
                })
        return json.dumps({"query": query, "pathways": pathways[:15], "total": len(pathways)})

    elif action == "details":
        pid = pathway_id or query
        if not pid:
            return json.dumps({"error": "pathway_id required"})
        resp = _get(f"{REACTOME_BASE}/data/query/{pid}")
        if isinstance(resp, dict) and "error" in resp:
            return json.dumps(resp)
        if not isinstance(resp, dict):
            return json.dumps({"error": "Invalid response from Reactome"})
        participants_resp = _get(f"{REACTOME_BASE}/data/pathway/{pid}/containedEvents/count")
        return json.dumps({
            "stId": resp.get("stId"),
            "name": resp.get("displayName"),
            "species": resp.get("speciesName"),
            "summation": (resp.get("summation") or [{}])[0].get("text", "")[:500],
            "event_count": participants_resp if isinstance(participants_resp, int) else None,
            "url": f"https://reactome.org/PathwayBrowser/#/{resp.get('stId')}",
        })

    elif action == "enrich":
        genes = gene_list or query
        if not genes:
            return json.dumps({"error": "gene_list required for enrichment"})
        gene_str = genes.replace(",", "\n").replace(";", "\n")
        headers = {"Content-Type": "text/plain", "Accept": "application/json"}
        try:
            with httpx.Client(timeout=30) as c:
                r = c.post(f"{REACTOME_ANALYSIS}/identifiers/", content=gene_str.encode(),
                           headers=headers, params={"species": species, "pageSize": 20, "page": 1})
                r.raise_for_status()
                resp = r.json()
        except Exception as e:
            return json.dumps({"error": str(e)})

        token = resp.get("summary", {}).get("token")
        pathways_raw = resp.get("pathways", [])
        pathways = [
            {
                "name": p.get("name"),
                "stId": p.get("stId"),
                "pValue": p.get("entities", {}).get("pValue"),
                "fdr": p.get("entities", {}).get("fdr"),
                "found": p.get("entities", {}).get("found"),
                "total": p.get("entities", {}).get("total"),
                "url": f"https://reactome.org/PathwayBrowser/#/{p.get('stId')}&DTAB=AN&ANALYSIS={token}",
            }
            for p in pathways_raw[:20]
        ]
        return json.dumps({
            "genes_submitted": len(gene_str.split()),
            "pathways_found": len(pathways),
            "significant_pathways": pathways,
            "analysis_url": f"https://reactome.org/PathwayBrowser/#DTAB=AN&ANALYSIS={token}" if token else None,
        })

    return json.dumps({"error": f"Unknown action '{action}'. Use: search, details, enrich"})


REACTOME_SCHEMA = {
    "name": "reactome",
    "description": "Query Reactome pathway database. Search pathways by keyword, get pathway details, or run gene-list enrichment analysis to find significantly affected pathways.",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["search", "details", "enrich"], "description": "search=find pathways, details=get pathway info, enrich=pathway enrichment on a gene list", "default": "search"},
            "query": {"type": "string", "description": "Keyword (for search), pathway Reactome stId (for details), or gene list (for enrich)"},
            "gene_list": {"type": "string", "description": "Comma/newline-separated gene symbols for enrichment (e.g. 'TP53,BRCA1,MDM2')"},
            "pathway_id": {"type": "string", "description": "Reactome pathway ID (stId) like 'R-HSA-69278' for details action"},
            "species": {"type": "string", "description": "Species name (default 'Homo sapiens')", "default": "Homo sapiens"},
        },
        "required": ["action"],
    },
}

registry.register(
    name="reactome",
    toolset="cryo_omics_databases",
    schema=REACTOME_SCHEMA,
    handler=_reactome,
    check_fn=lambda: True,
    emoji="⚗️",
)
