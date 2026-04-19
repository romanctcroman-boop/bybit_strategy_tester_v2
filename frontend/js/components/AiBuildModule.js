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
    const _agentMsgCount = { deepseek: 0, qwen: 0, perplexity: 0, claude: 0 };

    // ── Helper: load strategies from DB into #aiExistingStrategy ─────────────
    async function _loadStrategiesList() {
        const sel = document.getElementById('aiExistingStrategy');
        if (!sel) return;
        try {
            const resp = await fetch('/api/v1/strategies/?page_size=100');
            if (!resp.ok) return;
            const data = await resp.json();
            const strategies = Array.isArray(data) ? data : (data.items || data.strategies || []);
            // keep first empty option
            sel.innerHTML = '<option value="">— Create New Strategy —</option>';
            strategies.forEach(s => {
                const opt = document.createElement('option');
                opt.value = s.id || s.strategy_id || '';
                const symbol = s.symbol || '';
                const tf = s.timeframe ? s.timeframe + 'm' : '';
                const name = s.name || s.strategy_name || s.id || '?';
                opt.textContent = `${name}${symbol ? ' · ' + symbol : ''}${tf ? ' · ' + tf : ''}`;
                opt.dataset.stratName = name;
                sel.appendChild(opt);
            });
        } catch (e) {
            console.warn('[AI Build] Could not load strategies:', e);
        }
    }

    // ── Helper: apply mode based on #aiExistingStrategy selection ────────────
    function _applyExistingStrategySelection() {
        const sel = document.getElementById('aiExistingStrategy');
        const hint = document.getElementById('aiExistingStrategyHint');
        const nameHint = document.getElementById('aiNameHint');
        const aiNameEl = document.getElementById('aiName');
        const presetSection = document.getElementById('aiPresetSection');
        const blocksPreview = document.getElementById('aiBlocksPreview');
        const btnRun = document.getElementById('btnRunAiBuild');
        const modal = document.getElementById('aiBuildModal');
        const titleEl = modal?.querySelector('.ai-build-header h3');
        const descriptionEl = document.getElementById('aiDescription');

        const selectedId = sel?.value || '';

        if (selectedId) {
            // ── Optimize mode ──
            _aiBuildMode = 'optimize';
            _aiBuildExistingStrategyId = selectedId;
            const selOption = sel.options[sel.selectedIndex];
            const stratName = selOption?.dataset?.stratName || selOption?.text || 'Strategy';

            if (hint) hint.style.display = 'block';
            if (nameHint) nameHint.textContent = '(name to save optimization result as)';
            if (aiNameEl) aiNameEl.value = `Opt_${stratName}`;
            if (presetSection) presetSection.style.display = 'none';
            if (blocksPreview) blocksPreview.textContent = 'AI will load blocks from the selected strategy and optimize parameters.';
            if (descriptionEl) descriptionEl.placeholder = 'Describe what to improve (optional)';
            if (btnRun) btnRun.innerHTML = '<i class="bi bi-stars"></i> Optimize & Backtest';
            if (titleEl) titleEl.innerHTML = '<i class="bi bi-stars"></i> AI Strategy Optimizer';
        } else {
            // ── Build mode ──
            _aiBuildMode = 'build';
            _aiBuildExistingStrategyId = null;

            if (hint) hint.style.display = 'none';
            if (nameHint) nameHint.textContent = '(name for new strategy)';
            if (presetSection) presetSection.style.display = '';
            if (descriptionEl) descriptionEl.placeholder = 'e.g. RSI mean-reversion with EMA trend filter, SL 1.5%, TP 3%';
            if (btnRun) btnRun.innerHTML = '<i class="bi bi-play-fill"></i> Build & Backtest';
            if (titleEl) titleEl.innerHTML = '<i class="bi bi-robot"></i> AI Strategy Builder';
            applyAiPreset();
        }
    }

    // ── Public: openAiBuildModal ──────────────────────────────────────────────
    function openAiBuildModal() {
        // Reset to config form only if a run is NOT currently in progress
        const progressEl = document.getElementById('aiBuildProgress');
        const isRunning = progressEl && !progressEl.classList.contains('hidden');
        if (!isRunning) resetAiBuild();

        const modal = document.getElementById('aiBuildModal');
        modal.classList.remove('hidden');
        modal.style.display = 'flex';

        // Load strategies list (async, non-blocking)
        _loadStrategiesList().then(() => {
            // After loading, if canvas already has a strategy → pre-select it
            const existingId = getStrategyIdFromURL();
            const blocks = getBlocks();
            const hasCanvasBlocks = blocks.length > 0;
            const sel = document.getElementById('aiExistingStrategy');
            if (existingId && hasCanvasBlocks && sel) {
                // Try to find the option
                const matchOpt = Array.from(sel.options).find(o => o.value === existingId);
                if (matchOpt) {
                    sel.value = existingId;
                } else {
                    // Canvas has a strategy not yet in the list → add it
                    const stratName = document.getElementById('strategyName')?.value || existingId;
                    const opt = document.createElement('option');
                    opt.value = existingId;
                    opt.textContent = stratName;
                    opt.dataset.stratName = stratName;
                    sel.appendChild(opt);
                    sel.value = existingId;
                }
            }
            _applyExistingStrategySelection();
        });

        // Fill summary
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
                warning = '<div class="summary-warning"><i class="bi bi-exclamation-triangle"></i> Select a Symbol in the Parameters panel</div>';
            }
            summaryEl.innerHTML = `
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
        // Hide inline header status
        const headerStatus = document.getElementById('aiBuildHeaderStatus');
        if (headerStatus) headerStatus.classList.add('hidden');
        // Remove expanded-modal class left over from a previous run
        const modalContent = document.querySelector('.ai-build-modal-content');
        if (modalContent) modalContent.classList.remove('has-agents');
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
            alert('Please select a Symbol in the Parameters panel');
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
            agent: document.getElementById('aiAgentSelect')?.value || 'qwen',
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
                source_block_id: c.sourceBlockId || c.source_block_id || (c.source?.blockId ?? (typeof c.source === 'string' ? c.source : '')) || '',
                source_port: c.sourcePort || c.source_port || c.source?.portId || 'output',
                target_block_id: c.targetBlockId || c.target_block_id || (c.target?.blockId ?? (typeof c.target === 'string' ? c.target : '')) || '',
                target_port: c.targetPort || c.target_port || c.target?.portId || 'input'
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

        // Show inline header status
        const headerStatus = document.getElementById('aiBuildHeaderStatus');
        if (headerStatus) headerStatus.classList.remove('hidden');

        const stageEl = document.getElementById('aiBuildStage');
        if (stageEl) {
            stageEl.textContent = _aiBuildMode === 'optimize'
                ? 'Optimizing strategy with AI agent…'
                : (description ? `Planning: "${description.substring(0, 60)}…"` : 'Building strategy with AI agent…');
        }

        // Elapsed timer — static element in header
        const timerEl = document.getElementById('aiBuildElapsed');
        const _startTime = Date.now();
        if (timerEl) timerEl.textContent = '0s elapsed';
        const _timerInterval = setInterval(() => {
            const elapsed = Math.floor((Date.now() - _startTime) / 1000);
            if (timerEl) timerEl.textContent = `${elapsed}s elapsed`;
        }, 1000);

        try {
            await _runAiBuildWithSSE(payload);
        } catch (err) {
            document.getElementById('aiBuildProgress').classList.add('hidden');
            document.getElementById('aiBuildResults').classList.remove('hidden');
            document.getElementById('aiBuildResultContent').innerHTML =
                `<div class="ai-result-warn"><i class="bi bi-exclamation-triangle-fill"></i> ${escapeHtml(err.message)}</div>`;
        } finally {
            clearInterval(_timerInterval);
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

    /** Meta per-agent: icon class + display name */
    const _agentMeta = {
        deepseek:   { icon: 'bi-stars',           name: 'DeepSeek' },
        qwen:       { icon: 'bi-lightning-charge', name: 'Qwen' },
        perplexity: { icon: 'bi-search',           name: 'Perplexity' },
        claude:     { icon: 'bi-robot',            name: 'Claude' }
    };

    function _appendAgentLog(log) {
        const agent = (log.agent || '').toLowerCase();
        const role = (log.role || 'unknown').toLowerCase();
        const title = log.title || '';
        const promptExcerpt = log.prompt_excerpt || '';
        const response = log.response || '';
        const ts = log.ts ? new Date(log.ts).toLocaleTimeString() : '';

        // Unknown / system agents fall back to the selected single-agent
        const _selectedAgent = (document.getElementById('aiAgentSelect')?.value || 'deepseek').toLowerCase();
        const col = _agentMeta[agent] ? agent : _selectedAgent;

        _ensureAgentMonitorVisible();

        // Route to the per-agent column feed
        const feed = document.getElementById(`agentFeed-${col}`);
        if (!feed) return;

        // Per-agent badge
        _agentMsgCount[col] = (_agentMsgCount[col] || 0) + 1;
        const badge = document.getElementById(`agentBadge-${col}`);
        if (badge) badge.textContent = _agentMsgCount[col];

        const roleClass = `role-${role}`;
        const roleLabel = { planner: 'Planner', deliberation: 'Deliberation', optimizer: 'Optimizer' }[role] || role;

        const formattedResponse = escapeHtml(response)
            .replace(/\*\*(.+?)\*\*/gs, '<strong>$1</strong>')
            .replace(/\*([^*\n]+)\*/g, '<em>$1</em>')
            .replace(/`([^`\n]+)`/g, '<code>$1</code>')
            .replace(/^#{1,3} (.+)$/gm, '<strong>$1</strong>')
            .replace(/^[*\-] (.+)$/gm, '• $1')
            .replace(/\n/g, '<br>');

        const card = document.createElement('div');
        card.className = 'agent-message';
        card.dataset.agent = col;
        card.innerHTML = `
      <div class="agent-msg-header">
        ${role !== 'unknown' ? `<span class="agent-msg-role-badge ${escapeHtml(roleClass)}">${escapeHtml(roleLabel)}</span>` : ''}
        <span class="agent-msg-time">${escapeHtml(ts)}</span>
      </div>
      ${title ? `<div class="agent-msg-title">${escapeHtml(title)}</div>` : ''}
      ${response ? `<div class="agent-msg-response">${formattedResponse}</div>` : ''}
      ${promptExcerpt ? `<details class="agent-msg-context"><summary>Context</summary><div class="agent-msg-excerpt">${escapeHtml(promptExcerpt)}</div></details>` : ''}
    `;

        // Smart auto-scroll: only scroll if user is already near the bottom
        const isNearBottom = feed.scrollTop + feed.clientHeight >= feed.scrollHeight - 20;
        feed.appendChild(card);
        if (isNearBottom) feed.scrollTop = feed.scrollHeight;
    }

    function _resetAgentMonitor() {
        ['deepseek', 'qwen', 'perplexity', 'claude'].forEach(col => {
            _agentMsgCount[col] = 0;
            const badge = document.getElementById(`agentBadge-${col}`);
            if (badge) badge.textContent = '0';
            const feed = document.getElementById(`agentFeed-${col}`);
            if (feed) feed.innerHTML = '';
        });

        // Show the monitor immediately so users can see agent activity from the start
        const monitor = document.getElementById('agentMonitor');
        const modal = document.querySelector('.ai-build-modal-content');
        if (monitor) monitor.classList.remove('hidden');
        if (modal) modal.classList.add('has-agents');
    }

    // ── Public: toggleAgentMonitor ────────────────────────────────────────────
    function toggleAgentMonitor() {
        const cols = document.getElementById('agentCols');
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
        const sortino = lastIter.sortino_ratio ?? apiMetrics.sortino_ratio ?? 0;
        const winRate = lastIter.win_rate != null
            ? lastIter.win_rate
            : (apiMetrics.win_rate || 0) / 100;
        const netProfit = lastIter.net_profit ?? apiMetrics.net_profit ?? 0;
        const maxDd = lastIter.max_drawdown ?? apiMetrics.max_drawdown ?? 0;
        const totalTrades = lastIter.total_trades ?? apiMetrics.total_trades ?? 0;

        // Composite quality score: same formula as backend composite_quality_score()
        // score = Sharpe × Sortino × log(1+trades) / (1 + maxDD/100), capped at 1000
        function calcCompositeScore(sh, so, tr, dd) {
            if (sh <= 0 || so <= 0) return 0.0;
            const raw = sh * so * Math.log1p(tr) / (1 + Math.abs(dd) / 100);
            return Math.min(1000, Math.max(0, raw));
        }
        const compositeScore = calcCompositeScore(sharpe, sortino, totalTrades, maxDd);

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
        // ── Status header ─────────────────────────────────────────────────────
        const statusIcon = ok ? (wasOptimize ? 'bi-stars' : 'bi-check-circle-fill') : 'bi-exclamation-triangle-fill';
        const statusLabel = ok ? (wasOptimize ? 'Strategy Optimized' : 'Strategy Built') : 'Below Target';
        const statusMod = ok ? 'is-ok' : 'is-warn';
        const dur = (w.duration_seconds || 0).toFixed(1);

        const savedName = w.final_version_name || '';
        let html = `<div class="ai-result-status ${statusMod}">
      <i class="bi ${statusIcon}"></i>
      <span class="ai-result-status-label">${statusLabel}</span>
      ${savedName ? `<span class="ai-result-saved-name" title="Saved as"><i class="bi bi-floppy"></i> ${escapeHtml(savedName)}</span>` : ''}
      <span class="ai-result-status-meta">${w.status || ''} · ${dur}s${usedOptimizer ? ' · Optimizer' : ''}</span>
    </div>`;

        // ── Zero-trades warning ───────────────────────────────────────────────
        if (totalTrades === 0) {
            html += `<div class="ai-result-warn">
      <i class="bi bi-exclamation-triangle-fill"></i>
      <strong>0 Trades</strong> — check that indicator blocks are wired to Entry Long / Entry Short ports on the Strategy node.
    </div>`;
        }

        // ── Metrics grid ─────────────────────────────────────────────────────
        html += `<div class="ai-metrics-grid">
      <div class="ai-metric-card">
        <div class="ai-metric-label">Sharpe Ratio</div>
        <div class="ai-metric-value ${sharpeClass}">${sharpe.toFixed(3)}</div>
      </div>
      <div class="ai-metric-card">
        <div class="ai-metric-label">Sortino</div>
        <div class="ai-metric-value ${metricColor(sortino, [1.0, 0.3])}">${sortino.toFixed(3)}</div>
      </div>
      <div class="ai-metric-card">
        <div class="ai-metric-label">Win Rate</div>
        <div class="ai-metric-value ${winRateClass}">${(winRate * 100).toFixed(1)}%</div>
      </div>
      <div class="ai-metric-card">
        <div class="ai-metric-label">Net Profit</div>
        <div class="ai-metric-value ${profitClass}">$${netProfit.toFixed(2)}</div>
      </div>
      <div class="ai-metric-card">
        <div class="ai-metric-label">Max Drawdown</div>
        <div class="ai-metric-value ${ddClass}">${maxDd.toFixed(2)}%</div>
      </div>
      <div class="ai-metric-card">
        <div class="ai-metric-label">Trades</div>
        <div class="ai-metric-value ${tradesClass}">${totalTrades}</div>
      </div>
    </div>`;

        // ── AI Score bar ──────────────────────────────────────────────────────
        const scoreClass = compositeScore >= 1.0 ? 'is-good' : compositeScore > 0 ? 'is-mid' : 'is-bad';
        const candidatesMeta = w.candidates_count > 1
            ? `${w.candidates_count} candidates${w.agreement_score != null ? ` · ${(w.agreement_score * 100).toFixed(0)}% agreement` : ''}`
            : '';
        html += `<div class="ai-score-bar">
      <span class="ai-score-label">AI Score</span>
      <span class="ai-score-value ${scoreClass}" title="Sharpe × Sortino × ln(1+trades) / (1 + DD%)">${compositeScore.toFixed(2)}</span>
      ${candidatesMeta ? `<span class="ai-score-meta">${candidatesMeta}</span>` : ''}
    </div>`;

        // ── Meta badges ───────────────────────────────────────────────────────
        html += `<div class="ai-meta-bar">
      <span class="ai-meta-chip" title="Strategy ID">${(w.strategy_id || '—').substring(0, 8)}…</span>
      <span class="ai-meta-chip" title="Backtest ID">${(backtestId || '—').substring(0, 8)}…</span>
      <span class="ai-meta-chip is-accent">${iters.length} iteration${iters.length !== 1 ? 's' : ''}</span>
      ${w.final_version_name ? `<span class="ai-meta-chip is-saved" title="Saved as new version">💾 ${escapeHtml(w.final_version_name)}</span>` : ''}
    </div>`;

        // ── Saved banner + load button ────────────────────────────────────────
        if (w.final_version_name && w.final_version_id) {
            html += `<div class="ai-saved-banner">
      <i class="bi bi-floppy2-fill"></i>
      <span>Saved as <strong>${escapeHtml(w.final_version_name)}</strong></span>
      <button class="ai-action-btn is-primary" id="btnLoadAiFinalVersion"
        data-version-id="${escapeHtml(w.final_version_id)}"
        data-version-name="${escapeHtml(w.final_version_name)}">
        <i class="bi bi-folder2-open"></i> Load onto Canvas
      </button>
    </div>`;
        }

        // ── Iterations table ──────────────────────────────────────────────────
        if (iters.length > 0) {
            html += `<details class="ai-detail-block" open>
      <summary><i class="bi bi-bar-chart-steps"></i> Iterations <span class="ai-detail-count">${iters.length}</span></summary>
      <div class="ai-iter-table-wrap">
      <table class="ai-iter-table">
        <thead><tr><th>#</th><th>Sharpe</th><th>Win Rate</th><th>Profit</th><th>Trades</th><th>DD</th><th></th></tr></thead>
        <tbody>`;
            iters.forEach(function (it, idx) {
                const isBest = idx === bestIterIdx && iters.length > 1;
                const profit = (it.net_profit || 0).toFixed(2);
                const profitSign = parseFloat(profit) > 0 ? 'pos' : parseFloat(profit) < 0 ? 'neg' : '';
                const itOk = it.acceptable;
                html += `<tr class="${isBest ? 'is-best' : itOk ? 'is-ok' : ''}">
          <td>${it.iteration}${isBest ? ' ⭐' : ''}</td>
          <td>${(it.sharpe_ratio || 0).toFixed(3)}</td>
          <td>${((it.win_rate || 0) * 100).toFixed(1)}%</td>
          <td class="${profitSign}">$${profit}</td>
          <td class="${(it.total_trades || 0) === 0 ? 'zero' : ''}">${it.total_trades || 0}</td>
          <td>${(it.max_drawdown || 0).toFixed(2)}%</td>
          <td>${itOk ? '✓' : '✗'}</td>
        </tr>`;
            });
            html += '</tbody></table></div></details>';
        }

        // ── Deliberation ──────────────────────────────────────────────────────
        if (w.deliberation && w.deliberation.decision) {
            const conf = (w.deliberation.confidence * 100).toFixed(0);
            const decText = escapeHtml(w.deliberation.decision.substring(0, 600)) +
                (w.deliberation.decision.length > 600 ? '…' : '');
            html += `<details class="ai-detail-block" open>
      <summary><i class="bi bi-cpu"></i> AI Deliberation <span class="ai-detail-count">${conf}% confidence</span></summary>
      <div class="ai-deliberation-text">${decText}</div>
    </details>`;
        }

        // ── Errors ────────────────────────────────────────────────────────────
        if (w.errors && w.errors.length > 0) {
            html += `<details class="ai-detail-block is-error" open>
      <summary><i class="bi bi-x-circle-fill"></i> Errors <span class="ai-detail-count">${w.errors.length}</span></summary>
      <ul class="ai-error-list">`;
            w.errors.forEach(function (e) {
                html += `<li>${escapeHtml(e)}</li>`;
            });
            html += '</ul></details>';
        }

        // ── Action buttons row ────────────────────────────────────────────────
        if (backtestId) {
            html += `<div class="ai-result-actions">
      <button class="ai-action-btn" id="btnViewAiFullResults" data-backtest-id="${escapeHtml(backtestId)}">
        <i class="bi bi-bar-chart-line"></i> Full Results
      </button>
    </div>`;
        }

        document.getElementById('aiBuildResultContent').innerHTML = html;

        // Wire result buttons via data attributes (avoids inline onclick)
        const loadVersionBtn = document.getElementById('btnLoadAiFinalVersion');
        if (loadVersionBtn) {
            loadVersionBtn.addEventListener('click', () =>
                _loadAiFinalVersion(loadVersionBtn.dataset.versionId, loadVersionBtn.dataset.versionName));
        }
        const viewFullBtn = document.getElementById('btnViewAiFullResults');
        if (viewFullBtn) {
            viewFullBtn.addEventListener('click', () => viewAiBacktestFullResults(viewFullBtn.dataset.backtestId));
        }

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

        // Prefer the final named version (AI-N clone); fall back to working strategy
        const loadId = w.final_version_id || w.strategy_id;
        const loadName = w.final_version_name || '';
        console.log('[AI Build] Loading strategy onto canvas:', loadId, loadName || '');

        if (loadId && typeof loadStrategy === 'function') {
            try {
                await loadStrategy(loadId);
                console.log('[AI Build] Strategy loaded onto canvas:', loadId, loadName);

                const newUrl = new URL(window.location);
                newUrl.searchParams.set('id', loadId);
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

    // ── Public: load final saved version onto canvas ──────────────────────────
    async function _loadAiFinalVersion(strategyId, strategyName) {
        if (!strategyId) return;
        try {
            if (typeof loadStrategy === 'function') {
                await loadStrategy(strategyId);
                const newUrl = new URL(window.location);
                newUrl.searchParams.set('id', strategyId);
                window.history.replaceState({}, '', newUrl);
                console.log('[AI Build] Final version loaded onto canvas:', strategyName, strategyId);
            }
        } catch (err) {
            console.error('[AI Build] Failed to load final version:', err);
            alert('Failed to load final version: ' + err.message);
        }
    }
    // (no global window exposure needed — called via data-attr + addEventListener)

    // ── Wire deliberation toggle → hide/show agent select ────────────────────
    (function _wireControls() {
        // Deliberation checkbox ↔ single-agent select visibility
        const checkbox = document.getElementById('aiDeliberation');
        const agentRow = document.getElementById('aiAgentRow');
        if (checkbox && agentRow) {
            const syncVisibility = () => {
                agentRow.style.display = checkbox.checked ? 'none' : '';
            };
            syncVisibility();
            checkbox.addEventListener('change', syncVisibility);
        }

        // Existing strategy selector → switch Build / Optimize mode
        const existingSel = document.getElementById('aiExistingStrategy');
        if (existingSel) {
            existingSel.addEventListener('change', _applyExistingStrategySelection);

            // Reload list every time the dropdown is opened (catches deletions/renames)
            existingSel.addEventListener('mousedown', async () => {
                const prevValue = existingSel.value;
                await _loadStrategiesList();
                // Restore selection if the item still exists, else reset to empty
                if (prevValue && Array.from(existingSel.options).some(o => o.value === prevValue)) {
                    existingSel.value = prevValue;
                } else if (prevValue) {
                    existingSel.value = '';
                    _applyExistingStrategySelection();
                }
            });
        }

        // Refresh button → reload strategies list
        const refreshBtn = document.getElementById('btnRefreshStrategies');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', async () => {
                refreshBtn.disabled = true;
                refreshBtn.innerHTML = '<i class="bi bi-arrow-clockwise spin"></i>';
                await _loadStrategiesList();
                _applyExistingStrategySelection();
                refreshBtn.disabled = false;
                refreshBtn.innerHTML = '<i class="bi bi-arrow-clockwise"></i>';
            });
        }

        // Toggle agent monitor (no inline onclick in HTML)
        const toggleBtn = document.getElementById('btnToggleAgentMonitor');
        if (toggleBtn) toggleBtn.addEventListener('click', toggleAgentMonitor);

        // Close button
        const closeBtn = document.getElementById('btnCloseAiBuild');
        if (closeBtn) closeBtn.addEventListener('click', closeAiBuildModal);

        // Reset / Back button
        const resetBtn = document.getElementById('btnResetAiBuild');
        if (resetBtn) resetBtn.addEventListener('click', resetAiBuild);
    })();

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
