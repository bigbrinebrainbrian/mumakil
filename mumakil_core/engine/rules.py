"""Declarative Rule Evaluator for Mumakil 2.0.

Replaces brittle procedural switch-cases and nested conditionals from legacy qc_engine.php.
Evaluates deterministic verdicts (PASSED/FAILED), risk levels (0-100), and explanations
for all Acceptance Criteria (AC01 - AC21).
"""

from typing import Any, Dict, Optional, Tuple
from mumakil_core.models.schemas import ACPayload, EngineResult, TargetApiResponse


class RuleEvaluator:
    """Deterministic Rule Evaluator for Acceptance Criteria."""

    @staticmethod
    def evaluate(
        payload: ACPayload,
        response: TargetApiResponse,
        is_duplicate: bool = False,
    ) -> EngineResult:
        """Evaluate business rules against backend response and context."""
        ac_id = payload.ac_id.upper()
        action = payload.get_effective_action()
        status_code = response.status_code
        is_success = response.success
        auto_status = payload.automation_status

        # ----------------------------------------------------------------------
        # AC21 & AC08: Security & Token Requirement
        # ----------------------------------------------------------------------
        if ac_id in ("AC21", "AC08", "AC8"):
            # Check soft-fail status from caller or response
            if auto_status == 401 or status_code == 401:
                return EngineResult(
                    status="PASSED",
                    return_code=401,
                    reason="Token missing/invalid and request was correctly blocked",
                    risk=0,
                )
            elif status_code == 200 and is_success:
                return EngineResult(
                    status="PASSED",
                    return_code=200,
                    reason="Authorized request succeeded with valid credentials",
                    risk=0,
                )
            else:
                return EngineResult(
                    status="FAILED",
                    return_code=status_code,
                    reason=f"Security token policy mismatch (HTTP {status_code}): {response.error or 'Unexpected behavior'}",
                    risk=80,
                )

        # ----------------------------------------------------------------------
        # AC01: GetView (Endpoint discovery & full table projection)
        # ----------------------------------------------------------------------
        if ac_id in ("AC01", "AC1"):
            # Expected negative check (e.g. GetMS_SHIP)
            if status_code in (404, 400) or (status_code == 200 and not is_success):
                return EngineResult(
                    status="PASSED",
                    return_code=status_code,
                    reason="Endpoint not found or rejected as expected (negative test case)",
                    risk=0,
                )
            if status_code == 200 and is_success:
                return EngineResult(
                    status="PASSED",
                    return_code=200,
                    reason="GetView successfully loaded table structure and data",
                    risk=0,
                )
            return EngineResult(
                status="FAILED",
                return_code=status_code,
                reason=f"Failed to load table view (HTTP {status_code})",
                risk=70,
            )

        # ----------------------------------------------------------------------
        # AC02: GetCheck (Filtered searches: Nama, NIP, KDBANK)
        # ----------------------------------------------------------------------
        if ac_id in ("AC02", "AC2"):
            if status_code == 200 and is_success:
                return EngineResult(
                    status="PASSED",
                    return_code=200,
                    reason="Filter query found matching record",
                    risk=0,
                )
            elif status_code == 404 or (status_code == 200 and not response.data):
                return EngineResult(
                    status="PASSED",
                    return_code=404,
                    reason="Record not found for given filter (expected negative test)",
                    risk=0,
                )
            return EngineResult(
                status="FAILED",
                return_code=status_code,
                reason=f"GetCheck query failed unexpectedly (HTTP {status_code})",
                risk=65,
            )

        # ----------------------------------------------------------------------
        # AC03: Insert Operations
        # ----------------------------------------------------------------------
        if ac_id in ("AC03", "AC3"):
            if status_code in (200, 201) and is_success:
                return EngineResult(
                    status="PASSED",
                    return_code=status_code,
                    reason="Insert entity succeeded",
                    risk=0,
                )
            elif status_code == 404:
                return EngineResult(
                    status="PASSED",
                    return_code=404,
                    reason="Target table not found for insert (expected negative)",
                    risk=0,
                )
            return EngineResult(
                status="FAILED",
                return_code=status_code,
                reason=f"Insert failed with HTTP {status_code}: {response.error or 'Validation/DB error'}",
                risk=75,
            )

        # ----------------------------------------------------------------------
        # AC04 & AC12: Duplicate Insert Behavior
        # ----------------------------------------------------------------------
        if ac_id in ("AC04", "AC4"):
            if is_duplicate and status_code in (200, 201):
                return EngineResult(
                    status="PASSED",
                    return_code=status_code,
                    reason="Duplicate insert permitted by design (AC04 idempotent policy)",
                    risk=0,
                )
            elif status_code in (200, 201):
                return EngineResult(
                    status="PASSED",
                    return_code=status_code,
                    reason="Initial entity insert succeeded",
                    risk=0,
                )
            return EngineResult(
                status="FAILED",
                return_code=status_code,
                reason="Unexpected rejection on duplicate insert",
                risk=50,
            )

        if ac_id == "AC12":
            if status_code in (400, 409):
                return EngineResult(
                    status="PASSED",
                    return_code=status_code,
                    reason="Duplicate insert strictly rejected (AC12 constraint enforced)",
                    risk=0,
                )
            elif status_code in (200, 201):
                # If permitted or flagged
                return EngineResult(
                    status="PASSED",
                    return_code=status_code,
                    reason="Duplicate insert handled by backend",
                    risk=10,
                )

        # ----------------------------------------------------------------------
        # AC07: Delete Operations
        # ----------------------------------------------------------------------
        if ac_id in ("AC07", "AC7"):
            if status_code == 200 and is_success:
                return EngineResult(
                    status="PASSED",
                    return_code=200,
                    reason="Delete succeeded",
                    risk=0,
                )
            elif status_code == 404:
                return EngineResult(
                    status="PASSED",
                    return_code=404,
                    reason="Record not found (expected negative delete)",
                    risk=0,
                )
            return EngineResult(
                status="FAILED",
                return_code=status_code,
                reason=f"Unexpected delete behavior: HTTP {status_code}",
                risk=50,
            )

        # ----------------------------------------------------------------------
        # AC09: Update Operations
        # ----------------------------------------------------------------------
        if ac_id in ("AC09", "AC9"):
            if status_code == 200 and is_success:
                return EngineResult(
                    status="PASSED",
                    return_code=200,
                    reason="Update successful",
                    risk=0,
                )
            elif status_code == 404:
                return EngineResult(
                    status="PASSED",
                    return_code=404,
                    reason="Update target not found (expected negative update)",
                    risk=0,
                )
            return EngineResult(
                status="FAILED",
                return_code=status_code,
                reason=f"Unexpected update behavior: HTTP {status_code}",
                risk=60,
            )

        # ----------------------------------------------------------------------
        # AC10: Update Validation Check
        # ----------------------------------------------------------------------
        if ac_id in ("AC10"):
            if status_code == 400:
                return EngineResult(
                    status="PASSED",
                    return_code=400,
                    reason="Validation rule triggered successfully",
                    risk=0,
                )
            elif status_code == 200:
                return EngineResult(
                    status="PASSED",
                    return_code=200,
                    reason="Validation off but update allowed by backend",
                    risk=30,
                )
            return EngineResult(
                status="FAILED",
                return_code=status_code,
                reason=f"Unexpected validation response: HTTP {status_code}",
                risk=70,
            )

        # ----------------------------------------------------------------------
        # Generic Default Rules
        # ----------------------------------------------------------------------
        if is_success or status_code == 200:
            return EngineResult(
                status="PASSED",
                return_code=status_code,
                reason="Operation completed successfully",
                risk=0,
            )
        elif status_code == 404:
            return EngineResult(
                status="PASSED",
                return_code=404,
                reason="Endpoint/Entity not found (expected negative)",
                risk=0,
            )

        return EngineResult(
            status="FAILED",
            return_code=status_code,
            reason=f"Unrecognized status code or execution failure: {status_code}",
            risk=70,
        )
