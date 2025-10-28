# MCP Integration Setup Guide

## 🚀 Quick Start

### 1. Install Dependencies

```bash
# Install MCP servers globally
npm install -g @modelcontextprotocol/server-perplexity-ask
npm install -g @modelcontextprotocol/server-capiton-github
```

### 2. Configure API Keys

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Fill in your API keys:
   - **PERPLEXITY_API_KEY**: Get from https://www.perplexity.ai/settings/api
   - **GITHUB_TOKEN**: Create at https://github.com/settings/tokens
     - Required scopes: `repo`, `workflow`, `write:packages`, `read:org`

### 3. Load Environment Variables

Add to your PowerShell profile or run before starting VS Code:

```powershell
# Load .env file
Get-Content .env | ForEach-Object {
    if ($_ -match '^([^=]+)=(.*)$') {
        [System.Environment]::SetEnvironmentVariable($matches[1], $matches[2], 'Process')
    }
}
```

Or use VS Code extension: **DotENV** by mikestead

### 4. Restart VS Code

MCP servers will auto-start when workspace opens!

---

## 🔧 Architecture

### Agent Responsibilities

#### **Perplexity** (Deep Analysis)
- ✅ Knowledge synthesis
- ✅ Solution research
- ✅ Bug investigation
- ✅ Context aggregation
- ✅ Comprehensive analysis
- ❌ Task creation (handled by Capiton)
- ❌ Setting restrictions (handled by Capiton)

#### **Capiton GitHub** (Orchestration)
- ✅ Task prioritization
- ✅ Issue tracking
- ✅ Access control
- ✅ Setting restrictions
- ✅ GitHub integration
- ✅ Code review coordination
- ❌ Deep analysis (delegated to Perplexity)

### Workflow Pipeline

```
1. ANALYSIS (Perplexity)
   ↓
   Context gathered, solutions researched
   ↓
2. PLANNING (Capiton)
   ↓
   Tasks created, priorities set
   ↓
3. EXECUTION (Perplexity)
   ↓
   Solutions implemented
   ↓
4. VALIDATION (Capiton)
   ↓
   Issues tracked, reviews completed
```

---

## 📋 Usage Examples

### Automated Bug Fix Workflow

1. **Analysis** (Perplexity):
   - Deep dive into error logs
   - Research similar issues
   - Synthesize knowledge from docs

2. **Planning** (Capiton):
   - Create GitHub issue
   - Set priority (critical/high/medium/low)
   - Assign to milestone

3. **Execution** (Perplexity):
   - Generate solution code
   - Create test cases
   - Document changes

4. **Validation** (Capiton):
   - Create pull request
   - Request code review
   - Track completion

### High Priority Anomalies (4-7)

Current focus: Position Sizing, Signal Exit, Buy & Hold, Margin Calls

**Workflow**:
```bash
# Run via VS Code Task
Ctrl+Shift+P → Tasks: Run Task → Workflow: High Priority Anomalies
```

**Automated steps**:
1. Perplexity analyzes each anomaly
2. Capiton creates 4 GitHub issues
3. Perplexity researches solutions
4. Capiton prioritizes tasks
5. Agent executes fixes with validation

---

## 🛠️ VS Code Tasks

Available tasks (Ctrl+Shift+P → Tasks: Run Task):

- **MCP: Install Servers** - Install npm packages
- **MCP: Start All Servers** - Start Perplexity + Capiton
- **Workflow: Critical Anomaly Fix** - Run full fix workflow
- **Workflow: High Priority Anomalies** - Process anomalies 4-7
- **Test: Run All Critical Tests** - Run pytest suite

---

## 🔍 Monitoring

### Check MCP Server Status

```bash
# View running processes
Get-Process | Where-Object {$_.ProcessName -like "*node*"}

# Check logs
tail -f .vscode/mcp.log
```

### Metrics Tracked

- Task completion rate
- Analysis depth score
- Response time (ms)
- Error rate (%)

View in VS Code: `Ctrl+Shift+P → MCP: Show Metrics`

---

## 🚨 Troubleshooting

### MCP Servers Not Starting

1. Check npm installation:
   ```bash
   npm list -g @modelcontextprotocol/server-perplexity-ask
   npm list -g @modelcontextprotocol/server-capiton-github
   ```

2. Verify API keys:
   ```powershell
   echo $env:PERPLEXITY_API_KEY
   echo $env:GITHUB_TOKEN
   ```

3. Check VS Code output:
   - View → Output → Select "MCP" from dropdown

### Agent Not Responding

1. Restart MCP servers:
   ```bash
   Ctrl+Shift+P → Tasks: Run Task → MCP: Start All Servers
   ```

2. Check network connectivity
3. Verify API key validity

### GitHub Integration Issues

1. Verify token scopes:
   - Go to https://github.com/settings/tokens
   - Ensure `repo`, `workflow`, `write:packages` are enabled

2. Check repository access:
   ```bash
   curl -H "Authorization: token $GITHUB_TOKEN" \
        https://api.github.com/repos/RomanCTC/bybit_strategy_tester_v2
   ```

---

## 📊 Current Project Status

### ✅ Completed Anomalies (1-3)
- Code Consolidation: 100% tests passing
- RBAC Implementation: 89.5% tests passing
- DataManager Refactoring: 88.9% tests passing

### 🔄 Next Focus (Anomalies 4-7)
1. Position Sizing implementation
2. Signal Exit logic
3. Buy & Hold calculation
4. Margin Calls simulation

**Estimated effort**: 7 days with MCP automation

---

## 🎯 Best Practices

### Do's ✅
- Let Capiton handle all task creation
- Use Perplexity for deep analysis
- Review automated PR's before merge
- Monitor MCP metrics regularly

### Don'ts ❌
- Don't let Perplexity set restrictions
- Don't override Capiton priorities manually
- Don't disable auto-start in production
- Don't commit .env with real keys

---

## 📚 Resources

- [MCP Documentation](https://modelcontextprotocol.io/)
- [Perplexity API Docs](https://docs.perplexity.ai/)
- [GitHub API Reference](https://docs.github.com/en/rest)
- [VS Code Tasks Guide](https://code.visualstudio.com/docs/editor/tasks)

---

**Status**: ✅ READY TO USE  
**Last Updated**: 2025-01-27  
**Version**: 1.0.0
