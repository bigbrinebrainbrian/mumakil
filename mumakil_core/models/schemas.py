"""Pydantic v2 schemas for request validation, API responses, and AI structured output.

Ensures end-to-end type safety, normalization between legacy Postman payload formats
and modern async models, and schema validation for Google Gemini structured outputs.
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, ConfigDict, Field, model_validator


# ==============================================================================
# Request Models
# ==============================================================================

class ACPayload(BaseModel):
    """Payload representing a single Acceptance Criteria test invocation."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    ac_id: str = Field(description="Acceptance Criteria Identifier, e.g. AC01, AC02")
    action: Optional[str] = Field(default=None, description="Action to call on target backend")
    params: Dict[str, Any] = Field(default_factory=dict, description="Parameters for the action")
    request: Optional[Dict[str, Any]] = Field(
        default=None, description="Legacy alias for params from Postman collection"
    )
    filter: Optional[Dict[str, Any]] = Field(default=None, description="Filter parameters for queries")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Entity data for Insert/Update")
    token: Optional[str] = Field(default=None, description="Auth token passed for QC evaluation")
    automation_status: int = Field(default=200, description="Automation caller status code (200 or 401)")

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_fields(cls, data: Any) -> Any:
        """Harmonize legacy 'request' key to 'params' and resolve action hierarchy."""
        if not isinstance(data, dict):
            return data

        d = dict(data)
        # 1. Normalize 'request' -> 'params'
        legacy_req = d.get("request")
        if legacy_req and isinstance(legacy_req, dict):
            existing_params = d.get("params") or {}
            merged = {**legacy_req, **existing_params}
            d["params"] = merged

        params = d.get("params") or {}

        # 2. Extract action if embedded in params/request
        if not d.get("action") and "action" in params:
            d["action"] = params["action"]

        # 3. Pull 'data' from params if specified there
        if not d.get("data") and "data" in params:
            d["data"] = params["data"]

        # 4. Pull 'filter' from params if specified there
        if not d.get("filter") and "filter" in params:
            d["filter"] = params["filter"]

        return d

    def get_effective_action(self) -> str:
        """Resolve the final target action string."""
        if self.action:
            return self.action
        if self.params and "action" in self.params:
            return str(self.params["action"])
        return ""

    def get_merged_call_params(self, default_token: Optional[str] = None) -> Dict[str, Any]:
        """Produce the canonical flat parameter dictionary for calling the backend."""
        out: Dict[str, Any] = {}

        # Base params
        if self.params:
            out.update(self.params)

        # Merge data fields
        if self.data and isinstance(self.data, dict):
            out.update(self.data)

        # Merge filter fields
        if self.filter and isinstance(self.filter, dict):
            out.update(self.filter)

        # Ensure action is set
        action = self.get_effective_action()
        if action:
            out["action"] = action

        # Set token
        if self.token is not None:
            out["token"] = self.token
        elif "token" not in out and default_token:
            out["token"] = default_token

        return out


class EvaluateRequest(BaseModel):
    """Top-level evaluation request compatible with legacy index.php."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    action: str = Field(default="EvaluateAC", description="Controller action, e.g. EvaluateAC, ListACs")
    token: Optional[str] = Field(default=None, description="Security token from client")
    use_ai: bool = Field(default=True, description="Whether to trigger Gemini AI reasoning")
    payload: Optional[ACPayload] = Field(default=None, description="AC evaluation payload")


# ==============================================================================
# Target API Models
# ==============================================================================

class TargetApiResponse(BaseModel):
    """Normalized response received from target backend project."""

    model_config = ConfigDict(extra="allow")

    status_code: int = Field(description="HTTP status code (e.g. 200, 401, 404, 500)")
    success: bool = Field(default=False, description="Whether operation succeeded according to backend")
    data: Any = Field(default=None, description="Primary payload or records returned")
    raw: Any = Field(default=None, description="Raw deserialized JSON response or string")
    error: Optional[str] = Field(default=None, description="Error message if network/HTTP failed")
    latency_ms: float = Field(default=0.0, description="Round-trip latency in milliseconds")


# ==============================================================================
# QC Engine Models
# ==============================================================================

class EngineResult(BaseModel):
    """Deterministic QC result produced by Mumakil rule evaluators."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    status: Literal["PASSED", "FAILED"] = Field(description="Evaluation verdict: PASSED or FAILED")
    return_code: int = Field(alias="return", description="Effective HTTP status code evaluated")
    reason: str = Field(description="Deterministic human-readable explanation")
    risk: int = Field(ge=0, le=100, description="Assessed risk score from 0 to 100")
    ai_reasoning: Optional[str] = Field(
        default=None, alias="AI_reasoning", description="AI summary explanation if integrated"
    )


