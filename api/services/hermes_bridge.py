"""Bridge between CRYO's FastAPI backend and the Hermes Agent.

Handles:
- Slash command translation to natural language
- Hermes AIAgent lifecycle management
- SSE streaming with tool event tracking
- All tool executions logged to DB
"""

import asyncio
import json
import logging
import re
import sys
import traceback
from pathlib import Path
from typing import Any, AsyncGenerator

from api.core.config import settings

logger = logging.getLogger("cryo.bridge")

# Add hermes-agent to sys.path
HERMES_PATH = Path(__file__).resolve().parent.parent.parent / "hermes-agent"
if str(HERMES_PATH) not in sys.path:
    sys.path.insert(0, str(HERMES_PATH))

SOUL_PATH = Path(__file__).resolve().parent.parent.parent / "SOUL.md"
SYSTEM_PROMPT = SOUL_PATH.read_text() if SOUL_PATH.exists() else ""

# Slash command → detailed prompt translation
SLASH_TRANSLATORS = {
    "/pubmed": "Search PubMed for scientific papers about: {query}. Use the pubmed_search tool.",
    "/biorxiv": "Search bioRxiv preprints about: {query}. Use the biorxiv_search tool.",
    "/protein": "Look up detailed protein/gene information for: {query}. Use the uniprot_lookup tool.",
    "/structure": "Search for 3D protein structures of: {query}. Use the pdb_search tool.",
    "/drug": "Search for drug/compound information about: {query}. Use the chembl_search tool.",
    "/targets": "Find disease-target associations for: {query}. Use the opentargets_search tool.",
    "/variant": "Look up clinical significance of variant: {query}. Use the clinvar_lookup tool.",
    "/vep": "Predict functional effects of variant: {query}. Use the ensembl_vep tool.",
    "/repurpose": "Analyze drug repurposing opportunities for: {query}. Search for existing drugs that could be repurposed. Use chembl_search and opentargets_search tools.",
    "/pathway": "Explain the biological pathway: {query}. Include key genes/proteins, signaling cascade, disease relevance, and therapeutic targets.",
    "/compare": "Compare and contrast: {query}. Use relevant tools to gather data, then provide a detailed comparison.",
    "/export": "Export data about: {query}. Gather the data using appropriate tools, then generate an Excel file using generate_excel.",
    "/report": "Do these steps in order: Step 1: Call opentargets_search OR pubmed_search ONCE to get data about: {query}. Step 2: Using the data you got, call generate_pdf with a title, summary, and sections array. Do NOT skip Step 2. You MUST call generate_pdf.",
    "/chart": "Do these steps in order: Step 1: Gather data about {query} using ONE tool call. Step 2: Call generate_chart with the data formatted as labels and values arrays. You MUST call generate_chart.",
}

SLASH_COMMANDS = [
    {"command": "/pubmed", "description": "Search PubMed literature", "example": "/pubmed CRISPR glioblastoma"},
    {"command": "/biorxiv", "description": "Search bioRxiv preprints", "example": "/biorxiv single-cell RNA-seq"},
    {"command": "/protein", "description": "Look up protein/gene info", "example": "/protein TP53"},
    {"command": "/structure", "description": "Find protein 3D structures", "example": "/structure EGFR"},
    {"command": "/drug", "description": "Search drugs and compounds", "example": "/drug temozolomide"},
    {"command": "/targets", "description": "Disease-target associations", "example": "/targets glioblastoma"},
    {"command": "/variant", "description": "Variant clinical significance", "example": "/variant rs28934578"},
    {"command": "/vep", "description": "Variant effect prediction", "example": "/vep 17:7675088:C:T"},
    {"command": "/repurpose", "description": "Drug repurposing candidates", "example": "/repurpose Huntington disease"},
    {"command": "/pathway", "description": "Explore biological pathways", "example": "/pathway p53 signaling"},
    {"command": "/compare", "description": "Compare genes/proteins/drugs", "example": "/compare BRCA1 BRCA2"},
    {"command": "/export", "description": "Export data to Excel", "example": "/export TP53 variants"},
    {"command": "/report", "description": "Generate PDF report", "example": "/report glioblastoma drug targets"},
    {"command": "/chart", "description": "Generate visualization", "example": "/chart cancer mutation frequency"},
]

CRYO_TOOLS = [
    {"name": cmd["command"].lstrip("/"), "category": "biology", "description": cmd["description"], "slash": cmd["command"]}
    for cmd in SLASH_COMMANDS
]


