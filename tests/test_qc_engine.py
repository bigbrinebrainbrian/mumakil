"""Comprehensive test suite for Mumakil 2.0 Async QC Engine (AC01 - AC21)."""

import pytest
from mumakil_core.engine.qc_runner import AsyncQCRunner
from mumakil_core.models.schemas import ACPayload
from mumakil_core.testcases.ac_definitions import get_all_test_cases, get_test_case_by_id


@pytest.fixture
def runner():
    """Provides AsyncQCRunner instance."""
    return AsyncQCRunner()


@pytest.mark.asyncio
async def test_ac01_get_view_positive_and_negative(runner):
    """Test AC01: Valid table loads 200, non-existent table returns 404 (both PASS QC)."""
    # 1. Positive case: GetMS_BANK
    res_pos = await runner.evaluate_single(
        ACPayload(ac_id="AC01", request={"action": "GetMS_BANK"}),
        use_ai=False,
    )
    assert res_pos.success is True
    assert res_pos.deterministic.status == "PASSED"
    assert res_pos.deterministic.return_code == 200
    assert res_pos.deterministic.risk == 0

    # 2. Negative case: GetMS_SHIP (expected 404)
    res_neg = await runner.evaluate_single(
        ACPayload(ac_id="AC01", request={"action": "GetMS_SHIP"}),
        use_ai=False,
    )
    assert res_neg.success is True
    assert res_neg.deterministic.status == "PASSED"
    assert res_neg.deterministic.return_code == 404
    assert res_neg.deterministic.risk == 0


@pytest.mark.asyncio
async def test_ac02_get_check_filters(runner):
    """Test AC02: Filtered searches (nama, nip, kdbank)."""
    # Nama Found
    res1 = await runner.evaluate_single(
        ACPayload(ac_id="AC02", request={"action": "GetNamaKaryawan", "nama": "Steph"}),
        use_ai=False,
    )
    assert res1.success is True
    assert res1.deterministic.status == "PASSED"
    assert res1.deterministic.return_code == 200

    # Nama Not Found (Negative test passes)
    res2 = await runner.evaluate_single(
        ACPayload(ac_id="AC02", request={"action": "GetNamaKaryawan", "nama": "Unknown Person"}),
        use_ai=False,
    )
    assert res2.success is True
    assert res2.deterministic.status == "PASSED"
    assert res2.deterministic.return_code == 404


@pytest.mark.asyncio
async def test_ac03_insert_operations(runner):
    """Test AC03: Entity insert and table not found negative check."""
    # Positive insert
    res_pos = await runner.evaluate_single(
        ACPayload(
            ac_id="AC03",
            action="InsertMS_BANK",
            data={"KDBANK": "ABALIDBS", "NAMABANK": "PT.BPD BALI"},
        ),
        use_ai=False,
    )
    assert res_pos.success is True
    assert res_pos.deterministic.status == "PASSED"
    assert res_pos.deterministic.return_code == 200

    # Negative insert
    res_neg = await runner.evaluate_single(
        ACPayload(
            ac_id="AC03",
            action="InsertMS_SHIP",
            data={"ship": "ghost_ship"},
        ),
        use_ai=False,
    )
    assert res_neg.success is True
    assert res_neg.deterministic.status == "PASSED"
    assert res_neg.deterministic.return_code == 404


@pytest.mark.asyncio
async def test_ac04_duplicate_insert_permitted(runner):
    """Test AC04: Idempotent duplicate insert policy permits repeated inserts."""
    data = {
        "nip": "199211092020122001",
        "nama": "Stephany Novianty",
        "kodejabatan": "113",
        "rek_bank": "BRI",
        "rek_nomor": "037801015331504",
        "rek_kdbank": "BRINIDJA",
    }
    # Initial insert
    res1 = await runner.evaluate_single(
        ACPayload(ac_id="AC04", action="InsertMS_KARYAWAN", data=data),
        use_ai=False,
    )
    assert res1.success is True

    # Duplicate insert MUST also be permitted by AC04 design
    res2 = await runner.evaluate_single(
        ACPayload(ac_id="AC04", action="InsertMS_KARYAWAN", data=data),
        use_ai=False,
    )
    assert res2.success is True
    assert res2.deterministic.status == "PASSED"
    assert "Duplicate insert permitted" in res2.deterministic.reason


