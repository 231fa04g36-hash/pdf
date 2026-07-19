from fastapi import APIRouter
from app.services.health import health_service
from app.schemas.envelope import ResponseEnvelope
from app.schemas.health import HealthData
from app.schemas.test_schema import TestSchema

router = APIRouter(tags=["Health"])

@router.get("/health", response_model=ResponseEnvelope[HealthData])
def get_health() -> ResponseEnvelope[HealthData]:
    """
    Check the health of the API server and its upstream dependencies.
    """
    health_info = health_service.check_health()
    return ResponseEnvelope(
        success=True,
        message="System health status retrieved successfully",
        data=HealthData(**health_info)
    )

@router.get("/test-serialization", response_model=ResponseEnvelope[TestSchema])
def test_serialization() -> ResponseEnvelope[TestSchema]:
    """
    Diagnostic endpoint to prove camelCase serialization works correctly.
    """
    test_data = {
        "document_id": "doc_12345",
        "page_count": 12,
        "ocr_triggered": True,
        "user_friendly_name": "Test PDF Document"
    }
    # Pass as snake_case kwargs, Pydantic should serialize to camelCase keys
    return ResponseEnvelope(
        success=True,
        message="Serialization test passed",
        data=TestSchema(**test_data)
    )

