/**
 * AiBuildModule.js — AI Strategy Builder / Optimizer modal logic.
 *
 * Extracted from strategy_builder.js during P0-1 refactoring (2026-02-26).
 *
 * Responsibilities:
 *   - AI Build modal open/close/reset
 *   - Preset management (AI_PRESETS)
 *   - runAiBuild() — builds payload and calls SSE stream endpoint
 *   - _runAiBuildWithSSE() — SSE streaming reader
 *   - Agent activity monitor (_appendAgentLog, _resetAgentMonitor, toggleAgentMonitor)
 *   - showAiBuildResults() — renders iteration table + metric cards
 *   - viewAiBacktestFullResults() — opens backtest-results page
 *
 * Usage:
 *   import { createAiBuildModule } from './AiBuildModule.js';
 *   const aiModule = createAiBuildModule({ getStrategyId, getBlocks, getConnections,
 *                                          displayBacktestResults, loadStrategy, escapeHtml });
 *   aiModule.openAiBuildModal();
 */

// ── Presets ──────────────────────────────────────────────────────────────────

export const AI_PRESETS = {
    rsi: {
        blocks: [
            { type: 'rsi', params: { period: 14, use_cross_level: true, cross_long_level: 30, cross_short_level: 70 } },
            { type: 'buy' },
            { type: 'sell' },
            { type: 'static_sltp', id: 'sltp_1', params: { stop_loss_percent: 2.0, take_profit_percent: 4.0 } }
        ],
        connections: [
            { source: 'rsi', source_port: 'long', target: 'buy', target_port: 'signal' },
            { source: 'rsi', source_port: 'short', target: 'sell', target_port: 'signal' }
        ]
    },
    ema_cross: {
        blocks: [
            { type: 'ema', params: { period: 9 }, id: 'ema_fast' },
            { type: 'ema', params: { period: 21 }, id: 'ema_slow' },
            { type: 'crossover', id: 'cross_up' },
            { type: 'crossunder', id: 'cross_down' },
            { type: 'buy' },
            { type: 'sell' },
            { type: 'static_sltp', id: 'sltp_1', params: { stop_loss_percent: 2.0, take_profit_percent: 4.0 } }
        ],
        connections: [
            { source: 'ema_fast', source_port: 'value', target: 'cross_up', target_port: 'a' },
            { source: 'ema_slow', source_port: 'value', target: 'cross_up', target_port: 'b' },
            { source: 'ema_fast', source_port: 'value', target: 'cross_down', target_port: 'a' },
            { source: 'ema_slow', source_port: 'value', target: 'cross_down', target_port: 'b' },
            { source: 'cross_up', source_port: 'result', target: 'buy', target_port: 'signal' },
            { source: 'cross_down', source_port: 'result', target: 'sell', target_port: 'signal' }
        ]
    },
    macd: {
        blocks: [
            { type: 'macd', params: { fast_period: 12, slow_period: 26, signal_period: 9, use_macd_cross_signal: true } },
            { type: 'buy' },
            { type: 'sell' },
            { type: 'static_sltp', id: 'sltp_1', params: { stop_loss_percent: 2.0, take_profit_percent: 4.0 } }
        ],
        connections: [
            { source: 'macd', source_port: 'long', target: 'buy', target_port: 'signal' },
            { source: 'macd', source_port: 'short', target: 'sell', target_port: 'signal' }
        ]
    },
    bb: {
        blocks: [
            { type: 'bollinger', params: { period: 20, std_dev: 2.0 } },
            { type: 'price', id: 'price' },
            { type: 'crossover', id: 'cross_up' },
            { type: 'crossunder', id: 'cross_down' },
            { type: 'buy' },
            { type: 'sell' },
            { type: 'static_sltp', id: 'sltp_1', params: { stop_loss_percent: 2.0, take_profit_percent: 4.0 } }
        ],
        connections: [
            { source: 'price', source_port: 'close', target: 'cross_up', target_port: 'a' },
            { source: 'bollinger', source_port: 'lower', target: 'cross_up', target_port: 'b' },
            { source: 'price', source_port: 'close', target: 'cross_down', target_port: 'a' },
            { source: 'bollinger', source_port: 'upper', target: 'cross_down', target_port: 'b' },
            { source: 'cross_up', source_port: 'result', target: 'buy', target_port: 'signal' },
            { source: 'cross_down', source_port: 'result', target: 'sell', target_port: 'signal' }
        ]
    },
    custom: { blocks: [], connections: [] }
};

