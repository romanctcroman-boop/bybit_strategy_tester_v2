/**
 * AI Pipeline Page JavaScript
 * Handles strategy generation, backtest, market analysis, and agent monitoring.
 *
 * Uses existing backend API at /api/v1/ai-pipeline/*
 */

/* ============================================
   GLOBALS
   ============================================ */
const API_BASE = '/api/v1/ai-pipeline';
const MONITOR_API = '/api/v1/agents/monitoring';
const ADVANCED_API = '/api/v1/agents/advanced';

/* ============================================
   AGENT TOGGLE
   ============================================ */
function toggleAgent(chip) {
    chip.classList.toggle('selected');
}

function getSelectedAgents() {
    const chips = document.querySelectorAll('.agent-chip.selected');
    const agents = Array.from(chips).map((c) => c.dataset.agent);
    return agents.length > 0 ? agents : ['deepseek'];
}

/* ============================================
   NOTIFICATION
   ============================================ */
function showNotification(message, type = 'info') {
    // Remove any existing toast
    const existing = document.querySelector('.notification-toast');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.className = `notification-toast ${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);

    requestAnimationFrame(() => toast.classList.add('show'));
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

/* ============================================
   PROGRESS
   ============================================ */
const PIPELINE_STAGES = [
    'context_analysis',
    'strategy_generation',
    'response_parsing',
    'consensus',
    'backtest',
    'walk_forward',
    'report'
];

function showProgress(label) {
    const section = document.getElementById('progressSection');
    section.classList.add('visible');
    document.getElementById('progressLabel').textContent = label;
    document.getElementById('progressBar').style.width = '0%';
    renderStages([]);
}

function updateProgress(pct, label) {
    document.getElementById('progressBar').style.width = `${pct}%`;
    if (label) {
        document.getElementById('progressLabel').textContent = label;
    }
}

function hideProgress() {
    document.getElementById('progressSection').classList.remove('visible');
}

function renderStages(stages) {
    const container = document.getElementById('stagesList');
    container.innerHTML = stages
        .map((s) => {
            const cls = s.success ? 'completed' : s.error ? 'failed' : 'active';
            const icon = s.success ? '✅' : s.error ? '❌' : '⏳';
            return `<span class="stage-item ${cls}">${icon} ${s.stage}</span>`;
        })
        .join('');
}

/* ============================================
   RUN PIPELINE
   ============================================ */
async function runPipeline() {
    const btn = document.getElementById('btnGenerate');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Generating...';

    // Hide previous results
    document.getElementById('resultsSection').classList.remove('visible');

    const payload = {
        symbol: document.getElementById('symbol').value,
        timeframe: document.getElementById('timeframe').value,
        agents: getSelectedAgents(),
        run_backtest: document.getElementById('runBacktest').checked,
        enable_walk_forward: document.getElementById('walkForward').checked,
        initial_capital: parseFloat(document.getElementById('initialCapital').value) || 10000,
        leverage: parseInt(document.getElementById('leverage').value) || 10,
        start_date: document.getElementById('startDate').value,
        end_date: document.getElementById('endDate').value
    };

    // Validate
    if (!payload.start_date || !payload.end_date) {
        showNotification('Please set start and end dates', 'error');
        resetButton(btn);
        return;
    }

    showProgress('Starting AI pipeline...');

    // Simulate progress stages
    const progressInterval = setInterval(() => {
        const bar = document.getElementById('progressBar');
        const current = parseFloat(bar.style.width) || 0;
        if (current < 85) {
            updateProgress(current + 2);
        }
    }, 500);

    try {
        const response = await fetch(`${API_BASE}/generate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        clearInterval(progressInterval);

        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.detail || `API error: ${response.status}`);
        }

        const data = await response.json();
        updateProgress(100, 'Pipeline completed!');

        setTimeout(() => {
            hideProgress();
            displayResults(data);
            showNotification('Strategy generated successfully!', 'success');
        }, 500);
    } catch (error) {
        clearInterval(progressInterval);
        hideProgress();
        console.error('Pipeline error:', error);
        showNotification(`Pipeline failed: ${error.message}`, 'error');
    } finally {
        resetButton(btn);
    }
}

