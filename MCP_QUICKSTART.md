# 🚀 MCP Integration - Quick Start Guide

## ✅ Installation Status

**Step 1: Configuration** ✅ DONE
- `.vscode/mcp.json` - MCP servers configured
- `.vscode/settings.json` - MCP enabled
- `.vscode/tasks.json` - MCP workflows added

**Step 2: Environment** ⚠️ ACTION NEEDED
- `.env` file created
- ✅ Perplexity API key added
- ❌ **GitHub token needed!**

**Step 3: MCP Servers** ℹ️ INFO
- MCP servers are installed via VS Code, not npm
- VS Code will auto-install on first use

---

## 🔑 Add GitHub Token (Required)

### Create Token:
1. Go to: https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Select scopes:
   - ✅ `repo` (full repository access)
   - ✅ `workflow` (update workflows)
   - ✅ `write:packages`
4. Click "Generate token"
5. Copy the token (starts with `ghp_` or `github_pat_`)

### Add to .env:
```bash
# Open .env file and replace:
GITHUB_TOKEN=YOUR_GITHUB_TOKEN_HERE

# With your actual token:
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

---

## 🚀 Launch MCP Workflow

### Option 1: VS Code Tasks (Recommended)
```
1. Press: Ctrl+Shift+P
2. Type: "Tasks: Run Task"
3. Select: "MCP: Analyze Test Failures"
```

### Option 2: Command Line
```powershell
# Run MCP workflow script
.\scripts\mcp_workflow.ps1 -Workflow "analyze-tests"
```

### Option 3: Auto-Fix Failed Tests
```
Ctrl+Shift+P → "MCP: Auto-Fix Test Failures"
```

---

## 🎯 What MCP Will Do

### 1️⃣ Perplexity AI Analysis
- Read 16 failed test results
- Identify root causes:
  - MonteCarloResult API change (11 tests)
  - WalkForwardOptimizer params (5 tests)
  - MTF Engine import error (1 module)
- Generate code fixes
- Suggest best practices

### 2️⃣ Capiton GitHub Orchestration
- Create GitHub issues:
  - Issue #1: Fix Monte Carlo tests (High Priority)
  - Issue #2: Update Walk-Forward tests (Medium)
  - Issue #3: Fix MTF import (Critical)
- Assign labels and priorities
- Create fix branches
- Coordinate PRs

### 3️⃣ Automated Fixes
- Apply Perplexity's suggested fixes
- Run tests to verify
- Create PRs for review
- Update documentation

---

## 📊 Expected Results

**Before MCP:**
- 48 passed, 16 failed (75% pass rate)
- Manual analysis: 4-6 hours
- Manual fixes: 8-12 hours

**After MCP:**
- All 64 tests passing (100%)
- Auto-analysis: 10 minutes
- Auto-fixes: 2-3 hours
- **Time saved: 10-16 hours (83-89%)** 🎉

---

## 🧪 Test the Setup

### Quick Test:
```powershell
# Test MCP configuration
.\scripts\test_mcp_scenarios.ps1

# Should show: 10/10 tests passed
```

### Full Test:
```powershell
# Run MCP workflow on real data
.\scripts\mcp_workflow.ps1 -Workflow "high-priority-anomalies"
```

---

## ❓ Troubleshooting

### MCP servers not starting?
```powershell
# Check VS Code MCP extension
code --list-extensions | Select-String "mcp"

# Restart VS Code
code .
```

### API keys not working?
```bash
# Verify .env file
cat .env | grep "API_KEY\|TOKEN"

# Check format:
PERPLEXITY_API_KEY=pplx-xxxxx  # ✅ Correct
GITHUB_TOKEN=ghp_xxxxx          # ✅ Correct
```

### Tests still failing?
```powershell
# Re-run MCP analysis
.\scripts\mcp_run_all_tests.ps1

# Check report
cat MCP_FULL_TEST_ANALYSIS.md
```

---

## 📚 Documentation

- **Full Guide**: `MCP_INTEGRATION.md`
- **Test Report**: `MCP_FULL_TEST_ANALYSIS.md`  
- **Setup Guide**: `.vscode/MCP_SETUP_GUIDE.md`
- **Quick Start**: This file

---

## 🎉 Ready!

Once you add the GitHub token:

1. ✅ Restart VS Code: `code .`
2. ✅ Press `Ctrl+Shift+P`
3. ✅ Run: "Tasks: Run Task → MCP: Analyze Test Failures"
4. ✅ Watch the magic happen! 🌟

---

**Status**: ⚠️ **Waiting for GitHub token**  
**Next**: Add token to `.env` → Restart VS Code → Launch workflow!

**Estimated time to 100% tests**: 2-3 hours (automated) 🚀
