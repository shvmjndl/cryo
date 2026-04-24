from fastapi import APIRouter, HTTPException
from typing import Optional

from pydantic import BaseModel

from api.services.digital_twin_service import digital_twin_service

router = APIRouter(prefix="/digital_twin", tags=["digital_twin"])

class DigitalTwinSimulateRequest(BaseModel):
    user_id: str
    conversation_id: str
    drug_id: str
    patient_omics_profile_path: Optional[str] = None

@router.post("/simulate_drug_response")
async def simulate_drug_response_endpoint(request: DigitalTwinSimulateRequest):
    """
    API endpoint to simulate drug response using the digital twin service.
    """
    try:
        simulation_output = digital_twin_service.simulate_drug_response(
            user_id=request.user_id,
            conversation_id=request.conversation_id,
            drug_id=request.drug_id,
            patient_omics_profile_path=request.patient_omics_profile_path,
        )

        if "error" in simulation_output:
            raise HTTPException(status_code=500, detail=simulation_output["error"])

        return {
            "message": "Digital twin simulation initiated successfully",
            "report_path": simulation_output["report_path"],
            "plot_path": simulation_output["plot_path"],
            "summary": simulation_output["summary"],
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Internal server error: {exc}")
