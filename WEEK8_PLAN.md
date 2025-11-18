# Week 8 Testing Campaign: Low-Coverage Routers

**Start Date**: November 13, 2025  
**Status**: 📋 PLANNED  
**Goal**: Reach 70-90% coverage on 4 critical router modules

---

## 📊 Current Status (Post Week 7)

### ✅ Week 7 Completed (4/4 modules @ 100%)
```
wizard.py:        59.26% → 100% (41 tests) ✅
active_deals.py:  47.14% → 100% (41 tests) ✅  
bots.py:          45.35% → 100% (47 tests) ✅
security.py:      34.48% → 100% (42 tests) ✅

Total: 171 tests, ~9 hours
```

### 🎯 Week 8 Target Modules

Based on current coverage analysis (`pytest --co -q backend/`):

| Module | Coverage | Stmts | Priority | Reason |
|--------|----------|-------|----------|--------|
| **backtests.py** | 0% | 279 | 🔴 CRITICAL | Core backtest engine API |
| **optimizations.py** | 0% | 170 | 🔴 CRITICAL | Grid/WFO optimization |
| **health.py** | 0% | 114 | 🟡 HIGH | System monitoring |
| **marketdata.py** | 0% | 348 | 🔴 CRITICAL | Data ingestion |

**Estimated Total**: ~911 statements to cover  
**Estimated Tests**: ~150-180 tests  
**Estimated Time**: ~12-15 hours (3h per module)

---

## 📅 Week 8 Schedule

### Day 1: backtests.py (3-4 hours) 🔴 CRITICAL
**Module**: `backend/api/routers/backtests.py` (279 statements, 12 endpoints)

**Endpoints to Test**:
- `GET /` - List all backtests (pagination, filtering)
- `GET /{backtest_id}` - Get single backtest
- `POST /` - Create backtest
- `POST /mtf` - Multi-timeframe backtest (MTF engine)
- `PUT /{backtest_id}` - Update backtest
- `POST /{backtest_id}/claim` - Worker claim
- `POST /{backtest_id}/results` - Submit results
- `GET /{backtest_id}/trades` - Get trades
- `GET /{backtest_id}/export/{report_type}` - Export (CSV, JSON, PDF)
- `GET /{backtest_id}/charts/equity_curve`
- `GET /{backtest_id}/charts/drawdown_overlay`
- `GET /{backtest_id}/charts/pnl_distribution`

**Test Categories**:
1. **CRUD Operations** (40%):
   - Create backtest (success, validation errors)
   - List with pagination
   - Get by ID (found, not found)
   - Update (success, not found)

2. **MTF Engine** (20%):
   - Multi-timeframe backtest creation
   - Strategy config validation
   - Data integration

3. **Worker Queue** (15%):
   - Claim backtest (success, already claimed)
   - Submit results (valid, invalid)
   - Status transitions (pending → claimed → completed)

4. **Export & Charts** (15%):
   - CSV export
   - JSON export
   - PDF export (Plotly charts)
   - Equity curve chart
   - Drawdown chart
   - PnL distribution

5. **Edge Cases** (10%):
   - Invalid backtest_id format
   - Missing required fields
   - Concurrent claims (race condition)
   - Large result sets

**Estimated Tests**: 50-60 tests  
**Target Coverage**: 85-95%

---

### Day 2: optimizations.py (3-4 hours) 🔴 CRITICAL
**Module**: `backend/api/routers/optimizations.py` (170 statements, 9 endpoints)

**Endpoints to Test**:
- `GET /` - List optimizations
- `GET /{optimization_id}` - Get single optimization
- `POST /` - Create optimization
- `PUT /{optimization_id}` - Update optimization
- `GET /{optimization_id}/results` - Get optimization results
- `GET /{optimization_id}/best-params` - Get best parameters
- `POST /{optimization_id}/grid` - Grid search
- `POST /{optimization_id}/walk-forward` - Walk-forward optimization
- `POST /{optimization_id}/monte-carlo` - Monte Carlo simulation

