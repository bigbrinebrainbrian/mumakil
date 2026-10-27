"""AI Reasoning Evaluator for Mumakil 2.0.

Replaces legacy analyze.php.
Uses Google Gemini API with Native Structured Outputs (response_mime_type='application/json'
and response_schema), completely eliminating regex fallback (preg_match('/\\{.*\\}/s')).
Guarantees 100% Pydantic schema validation.
"""

from datetime import datetime
import json
import logging
from typing import Any, Dict, Optional
import httpx

from mumakil_core.config import Settings, get_settings
from mumakil_core.models.schemas import (
    ACPayload,
    AIEvaluationResponse,
    EngineResult,
    FindingItem,
    TargetApiResponse,
)

logger = logging.getLogger("mumakil.ai_evaluator")


# Canonical JSON Schema for Google Gemini responseSchema
GEMINI_RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "success": {"type": "BOOLEAN"},
        "findings": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "rule": {"type": "STRING"},
                    "result": {"type": "STRING"},
                    "details": {"type": "STRING"},
                },
                "required": ["rule", "result", "details"],
            },
        },
        "severity": {
            "type": "STRING",
            "enum": ["low", "medium", "high"],
        },
        "risk_tags": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
        },
        "reason": {"type": "STRING"},
    },
    "required": ["success", "findings", "severity", "risk_tags", "reason"],
}


SYSTEM_PROMPT = """You are Mumakil 2.0 Autonomous AI reasoning module (modern successor to ACES).
Your task is to analyze deterministic QA results along with the target API response and produce
STRICT structured evaluations matching the requested schema.

Key Evaluation Rules:
- Findings must evaluate each significant rule check (status code, payload integrity, schema compliance).
- If dataset/table is empty: reason must state "Table returned 0 rows. Expected non-empty dataset based on AC rule."
- For DELETE actions:
    * 200 + success:true -> "Delete succeeded"
    * 404 -> "Record not found (expected negative for AC07)"
    * 401 -> "Unauthorized" (expected for AC08/AC21 when token invalid/missing)
- For UPDATE actions:
    * 200 + success:true -> "Update successful"
    * 404 -> "Update target not found (expected in AC09 negative case)"
    * 400 -> "Validation error (expected for AC10 when validation triggered)"
- For TOKEN / SECURITY actions (AC21, AC08):
    * 401 -> "Unauthorized access blocked correctly by API security policy"
    * 200 -> "Authorized access confirmed"
- Assign severity ("low", "medium", or "high") reflecting system impact.
- Provide domain risk tags such as "auth_validation", "empty_result", "data_integrity", "contract_ok".
"""


