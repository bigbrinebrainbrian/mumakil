"""Concurrency and thread-safety tests for StateManager."""

import asyncio
import pytest
from mumakil_core.engine.state_manager import StateManager


@pytest.mark.asyncio
async def test_state_manager_duplicate_detection(tmp_path):
    """Verify primary group extraction and duplicate insert detection."""
    db_file = tmp_path / "test_state.db"
    sm = StateManager(use_sqlite=False)
    sm.db_path = db_file
    # Isolate storage directory for testing
    sm.settings.storage_dir = tmp_path
    await sm.clear()

    action = "InsertMS_KARYAWAN_TEST_ISOLATED"
    record1 = {
        "nip": "199211092020122001",
        "nama": "Stephany Novianty",
        "kodejabatan": "113",
        "rek_bank": "BANK RAKYAT INDONESIA",
        "rek_nomor": "037801015331504",
        "rek_kdbank": "BRINIDJA",
        "jabatan": "Staf SDMK",
    }

    # First insert is not duplicate
    is_dup1 = await sm.is_duplicate_insert(action, record1)
    assert is_dup1 is False

    # Record insert
    await sm.record_insert(action, record1)

    # Second identical insert MUST be detected as duplicate
    is_dup2 = await sm.is_duplicate_insert(action, record1)
    assert is_dup2 is True

    # Modified record (different NIP) MUST NOT be duplicate
    record2 = dict(record1)
    record2["nip"] = "999999999999999999"
    is_dup3 = await sm.is_duplicate_insert(action, record2)
    assert is_dup3 is False


@pytest.mark.asyncio
async def test_state_manager_concurrency_stress(tmp_path):
    """Stress test StateManager under 50 concurrent coroutines to verify race-condition immunity."""
    db_file = tmp_path / "concurrent_state.db"
    sm = StateManager(use_sqlite=True)
    sm.db_path = db_file
    sm._init_sqlite()

    concurrency_count = 50
    actions = [f"InsertEntity_{i % 5}" for i in range(concurrency_count)]

    async def worker(idx: int, action: str):
        candidate = {
            "nip": f"NIP_{idx:04d}",
            "nama": f"Worker_{idx}",
            "kodejabatan": f"JOB_{idx % 10}",
            "rek_bank": "BCA",
            "rek_nomor": f"REK_{idx:08d}",
            "rek_kdbank": "BCAIDJA",
        }
        # Check duplicate
        _ = await sm.is_duplicate_insert(action, candidate)
        # Record insert
        await sm.record_insert(action, candidate)
        # Read back last insert
        last = await sm.get_last_insert(action)
        assert last is not None
        assert "nip" in last
        assert "nama" in last

    # Run 50 concurrent worker coroutines
    tasks = [worker(i, actions[i]) for i in range(concurrency_count)]
    await asyncio.gather(*tasks)

    # Verify state integrity across all actions
    for a in set(actions):
        record = await sm.get_last_insert(a)
        assert record is not None
        assert record["rek_bank"] == "BCA"
