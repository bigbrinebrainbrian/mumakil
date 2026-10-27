"""Command Line Interface for Mumakil 2.0 Autonomous QA Engine.

Usage:
    python -m mumakil_core.cli --run-all
    python -m mumakil_core.cli --ac AC01
    python -m mumakil_core.cli --benchmark
    python -m mumakil_core.cli --generate-tests
    python -m mumakil_core.cli --serve --port 8000
"""

import argparse
import asyncio
import json
import sys
import time
from typing import List

from mumakil_core.ai.generator import AutonomousTestCaseGenerator
from mumakil_core.config import get_settings
from mumakil_core.engine.qc_runner import AsyncQCRunner
from mumakil_core.models.schemas import TestCaseDefinition
from mumakil_core.testcases.ac_definitions import get_all_test_cases, get_test_case_by_id


async def run_all_cases(use_ai: bool = True, output_json: bool = False) -> int:
    """Execute all 21 Acceptance Criteria test cases."""
    print("=" * 70)
    print("MUMAKIL 2.0 - AUTONOMOUS ASYNC QA ENGINE")
    print("Executing all 21 Acceptance Criteria test cases concurrently...")
    print("=" * 70)

    test_cases = get_all_test_cases()
    settings = get_settings()

    async with AsyncQCRunner(settings=settings) as runner:
        start_time = time.perf_counter()
        batch_res = await runner.evaluate_batch(test_cases, use_ai=use_ai)
        duration_ms = (time.perf_counter() - start_time) * 1000.0

    if output_json:
        print(batch_res.model_dump_json(indent=2))
        return 0 if batch_res.failed_cases == 0 else 1

    print(f"\n{'ID':<18} | {'AC':<5} | {'ACTION':<20} | {'STATUS':<7} | {'RISK':<4} | {'TIME'}")
    print("-" * 75)

    for res in batch_res.results:
        status_str = "[PASS]" if res.success else "[FAIL]"
        print(
            f"{res.action_called:<18} | {res.ac_id:<5} | {res.action_called:<20} | "
            f"{status_str:<7} | {res.deterministic.risk:<4} | {res.execution_time_ms:>6.1f}ms"
        )
        if res.deterministic.ai_reasoning:
            print(f"   AI Reasoning: {res.deterministic.ai_reasoning}")

    print("-" * 75)
    print(f"Summary: {batch_res.passed_cases}/{batch_res.total_cases} Passed, "
          f"{batch_res.failed_cases} Failed in {duration_ms:.2f}ms")
    print("=" * 70)

    return 0 if batch_res.failed_cases == 0 else 1


async def run_single_ac(ac_id: str, use_ai: bool = True) -> int:
    """Execute a single AC or test case ID."""
    test_cases = [tc for tc in get_all_test_cases() if tc.ac_id.upper() == ac_id.upper() or tc.id == ac_id]
    if not test_cases:
        print(f"Error: No test cases found matching '{ac_id}'.")
        return 1

    print(f"Executing {len(test_cases)} case(s) for {ac_id}...")
    async with AsyncQCRunner() as runner:
        batch_res = await runner.evaluate_batch(test_cases, use_ai=use_ai)

    for r in batch_res.results:
        print(json.dumps(r.model_dump(), indent=2, default=str))

    return 0 if batch_res.failed_cases == 0 else 1


def run_generate_tests() -> int:
    """Generate synthetic edge cases from table schemas."""
    print("=" * 70)
    print("MUMAKIL 2.0 - AUTONOMOUS TEST CASE GENERATOR")
    print("Synthesizing Boundary Values, Payload Tampering & Negative Cases...")
    print("=" * 70)

    generator = AutonomousTestCaseGenerator()
    suite = generator.generate_full_suite()

    print(f"Generated {len(suite)} autonomous test cases:")
    for idx, tc in enumerate(suite, start=1):
        print(f"[{idx:02d}] {tc.id}: {tc.name}")
        print(f"     Target: {tc.action} | Expected: HTTP {tc.expected_status}")

    print("=" * 70)
    return 0


def main() -> None:
    """CLI entrypoint dispatcher."""
    parser = argparse.ArgumentParser(
        prog="mumakil",
        description="Mumakil 2.0 - Modern Autonomous Asynchronous QA Engine",
    )
    parser.add_argument("--run-all", action="store_true", help="Execute all 21 AC test cases")
    parser.add_argument("--ac", type=str, help="Execute specific AC (e.g. AC01, AC21)")
    parser.add_argument("--generate-tests", action="store_true", help="Generate edge-case test suite")
    parser.add_argument("--no-ai", action="store_true", help="Disable AI reasoning")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    parser.add_argument("--serve", action="store_true", help="Start FastAPI web server")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Server host")
    parser.add_argument("--port", type=int, default=8000, help="Server port")

    args = parser.parse_args()

    use_ai = not args.no_ai

    if args.serve:
        import uvicorn
        print(f"Starting Mumakil 2.0 server at http://{args.host}:{args.port}")
        uvicorn.run("main:app", host=args.host, port=args.port, reload=False)
        sys.exit(0)

    if args.generate_tests:
        sys.exit(run_generate_tests())

    if args.ac:
        sys.exit(asyncio.run(run_single_ac(args.ac, use_ai=use_ai)))

    if args.run_all or len(sys.argv) == 1:
        sys.exit(asyncio.run(run_all_cases(use_ai=use_ai, output_json=args.json)))


if __name__ == "__main__":
    main()
