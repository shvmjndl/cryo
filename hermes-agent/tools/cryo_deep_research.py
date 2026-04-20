"""CRYO Deep Research Tool — wraps GPT-Researcher for autonomous multi-source research reports.

GPT-Researcher autonomously:
1. Generates research questions from a query
2. Searches multiple sources (web, docs, local files)
3. Filters and aggregates results
4. Writes a comprehensive research report with citations

We wrap it as a Hermes tool so the CRYO agent can invoke it for deep dives.
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

from tools.registry import registry

logger = logging.getLogger("cryo.deep_research")

# Add gpt-researcher to path
GPT_RESEARCHER_PATH = Path(__file__).resolve().parent.parent.parent / "integrations" / "gpt-researcher"
if str(GPT_RESEARCHER_PATH) not in sys.path:
    sys.path.insert(0, str(GPT_RESEARCHER_PATH))


def _deep_research(args: dict, **kw) -> str:
    query = args.get("query", "").strip()
    report_type = args.get("report_type", "research_report")
    max_sections = int(args.get("max_sections", 5))

    if not query:
        return json.dumps({"error": "query is required"})

    logger.info("Deep research: query=%r type=%s", query, report_type)

    try:
        from gpt_researcher import GPTResearcher

        async def _run():
            researcher = GPTResearcher(
                query=query,
                report_type=report_type,
            )
            report = await researcher.conduct_research()
            return report

        # Run async researcher
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(lambda: asyncio.run(_run()))
                    report = future.result(timeout=120)
            else:
                report = loop.run_until_complete(_run())
        except RuntimeError:
            report = asyncio.run(_run())

        if not report:
            return json.dumps({"error": "Research produced no results", "query": query})

        logger.info("Deep research complete: %d chars", len(report))
        return json.dumps({
            "status": "success",
            "query": query,
            "report_type": report_type,
            "report": report[:8000],
            "full_length": len(report),
        })

    except ImportError as e:
        logger.warning("gpt-researcher not installed: %s", e)
        return json.dumps({"error": f"gpt-researcher not available: {e}. Install with: pip install gpt-researcher"})
    except Exception as e:
        logger.error("Deep research failed: %s", e, exc_info=True)
        return json.dumps({"error": f"Deep research failed: {e}"})


DEEP_RESEARCH_SCHEMA = {
    "name": "deep_research",
    "description": "Conduct autonomous deep research on any topic. Searches multiple web sources, aggregates findings, and produces a comprehensive research report with citations. Use this for complex research questions that need thorough multi-source investigation. Takes 30-120 seconds.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Research question or topic (e.g. 'What are the latest breakthroughs in CAR-T therapy for solid tumors?')"
            },
            "report_type": {
                "type": "string",
                "enum": ["research_report", "detailed_report", "quick_report"],
                "description": "Report depth: research_report (default, balanced), detailed_report (very thorough), quick_report (fast overview)"
            },
        },
        "required": ["query"],
    },
}

registry.register(
    name="deep_research",
    toolset="cryo_deep_research",
    schema=DEEP_RESEARCH_SCHEMA,
    handler=_deep_research,
    check_fn=lambda: (Path(__file__).resolve().parent.parent.parent / "integrations" / "gpt-researcher" / "gpt_researcher").exists(),
    emoji="🔬",
)
