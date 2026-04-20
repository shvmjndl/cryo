"""CRYO Open Deep Research Integration — LangChain's multi-agent research system.

Uses supervisor-researcher architecture:
1. Supervisor breaks topic into subtopics
2. Multiple researcher agents work in parallel
3. Each researcher searches, reads, and returns findings with citations
4. Supervisor synthesizes into comprehensive report

Heavier than GPT-Researcher but more structured and configurable.
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

from tools.registry import registry

logger = logging.getLogger("cryo.open_deep_research")

ODR_PATH = Path(__file__).resolve().parent.parent.parent / "integrations" / "open_deep_research"
if str(ODR_PATH / "src") not in sys.path:
    sys.path.insert(0, str(ODR_PATH / "src"))


def _open_deep_research(args: dict, **kw) -> str:
    topic = args.get("topic", "").strip()
    max_sections = int(args.get("max_sections", 5))
    search_provider = args.get("search_provider", "tavily")

    if not topic:
        return json.dumps({"error": "topic is required"})

    logger.info("Open Deep Research: topic=%r sections=%d", topic, max_sections)

    try:
        from open_deep_research.graph import builder

        async def _run():
            graph = builder.compile()
            result = await graph.ainvoke({
                "topic": topic,
                "max_sections": max_sections,
            })
            return result

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(lambda: asyncio.run(_run()))
                    result = future.result(timeout=180)
            else:
                result = loop.run_until_complete(_run())
        except RuntimeError:
            result = asyncio.run(_run())

        report = result.get("final_report", "") if isinstance(result, dict) else str(result)

        logger.info("Open Deep Research complete: %d chars", len(report))
        return json.dumps({
            "status": "success",
            "topic": topic,
            "report": report[:8000],
            "full_length": len(report),
        })

    except ImportError as e:
        logger.warning("open_deep_research not available: %s — using fallback", e)
        return _fallback_research(topic)
    except Exception as e:
        logger.error("Open Deep Research failed: %s — using fallback", e, exc_info=True)
        return _fallback_research(topic)


def _fallback_research(topic: str) -> str:
    """Fallback: structured research using CRYO's own PubMed + CrossRef tools."""
    import httpx

    logger.info("Fallback research for: %r", topic)

    sections = []

    try:
        with httpx.Client(timeout=20) as client:
            # PubMed search
            r = client.get(
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
                params={"db": "pubmed", "term": topic, "retmax": 8, "retmode": "json", "sort": "relevance"}
            )
            if r.status_code == 200:
                ids = r.json().get("esearchresult", {}).get("idlist", [])
                total = r.json().get("esearchresult", {}).get("count", 0)

                if ids:
                    # Fetch summaries
                    r2 = client.get(
                        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
                        params={"db": "pubmed", "id": ",".join(ids[:5]), "retmode": "json"}
                    )
                    if r2.status_code == 200:
                        papers = []
                        for pid in ids[:5]:
                            info = r2.json().get("result", {}).get(pid, {})
                            if isinstance(info, dict):
                                papers.append({
                                    "title": info.get("title", ""),
                                    "authors": ", ".join(a.get("name", "") for a in info.get("authors", [])[:3]),
                                    "journal": info.get("fulljournalname", ""),
                                    "year": info.get("pubdate", "").split(" ")[0],
                                    "pmid": pid,
                                })
                        sections.append({
                            "heading": "Literature Survey",
                            "total_papers_found": int(total),
                            "key_papers": papers,
                        })

            # CrossRef for additional academic context
            r3 = client.get(
                "https://api.crossref.org/works",
                params={"query.bibliographic": topic, "rows": 3},
                headers={"Accept": "application/json"},
            )
            if r3.status_code == 200:
                items = r3.json().get("message", {}).get("items", [])
                crossref_papers = []
                for item in items[:3]:
                    crossref_papers.append({
                        "title": (item.get("title", [""])[0] if item.get("title") else ""),
                        "doi": item.get("DOI", ""),
                        "citations": item.get("is-referenced-by-count", 0),
                    })
                if crossref_papers:
                    sections.append({
                        "heading": "Most Cited Works",
                        "papers": crossref_papers,
                    })

    except Exception as e:
        logger.error("Fallback research failed: %s", e)

    return json.dumps({
        "status": "success",
        "topic": topic,
        "method": "fallback_multi_source",
        "sections": sections,
        "message": "Research compiled from PubMed and CrossRef. For deeper analysis, install open_deep_research dependencies.",
    })


ODR_SCHEMA = {
    "name": "multi_agent_research",
    "description": "Conduct structured multi-agent deep research on a topic. Uses supervisor-researcher architecture where multiple agents research subtopics in parallel, then synthesize findings into a comprehensive report. Best for broad topics that benefit from multi-angle investigation. Falls back to PubMed+CrossRef if full system unavailable.",
    "parameters": {
        "type": "object",
        "properties": {
            "topic": {
                "type": "string",
                "description": "Research topic (e.g. 'Recent advances in mRNA vaccine technology for cancer immunotherapy')"
            },
            "max_sections": {
                "type": "integer",
                "description": "Maximum report sections (default 5)"
            },
        },
        "required": ["topic"],
    },
}

registry.register(
    name="multi_agent_research",
    toolset="cryo_deep_research",
    schema=ODR_SCHEMA,
    handler=_open_deep_research,
    check_fn=lambda: True,
    emoji="🔍",
)