class AIReasoningEvaluator:
    """Async AI Reasoning Evaluator powered by Google Gemini Structured Outputs."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        custom_client: Optional[httpx.AsyncClient] = None,
    ):
        self.settings = settings or get_settings()
        self._client = custom_client or httpx.AsyncClient(
            timeout=httpx.Timeout(self.settings.ai_timeout_seconds)
        )
        self._owns_client = custom_client is None
        self._gemini_key_valid: Optional[bool] = None

    async def probe_key(self) -> bool:
        """Pre-flight check to verify Gemini API Key validity once."""
        if self._gemini_key_valid is not None:
            return self._gemini_key_valid
        api_key = self.settings.gemini_api_key
        if not api_key:
            self._gemini_key_valid = False
            return False
        url = f"{self.settings.gemini_base_url}/{self.settings.gemini_model}:generateContent?key={api_key}"
        try:
            resp = await self._client.post(
                url,
                json={"contents": [{"parts": [{"text": "ping"}]}]},
                timeout=1.0,
            )
            self._gemini_key_valid = (resp.status_code == 200)
            if not self._gemini_key_valid:
                logger.info("Gemini API key inactive/invalid (HTTP %d). Local AI reasoning activated.", resp.status_code)
        except Exception:
            self._gemini_key_valid = False
        return self._gemini_key_valid

    async def close(self) -> None:
        """Close HTTP client connection."""
        if self._owns_client and not self._client.is_closed:
            await self._client.aclose()

    async def __aenter__(self) -> "AIReasoningEvaluator":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    def build_prompt_context(
        self,
        payload: ACPayload,
        engine_result: EngineResult,
        target_response: TargetApiResponse,
    ) -> str:
        """Construct deterministic context for Gemini reasoning."""
        context = {
            "ac_id": payload.ac_id,
            "action": payload.get_effective_action(),
            "deterministic_result": {
                "status": engine_result.status,
                "return_code": engine_result.return_code,
                "reason": engine_result.reason,
                "risk": engine_result.risk,
            },
            "api_response": {
                "status_code": target_response.status_code,
                "success": target_response.success,
                "data": target_response.data,
                "error": target_response.error,
            },
            "automation_status": payload.automation_status,
        }
        return f"{SYSTEM_PROMPT}\n\nINPUT DATA:\n{json.dumps(context, indent=2, ensure_ascii=False)}"

    async def evaluate(
        self,
        payload: ACPayload,
        engine_result: EngineResult,
        target_response: TargetApiResponse,
        mock_mode: bool = False,
    ) -> AIEvaluationResponse:
        """Execute AI reasoning with Gemini Native Structured Output, falling back safely."""
        api_key = self.settings.gemini_api_key

        # If mock mode is explicitly requested, API key is absent, or key was identified invalid
        if mock_mode or not api_key or self._gemini_key_valid is False:
            return self._generate_fallback_reasoning(payload, engine_result, target_response)

        prompt_text = self.build_prompt_context(payload, engine_result, target_response)

        # Gemini REST request with native JSON schema enforcement
        url = f"{self.settings.gemini_base_url}/{self.settings.gemini_model}:generateContent?key={api_key}"
        request_body = {
            "contents": [
                {
                    "parts": [{"text": prompt_text}]
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": GEMINI_RESPONSE_SCHEMA,
                "temperature": 0.2,
            },
        }

        try:
            resp = await self._client.post(url, json=request_body)
            if resp.status_code != 200:
                if resp.status_code in (400, 401, 403):
                    self._gemini_key_valid = False
                logger.warning(
                    "Gemini API returned status %d. Using local AI reasoning engine.",
                    resp.status_code,
                )
                return self._generate_fallback_reasoning(payload, engine_result, target_response)

            self._gemini_key_valid = True

            resp_data = resp.json()
            candidates = resp_data.get("candidates", [])
            if not candidates:
                logger.warning("Gemini returned empty candidates. Using local AI reasoning engine.")
                return self._generate_fallback_reasoning(payload, engine_result, target_response)

            parts = candidates[0].get("content", {}).get("parts", [])
            if not parts or "text" not in parts[0]:
                logger.warning("Gemini response missing text part. Using local AI reasoning engine.")
                return self._generate_fallback_reasoning(payload, engine_result, target_response)

            raw_json_text = parts[0]["text"]

            # Parse directly into Pydantic model - ZERO regex needed!
            ai_model = AIEvaluationResponse.model_validate_json(raw_json_text)
            return ai_model

        except (httpx.RequestError, json.JSONDecodeError, Exception) as err:
            logger.warning("Error invoking Gemini API (%s), falling back to local reasoning.", err)
            return self._generate_fallback_reasoning(payload, engine_result, target_response)

    def _generate_fallback_reasoning(
        self,
        payload: ACPayload,
        engine_result: EngineResult,
        target_response: TargetApiResponse,
    ) -> AIEvaluationResponse:
        """Deterministic local AI reasoning emulator satisfying all AC domain rules.

        Matches exact specifications from legacy analyze.php and AC01-AC21 rules.
        """
        ac_id = payload.ac_id.upper()
        status_code = target_response.status_code
        action = payload.get_effective_action()

        findings = [
            FindingItem(
                rule="HTTP Response Status",
                result="pass" if engine_result.status == "PASSED" else "fail",
                details=f"Received status {status_code}, expected contract conformity for {ac_id}.",
            ),
            FindingItem(
                rule="Data Integrity Check",
                result="pass" if engine_result.risk < 50 else "fail",
                details=f"Deterministic risk assessed at {engine_result.risk}/100.",
            ),
        ]

        # AC21 / AC08: Token Security
        if ac_id in ("AC21", "AC08", "AC8"):
            if status_code == 401 or payload.automation_status == 401:
                return AIEvaluationResponse(
                    success=True,
                    findings=findings,
                    severity="low",
                    risk_tags=["security", "auth_blocked", "token_validation"],
                    reason="Unauthorized access correctly blocked by API security policy.",
                )
            elif status_code == 200:
                return AIEvaluationResponse(
                    success=True,
                    findings=findings,
                    severity="low",
                    risk_tags=["security", "authorized", "token_valid"],
                    reason="Authorized request succeeded with valid credentials.",
                )

        # DELETE actions (AC07)
        if "delete" in action.lower() or ac_id in ("AC07", "AC7"):
            if status_code == 200:
                reason = "Delete succeeded"
                severity = "low"
                tags = ["delete_success", "db_cleanup"]
            elif status_code == 404:
                reason = "Record not found (expected negative for AC07)"
                severity = "low"
                tags = ["delete_not_found", "negative_test_pass"]
            elif status_code == 401:
                reason = "Unauthorized (expected for AC08 when token missing)"
                severity = "low"
                tags = ["auth_required"]
            else:
                reason = f"Unexpected delete failure with status {status_code}"
                severity = "high"
                tags = ["delete_failure"]

            return AIEvaluationResponse(
                success=engine_result.status == "PASSED",
                findings=findings,
                severity=severity,
                risk_tags=tags,
                reason=reason,
            )

        # UPDATE actions (AC09, AC10)
        if "update" in action.lower() or ac_id in ("AC09", "AC10"):
            if status_code == 200:
                reason = "Update successful"
                severity = "low"
                tags = ["update_success"]
            elif status_code == 404:
                reason = "Update target not found (expected in AC09 negative case)"
                severity = "low"
                tags = ["update_target_missing"]
            elif status_code == 400:
                reason = "Validation error (expected for AC10 when validation=ON)"
                severity = "low"
                tags = ["validation_triggered"]
            else:
                reason = f"Update action failed unexpectedly (HTTP {status_code})"
                severity = "medium"
                tags = ["update_failure"]

            return AIEvaluationResponse(
                success=engine_result.status == "PASSED",
                findings=findings,
                severity=severity,
                risk_tags=tags,
                reason=reason,
            )

        # GET View checks (AC01, AC02)
        if "get" in action.lower() or ac_id in ("AC01", "AC02"):
            if status_code == 404:
                return AIEvaluationResponse(
                    success=True,
                    findings=findings,
                    severity="low",
                    risk_tags=["endpoint_not_found", "negative_test"],
                    reason="Endpoint not found or filter returned 0 records (expected negative test).",
                )
            if status_code == 200:
                if not target_response.data or len(target_response.data) == 0:
                    return AIEvaluationResponse(
                        success=False,
                        findings=findings,
                        severity="high",
                        risk_tags=["empty_dataset", "schema_violation"],
                        reason="Table returned 0 rows. Expected non-empty dataset based on AC rule.",
                    )
                return AIEvaluationResponse(
                    success=True,
                    findings=findings,
                    severity="low",
                    risk_tags=["view_ok", "data_loaded"],
                    reason=f"Dataset retrieved successfully for {action}.",
                )

        # INSERT operations (AC03, AC04, AC12)
        if "insert" in action.lower() or ac_id in ("AC03", "AC04", "AC12"):
            if status_code in (200, 201):
                return AIEvaluationResponse(
                    success=True,
                    findings=findings,
                    severity="low",
                    risk_tags=["insert_success", "db_write"],
                    reason="Entity inserted successfully.",
                )
            elif status_code == 404:
                return AIEvaluationResponse(
                    success=True,
                    findings=findings,
                    severity="low",
                    risk_tags=["insert_table_missing", "negative_test"],
                    reason="Target table not found for insert operation.",
                )

        return AIEvaluationResponse(
            success=engine_result.status == "PASSED",
            findings=findings,
            severity="low" if engine_result.risk == 0 else "medium",
            risk_tags=["qc_evaluation", "contract_test"],
            reason=engine_result.reason,
        )


_global_evaluator: Optional[AIReasoningEvaluator] = None


def get_ai_evaluator() -> AIReasoningEvaluator:
    """Singleton getter for AIReasoningEvaluator."""
    global _global_evaluator
    if _global_evaluator is None:
        _global_evaluator = AIReasoningEvaluator()
    return _global_evaluator