@pytest.mark.asyncio
async def test_ac07_delete_operations(runner):
    """Test AC07: Delete existing record returns 200, non-existent returns 404."""
    # Delete existing
    res_pos = await runner.evaluate_single(
        ACPayload(ac_id="AC07", action="DeleteMS_BANK", data={"KDBANK": "ABALIDBS"}),
        use_ai=False,
    )
    assert res_pos.success is True
    assert res_pos.deterministic.status == "PASSED"
    assert res_pos.deterministic.return_code == 200

    # Delete non-existent
    res_neg = await runner.evaluate_single(
        ACPayload(ac_id="AC07", action="DeleteMS_Ship", data={"ship": "ship"}),
        use_ai=False,
    )
    assert res_neg.success is True
    assert res_neg.deterministic.status == "PASSED"
    assert res_neg.deterministic.return_code == 404


@pytest.mark.asyncio
async def test_ac21_soft_fail_unauthorized_token(runner):
    """Test AC21: Missing or invalid token soft-fails to 401 and correctly passes QC security rule."""
    payload = ACPayload(
        ac_id="AC21",
        action="DeleteMS_BANK",
        token="INVALID_TOKEN_ABC",
        data={"KDBANK": "BRINIDJA"},
    )
    res = await runner.evaluate_single(payload, caller_token="INVALID_TOKEN_ABC", use_ai=True)

    # Soft-fail: runner did not crash, payload automation_status set to 401
    assert payload.automation_status == 401
    assert res.success is True
    assert res.deterministic.status == "PASSED"
    assert res.deterministic.return_code == 401
    assert res.deterministic.risk == 0
    assert "correctly blocked" in res.deterministic.reason

    # AI reasoning received 401 context
    assert res.ai_reasoning is not None
    assert "auth_blocked" in res.ai_reasoning.risk_tags or "security" in res.ai_reasoning.risk_tags


@pytest.mark.asyncio
async def test_ac09_ac10_update_operations(runner):
    """Test AC09 update and AC10 validation enforcement."""
    # AC09 valid update
    res_up = await runner.evaluate_single(
        ACPayload(
            ac_id="AC09",
            action="UpdateMS_BANK",
            data={"KDBANK": "ABALIDBS", "NAMABANK": "PT.BPD BALI", "alias": "BALI"},
        ),
        use_ai=False,
    )
    assert res_up.success is True
    assert res_up.deterministic.status == "PASSED"
    assert res_up.deterministic.return_code == 200

    # AC10 validation triggered on empty NMBANK
    res_val = await runner.evaluate_single(
        ACPayload(
            ac_id="AC10",
            action="UpdateMS_BANK",
            data={"KDBANK": "BRINIDJA", "NMBANK": ""},
        ),
        use_ai=False,
    )
    assert res_val.success is True
    assert res_val.deterministic.status == "PASSED"
    assert res_val.deterministic.return_code == 400
    assert "Validation rule triggered" in res_val.deterministic.reason


@pytest.mark.asyncio
async def test_all_21_cases_batch_concurrent(runner):
    """Execute all 21 migrated Acceptance Criteria concurrently and verify 100% pass."""
    all_cases = get_all_test_cases()
    assert len(all_cases) == 21

    batch_res = await runner.evaluate_batch(all_cases, use_ai=False)
    assert batch_res.total_cases == 21
    assert batch_res.passed_cases == 21
    assert batch_res.failed_cases == 0
    # Performance requirement: < 3 seconds
    assert batch_res.total_duration_ms < 3000.0
