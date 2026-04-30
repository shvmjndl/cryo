from fastapi import APIRouter, HTTPException
from typing import Optional

from pydantic import BaseModel

from api.services.digital_twin_service import digital_twin_service

router = APIRouter(prefix="/digital_twin", tags=["digital_twin"])


class DigitalTwinSimulateRequest(BaseModel):
    user_id: str
    conversation_id: str
    drug_id: str
    cell_line: Optional[str] = None
    backbone: Optional[str] = None
    patient_omics_profile_path: Optional[str] = None


@router.post("/simulate_drug_response")
async def simulate_drug_response_endpoint(request: DigitalTwinSimulateRequest):
    """Simulate drug response using the digital twin service."""
    try:
        simulation_output = digital_twin_service.simulate_drug_response(
            user_id=request.user_id,
            conversation_id=request.conversation_id,
            drug_id=request.drug_id,
            cell_line=request.cell_line or "",
            backbone=request.backbone or "",
            patient_omics_profile_path=request.patient_omics_profile_path,
        )

        if "error" in simulation_output:
            raise HTTPException(status_code=500, detail=simulation_output["error"])

        return {
            "message": "Digital twin simulation completed",
            "report_path": simulation_output["report_path"],
            "plot_path": simulation_output["plot_path"],
            "summary": simulation_output["summary"],
            "citations": simulation_output.get("citations", []),
            "backbone": simulation_output.get("backbone", ""),
            "organism": simulation_output.get("organism", ""),
            "organism_display": simulation_output.get("organism_display", ""),
            "biomass_change_percent": simulation_output.get("biomass_change_percent"),
            "drug_target_info": simulation_output.get("drug_target_info", {}),
            "gdsc_validation": simulation_output.get("gdsc_validation", {}),
            "personalization_notes": simulation_output.get("personalization_notes", {}),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Internal server error: {exc}")