**Test Categories**:
1. **CRUD Operations** (30%):
   - Create optimization (grid, WFO, monte carlo)
   - List with filters
   - Get by ID
   - Update status

2. **Grid Search** (25%):
   - Parameter grid generation
   - Parallel execution
   - Result aggregation
   - Best parameter selection

3. **Walk-Forward Optimization** (25%):
   - Window configuration (in-sample, out-of-sample)
   - Rolling window logic
   - Overfitting detection
   - Stability metrics

4. **Monte Carlo** (15%):
   - Random parameter sampling
   - Distribution analysis
   - Confidence intervals
   - Stress testing scenarios

5. **Edge Cases** (5%):
   - Invalid parameter ranges
   - Empty result sets
   - Timeout handling

**Estimated Tests**: 40-50 tests  
**Target Coverage**: 80-90%

---

### Day 3: health.py (2-3 hours) 🟡 HIGH
**Module**: `backend/api/routers/health.py` (114 statements, 6 endpoints)

**Endpoints to Test**:
- `GET /health` - Main health check
- `GET /health/bybit` - Bybit API connectivity
- `GET /health/ready` - Readiness probe (K8s)
- `GET /health/live` - Liveness probe (K8s)
- `GET /health/db_pool` - Database pool metrics
- `GET /health/metrics` - Prometheus metrics

**Test Categories**:
1. **Health Checks** (35%):
   - All services healthy (200)
   - Database down (503)
   - Redis down (503)
   - Bybit API down (503)
   - Partial degradation (200 with warnings)

2. **Kubernetes Probes** (25%):
   - Readiness probe (startup sequence)
   - Liveness probe (crash detection)
   - Graceful shutdown handling

3. **Database Pool** (20%):
   - Pool size metrics
   - Connection leak detection
   - High connection count warnings
   - Idle connection cleanup

4. **Prometheus Metrics** (15%):
   - Counter metrics
   - Gauge metrics
   - Histogram metrics
   - Metric format validation

5. **Edge Cases** (5%):
   - Timeout scenarios
   - Network partition simulation
   - Rapid health check requests

**Estimated Tests**: 30-35 tests  
**Target Coverage**: 75-85%

---

### Day 4: marketdata.py (4-5 hours) 🔴 CRITICAL
**Module**: `backend/api/routers/marketdata.py` (348 statements, 11 endpoints)

**Endpoints to Test**:
- `GET /bybit/klines` - Get historical klines
- `GET /bybit/klines/fetch` - Fetch fresh klines from Bybit
- `GET /bybit/recent-trades` - Recent trades
- `GET /bybit/klines/working` - Working set candles
- `GET /bybit/mtf` - Multi-timeframe data
- `POST /upload` - Upload CSV data
- `GET /uploads` - List uploads
- `DELETE /uploads/{upload_id}` - Delete upload
- `POST /uploads/{upload_id}/ingest` - Ingest uploaded data
- `POST /bybit/prime` - Prime database (backfill)
- `POST /bybit/reset` - Reset data

**Test Categories**:
1. **Data Retrieval** (30%):
   - Get klines (success, filters, pagination)
   - Fetch from Bybit (success, API errors)
   - Recent trades (real-time data)
   - Working set candles (active strategies)
   - MTF data (multiple timeframes)

2. **Data Upload** (25%):
   - CSV upload (valid format)
   - Invalid CSV (wrong columns, bad data)
   - File size limits
   - Duplicate detection

3. **Data Ingestion** (20%):
   - Ingest uploaded CSV
   - Data validation (timestamps, prices)
   - Duplicate handling
   - Transaction integrity

4. **Admin Operations** (15%):
   - Prime database (backfill historical data)
   - Reset data (cleanup)
   - Progress tracking
   - Bybit API rate limiting

