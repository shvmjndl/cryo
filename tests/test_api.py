import httpx
import pytest
import os
import asyncio
import pytest_asyncio

BASE_URL = "http://cryo-api-1:8000/api"

@pytest.fixture(scope="module")
def anyio_backend():
    return "asyncio"

@pytest_asyncio.fixture(scope="module") # Use pytest_asyncio.fixture
async def client_fixture(): 
    async with httpx.AsyncClient(base_url=BASE_URL) as client_instance:
        yield client_instance

@pytest_asyncio.fixture(scope="module") # Use pytest_asyncio.fixture
async def authenticated_client_fixture(client_fixture): 
    # Test registration
    register_data = {
        "username": "testuser_digitaltwin",
        "email": "test_digitaltwin@example.com",
        "password": "testpassword"
    }
    response = await client_fixture.post("/auth/register", json=register_data)
    # Allow for existing user in case of repeated tests
    if response.status_code == 400 and "User already registered" in response.json().get("detail", ""):
        pass
    else:
        response.raise_for_status()
        assert response.status_code == 200
        assert "id" in response.json()

    # Test login
    login_data = {
        "username": "testuser_digitaltwin",
        "password": "testpassword"
    }
    response = await client_fixture.post("/auth/token", data=login_data)
    response.raise_for_status()
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "bearer"

    # Use the authenticated client for subsequent tests
    client_fixture.headers["Authorization"] = f"Bearer {response.json()['access_token']}"
    yield client_fixture

# --- Health Check ---

@pytest.mark.asyncio
async def test_health_check(client_fixture):
    response = await client_fixture.get("/health")
    response.raise_for_status()
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "cryo"}

# --- Auth Tests ---

@pytest.mark.asyncio
async def test_read_users_me(authenticated_client_fixture):
    response = await authenticated_client_fixture.get("/auth/users/me")
    response.raise_for_status()
    assert response.status_code == 200
    assert response.json()["username"] == "testuser_digitaltwin"

# --- Workspace Tests (Basic checks) ---

@pytest.mark.asyncio
async def test_list_workspaces(authenticated_client_fixture):
    response = await authenticated_client_fixture.get("/workspace/list")
    response.raise_for_status()
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    # Should at least have one default workspace
    assert len(response.json()) >= 1

# --- Digital Twin Tests ---

@pytest.mark.asyncio
async def test_digital_twin_simulate_drug_response(authenticated_client_fixture):
    user_id = "testuser_digitaltwin_id" # This would normally come from auth, but for now fixed
    conversation_id = "test_conversation_digitaltwin"

    # Test with a known inhibitor
    payload = {
        "user_id": user_id,
        "conversation_id": conversation_id,
        "drug_id": "glucose_inhibitor_X",
        "patient_omics_profile_path": None # Not used in current simple implementation
    }
    response = await authenticated_client_fixture.post("/digital_twin/simulate_drug_response", json=payload)
    response.raise_for_status()
    assert response.status_code == 200
    response_data = response.json()
    assert "report_path" in response_data
    assert "summary" in response_data
    assert "Digital Twin Simulation Report" in response_data["summary"]
    assert "Potential Toxicity / Inhibition Detected!" in response_data["summary"]

    # Test with a non-inhibitor (expect no significant change in simple model)
    payload_no_effect = {
        "user_id": user_id,
        "conversation_id": conversation_id,
        "drug_id": "harmless_drug_Y",
        "patient_omics_profile_path": None
    }
    response_no_effect = await authenticated_client_fixture.post("/digital_twin/simulate_drug_response", json=payload_no_effect)
    response_no_effect.raise_for_status()
    assert response_no_effect.status_code == 200
    response_data_no_effect = response_no_effect.json()
    assert "report_path" in response_data_no_effect
    assert "summary" in response_data_no_effect
    assert "No Significant Change in Biomass Flux." in response_data_no_effect["summary"]

# --- Chat Tests (Placeholder - more detailed tests would be complex) ---
@pytest.mark.asyncio
async def test_chat_stream(authenticated_client_fixture):
    user_id = "testuser_digitaltwin_id"
    conversation_id = "test_conversation_chat"

    # Simplified test: just ensure the endpoint responds without error for a basic message
    payload = {
        "user_id": user_id,
        "conversation_id": conversation_id,
        "message": "Hello, CRYO!"
    }
    # This endpoint is streaming, so we just check the initial response header/status
    # A full test would involve consuming the SSE stream.
    response = await authenticated_client_fixture.post("/chat/stream", json=payload, timeout=5)
    response.raise_for_status()
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