# ==============================================================================
# Gemini Structured Output Models (Native JSON Schema)
# ==============================================================================

class FindingItem(BaseModel):
    """Specific rule finding reported by AI reasoning."""

    rule: str = Field(description="Name or description of the rule evaluated")
    result: Literal["pass", "fail"] = Field(description="Rule outcome: pass or fail")
    details: str = Field(description="Specific technical detail or observation")


class AIEvaluationResponse(BaseModel):
    """Google Gemini AI Structured Output Model.

    Enforced via Gemini Native Structured Outputs (responseSchema & responseMimeType="application/json").
    Completely eliminates fragile regex fallbacks.
    """

    model_config = ConfigDict(extra="allow")

    success: bool = Field(description="Whether the AI evaluation successfully completed")
    findings: List[FindingItem] = Field(
        default_factory=list, description="List of individual rule checks and observations"
    )
    severity: Literal["low", "medium", "high"] = Field(
        default="low", description="Severity assessment: low, medium, or high"
    )
    risk_tags: List[str] = Field(
        default_factory=list, description="Categorization risk tags, e.g. ['auth_failure', 'empty_set']"
    )
    reason: str = Field(description="Concise, authoritative explanation of the evaluation outcome")
    evaluated_at: Optional[str] = Field(
        default_factory=lambda: datetime.now().strftime("%d/%m/%Y %H:%M"),
        description="Timestamp string in d/m/Y H:i format"
    )


# ==============================================================================
# Combined Full Results
# ==============================================================================

class CombinedEvaluationResult(BaseModel):
    """Complete evaluation envelope containing deterministic results + AI reasoning."""

    model_config = ConfigDict(extra="allow")

    success: bool = Field(default=True, description="Overall pipeline success")
    ac_id: str = Field(description="Identifier of the evaluated Acceptance Criteria")
    action_called: str = Field(default="", description="Name of backend action invoked")
    deterministic: EngineResult = Field(description="Deterministic rule evaluation outcome")
    ai_reasoning: Optional[AIEvaluationResponse] = Field(
        default=None, description="Deep AI reasoning analysis from Gemini"
    )
    raw_api_response: Optional[Any] = Field(
        default=None, description="Raw data or response from target API"
    )
    execution_time_ms: float = Field(default=0.0, description="Total pipeline latency in ms")
    message: str = Field(default="AC evaluation completed", description="Status message")


class TestCaseDefinition(BaseModel):
    """Declarative definition of a test case migrated from Postman collection."""

    id: str = Field(description="Test case ID (e.g. TC1-AC01)")
    ac_id: str = Field(description="Acceptance Criteria ID (e.g. AC01)")
    name: str = Field(description="Descriptive name")
    description: str = Field(default="", description="Detailed AC description")
    action: str = Field(description="Action name to test")
    payload: ACPayload = Field(description="Full input payload")
    expected_status: int = Field(default=200, description="Expected HTTP response status code")
    expected_engine_status: Literal["PASSED", "FAILED"] = Field(
        default="PASSED", description="Expected QC verdict"
    )
    use_ai: bool = Field(default=True, description="Whether AI evaluation is enabled for this test")


class BatchEvaluationResult(BaseModel):
    """Summary metrics of a concurrent batch test run."""

    total_cases: int = Field(description="Total test cases executed")
    passed_cases: int = Field(description="Number of passed test cases")
    failed_cases: int = Field(description="Number of failed test cases")
    total_duration_ms: float = Field(description="Total batch duration in milliseconds")
    results: List[CombinedEvaluationResult] = Field(
        default_factory=list, description="List of individual evaluation results"
    )