function resetButton(btn) {
    btn.disabled = false;
    btn.innerHTML = '<i class="bi bi-lightning-charge"></i> Generate Strategy';
}

/* ============================================
   DISPLAY RESULTS
   ============================================ */
function displayResults(data) {
    const section = document.getElementById('resultsSection');
    section.classList.add('visible');

    // Strategy card
    if (data.strategy) {
        const card = document.getElementById('strategyCard');
        card.classList.remove('hidden');
        const s = data.strategy;
        document.getElementById('strategyInfo').innerHTML = `
            <div class="info-item">
                <span class="info-label">Strategy Name</span>
                <span class="info-value">${escapeHtml(s.strategy_name)}</span>
            </div>
            <div class="info-item">
                <span class="info-label">Type</span>
                <span class="info-value">${escapeHtml(s.strategy_type)}</span>
            </div>
            <div class="info-item">
                <span class="info-label">Agent</span>
                <span class="info-value">${escapeHtml(s.agent || 'N/A')}</span>
            </div>
            <div class="info-item">
                <span class="info-label">Signals</span>
                <span class="info-value">${s.signals_count}</span>
            </div>
            <div class="info-item">
                <span class="info-label">Quality Score</span>
                <span class="info-value">${(s.quality_score * 100).toFixed(1)}%</span>
            </div>
            <div class="info-item">
                <span class="info-label">Parameters</span>
                <span class="info-value" style="font-size:0.85rem;">${escapeHtml(JSON.stringify(s.strategy_params))}</span>
            </div>
            ${s.description ? `<div class="info-item" style="grid-column:1/-1;">
                <span class="info-label">Description</span>
                <span class="info-value" style="font-weight:normal;font-size:0.9rem;">${escapeHtml(s.description)}</span>
            </div>` : ''}
        `;
    }

    // Backtest metrics
    if (data.backtest_metrics && Object.keys(data.backtest_metrics).length > 0) {
        const card = document.getElementById('metricsCard');
        card.classList.remove('hidden');
        const m = data.backtest_metrics;

        const metricItems = [
            { label: 'Net Profit', value: formatPct(m.net_profit_pct || m.total_return), key: 'profit' },
            { label: 'Sharpe Ratio', value: formatNum(m.sharpe_ratio), key: 'sharpe' },
            { label: 'Max Drawdown', value: formatPct(m.max_drawdown), key: 'dd' },
            { label: 'Win Rate', value: formatPct(m.win_rate), key: 'wr' },
            { label: 'Profit Factor', value: formatNum(m.profit_factor), key: 'pf' },
            { label: 'Total Trades', value: m.total_trades || m.total_closed_trades || 0, key: 'trades' },
            { label: 'Sortino Ratio', value: formatNum(m.sortino_ratio), key: 'sortino' },
            { label: 'Calmar Ratio', value: formatNum(m.calmar_ratio), key: 'calmar' }
        ];

        document.getElementById('metricsGrid').innerHTML = metricItems
            .map((item) => {
                let cls = '';
                if (item.key === 'profit' || item.key === 'sharpe' || item.key === 'pf') {
                    const raw = parseFloat(String(item.value).replace('%', ''));
                    cls = raw > 0 ? 'positive' : raw < 0 ? 'negative' : '';
                }
                if (item.key === 'dd') {
                    const raw = Math.abs(parseFloat(String(item.value).replace('%', '')));
                    cls = raw > 15 ? 'negative' : 'positive';
                }
                return `
                    <div class="metric-card">
                        <div class="metric-label">${item.label}</div>
                        <div class="metric-value ${cls}">${item.value}</div>
                    </div>
                `;
            })
            .join('');
    }

    // Walk-forward
    if (data.walk_forward && Object.keys(data.walk_forward).length > 0) {
        const card = document.getElementById('wfCard');
        card.classList.remove('hidden');
        const wf = data.walk_forward;

        const stats = [
            { label: 'Consistency', value: formatPct(wf.consistency_ratio) },
            { label: 'Overfit Score', value: formatNum(wf.overfit_score) },
            { label: 'Param Stability', value: formatPct(wf.parameter_stability) },
            { label: 'Confidence', value: wf.confidence_level || 'N/A' }
        ];

        document.getElementById('wfSummary').innerHTML = stats
            .map(
                (s) => `
                <div class="wf-stat">
                    <div class="stat-label">${s.label}</div>
                    <div class="stat-value">${s.value}</div>
                </div>
            `
            )
            .join('');
    }

    // Consensus
    if (data.consensus_summary) {
        const card = document.getElementById('consensusCard');
        card.classList.remove('hidden');
        document.getElementById('consensusBox').textContent = data.consensus_summary;
    }

    // Stages timeline
    if (data.stages && data.stages.length > 0) {
        const card = document.getElementById('stagesCard');
        card.classList.remove('hidden');

        document.getElementById('stagesTimeline').innerHTML = data.stages
            .map((s) => {
                const icon = s.success ? '✅' : '❌';
                return `
                    <div class="timeline-item">
                        <span class="timeline-icon">${icon}</span>
                        <span class="timeline-label">${escapeHtml(s.stage)}</span>
                        <span class="timeline-duration">${s.duration_ms.toFixed(0)}ms</span>
                    </div>
                `;
            })
            .join('');

        // Total duration
        if (data.total_duration_ms) {
            document.getElementById('stagesTimeline').innerHTML += `
                <div class="timeline-item" style="border-top: 1px solid var(--color-border); margin-top: 4px; padding-top: 12px;">
                    <span class="timeline-icon">⏱️</span>
                    <span class="timeline-label"><strong>Total</strong></span>
                    <span class="timeline-duration"><strong>${(data.total_duration_ms / 1000).toFixed(2)}s</strong></span>
                </div>
            `;
        }
    }
}

