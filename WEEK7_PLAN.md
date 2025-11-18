# Week 7 Testing Plan - Low Coverage Router Modules

**Date**: January 2025  
**Goal**: Continue systematic router testing campaign  
**Target**: 4-5 modules with lowest coverage  
**Coverage Target**: 70-90% per module

---

## 🎯 Priority Targets (Based on Current Coverage)

### Selection Criteria
- Focus on `backend/api/routers/` modules
- Prioritize modules < 60% coverage
- Exclude modules being actively developed
- Consider module importance/usage

### Week 7 Target Modules

| Priority | Module | Current Coverage | Target | Estimated Time | Rationale |
|----------|--------|------------------|--------|----------------|-----------|
| **P1** | `wizard.py` | 59.26% | 90%+ | 2-3h | Small (25 stmts), quick win |
| **P2** | `active_deals.py` | 47.14% | 75%+ | 3-4h | CRUD operations, business logic |
| **P3** | `bots.py` | 45.35% | 75%+ | 4-5h | Bot lifecycle management |
| **P4** | `security.py` | 34.48% | 70%+ | 5-6h | Critical security module |

**Total Estimated Time**: 14-18 hours (3-4 days)

---

## 📊 Module Analysis

### P1: wizard.py (59.26% → 90%+)

**Current State**:
- Size: 25 statements
- Coverage: 59.26% (15/25 covered)
- Missing: 10 statements

**Endpoints**:
1. Strategy configuration wizard
2. Step-by-step backtest setup
3. Parameter validation

**Test Strategy**:
- Happy path: Complete wizard flow
- Step validation
- Invalid parameters
- Edge cases (partial completion)

**Estimated Tests**: 15-20 tests  
**Time**: 2-3 hours

---

### P2: active_deals.py (47.14% → 75%+)

**Current State**:
- Size: 62 statements  
- Coverage: 47.14% (29/62 covered)
- Missing: 33 statements

**Endpoints**:
1. `GET /active-deals` - List active deals
2. `POST /active-deals` - Create new deal
3. `GET /active-deals/{id}` - Get deal details
4. `PUT /active-deals/{id}` - Update deal
5. `DELETE /active-deals/{id}` - Close deal

**Test Strategy**:
- CRUD operations for each endpoint
- Authentication/authorization
- Data validation
- Deal state management
- Error handling

**Estimated Tests**: 25-30 tests  
**Time**: 3-4 hours

---

### P3: bots.py (45.35% → 75%+)

**Current State**:
- Size: 74 statements
- Coverage: 45.35% (35/74 covered)
- Missing: 39 statements

**Endpoints**:
1. `GET /bots` - List bots
2. `POST /bots` - Create bot
3. `GET /bots/{id}` - Get bot details
4. `PUT /bots/{id}` - Update bot configuration
5. `DELETE /bots/{id}` - Delete bot
6. `POST /bots/{id}/start` - Start bot
7. `POST /bots/{id}/stop` - Stop bot

**Test Strategy**:
- Bot lifecycle (create → configure → start → stop → delete)
- State transitions
- Multiple bots management
- Error scenarios (start already running bot, stop inactive bot)
- Configuration validation

**Estimated Tests**: 30-35 tests  
**Time**: 4-5 hours

---

### P4: security.py (34.48% → 70%+)

**Current State**:
- Size: 98 statements
- Coverage: 34.48% (34/98 covered)
- Missing: 64 statements

**Endpoints**:
1. API key management
2. Permission validation
3. Access control
4. Security audit logs

**Test Strategy**:
- API key CRUD operations
- Permission checks
- Role-based access control (RBAC)
- Security event logging
- Token validation
- Rate limiting integration

**Estimated Tests**: 35-40 tests  
**Time**: 5-6 hours

---

## ✅ Success Criteria

### Per-Module Requirements
- [ ] Coverage target met or exceeded
- [ ] All tests passing (100% success rate)
- [ ] Comprehensive test documentation
- [ ] Edge cases covered
- [ ] Error handling tested

### Week 7 Goals
- [ ] 4 modules tested with 70%+ coverage
- [ ] Average coverage > 75%
- [ ] ~120-130 total tests created
- [ ] Detailed report for each module
- [ ] Final Week 7 summary document

---

## 📋 Testing Patterns (From Week 6)

### Fixtures to Reuse
```python
@pytest.fixture
def client():
    """FastAPI test client"""
    return TestClient(app)

@pytest.fixture
def valid_auth_headers():
    """Valid authentication headers"""
    return {"Authorization": "Bearer valid_token"}

@pytest.fixture
def mock_db_session():
    """Mock database session"""
    session = MagicMock(spec=Session)
    # ... setup
    return session
```