def translate_slash_command(message: str) -> str:
    """Convert /command queries into tool-directing prompts."""
    message = message.strip()
    if not message.startswith("/"):
        return message

    match = re.match(r"^(/\w+)\s*(.*)", message)
    if not match:
        return message

    cmd, query = match.group(1).lower(), match.group(2).strip()
    if not query:
        return message

    template = SLASH_TRANSLATORS.get(cmd)
    if template:
        translated = template.format(query=query)
        logger.info("Slash translated: %r → %r", message, translated[:80])
        return translated

    return message


class HermesBridge:
    """Wraps Hermes AIAgent for use in FastAPI endpoints."""

    def __init__(self):
        self._agent = None
        self._tool_executions: list[dict] = []
        logger.info("HermesBridge initialized")

    def _get_agent(self):
        """Lazy-init the Hermes agent with CRYO tools enabled."""
        if self._agent is None:
            logger.info("Initializing Hermes AIAgent: model=%s provider=%s",
                        settings.HERMES_MODEL, settings.HERMES_PROVIDER)
            try:
                from run_agent import AIAgent

                self._agent = AIAgent(
                    model=settings.HERMES_MODEL,
                    max_iterations=6,
                    quiet_mode=True,
                    skip_context_files=True,
                    max_tokens=8192,
                    enabled_toolsets=[
                        "cryo_literature", "cryo_protein", "cryo_drug",
                        "cryo_variant", "cryo_reports", "cryo_vlm",
                        "code_execution",
                    ],
                )
                logger.info("Hermes AIAgent initialized successfully")
            except Exception as e:
                logger.error("Failed to initialize Hermes AIAgent: %s", e, exc_info=True)
                raise

        return self._agent

    async def chat_stream(
        self, message: str, history: list[dict[str, str]] | None = None
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream a chat response from Hermes, yielding SSE-compatible events."""

        translated = translate_slash_command(message)
        logger.info("Chat request: original=%r translated=%r", message[:80], translated[:80])

        chunks: list[str] = []
        tool_events: list[dict] = []
        errors: list[str] = []

        def on_delta(text: str):
            chunks.append(text)

        def on_tool_start(tool_id: str, name: str, args: dict):
            logger.info("Tool started: %s args=%s", name, json.dumps(args)[:200])
            tool_events.append({
                "type": "tool_start",
                "name": name,
                "args": args,
                "tool_id": tool_id,
            })

        def on_tool_complete(tool_id: str, name: str, args: dict, result: str):
            result_preview = result[:200] if result else ""
            is_error = '"error"' in result[:100] if result else False
            logger.info("Tool completed: %s success=%s result_preview=%s",
                        name, not is_error, result_preview)
            tool_events.append({
                "type": "tool_result",
                "name": name,
                "result": result[:3000] if result else "",
                "tool_id": tool_id,
                "is_error": is_error,
            })

        loop = asyncio.get_event_loop()

        def _run():
            agent = self._get_agent()
            full_message = (
                "IMPORTANT: You have max 5 tool calls. Use each one wisely. "
                "After calling tools, IMMEDIATELY write your full response synthesizing the results. "
                "Do NOT call the same tool twice with the same query. "
                "Do NOT call more tools after you have enough data to answer.\n\n"
                f"{translated}"
            )
            return agent.chat(full_message, stream_callback=on_delta)

        future = loop.run_in_executor(None, _run)

        while not future.done():
            while tool_events:
                yield tool_events.pop(0)
            while chunks:
                yield {"type": "delta", "text": chunks.pop(0)}
            await asyncio.sleep(0.05)

        # Drain remaining
        while tool_events:
            yield tool_events.pop(0)
        while chunks:
            yield {"type": "delta", "text": chunks.pop(0)}

        try:
            result = future.result()
            logger.info("Chat completed successfully")
        except Exception as e:
            error_msg = f"Agent error: {e}"
            logger.error("Chat failed: %s", e, exc_info=True)
            yield {"type": "delta", "text": f"\n\n**Error:** {error_msg}"}
            yield {"type": "error", "message": error_msg, "traceback": traceback.format_exc()}

    def get_available_tools(self) -> dict:
        """Return tools and slash commands for UI autocomplete."""
        return {
            "tools": CRYO_TOOLS,
            "slash_commands": SLASH_COMMANDS,
        }
