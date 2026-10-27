"""Tests for AI Reasoning Evaluator and Structured Outputs."""

import json
import pytest
import httpx
from mumakil_core.ai.evaluator import AIReasoningEvaluator, GEMINI_RESPONSE_SCHEMA
from mumakil_core.models.schemas import (
    ACPayload,
    AIEvaluationResponse,
    EngineResult,
    TargetApiResponse,
)


@pytest.mark.asyncio
async def test_ai_evaluator_structured_output_parsing():
    """Verify Gemini AI structured outputs parse into Pydantic models with 0 regex."""
    evaluator = AIReasoningEvaluator()

    mock_gemini_json = json.dumps({
        "success": True,
        "findings": [
            {
                "rule": "AC01 Projection Rule",
                "result": "pass",
                "details": "Table returned all expected columns."
            }
        ],
        "severity": "low",
        "risk_tags": ["contract_ok", "full_projection"],
        "reason": "Dataset retrieved successfully for GetMS_BANK."
    })

    # Validate that model_validate_json accepts the structured output perfectly
    parsed = AIEvaluationResponse.model_validate_json(mock_gemini_json)
    assert parsed.success is True
    assert len(parsed.findings) == 1
    assert parsed.findings[0].rule == "AC01 Projection Rule"
    assert parsed.findings[0].result == "pass"
    assert parsed.severity == "low"
    assert "contract_ok" in parsed.risk_tags
    assert parsed.reason == "Dataset retrieved successfully for GetMS_BANK."


@pytest.mark.asyncio
async def test_ai_evaluator_fallback_graceful_handling():
    """Verify evaluator provides fully-structured reasoning when Gemini is offline."""
    evaluator = AIReasoningEvaluator()

    payload = ACPayload(ac_id="AC01", action="GetMS_BANK")
    engine_result = EngineResult(status="PASSED", return_code=200, reason="OK", risk=0)
    target_resp = TargetApiResponse(
        status_code=200,
        success=True,
        data=[{"KDBANK": "ABALIDBS"}],
        raw={"success": True},
    )

    # Force mock/fallback mode
    ai_resp = await evaluator.evaluate(
        payload=payload,
        engine_result=engine_result,
        target_response=target_resp,
        mock_mode=True,
    )

    assert isinstance(ai_resp, AIEvaluationResponse)
    assert ai_resp.success is True
    assert ai_resp.severity == "low"
    assert len(ai_resp.findings) >= 2
    assert "view_ok" in ai_resp.risk_tags
    assert "Dataset retrieved successfully" in ai_resp.reason