### Test Class Organization
```python
class TestModuleEndpoint:
    """Test /api/module endpoint"""
    
    def test_list_success(self, client):
        """GET /module - successful list"""
        ...
    
    def test_create_success(self, client):
        """POST /module - successful creation"""
        ...
    
    def test_get_success(self, client):
        """GET /module/{id} - successful retrieval"""
        ...
    
    def test_update_success(self, client):
        """PUT /module/{id} - successful update"""
        ...
    
    def test_delete_success(self, client):
        """DELETE /module/{id} - successful deletion"""
        ...
    
    def test_validation_errors(self, client):
        """Test input validation"""
        ...
    
    def test_not_found(self, client):
        """Test 404 responses"""
        ...
    
    def test_unauthorized(self, client):
        """Test 401/403 responses"""
        ...
```

### Mock Data Patterns
```python
MOCK_BOT_CONFIG = {
    "id": 1,
    "name": "Test Bot",
    "strategy_id": 1,
    "symbol": "BTCUSDT",
    "timeframe": "1h",
    "status": "inactive",
    "config": {}
}
```

---

## 🚀 Week 7 Timeline

### Day 1: wizard.py (2-3 hours)
- Morning: Module analysis, test planning
- Afternoon: Test implementation (15-20 tests)
- Evening: Coverage verification, documentation

### Day 2: active_deals.py (3-4 hours)
- Morning: CRUD endpoint tests
- Afternoon: Error handling, edge cases
- Evening: Coverage check, report creation

### Day 3: bots.py (4-5 hours)
- Morning: Lifecycle tests (create, start, stop)
- Midday: State transition tests
- Afternoon: Error scenarios, edge cases
- Evening: Documentation

### Day 4: security.py (5-6 hours)
- Morning: API key management tests
- Midday: Permission/RBAC tests
- Afternoon: Security event logging
- Evening: Final coverage verification

### Day 5: Week 7 Summary (1-2 hours)
- Compile Week 7 results
- Update overall project coverage
- Create final summary report
- Plan Week 8 priorities

---

## 📊 Expected Outcomes

### Coverage Improvements
```
wizard.py:        59.26% → 90%+   (+30.74%)
active_deals.py:  47.14% → 75%+   (+27.86%)
bots.py:          45.35% → 75%+   (+29.65%)
security.py:      34.48% → 70%+   (+35.52%)

Average gain: ~30.94% per module
Total tests: ~120-130 new tests
```

### Quality Metrics
- All tests passing (100% success rate)
- Comprehensive edge case coverage
- Error handling validated
- Authentication/authorization tested
- Business logic verified

---

## 🔧 Tools & Infrastructure

### Testing Stack
- **pytest**: 8.4.2
- **pytest-cov**: 7.0.0
- **pytest-asyncio**: 1.2.0
- **FastAPI TestClient**: Built-in

### Coverage Commands
```bash
# Single module with coverage
pytest tests/backend/api/routers/test_wizard.py -v --cov=backend/api/routers/wizard --cov-report=term-missing

# All router tests
pytest tests/backend/api/routers/ --cov=backend/api/routers --cov-report=html

# Coverage report only
pytest --cov=backend/api/routers --cov-report=term-missing --co -q
```

### Quality Checks
```bash
# Run with verbose output
pytest tests/backend/api/routers/test_wizard.py -vv

# Run with failure details
pytest tests/backend/api/routers/test_wizard.py -v --tb=short

# Run specific test class
pytest tests/backend/api/routers/test_wizard.py::TestWizardEndpoint -v
```

---

## 📝 Deliverables

### Per Module
1. Test file: `tests/backend/api/routers/test_{module}.py`
2. Coverage report: Markdown document with metrics
3. Test documentation: Inline docstrings
4. Challenge notes: Issues encountered and resolutions

### Week 7 Summary
1. **WEEK7_FINAL_SUMMARY.md** - Comprehensive campaign report
2. **Coverage metrics** - Before/after comparison
3. **Lessons learned** - Best practices and insights
4. **Week 8 recommendations** - Next priorities

---

## 🎓 Lessons from Week 6

### Rate Limiting Fix
- ✅ Add "testclient" to middleware whitelists
- ✅ Check middleware configuration before complex workarounds
- ✅ Simple solutions often best

### Testing Efficiency
- Focus on happy paths first (70% of tests)
- Add error handling (20% of tests)
- Include edge cases (10% of tests)
- Small modules may have lower %/hour efficiency due to fixed overhead

### Mock Patterns
- Mock at API boundary, not deep in call stack
- Use consistent fixture patterns
- Create reusable mock data dictionaries
- Document mock behavior clearly

---

## 🎯 Week 7 Goals Summary

**Primary Objective**: Test 4 low-coverage router modules to 70-90% coverage

**Success Metrics**:
- ✅ 4 modules tested (wizard, active_deals, bots, security)
- ✅ Average coverage > 75%
- ✅ 120-130 total tests created
- ✅ 100% test success rate
- ✅ Comprehensive documentation

**Time Budget**: 14-18 hours (3-4 days)

**Expected Coverage Gain**: ~124 percentage points across 4 modules

---

*Plan created: January 2025*  
*Based on Week 6 campaign learnings*  
*Target start: Immediately after Week 6 completion*