5. **Edge Cases** (10%):
   - Missing data gaps
   - Timezone handling (UTC conversion)
   - Large date ranges
   - Corrupt CSV files

**Estimated Tests**: 55-65 tests  
**Target Coverage**: 80-90%

---

### Day 5: Week 8 Summary (1-2 hours)
- Compile Week 8 results
- Update overall project coverage
- Create final summary report
- Plan Week 9 priorities

---

## 📊 Expected Outcomes

### Coverage Improvements
```
backtests.py:      0% → 85%+   (+85%)    [279 stmts]
optimizations.py:  0% → 85%+   (+85%)    [170 stmts]
health.py:         0% → 80%+   (+80%)    [114 stmts]
marketdata.py:     0% → 85%+   (+85%)    [348 stmts]

Average gain: ~85% per module
Total statements: 911 (from 0% to ~85% = 774 new covered)
Total tests: ~175-210 new tests
```

### Quality Metrics
- All tests passing (100% success rate)
- Critical path coverage (backtests, optimizations, marketdata)
- Health monitoring validated
- Integration with MTF engine tested
- Export functionality verified

---

## 🔧 Tools & Infrastructure

### Testing Stack
- **pytest**: 8.4.2
- **pytest-cov**: 7.0.0
- **pytest-asyncio**: 1.2.0
- **FastAPI TestClient**: Built-in
- **Shared conftest.py**: From Week 7

### Coverage Commands
```bash
# Day 1: backtests.py
pytest tests/backend/api/routers/test_backtests.py -v --cov=backend/api/routers/backtests --cov-report=term-missing

# Day 2: optimizations.py
pytest tests/backend/api/routers/test_optimizations.py -v --cov=backend/api/routers/optimizations --cov-report=term-missing

# Day 3: health.py
pytest tests/backend/api/routers/test_health.py -v --cov=backend/api/routers/health --cov-report=term-missing

# Day 4: marketdata.py
pytest tests/backend/api/routers/test_marketdata.py -v --cov=backend/api/routers/marketdata --cov-report=term-missing

# All Week 8 tests
pytest tests/backend/api/routers/ --cov=backend/api/routers --cov-report=html
```

---

## 📝 Deliverables

### Per Module
1. Test file: `tests/backend/api/routers/test_{module}.py`
2. Coverage report: Daily progress update
3. Test documentation: Inline docstrings
4. Challenge notes: Issues and resolutions

### Week 8 Summary
1. **WEEK8_FINAL_SUMMARY.md** - Comprehensive campaign report
2. **Coverage metrics** - Before/after comparison
3. **Lessons learned** - Best practices
4. **Week 9 recommendations** - Next priorities

---

## 🎓 Lessons from Week 7 (Applied to Week 8)

### Testing Patterns
1. **Shared Fixtures**: Reuse `client` fixture from conftest.py
2. **Mock External APIs**: Mock Bybit API calls, database sessions
3. **Test Structure**:
   - CRUD: 30-40% of tests
   - Business Logic: 30-40% of tests
   - Edge Cases: 20-30% of tests
4. **Coverage First**: Aim for 70%+ before refining

### Common Pitfalls
- ✅ Verify router registration paths (no duplicate `/security/`)
- ✅ Mock at correct import location (not router module)
- ✅ Test HTTP-only cookies separately
- ✅ Validate response schemas
- ✅ Check error status codes (400, 401, 403, 404, 500)

### Efficiency Tips
- Start with happy paths (quick coverage boost)
- Add error handling tests next
- Finish with edge cases
- Run coverage after each test class (not each test)

---

## 🚀 Week 9+ Roadmap (Preview)

### Week 9 Candidates (Next 4 modules):
1. **admin.py** (304 stmts, 0%) - Backfill, archive, restore
2. **queue.py** (100 stmts, 0%) - Redis queue management
3. **tournament.py** (139 stmts, 0%) - Strategy competitions
4. **sandbox.py** (113 stmts, 0%) - Secure code execution

