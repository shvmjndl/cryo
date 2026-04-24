from __future__ import annotations

import os
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

from api.services.report_engine import generate_report


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
) -> dict[str, str]:
    """Render a CRYO HTML report plus a standalone PNG chart for digital twin runs."""
    if "error" in simulation_results:
        return {
            "report_path": "",
            "plot_path": "",
            "summary": f"Simulation failed: {simulation_results['error']}",
        }

    personalization_notes = personalization_notes or {}
    model_metadata = model_metadata or {}

    report_dir = _reports_dir(user_id, conversation_id)

    initial_flux = simulation_results["initial_biomass_flux"]
    drug_flux = simulation_results["drug_biomass_flux"]
    flux_delta = drug_flux - initial_flux
    percent_change = 0.0 if initial_flux == 0 else (flux_delta / initial_flux) * 100

    if drug_flux < initial_flux:
        interpretation = "The perturbation reduces predicted growth capacity in this model."
    elif drug_flux > initial_flux:
        interpretation = "The perturbation increases predicted growth capacity in this model."
    else:
        interpretation = "The perturbation does not materially change predicted growth capacity in this model."

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.bar(["Initial", "With Drug"], [initial_flux, drug_flux], color=["#3b82f6", "#ef4444"])
    ax.set_ylabel("Biomass Flux")
    ax.set_title(f"Biomass Flux for {simulation_results['drug_id']}")
    plot_filename = (
        f"digital_twin_biomass_plot_{simulation_results['drug_id'].replace(' ', '_')}_"
        f"{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.png"
    )
    plot_filepath = os.path.join(report_dir, plot_filename)
    plot_url_path = f"/api/reports/{user_id}/{conversation_id}/{plot_filename}"
    plt.savefig(plot_filepath)
    plt.close(fig)

    changed_fluxes = simulation_results.get("changed_fluxes", {})
    ranked_changes = sorted(changed_fluxes.items(), key=lambda item: abs(item[1]), reverse=True)
    effects = simulation_results.get("drug_effects_applied", {}) or {}

    previous_user = os.environ.get("CRYO_USER_ID")
    previous_conversation = os.environ.get("CRYO_CONVERSATION_ID")
    os.environ["CRYO_USER_ID"] = user_id
    os.environ["CRYO_CONVERSATION_ID"] = conversation_id
    try:
        report_result = generate_report({
            "title": f"Digital Twin Simulation: {simulation_results['drug_id']}",
            "subtitle": "Constraint-based perturbation analysis rendered with the CRYO v4 report engine.",
            "summary": (
                f"**Outcome:** {interpretation} Baseline biomass flux is **{initial_flux:.4f}** and "
                f"post-perturbation biomass flux is **{drug_flux:.4f}**, corresponding to a "
                f"**{percent_change:.2f}%** change."
            ),
            "sections": [
                {
                    "heading": "Decision Snapshot",
                    "highlights": [
                        {"label": "Initial Biomass", "value": f"{initial_flux:.2f}"},
                        {"label": "Drug Biomass", "value": f"{drug_flux:.2f}"},
                        {"label": "Absolute Delta", "value": f"{flux_delta:.2f}"},
                        {"label": "Percent Change", "value": f"{percent_change:.1f}%"},
                    ],
                    "content": (
                        ":::callout info\n"
                        f"{interpretation}\n"
                        ":::\n\n"
                        "This result comes from CRYO's current metabolic modeling pipeline and is best used "
                        "for product validation, regression testing, and directional analysis."
                    ),
                    "chart": {
                        "type": "bar",
                        "title": f"Biomass Flux Response: {simulation_results['drug_id']}",
                        "labels": ["Initial", "With Drug"],
                        "values": [initial_flux, drug_flux],
                    },
                },
                {
                    "heading": "Applied Perturbations",
                    "content": "\n".join(
                        [f"- **{reaction_id}**: {effect}" for reaction_id, effect in effects.items()]
                        or ["- No explicit reaction-level inhibition was applied."]
                    ),
                    "table": {
                        "headers": ["Reaction", "Effect"],
                        "rows": [[reaction_id, effect] for reaction_id, effect in effects.items()]
                        or [["None", "No explicit inhibition applied"]],
                    },
                },
                {
                    "heading": "Flux Rewiring",
                    "content": (
                        "The ranked table below shows the strongest flux deltas induced by the requested "
                        "perturbation. Negative values indicate suppression relative to baseline."
                    ),
                    "table": {
                        "headers": ["Reaction", "Flux Change"],
                        "rows": [
                            [reaction_id, f"{flux_change:.4f}"]
                            for reaction_id, flux_change in ranked_changes
                        ] or [["No significant change detected", "0.0000"]],
                    },
                },
                {
                    "heading": "Model Context",
                    "content": (
                        f"- **Model Source:** {model_metadata.get('source', 'unknown')}\n"
                        f"- **Configured Backbone Path:** {model_metadata.get('configured_model_path', '') or 'not set'}\n"
                        f"- **Loaded Backbone Path:** {model_metadata.get('loaded_model_path', '') or 'demo model'}\n"
                        f"- **Personalization Applied:** {personalization_notes.get('personalization_applied', False)}\n"
                        f"- **Environment Preset:** {personalization_notes.get('environment_context', {}).get('preset', '') or 'none'}\n"
                        f"- **Omics Input Path:** {personalization_notes.get('omics_summary', {}).get('path', '') or 'none'}"
                    ),
                },
                {
                    "heading": "Artifacts and Limitations",
                    "content": (
                        f"- **Standalone Biomass Plot:** [Download PNG]({plot_url_path})\n"
                        "- This is not yet a patient-calibrated whole-cell digital twin.\n"
                        "- `patient_omics_profile_path` is ingested but not yet used to modify reaction bounds.\n"
                        "- The result should be treated as a mechanistic prototype output, not a clinical prediction."
                    ),
                },
            ],
            "citations": [],
            "metadata": {
                "data_sources": ["COBRApy", "CRYO Digital Twin Model"],
                "verification_status": "prototype",
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
    }
