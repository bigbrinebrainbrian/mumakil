"""Asynchronous QC Runner for Mumakil 2.0.

Replaces legacy multi-hop blocking PHP pipeline (Postman -> index.php -> project_dbmigas -> analyze.php).
Features:
- Full asynchronous parallel execution of AC01 to AC21 via asyncio.gather and Semaphore pooling
- Seamless soft-fail token architecture preserving AI reasoning context under 401
- Integrated thread-safe StateManager for duplicate insert policies
- Native Gemini AI Reasoning evaluation with zero regex fallbacks
- Compatibility with legacy audit and application logs
"""

import asyncio
from datetime import datetime
import json
import logging
from pathlib import Path
import time
from typing import Any, Dict, List, Optional

from mumakil_core.ai.evaluator import AIReasoningEvaluator, get_ai_evaluator
from mumakil_core.client import AsyncTargetApiClient
from mumakil_core.config import Settings, get_settings
from mumakil_core.engine.rules import RuleEvaluator
from mumakil_core.engine.state_manager import StateManager, get_state_manager
from mumakil_core.models.schemas import (
    ACPayload,
    BatchEvaluationResult,
    CombinedEvaluationResult,
    EngineResult,
    TestCaseDefinition,
)

logger = logging.getLogger("mumakil.qc_runner")


class AsyncQCRunner:
    """Core Asynchronous Quality Control Engine Runner."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        client: Optional[AsyncTargetApiClient] = None,
        state_manager: Optional[StateManager] = None,
        ai_evaluator: Optional[AIReasoningEvaluator] = None,
    ):
        self.settings = settings or get_settings()
        self.client = client or AsyncTargetApiClient(settings=self.settings)
        self.state_manager = state_manager or get_state_manager()
        self.ai_evaluator = ai_evaluator or get_ai_evaluator()
        self._owns_client = client is None
        self._semaphore = asyncio.Semaphore(self.settings.concurrency_limit)

    async def close(self) -> None:
        """Close managed clients."""
        if self._owns_client:
            await self.client.close()

    async def __aenter__(self) -> "AsyncQCRunner":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    def _write_audit_log(self, event_name: str, data: Any) -> None:
        """Append to storage/logs/audit.log in legacy format."""
        try:
            log_file = self.settings.log_dir / "audit.log"
            line = json.dumps(
                {
                    "ts": datetime.now().strftime("%d/%m/%Y %H:%M"),
                    "name": event_name,
                    "data": data,
                },
                ensure_ascii=False,
            ) + "\n"
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception as e:
            logger.debug("Failed writing audit log: %s", e)

    def _write_app_log(self, tag: str, data: Any) -> None:
        """Append to storage/logs/app.log in legacy format."""
        try:
            log_file = self.settings.log_dir / "app.log"
            line = json.dumps(
                {
                    "ts": datetime.now().isoformat(),
                    "tag": tag,
                    "data": data,
                },
                ensure_ascii=False,
            ) + "\n"
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception as e:
            logger.debug("Failed writing app log: %s", e)

    async def evaluate_single(
        self,
        payload: ACPayload,
        caller_token: Optional[str] = None,
        use_ai: bool = True,
    ) -> CombinedEvaluationResult:
        """Execute complete evaluation pipeline for a single Acceptance Criteria test case."""
        start_time = time.perf_counter()
        ac_id = payload.ac_id
        action = payload.get_effective_action()

        # ----------------------------------------------------------------------
        # 1. Soft-fail Token Handling (Preserves AI reasoning on 401)
        # ----------------------------------------------------------------------
        effective_token = caller_token or payload.token or self.settings.qc_token
        is_token_valid = (effective_token == self.settings.qc_token)

        # If token invalid, mark automation_status = 401 without immediate abort
        if not is_token_valid:
            self._write_audit_log("unauthorized_request", {"ac_id": ac_id, "token": effective_token})
            payload.automation_status = 401
        else:
            payload.automation_status = 200

        self._write_audit_log("action_received", {"action": action, "ac_id": ac_id})

        # ----------------------------------------------------------------------
        # 2. State & Concurrency Check for Insert Operations (AC03, AC04, AC12)
        # ----------------------------------------------------------------------
        is_insert_action = "insert" in action.lower()
        is_duplicate = False

        if is_insert_action and payload.data:
            is_duplicate = await self.state_manager.is_duplicate_insert(action, payload.data)
            # Record current candidate for future duplicate checks
            await self.state_manager.record_insert(action, payload.data)

        # ----------------------------------------------------------------------
        # 3. Asynchronous Target API Dispatch
        # ----------------------------------------------------------------------
        merged_params = payload.get_merged_call_params(default_token=self.settings.qc_token)
        target_response = await self.client.call_action(
            action=action,
            params=merged_params,
            token=effective_token,
        )

        # ----------------------------------------------------------------------
        # 4. Deterministic QC Evaluation
        # ----------------------------------------------------------------------
        engine_result = RuleEvaluator.evaluate(
            payload=payload,
            response=target_response,
            is_duplicate=is_duplicate,
        )

        # ----------------------------------------------------------------------
        # 5. AI Reasoning Engine (Google Gemini Native Structured Output)
        # ----------------------------------------------------------------------
        ai_response = None
        if use_ai:
            ai_response = await self.ai_evaluator.evaluate(
                payload=payload,
                engine_result=engine_result,
                target_response=target_response,
            )
            # Link AI reason back to deterministic result
            engine_result.ai_reasoning = ai_response.reason

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        return CombinedEvaluationResult(
            success=(engine_result.status == "PASSED"),
            ac_id=ac_id,
            action_called=action,
            deterministic=engine_result,
            ai_reasoning=ai_response,
            raw_api_response=target_response.raw,
            execution_time_ms=elapsed_ms,
            message="AC evaluation completed with AI" if use_ai else "AC evaluation completed (deterministic only)",
        )

    async def evaluate_batch(
        self,
        test_cases: List[TestCaseDefinition],
        use_ai: bool = True,
    ) -> BatchEvaluationResult:
        """Execute a full batch of Acceptance Criteria concurrently with concurrency throttling."""
        start_time = time.perf_counter()

        # Pre-probe connectivity once so all concurrent coroutines don't synchronously wait for TCP timeouts
        if self.client._backend_reachable is None:
            await self.client.probe_connectivity()

        # Pre-probe Gemini API key once to avoid repeated 400 warnings on concurrent workers
        if use_ai and self.ai_evaluator._gemini_key_valid is None:
            await self.ai_evaluator.probe_key()

        async def _run_guarded(tc: TestCaseDefinition) -> CombinedEvaluationResult:
            async with self._semaphore:
                return await self.evaluate_single(
                    payload=tc.payload,
                    caller_token=tc.payload.token,
                    use_ai=(use_ai and tc.use_ai),
                )

        # Launch all test coroutines concurrently
        tasks = [_run_guarded(tc) for tc in test_cases]
        results = await asyncio.gather(*tasks, return_exceptions=False)

        total_duration = (time.perf_counter() - start_time) * 1000.0
        passed_count = sum(1 for r in results if r.success)
        failed_count = len(results) - passed_count

        return BatchEvaluationResult(
            total_cases=len(results),
            passed_cases=passed_count,
            failed_cases=failed_count,
            total_duration_ms=total_duration,
            results=list(results),
        )
