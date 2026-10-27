"""Main Application Entrypoint for Mumakil 2.0.

Provides modern FastAPI asynchronous REST endpoints alongside legacy-compatible
routes (/index.php) for backward compatibility with Postman collections.
"""

from contextlib import asynccontextmanager
import time
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from mumakil_core import __version__
from mumakil_core.ai.generator import AutonomousTestCaseGenerator
from mumakil_core.config import Settings, get_settings
from mumakil_core.engine.qc_runner import AsyncQCRunner
from mumakil_core.models.schemas import (
    ACPayload,
    BatchEvaluationResult,
    CombinedEvaluationResult,
    EvaluateRequest,
    TestCaseDefinition,
)
from mumakil_core.testcases.ac_definitions import get_all_test_cases


runner_instance: Optional[AsyncQCRunner] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for startup and graceful shutdown."""
    global runner_instance
    settings = get_settings()
    runner_instance = AsyncQCRunner(settings=settings)
    yield
    if runner_instance:
        await runner_instance.close()


app = FastAPI(
    title="Mumakil 2.0 - Autonomous QA Engine",
    description="Modern Asynchronous Quality Control & Autonomous Test Engine for dbmigas.",
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==============================================================================
# Health & Status
# ==============================================================================

@app.get("/health", tags=["System"])
async def health_check() -> Dict[str, Any]:
    """Health check endpoint reporting engine status and version."""
    settings = get_settings()
    return {
        "status": "healthy",
        "engine": "Mumakil 2.0 (Async Python)",
        "version": __version__,
        "concurrency_limit": settings.concurrency_limit,
        "target_url": settings.target_base_url,
    }


# ==============================================================================
# Legacy Compatible Endpoint (/index.php)
# ==============================================================================

@app.post("/index.php", tags=["Legacy Compatibility"])
@app.post("/automation_dbmigas/index.php", tags=["Legacy Compatibility"])
async def legacy_index_endpoint(request: Request) -> JSONResponse:
    """Backward-compatible endpoint matching legacy index.php contract from Postman.

    Handles actions: 'ListACs' and 'EvaluateAC'.
    Soft-fails missing or invalid tokens as per ACES v1.7.2 specification.
    """
    global runner_instance
    if not runner_instance:
        runner_instance = AsyncQCRunner()

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "Invalid JSON", "data": None},
        )

    if not isinstance(body, dict):
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "Invalid input format", "data": None},
        )

    action = body.get("action", "")
    if not action:
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "Action is required", "data": None},
        )

    # 1. Action: ListACs
    if action == "ListACs":
        tcs = get_all_test_cases()
        data = [tc.model_dump() for tc in tcs]
        return JSONResponse(
            status_code=200,
            content={"success": True, "message": "AC registry loaded", "data": data},
        )

    # 2. Action: EvaluateAC
    if action == "EvaluateAC":
        payload_dict = body.get("payload")
        if not payload_dict or not isinstance(payload_dict, dict):
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "Missing payload or ac_id", "data": None},
            )

        caller_token = body.get("token")
        use_ai = bool(body.get("use_ai", True))

        try:
            payload = ACPayload.model_validate(payload_dict)
        except Exception as e:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": f"Payload validation error: {e}", "data": None},
            )

        result = await runner_instance.evaluate_single(
            payload=payload,
            caller_token=caller_token,
            use_ai=use_ai,
        )

        # Legacy response formatting envelope
        combined_dict = result.deterministic.model_dump(by_alias=True)
        if result.ai_reasoning:
            combined_dict["AI_reasoning"] = result.ai_reasoning.reason

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "AC evaluation completed with AI" if use_ai else "AC evaluation OK",
                "data": {
                    "combined": combined_dict,
                    "deterministic": result.deterministic.model_dump(by_alias=True),
                    "ai_reasoning": result.ai_reasoning.model_dump() if result.ai_reasoning else None,
                },
            },
        )

    return JSONResponse(
        status_code=400,
        content={"success": False, "message": f"Invalid action: {action}", "data": None},
    )


# ==============================================================================
# Modern REST API Endpoints
# ==============================================================================

@app.post("/api/evaluate", response_model=CombinedEvaluationResult, tags=["QC Evaluation"])
async def evaluate_single_ac(req: EvaluateRequest) -> CombinedEvaluationResult:
    """Evaluate a single Acceptance Criteria test case asynchronously."""
    global runner_instance
    if not runner_instance:
        runner_instance = AsyncQCRunner()

    if not req.payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payload is required for AC evaluation",
        )

    return await runner_instance.evaluate_single(
        payload=req.payload,
        caller_token=req.token,
        use_ai=req.use_ai,
    )


@app.post("/api/evaluate-batch", response_model=BatchEvaluationResult, tags=["QC Evaluation"])
async def evaluate_batch_acs(
    test_cases: Optional[List[TestCaseDefinition]] = None,
    use_ai: bool = True,
) -> BatchEvaluationResult:
    """Execute a batch of Acceptance Criteria test cases concurrently."""
    global runner_instance
    if not runner_instance:
        runner_instance = AsyncQCRunner()

    cases_to_run = test_cases or get_all_test_cases()
    return await runner_instance.evaluate_batch(cases_to_run, use_ai=use_ai)


@app.get("/api/testcases", response_model=List[TestCaseDefinition], tags=["Test Cases"])
async def list_test_cases() -> List[TestCaseDefinition]:
    """Retrieve all 21 Acceptance Criteria test definitions."""
    return get_all_test_cases()


@app.post("/api/generate-tests", response_model=List[TestCaseDefinition], tags=["Autonomous AI"])
async def generate_autonomous_tests(table_name: Optional[str] = None) -> List[TestCaseDefinition]:
    """Autonomously synthesize boundary, tampering, and negative test cases."""
    generator = AutonomousTestCaseGenerator()
    if table_name:
        return generator.generate_all_for_table(table_name)
    return generator.generate_full_suite()


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run("main:app", host=settings.app_host, port=settings.app_port, reload=settings.debug)