/* ============================================
   ANALYZE MARKET
   ============================================ */
async function analyzeMarket() {
    const btn = document.getElementById('btnAnalyze');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Analyzing...';

    const payload = {
        symbol: document.getElementById('symbol').value,
        timeframe: document.getElementById('timeframe').value,
        start_date: document.getElementById('startDate').value,
        end_date: document.getElementById('endDate').value
    };

    try {
        const response = await fetch(`${API_BASE}/analyze-market`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.detail || `API error: ${response.status}`);
        }

        const data = await response.json();
        displayMarketAnalysis(data);
        showNotification('Market analysis completed!', 'success');
    } catch (error) {
        console.error('Market analysis error:', error);
        showNotification(`Analysis failed: ${error.message}`, 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-search"></i> Analyze Market';
    }
}

function displayMarketAnalysis(data) {
    const section = document.getElementById('marketAnalysisSection');
    section.classList.add('visible');
    const card = document.getElementById('marketCard');
    card.classList.remove('hidden');

    document.getElementById('marketInfo').innerHTML = `
        <div class="info-item">
            <span class="info-label">Symbol</span>
            <span class="info-value">${escapeHtml(data.symbol)}</span>
        </div>
        <div class="info-item">
            <span class="info-label">Market Regime</span>
            <span class="info-value">${escapeHtml(data.market_regime || 'N/A')}</span>
        </div>
        <div class="info-item">
            <span class="info-label">Trend</span>
            <span class="info-value">${escapeHtml(data.trend_direction || 'N/A')}</span>
        </div>
        <div class="info-item">
            <span class="info-label">Volatility</span>
            <span class="info-value">${escapeHtml(data.volatility_level || 'N/A')}</span>
        </div>
        <div class="info-item">
            <span class="info-label">Candles Analyzed</span>
            <span class="info-value">${data.candles_analyzed || 0}</span>
        </div>
        <div class="info-item">
            <span class="info-label">Recommended Strategies</span>
            <span class="info-value">${(data.recommended_strategies || []).join(', ') || 'N/A'}</span>
        </div>
    `;

    document.getElementById('marketContext').textContent =
        data.context_summary || 'No detailed context available.';
}

/* ============================================
   MONITORING
   ============================================ */
async function loadMonitoring() {
    const section = document.getElementById('monitorSection');
    section.classList.toggle('hidden');

    if (section.classList.contains('hidden')) return;

    try {
        const response = await fetch(`${MONITOR_API}/metrics`, {
            headers: { 'Content-Type': 'application/json' }
        });

        if (!response.ok) {
            throw new Error(`API error: ${response.status}`);
        }

        const data = await response.json();
        displayMonitoring(data);
    } catch (error) {
        console.error('Monitoring error:', error);
        document.getElementById('monitorGrid').innerHTML = `
            <div style="grid-column: 1/-1; text-align: center; color: var(--color-text-muted); padding: 20px;">
                Monitoring data unavailable. The system monitor may not have collected data yet.
            </div>
        `;
        document.getElementById('alertsList').innerHTML = '';
    }
}

