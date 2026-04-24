import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.services.digital_twin_service import digital_twin_service


def test_simulate_drug_response_generates_html_report_and_plot():
    result = digital_twin_service.simulate_drug_response(
        user_id="test-user",
        conversation_id="test-conversation",
        drug_id="glucose_inhibitor",
    )

    assert "error" not in result
    assert result["report_path"].endswith(".html")
    assert result["plot_path"].endswith(".png")
    assert result["drug_effects_applied"]
    assert "environment_context" in result["personalization_notes"]


def test_load_omics_payload_missing_file_is_nonfatal():
    result = digital_twin_service.simulate_drug_response(
        user_id="test-user",
        conversation_id="test-conversation",
        drug_id="placebo",
        patient_omics_profile_path="/tmp/does-not-exist-omics.json",
    )

    assert "error" not in result
    assert result["personalization_notes"]["omics_summary"]["error"] == "Omics file not found"
