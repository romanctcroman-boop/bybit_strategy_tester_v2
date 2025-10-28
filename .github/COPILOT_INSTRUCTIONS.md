# GitHub Copilot Instructions for bybit_strategy_tester_v2

## 🤖 Multi-Agent Workflow (Copilot + External Research)

### **Agent Roles:**
1. **GitHub Copilot (You)** = Task Management + Code Implementation + Testing
2. **External Research (User)** = Best Practices + Architecture Decisions + Security Analysis

### **Strict Routing Rules:**
- **ALL tasks** MUST start with GitHub Issue creation by Copilot
- **Complex decisions** require user to consult external research (Perplexity, GPT-4, etc.)
- **Code implementation** only after research approval
- **Testing** mandatory before marking task complete

---

## 🎯 Project Overview
This is a **Bybit trading strategy backtesting system** with:
- **Backend**: FastAPI + Python 3.13 + PostgreSQL
- **Frontend**: React 18 + TypeScript + Material-UI
- **Testing**: pytest (200+ tests, 98%+ passing)

## 📋 Development Workflow

### 1. **Task Management**
- **ALL tasks MUST be tracked in GitHub Issues**
- Use labels: `bug`, `feature`, `enhancement`, `documentation`, `anomaly`
- Prioritize using milestones: `High Priority Anomalies`, `Medium Priority`, `Low Priority`
- Link commits to issues: `Fixes #123` or `Relates to #456`

### 2. **Code Analysis & Research**
For complex decisions, research best practices:
- **Prompt**: "Research best practices for [topic]"
- **Prompt**: "Analyze pros/cons of [approach A] vs [approach B]"
- **Prompt**: "Find similar implementations in open-source projects"

### 3. **Testing Requirements**
- **Test coverage required**: Minimum 80%
- **Test files naming**: `test_*.py` in `tests/` directory
- **Run tests before commit**: `py -3.13 -m pytest tests/ -v`

### 4. **Code Quality Standards**
```python
# ✅ Good: Type hints required
def calculate_pnl(
    entry_price: float,
    exit_price: float,
    position_size: float
) -> float:
    return (exit_price - entry_price) * position_size

# ❌ Bad: No type hints
def calculate_pnl(entry_price, exit_price, position_size):
    return (exit_price - entry_price) * position_size
```

### 5. **Current Priorities**

#### **High Priority Anomalies (Issues #4-7):**
1. **Position Sizing** - implement risk-based position sizing
2. **Signal Exit Logic** - fix early exits on pullbacks
3. **Buy & Hold Benchmark** - add comparison calculations
4. **Margin Calls** - simulate liquidations in backtests

#### **Completed Tasks:**
- ✅ Anomaly #1: Code Consolidation
- ✅ Anomaly #2: RBAC Implementation
- ✅ Anomaly #3: DataManager Refactoring
- ✅ MCP Integration (100% tests passing)

## 🔍 Research & Analysis Prompts

### When to Research:
```markdown
User: "Implement position sizing for backtests"

✅ Good Response:
1. "Let me research common position sizing algorithms used in trading systems..."
2. Create GitHub Issue: "Feature: Risk-based Position Sizing"
3. Analyze current codebase for integration points
4. Propose implementation with pros/cons
5. Implement with tests
6. Link PR to issue

❌ Bad Response:
"Here's the code for position sizing: [code]"
(No research, no issue, no testing)
```

## 📝 Documentation Standards

### Code Comments:
```python
# ✅ Good: Explains WHY, not WHAT
# Use VWAP for exit to avoid slippage on large positions
exit_price = calculate_vwap(trades[-100:])

# ❌ Bad: Explains WHAT (obvious from code)
# Calculate exit price using VWAP
exit_price = calculate_vwap(trades[-100:])
```

### Commit Messages:
```bash
# ✅ Good
feat: Add risk-based position sizing algorithm
Fixes #4

- Implement Kelly Criterion for position sizing
- Add tests for edge cases (zero volatility, negative returns)
- Update documentation in STRATEGY_GUIDE.md

# ❌ Bad
fix bug
```

