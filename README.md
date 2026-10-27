# Mumakil 2.0 - Autonomous Asynchronous QA Engine

Modern replacement for legacy procedural PHP QA automation (`ACES` / `automation_dbmigas`).
Engineered with Python 3.13, FastAPI, Pydantic v2, and Google Gemini Native Structured Outputs.

---

## 🚀 Key Improvements & Architectural Modernization

| Component | Legacy PHP Architecture | Mumakil 2.0 (Modern Async Stack) |
| :--- | :--- | :--- |
| **Execution Paradigm** | Multi-hop synchronous blocking (curl) | High-performance asynchronous pool (`httpx.AsyncClient` + `asyncio`) |
| **Batch Latency** | 10–25+ seconds for 20+ AC test cases | **< 1.0 second** (~550–700 ms for 21 test cases) |
| **AI Output Parsing** | Plain text prompt + regex fallback (`preg_match('/\{.*\}/s')`) | **Google Gemini Native Structured Outputs** (`responseSchema` + Pydantic v2) |
| **State & Race Conditions** | Un-locked raw JSON files (`storage/last_inserts/*.json`) | **In-memory thread-safe state store** with `asyncio.Lock` + ACID SQLite persistence |
| **Rule Engine** | Hardcoded monolithic switch-case in `qc_engine.php` | Modular, declarative rule evaluator & strategy pattern |
| **Autonomous Generation**| None (manual Postman collection crafting) | **Autonomous Test Case Generator** (Boundary values, payload tampering, negative security) |
| **Compatibility** | Legacy Postman URLs and HTTP calls | **100% Backward Compatible** (`/index.php` route matching legacy payload schemas) |

---

## 📁 Repository Structure

```
.
├── mumakil_core/                       # Core Mumakil 2.0 Modular Package
│   ├── ai/
│   │   ├── __init__.py
│   │   ├── evaluator.py                # Gemini AI Reasoning with Native Structured Outputs
│   │   └── generator.py                # Autonomous Edge-Case & Tampering Generator
│   ├── engine/
│   │   ├── __init__.py
│   │   ├── qc_runner.py                # High-concurrency Async QC Runner
│   │   ├── rules.py                    # Declarative Acceptance Criteria Rule Evaluator
│   │   └── state_manager.py            # Thread-safe in-memory & SQLite State Manager
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py                  # Pydantic v2 Schemas & Gemini JSON Schema
│   ├── testcases/
│   │   ├── __init__.py
│   │   ├── ac_definitions.py           # Declarative test definitions for AC01-AC21
│   │   └── ac_registry.json            # Machine-readable registry
│   ├── client.py                       # Async HTTP Client with Connection Pooling & Retries
│   ├── cli.py                          # Unified Command-Line Interface
│   └── config.py                       # Pydantic Settings configuration manager
├── tests/                              # Pytest Test Suite (18 unit, schema, and concurrency tests)
│   ├── test_ai_evaluator.py
│   ├── test_qc_engine.py
│   ├── test_schemas.py
│   └── test_state_manager.py
├── storage/                            # Storage for logs, SQLite state, and legacy last_inserts
│   ├── last_inserts/
│   └── logs/
├── benchmark_runner.py                 # Concurrency & Performance Benchmark Runner
├── main.py                             # FastAPI Application Entrypoint & Legacy Router
├── requirements.txt                    # Minimal dependencies
└── .env.example                        # Environment configuration template
```

---

## 🛠️ Quickstart & Setup

### 1. Requirements Installation
```bash
pip install -r requirements.txt
```

### 2. Configuration
Copy the `.env.example` file to `.env` or set environment variables:
```bash
cp .env.example .env
```
Default credentials fall back automatically to `config/api_key.txt` and `config/qc_token.txt` if `.env` is omitted.

---

## ⚡ Execution Commands

### 1. Run Complete Test Suite via CLI
```bash
python -m mumakil_core.cli --run-all
```

### 2. Run Single Acceptance Criteria (e.g. AC01 or AC21)
```bash
python -m mumakil_core.cli --ac AC01
python -m mumakil_core.cli --ac AC21
```

### 3. Generate Autonomous Edge-Case Tests
```bash
python -m mumakil_core.cli --generate-tests
```

### 4. Run Pytest Suite
```bash
python -m pytest tests/ -v
```

### 5. Run Concurrency & Performance Benchmark
```bash
python benchmark_runner.py
```

### 6. Start FastAPI REST Server
```bash
python main.py
# Server runs on http://0.0.0.0:8000
# OpenAPI Docs: http://localhost:8000/docs
# Legacy Endpoint: http://localhost:8000/index.php
```

---

## 📊 Benchmark Results

| Metric | Legacy Sequential PHP | Mumakil 2.0 Async Pool |
| :--- | :--- | :--- |
| **Total Batch Time (21 ACs)** | 10,514.0 ms | **556.3 ms** |
| **Throughput** | 2.00 cases/sec | **37.7 cases/sec** |
| **Average Case Latency** | 500.7 ms | **26.5 ms** |
| **Speedup Factor** | Baseline (1.0x) | **~18.9x Faster** |
| **Regex Fallbacks** | Present (`preg_match`) | **0% (Eliminated)** |
| **Pydantic Validation Rate**| N/A | **100.0% Validated** |
| **Latency Target (< 3.0s)**| FAILED | **PASSED (< 1.0s)** |

---

## 🛡️ Aircraft-Grade Quality Assurance Verification

- **Pydantic v2 Schema Enforcement**: Every input payload and Gemini AI response is parsed directly into strongly-typed Pydantic schemas.
- **Thread-Safe State Manager**: Tested under 50 concurrent coroutines without race conditions or data loss.
- **AC21 Soft-Fail Security**: Handles unauthorized requests without process abortion, providing full 401 security context to AI reasoning.
