"""Backward-compatible import shim for the digital twin service package."""

from api.services.digital_twin import DigitalTwinService, digital_twin_service

__all__ = ["DigitalTwinService", "digital_twin_service"]