// ── Factory ───────────────────────────────────────────────────────────────────

/**
 * Create an AI Build module instance.
 *
 * @param {Object} deps
 * @param {() => string|null}   deps.getStrategyIdFromURL     — current strategy ID from URL
 * @param {() => Array}         deps.getBlocks                — live canvas blocks array
 * @param {() => Array}         deps.getConnections           — live canvas connections array
 * @param {(results: Object) => void} deps.displayBacktestResults — show backtest results modal
 * @param {(id: string) => Promise} deps.loadStrategy         — load strategy onto canvas
 * @param {(s: string) => string}   deps.escapeHtml           — HTML-escape helper
 * @returns {Object} public API
 */
export function createAiBuildModule(deps) {
    const {
        getStrategyIdFromURL,
        getBlocks,
        getConnections,
        displayBacktestResults,
        loadStrategy,
        escapeHtml
    } = deps;

    // ── Module state ──────────────────────────────────────────────────────────
    let _aiBuildMode = 'build';          // 'build' | 'optimize'
    let _aiBuildExistingStrategyId = null;

    /** Counts for each agent column badge */
    const _agentMsgCount = { deepseek: 0, qwen: 0, perplexity: 0 };

    // ── Public: openAiBuildModal ──────────────────────────────────────────────
    function openAiBuildModal() {
        const modal = document.getElementById('aiBuildModal');
        modal.classList.remove('hidden');
        modal.style.display = 'flex';

        const existingId = getStrategyIdFromURL();
        const blocks = getBlocks();
        const hasCanvasBlocks = blocks.length > 0;
        const stratName = document.getElementById('strategyName')?.value || 'New Strategy';

        if (existingId && hasCanvasBlocks) {
            _aiBuildMode = 'optimize';
            _aiBuildExistingStrategyId = existingId;
        } else {
            _aiBuildMode = 'build';
            _aiBuildExistingStrategyId = null;
        }

        const titleEl = modal.querySelector('.ai-build-header h3');
        if (titleEl) {
            titleEl.innerHTML = _aiBuildMode === 'optimize'
                ? '<i class="bi bi-stars"></i> AI Strategy Optimizer'
                : '<i class="bi bi-robot"></i> AI Strategy Builder';
        }

        const presetHeading = modal.querySelector('.ai-build-preset-heading');
        const presetSelect = document.getElementById('aiPreset');
        const blocksPreview = document.getElementById('aiBlocksPreview');
        const isOptimize = _aiBuildMode === 'optimize';

        if (presetHeading) presetHeading.style.display = isOptimize ? 'none' : '';
        if (presetSelect) presetSelect.style.display = isOptimize ? 'none' : '';
        if (blocksPreview) {
            if (isOptimize) {
                const blockTypes = blocks.map(b => b.type || b.blockType || '?');
                blocksPreview.textContent = `Текущие блоки на канвасе (${blockTypes.length}):\n` +
                    blockTypes.map(t => `  • ${t}`).join('\n');
                blocksPreview.style.display = '';
            }
        }

        const btnRun = document.getElementById('btnRunAiBuild');
        if (btnRun) {
            btnRun.innerHTML = isOptimize
                ? '<i class="bi bi-stars"></i> Optimize & Backtest'
                : '<i class="bi bi-play-fill"></i> Build & Backtest';
        }

        const symbol = document.getElementById('backtestSymbol')?.value || '';
        const timeframe = document.getElementById('strategyTimeframe')?.value || '15';
        const direction = document.getElementById('builderDirection')?.value || 'both';
        const capital = document.getElementById('backtestCapital')?.value || '10000';
        const leverage = document.getElementById('backtestLeverage')?.value || '10';
        const startDate = document.getElementById('backtestStartDate')?.value || '';
        const endDate = document.getElementById('backtestEndDate')?.value || '';
        const marketType = document.getElementById('builderMarketType')?.value || 'linear';

        const tfLabels = { '1': '1m', '5': '5m', '15': '15m', '30': '30m', '60': '1h', '240': '4h', 'D': '1D', 'W': '1W', 'M': '1M' };
        const dirLabels = { 'both': 'Long & Short', 'long': 'Long only', 'short': 'Short only' };
        const mktLabels = { 'linear': 'Futures', 'spot': 'SPOT' };

        const summaryEl = document.getElementById('aiBuildSummary');
        if (summaryEl) {
            let warning = '';
            if (!symbol) {
                warning = '<div class="summary-warning"><i class="bi bi-exclamation-triangle"></i> Выберите тикер в панели Параметры</div>';
            }
            let modeInfo = '';
            if (isOptimize) {
                modeInfo = `<div class="summary-row" style="background:#1a3a1a;border-radius:4px;padding:4px 8px;margin-bottom:4px;">
          <span class="summary-label"><i class="bi bi-stars"></i> Режим:</span>
          <span class="summary-value">Оптимизация «${stratName}»</span></div>`;
            }
            summaryEl.innerHTML = `
        ${modeInfo}
        <div class="summary-row"><span class="summary-label">Symbol:</span><span class="summary-value">${symbol || '—'}</span></div>
        <div class="summary-row"><span class="summary-label">Timeframe:</span><span class="summary-value">${tfLabels[timeframe] || timeframe}</span></div>
        <div class="summary-row"><span class="summary-label">Direction:</span><span class="summary-value">${dirLabels[direction] || direction}</span></div>
        <div class="summary-row"><span class="summary-label">Market:</span><span class="summary-value">${mktLabels[marketType] || marketType}</span></div>
        <div class="summary-row"><span class="summary-label">Capital:</span><span class="summary-value">$${parseFloat(capital).toLocaleString()}</span></div>
        <div class="summary-row"><span class="summary-label">Leverage:</span><span class="summary-value">${leverage}x</span></div>
        <div class="summary-row"><span class="summary-label">Period:</span><span class="summary-value">${startDate || '—'} → ${endDate || '—'}</span></div>
        ${warning}
      `;
        }

        const aiNameEl = document.getElementById('aiName');
        if (isOptimize) {
            if (aiNameEl) aiNameEl.value = stratName;
        } else {
            if (aiNameEl && (aiNameEl.value === 'AI RSI Strategy' || aiNameEl.value === 'New Strategy' || !aiNameEl.value)) {
                aiNameEl.value = stratName === 'New Strategy' ? 'AI RSI Strategy' : `AI ${stratName}`;
            }
        }

        if (!isOptimize) {
            applyAiPreset();
        }
    }

    // ── Public: closeAiBuildModal ─────────────────────────────────────────────
    function closeAiBuildModal() {
        const modal = document.getElementById('aiBuildModal');
        modal.classList.add('hidden');
        modal.style.display = '';
    }

    // ── Public: applyAiPreset ─────────────────────────────────────────────────
    function applyAiPreset() {
        const presetSelect = document.getElementById('aiPreset');
        if (!presetSelect) return;
        const preset = AI_PRESETS[presetSelect.value];
        const preview = document.getElementById('aiBlocksPreview');
        if (preview && preset) {
            preview.textContent = JSON.stringify(preset.blocks, null, 2);
        }
    }

    // ── Public: resetAiBuild ──────────────────────────────────────────────────
    function resetAiBuild() {
        document.getElementById('aiBuildConfig').classList.remove('hidden');
        document.getElementById('aiBuildProgress').classList.add('hidden');
        document.getElementById('aiBuildResults').classList.add('hidden');
        _aiBuildMode = 'build';
        _aiBuildExistingStrategyId = null;
    }

    // ── Public: runAiBuild ────────────────────────────────────────────────────
    async function runAiBuild() {
        const symbol = document.getElementById('backtestSymbol')?.value || '';
        const timeframe = document.getElementById('strategyTimeframe')?.value || '15';
        const direction = document.getElementById('builderDirection')?.value || 'both';
        const startDate = document.getElementById('backtestStartDate')?.value || '2025-01-01';
        const endDate = document.getElementById('backtestEndDate')?.value || '2025-06-01';
        const capital = parseFloat(document.getElementById('backtestCapital')?.value || '10000');
        const leverage = parseFloat(document.getElementById('backtestLeverage')?.value || '10');

        if (!symbol) {
            alert('Выберите тикер (Symbol) в панели Параметры');
            return;
        }

        const descriptionEl = document.getElementById('aiDescription');
        const description = descriptionEl?.value?.trim() || '';
        const nameEl = document.getElementById('aiName');
        const strategyName = description || nameEl?.value || 'AI Strategy';

        const payload = {
            name: strategyName,
            symbol,
            timeframe,
            direction,
            start_date: startDate,
            end_date: endDate,
            initial_capital: capital,
            leverage,
            max_iterations: parseInt(document.getElementById('aiMaxIter')?.value || '3', 10),
            min_sharpe: parseFloat(document.getElementById('aiMinSharpe')?.value || '0.5'),
            min_win_rate: 0.4,
            enable_deliberation: document.getElementById('aiDeliberation')?.checked ?? false,
            use_optimizer_mode: document.getElementById('aiUseOptimizer')?.checked ?? false,
            evaluation_config: (window.evaluationCriteriaPanel?.getCriteria && window.evaluationCriteriaPanel.getCriteria()) || {
                primary_metric: 'sharpe_ratio',
                secondary_metrics: [],
                constraints: [],
                sort_order: [],
                use_composite: false,
                weights: null
            }
        };

        const blocks = getBlocks();
        const conns = getConnections();

        if (_aiBuildMode === 'optimize' && _aiBuildExistingStrategyId) {
            payload.existing_strategy_id = _aiBuildExistingStrategyId;
            payload.blocks = blocks.map(b => ({
                id: b.id,
                type: b.type,
                name: b.name || b.type,
                params: b.params || {}
            }));
            payload.connections = conns.map(c => ({
                id: c.id,
                source_block_id: c.sourceBlockId || c.source_block_id || c.source,
                source_port: c.sourcePort || c.source_port || 'output',
                target_block_id: c.targetBlockId || c.target_block_id || c.target,
                target_port: c.targetPort || c.target_port || 'input'
            }));
        } else {
            const presetSelect = document.getElementById('aiPreset');
            const presetKey = presetSelect?.value || 'custom';
            if (description || presetKey === 'custom') {
                payload.blocks = [];
                payload.connections = [];
            } else {
                const preset = AI_PRESETS[presetKey] || AI_PRESETS.rsi;
                payload.blocks = preset.blocks;
                payload.connections = preset.connections;
            }
        }

        document.getElementById('aiBuildConfig').classList.add('hidden');
        document.getElementById('aiBuildProgress').classList.remove('hidden');
        const _progressModal = document.querySelector('.ai-build-modal-content');
        if (_progressModal) _progressModal.classList.add('has-agents');
        _resetAgentMonitor();

        const stageEl = document.getElementById('aiBuildStage');
        if (stageEl) {
            stageEl.textContent = _aiBuildMode === 'optimize'
                ? 'Optimizing strategy with AI agent…'
                : (description ? `Planning: "${description.substring(0, 60)}…"` : 'Building strategy with AI agent…');
        }

        try {
            await _runAiBuildWithSSE(payload);
        } catch (err) {
            document.getElementById('aiBuildProgress').classList.add('hidden');
            document.getElementById('aiBuildResults').classList.remove('hidden');
            document.getElementById('aiBuildResultContent').innerHTML =
                `<div class="alert alert-danger"><i class="bi bi-exclamation-triangle"></i> ${escapeHtml(err.message)}</div>`;
        }
    }

    // ── Private: _runAiBuildWithSSE ───────────────────────────────────────────
    async function _runAiBuildWithSSE(payload) {
        const stageEl = document.getElementById('aiBuildStage');

        const response = await fetch('/api/v1/agents/advanced/builder/task/stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!response.ok || !response.body) {
            const fallback = await fetch('/api/v1/agents/advanced/builder/task', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (!fallback.ok) throw new Error(`HTTP ${fallback.status}: ${fallback.statusText}`);
            const data = await fallback.json();
            await showAiBuildResults(data);
            return;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let streamDone = false;

        while (!streamDone) {
            const { done, value } = await reader.read();
            if (done) { streamDone = true; break; }

            buffer += decoder.decode(value, { stream: true });
            const frames = buffer.split('\n\n');
            buffer = frames.pop() || '';

            for (const frame of frames) {
                if (!frame.trim()) continue;
                let eventType = 'message';
                let dataStr = '';

                for (const line of frame.split('\n')) {
                    if (line.startsWith('event:')) eventType = line.slice(6).trim();
                    else if (line.startsWith('data:')) dataStr = line.slice(5).trim();
                }

                if (!dataStr) continue;

                try {
                    const msg = JSON.parse(dataStr);

                    if (eventType === 'stage' && stageEl) {
                        stageEl.textContent = msg.label || msg.stage || '…';
                    } else if (eventType === 'agent_log') {
                        _appendAgentLog(msg);
                    } else if (eventType === 'result') {
                        await showAiBuildResults(msg);
                        return;
                    } else if (eventType === 'error') {
                        throw new Error(msg.message || 'Unknown error from agent');
                    }
                } catch (parseErr) {
                    if (parseErr instanceof SyntaxError) continue;
                    throw parseErr;
                }
            }
        }

        throw new Error('AI agent stream closed without returning a result. The task may have timed out or the server restarted.');
    }

    // ── Private: Agent Monitor ────────────────────────────────────────────────

    function _ensureAgentMonitorVisible() {
        const monitor = document.getElementById('agentMonitor');
        const modal = document.querySelector('.ai-build-modal-content');
        if (monitor && monitor.classList.contains('hidden')) {
            monitor.classList.remove('hidden');
            if (modal) modal.classList.add('has-agents');
        }
    }

    function _appendAgentLog(log) {
        const agent = (log.agent || 'deepseek').toLowerCase();
        const role = (log.role || 'unknown').toLowerCase();
        const title = log.title || '';
        const promptExcerpt = log.prompt_excerpt || '';
        const response = log.response || '';
        const ts = log.ts ? new Date(log.ts).toLocaleTimeString() : '';

        const col = ['deepseek', 'qwen', 'perplexity'].includes(agent) ? agent : 'deepseek';

        _ensureAgentMonitorVisible();

        const feed = document.getElementById(`agentFeed-${col}`);
        const badge = document.getElementById(`agentBadge-${col}`);
        if (!feed) return;

        _agentMsgCount[col] = (_agentMsgCount[col] || 0) + 1;
        if (badge) badge.textContent = _agentMsgCount[col];

        const roleClass = `role-${role}`;
        const roleLabel = {
            planner: '🔍 Planner',
            deliberation: '🤝 Deliberation',
            optimizer: '⚙️ Optimizer'
        }[role] || role;

        const formattedResponse = escapeHtml(response)
            .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
            .replace(/\n/g, '<br>');

        const card = document.createElement('div');
        card.className = 'agent-message';
        card.innerHTML = `
      <div class="agent-msg-role ${escapeHtml(roleClass)}">
        <span class="agent-msg-role-label">${escapeHtml(roleLabel)}</span>
        <span class="agent-msg-time">${escapeHtml(ts)}</span>
      </div>
      ${title ? `<div class="agent-msg-title">${escapeHtml(title)}</div>` : ''}
      ${response ? `<div class="agent-msg-response">${formattedResponse}</div>` : ''}
      ${promptExcerpt ? `<details class="agent-msg-context"><summary>Context</summary><div class="agent-msg-excerpt">${escapeHtml(promptExcerpt)}</div></details>` : ''}
    `;

        feed.appendChild(card);
        feed.scrollTop = feed.scrollHeight;
    }

    function _resetAgentMonitor() {
        ['deepseek', 'qwen', 'perplexity'].forEach(col => {
            _agentMsgCount[col] = 0;
            const feed = document.getElementById(`agentFeed-${col}`);
            const badge = document.getElementById(`agentBadge-${col}`);
            if (feed) feed.innerHTML = '';
            if (badge) badge.textContent = '0';
        });
        const monitor = document.getElementById('agentMonitor');
        const modal = document.querySelector('.ai-build-modal-content');
        if (monitor) monitor.classList.add('hidden');
        if (modal) modal.classList.remove('has-agents');
    }

    // ── Public: toggleAgentMonitor ────────────────────────────────────────────
    function toggleAgentMonitor() {
        const cols = document.getElementById('agentColumns');
        const btn = document.getElementById('btnToggleAgentMonitor');
        if (!cols) return;
        const collapsed = cols.classList.toggle('hidden');
        if (btn) {
            btn.innerHTML = collapsed
                ? '<i class="bi bi-chevron-down"></i>'
                : '<i class="bi bi-chevron-up"></i>';
            btn.title = collapsed ? 'Show agent panel' : 'Hide agent panel';
        }
    }

    // ── Public: showAiBuildResults ────────────────────────────────────────────
    async function showAiBuildResults(data) {
        document.getElementById('aiBuildResults').classList.remove('hidden');

        const w = data.workflow || {};
        const rawBt = w.backtest_results || {};
        const apiMetrics = rawBt.results || rawBt.metrics || rawBt || {};
        const backtestId = rawBt.backtest_id || null;

        const iters = w.iterations || [];
        const lastIter = iters[iters.length - 1] || {};
        const ok = data.success;

        let bestIterIdx = 0;
        let bestSharpe = -Infinity;
        iters.forEach(function (it, idx) {
            if ((it.sharpe_ratio || 0) > bestSharpe) {
                bestSharpe = it.sharpe_ratio || 0;
                bestIterIdx = idx;
            }
        });

        const sharpe = lastIter.sharpe_ratio ?? apiMetrics.sharpe_ratio ?? 0;
        const winRate = lastIter.win_rate != null
            ? lastIter.win_rate
            : (apiMetrics.win_rate || 0) / 100;
        const netProfit = lastIter.net_profit ?? apiMetrics.net_profit ?? 0;
        const maxDd = lastIter.max_drawdown ?? apiMetrics.max_drawdown ?? 0;
        const totalTrades = lastIter.total_trades ?? apiMetrics.total_trades ?? 0;

        const wasOptimize = _aiBuildMode === 'optimize';
        const usedOptimizer = w.used_optimizer_mode || false;

        function metricColor(val, thresholds) {
            if (val >= thresholds[0]) return 'text-success fw-bold';
            if (val >= thresholds[1]) return 'text-warning fw-bold';
            return 'text-danger fw-bold';
        }

        const sharpeClass = metricColor(sharpe, [1.0, 0.3]);
        const winRateClass = metricColor(winRate * 100, [50, 35]);
        const profitClass = netProfit > 0 ? 'text-success fw-bold' : (netProfit === 0 ? 'text-secondary' : 'text-danger fw-bold');
        const ddClass = maxDd < 10 ? 'text-success' : (maxDd < 25 ? 'text-warning' : 'text-danger');
        const tradesClass = totalTrades >= 10 ? 'text-success' : (totalTrades > 0 ? 'text-warning' : 'text-danger fw-bold');
        const zeroTradesWarning = totalTrades === 0
            ? `<div class="alert alert-danger mt-2 py-2">
          <i class="bi bi-exclamation-triangle-fill"></i>
          <strong>0 Trades Detected!</strong>
          Check that indicator blocks are connected to <em>Entry Long / Entry Short</em> ports on the Strategy node.
          Review errors below.
         </div>`
            : '';

        let html = `
      <div class="alert ${ok ? 'alert-success' : 'alert-warning'} py-2 mb-2">
        <strong>${ok ? (wasOptimize ? '✅ Strategy Optimized!' : '✅ Strategy Built!') : '⚠️ Below Target'}</strong>
        — ${w.status || 'unknown'} in ${(w.duration_seconds || 0).toFixed(1)}s
        ${usedOptimizer ? '<span class="badge bg-primary ms-1">🎯 Optimizer</span>' : ''}
      </div>
      ${zeroTradesWarning}
      <div class="row g-2 mb-3">
        <div class="col-6 col-md-4">
          <div class="card card-body p-2 text-center">
            <div class="small text-muted">Sharpe Ratio</div>
            <div class="fs-5 ${sharpeClass}">${sharpe.toFixed(3)}</div>
          </div>
        </div>
        <div class="col-6 col-md-4">
          <div class="card card-body p-2 text-center">
            <div class="small text-muted">Win Rate</div>
            <div class="fs-5 ${winRateClass}">${(winRate * 100).toFixed(1)}%</div>
          </div>
        </div>
        <div class="col-6 col-md-4">
          <div class="card card-body p-2 text-center">
            <div class="small text-muted">Net Profit</div>
            <div class="fs-5 ${profitClass}">$${netProfit.toFixed(2)}</div>
          </div>
        </div>
        <div class="col-6 col-md-4">
          <div class="card card-body p-2 text-center">
            <div class="small text-muted">Max Drawdown</div>
            <div class="fs-5 ${ddClass}">${maxDd.toFixed(2)}%</div>
          </div>
        </div>
        <div class="col-6 col-md-4">
          <div class="card card-body p-2 text-center">
            <div class="small text-muted">Total Trades</div>
            <div class="fs-5 ${tradesClass}">${totalTrades}</div>
          </div>
        </div>
        <div class="col-6 col-md-4">
          <div class="card card-body p-2 text-center">
            <div class="small text-muted">Blocks / Connections</div>
            <div class="fs-5">${(w.blocks_added || []).length} / ${(w.connections_made || []).length}</div>
          </div>
        </div>
      </div>

      <div class="d-flex gap-2 mb-2 flex-wrap">
        <span class="badge bg-secondary">ID: ${(w.strategy_id || '—').substring(0, 8)}…</span>
        <span class="badge bg-secondary">Backtest: ${(backtestId || '—').substring(0, 8)}…</span>
        <span class="badge bg-info text-dark">${iters.length} iteration${iters.length !== 1 ? 's' : ''}</span>
      </div>`;

        if (iters.length > 0) {
            html += `
      <details open class="mb-3">
        <summary class="fw-semibold mb-1" style="cursor:pointer">📊 Iterations</summary>
        <div class="table-responsive">
        <table class="table table-sm table-hover table-bordered mb-0" style="font-size:0.82rem">
          <thead class="table-dark">
            <tr>
              <th>#</th><th>Sharpe</th><th>Win Rate</th>
              <th>Net Profit</th><th>Trades</th><th>Max DD</th><th>OK?</th>
            </tr>
          </thead>
          <tbody>`;
            iters.forEach(function (it, idx) {
                const isBest = idx === bestIterIdx && iters.length > 1;
                const itSharpe = (it.sharpe_ratio || 0).toFixed(3);
                const itWR = ((it.win_rate || 0) * 100).toFixed(1);
                const itProfit = (it.net_profit || 0).toFixed(2);
                const itDD = (it.max_drawdown || 0).toFixed(2);
                const itTrades = it.total_trades || 0;
                const itOk = it.acceptable;
                const rowClass = isBest ? 'table-success' : (itOk ? 'table-info' : '');
                html += `<tr class="${rowClass}">
          <td>${it.iteration}${isBest ? ' ⭐' : ''}</td>
          <td>${itSharpe}</td>
          <td>${itWR}%</td>
          <td class="${parseFloat(itProfit) > 0 ? 'text-success' : (parseFloat(itProfit) < 0 ? 'text-danger' : '')}">
            $${itProfit}
          </td>
          <td class="${itTrades === 0 ? 'text-danger fw-bold' : ''}">${itTrades}</td>
          <td>${itDD}%</td>
          <td>${itOk ? '✅' : '❌'}</td>
        </tr>`;
            });
            html += '</tbody></table></div></details>';
        }

        if (w.deliberation && w.deliberation.decision) {
            html += `
        <details class="mb-2">
          <summary class="fw-semibold" style="cursor:pointer">🤖 AI Deliberation
            (${(w.deliberation.confidence * 100).toFixed(0)}% confidence)
          </summary>
          <div class="alert alert-info mt-1 mb-0 py-2">
            <small>${escapeHtml(w.deliberation.decision.substring(0, 500))}${w.deliberation.decision.length > 500 ? '…' : ''}</small>
          </div>
        </details>`;
        }

        if (w.errors && w.errors.length > 0) {
            html += `
      <details open class="mb-2">
        <summary class="fw-semibold text-danger" style="cursor:pointer">
          ❌ Errors (${w.errors.length})
        </summary>
        <ul class="list-unstyled mb-0 mt-1">`;
            w.errors.forEach(function (e) {
                html += `<li class="small text-danger border-start border-danger ps-2 mb-1">${escapeHtml(e)}</li>`;
            });
            html += '</ul></details>';
        }

        if (backtestId) {
            html += `
        <button class="btn btn-outline-primary btn-sm mt-2"
                onclick="viewAiBacktestFullResults('${backtestId}')">
          📊 View Full Results
        </button>`;
        }

        document.getElementById('aiBuildResultContent').innerHTML = html;

        if (backtestId && typeof displayBacktestResults === 'function') {
            try {
                const resp = await fetch(`/api/v1/backtests/${backtestId}`);
                if (resp.ok) {
                    const fullResults = await resp.json();
                    fullResults.backtest_id = backtestId;
                    console.log('[AI Build] Opening full backtest results modal for', backtestId);
                    displayBacktestResults(fullResults);
                } else {
                    console.warn('[AI Build] Could not fetch full backtest results:', resp.status);
                }
            } catch (err) {
                console.warn('[AI Build] Failed to load full backtest results:', err);
            }
        }

        console.log('[AI Build] Loading optimized strategy onto canvas:', w.strategy_id);

        if (w.strategy_id && typeof loadStrategy === 'function') {
            try {
                await loadStrategy(w.strategy_id);
                console.log('[AI Build] Optimized strategy loaded onto canvas:', w.strategy_id);

                const newUrl = new URL(window.location);
                newUrl.searchParams.set('id', w.strategy_id);
                window.history.replaceState({}, '', newUrl);
            } catch (err) {
                console.error('[AI Build] Failed to reload strategy onto canvas:', err);
            }
        }
    }

    // ── Public: viewAiBacktestFullResults ─────────────────────────────────────
    function viewAiBacktestFullResults(backtestId) {
        if (backtestId) {
            window.open(`/frontend/backtest-results.html?backtest_id=${backtestId}`, '_blank');
        }
    }

    // ── Public API ────────────────────────────────────────────────────────────
    return {
        openAiBuildModal,
        closeAiBuildModal,
        applyAiPreset,
        resetAiBuild,
        runAiBuild,
        showAiBuildResults,
        toggleAgentMonitor,
        viewAiBacktestFullResults
    };
}