function displayMonitoring(data) {
    const metrics = data.metrics || {};
    const alerts = data.alerts || [];

    const grid = document.getElementById('monitorGrid');
    const items = [
        { label: 'Success Rate', value: formatPct(metrics.agent_success_rate), icon: '✅' },
        { label: 'Avg Gen Time', value: `${(metrics.strategy_generation_time || 0).toFixed(1)}s`, icon: '⏱️' },
        { label: 'Avg Backtest', value: `${(metrics.backtest_duration || 0).toFixed(1)}s`, icon: '📊' },
        { label: 'Token Usage', value: (metrics.llm_token_usage || 0).toLocaleString(), icon: '🔤' },
        { label: 'API Cost', value: `$${(metrics.api_costs || 0).toFixed(4)}`, icon: '💰' },
        { label: 'Total Runs', value: metrics.total_runs || 0, icon: '🔄' }
    ];

    grid.innerHTML = items
        .map(
            (item) => `
        <div class="monitor-card">
            <div class="monitor-label">${item.icon} ${item.label}</div>
            <div class="monitor-value">${item.value}</div>
        </div>
    `
        )
        .join('');

    const alertsList = document.getElementById('alertsList');
    if (alerts.length === 0) {
        alertsList.innerHTML = '<div style="color: var(--color-text-muted); font-size: 0.85rem;">No alerts</div>';
    } else {
        alertsList.innerHTML = alerts
            .map(
                (a) => `
            <div class="alert-item ${a.severity || 'info'}">
                <span>${a.severity === 'warning' ? '⚠️' : a.severity === 'error' ? '🔴' : 'ℹ️'}</span>
                <span>${escapeHtml(a.message)}</span>
                <span style="margin-left:auto; font-size:0.75rem; opacity:0.7;">${a.timestamp || ''}</span>
            </div>
        `
            )
            .join('');
    }
}

/* ============================================
   AGENT HEALTH PANEL
   ============================================ */
function toggleHealthPanel() {
    const content = document.getElementById('healthContent');
    const icon = document.getElementById('healthToggleIcon');
    const isHidden = content.classList.contains('hidden');

    content.classList.toggle('hidden', !isHidden);
    icon.classList.toggle('open', isHidden);

    if (isHidden) {
        runPreflight();
        loadAgentAccuracy();
    }
}

