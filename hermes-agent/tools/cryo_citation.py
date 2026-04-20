"""CRYO Citation Tool — Fetch proper academic citations from CrossRef and PubMed."""

import json
import logging
import re

import httpx

from tools.registry import registry

logger = logging.getLogger("cryo.citation")

CROSSREF_BASE = "https://api.crossref.org/works"
NCBI_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
TIMEOUT = 15


def _fetch_citation(args: dict, **kw) -> str:
    query = args.get("query", "").strip()
    doi = args.get("doi", "").strip()
    pmid = args.get("pmid", "").strip()
    style = args.get("style", "apa")
    max_results = min(int(args.get("max_results", 5)), 15)

    if not query and not doi and not pmid:
        return json.dumps({"error": "Provide query, doi, or pmid"})

    logger.info("Citation fetch: query=%r doi=%r pmid=%r style=%s", query, doi, pmid, style)

    citations = []

    try:
        with httpx.Client(timeout=TIMEOUT) as client:

            # Direct DOI lookup
            if doi:
                doi_clean = doi.replace("https://doi.org/", "").replace("http://doi.org/", "")
                r = client.get(f"https://api.crossref.org/works/{doi_clean}",
                               headers={"Accept": "application/json"})
                if r.status_code == 200:
                    work = r.json().get("message", {})
                    citations.append(_format_crossref_work(work, style))

            # PMID lookup
            elif pmid:
                params = {"db": "pubmed", "id": pmid, "retmode": "json"}
                r = client.get(f"{NCBI_BASE}/esummary.fcgi", params=params)
                if r.status_code == 200:
                    data = r.json()
                    info = data.get("result", {}).get(pmid, {})
                    if isinstance(info, dict) and info.get("title"):
                        citations.append(_format_pubmed_citation(info, pmid, style))

            # Search query
            else:
                params = {
                    "query.bibliographic": query,
                    "rows": max_results,
                    "select": "DOI,title,author,container-title,published-print,published-online,volume,issue,page,type,is-referenced-by-count",
                }
                r = client.get(CROSSREF_BASE, params=params,
                               headers={"Accept": "application/json"})
                if r.status_code == 200:
                    items = r.json().get("message", {}).get("items", [])
                    for work in items:
                        citations.append(_format_crossref_work(work, style))

    except Exception as e:
        logger.error("Citation fetch failed: %s", e, exc_info=True)
        return json.dumps({"error": f"Citation fetch failed: {e}"})

    if not citations:
        return json.dumps({"error": f"No citations found for query", "query": query or doi or pmid})

    return json.dumps({
        "query": query or doi or pmid,
        "style": style,
        "count": len(citations),
        "citations": citations,
    })


def _format_crossref_work(work: dict, style: str) -> dict:
    """Format a CrossRef work into a citation."""
    # Authors
    authors_raw = work.get("author", [])
    authors = []
    for a in authors_raw[:10]:
        family = a.get("family", "")
        given = a.get("given", "")
        if family:
            authors.append(f"{family}, {given[0]}." if given else family)

    # Title
    title = work.get("title", [""])[0] if work.get("title") else ""

    # Journal
    journal = work.get("container-title", [""])[0] if work.get("container-title") else ""

    # Date
    date_parts = (work.get("published-print", {}) or work.get("published-online", {})).get("date-parts", [[]])
    year = str(date_parts[0][0]) if date_parts and date_parts[0] else ""

    # Volume, issue, pages
    volume = work.get("volume", "")
    issue = work.get("issue", "")
    pages = work.get("page", "")
    doi = work.get("DOI", "")

    # Format based on style
    author_str = ", ".join(authors[:6])
    if len(authors) > 6:
        author_str += " et al."

    if style == "apa":
        formatted = f"{author_str} ({year}). {title}. *{journal}*"
        if volume:
            formatted += f", *{volume}*"
        if issue:
            formatted += f"({issue})"
        if pages:
            formatted += f", {pages}"
        formatted += f". https://doi.org/{doi}" if doi else ""
    elif style == "mla":
        formatted = f'{author_str}. "{title}." *{journal}*'
        if volume:
            formatted += f" {volume}"
        if issue:
            formatted += f".{issue}"
        if year:
            formatted += f" ({year})"
        if pages:
            formatted += f": {pages}"
        formatted += "."
    elif style == "chicago":
        formatted = f'{author_str}. "{title}." *{journal}*'
        if volume:
            formatted += f" {volume}"
        if issue:
            formatted += f", no. {issue}"
        if year:
            formatted += f" ({year})"
        if pages:
            formatted += f": {pages}"
        formatted += "."
    else:
        formatted = f"{author_str}. {title}. {journal}. {year};{volume}:{pages}."

    return {
        "formatted": formatted,
        "doi": doi,
        "title": title,
        "authors": authors[:6],
        "journal": journal,
        "year": year,
        "volume": volume,
        "issue": issue,
        "pages": pages,
        "citations_count": work.get("is-referenced-by-count", 0),
        "url": f"https://doi.org/{doi}" if doi else "",
    }


def _format_pubmed_citation(info: dict, pmid: str, style: str) -> dict:
    """Format a PubMed summary into a citation."""
    authors_raw = info.get("authors", [])
    authors = [a.get("name", "") for a in authors_raw[:6]]
    title = info.get("title", "")
    journal = info.get("fulljournalname", info.get("source", ""))
    pub_date = info.get("pubdate", "")
    year = pub_date.split(" ")[0] if pub_date else ""
    volume = info.get("volume", "")
    issue = info.get("issue", "")
    pages = info.get("pages", "")
    doi = info.get("elocationid", "").replace("doi: ", "")

    author_str = ", ".join(authors)
    if len(authors_raw) > 6:
        author_str += " et al."

    formatted = f"{author_str} ({year}). {title} *{journal}*"
    if volume:
        formatted += f", *{volume}*"
    if issue:
        formatted += f"({issue})"
    if pages:
        formatted += f", {pages}"
    formatted += f". PMID: {pmid}"

    return {
        "formatted": formatted,
        "pmid": pmid,
        "doi": doi,
        "title": title,
        "authors": authors,
        "journal": journal,
        "year": year,
        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
    }


CITATION_SCHEMA = {
    "name": "fetch_citation",
    "description": "Fetch properly formatted academic citations from CrossRef or PubMed. Use this to add legitimate references to any research answer. Supports APA, MLA, Chicago, and Vancouver citation styles. Can search by topic, DOI, or PMID.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search terms to find papers (e.g. 'CRISPR Cas9 gene therapy glioblastoma')"
            },
            "doi": {
                "type": "string",
                "description": "Direct DOI lookup (e.g. '10.1038/s41586-020-2649-2')"
            },
            "pmid": {
                "type": "string",
                "description": "PubMed ID lookup (e.g. '32848221')"
            },
            "style": {
                "type": "string",
                "enum": ["apa", "mla", "chicago", "vancouver"],
                "description": "Citation format style (default: apa)"
            },
            "max_results": {
                "type": "integer",
                "description": "Max citations to return (1-15, default 5)"
            },
        },
    },
}

registry.register(
    name="fetch_citation",
    toolset="cryo_literature",
    schema=CITATION_SCHEMA,
    handler=_fetch_citation,
    check_fn=lambda: True,
    emoji="📖",
)
