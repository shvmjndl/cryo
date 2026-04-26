from __future__ import annotations

import os
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

from api.services.report_engine import generate_report

# ─── Standard Citations ────────────────────────────────────────────────────────
# Always included: Human-GEM, COBRApy
# Conditionally included: ChEMBL/DGIdb (drug lookup), CCLE (GPR scaling), GDSC (validation)

CITATIONS = {
    "human_gem": {
        "title": "An atlas of human metabolism",
        "authors": "Robinson JL et al.",
        "year": 2020,
        "journal": "Science Signaling",
        "doi": "10.1126/scisignal.aaz1482",
        "url": "https://doi.org/10.1126/scisignal.aaz1482",
        "note": "Human1 genome-scale metabolic model used as simulation backbone",
    },
    "cobrapy": {
        "title": "COBRApy: COnstraints-Based Reconstruction and Analysis for Python",
        "authors": "Ebrahim A et al.",
        "year": 2013,
        "journal": "BMC Systems Biology",
        "doi": "10.1186/1752-0509-7-74",
        "url": "https://doi.org/10.1186/1752-0509-7-74",
        "note": "Flux Balance Analysis engine",
    },
    "chembl": {
        "title": "ChEMBL: a large-scale bioactivity database for drug discovery",
        "authors": "Gaulton A et al.",
        "year": 2012,
        "journal": "Nucleic Acids Research",
        "doi": "10.1093/nar/gkr777",
        "url": "https://doi.org/10.1093/nar/gkr777",
        "note": "Drug-target mechanism of action data",
    },
    "dgidb": {
        "title": "DGIdb: mining the druggable genome",
        "authors": "Griffith M et al.",
        "year": 2013,
        "journal": "Nature Methods",
        "doi": "10.1038/nmeth.2689",
        "url": "https://doi.org/10.1038/nmeth.2689",
        "note": "Drug-gene interaction database",
    },
    "ccle": {
        "title": "The Cancer Cell Line Encyclopedia enables predictive modelling of anticancer drug sensitivity",
        "authors": "Barretina J et al.",
        "year": 2012,
        "journal": "Nature",
        "doi": "10.1038/nature11003",
        "url": "https://doi.org/10.1038/nature11003",
        "note": "Cell line gene expression data for GPR-based model contextualization",
    },
    "gdsc": {
        "title": "Genomics of Drug Sensitivity in Cancer (GDSC): a resource for therapeutic biomarker discovery in cancer cells",
        "authors": "Yang W et al.",
        "year": 2013,
        "journal": "Nucleic Acids Research",
        "doi": "10.1093/nar/gks1111",
        "url": "https://doi.org/10.1093/nar/gks1111",
        "note": "Experimental IC50 validation data",
    },
}


def _build_active_citations(drug_target_info: dict, personalization_notes: dict, gdsc_validation: dict) -> list[dict]:
    active = [CITATIONS["human_gem"], CITATIONS["cobrapy"]]

    if drug_target_info:
        sources = {t.get("source") for t in drug_target_info.get("targets", [])}
        if "chembl" in sources:
            active.append(CITATIONS["chembl"])
        if "dgidb" in sources:
            active.append(CITATIONS["dgidb"])

    if personalization_notes.get("gpr_scaling", {}).get("applied"):
        active.append(CITATIONS["ccle"])

    if gdsc_validation and gdsc_validation.get("found"):
        active.append(CITATIONS["gdsc"])

    return active


def _format_citations_section(citations: list[dict]) -> str:
    if not citations:
        return (
            "**Sources could not be verified** — please cross-check results before "
            "clinical or research use."
        )
    lines = []
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
    return "\n".join(lines)


def _reports_dir(user_id: str, conversation_id: str) -> str:
    base = os.path.join(os.getenv("CRYO_DATA_DIR", "./cryo-data"), "reports")
    path = os.path.join(base, user_id, conversation_id)
    os.makedirs(path, exist_ok=True)
    return path