async function runPreflight() {
    const providers = ['deepseek', 'qwen', 'perplexity'];
    providers.forEach((p) => {
        const el = document.getElementById(`${p}Status`);
        if (el) el.textContent = '\u23F3 Checking...';
        const card = el?.closest('.health-card');
        if (card) card.className = 'health-card';
    });

    try {
        const response = await fetch(`${ADVANCED_API}/keys/preflight`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();

        for (const [provider, result] of Object.entries(data.providers || {})) {
            const statusEl = document.getElementById(`${provider}Status`);
            const card = statusEl?.closest('.health-card');
            if (!statusEl || !card) continue;

            if (result.valid === true) {
                statusEl.textContent = `\u2705 Valid (HTTP ${result.status})`;
                card.className = 'health-card valid';
            } else if (result.valid === false) {
                statusEl.textContent = `\u274C Invalid: ${result.reason || 'auth failed'}`;
                card.className = 'health-card invalid';
            } else {
                statusEl.textContent = `\u26A0\uFE0F Unknown: ${result.reason || 'check failed'}`;
                card.className = 'health-card unknown';
            }
        }

        showNotification(
            `Key check: ${data.summary?.valid || 0}/${data.summary?.total || 0} valid`,
            data.all_valid ? 'success' : 'warning'
        );
    } catch (error) {
        console.error('Pre-flight error:', error);
        providers.forEach((p) => {
            const el = document.getElementById(`${p}Status`);
            if (el) el.textContent = '\u274C Check failed';
        });
        showNotification('Key validation failed: ' + error.message, 'error');
    }
}

async function loadAgentAccuracy() {
    try {
        const response = await fetch(`${ADVANCED_API}/deliberation/accuracy`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();

        const agents = data.accuracy?.agents || {};
        for (const [agentName, stats] of Object.entries(agents)) {
            const weightEl = document.getElementById(`${agentName}Weight`);
            if (weightEl) {
                const w = stats.weight || 1.0;
                const correct = stats.correct || 0;
                const total = stats.total || 0;
                weightEl.textContent = `Weight: ${w.toFixed(2)} (${correct}/${total})`;
            }
        }
    } catch (error) {
        console.error('Agent accuracy load error:', error);
    }
}

async function loadAuditLog() {
    const container = document.getElementById('auditLogContainer');
    const entries = document.getElementById('auditLogEntries');
    const isHidden = container.classList.contains('hidden');

    container.classList.toggle('hidden', !isHidden);
    if (!isHidden) return;

    entries.innerHTML = '<div class="health-loading">Loading...</div>';

    try {
        const response = await fetch(`${ADVANCED_API}/deliberation/audit-log?last_n=30`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();

        if (!data.entries || data.entries.length === 0) {
            entries.innerHTML = '<div class="health-loading">No audit entries yet. Run a deliberation first.</div>';
            return;
        }

        entries.innerHTML = data.entries
            .map((entry) => {
                const time = new Date(entry.timestamp).toLocaleTimeString();
                const event = entry.event || 'unknown';
                const dataStr = JSON.stringify(entry.data || {}).substring(0, 120);
                return `
                    <div class="audit-entry">
                        <span class="audit-time">${escapeHtml(time)}</span>
                        <span class="audit-event">${escapeHtml(event)}</span>
                        <span class="audit-data" title="${escapeHtml(dataStr)}">${escapeHtml(dataStr)}</span>
                    </div>
                `;
            })
            .join('');
    } catch (error) {
        entries.innerHTML = `<div class="health-loading" style="color:var(--color-danger)">Failed: ${escapeHtml(error.message)}</div>`;
    }
}

async function loadDeliberationHistory() {
    const container = document.getElementById('deliberationHistoryContainer');
    const entries = document.getElementById('deliberationHistoryEntries');
    const isHidden = container.classList.contains('hidden');

    container.classList.toggle('hidden', !isHidden);
    if (!isHidden) return;

    entries.innerHTML = '<div class="health-loading">Loading...</div>';

    try {
        const response = await fetch(`${ADVANCED_API}/deliberation/history?limit=15`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();

        if (!data.deliberations || data.deliberations.length === 0) {
            entries.innerHTML = '<div class="health-loading">No deliberations yet.</div>';
            return;
        }

        entries.innerHTML = data.deliberations
            .map((d) => {
                const conf = (d.confidence * 100).toFixed(0);
                const confClass = d.confidence >= 0.8 ? 'high' : d.confidence >= 0.5 ? 'medium' : 'low';
                const duration = d.duration_seconds ? `${d.duration_seconds.toFixed(1)}s` : '\u2014';
                return `
                    <div class="delib-entry">
                        <span class="delib-question" title="${escapeHtml(d.question)}">${escapeHtml(d.decision || d.question)}</span>
                        <span class="delib-confidence ${confClass}">${conf}%</span>
                        <span class="delib-rounds">${d.rounds}R</span>
                        <span class="delib-duration">${duration}</span>
                    </div>
                `;
            })
            .join('');
    } catch (error) {
        entries.innerHTML = `<div class="health-loading" style="color:var(--color-danger)">Failed: ${escapeHtml(error.message)}</div>`;
    }
}

/* ============================================
   UTILITIES
   ============================================ */
function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = String(str);
    return div.innerHTML;
}

function formatPct(value) {
    if (value === null || value === undefined) return 'N/A';
    const num = parseFloat(value);
    if (isNaN(num)) return 'N/A';
    return `${(num * 100).toFixed(2)}%`;
}

function formatNum(value) {
    if (value === null || value === undefined) return 'N/A';
    const num = parseFloat(value);
    if (isNaN(num)) return 'N/A';
    return num.toFixed(2);
}
