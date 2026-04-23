"""Bridge between CRYO's FastAPI backend and the Hermes Agent."""

import asyncio
import json
import logging
import os
import re
import sys
import traceback
from pathlib import Path
from typing import Any, AsyncGenerator

from api.core.config import settings

logger = logging.getLogger("cryo.bridge")

HERMES_PATH = Path(__file__).resolve().parent.parent.parent / "hermes-agent"
if str(HERMES_PATH) not in sys.path:
    sys.path.insert(0, str(HERMES_PATH))

# Slash command → prompt translation
SLASH_TRANSLATORS = {
    "/pubmed": "Search PubMed for scientific papers about: {query}. Use the pubmed_search tool.",
    "/biorxiv": "Search bioRxiv preprints about: {query}. Use the biorxiv_search tool.",
    "/protein": "Look up detailed protein/gene information for: {query}. Use the uniprot_lookup tool.",
    "/structure": "Search for 3D protein structures of: {query}. Use the pdb_search tool.",
    "/drug": "Search for drug/compound information about: {query}. Use the chembl_search tool.",
    "/targets": "Find disease-target associations for: {query}. Use the opentargets_search tool.",
    "/variant": "Look up clinical significance of variant: {query}. Use the clinvar_lookup tool.",
    "/vep": "Predict functional effects of variant: {query}. Use the ensembl_vep tool.",
    "/repurpose": "Analyze drug repurposing opportunities for: {query}. Use chembl_search and opentargets_search tools.",
    "/pathway": "Explain the biological pathway: {query}. Include key genes/proteins, signaling cascade, disease relevance.",
    "/compare": "Compare and contrast: {query}. Use relevant tools to gather data, then provide a detailed comparison.",
    "/export": "Export data about: {query}. Gather data using tools, then generate an Excel file using generate_excel.",
    "/report": (
        "Write a comprehensive research report about: {query}. Steps: "
        "1) Call 2-3 biology tools to gather real data. "
        "2) Call fetch_citation for 5-8 APA citations. "
        "3) Call compile_report with your FULL research as markdown (2000+ words). "
        "You MUST call compile_report as the final tool."
    ),
    "/chart": "Create a visualization about: {query}. Gather data, then call generate_chart.",
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
    {"command": "/report", "description": "Generate research report", "example": "/report glioblastoma drug targets"},
    {"command": "/chart", "description": "Generate visualization", "example": "/chart cancer mutation frequency"},
]

# Report format instructions injected for /report queries
REPORT_FORMAT_PROMPT = (
    "CRITICAL REPORT FORMAT: When calling compile_report, your content MUST include these blocks:\n\n"
    '1. CHARTS — :::chart\\n{"type":"bar","title":"Title","labels":["A","B"],"values":[10,20]}\\n:::\n'
    "2. DIAGRAMS — :::diagram\\ngraph TD\\n    A[Gene] --> B[Protein]\\n:::\n"
    "3. CALLOUTS — :::callout success\\nKey finding here\\n:::\n"
    "4. TIMELINES — :::timeline\\n- **2015**: Event\\n:::\n"
    "5. PROGRESS — :::progress\\n- Label: 45% (Note)\\n:::\n"
    "6. TABLES — | col1 | col2 | with real data\n\n"
    "Include at least 2 charts, 1 diagram, 2 callouts, 1 timeline, and tables. Write 2000+ words.\n\n"
)


def translate_slash_command(message: str) -> str:
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
        logger.info("Slash translated: %r → %r", message[:60], translated[:80])
        return translated

    return message


