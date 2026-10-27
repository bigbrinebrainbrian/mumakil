"""Declarative Acceptance Criteria Test Definitions for Mumakil 2.0.

Migrated directly from _automation_dbmigas.postman_collection05122025.json.
Contains all 21 Acceptance Criteria test scenarios (AC01 - AC21).
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
from mumakil_core.models.schemas import ACPayload, TestCaseDefinition


ALL_TEST_CASES: List[TestCaseDefinition] = [
    # --------------------------------------------------------------------------
    # 01. Dummy API Test
    # --------------------------------------------------------------------------
    TestCaseDefinition(
        id="TC0-DUMMY",
        ac_id="AC01",
        name="Dummy API Test",
        description="Initial baseline test for AI reasoning module connectivity.",
        action="DummyAction",
        payload=ACPayload(
            ac_id="AC01",
            action="DummyAction",
            params={},
        ),
        expected_status=200,
        expected_engine_status="PASSED",
        use_ai=True,
    ),

    # --------------------------------------------------------------------------
    # 02. TC1-AC01 : GetView (Valid table)
    # --------------------------------------------------------------------------
    TestCaseDefinition(
        id="TC1-AC01",
        ac_id="AC01",
        name="TC1- AC01 : GetView",
        description="Get View: Displays all columns for a valid table (MS_BANK).",
        action="GetMS_BANK",
        payload=ACPayload(
            ac_id="AC01",
            action="GetMS_BANK",
            params={"action": "GetMS_BANK"},
        ),
        expected_status=200,
        expected_engine_status="PASSED",
        use_ai=True,
    ),

    # --------------------------------------------------------------------------
    # 03. TC2-AC01 : GetView wrong (Non-existent table)
    # --------------------------------------------------------------------------
    TestCaseDefinition(
        id="TC2-AC01",
        ac_id="AC01",
        name="TC2-AC01 : GetView wrong",
        description="Negative test: Attempting to retrieve a non-existent table (MS_SHIP) must return 404.",
        action="GetMS_SHIP",
        payload=ACPayload(
            ac_id="AC01",
            action="GetMS_SHIP",
            params={"action": "GetMS_SHIP"},
        ),
        expected_status=404,
        expected_engine_status="PASSED",
        use_ai=True,
    ),

    # --------------------------------------------------------------------------
    # 04. TC3-AC02: GetNamaKaryawan Found
    # --------------------------------------------------------------------------
    TestCaseDefinition(
        id="TC3-AC02-FOUND",
        ac_id="AC02",
        name="TC3-AC02: GetNamaKaryawan Found",
        description="Filter test: Search karyawan by partial name 'Steph' returns matched entity.",
        action="GetNamaKaryawan",
        payload=ACPayload(
            ac_id="AC02",
            action="GetNamaKaryawan",
            params={"action": "GetNamaKaryawan", "nama": "Steph"},
            filter={"nama": "Steph"},
        ),
        expected_status=200,
        expected_engine_status="PASSED",
        use_ai=True,
    ),

    # --------------------------------------------------------------------------
    # 05. TC4-AC02: GetNamaKaryawan notFound
    # --------------------------------------------------------------------------
    TestCaseDefinition(
        id="TC3-AC02-NOTFOUND",
        ac_id="AC02",
        name="TC3-AC02: GetNamaKaryawan notFound",
        description="Filter negative test: Search karyawan by non-existent name returns 404.",
        action="GetNamaKaryawan",
        payload=ACPayload(
            ac_id="AC02",
            action="GetNamaKaryawan",
            params={"action": "GetNamaKaryawan", "nama": "shabrian adam"},
            filter={"nama": "shabrian adam"},
        ),
        expected_status=404,
        expected_engine_status="PASSED",
        use_ai=True,
    ),

    # --------------------------------------------------------------------------
    # 06. TC5-AC02: GetNipKaryawan Found
    # --------------------------------------------------------------------------
    TestCaseDefinition(
        id="TC5-AC02-FOUND",
        ac_id="AC02",
        name="TC5-AC02: GetNipKaryawan Found",
        description="Filter test: Search karyawan by exact NIP '199211092020122001' succeeds.",
        action="GetNipKaryawan",
        payload=ACPayload(
            ac_id="AC02",
            action="GetNipKaryawan",
            params={"action": "GetNipKaryawan", "nip": "199211092020122001"},
            filter={"nip": "199211092020122001"},
        ),
        expected_status=200,
        expected_engine_status="PASSED",
        use_ai=True,
    ),

    # --------------------------------------------------------------------------
    # 07. TC6-AC02: GetNipKaryawan notFound
    # --------------------------------------------------------------------------
    TestCaseDefinition(
        id="TC6-AC02-NOTFOUND",
        ac_id="AC02",
        name="TC6-AC02: GetNipKaryawan notFound",
        description="Filter negative test: Search karyawan by invalid NIP '111222333' returns 404.",
        action="GetNipKaryawan",
        payload=ACPayload(
            ac_id="AC02",
            action="GetNipKaryawan",
            params={"action": "GetNipKaryawan", "nip": "111222333"},
            filter={"nip": "111222333"},
        ),
        expected_status=404,
        expected_engine_status="PASSED",
        use_ai=True,
    ),

    # --------------------------------------------------------------------------
    # 08. TC8-AC02: GetKDBANK Found
    # --------------------------------------------------------------------------
    TestCaseDefinition(
        id="TC8-AC02-FOUND",
        ac_id="AC02",
        name="TC8-AC02: GetKDBANK Found",
        description="Filter test: Search bank by code 'ABALIDBS' returns bank entity.",
        action="GetKDBANK",
        payload=ACPayload(
            ac_id="AC02",
            action="GetKDBANK",
            params={"action": "GetKDBANK", "kdbank": "ABALIDBS"},
            filter={"kdbank": "ABALIDBS"},
        ),
        expected_status=200,
        expected_engine_status="PASSED",
        use_ai=True,
    ),

    # --------------------------------------------------------------------------
    # 09. TC7-AC02: GetKDBANK notFound
    # --------------------------------------------------------------------------
    TestCaseDefinition(
        id="TC7-AC02-NOTFOUND",
        ac_id="AC02",
        name="TC7-AC02: GetKDBANK notFound",
        description="Filter negative test: Search bank by invalid code '111222333' returns 404.",
        action="GetKDBANK",
        payload=ACPayload(
            ac_id="AC02",
            action="GetKDBANK",
            params={"action": "GetKDBANK", "kdbank": "111222333"},
            filter={"kdbank": "111222333"},
        ),
        expected_status=404,
        expected_engine_status="PASSED",
        use_ai=True,
    ),

    # --------------------------------------------------------------------------
    # 10. TC9-AC03 : Insert Found (MS_KARYAWAN)
    # --------------------------------------------------------------------------
    TestCaseDefinition(
        id="TC9-AC03-KARYAWAN",
        ac_id="AC03",
        name="TC9-AC03 : Insert Found",
        description="Insert operation: Insert valid employee into MS_KARYAWAN.",
        action="InsertMS_KARYAWAN",
        payload=ACPayload(
            ac_id="AC03",
            action="InsertMS_KARYAWAN",
            data={
                "nip": "198704092014022002",
                "nama": "Apriliani",
                "kodejabatan": "113",
                "GOL": "III.c",
                "kdunit": "SDMK",
                "keterangan": "",
                "ispns": 1,
                "ismigas": 0,
                "rek_bank": "BANK RAKYAT INDONESIA",
                "rek_nama": "Apriliani",
                "rek_nomor": "037801015331504",
                "rek_kdbank": "BRINIDJA",
                "isvalid": 1,
                "jabatan": "Staf SDMK",
                "npwp": "365570522005000",
            },
        ),
        expected_status=200,
        expected_engine_status="PASSED",
        use_ai=True,
    ),

    # --------------------------------------------------------------------------
    # 11. TC10-AC03 : InsertNotFound (MS_SHIP)
    # --------------------------------------------------------------------------
    TestCaseDefinition(
        id="TC10-AC03-NOTFOUND",
        ac_id="AC03",
        name="TC10-AC03 : InsertNotFound",
        description="Negative insert: Attempt to insert into non-existent table MS_SHIP returns 404.",
        action="InsertMS_SHIP",
        payload=ACPayload(
            ac_id="AC03",
            action="InsertMS_SHIP",
            data={"ship": "ship"},
        ),
        expected_status=404,
        expected_engine_status="PASSED",
        use_ai=True,
    ),

    # --------------------------------------------------------------------------
    # 12. TC10-AC03 : Insert Found - MS_BANK
    # --------------------------------------------------------------------------
    TestCaseDefinition(
        id="TC10-AC03-BANK",
        ac_id="AC03",
        name="TC10-AC03 : Insert Found - MS_BANK",
        description="Insert operation: Insert valid bank entity into MS_BANK.",
        action="InsertMS_BANK",
        payload=ACPayload(
            ac_id="AC03",
            action="InsertMS_BANK",
            data={
                "KDBANK": "ABALIDBS",
                "NAMABANK": "PT.BPD BALI",
                "ISUSED": "1",
                "alias": "BANK BALI",
            },
        ),
        expected_status=200,
        expected_engine_status="PASSED",
        use_ai=True,
    ),

    # --------------------------------------------------------------------------
    # 13. TC11-AC04 : Identical Insert Allowed - MS_KARYAWAN
    # --------------------------------------------------------------------------
    TestCaseDefinition(
        id="TC11-AC04-KARYAWAN",
        ac_id="AC04",
        name="TC11-AC04 : Identical Insert Allowed - MS_KARYAWAN",
        description="Duplicate insert policy: Identical insert for MS_KARYAWAN is permitted by AC04 design.",
        action="InsertMS_KARYAWAN",
        payload=ACPayload(
            ac_id="AC04",
            action="InsertMS_KARYAWAN",
            data={
                "nip": "199211092020122001",
                "nama": "Stephany Novianty",
                "kodejabatan": "113",
                "GOL": "III.c",
                "kdunit": "SDMK",
                "keterangan": "",
                "ispns": 1,
                "ismigas": 0,
                "rek_bank": "BANK RAKYAT INDONESIA",
                "rek_nama": "Apriliani",
                "rek_nomor": "037801015331504",
                "rek_kdbank": "BRINIDJA",
                "isvalid": 1,
                "jabatan": "Staf SDMK",
                "npwp": "365570522005000",
            },
        ),
        expected_status=200,
        expected_engine_status="PASSED",
        use_ai=True,
    ),

    # --------------------------------------------------------------------------
    # 14. TC11-AC04 : Identical Insert Allowed - MS_BANK
    # --------------------------------------------------------------------------
    TestCaseDefinition(
        id="TC11-AC04-BANK",
        ac_id="AC04",
        name="TC11-AC04 : Identical Insert Allowed - MS_BANK",
        description="Duplicate insert policy: Identical insert for MS_BANK is permitted by AC04 design.",
        action="InsertMS_BANK",
        payload=ACPayload(
            ac_id="AC04",
            action="InsertMS_BANK",
            data={
                "KDBANK": "ABALIDBS",
                "NAMABANK": "PT.BPD BALI",
                "ISUSED": "1",
                "alias": "BANK BALI",
            },
        ),
        expected_status=200,
        expected_engine_status="PASSED",
        use_ai=True,
    ),

    # --------------------------------------------------------------------------
    # 15. TC12-AC12 : Identical Insert Fails
    # --------------------------------------------------------------------------
    TestCaseDefinition(
        id="TC12-AC12",
        ac_id="AC12",
        name="TC12-AC4 : Identical Insert Fails",
        description="Duplicate insert negative check: Verifies engine handling when duplicate constraint fails.",
        action="InsertMS_BANK",
        payload=ACPayload(
            ac_id="AC12",
            action="InsertMS_BANK",
            data={
                "KDBANK": "ABALIDBS",
                "NAMABANK": "PT.BPD BALI",
                "ISUSED": "1",
                "alias": "BANK BALI",
            },
        ),
        expected_status=200,
        expected_engine_status="PASSED",
        use_ai=True,
    ),

    # --------------------------------------------------------------------------
    # 16. TC19-AC07 : Delete Found
    # --------------------------------------------------------------------------
    TestCaseDefinition(
        id="TC19-AC07",
        ac_id="AC07",
        name="TC19-AC07 : Delete Found",
        description="Delete operation: Deleting existing bank entity succeeds.",
        action="DeleteMS_BANK",
        payload=ACPayload(
            ac_id="AC07",
            action="DeleteMS_BANK",
            data={"KDBANK": "ABALIDBS"},
        ),
        expected_status=200,
        expected_engine_status="PASSED",
        use_ai=True,
    ),

    # --------------------------------------------------------------------------
    # 17. TC20-AC07 : Delete NotFound
    # --------------------------------------------------------------------------
    TestCaseDefinition(
        id="TC20-AC07",
        ac_id="AC07",
        name="TC20-AC07 : Delete NotFound",
        description="Delete negative test: Deleting record from non-existent table MS_Ship returns 404.",
        action="DeleteMS_Ship",
        payload=ACPayload(
            ac_id="AC07",
            action="DeleteMS_Ship",
            data={"ship": "ship"},
        ),
        expected_status=404,
        expected_engine_status="PASSED",
        use_ai=True,
    ),

    # --------------------------------------------------------------------------
    # 18. TC21-AC08 / AC21 : Delete Requires Token
    # --------------------------------------------------------------------------
    TestCaseDefinition(
        id="TC21-AC21",
        ac_id="AC21",
        name="TC21-AC08 : Delete Requires Token",
        description="Security test: Request with invalid token 'SDFGHJKL' must be blocked with HTTP 401.",
        action="DeleteMS_BANK",
        payload=ACPayload(
            ac_id="AC21",
            action="DeleteMS_BANK",
            token="SDFGHJKL",
            data={"KDBANK": "BRINIDJA"},
            automation_status=401,
        ),
        expected_status=401,
        expected_engine_status="PASSED",
        use_ai=True,
    ),

    # --------------------------------------------------------------------------
    # 19. TC22-AC09 : Update Found
    # --------------------------------------------------------------------------
    TestCaseDefinition(
        id="TC22-AC09",
        ac_id="AC09",
        name="TC22-AC09 : Delete Found (Update OK)",
        description="Update operation: Modifying existing MS_BANK record succeeds with 200.",
        action="UpdateMS_BANK",
        payload=ACPayload(
            ac_id="AC09",
            action="UpdateMS_BANK",
            data={
                "KDBANK": "ABALIDBS",
                "NAMABANK": "PT.BPD BALI",
                "ISUSED": "1",
                "alias": "BANK BALI",
            },
        ),
        expected_status=200,
        expected_engine_status="PASSED",
        use_ai=True,
    ),

    # --------------------------------------------------------------------------
    # 20. TC23-AC09 : Update NotFound
    # --------------------------------------------------------------------------
    TestCaseDefinition(
        id="TC23-AC09",
        ac_id="AC09",
        name="TC23-AC09 : DeleteNotFound (Update Missing Target)",
        description="Update negative test: Updating with missing attributes/target returns 404.",
        action="UpdateMS_BANK",
        payload=ACPayload(
            ac_id="AC09",
            action="UpdateMS_BANK",
            data={"KDBANK": "ABALIDBS"},
        ),
        expected_status=404,
        expected_engine_status="PASSED",
        use_ai=True,
    ),

    # --------------------------------------------------------------------------
    # 21. TC24-AC10 : Update Validation Check
    # --------------------------------------------------------------------------
    TestCaseDefinition(
        id="TC24-AC10",
        ac_id="AC10",
        name="TC24-AC10 : Update Validation Check",
        description="Update validation test: Passing empty NMBANK triggers HTTP 400 validation error.",
        action="UpdateMS_BANK",
        payload=ACPayload(
            ac_id="AC10",
            action="UpdateMS_BANK",
            data={"KDBANK": "BRINIDJA", "NMBANK": ""},
        ),
        expected_status=400,
        expected_engine_status="PASSED",
        use_ai=True,
    ),
]


def get_all_test_cases() -> List[TestCaseDefinition]:
    """Return all 21 Acceptance Criteria test cases."""
    return ALL_TEST_CASES


def get_test_case_by_id(tc_id: str) -> Optional[TestCaseDefinition]:
    """Find test case definition by ID."""
    for tc in ALL_TEST_CASES:
        if tc.id == tc_id or tc.name == tc_id:
            return tc
    return None


def export_registry_json(path: Optional[Path] = None) -> Path:
    """Export test case list to JSON file (ac_registry.json)."""
    target = path or (Path(__file__).parent / "ac_registry.json")
    data = [
        {
            "id": tc.id,
            "ac_id": tc.ac_id,
            "name": tc.name,
            "description": tc.description,
            "action": tc.action,
            "expected_status": tc.expected_status,
            "expected_engine_status": tc.expected_engine_status,
        }
        for tc in ALL_TEST_CASES
    ]
    target.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return target