### Week 10+ Candidates:
- **anomaly_detection.py** (210 stmts, 0%) - ML anomaly detection
- **automl.py** (138 stmts, 0%) - AutoML with Optuna
- **lstm_predictions.py** (145 stmts, 0%) - LSTM queue prediction
- **reasoning.py** (165 stmts, 0%) - AI reasoning endpoints
- **ab_testing.py** (69 stmts, 0%) - A/B testing framework

---

## 📈 Project Impact

### Current Overall Coverage (Estimated):
```
Backend Total: 16,631 statements
Current Coverage: ~3.45% (573 statements)
Week 7 Added: ~400 statements (wizard, active_deals, bots, security)

After Week 7: ~973 statements covered (~5.85%)
```

### After Week 8 (Projected):
```
Week 8 Adding: ~774 statements (backtests, optimizations, health, marketdata)
Total Covered: ~1,747 statements (10.5%)

Gain: +5.65% overall backend coverage 🚀
```

### After Week 9 (Projected):
```
Week 9 Adding: ~656 statements (admin, queue, tournament, sandbox)
Total Covered: ~2,403 statements (14.5%)

Cumulative Gain: +11.05% over 3 weeks
```

---

## 🎯 Success Criteria (Week 8)

### Coverage Goals:
- ✅ backtests.py: ≥ 85% (target: 90%)
- ✅ optimizations.py: ≥ 80% (target: 85%)
- ✅ health.py: ≥ 75% (target: 80%)
- ✅ marketdata.py: ≥ 80% (target: 85%)

### Quality Goals:
- ✅ All tests passing (100% success rate)
- ✅ No test flakiness
- ✅ Comprehensive error handling
- ✅ Integration with existing infrastructure

### Documentation Goals:
- ✅ Daily progress reports
- ✅ Week 8 final summary
- ✅ Updated TESTING_CAMPAIGN_STATUS.md
- ✅ Week 9 planning document

---

## ⚠️ Known Risks

### Technical Risks:
1. **MTF Engine Integration**: Multi-timeframe backtest testing may be complex
2. **Plotly Charts**: PDF export tests may require additional mocking
3. **Bybit API**: Rate limiting may affect marketdata tests
4. **Database Pool**: Health tests may need connection pool mocking

### Mitigation Strategies:
1. Mock MTFBacktestEngine for unit tests (integration tests separate)
2. Mock Plotly chart generation, validate structure only
3. Mock all Bybit API calls (use recorded responses)
4. Mock database pool metrics (use test data)

### Time Risks:
1. **backtests.py**: Large module (279 stmts) may take 4-5 hours
2. **marketdata.py**: Complex data ingestion may take 5-6 hours

**Mitigation**: Break into 2-day sprints if needed, prioritize critical paths

---

## 📚 References

### Week 7 Documentation:
- `WEEK7_DAY1_WIZARD_COMPLETE.md` - Pattern established
- `WEEK7_DAY2_ACTIVE_DEALS_COMPLETE.md` - CRUD pattern
- `WEEK7_DAY3_BOTS_COMPLETE.md` - Lifecycle management
- `WEEK7_DAY4_SECURITY_COMPLETE.md` - Auth + security pattern

### Testing Infrastructure:
- `tests/backend/api/routers/conftest.py` - Shared fixtures
- `.coveragerc` - Coverage configuration
- `pytest.ini` - Pytest settings

### Module Documentation:
- `backend/api/routers/backtests.py` - Backtest endpoints
- `backend/api/routers/optimizations.py` - Optimization endpoints
- `backend/api/routers/health.py` - Health check endpoints
- `backend/api/routers/marketdata.py` - Market data endpoints

---

**Created**: November 13, 2025  
**Status**: 📋 PLANNED  
**Ready to Start**: Day 1 (backtests.py)