class HermesBridge:

    def __init__(self):
        logger.info("HermesBridge initialized")

    def _create_agent(self):
        """Create a fresh agent per request — prevents cross-talk between concurrent workspace nodes."""
        from run_agent import AIAgent
        logger.info("Creating AIAgent: model=%s", settings.HERMES_MODEL)
        return AIAgent(
            model=settings.HERMES_MODEL,
            max_iterations=settings.HERMES_MAX_ITERATIONS,
            quiet_mode=True,
            skip_context_files=True,
            max_tokens=32768,
            enabled_toolsets=[
                "cryo_literature", "cryo_protein", "cryo_drug",
                "cryo_variant", "cryo_reports", "cryo_vlm",
                "cryo_deep_research", "cryo_cosight",
                "cryo_scientific_skills",
            ],
        )

    async def chat_stream(
        self, message: str, history: list[dict[str, str]] | None = None,
        user_id: str = "", conversation_id: str = "",
    ) -> AsyncGenerator[dict[str, Any], None]:
        translated = translate_slash_command(message)
        logger.info("Chat: user=%s convo=%s history=%d translated=%r",
                    user_id[:8], conversation_id[:8], len(history or []), translated[:60])

        chunks: list[str] = []
        tool_events: list[dict] = []

        def on_delta(text: str):
            chunks.append(text)

        def on_tool_start(tool_id: str, name: str, args: dict):
            logger.info("Tool start: %s args=%s", name, json.dumps(args, default=str)[:200])
            tool_events.append({"type": "tool_start", "name": name, "args": args})

        def on_tool_complete(tool_id: str, name: str, args: dict, result: str):
            is_error = '"error"' in (result or "")[:100]
            logger.info("Tool done: %s ok=%s", name, not is_error)
            tool_events.append({"type": "tool_result", "name": name, "result": (result or "")[:3000], "is_error": is_error})

        loop = asyncio.get_event_loop()

        def _run():
            agent = self._create_agent()

            # Set per-request data path so tools write to user/conversation dirs
            if user_id and conversation_id:
                os.environ["CRYO_USER_ID"] = user_id
                os.environ["CRYO_CONVERSATION_ID"] = conversation_id

            # Build conversation history for Hermes (from our PostgreSQL messages)
            conversation_history = []
            if history:
                for msg in history:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    if role in ("user", "assistant") and content:
                        conversation_history.append({"role": role, "content": content})

            # System context — always injected so agent knows its identity
            system_ctx = (
                "You are CRYO, a biology research AI. Your slash commands: "
                "/pubmed, /protein, /drug, /variant, /vep, /targets, /structure, /biorxiv, "
                "/report, /chart, /export, /repurpose, /pathway, /compare. "
                "Your tools: pubmed_search, uniprot_lookup, pdb_search, chembl_search, "
                "opentargets_search, clinvar_lookup, ensembl_vep, fetch_citation, "
                "compile_report, generate_excel, generate_chart, verify_claim, analyze_image_vlm. "
                "Use max 5 tool calls. After tools return, respond immediately.\n\n"
            )

            # Add report format instructions for report queries
            report_ctx = ""
            if any(kw in translated.lower() for kw in ["report about", "research report", "compile_report"]):
                report_ctx = REPORT_FORMAT_PROMPT

            full_message = f"{system_ctx}{report_ctx}{translated}"

            # Use run_conversation with history so agent has context from prior messages
            result = agent.run_conversation(
                full_message,
                conversation_history=conversation_history if conversation_history else None,
                stream_callback=on_delta,
            )
            return result.get("final_response", "")

        future = loop.run_in_executor(None, _run)

        while not future.done():
            while tool_events:
                yield tool_events.pop(0)
            while chunks:
                yield {"type": "delta", "text": chunks.pop(0)}
            await asyncio.sleep(0.05)

        while tool_events:
            yield tool_events.pop(0)
        while chunks:
            yield {"type": "delta", "text": chunks.pop(0)}

        try:
            future.result()
            logger.info("Chat completed")
        except Exception as e:
            logger.error("Chat failed: %s", e, exc_info=True)
            yield {"type": "delta", "text": f"\n\n**Error:** {e}"}

    def get_available_tools(self) -> dict:
        return {"tools": [
            {"name": c["command"].lstrip("/"), "description": c["description"], "slash": c["command"]}
            for c in SLASH_COMMANDS
        ], "slash_commands": SLASH_COMMANDS}
