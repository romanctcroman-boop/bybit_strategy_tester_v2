# 🔧 Agent Infrastructure Modernization Plan

> **Created:** 2026-02-11  
> **Based on:** Engineering audit by 3 LLM agents (DeepSeek, Qwen, Perplexity)  
> **Scope:** `backend/agents/` — 27 files, 16,127 LOC  
> **Average Score:** 6.73/10 (DeepSeek 6.5, Qwen 7.5, Perplexity 6.2)

---

## 📊 Cross-Agent Consensus Matrix

| Category           | DeepSeek | Qwen | Perplexity | **Avg** | **Consensus** |
| ------------------ | -------- | ---- | ---------- | ------- | ------------- |
| Architecture       | 6        | 7    | 5          | **6.0** | ⚠️ Needs work |
| LLM Connections    | 7        | 8    | 7          | **7.3** | ✅ Good       |
| Prompt Engineering | 7        | 6    | 8          | **7.0** | ✅ Good       |
| Security           | 6        | 7    | 7          | **6.7** | ⚠️ Adequate   |
| Memory             | 4        | 5    | 4          | **4.3** | 🔴 Critical   |
| Consensus System   | 8        | 8    | 8          | **8.0** | ✅ Strong     |
| Testing            | 3        | 4    | 2          | **3.0** | 🔴 Critical   |
| Code Quality       | 7        | 7    | 4          | **6.0** | ⚠️ Needs work |
| Scalability        | 5        | 6    | 6          | **5.7** | ⚠️ Needs work |

### Key Observations

