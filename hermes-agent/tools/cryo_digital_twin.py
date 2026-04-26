import json
import os

import requests

from tools.registry import registry


def _digital_twin(args: dict, **_kw) -> str:
    action = args.get("action")
    drug_id = args.get("drug_id")
    cell_line = args.get("cell_line", "")
    tissue = args.get("tissue", "")
    patient_omics_profile_path = args.get("patient_omics_profile_path")

    api_base_url = os.getenv("CRYO_API_URL", "http://localhost:8000")
    cryo_user_id = os.getenv("CRYO_USER_ID", "default_user")
    cryo_conversation_id = os.getenv("CRYO_CONVERSATION_ID", "default_conversation")

    if action != "simulate_drug_response":
        return json.dumps({"error": f"Unknown action: {action}"})

    if not drug_id:
        return json.dumps({"error": "drug_id is required for simulate_drug_response action."})

    payload = {
        "user_id": cryo_user_id,
        "conversation_id": cryo_conversation_id,
        "drug_id": drug_id,
        "cell_line": cell_line or tissue or None,
        "patient_omics_profile_path": patient_omics_profile_path,
    }

    try:
        response = requests.post(
            f"{api_base_url}/api/digital_twin/simulate_drug_response",
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        return json.dumps(response.json())
    except requests.exceptions.RequestException as e:
        return json.dumps({"error": f"API request failed: {e}"})


DIGITAL_TWIN_SCHEMA = {
    "name": "digital_twin",
    "description": (
        "Run an in silico digital twin simulation of drug response using the CRYO metabolic "
        "modeling service (Human-GEM genome-scale model + COBRApy FBA). Returns flux changes, "
        "biomass impact, drug targets from ChEMBL/DGIdb, optional GDSC2 experimental IC50, "
        "and mandatory citations. Supports cancer cell line contextualization via CCLE expression data."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["simulate_drug_response"],
                "description": "The digital twin action to perform.",
            },
            "drug_id": {
                "type": "string",
                "description": (
                    "Drug name or identifier (e.g. 'imatinib', 'temozolomide', 'metformin'). "
                    "Also accepts special keywords: 'glucose_inhibitor', 'atp_synthase_inhibitor'. "
                    "Drug targets are resolved via ChEMBL REST API and DGIdb."
                ),
            },
            "cell_line": {
                "type": "string",
                "description": (
                    "Cancer cell line identifier for CCLE-based personalization (e.g. 'MCF7', "
                    "'HeLa', 'A549', 'HCT116', 'PC-3', 'LNCaP', 'U87', 'HepG2', 'K562'). "
                    "When provided, applies GPR-based expression scaling from CCLE data and "
                    "uses the cancer Warburg media preset. Also enables GDSC2 IC50 lookup."
                ),
            },
            "tissue": {
                "type": "string",
                "description": (
                    "Tissue type or cancer type context (e.g. 'breast', 'lung', 'glioblastoma'). "
                    "Used when no specific cell line is known. Informational only."
                ),
            },
            "patient_omics_profile_path": {
                "type": "string",
                "description": "Optional path to a patient omics profile JSON/CSV file for model personalization.",
            },
        },
        "required": ["action", "drug_id"],
    },
}

registry.register(
    name="digital_twin",
    toolset="cryo_digital_twin",
    schema=DIGITAL_TWIN_SCHEMA,
    handler=_digital_twin,
    check_fn=lambda: True,
    emoji="🧪",
)