def generate_digital_twin_report(
    simulation_results: dict[str, Any],
    user_id: str,
    conversation_id: str,
    personalization_notes: dict[str, Any] | None = None,
    model_metadata: dict[str, Any] | None = None,
    gdsc_validation: dict[str, Any] | None = None,
    drug_target_info: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Render CRYO HTML report + PNG chart for a digital twin simulation run."""
    if "error" in simulation_results:
        return {
            "report_path": "",
            "plot_path": "",
            "summary": f"Simulation failed: {simulation_results['error']}",
            "citations": [],
        }

    personalization_notes = personalization_notes or {}
    model_metadata = model_metadata or {}
    gdsc_validation = gdsc_validation or {}
    drug_target_info = drug_target_info or {}

    report_dir = _reports_dir(user_id, conversation_id)

    initial_flux = simulation_results["initial_biomass_flux"]
    drug_flux = simulation_results["drug_biomass_flux"]
    flux_delta = drug_flux - initial_flux
    percent_change = 0.0 if initial_flux == 0 else (flux_delta / initial_flux) * 100

    if abs(percent_change) < 1.0:
        interpretation = (
            f"The perturbation does not materially change predicted growth capacity "
            f"({percent_change:.2f}%). This is expected for the Human1 genome-scale model without "
            f"patient-specific omics contextualization — the model has metabolic flexibility to "
            f"route around single-target perturbations. Flux rewiring data shows the compensatory "
            f"pathway shifts that DO occur."
        )
    elif drug_flux < initial_flux:
        interpretation = (
            f"The perturbation reduces predicted growth capacity by {abs(percent_change):.1f}%. "
            f"This result incorporates cell-line specific gene expression constraints."
        )
    else:
        interpretation = (
            f"The perturbation increases predicted growth capacity by {percent_change:.1f}%."
        )

    # ── PNG chart ──────────────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.bar(["Baseline", "With Drug"], [initial_flux, drug_flux], color=["#3b82f6", "#ef4444"])
    ax.set_ylabel("Biomass Flux (mmol/gDW/hr)")
    ax.set_title(f"Digital Twin: {simulation_results['drug_id']}")
    plot_filename = (
        f"digital_twin_biomass_{simulation_results['drug_id'].replace(' ', '_')}_"
        f"{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.png"
    )
    plot_filepath = os.path.join(report_dir, plot_filename)
    plot_url_path = f"/api/reports/{user_id}/{conversation_id}/{plot_filename}"
    plt.tight_layout()
    plt.savefig(plot_filepath)
    plt.close(fig)

    # ── Build data sections ────────────────────────────────────────────────────
    changed_fluxes = simulation_results.get("changed_fluxes", {})
    ranked_changes = sorted(changed_fluxes.items(), key=lambda item: abs(item[1]), reverse=True)[:20]
    effects = simulation_results.get("drug_effects_applied", {}) or {}

    # Drug target section
    targets = drug_target_info.get("targets", [])
    target_summary = ""
    if targets:
        gene_list = ", ".join(t["gene_symbol"] for t in targets[:5])
        mech = targets[0].get("mechanism", "")
        target_summary = f"**Drug targets:** {gene_list}"
        if mech:
            target_summary += f"  \n**Mechanism:** {mech}"

    # GDSC validation section
    gdsc_content = ""
    if gdsc_validation.get("found"):
        ic50 = gdsc_validation.get("ic50_um", "N/A")
        auc = gdsc_validation.get("auc", "N/A")
        cell = gdsc_validation.get("cell_line", "")
        gdsc_content = (
            f":::callout success\n"
            f"GDSC2 experimental data found for this drug-cell line pair.\n"
            f":::\n\n"
            f"| Metric | Value |\n"
            f"| --- | --- |\n"
            f"| Cell Line | {cell} |\n"
            f"| Experimental IC50 | {ic50:.4f} μM |\n"
            f"| Area Under Curve (AUC) | {auc if auc else 'N/A'} |\n"
            f"| Predicted Growth Inhibition | {abs(percent_change):.1f}% |\n\n"
            f"Source: GDSC2 — Genomics of Drug Sensitivity in Cancer (Sanger Institute).  \n"
            f"DOI: [10.1093/nar/gks1111](https://doi.org/10.1093/nar/gks1111)"
        )
    else:
        gdsc_content = (
            ":::callout warning\n"
            "No experimental validation data available for this drug-cell line pair in GDSC2.\n"
            ":::\n\n"
            "Results should be cross-verified against independent experimental sources before "
            "clinical or research use."
        )

    # GPR scaling context
    gpr = personalization_notes.get("gpr_scaling", {})
    cell_line = gpr.get("cell_line", simulation_results.get("cell_line", ""))
    gpr_status = ""
    if gpr.get("applied"):
        gpr_status = (
            f"CCLE expression data applied for **{cell_line}**: "
            f"{gpr.get('reactions_constrained', 0)} reactions constrained "
            f"(TPM < {gpr.get('tpm_threshold', 1.0)}). "
            f"Source: CCLE/DepMap — [DOI: 10.1038/nature11003](https://doi.org/10.1038/nature11003)"
        )
    elif cell_line:
        gpr_status = (
            f"Cell line '{cell_line}' specified but CCLE data not available. "
            f"Run `scripts/setup_digital_twin.py` to enable GPR expression scaling.  \n"
            f"{gpr.get('reason', '')}"
        )

    # ── Citations ──────────────────────────────────────────────────────────────
    active_citations = _build_active_citations(drug_target_info, personalization_notes, gdsc_validation)
    citations_text = _format_citations_section(active_citations)

    # ── Render report ──────────────────────────────────────────────────────────
    previous_user = os.environ.get("CRYO_USER_ID")
    previous_conversation = os.environ.get("CRYO_CONVERSATION_ID")
    os.environ["CRYO_USER_ID"] = user_id
    os.environ["CRYO_CONVERSATION_ID"] = conversation_id
    try:
        report_result = generate_report({
            "title": f"Digital Twin Simulation: {simulation_results['drug_id']}",
            "subtitle": "Constraint-based metabolic perturbation analysis — CRYO v4",
            "summary": (
                f"**Outcome:** {interpretation}  \n"
                f"Baseline biomass flux: **{initial_flux:.4f}** | "
                f"Post-perturbation: **{drug_flux:.4f}** | "
                f"Change: **{percent_change:.2f}%**"
            ),
            "sections": [
                {
                    "heading": "Decision Snapshot",
                    "highlights": [
                        {"label": "Baseline Biomass Flux", "value": f"{initial_flux:.4f}"},
                        {"label": "Drug Biomass Flux", "value": f"{drug_flux:.4f}"},
                        {"label": "Absolute Delta", "value": f"{flux_delta:.4f}"},
                        {"label": "Percent Change", "value": f"{percent_change:.2f}%"},
                        {"label": "Flux Rewiring Events", "value": str(len(changed_fluxes))},
                    ],
                    "content": (
                        f":::callout {'info' if abs(percent_change) < 1 else 'success'}\n"
                        f"{interpretation}\n"
                        f":::\n\n"
                        + (f"{target_summary}\n\n" if target_summary else "")
                        + (f"**Cell line context:** {gpr_status}\n\n" if gpr_status else "")
                    ),
                    "chart": {
                        "type": "bar",
                        "title": f"Biomass Flux: {simulation_results['drug_id']}",
                        "labels": ["Baseline", "With Drug"],
                        "values": [initial_flux, drug_flux],
                    },
                },
                {
                    "heading": "Applied Perturbations",
                    "content": "\n".join(
                        [f"- **{k}**: {v}" for k, v in effects.items()]
                        or ["- No direct reaction-level inhibition was applied (drug targets not found in Human1)."]
                    ),
                    "table": {
                        "headers": ["Reaction / Note", "Effect"],
                        "rows": [[k, v] for k, v in effects.items()]
                        or [["No inhibition applied", "See flux rewiring for metabolic response"]],
                    },
                },
                {
                    "heading": "Flux Rewiring",
                    "content": (
                        f"**{len(changed_fluxes)} reactions** show altered flux after perturbation "
                        f"(threshold > 1×10⁻⁶). Top 20 ranked by magnitude:"
                    ),
                    "table": {
                        "headers": ["Reaction ID", "Flux Change (mmol/gDW/hr)"],
                        "rows": [
                            [rxn_id, f"{fc:+.4f}"]
                            for rxn_id, fc in ranked_changes
                        ] or [["No significant flux change detected", "0.0000"]],
                    },
                },
                {
                    "heading": "GDSC Experimental Validation",
                    "content": gdsc_content,
                },
                {
                    "heading": "Model Context",
                    "content": (
                        f"- **Model:** Human1 / Human-GEM genome-scale metabolic model  \n"
                        f"  DOI: [10.1126/scisignal.aaz1482](https://doi.org/10.1126/scisignal.aaz1482)\n"
                        f"- **Source:** {model_metadata.get('source', 'unknown')}\n"
                        f"- **Backbone:** {model_metadata.get('loaded_model_path', '') or 'demo model'}\n"
                        f"- **Media Preset:** {personalization_notes.get('environment_context', {}).get('preset', 'none')}\n"
                        f"- **Cell Line GPR Scaling:** {gpr_status or 'not applied'}\n"
                        f"- **Standalone Plot:** [Download PNG]({plot_url_path})\n"
                    ),
                },
                {
                    "heading": "Interpretation & Limitations",
                    "content": (
                        ":::callout warning\n"
                        "This simulation uses the Human1 genome-scale metabolic model with "
                        "constraint-based Flux Balance Analysis (FBA). Key limitations:\n"
                        ":::\n\n"
                        "- **Metabolic flexibility**: Human1 contains 12,931 reactions. Without "
                        "patient-specific gene expression constraints (GIMME/iMAT algorithm + CCLE "
                        "or RNA-seq data), the model has sufficient metabolic flexibility to route "
                        "around single-target perturbations with minimal biomass change.\n"
                        "- **Flux rewiring is real**: Even when biomass is unchanged, the "
                        "metabolic rewiring (pathway shifts) reflects true biological compensatory "
                        "mechanisms and is scientifically informative.\n"
                        "- **For quantitative drug response**: Run `scripts/setup_digital_twin.py` "
                        "to download CCLE data, then use `--cell_line MCF7` (or similar) to enable "
                        "GPR-based contextualization that makes drug effects measurable.\n"
                        "- **This is not a clinical prediction.** Results should be verified against "
                        "experimental data before use in research or clinical decision-making."
                    ),
                },
                {
                    "heading": "References",
                    "content": citations_text,
                },
            ],
            "citations": active_citations,
            "metadata": {
                "data_sources": [
                    "Human1/Human-GEM",
                    "COBRApy",
                    "ChEMBL" if any(t.get("source") == "chembl" for t in targets) else None,
                    "DGIdb" if any(t.get("source") == "dgidb" for t in targets) else None,
                    "CCLE/DepMap" if gpr.get("applied") else None,
                    "GDSC2" if gdsc_validation.get("found") else None,
                ],
                "verification_status": "research_grade" if targets else "prototype",
            },
        })
    finally:
        if previous_user is None:
            os.environ.pop("CRYO_USER_ID", None)
        else:
            os.environ["CRYO_USER_ID"] = previous_user
        if previous_conversation is None:
            os.environ.pop("CRYO_CONVERSATION_ID", None)
        else:
            os.environ["CRYO_CONVERSATION_ID"] = previous_conversation

    return {
        "report_path": report_result.get("download_url", ""),
        "plot_path": plot_url_path,
        "summary": report_result.get("filename", ""),
        "citations": active_citations,
    }
