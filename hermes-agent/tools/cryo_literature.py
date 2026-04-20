"""CRYO Literature Mining Tools — PubMed and bioRxiv search via free public APIs."""

import json
import logging
import os
from typing import Any
from urllib.parse import quote_plus

import httpx

from tools.registry import registry

logger = logging.getLogger("cryo.literature")

NCBI_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
BIORXIV_BASE = "https://api.biorxiv.org/details/biorxiv"
TIMEOUT = 20


def _safe_get(url: str, params: dict | None = None) -> dict | str:
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            r = client.get(url, params=params)
            r.raise_for_status()
            return r.json() if "json" in r.headers.get("content-type", "") else r.text
    except Exception as e:
        logger.error("HTTP GET failed: %s — %s", url, e)
        return {"error": str(e)}


# ─── PubMed Search ──────────────────────────────────────────

def _pubmed_search(args: dict, **kw) -> str:
    query = args.get("query", "").strip()
    max_results = min(int(args.get("max_results", 10)), 25)
    sort = args.get("sort", "relevance")

    if not query:
        return json.dumps({"error": "query is required"})

    logger.info("PubMed search: query=%r max=%d sort=%s", query, max_results, sort)

    # Step 1: ESearch to get PMIDs
    search_params = {
        "db": "pubmed",
        "term": query,
        "retmax": max_results,
        "sort": sort,
        "retmode": "json",
    }
    search_result = _safe_get(f"{NCBI_BASE}/esearch.fcgi", search_params)
    if isinstance(search_result, str):
        try:
            search_result = json.loads(search_result)
        except json.JSONDecodeError:
            return json.dumps({"error": "Failed to parse PubMed search response"})

    if "error" in search_result:
        return json.dumps(search_result)

    id_list = search_result.get("esearchresult", {}).get("idlist", [])
    total_count = search_result.get("esearchresult", {}).get("count", "0")

    if not id_list:
        return json.dumps({"total": 0, "papers": [], "message": f"No results for '{query}'"})

    # Step 2: ESummary for details
    summary_params = {
        "db": "pubmed",
        "id": ",".join(id_list),
        "retmode": "json",
    }
    summary_result = _safe_get(f"{NCBI_BASE}/esummary.fcgi", summary_params)
    if isinstance(summary_result, str):
        try:
            summary_result = json.loads(summary_result)
        except json.JSONDecodeError:
            return json.dumps({"error": "Failed to parse PubMed summary response"})

    papers = []
    result_data = summary_result.get("result", {})
    for pmid in id_list:
        info = result_data.get(pmid, {})
        if not isinstance(info, dict):
            continue
        authors = [a.get("name", "") for a in info.get("authors", [])[:5]]
        papers.append({
            "pmid": pmid,
            "title": info.get("title", ""),
            "authors": authors,
            "journal": info.get("fulljournalname", info.get("source", "")),
            "pub_date": info.get("pubdate", ""),
            "doi": info.get("elocationid", ""),
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        })

    # Step 3: Fetch abstracts via EFetch
    fetch_params = {
        "db": "pubmed",
        "id": ",".join(id_list[:5]),
        "retmode": "xml",
        "rettype": "abstract",
    }
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            r = client.get(f"{NCBI_BASE}/efetch.fcgi", params=fetch_params)
            xml_text = r.text
            # Simple XML abstract extraction
            import re
            abstracts = re.findall(r"<AbstractText[^>]*>(.*?)</AbstractText>", xml_text, re.DOTALL)
            for i, abstract in enumerate(abstracts[:len(papers)]):
                # Strip XML tags
                clean = re.sub(r"<[^>]+>", "", abstract).strip()
                papers[i]["abstract"] = clean[:800]
    except Exception as e:
        logger.warning("Failed to fetch abstracts: %s", e)

    return json.dumps({
        "total": int(total_count),
        "returned": len(papers),
        "query": query,
        "papers": papers,
    })


PUBMED_SCHEMA = {
    "name": "pubmed_search",
    "description": "Search PubMed for biomedical literature. Returns paper titles, authors, journals, dates, DOIs, and abstracts. Use this for any scientific literature search.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query (supports PubMed query syntax, e.g. 'CRISPR glioblastoma', 'TP53 mutation AND cancer')"
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum papers to return (1-25, default 10)"
            },
            "sort": {
                "type": "string",
                "enum": ["relevance", "pub_date"],
                "description": "Sort order (default: relevance)"
            },
        },
        "required": ["query"],
    },
}

registry.register(
    name="pubmed_search",
    toolset="cryo_literature",
    schema=PUBMED_SCHEMA,
    handler=_pubmed_search,
    check_fn=lambda: True,
    emoji="📚",
)


# ─── bioRxiv Search ──────────────────────────────────────────

def _biorxiv_search(args: dict, **kw) -> str:
    query = args.get("query", "").strip()
    server = args.get("server", "biorxiv")
    max_results = min(int(args.get("max_results", 10)), 25)

    if not query:
        return json.dumps({"error": "query is required"})

    logger.info("bioRxiv search: query=%r server=%s", query, server)

    # bioRxiv content detail API — search by date range, get recent
    # Use the search endpoint via their API
    url = f"https://api.biorxiv.org/details/{server}/2024-01-01/2026-12-31/0/{max_results}"
    result = _safe_get(url)

    if isinstance(result, str):
        try:
            result = json.loads(result)
        except json.JSONDecodeError:
            return json.dumps({"error": "Failed to parse bioRxiv response"})

    papers = []
    query_lower = query.lower()
    for item in result.get("collection", []):
        title = item.get("title", "")
        abstract = item.get("abstract", "")
        if query_lower in title.lower() or query_lower in abstract.lower():
            papers.append({
                "doi": item.get("doi", ""),
                "title": title,
                "authors": item.get("authors", ""),
                "date": item.get("date", ""),
                "category": item.get("category", ""),
                "abstract": abstract[:600],
                "url": f"https://www.biorxiv.org/content/{item.get('doi', '')}",
            })

    return json.dumps({
        "query": query,
        "server": server,
        "returned": len(papers),
        "papers": papers[:max_results],
    })


BIORXIV_SCHEMA = {
    "name": "biorxiv_search",
    "description": "Search bioRxiv or medRxiv preprint servers for recent scientific preprints.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search terms to find in preprint titles and abstracts"
            },
            "server": {
                "type": "string",
                "enum": ["biorxiv", "medrxiv"],
                "description": "Which preprint server to search (default: biorxiv)"
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum results to return (1-25, default 10)"
            },
        },
        "required": ["query"],
    },
}

registry.register(
    name="biorxiv_search",
    toolset="cryo_literature",
    schema=BIORXIV_SCHEMA,
    handler=_biorxiv_search,
    check_fn=lambda: True,
    emoji="📄",
)
