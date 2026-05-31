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
        "Run a digital twin metabolic simulation for drug response. Query: {query}. "
        "Use the digital_twin tool with action='simulate_drug_response'. "
        "Optional: include --cell_line <name> (e.g. MCF7, HeLa, A549) to contextualize "
        "to a specific cancer cell line using CCLE expression data."
    ),
    "/simulate": (
        "Run a digital twin metabolic simulation for drug response. Query: {query}. "
        "Use the digital_twin tool with action='simulate_drug_response'. "
        "Optional: include --cell_line <name> to use cancer cell line expression data."
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
    # ── Omics database tools ──
    "/ppi": (
        "Find protein-protein interaction network for: {query}. "
        "Use the stringdb_ppi tool with the gene(s) from the query. "
        "Report top interaction partners, confidence scores, enriched pathways, and include the network image URL."
    ),
    "/kegg": (
        "Search KEGG biological pathways for: {query}. "
        "Use kegg_pathway tool with action='search'. For top results, call kegg_pathway again with action='details' to get full pathway info."
    ),
    "/reactome": (
        "Query Reactome pathways for: {query}. "
        "If query looks like a gene list (comma-separated), use reactome tool with action='enrich' to run enrichment analysis. "
        "Otherwise use action='search' to find relevant pathways."
    ),
    # ── Analysis pipelines (return code templates + instructions) ──
    "/deseq": (
        "Set up differential expression analysis for: {query}. "
        "Use the differential_expression tool to get the analysis code template and instructions. "
        "Ask the user for their count matrix and metadata file paths if not provided. "
        "Explain the expected input format and output files clearly."
    ),
    "/scrna": (
        "Set up single-cell RNA-seq analysis for: {query}. "
        "Use the scrna_analysis tool to get the Scanpy pipeline code template. "
        "Ask for the .h5ad or 10x data path. Explain QC parameters and what outputs to expect."
    ),
    "/annotate": (
        "Annotate cell types in single-cell RNA-seq data: {query}. "
        "Use the cell_annotation tool. If no model specified, default to Immune_All_High.pkl. "
        "List available CellTypist models and their use cases."
    ),
    "/atac": (
        "Set up ATAC-seq peak calling analysis for: {query}. "
        "Use the atac_seq tool to get the MACS3 pipeline code. "
        "Explain Tn5-aware settings, FRiP QC threshold (>0.2), and expected outputs."
    ),
    "/chip": (
        "Set up ChIP-seq peak calling for: {query}. "
        "Use the chip_seq tool. Ask whether this is narrow peaks (TF/H3K4me3/H3K27ac) or broad peaks (H3K27me3/H3K36me3). "
        "Explain FRiP thresholds and the need for an input/IgG control."
    ),
    "/meta": (
        "Set up shotgun metagenomics analysis for: {query}. "
        "Use the metagenomics tool to get the Kraken2+HUMAnN3 pipeline. "
        "Explain database requirements (Kraken2 DB, HUMAnN3 DB) and QC expectations."
    ),
    "/ms": (
        "Set up mass spectrometry proteomics analysis for: {query}. "
        "Use the proteomics_ms tool. Ask for the proteinGroups.txt or equivalent file path. "
        "Explain MaxQuant/DIA-NN/FragPipe input formats and QC thresholds."
    ),
    "/sec": (
        "Analyze size-exclusion chromatography data: {query}. "
        "Use the sec_report tool. Ask for the CSV data file path. "
        "Explain oligomeric state classification and quality scoring."
    ),
    # ── GEM graph ──
    "/gem": (
        "Query the genome-scale metabolic model (GEM) knowledge graph for: {query}. "
        "Use the gem_graph tool. Actions: "
        "'query' to search metabolites/reactions/genes, "
        "'gene' to explore a gene's reaction neighborhood, "
        "'reaction' for reaction details, "
        "'stats' for model statistics, "
        "'essential_genes' to list computationally essential genes. "
        "Default backbone is 'human1'. For E. coli use backbone='ijo1366', for yeast use backbone='yeast8'."
    ),
    # ── Research workflow tools ──
    "/novelty": (
        "Check research novelty for this idea: {query}. "
        "Use the novelty_check tool with the idea from the query. "
        "Report novelty score, saturation level, least-crowded query variants, and concrete differentiation recommendations."
    ),
    "/paper": (
        "Plan a research manuscript for: {query}. "
        "Use the manuscript_pipeline tool. Ask for target journal and computational/biological/clinical focus. "
        "Walk through each stage: novelty → datasets → metrics → analysis → figures → draft. "
        "Use other CRYO tools (pubmed_search, scrna_analysis, etc.) to populate each section with real data."
    ),
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
    {"command": "/digital_twin", "description": "Simulate metabolic drug response", "example": "/digital_twin imatinib --cell_line MCF7"},
    {"command": "/simulate", "description": "Alias for /digital_twin", "example": "/simulate temozolomide --cell_line HeLa"},
    {"command": "/repurpose", "description": "Drug repurposing candidates", "example": "/repurpose Huntington disease"},
    {"command": "/pathway", "description": "Explore biological pathways", "example": "/pathway p53 signaling"},
    {"command": "/compare", "description": "Compare genes/proteins/drugs", "example": "/compare BRCA1 BRCA2"},
    {"command": "/export", "description": "Export data to Excel", "example": "/export TP53 variants"},
    {"command": "/report", "description": "Generate research report", "example": "/report glioblastoma drug targets"},
    {"command": "/chart", "description": "Generate visualization", "example": "/chart cancer mutation frequency"},
    # ── Omics databases ──
    {"command": "/ppi", "description": "Protein-protein interaction network (StringDB)", "example": "/ppi TP53"},
    {"command": "/kegg", "description": "KEGG pathway search and details", "example": "/kegg cell cycle"},
    {"command": "/reactome", "description": "Reactome pathway enrichment", "example": "/reactome BRCA1,BRCA2,ATM"},
    # ── Analysis pipelines ──
    {"command": "/deseq", "description": "Differential expression analysis (PyDESeq2)", "example": "/deseq counts.csv vs control"},
    {"command": "/scrna", "description": "scRNA-seq preprocessing and clustering (Scanpy)", "example": "/scrna data.h5ad"},
    {"command": "/annotate", "description": "Cell type annotation (CellTypist)", "example": "/annotate scrna_processed.h5ad"},
    {"command": "/atac", "description": "ATAC-seq peak calling (MACS3)", "example": "/atac sample.bam"},
    {"command": "/chip", "description": "ChIP-seq peak calling (MACS3)", "example": "/chip chip.bam vs input.bam"},
    {"command": "/meta", "description": "Metagenomics pipeline (Kraken2 + HUMAnN3)", "example": "/meta sample_R1.fastq.gz"},
    {"command": "/ms", "description": "Mass spectrometry proteomics (MaxQuant/DIA-NN)", "example": "/ms proteinGroups.txt"},
    {"command": "/sec", "description": "SEC chromatography peak analysis", "example": "/sec sec_data.csv"},
    # ── GEM graph ──
    {"command": "/gem", "description": "Query GEM metabolite–reaction–gene knowledge graph", "example": "/gem glucose reactions --model ijo1366"},
    # ── Document collections ──
    {"command": "/collections", "description": "Search or read uploaded PDF/image documents (VLM parsed)", "example": "/collections search kinase inhibitor"},
    # ── Research workflow ──
    {"command": "/novelty", "description": "Research novelty / saturation check", "example": "/novelty CRISPR base editing sickle cell"},
    {"command": "/paper", "description": "Full manuscript planning pipeline", "example": "/paper spatial transcriptomics TNBC"},
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


def _extract_digital_twin_query(message: str) -> tuple[str | None, str, str]:
    """
    Parse /digital_twin <drug_id> [--cell_line <name>] [--model <backbone>]
    Returns (drug_id, cell_line, backbone). drug_id is None if not matched.
    """
    msg = message.strip()
    pattern = re.match(r"^/(?:digital_twin|simulate)\s+(.+)$", msg, re.IGNORECASE)
    if not pattern:
        return None, "", ""

    raw = pattern.group(1).strip()

    # Extract --cell_line flag
    cell_line = ""
    cl_match = re.search(r"--cell[_\-]?line\s+(\S+)", raw, re.IGNORECASE)
    if cl_match:
        cell_line = cl_match.group(1)
        raw = (raw[:cl_match.start()] + raw[cl_match.end():]).strip()

    # Extract --model / --backbone flag
    backbone = ""
    m_match = re.search(r"--(?:model|backbone)\s+(\S+)", raw, re.IGNORECASE)
    if m_match:
        backbone = m_match.group(1)
        raw = (raw[:m_match.start()] + raw[m_match.end():]).strip()

    drug_id = raw.strip() or None
    return drug_id, cell_line, backbone


def _format_digital_twin_response(drug_id: str, result: dict[str, Any]) -> str:
    initial_flux = float(result.get("initial_biomass_flux", 0.0))
    drug_flux = float(result.get("drug_biomass_flux", 0.0))
    delta = drug_flux - initial_flux
    percent_change = 0.0 if initial_flux == 0 else (delta / initial_flux) * 100
    cell_line = result.get("cell_line", "")
    organism_disp = result.get("organism_display", "")
    backbone = result.get("backbone", "")

    if percent_change <= -5:
        outcome = f"Predicted growth suppression ({abs(percent_change):.1f}%)"
    elif percent_change >= 5:
        outcome = f"Predicted growth enhancement ({percent_change:.1f}%)"
    else:
        outcome = (
            "Minimal biomass change — metabolic rewiring detected. "
            "For quantitative drug response, use `--cell_line MCF7` (or similar) "
            "to enable CCLE-based contextualization."
        )

    effects = result.get("drug_effects_applied", {}) or {}
    changed_fluxes = result.get("changed_fluxes", {}) or {}
    report_path = result.get("report_path", "")
    plot_path = result.get("plot_path", "")
    drug_target_info = result.get("drug_target_info", {}) or {}
    gdsc_validation = result.get("gdsc_validation", {}) or {}
    citations = result.get("citations", [])

    lines = [
        f"## Digital Twin Result: `{drug_id}`",
        "",
        f"**Outcome:** {outcome}",
    ]

    # Organism / model context
    if organism_disp:
        backbone_str = f" (`{backbone}`)" if backbone else ""
        lines.extend(["", f"**Model:** {organism_disp}{backbone_str}"])

    # Drug target info
    targets = drug_target_info.get("targets", [])
    if targets:
        source = drug_target_info.get("source", "ChEMBL/DGIdb")
        src_label = {
            "pathogen_targets_db": "Pathogen Target DB",
            "chembl": "ChEMBL",
            "dgidb": "DGIdb",
        }.get(source, source)
        gene_list = ", ".join(t["gene_symbol"] for t in targets[:5])
        mech = targets[0].get("mechanism", "")
        lines.extend(["", f"**Drug targets ({src_label}):** {gene_list}"])
        if mech:
            lines.extend(["", f"**Mechanism:** {mech}"])

    # Cell line context
    if cell_line:
        gpr = result.get("personalization_notes", {}).get("gpr_scaling", {})
        if gpr.get("applied"):
            lines.extend(["", f"**Cell line:** {cell_line} — {gpr.get('reactions_constrained', 0)} reactions constrained via CCLE GPR scaling"])
        else:
            lines.extend(["", f"**Cell line:** {cell_line} — CCLE data not available (run `setup_digital_twin.py`)"])

    lines.extend([
        "",
        "### Key Metrics",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Baseline Biomass Flux | {initial_flux:.4f} |",
        f"| Biomass Flux With Drug | {drug_flux:.4f} |",
        f"| Absolute Change | {delta:.4f} |",
        f"| Percent Change | {percent_change:.2f}% |",
        f"| Flux Rewiring Events | {len(changed_fluxes)} reactions |",
    ])

    # GDSC validation
    if gdsc_validation.get("found"):
        ic50 = gdsc_validation.get("ic50_um", "N/A")
        lines.extend([
            "",
            "### GDSC2 Experimental Validation",
            f"| Metric | Value |",
            f"| --- | --- |",
            f"| Experimental IC50 | {ic50:.4f} μM |",
            f"| Area Under Curve | {gdsc_validation.get('auc', 'N/A')} |",
            f"| Source | GDSC2 (Sanger Institute) |",
        ])
    elif cell_line:
        lines.extend([
            "",
            "### GDSC2 Experimental Validation",
            "",
            f"No GDSC2 data available for {drug_id} in {cell_line}. "
            "Results should be independently verified before use in research.",
        ])

    lines.extend([
        "",
        "### Applied Perturbations",
        "",
    ])
    if effects:
        for reaction_id, effect in effects.items():
            lines.append(f"- **{reaction_id}**: {effect}")
    else:
        lines.append("- No Human1-mapped reactions found for this drug. Flux rewiring reflects model-level response.")

    # Top flux shifts (limit to top 10 for readability)
    top_fluxes = sorted(changed_fluxes.items(), key=lambda x: abs(x[1]), reverse=True)[:10]
    if top_fluxes:
        lines.extend([
            "",
            "### Top Flux Shifts (Metabolic Rewiring)",
            "| Reaction | Flux Change |",
            "| --- | --- |",
        ])
        for rxn_id, fc in top_fluxes:
            lines.append(f"| {rxn_id} | {fc:+.4f} |")
        if len(changed_fluxes) > 10:
            lines.append(f"| *+{len(changed_fluxes)-10} more...* | See full report |")

    lines.extend(["", "### Files"])
    if report_path:
        lines.append(f"- [Digital Twin Report]({report_path})")
    if plot_path:
        lines.append(f"- [Biomass Plot]({plot_path})")
    if not report_path and not plot_path:
        lines.append("- No report artifact was generated.")

    # Citations — always present
    lines.extend(["", "### References"])
    if citations:
        for i, c in enumerate(citations, 1):
            doi = c.get("doi", "")
            url = c.get("url", f"https://doi.org/{doi}" if doi else "")
            note = c.get("note", "")
            note_str = f" *({note})*" if note else ""
            if url:
                lines.append(
                    f"{i}. {c['authors']} ({c['year']}). *{c['title']}*. "
                    f"{c['journal']}. [{doi}]({url}){note_str}"
                )
            else:
                lines.append(f"{i}. {c['authors']} ({c['year']}). *{c['title']}*. {c['journal']}{note_str}")
    else:
        lines.append(
            "**Sources could not be verified** — please cross-check results before "
            "clinical or research use."
        )

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
                "cryo_digital_twin", "cryo_gem_graph",
                "cryo_omics_databases", "cryo_analysis_skills",
                "cryo_deep_research", "cryo_cosight",
                "cryo_scientific_skills", "cryo_collections",
            ],
        )

    async def _fetch_file_context(
        self, file_ids: list[str], user_id: str = "", message: str = ""
    ) -> str:
        """Fetch markdown content for @-mentioned files and format as injected context.

        Resolves files by UUID (from explicit file_ids) OR by @filename mention in the
        message text (fallback when the frontend didn't pass file_ids).
        """
        from pathlib import Path as _Path
        from api.core.database import async_session
        from api.models.collection import Collection, CollectionFile
        from sqlalchemy import select
        import re as _re
        import uuid as _uuid

        blocks: list[str] = []
        try:
            async with async_session() as db:
                if file_ids:
                    result = await db.execute(
                        select(CollectionFile).where(
                            CollectionFile.id.in_([_uuid.UUID(fid) for fid in file_ids]),
                            CollectionFile.status == "done",
                        )
                    )
                    rows = result.scalars().all()
                else:
                    # Fallback: extract @filename mentions from message text
                    mentions = _re.findall(r'@([\w\s.\-]+?)(?=\s+\w|\s*$)', message)
                    if not mentions or not user_id:
                        return ""
                    # Find user's collections and search for files by name
                    col_result = await db.execute(
                        select(Collection).where(
                            Collection.user_id == _uuid.UUID(user_id),
                        ).order_by(Collection.created_at.desc()).limit(5)
                    )
                    col_ids = [c.id for c in col_result.scalars().all()]
                    if not col_ids:
                        return ""
                    file_result = await db.execute(
                        select(CollectionFile).where(
                            CollectionFile.collection_id.in_(col_ids),
                            CollectionFile.status == "done",
                        )
                    )
                    all_files = file_result.scalars().all()
                    # Match by filename (case-insensitive, strip extension for fuzzy match)
                    rows = []
                    for mention in mentions:
                        mention_clean = mention.strip().lower()
                        match = next(
                            (f for f in all_files
                             if mention_clean in f.original_filename.lower()
                             or f.original_filename.lower().startswith(mention_clean)),
                            None,
                        )
                        if match and match not in rows:
                            rows.append(match)

                for f in rows:
                    if f.markdown_path and _Path(f.markdown_path).exists():
                        content = _Path(f.markdown_path).read_text(encoding="utf-8")
                        blocks.append(
                            f"[Document: {f.original_filename}]\n{content}\n[/Document]"
                        )
                        logger.info("Injecting document context: %s", f.original_filename)
        except Exception as e:
            logger.warning("Failed to fetch file context for %s: %s", file_ids or message[:60], e)
        return "\n\n".join(blocks)

    async def chat_stream(
        self, message: str, history: list[dict[str, str]] | None = None,
        user_id: str = "", conversation_id: str = "",
        file_ids: list[str] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        digital_twin_query, cell_line, backbone = _extract_digital_twin_query(message)
        if digital_twin_query:
            logger.info("Direct digital twin path: user=%s convo=%s drug_id=%r cell_line=%r backbone=%r",
                        user_id[:8], conversation_id[:8], digital_twin_query, cell_line, backbone)
            if user_id and conversation_id:
                os.environ["CRYO_USER_ID"] = user_id
                os.environ["CRYO_CONVERSATION_ID"] = conversation_id

            yield {"type": "tool_start", "name": "digital_twin", "args": {
                "action": "simulate_drug_response",
                "drug_id": digital_twin_query,
                "cell_line": cell_line,
                "backbone": backbone,
            }}

            # Full simulate_drug_response handles drug_lookup + CCLE + GDSC + pathogen targets
            simulation_output = digital_twin_service.simulate_drug_response(
                user_id=user_id or "default_user",
                conversation_id=conversation_id or "default_conversation",
                drug_id=digital_twin_query,
                cell_line=cell_line,
                backbone=backbone,
            )

            if "error" in simulation_output:
                yield {"type": "tool_result", "name": "digital_twin", "result": json.dumps(simulation_output)}
                yield {"type": "delta", "text": f"Digital twin simulation failed: {simulation_output['error']}"}
                return

            yield {"type": "tool_result", "name": "digital_twin", "result": json.dumps({
                k: v for k, v in simulation_output.items()
                if k not in ("full_solution", "changed_fluxes")  # keep payload small
            })}
            yield {"type": "delta", "text": _format_digital_twin_response(digital_twin_query, simulation_output)}
            return

        translated = translate_slash_command(message)
        logger.info("Chat: user=%s convo=%s history=%d translated=%r",
                    user_id[:8], conversation_id[:8], len(history or []), translated[:60])

        # Pre-fetch @-mentioned file content so agent receives it inline
        file_context = await self._fetch_file_context(file_ids or [], user_id=user_id, message=translated)

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
                # Mint a short-lived token so collections tool can call the API
                from api.core.auth import create_access_token
                os.environ["CRYO_USER_TOKEN"] = create_access_token(user_id)

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
                "compile_report, generate_excel, generate_chart, verify_claim, analyze_image_vlm, digital_twin, collections. "
                "IMPORTANT — document access: If the user references 'the document', 'the file', 'the PDF', 'the paper', "
                "'the report', or asks to summarise/read/analyse an uploaded file, you MUST call the collections tool "
                "(action='read_file' or action='search') FIRST before answering. "
                "Do NOT summarise from your own knowledge when a document has been uploaded. "
                "For every non-digital-twin answer, you must call fetch_citation before the final response and include citations and/or a References section. "
                "Use max 5 tool calls. After tools return, respond immediately.\n\n"
            )

            # Add report format instructions for report queries
            report_ctx = ""
            if any(kw in translated.lower() for kw in ["report about", "research report", "compile_report"]):
                report_ctx = REPORT_FORMAT_PROMPT

            # Inject @-mentioned document content before the user message
            if file_context:
                doc_ctx = (
                    "The following document(s) have been provided inline — answer DIRECTLY from their content. "
                    "Do NOT call the collections tool for these documents; the content is already below.\n\n"
                    f"{file_context}\n\n"
                )
                # Strip @mentions from user message — content already injected above
                import re as _re
                clean_message = _re.sub(r'@[\w.\-\s]+?(?=\s+\w|\s*$)', '', translated).strip()
                user_message = clean_message or translated
            else:
                doc_ctx = ""
                user_message = translated

            full_message = f"{system_ctx}{report_ctx}{doc_ctx}{user_message}"

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
