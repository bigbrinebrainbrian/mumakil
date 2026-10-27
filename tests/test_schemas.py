"""Unit tests for Pydantic v2 schemas and Gemini Structured Output validation."""

import json
import pytest
from pydantic import ValidationError

from mumakil_core.models.schemas import (
    ACPayload,
    AIEvaluationResponse,
    CombinedEvaluationResult,
    EngineResult,
    EvaluateRequest,
    FindingItem,
    TargetApiResponse,
)
from mumakil_core.ai.evaluator import GEMINI_RESPONSE_SCHEMA


def test_ac_payload_legacy_normalization():
    """Verify legacy Postman 'request' key is normalized into 'params'."""
    raw = {
        "ac_id": "AC01",
        "request": {
            "action": "GetMS_BANK",
            "filter_id": 42
        }
    }
    payload = ACPayload.model_validate(raw)
    assert payload.ac_id == "AC01"
    assert payload.action == "GetMS_BANK"
    assert payload.params["action"] == "GetMS_BANK"
    assert payload.params["filter_id"] == 42
    assert payload.get_effective_action() == "GetMS_BANK"


def test_ac_payload_get_merged_call_params():
    """Verify parameters, filter, and data merge cleanly with default token."""
    payload = ACPayload(
        ac_id="AC03",
        action="InsertMS_KARYAWAN",
        params={"category": "HR"},
        data={"nip": "123456", "nama": "Budi"},
    )
    merged = payload.get_merged_call_params(default_token="DEFAULT_QC_TOKEN")
    assert merged["action"] == "InsertMS_KARYAWAN"
    assert merged["category"] == "HR"
    assert merged["nip"] == "123456"
    assert merged["nama"] == "Budi"
    assert merged["token"] == "DEFAULT_QC_TOKEN"


def test_gemini_structured_output_schema_valid():
    """Verify that Gemini Structured Output schema enforces required fields and types."""
    assert GEMINI_RESPONSE_SCHEMA["type"] == "OBJECT"
    required = GEMINI_RESPONSE_SCHEMA["required"]
    for field in ["success", "findings", "severity", "risk_tags", "reason"]:
        assert field in required


def test_gemini_structured_output_validation_success():
    """Verify valid Gemini AI response JSON parses 100% cleanly without regex."""
    sample_json = json.dumps({
        "success": True,
        "findings": [
            {
                "rule": "HTTP Status Check",
                "result": "pass",
                "details": "Status code 200 returned valid dataset."
            }
        ],
        "severity": "low",
        "risk_tags": ["view_ok", "data_loaded"],
        "reason": "Dataset retrieved successfully for GetMS_BANK."
    })

    # Direct validation via Pydantic model_validate_json
    ai_response = AIEvaluationResponse.model_validate_json(sample_json)
    assert ai_response.success is True
    assert len(ai_response.findings) == 1
    assert ai_response.findings[0].rule == "HTTP Status Check"
    assert ai_response.findings[0].result == "pass"
    assert ai_response.severity == "low"
    assert "view_ok" in ai_response.risk_tags
    assert ai_response.reason == "Dataset retrieved successfully for GetMS_BANK."


def test_gemini_structured_output_validation_rejects_invalid_severity():
    """Verify Pydantic rejects invalid severity outside low/medium/high."""
    invalid_json = json.dumps({
        "success": True,
        "findings": [],
        "severity": "critical_extreme",  # Invalid enum
        "risk_tags": [],
        "reason": "Some reason"
    })
    with pytest.raises(ValidationError):
        AIEvaluationResponse.model_validate_json(invalid_json)


def test_engine_result_serialization():
    """Verify EngineResult serializes return code as 'return' for PHP compatibility."""
    result = EngineResult(
        status="PASSED",
        return_code=200,
        reason="OK",
        risk=0,
    )
    dumped = result.model_dump(by_alias=True)
    assert dumped["status"] == "PASSED"
    assert dumped["return"] == 200
    assert dumped["reason"] == "OK"
    assert dumped["risk"] == 0