## 🧪 Testing Workflow

### Before Committing:
```bash
# 1. Run specific test file
py -3.13 -m pytest tests/test_position_sizing.py -v

# 2. Run all tests
py -3.13 -m pytest tests/ -v

# 3. Check coverage
py -3.13 -m pytest --cov=backend --cov-report=term-missing
```

### Test Structure:
```python
def test_position_sizing_with_kelly_criterion():
    """Test Kelly Criterion position sizing with 60% win rate."""
    # Arrange
    win_rate = 0.6
    avg_win = 150
    avg_loss = 100
    capital = 10000
    
    # Act
    position_size = calculate_kelly_position(
        win_rate, avg_win, avg_loss, capital
    )
    
    # Assert
    assert 0 < position_size < capital * 0.25  # Kelly never > 25% of capital
    assert position_size == pytest.approx(1200, rel=0.01)
```

## 🔐 Security & Safety

### Database Queries:
```python
# ✅ Good: Parameterized query
query = "SELECT * FROM backtests WHERE user_id = :user_id"
result = db.execute(query, {"user_id": user_id})

# ❌ Bad: SQL injection risk
query = f"SELECT * FROM backtests WHERE user_id = {user_id}"
result = db.execute(query)
```

### API Endpoints:
```python
# ✅ Good: RBAC decorator
@router.post("/optimizations/start")
@require_access(AccessLevel.ADVANCED)
async def start_optimization(...):
    ...

# ❌ Bad: No access control
@router.post("/optimizations/start")
async def start_optimization(...):
    ...
```

## 🎨 Frontend Standards

### Component Structure:
```tsx
// ✅ Good: Type-safe props
interface BacktestDetailProps {
  backtestId: number;
  onClose: () => void;
}

export const BacktestDetailPage: React.FC<BacktestDetailProps> = ({
  backtestId,
  onClose
}) => {
  // ...
};

// ❌ Bad: No type safety
export const BacktestDetailPage = ({ backtestId, onClose }) => {
  // ...
};
```

## 🚀 Deployment Checklist

Before marking a feature as complete:
- [ ] Tests passing (100%)
- [ ] Documentation updated
- [ ] GitHub Issue linked
- [ ] Code reviewed (self-review minimum)
- [ ] No console errors in browser
- [ ] No pytest warnings
- [ ] Type hints added (Python)
- [ ] TypeScript types correct (Frontend)

---

## 💡 Example Workflow

```markdown
User: "Fix position sizing - positions are too large and get liquidated"

Copilot Workflow:
1. 🔍 Research: "Best practices for position sizing in crypto trading"
2. 📝 Create Issue: "Bug: Position sizes exceed risk tolerance #123"
3. 🔬 Analyze: Check current position_size calculation in backtest_engine.py
4. 💡 Propose: 
   - Option A: Fixed fractional sizing (2% per trade)
   - Option B: Kelly Criterion (optimal growth)
   - Option C: Volatility-based sizing (ATR-based)
5. 🛠️ Implement: Option B with fallback to Option A
6. ✅ Test: Write test_position_sizing.py with 10+ test cases
7. 📊 Validate: Run backtest on historical data
8. 🎉 PR: "feat: Implement Kelly Criterion position sizing" (Fixes #123)
```

---

## 📚 Resources

- Technical Specification: `ТЕХНИЧЕСКОЕ ЗАДАНИЕ.md`
- Data Types: `Типы данных.md`
- API Notes: `docs/API_NOTES.md`
- MCP Quickstart: `MCP_QUICKSTART.md`

---

## ⚠️ Common Mistakes to Avoid

1. ❌ **NO direct code without research** for complex features
2. ❌ **NO untested code** - minimum 1 test per function
3. ❌ **NO commits without issue links**
4. ❌ **NO hardcoded values** - use constants or config
5. ❌ **NO SQL injection risks** - always use parameterized queries

---

**Remember**: Quality > Speed. Take time to research, test, and document properly!
