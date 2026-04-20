"""Bridge between CRYO's FastAPI backend and the Hermes Agent."""

import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Any, AsyncGenerator

from api.core.config import settings

# Add hermes-agent to sys.path so we can import it
HERMES_PATH = Path(__file__).resolve().parent.parent.parent / "hermes-agent"
if str(HERMES_PATH) not in sys.path:
    sys.path.insert(0, str(HERMES_PATH))

SOUL_PATH = Path(__file__).resolve().parent.parent.parent / "SOUL.md"
SYSTEM_PROMPT = ""
if SOUL_PATH.exists():
    SYSTEM_PROMPT = SOUL_PATH.read_text()


# Slash command → natural language prompt translation
SLASH_TRANSLATORS = {
    "/pubmed": "Search PubMed for scientific papers about: {query}. Summarize the key findings from recent research.",
    "/biorxiv": "Search bioRxiv/medRxiv preprints about: {query}. What are the latest preprint findings?",
    "/protein": "Provide a comprehensive protein/gene analysis for: {query}. Include: function, structure, domains, pathways, disease associations, known mutations, and therapeutic relevance.",
    "/structure": "Describe the known 3D protein structures for: {query}. Include PDB IDs if known, structural features, binding sites, and how structure relates to function.",
    "/drug": "Provide detailed pharmacological information about the drug: {query}. Include: mechanism of action, targets, indications, clinical trials status, side effects, and molecular properties.",
    "/targets": "What are the key drug targets and therapeutic approaches for: {query}? Include validated targets, drugs in development, and clinical trial landscape.",
    "/variant": "Interpret the genomic variant: {query}. Include: clinical significance, associated conditions, population frequency, functional impact predictions, and relevant literature.",
    "/vep": "Predict the functional effects of the variant: {query}. Include: consequence type, impact severity, affected protein domains, and pathogenicity predictions.",
    "/repurpose": "Analyze drug repurposing opportunities for: {query}. What existing approved drugs could be repurposed based on mechanism of action, shared pathways, or structural similarity?",
    "/pathway": "Explain the biological pathway: {query}. Include: key genes/proteins involved, upstream/downstream signaling, disease relevance, and therapeutic intervention points.",
    "/compare": "Compare and contrast: {query}. Include similarities, differences, functional overlap, disease associations, and therapeutic implications.",
    "/export": "Summarize the most recent research results in a structured format for: {query}.",
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
    {"command": "/repurpose", "description": "Find drug repurposing candidates", "example": "/repurpose Huntington disease"},
    {"command": "/pathway", "description": "Explore biological pathways", "example": "/pathway p53 signaling"},
    {"command": "/compare", "description": "Compare genes/proteins/drugs", "example": "/compare BRCA1 BRCA2"},
    {"command": "/export", "description": "Export results to CSV/JSON", "example": "/export last"},
]

CRYO_TOOLS = [
    {"name": cmd["command"].lstrip("/"), "category": "biology", "description": cmd["description"], "slash": cmd["command"]}
    for cmd in SLASH_COMMANDS
]


def translate_slash_command(message: str) -> str:
    """Convert slash commands into rich natural language prompts."""
    message = message.strip()
    if not message.startswith("/"):
        return message

    # Parse: /command query text
    match = re.match(r"^(/\w+)\s*(.*)", message)
    if not match:
        return message

    cmd, query = match.group(1).lower(), match.group(2).strip()
    if not query:
        return message

    template = SLASH_TRANSLATORS.get(cmd)
    if template:
        return template.format(query=query)

    return message


class HermesBridge:
    """Wraps Hermes AIAgent for use in FastAPI endpoints."""

    def __init__(self):
        self._agent = None

    def _get_agent(self):
        """Lazy-init the Hermes agent."""
        if self._agent is None:
            from run_agent import AIAgent

            self._agent = AIAgent(
                model=settings.HERMES_MODEL,
                max_iterations=settings.HERMES_MAX_ITERATIONS,
                quiet_mode=True,
                skip_context_files=True,
                disabled_toolsets=["file", "terminal", "browser"],
            )
        return self._agent

    async def chat_stream(
        self, message: str, history: list[dict[str, str]] | None = None
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream a chat response from Hermes, yielding SSE-compatible events."""

        # Translate slash commands to natural language
        translated = translate_slash_command(message)

        chunks: list[str] = []
        tool_events: list[dict] = []

        def on_delta(text: str):
            chunks.append(text)

        def on_tool_start(tool_id: str, name: str, args: dict):
            tool_events.append({"type": "tool_start", "name": name, "args": args})

        def on_tool_complete(tool_id: str, name: str, args: dict, result: str):
            tool_events.append({"type": "tool_result", "name": name, "result": result[:2000]})

        loop = asyncio.get_event_loop()

        def _run():
            agent = self._get_agent()
            # Prepend system prompt to the message
            full_message = translated
            if SYSTEM_PROMPT:
                full_message = f"[System context: {SYSTEM_PROMPT}]\n\nUser query: {translated}"
            return agent.chat(full_message, stream_callback=on_delta)

        future = loop.run_in_executor(None, _run)

        while not future.done():
            while tool_events:
                yield tool_events.pop(0)
            while chunks:
                yield {"type": "delta", "text": chunks.pop(0)}
            await asyncio.sleep(0.05)

        # Yield remaining
        while tool_events:
            yield tool_events.pop(0)
        while chunks:
            yield {"type": "delta", "text": chunks.pop(0)}

        try:
            future.result()
        except Exception as e:
            yield {"type": "delta", "text": f"\n\nError: {str(e)}"}

    def get_available_tools(self) -> dict:
        """Return tools and slash commands for UI autocomplete."""
        return {
            "tools": CRYO_TOOLS,
            "slash_commands": SLASH_COMMANDS,
        }