- **Testing (3.0)** and **Memory (4.3)** are critical bottlenecks — all 3 agents agree
- **Consensus system (8.0)** is the strongest module — unanimous praise
- **LLM Connections (7.3)** and **Prompt Engineering (7.0)** are solid but improvable
- Biggest disagreement: Code Quality (Perplexity scored 4 vs others' 7) — Perplexity focused on structural issues

---

## 🔴 Critical Issues — All 3 Agents Agree

### Issue #1: `unified_agent_interface.py` God-Class (1875 LOC)

**Severity:** HIGH | **Agreement:** 3/3 agents | **Priority:** P0

| Agent      | Diagnosis                                                                |
| ---------- | ------------------------------------------------------------------------ |
| DeepSeek   | "Massive monolithic file with multiple responsibilities. Violates SRP."  |
| Qwen       | "Zero test coverage for fallback routing, key rotation, MCP switching."  |
| Perplexity | "1875 LOC god-class. Duplicates APIKey class already in key_manager.py." |

**Proposed Fix:**

```
unified_agent_interface.py (1875 LOC)
  ├── llm/client_deepseek.py    (~200 LOC) — DeepSeek-specific client
  ├── llm/client_qwen.py        (~200 LOC) — Qwen-specific client
  ├── llm/client_perplexity.py  (~200 LOC) — Perplexity-specific client
  ├── orchestrator.py           (~300 LOC) — Routing, fallback, orchestration
  ├── health_monitor.py         (~150 LOC) — Health checks, diagnostics
  └── agent_interface.py        (~300 LOC) — Public API, thin facade
```

**Effort:** Large (3-5 days) | **Impact:** High

---

### Issue #2: Zero Test Coverage for 28K LOC

**Severity:** HIGH | **Agreement:** 3/3 agents | **Priority:** P0

| Agent      | Diagnosis                                                      |
| ---------- | -------------------------------------------------------------- |
| DeepSeek   | "No test files. Critical systems lack unit tests. Target 70%+" |
| Qwen       | "Zero coverage. No mocks, no fixtures, no CI pipeline."        |
| Perplexity | "No visible tests in 28K LOC. Target 80%+"                     |

**Proposed Structure:**

```
tests/
  agents/
    unit/
      test_api_key_pool.py        — Key rotation, pool exhaustion
      test_circuit_breaker.py     — State transitions, recovery
      test_prompt_guard.py        — Injection detection, false positives
      test_response_parser.py     — JSON/markdown parsing, edge cases
      test_rate_limiter.py        — Token bucket, rate enforcement
      test_key_manager.py         — Encryption, decryption, None handling
      test_prompt_optimizer.py    — Token reduction, metric filtering
    integration/
      test_llm_fallback.py        — Provider failure → fallback routing
      test_consensus_flow.py      — Full deliberation → consensus
      test_memory_persistence.py  — Save/load/TTL/eviction
    e2e/
      test_agent_workflow.py      — Complete agent task execution
```

**Effort:** Large (1-2 weeks) | **Impact:** High

---

### Issue #3: Memory System — No Persistence, No Concurrency

**Severity:** HIGH | **Agreement:** 3/3 agents | **Priority:** P1

| Agent      | Diagnosis                                                                                   |
| ---------- | ------------------------------------------------------------------------------------------- |
| DeepSeek   | "File-based JSON storage, no concurrency control, no TTL/cleanup."                          |
| Qwen       | "All memory tiers in-memory only. Data loss on restart. vector_store.py exists but unused." |
| Perplexity | "File-based memory won't scale. Replace with Redis/memcached."                              |

**Proposed Fix (2 phases):**

1. **Phase A (quick win):** SQLite-backed persistence for `HierarchicalMemory` with TTL and LRU eviction
2. **Phase B (optional):** Redis adapter for multi-node deployment

**Effort:** Medium (2-3 days for Phase A) | **Impact:** High

---

## ⚠️ Significant Issues — 2/3 Agents Agree

### Issue #4: `APIKey` Class Duplicated 3x

**Agents:** DeepSeek (implied), Perplexity (explicit)

- `unified_agent_interface.py` — has its own APIKey
- `key_manager.py` — has APIKey with decryption
- `api_key_pool.py` — has APIKey with pool management

**Fix:** Single source of truth in `models.py`, delete duplicates.  
**Effort:** Small (2-4 hours) | **Impact:** Medium

### Issue #5: Mixed Russian/English in Code

**Agents:** DeepSeek, Perplexity

- `models.py`, various docstrings have Russian comments
- Reduces maintainability for international collaboration

**Fix:** Standardize to English. Run automated scan + manual review.  
**Effort:** Small (1-2 hours) | **Impact:** Low-Medium

### Issue #6: `connections.py` Oversized (969 LOC)

**Agents:** Perplexity (explicit), DeepSeek (implied via RateLimiter issues)

**Fix:** Split into `connections/base.py`, `connections/rate_limiter.py`, `connections/models.py`  
**Effort:** Medium (1-2 days) | **Impact:** Medium

---

## 📋 Unique Insights by Agent

### DeepSeek Only

- **Dead letter queue with retry policies** — failed LLM calls should be queued for retry
- **Cost tracking per agent** — no budget alerts or spend monitoring
- **Configuration validation at startup** — no fail-fast on missing config

### Qwen Only

- **Circular import risk** — `unified_agent_interface.py` ↔ `key_manager.py` ↔ `api_key_pool.py` ↔ `circuit_breaker_manager.py` all reference each other via lazy imports
- **Token budgeting in RateLimiter** — currently tracks only request count, not tokens. Needs `tiktoken` integration
- **PromptGuard semantic jailbreaks** — regex-only is vulnerable; needs LLM-based classifier fallback
- **Pydantic model versioning** — no schema migration for `models.py`
- **Hardcoded thresholds in templates.py** — values like "Max Drawdown < 15%" should be template variables

### Perplexity Only

- **src/ layout migration** — `backend/agents/` should follow Python packaging best practices
- **pre-commit hooks** — enforce `black`, `isort`, `mypy`, `ruff` before commit
- **Docker/K8s deployment manifests** — no container orchestration for agents

---

## 🏗️ Modernization Roadmap

### Phase 1: Foundation (Week 1-2) — P0 Items

| #   | Task                                                        | Source              | Effort | Impact    |
| --- | ----------------------------------------------------------- | ------------------- | ------ | --------- |
| 1.1 | Split `unified_agent_interface.py` into 5-6 focused modules | All 3               | Large  | 🟢 High   |
| 1.2 | Consolidate `APIKey` into single `models.py`                | Perplexity+DeepSeek | Small  | 🟡 Medium |
| 1.3 | Create pytest structure with 20+ critical tests             | All 3               | Large  | 🟢 High   |
| 1.4 | Split `connections.py` into submodules                      | Perplexity+DeepSeek | Medium | 🟡 Medium |
| 1.5 | Standardize English-only comments                           | DeepSeek+Perplexity | Small  | 🟡 Medium |

**Success Criteria:** No file > 500 LOC, 50+ test cases, 0 duplicate classes

### Phase 2: Reliability (Week 3-4) — P1 Items

| #   | Task                                                   | Source              | Effort | Impact    |
| --- | ------------------------------------------------------ | ------------------- | ------ | --------- |
| 2.1 | SQLite-backed `HierarchicalMemory` with TTL            | All 3               | Medium | 🟢 High   |
| 2.2 | Token-aware `RateLimiter` (tiktoken integration)       | Qwen                | Small  | 🟢 High   |
| 2.3 | Structured logging with correlation IDs                | DeepSeek+Perplexity | Small  | 🟢 High   |
| 2.4 | Resolve circular imports (dependency injection)        | Qwen                | Medium | 🟡 Medium |
| 2.5 | Template variables for hardcoded thresholds            | Qwen                | Small  | 🟡 Medium |
| 2.6 | PromptGuard semantic fallback (lightweight classifier) | Qwen                | Medium | 🟡 Medium |
| 2.7 | Configuration validation at startup                    | DeepSeek            | Small  | 🟡 Medium |

**Success Criteria:** Memory persists across restarts, rate limiting tracks tokens, all logs have request IDs

### Phase 3: Scale & Quality (Month 2) — P2 Items

| #   | Task                                      | Source              | Effort | Impact    |
| --- | ----------------------------------------- | ------------------- | ------ | --------- |
| 3.1 | Cost tracking and budget alerts per agent | DeepSeek            | Medium | 🟡 Medium |
| 3.2 | A/B testing framework for prompts         | DeepSeek+Qwen       | Medium | 🟡 Medium |
| 3.3 | Pre-commit hooks (ruff, mypy enforcement) | Perplexity          | Small  | 🟡 Medium |
| 3.4 | Secret rotation automation                | DeepSeek            | Medium | 🟡 Medium |
| 3.5 | Load testing suite for API key rotation   | DeepSeek+Qwen       | Medium | 🟡 Medium |
| 3.6 | Dead letter queue for failed LLM calls    | DeepSeek            | Medium | 🟡 Medium |
| 3.7 | OpenTelemetry distributed tracing         | DeepSeek+Perplexity | Medium | 🟡 Medium |

**Success Criteria:** Cost dashboards active, prompt versions tracked, tracing across agent calls

---

## 📈 Expected Score Improvement

| Category           | Current Avg | Target (Phase 1) | Target (Phase 2) | Target (Phase 3) |
| ------------------ | ----------- | ---------------- | ---------------- | ---------------- |
| Architecture       | 6.0         | **8.0**          | 8.5              | 9.0              |
| LLM Connections    | 7.3         | 7.5              | **8.5**          | 9.0              |
| Prompt Engineering | 7.0         | 7.0              | **8.0**          | 8.5              |
| Security           | 6.7         | 7.0              | **8.0**          | 8.5              |
| Memory             | 4.3         | 4.5              | **7.5**          | 8.0              |
| Consensus          | 8.0         | 8.0              | 8.0              | **8.5**          |
| Testing            | 3.0         | **6.5**          | 7.5              | 8.5              |
| Code Quality       | 6.0         | **8.0**          | 8.5              | 9.0              |
| Scalability        | 5.7         | 6.0              | **7.5**          | 8.5              |
| **Overall**        | **6.0**     | **7.0**          | **7.8**          | **8.6**          |

---

## 🎯 Agreed Strengths (Do NOT Refactor)

All 3 agents unanimously praised these — preserve and extend:

1. **Consensus System (8.0)** — Multi-agent deliberation with structured signal exchange
2. **LLM Provider Abstraction** — Good connection pooling, circuit breakers, adaptive retries
3. **Prompt Engineering Stack** — Context builder, templating, parsing, optimization
4. **Security Layers** — Prompt guard, output validator, key encryption, rate limiting
5. **MCP Tool Registry** — Auto-schema generation, tool introspection

---

## 📊 Audit Metadata

| Metric                  | Value         |
| ----------------------- | ------------- |
| Total audit time        | 105.6 seconds |
| Total tokens consumed   | 70,791        |
| Total prompt tokens     | 67,095        |
| Total completion tokens | 3,696         |
| Avg latency per agent   | 31.9s         |
| Files audited           | 27            |
| LOC audited             | 16,127        |
| Audit date              | 2026-02-11    |

---

_Generated by cross-referencing engineering audits from DeepSeek (deepseek-chat), Qwen (qwen-plus), and Perplexity (sonar-pro). See `engineering_audit_results.json` for raw data._
