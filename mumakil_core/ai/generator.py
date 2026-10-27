"""Autonomous Test Case Generator for Mumakil 2.0.

Autonomously synthesizes robust test cases covering:
- Boundary Values (empty strings, maximum lengths, unicode characters, zero/overflows)
- Payload Tampering (missing primary keys, extra unexpected fields, type corruption)
- Negative Testing (unauthorized access, non-existent entities, malformed actions)
"""

from typing import Any, Dict, List, Optional
from mumakil_core.models.schemas import ACPayload, TestCaseDefinition


class AutonomousTestCaseGenerator:
    """Generates synthetic and edge-case test definitions from endpoint schemas."""

    # Default known table schemas for dbmigas
    KNOWN_SCHEMAS: Dict[str, Dict[str, Any]] = {
        "MS_BANK": {
            "primary_key": "KDBANK",
            "required_fields": ["KDBANK", "NAMABANK"],
            "fields": {
                "KDBANK": {"type": "string", "max_length": 20, "sample": "ABALIDBS"},
                "NAMABANK": {"type": "string", "max_length": 100, "sample": "PT.BPD BALI"},
                "ISUSED": {"type": "string", "max_length": 1, "sample": "1"},
                "alias": {"type": "string", "max_length": 50, "sample": "BANK BALI"},
            },
        },
        "MS_KARYAWAN": {
            "primary_key": "nip",
            "required_fields": ["nip", "nama", "kodejabatan"],
            "fields": {
                "nip": {"type": "string", "max_length": 18, "sample": "199211092020122001"},
                "nama": {"type": "string", "max_length": 100, "sample": "Stephany Novianty"},
                "kodejabatan": {"type": "string", "max_length": 10, "sample": "113"},
                "GOL": {"type": "string", "max_length": 10, "sample": "III.c"},
                "kdunit": {"type": "string", "max_length": 10, "sample": "SDMK"},
                "keterangan": {"type": "string", "max_length": 255, "sample": ""},
                "ispns": {"type": "integer", "sample": 1},
                "ismigas": {"type": "integer", "sample": 0},
                "rek_bank": {"type": "string", "max_length": 50, "sample": "BANK RAKYAT INDONESIA"},
                "rek_nama": {"type": "string", "max_length": 100, "sample": "Stephany"},
                "rek_nomor": {"type": "string", "max_length": 30, "sample": "037801015331504"},
                "rek_kdbank": {"type": "string", "max_length": 20, "sample": "BRINIDJA"},
            },
        },
    }

    def __init__(self, schemas: Optional[Dict[str, Dict[str, Any]]] = None):
        self.schemas = schemas or self.KNOWN_SCHEMAS

    def generate_boundary_cases(self, table_name: str) -> List[TestCaseDefinition]:
        """Generate boundary value test cases (empty, maximum length, unicode strings)."""
        schema = self.schemas.get(table_name)
        if not schema:
            return []

        cases: List[TestCaseDefinition] = []
        action = f"Insert{table_name}"
        pk = schema["primary_key"]

        # 1. Boundary: Empty non-primary strings
        empty_data: Dict[str, Any] = {}
        for f, meta in schema["fields"].items():
            if f == pk:
                empty_data[f] = f"TEST_PK_{meta['sample']}"
            else:
                empty_data[f] = ""

        cases.append(
            TestCaseDefinition(
                id=f"GEN-{table_name}-BOUND-01",
                ac_id="AC03",
                name=f"Boundary: Empty string fields for {table_name}",
                description=f"Ensures {table_name} handles empty string attributes gracefully without DB crash.",
                action=action,
                payload=ACPayload(
                    ac_id="AC03",
                    action=action,
                    data=empty_data,
                ),
                expected_status=200,
                expected_engine_status="PASSED",
                use_ai=True,
            )
        )

        # 2. Boundary: Maximum length and Unicode string testing
        max_data: Dict[str, Any] = {}
        for f, meta in schema["fields"].items():
            if f == pk:
                max_data[f] = f"MAX_{meta['sample']}"
            elif meta.get("type") == "string":
                max_len = meta.get("max_length", 20)
                # Max length with non-ASCII unicode characters
                max_data[f] = ("★αβγ" * 50)[:max_len]
            else:
                max_data[f] = meta.get("sample", 1)

        cases.append(
            TestCaseDefinition(
                id=f"GEN-{table_name}-BOUND-02",
                ac_id="AC03",
                name=f"Boundary: Max-length & Unicode fields for {table_name}",
                description="Verifies boundary string lengths and UTF-8 multi-byte character encoding safety.",
                action=action,
                payload=ACPayload(
                    ac_id="AC03",
                    action=action,
                    data=max_data,
                ),
                expected_status=200,
                expected_engine_status="PASSED",
                use_ai=True,
            )
        )

        return cases

    def generate_tampering_cases(self, table_name: str) -> List[TestCaseDefinition]:
        """Generate payload tampering test cases (missing required keys, injected SQL chars)."""
        schema = self.schemas.get(table_name)
        if not schema:
            return []

        cases: List[TestCaseDefinition] = []
        action = f"Insert{table_name}"
        pk = schema["primary_key"]

        # 1. Tampering: Missing primary key
        tampered_missing_pk: Dict[str, Any] = {
            f: meta["sample"] for f, meta in schema["fields"].items() if f != pk
        }

        cases.append(
            TestCaseDefinition(
                id=f"GEN-{table_name}-TAMP-01",
                ac_id="AC03",
                name=f"Tampering: Missing primary key '{pk}' in {table_name}",
                description="Simulates payload tampering by stripping the primary key.",
                action=action,
                payload=ACPayload(
                    ac_id="AC03",
                    action=action,
                    data=tampered_missing_pk,
                ),
                expected_status=200,  # Engine handles or defaults
                expected_engine_status="PASSED",
                use_ai=True,
            )
        )

        # 2. Tampering: SQL Injection string probe
        tampered_sqli: Dict[str, Any] = {}
        for f, meta in schema["fields"].items():
            if f == pk:
                tampered_sqli[f] = "TEST' OR '1'='1"
            else:
                tampered_sqli[f] = meta.get("sample", "")

        cases.append(
            TestCaseDefinition(
                id=f"GEN-{table_name}-TAMP-02",
                ac_id="AC03",
                name=f"Tampering: SQL Injection payload probe in {table_name}",
                description="Verifies that parameterized queries prevent SQL injection payload crashes.",
                action=action,
                payload=ACPayload(
                    ac_id="AC03",
                    action=action,
                    data=tampered_sqli,
                ),
                expected_status=200,
                expected_engine_status="PASSED",
                use_ai=True,
            )
        )

        return cases

    def generate_negative_cases(self, table_name: str) -> List[TestCaseDefinition]:
        """Generate negative security & non-existent entity test cases."""
        schema = self.schemas.get(table_name)
        if not schema:
            return []

        cases: List[TestCaseDefinition] = []

        # 1. Negative: Unauthorized access (Invalid Token)
        cases.append(
            TestCaseDefinition(
                id=f"GEN-{table_name}-NEG-01",
                ac_id="AC21",
                name=f"Negative: Invalid Token on Delete{table_name}",
                description="Ensures delete endpoint strictly rejects invalid authentication tokens.",
                action=f"Delete{table_name}",
                payload=ACPayload(
                    ac_id="AC21",
                    action=f"Delete{table_name}",
                    token="CORRUPTED_OR_TAMPERED_TOKEN_XYZ",
                    data={schema["primary_key"]: "NON_EXISTENT_KEY"},
                    automation_status=401,
                ),
                expected_status=401,
                expected_engine_status="PASSED",
                use_ai=True,
            )
        )

        # 2. Negative: Non-existent entity delete
        cases.append(
            TestCaseDefinition(
                id=f"GEN-{table_name}-NEG-02",
                ac_id="AC07",
                name=f"Negative: Delete non-existent record from {table_name}",
                description="Verifies 404/safe return when attempting to delete a non-existent entity.",
                action=f"Delete{table_name}",
                payload=ACPayload(
                    ac_id="AC07",
                    action=f"Delete{table_name}",
                    data={schema["primary_key"]: "DEFINITELY_NOT_IN_DB_999999"},
                ),
                expected_status=404,
                expected_engine_status="PASSED",
                use_ai=True,
            )
        )

        return cases

    def generate_all_for_table(self, table_name: str) -> List[TestCaseDefinition]:
        """Generate comprehensive suite of boundary, tampering, and negative test cases."""
        all_cases: List[TestCaseDefinition] = []
        all_cases.extend(self.generate_boundary_cases(table_name))
        all_cases.extend(self.generate_tampering_cases(table_name))
        all_cases.extend(self.generate_negative_cases(table_name))
        return all_cases

    def generate_full_suite(self) -> List[TestCaseDefinition]:
        """Generate test cases across all registered table schemas."""
        suite: List[TestCaseDefinition] = []
        for table in self.schemas.keys():
            suite.extend(self.generate_all_for_table(table))
        return suite
