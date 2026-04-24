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
from api.services.digital_twin_service import digital_twin_service

logger = logging.getLogger("cryo.bridge")

HERMES_PATH = Path(__file__).resolve().parent.parent.parent / "hermes-agent"
if str(HERMES_PATH) not in sys.path:
    sys.path.insert(0, str(HERMES_PATH))

# Slash command → prompt translation
SLASH_TRANSLATORS = {
    "/pubmed": "Search PubMed for scientific papers about: {query}. Use the pubmed_search tool.",
    "/biorxiv": "Search bioRxiv preprints about: {query}. Use the biorxiv_search tool.",
    "/protein": "Look up detailed protein/gene information for: {query}. Use the uniprot_lookup tool.",
    "/structure": (
        "Search for 3D protein structures of: {query}. Use the pdb_search tool. "
        "For each structure found, include a viewer tag in the format [3D:PDBID|Structure Title] "
        "(e.g., [3D:1TUP|Tumor Suppressor p53]) so CRYO can render it in the inline 3D viewer. "
        "Place the tag immediately after describing each structure."
    ),
    "/drug": "Search for drug/compound information about: {query}. Use the chembl_search tool.",
    "/targets": "Find disease-target associations for: {query}. Use the opentargets_search tool.",
    "/variant": "Look up clinical significance of variant: {query}. Use the clinvar_lookup tool.",
    "/vep": "Predict functional effects of variant: {query}. Use the ensembl_vep tool.",
    "/digital_twin": (
        "Run a digital twin metabolic simulation for drug response using drug id: {query}. "
        "Use the digital_twin tool with action='simulate_drug_response'."
    ),
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
    {"command": "/digital_twin", "description": "Simulate metabolic drug response", "example": "/digital_twin glucose_inhibitor"},
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


def _extract_digital_twin_query(message: str) -> str | None:
    match = re.match(r"^/digital_twin\s+(.+)$", message.strip(), re.IGNORECASE)
    if not match:
        return None
    return match.group(1).strip() or None


def _format_digital_twin_response(drug_id: str, result: dict[str, Any]) -> str:
    initial_flux = float(result.get("initial_biomass_flux", 0.0))
    drug_flux = float(result.get("drug_biomass_flux", 0.0))
    delta = drug_flux - initial_flux
    percent_change = 0.0 if initial_flux == 0 else (delta / initial_flux) * 100

    if percent_change <= -1:
        outcome = "Predicted growth suppression"
    elif percent_change >= 1:
        outcome = "Predicted growth enhancement"
    else:
        outcome = "No material growth change"

    effects = result.get("drug_effects_applied", {}) or {}
    changed_fluxes = result.get("changed_fluxes", {}) or {}
    report_path = result.get("report_path", "")
    plot_path = result.get("plot_path", "")

    lines = [
        f"## Digital Twin Result: `{drug_id}`",
        "",
        f"**Outcome:** {outcome}",
        "",
        "### Key Metrics",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Initial Biomass Flux | {initial_flux:.4f} |",
        f"| Biomass Flux With Drug | {drug_flux:.4f} |",
        f"| Absolute Change | {delta:.4f} |",
        f"| Percent Change | {percent_change:.2f}% |",
        "",
        "### Applied Effects",
    ]

    if effects:
        for reaction_id, effect in effects.items():
            lines.append(f"- **{reaction_id}**: {effect}")
    else:
        lines.append("- No explicit reaction-level inhibition was applied.")

    lines.extend([
        "",
        "### Flux Shifts",
        "| Reaction | Flux Change |",
        "| --- | --- |",
    ])

    if changed_fluxes:
        for reaction_id, flux_change in sorted(
            changed_fluxes.items(), key=lambda item: abs(item[1]), reverse=True
        ):
            lines.append(f"| {reaction_id} | {flux_change:.4f} |")
    else:
        lines.append("| No significant change detected | 0.0000 |")

    lines.extend([
        "",
        "### Interpretation",
        "This is a deterministic result from CRYO's current demo metabolic model. It is useful for product testing and directional tool validation, but it is not a patient-specific clinical prediction.",
        "",
        "### Files",
    ])

    if report_path:
        lines.append(f"- [Digital Twin Report]({report_path})")
    if plot_path:
        lines.append(f"- [Biomass Plot]({plot_path})")
    if not report_path and not plot_path:
        lines.append("- No report artifact was generated.")

    return "\n".join(lines)


def _has_references_or_citations(text: str) -> bool:
    patterns = [
        r"\[[^\]]+\]\([^)]+\)",         # markdown links
        r"\[(?:\d+|[A-Za-z0-9_,\-\s]+)\]",  # bracket citations / refs
        r"\bdoi:\s*\S+",
        r"/api/reports/",
        r"https?://",
        r"\bReferences\b",
        r"\bSources\b",
        r"\bCitations\b",
    ]
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def _fallback_references_footer() -> str:
    return (
        "\n\n### References\n"
        "- No source-backed references or citations were included in this answer.\n"
        "- Please cross-verify it before relying on it."
    )


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
                "cryo_digital_twin",
                "cryo_deep_research", "cryo_cosight",
                "cryo_scientific_skills",
            ],
        )

    async def chat_stream(
        self, message: str, history: list[dict[str, str]] | None = None,
        user_id: str = "", conversation_id: str = "",
    ) -> AsyncGenerator[dict[str, Any], None]:
        digital_twin_query = _extract_digital_twin_query(message)
        if digital_twin_query:
            logger.info("Direct digital twin path: user=%s convo=%s drug_id=%r",
                        user_id[:8], conversation_id[:8], digital_twin_query)
            if user_id and conversation_id:
                os.environ["CRYO_USER_ID"] = user_id
                os.environ["CRYO_CONVERSATION_ID"] = conversation_id
            # Only reload if the query implies a different backbone than the loaded one
            inferred = digital_twin_service.model_metadata.get("configured_backbone", "")
            from api.services.digital_twin.model_registry import infer_backbone_from_query
            query_backbone = infer_backbone_from_query(digital_twin_query)
            if query_backbone and query_backbone != inferred:
                digital_twin_service.reload_model_for_query(digital_twin_query)
            yield {"type": "tool_start", "name": "digital_twin", "args": {
                "action": "simulate_drug_response",
                "drug_id": digital_twin_query,
            }}

            personalized_model, personalization_notes = digital_twin_service.personalize_model(
                digital_twin_service.model.copy(),
                {},
                {
                    "drug_id": digital_twin_query,
                    "configured_backbone": digital_twin_service.model_metadata.get("configured_backbone", ""),
                },
            )
            simulation_results = digital_twin_service.simulate_drug_effect(
                personalized_model,
                digital_twin_query,
            )
            if "error" in simulation_results:
                yield {"type": "tool_result", "name": "digital_twin", "result": json.dumps(simulation_results)}
                yield {"type": "delta", "text": f"Digital twin simulation failed: {simulation_results['error']}"}
                return

            report_output = digital_twin_service.generate_report(
                simulation_results,
                user_id or "default_user",
                conversation_id or "default_conversation",
                personalization_notes=personalization_notes,
            )
            combined = {
                **simulation_results,
                "report_path": report_output.get("report_path", ""),
                "plot_path": report_output.get("plot_path", ""),
            }
            yield {"type": "tool_result", "name": "digital_twin", "result": json.dumps(combined)}
            yield {"type": "delta", "text": _format_digital_twin_response(digital_twin_query, combined)}
            return

        translated = translate_slash_command(message)
        logger.info("Chat: user=%s convo=%s history=%d translated=%r",
                    user_id[:8], conversation_id[:8], len(history or []), translated[:60])

        chunks: list[str] = []
        transcript: list[str] = []
        tool_events: list[dict] = []

        def on_delta(text: str):
            chunks.append(text)
            transcript.append(text)

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
                "/report, /chart, /export, /repurpose, /pathway, /compare, /digital_twin. "
                "Your tools: pubmed_search, uniprot_lookup, pdb_search, chembl_search, "
                "opentargets_search, clinvar_lookup, ensembl_vep, fetch_citation, "
                "compile_report, generate_excel, generate_chart, verify_claim, analyze_image_vlm, digital_twin. "
                "For every non-digital-twin answer, you must call fetch_citation before the final response and include citations and/or a References section. "
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
            final_text = "".join(transcript)
            if final_text and not _has_references_or_citations(final_text):
                yield {"type": "delta", "text": _fallback_references_footer()}
            logger.info("Chat completed")
        except Exception as e:
            logger.error("Chat failed: %s", e, exc_info=True)
            yield {"type": "delta", "text": f"\n\n**Error:** {e}"}

    def get_available_tools(self) -> dict:
        return {"tools": [
            {"name": c["command"].lstrip("/"), "description": c["description"], "slash": c["command"]}
            for c in SLASH_COMMANDS
        ], "slash_commands": SLASH_COMMANDS}
