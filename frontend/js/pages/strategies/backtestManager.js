/**
 * 📄 Strategies Page - Backtest Manager
 *
 * Handles backtest modal, progress, execution and results display
 *
 * @version 1.0.0
 * @date 2025-12-23
 */

import { escapeHtml, formatPercent, sleep, showToast } from './utils.js';

const API_BASE = '/api/v1';

// Current backtest strategy ID (reserved for future use)
let _currentStrategyId = null;

// AbortController for canceling optimization request
let _optimizationAbortController = null;

/**
 * Cancel currently running optimization
 */
export function cancelOptimization() {
    if (_optimizationAbortController) {
        _optimizationAbortController.abort();
        _optimizationAbortController = null;
        showToast('⛔ Оптимизация отменена', 'warning');
        console.log('[cancelOptimization] Optimization aborted by user');
    }
}

/**
 * Open backtest modal for a strategy
 * @param {string} strategyId - Strategy UUID
 */
export async function openBacktestModal(strategyId) {
    _currentStrategyId = strategyId;
    document.getElementById('backtestStrategyId').value = strategyId;

    // Reset progress UI when opening modal
    resetBacktestProgress();
    // Hide previous results
    document.getElementById('backtestResults').classList.add('hidden');
    // Set default dates (last month)
    setBacktestPeriod('1m');

    // Load and display strategy info
    await loadBacktestStrategyInfo(strategyId);

    // Initialize optimization UI
    initOptimizationUI();

    document.getElementById('backtestModal').classList.add('active');
}

/**
 * Load strategy info and display in backtest modal
 * @param {string} strategyId - Strategy UUID
 */
export async function loadBacktestStrategyInfo(strategyId) {
    const infoContainer = document.getElementById('backtestStrategyInfo');
    if (!infoContainer) return;

    try {
        const response = await fetch(`${API_BASE}/strategies/${strategyId}`);
        if (!response.ok) throw new Error('Failed to load strategy');

        const strategy = await response.json();
        console.log('[loadBacktestStrategyInfo] Strategy loaded:', strategy);

        // Format strategy type display name
        const typeNames = {
            'rsi': 'RSI',
            'macd': 'MACD',
            'bollinger': 'Bollinger Bands',
            'bollinger_bands': 'Bollinger Bands',
            'sma_cross': 'SMA Cross',
            'sma_crossover': 'SMA Crossover',
            'ema_cross': 'EMA Cross',
            // Pyramiding strategies
            'grid': '📐 Grid (Сетка)',
            'dca': '📅 DCA (Усреднение)',
            'martingale': '🎰 Martingale',
            'custom': 'Custom'
        };
        const typeName = typeNames[strategy.strategy_type] || strategy.strategy_type;

        // Format parameters - filter out internal _prefixed ones
        const params = strategy.parameters || {};
        const displayParams = Object.entries(params)
            .filter(([key]) => !key.startsWith('_'))
            .map(([key, val]) => `<span class="param-tag">${key}: ${val}</span>`)
            .join(' ');

        // Get trading settings from parameters
        const leverage = params._leverage || 1;
        const direction = params._direction || 'both';
        const directionNames = { 'long': 'Long', 'short': 'Short', 'both': 'Long/Short' };

        // Calculate position size based on type
        const positionSizeType = params._position_size_type || 'percent';
        const orderAmount = params._order_amount || 0;
        const initialCapital = strategy.initial_capital || 10000;

        let positionSizeDisplay;
        if (positionSizeType === 'fixed_amount' && orderAmount > 0) {
            const effectiveSize = orderAmount * leverage;
            positionSizeDisplay = `$${orderAmount.toLocaleString()} × ${leverage}x = <strong>$${effectiveSize.toLocaleString()}</strong>`;
        } else {
            const positionPct = (strategy.position_size || 1) * 100;
            const effectiveSize = initialCapital * (strategy.position_size || 1) * leverage;
            positionSizeDisplay = `${positionPct}% × ${leverage}x = <strong>$${effectiveSize.toLocaleString()}</strong>`;
        }

        infoContainer.innerHTML = `
            <div class="strategy-info-card">
                <div class="strategy-info-header">
                    <span class="strategy-name">${escapeHtml(strategy.name)}</span>
                    <span class="strategy-type-badge">${escapeHtml(typeName)}</span>
                </div>
                <div class="strategy-info-details">
                    <div class="info-row">
                        <span class="info-label">Символ:</span>
                        <span class="info-value">${escapeHtml(strategy.symbol)}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Таймфрейм:</span>
                        <span class="info-value">${escapeHtml(strategy.timeframe)}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Капитал:</span>
                        <span class="info-value">$${initialCapital.toLocaleString()}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Размер позиции:</span>
                        <span class="info-value">${positionSizeDisplay}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Направление:</span>
                        <span class="info-value">${directionNames[direction]}</span>
                    </div>
                    <div class="info-row full-width">
                        <span class="info-label">Параметры стратегии:</span>
                        <span class="info-value params">${displayParams || 'По умолчанию'}</span>
                    </div>
                </div>
            </div>
        `;
    } catch (error) {
        console.error('Error loading strategy info:', error);
        infoContainer.innerHTML = '<div class="error-text">Не удалось загрузить информацию о стратегии</div>';
    }
}

/**
 * Close backtest modal
 */
export function closeBacktestModal() {
    document.getElementById('backtestModal').classList.remove('active');
    resetBacktestProgress();
    _currentStrategyId = null;
}

/**
 * Set backtest period from quick buttons
 * @param {string} period - '1d', '1w', '1m', '3m'
 */
export function setBacktestPeriod(period) {
    const endDate = new Date();
    const startDate = new Date();

    switch (period) {
    case '1d':
        startDate.setDate(startDate.getDate() - 1);
        break;
    case '1w':
        startDate.setDate(startDate.getDate() - 7);
        break;
    case '1m':
        startDate.setMonth(startDate.getMonth() - 1);
        break;
    case '3m':
        startDate.setMonth(startDate.getMonth() - 3);
        break;
    default:
        startDate.setMonth(startDate.getMonth() - 1);
    }

    // Format dates as YYYY-MM-DD for input[type="date"]
    document.getElementById('backtestStartDate').value = startDate.toISOString().split('T')[0];
    document.getElementById('backtestEndDate').value = endDate.toISOString().split('T')[0];

    // Update active button state
    document.querySelectorAll('.period-btn').forEach(btn => {
        btn.classList.remove('active');
        if (btn.dataset.period === period) {
            btn.classList.add('active');
        }
    });
}

/**
 * Initialize period buttons event listeners
 */
export function initPeriodButtons() {
    document.querySelectorAll('.period-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            setBacktestPeriod(btn.dataset.period);
        });
    });
}

/**
 * Reset backtest progress UI to initial state
 */
export function resetBacktestProgress() {
    const progressEl = document.getElementById('backtestProgress');
    const progressBar = document.getElementById('backtestProgressBar');
    const statusText = document.getElementById('backtestStatusText');
    const percentText = document.getElementById('backtestPercentText');
    const detailsText = document.getElementById('backtestProgressDetails');
    const btnText = document.getElementById('btnRunBacktestText');
    const btnSpinner = document.getElementById('btnRunBacktestSpinner');
    const btnRun = document.getElementById('btnRunBacktest');

    if (progressEl) progressEl.classList.add('hidden');
    if (progressBar) {
        progressBar.style.width = '0%';
        progressBar.classList.remove('indeterminate');
    }
    if (statusText) statusText.textContent = 'Инициализация...';
    if (percentText) percentText.textContent = '0%';
    if (detailsText) detailsText.textContent = 'Подготовка исторических данных...';
    if (btnText) btnText.textContent = 'Запустить';
    if (btnSpinner) btnSpinner.classList.add('hidden');
    if (btnRun) btnRun.disabled = false;

    // Reset worker progress bars
    resetWorkerBars();
}

// ============================================
// MULTI-THREAD PROGRESS TRACKING
// ============================================

let optimizationStartTime = null;
let totalCombinationsToProcess = 0;
let progressAnimationInterval = null;

/**
 * Reset all worker progress bars
 */
function resetWorkerBars() {
    // Stop animation if running
    if (progressAnimationInterval) {
        clearInterval(progressAnimationInterval);
        progressAnimationInterval = null;
    }

    const workerBars = document.getElementById('workerProgressBars');
    if (workerBars) {
        workerBars.querySelectorAll('.worker-bar').forEach(bar => {
            bar.style.width = '0%';
            bar.classList.remove('active');
        });
    }
    const speedEl = document.getElementById('progressSpeed');
    const etaEl = document.getElementById('progressEta');
    if (speedEl) {
        speedEl.textContent = '';
        speedEl.style.color = '';
    }
    if (etaEl) {
        etaEl.textContent = '';
        etaEl.style.color = '';
    }
}

/**
 * Start simulated progress animation for workers
 * Since API is synchronous, we simulate smooth progress until response arrives
 */
function startProgressAnimation(numWorkers, estimatedSeconds) {
    if (progressAnimationInterval) {
        clearInterval(progressAnimationInterval);
    }

    // Each worker starts at slightly different offset for visual effect
    const workerOffsets = Array.from({ length: numWorkers }, (_, i) => i * 0.15);
    const startTime = Date.now();
    // Ensure minimum animation time for visibility
    const animationDuration = Math.max(estimatedSeconds, 2);

    progressAnimationInterval = setInterval(() => {
        const elapsed = (Date.now() - startTime) / 1000;
        // Base progress grows smoothly, caps at 90% to leave room for completion
        const baseProgress = Math.min(90, (elapsed / animationDuration) * 85);

        // Update main progress bar
        const mainBar = document.getElementById('backtestProgressBar');
        if (mainBar) {
            mainBar.style.width = `${baseProgress}%`;
            mainBar.classList.remove('indeterminate');
        }
        const percentText = document.getElementById('backtestPercentText');
        if (percentText) {
            percentText.textContent = `${Math.round(baseProgress)}%`;
        }

        // Update each worker with staggered progress (each slightly behind previous)
        for (let i = 0; i < numWorkers; i++) {
            const workerProgress = Math.max(0, Math.min(95, baseProgress - workerOffsets[i] * 10 + (i * 2)));
            updateWorkerProgress(i, workerProgress);
        }

        // Update speed estimate
        const speedEl = document.getElementById('progressSpeed');
        const etaEl = document.getElementById('progressEta');
        const estSpeed = Math.round(totalCombinationsToProcess / animationDuration);

        if (speedEl) {
            speedEl.textContent = `⚡ ~${estSpeed.toLocaleString()} комб/сек`;
        }
        if (etaEl) {
            const remaining = Math.max(0, animationDuration - elapsed);
            if (remaining < 60) {
                etaEl.textContent = `⏱️ ~${Math.ceil(remaining)} сек`;
            } else {
                etaEl.textContent = `⏱️ ~${Math.ceil(remaining / 60)} мин`;
            }
        }
    }, 50);  // Faster updates for smoother animation
}

/**
 * Initialize multi-thread progress for optimization
 * @param {number} numWorkers - Number of parallel workers
 * @param {number} totalCombinations - Total combinations to process
 * @param {number} estimatedSeconds - Estimated time in seconds
 */
export function initMultiThreadProgress(numWorkers, totalCombinations, estimatedSeconds = 5) {
    optimizationStartTime = Date.now();
    totalCombinationsToProcess = totalCombinations;

    const workerBarsContainer = document.getElementById('workerProgressBars');
    if (workerBarsContainer) {
        // Show only the needed worker bars
        const rows = workerBarsContainer.querySelectorAll('.worker-bar-row');
        rows.forEach((row, index) => {
            if (index < numWorkers) {
                row.style.display = 'flex';
                const bar = row.querySelector('.worker-bar');
                if (bar) {
                    bar.style.width = '0%';
                    bar.classList.add('active');
                }
            } else {
                row.style.display = 'none';
            }
        });
        workerBarsContainer.style.gridTemplateColumns = `repeat(${Math.min(numWorkers, 4)}, 1fr)`;
    }

    // Start animated progress simulation
    startProgressAnimation(numWorkers, estimatedSeconds);
}

/**
 * Update individual worker progress
 * @param {number} workerId - Worker index (0-based)
 * @param {number} percent - Progress percentage for this worker
 */
export function updateWorkerProgress(workerId, percent) {
    const bar = document.getElementById(`workerBar${workerId}`);
    if (bar) {
        bar.style.width = `${percent}%`;
    }
}

/**
 * Update progress statistics (speed and ETA)
 * @param {number} completedCombinations - Number of completed combinations
 * @param {number} totalCombinations - Total combinations
 */
export function updateProgressStats(completedCombinations, totalCombinations) {
    const speedEl = document.getElementById('progressSpeed');
    const etaEl = document.getElementById('progressEta');

    if (!optimizationStartTime) return;

    const elapsed = (Date.now() - optimizationStartTime) / 1000;
    const speed = elapsed > 0 ? Math.round(completedCombinations / elapsed) : 0;
    const remaining = totalCombinations - completedCombinations;
    const etaSeconds = speed > 0 ? Math.ceil(remaining / speed) : 0;

    if (speedEl && speed > 0) {
        speedEl.textContent = `⚡ ${speed.toLocaleString()} комб/сек`;
    }

    if (etaEl && etaSeconds > 0) {
        if (etaSeconds < 60) {
            etaEl.textContent = `⏱️ ~${etaSeconds} сек`;
        } else if (etaSeconds < 3600) {
            etaEl.textContent = `⏱️ ~${Math.ceil(etaSeconds / 60)} мин`;
        } else {
            etaEl.textContent = `⏱️ ~${(etaSeconds / 3600).toFixed(1)} ч`;
        }
    }
}

/**
 * Complete multi-thread progress (all workers done)
 * @param {number} actualSpeed - Actual speed from server response
 * @param {number} actualTime - Actual execution time in seconds
 */
export function completeMultiThreadProgress(actualSpeed = null, actualTime = null) {
    // Stop animation
    if (progressAnimationInterval) {
        clearInterval(progressAnimationInterval);
        progressAnimationInterval = null;
    }

    // Complete main progress bar
    const mainBar = document.getElementById('backtestProgressBar');
    if (mainBar) {
        mainBar.style.width = '100%';
        mainBar.classList.remove('indeterminate');
    }
    const percentText = document.getElementById('backtestPercentText');
    if (percentText) {
        percentText.textContent = '100%';
    }

    // Complete worker bars
    const workerBarsContainer = document.getElementById('workerProgressBars');
    if (workerBarsContainer) {
        workerBarsContainer.querySelectorAll('.worker-bar').forEach(bar => {
            bar.style.width = '100%';
            bar.classList.remove('active');
        });
    }

    // Show final speed
    const elapsed = actualTime || (optimizationStartTime ? (Date.now() - optimizationStartTime) / 1000 : 0);
    const finalSpeed = actualSpeed || (elapsed > 0 ? Math.round(totalCombinationsToProcess / elapsed) : 0);

    const speedEl = document.getElementById('progressSpeed');
    if (speedEl && finalSpeed > 0) {
        speedEl.textContent = `✅ ${finalSpeed.toLocaleString()} комб/сек`;
        speedEl.style.color = '#4ecca3';
    }

    const etaEl = document.getElementById('progressEta');
    if (etaEl && elapsed > 0) {
        etaEl.textContent = `Готово за ${elapsed.toFixed(1)} сек`;
        etaEl.style.color = '#4ecca3';
    }

    optimizationStartTime = null;
}

/**
 * Update backtest progress UI
 * @param {string} status - Status text
 * @param {number} percent - Progress percentage (0-100), -1 for indeterminate
 * @param {string} details - Detailed progress message
 */
export function updateBacktestProgress(status, percent, details) {
    console.log('[Backtest Progress]', { status, percent, details });
    const progressEl = document.getElementById('backtestProgress');
    const progressBar = document.getElementById('backtestProgressBar');
    const statusText = document.getElementById('backtestStatusText');
    const percentText = document.getElementById('backtestPercentText');
    const detailsText = document.getElementById('backtestProgressDetails');

    console.log('[Progress Elements]', { progressEl, progressBar, statusText, percentText, detailsText });

    if (progressEl) progressEl.classList.remove('hidden');

    if (progressBar) {
        if (percent === -1) {
            progressBar.classList.add('indeterminate');
            if (percentText) percentText.textContent = '...';
        } else {
            progressBar.classList.remove('indeterminate');
            progressBar.style.width = `${percent}%`;
            if (percentText) percentText.textContent = `${Math.round(percent)}%`;
        }
    }

    if (statusText) statusText.textContent = status;
    if (detailsText) detailsText.textContent = details;
}

/**
 * Run backtest for current strategy
 * @param {Function} onComplete - Callback when backtest completes (to refresh strategies)
 */
export async function runBacktest(onComplete = null) {
    console.log('[runBacktest] Starting...');
    const strategyId = document.getElementById('backtestStrategyId').value;
    console.log('[runBacktest] strategyId:', strategyId);
    const startDateStr = document.getElementById('backtestStartDate').value;
    const endDateStr = document.getElementById('backtestEndDate').value;

    // Date validation
    if (!startDateStr || !endDateStr) {
        showToast('Выберите даты начала и окончания', 'error');
        return;
    }

    const startDate = new Date(startDateStr);
    const endDate = new Date(endDateStr);
    const now = new Date();

    if (startDate >= endDate) {
        showToast('Дата начала должна быть раньше даты окончания', 'error');
        return;
    }

    if (endDate > now) {
        showToast('Дата окончания не может быть в будущем', 'error');
        return;
    }

    const daysDiff = (endDate - startDate) / (1000 * 60 * 60 * 24);
    if (daysDiff > 365 * 5) {
        showToast('Период бэктеста не может превышать 5 лет', 'error');
        return;
    }

    if (daysDiff < 1) {
        showToast('Период бэктеста должен быть минимум 1 день', 'error');
        return;
    }

    const data = {
        start_date: startDateStr + 'T00:00:00Z',
        end_date: endDateStr + 'T23:59:59Z',
        save_result: document.getElementById('backtestSaveResult')?.checked || false
    };

    // Get UI elements (use same button as optimization - they share the button)
    const btnRun = document.getElementById('btnRunOptimization');
    const btnText = document.getElementById('btnRunOptimizationText');
    const btnSpinner = document.getElementById('btnRunOptimizationSpinner');
    const resultsSection = document.getElementById('backtestResults');

    try {
        // Hide previous results
        if (resultsSection) resultsSection.classList.add('hidden');

        // Show progress UI
        if (btnRun) btnRun.disabled = true;
        if (btnText) btnText.textContent = 'Выполняется...';
        if (btnSpinner) btnSpinner.classList.remove('hidden');

        // Phase 1: Initializing
        updateBacktestProgress('Инициализация...', 5, 'Подключение к серверу...');
        await sleep(200);

        // Phase 2: Fetching data
        updateBacktestProgress('Загрузка данных', 15, 'Скачивание исторических свечей с Bybit...');
        await sleep(300);

        // Phase 3: Running - use indeterminate progress during actual API call
        updateBacktestProgress('Выполнение бэктеста', -1, 'Анализ эффективности стратегии...');

        const response = await fetch(`${API_BASE}/backtests/from-strategy/${strategyId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });

        const result = await response.json();

        if (result.status === 'failed') {
            throw new Error(result.error_message || 'Ошибка бэктеста');
        }

        // Phase 4: Complete
        updateBacktestProgress('Готово!', 100, 'Бэктест успешно завершён');
        await sleep(300);

        const metrics = result.metrics;

        // If result was saved, redirect to metrics page
        if (data.save_result && result.backtest_id) {
            showToast(
                `✅ Бэктест завершён! Доходность: ${formatPercent(metrics?.total_return)}, ` +
                'Переход к метрикам...',
                'success'
            );

            // Close modal and redirect to metrics page
            closeBacktestModal();

            setTimeout(() => {
                window.location.replace(`/frontend/backtest-results.html?id=${result.backtest_id}&t=${Date.now()}`);
            }, 500);

            if (onComplete) onComplete();
            return;
        }

        // Display results in modal (if not redirecting)
        displayBacktestResults(result, startDate, endDate);

        // Reset button state
        if (btnRun) btnRun.disabled = false;
        if (btnText) btnText.textContent = '▶️ Запустить ещё';
        if (btnSpinner) btnSpinner.classList.add('hidden');

        // Callback to refresh strategies list
        if (onComplete) onComplete();

        showToast(
            `Бэктест завершён! Доходность: ${formatPercent(metrics?.total_return)}, ` +
            `Sharpe: ${metrics?.sharpe_ratio?.toFixed(2) || 'N/A'}`,
            'success'
        );
    } catch (error) {
        // Error state
        updateBacktestProgress('Ошибка', 0, error.message);
        showToast('Ошибка бэктеста: ' + error.message, 'error');

        // Reset button but keep progress visible
        if (btnRun) btnRun.disabled = false;
        if (btnText) btnText.textContent = '▶️ Повторить';
        if (btnSpinner) btnSpinner.classList.add('hidden');
    }
}

/**
 * Display backtest results in the modal
 * @param {Object} result - Backtest result from API
 * @param {Date} startDate - Start date
 * @param {Date} endDate - End date
 */
export function displayBacktestResults(result, startDate, endDate) {
    const resultsSection = document.getElementById('backtestResults');
    const metrics = result.metrics || {};

    // Total return
    const returnEl = document.getElementById('resultReturn');
    const totalReturn = metrics.total_return;
    if (returnEl) {
        returnEl.textContent = formatPercent(totalReturn);
        returnEl.className = 'result-value ' + (totalReturn >= 0 ? 'positive' : 'negative');
    }

    // Sharpe ratio
    const sharpeEl = document.getElementById('resultSharpe');
    if (sharpeEl) {
        sharpeEl.textContent = metrics.sharpe_ratio?.toFixed(2) || '-';
        sharpeEl.className = 'result-value ' + (metrics.sharpe_ratio >= 1 ? 'positive' : '');
    }

    // Win rate
    const winRateEl = document.getElementById('resultWinRate');
    const winRate = metrics.win_rate;
    if (winRateEl) {
        winRateEl.textContent = winRate != null ? winRate.toFixed(1) + '%' : '-';
        winRateEl.className = 'result-value ' + (winRate >= 50 ? 'positive' : 'negative');
    }

    // Max drawdown
    const drawdownEl = document.getElementById('resultDrawdown');
    const maxDD = metrics.max_drawdown;
    if (drawdownEl) {
        drawdownEl.textContent = maxDD != null ? (-Math.abs(maxDD)).toFixed(2) + '%' : '-';
        drawdownEl.className = 'result-value negative';
    }

    // Total trades
    const tradesEl = document.getElementById('resultTrades');
    if (tradesEl) {
        tradesEl.textContent = metrics.total_trades || '0';
    }

    // Profit factor
    const pfEl = document.getElementById('resultProfitFactor');
    const pf = metrics.profit_factor;
    if (pfEl) {
        pfEl.textContent = pf != null ? pf.toFixed(2) : '-';
        pfEl.className = 'result-value ' + (pf >= 1.5 ? 'positive' : (pf < 1 ? 'negative' : ''));
    }

    // Period info
    const periodEl = document.getElementById('resultPeriod');
    if (periodEl) {
        periodEl.textContent = `Период: ${startDate} — ${endDate}`;
    }

    // Show results section
    if (resultsSection) resultsSection.classList.remove('hidden');
}

// Expose to global scope for backwards compatibility
if (typeof window !== 'undefined') {
    window.openBacktestModal = openBacktestModal;
    window.closeBacktestModal = closeBacktestModal;
    window.runOptimization = runOptimization;
    window.setBacktestPeriod = setBacktestPeriod;
    window.updateCombinationsCount = updateCombinationsCount;
}

// Storage key for optimization parameters
const OPT_PARAMS_STORAGE_KEY = 'bybit_optimization_params';

/**
 * Save optimization parameters to localStorage
 */
function saveOptimizationParams() {
    const params = {};
    const optimizationInputs = [
        'optPeriodMin', 'optPeriodMax', 'optPeriodStep',
        'optOverboughtMin', 'optOverboughtMax', 'optOverboughtStep',
        'optOversoldMin', 'optOversoldMax', 'optOversoldStep',
        'optStopLossMin', 'optStopLossMax', 'optStopLossStep',
        'optTakeProfitMin', 'optTakeProfitMax', 'optTakeProfitStep'
    ];

    optimizationInputs.forEach(inputId => {
        const input = document.getElementById(inputId);
        if (input) {
            params[inputId] = input.value;
        }
    });

    try {
        localStorage.setItem(OPT_PARAMS_STORAGE_KEY, JSON.stringify(params));
        console.log('[saveOptimizationParams] Saved:', params);
    } catch (e) {
        console.warn('[saveOptimizationParams] Failed to save:', e);
    }
}

/**
 * Restore optimization parameters from localStorage
 */
function restoreOptimizationParams() {
    try {
        const saved = localStorage.getItem(OPT_PARAMS_STORAGE_KEY);
        if (!saved) {
            console.log('[restoreOptimizationParams] No saved params found');
            return;
        }

        const params = JSON.parse(saved);
        console.log('[restoreOptimizationParams] Restoring:', params);

        Object.entries(params).forEach(([inputId, value]) => {
            const input = document.getElementById(inputId);
            if (input && value !== undefined && value !== null) {
                input.value = value;
            }
        });
    } catch (e) {
        console.warn('[restoreOptimizationParams] Failed to restore:', e);
    }
}

/**
 * Initialize optimization UI on modal open
 * Generates dynamic fields based on strategy type
 */
export function initOptimizationUI() {
    // Generate dynamic strategy fields based on current strategy
    generateDynamicOptimizationFields();

    // Restore saved optimization parameters
    restoreOptimizationParams();

    // Ensure combinations count is updated
    updateCombinationsCount();

    // Add event listeners to dynamic inputs + TP/SL
    setupOptimizationListeners();

    // Setup reset button
    const btnReset = document.getElementById('btnResetOptParams');
    if (btnReset) {
        btnReset.removeEventListener('click', resetOptimizationToDefaults);
        btnReset.addEventListener('click', resetOptimizationToDefaults);
    }
}

/**
 * Cache for strategy types with parameters_meta
 */
let _strategyTypesCache = null;

/**
 * Load strategy types with parameters metadata
 */
async function loadStrategyTypesWithMeta() {
    if (_strategyTypesCache) return _strategyTypesCache;

    try {
        const response = await fetch(`${API_BASE}/strategies/types`);
        if (response.ok) {
            _strategyTypesCache = await response.json();
        }
    } catch (e) {
        console.warn('[loadStrategyTypesWithMeta] Failed to load:', e);
    }
    return _strategyTypesCache || [];
}

/**
 * Generate dynamic optimization fields based on strategy type
 */
async function generateDynamicOptimizationFields() {
    const container = document.getElementById('dynamicStrategyParams');
    if (!container) return;

    // Get current strategy type from loaded strategy info
    const strategyId = document.getElementById('backtestStrategyId')?.value;
    if (!strategyId) {
        container.innerHTML = '<p class="text-muted">Выберите стратегию</p>';
        return;
    }

    // Load strategy to get type
    let strategyType = 'rsi'; // fallback
    let strategyParams = {};
    try {
        const response = await fetch(`${API_BASE}/strategies/${strategyId}`);
        if (response.ok) {
            const strategy = await response.json();
            strategyType = strategy.strategy_type;
            strategyParams = strategy.parameters || {};
        }
    } catch (e) {
        console.warn('[generateDynamicOptimizationFields] Failed to load strategy:', e);
    }

    // Load strategy types with metadata
    const strategyTypes = await loadStrategyTypesWithMeta();
    const typeInfo = strategyTypes.find(t => t.strategy_type === strategyType);
    const paramsMeta = typeInfo?.parameters_meta || {};

    // Update info text
    const infoText = document.getElementById('optimizationInfoText');
    if (infoText) {
        infoText.textContent = `Grid Search автоматически подберет лучшие параметры ${strategyType.toUpperCase()}`;
    }

    // Generate HTML for each parameter
    let html = '';
    for (const [paramName, meta] of Object.entries(paramsMeta)) {
        const currentValue = strategyParams[paramName] ?? meta.default;
        const defaultStep = meta.step || 1;

        // Calculate reasonable from/to defaults around current value
        const rangeSize = (meta.max - meta.min) * 0.3; // 30% of range
        let defaultFrom = meta.min !== null ? Math.max(meta.min, currentValue - rangeSize) : currentValue - defaultStep * 2;
        let defaultTo = meta.max !== null ? Math.min(meta.max, currentValue + rangeSize) : currentValue + defaultStep * 2;

        // Round default display values: integers for int params, 2 decimals for float
        const isInt = meta.param_type === 'int';
        if (isInt) {
            defaultFrom = Math.round(defaultFrom);
            defaultTo = Math.round(defaultTo);
        } else {
            defaultFrom = Math.round(defaultFrom * 100) / 100;
            defaultTo = Math.round(defaultTo * 100) / 100;
        }

        // Hint shows recommended range from API, but input accepts 0.01-999
        const paramHint = meta.min !== null && meta.max !== null
            ? `(рекомендуется ${meta.min} — ${meta.max})`
            : '';

        html += `
            <div class="form-row optimization-row" data-param="${paramName}">
                <div class="form-group">
                    <label>${paramName.replace(/_/g, ' ').toUpperCase()} 
                        <span class="param-hint">${paramHint}${meta.description ? ', ' + meta.description : ''}</span>
                    </label>
                    <div class="range-inputs">
                        <div class="input-with-label">
                            <span class="input-label">от</span>
                            <input type="number" 
                                   class="opt-param-input" 
                                   data-param="${paramName}" 
                                   data-field="min"
                                   value="${defaultFrom}" 
                                   min="0.01" max="999" step="0.01"
                                   title="Минимальное значение ${paramName}">
                        </div>
                        <span class="range-separator">—</span>
                        <div class="input-with-label">
                            <span class="input-label">до</span>
                            <input type="number" 
                                   class="opt-param-input"
                                   data-param="${paramName}"
                                   data-field="max"
                                   value="${defaultTo}" 
                                   min="0.01" max="999" step="0.01"
                                   title="Максимальное значение ${paramName}">
                        </div>
                        <div class="input-with-label">
                            <span class="input-label">шаг</span>
                            <input type="number" 
                                   class="opt-param-input"
                                   data-param="${paramName}"
                                   data-field="step"
                                   value="${defaultStep}" 
                                   min="0.01" max="999" step="0.01"
                                   title="Шаг оптимизации ${paramName}">
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    // If no parameters found, show fallback
    if (!html) {
        html = '<p class="text-muted">Нет настраиваемых параметров для этой стратегии</p>';
    }

    container.innerHTML = html;

    // Setup listeners for new dynamic inputs
    setupOptimizationListeners();
    updateCombinationsCount();
}

/**
 * Setup event listeners for all optimization inputs (dynamic + static)
 */
function setupOptimizationListeners() {
    // Dynamic strategy params
    document.querySelectorAll('.opt-param-input').forEach(input => {
        input.removeEventListener('change', handleOptInputChange);
        input.removeEventListener('input', handleOptInputChange);
        input.removeEventListener('wheel', handleSmartWheel);
        input.addEventListener('change', handleOptInputChange);
        input.addEventListener('input', handleOptInputChange);
        input.addEventListener('wheel', handleSmartWheel, { passive: false });
    });

    // Static TP/SL inputs
    const staticInputs = [
        'optStopLossMin', 'optStopLossMax', 'optStopLossStep',
        'optTakeProfitMin', 'optTakeProfitMax', 'optTakeProfitStep'
    ];

    staticInputs.forEach(inputId => {
        const input = document.getElementById(inputId);
        if (input) {
            input.removeEventListener('change', handleOptInputChange);
            input.removeEventListener('input', handleOptInputChange);
            input.removeEventListener('wheel', handleSmartWheel);
            input.addEventListener('change', handleOptInputChange);
            input.addEventListener('input', handleOptInputChange);
            input.addEventListener('wheel', handleSmartWheel, { passive: false });
        }
    });
}

/**
 * Smart mouse wheel handler - adjusts step based on decimal precision
 * - 99 → scroll ±1 (100, 98)
 * - 99.1 → scroll ±0.1 (99.2, 99.0)
 * - 99.01 → scroll ±0.01 (99.02, 99.00)
 */
function handleSmartWheel(e) {
    // Only handle when input is focused
    if (document.activeElement !== e.target) return;

    e.preventDefault();

    const input = e.target;
    const currentValue = parseFloat(input.value) || 0;

    // Determine step based on decimal precision of current value
    const valueStr = input.value.toString();
    const decimalIndex = valueStr.indexOf('.');
    let step = 1; // default for integers

    if (decimalIndex !== -1) {
        const decimalPlaces = valueStr.length - decimalIndex - 1;
        step = Math.pow(10, -decimalPlaces); // 0.1 for 1 decimal, 0.01 for 2 decimals
    }

    // Scroll up = increase, scroll down = decrease
    const direction = e.deltaY < 0 ? 1 : -1;
    let newValue = currentValue + (step * direction);

    // Respect min/max limits
    const min = parseFloat(input.min) || 0.01;
    const max = parseFloat(input.max) || 999;
    newValue = Math.max(min, Math.min(max, newValue));

    // Round to avoid floating point errors
    const precision = decimalIndex !== -1 ? valueStr.length - decimalIndex - 1 : 0;
    input.value = newValue.toFixed(precision);

    // Trigger change events
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
}

/**
 * Default optimization parameter values
 */
const DEFAULT_OPT_PARAMS = {
    optPeriodMin: 7,
    optPeriodMax: 21,
    optPeriodStep: 7,
    optOverboughtMin: 65,
    optOverboughtMax: 80,
    optOverboughtStep: 5,
    optOversoldMin: 20,
    optOversoldMax: 35,
    optOversoldStep: 5,
    optStopLossMin: 5,
    optStopLossMax: 15,
    optStopLossStep: 5,
    optTakeProfitMin: 1,
    optTakeProfitMax: 3,
    optTakeProfitStep: 1
};

/**
 * Reset optimization parameters to defaults
 */
function resetOptimizationToDefaults() {
    console.log('[resetOptimizationToDefaults] Resetting to defaults');

    // Apply default values to all inputs
    Object.entries(DEFAULT_OPT_PARAMS).forEach(([inputId, defaultValue]) => {
        const input = document.getElementById(inputId);
        if (input) {
            input.value = defaultValue;
        }
    });

    // Clear saved params from localStorage
    try {
        localStorage.removeItem(OPT_PARAMS_STORAGE_KEY);
    } catch (e) {
        console.warn('[resetOptimizationToDefaults] Failed to clear localStorage:', e);
    }

    // Update combinations count
    updateCombinationsCount();

    // Show confirmation
    if (typeof showToast === 'function') {
        showToast('🔄 Параметры сброшены по умолчанию', 'info');
    }
}

/**
 * Handle optimization input change - update count and save params
 */
function handleOptInputChange() {
    updateCombinationsCount();
    saveOptimizationParams();
}

/**
 * Calculate and display total combinations count
 * Uses the same RSI parameter inputs as runOptimization() for consistency
 */
export function updateCombinationsCount() {
    // RSI Period range
    const periodMin = parseInt(document.getElementById('optPeriodMin')?.value) || 7;
    const periodMax = parseInt(document.getElementById('optPeriodMax')?.value) || 21;
    const periodStep = parseInt(document.getElementById('optPeriodStep')?.value) || 7;
    const periodCount = Math.max(1, Math.floor((periodMax - periodMin) / periodStep) + 1);

    // Overbought range
    const obMin = parseInt(document.getElementById('optOverboughtMin')?.value) || 65;
    const obMax = parseInt(document.getElementById('optOverboughtMax')?.value) || 80;
    const obStep = parseInt(document.getElementById('optOverboughtStep')?.value) || 5;
    const obCount = Math.max(1, Math.floor((obMax - obMin) / obStep) + 1);

    // Oversold range
    const osMin = parseInt(document.getElementById('optOversoldMin')?.value) || 20;
    const osMax = parseInt(document.getElementById('optOversoldMax')?.value) || 35;
    const osStep = parseInt(document.getElementById('optOversoldStep')?.value) || 5;
    const osCount = Math.max(1, Math.floor((osMax - osMin) / osStep) + 1);

    // Stop Loss range
    const slMin = parseFloat(document.getElementById('optStopLossMin')?.value) || 5;
    const slMax = parseFloat(document.getElementById('optStopLossMax')?.value) || 15;
    const slStep = parseFloat(document.getElementById('optStopLossStep')?.value) || 5;
    const slCount = Math.max(1, Math.floor((slMax - slMin) / slStep) + 1);

    // Take Profit range
    const tpMin = parseFloat(document.getElementById('optTakeProfitMin')?.value) || 1;
    const tpMax = parseFloat(document.getElementById('optTakeProfitMax')?.value) || 3;
    const tpStep = parseFloat(document.getElementById('optTakeProfitStep')?.value) || 1;
    const tpCount = Math.max(1, Math.floor((tpMax - tpMin) / tpStep) + 1);

    // Total: period × overbought × oversold × stopLoss × takeProfit
    const total = periodCount * obCount * osCount * slCount * tpCount;

    const el = document.getElementById('totalCombinations');
    if (el) {
        el.textContent = total.toLocaleString();
        // Color coding: green < 100, yellow 100-500, orange 500-1000, red > 1000
        if (total > 1000) {
            el.style.color = '#ff6b6b';
        } else if (total > 500) {
            el.style.color = '#ff9f43';
        } else if (total > 100) {
            el.style.color = '#ffd93d';
        } else {
            el.style.color = '#4ecca3';
        }
    }

    // Estimate time based on expected speed:
    // - Sync/grid-search: ~2-5 combinations/sec (real CPU processing)
    const timeEl = document.getElementById('timeEstimate');
    if (timeEl) {
        // Sync grid-search is slower than vectorbt
        const COMB_PER_SECOND = 3;  // ~3 combinations per second for sync
        const seconds = Math.max(1, Math.ceil(total / COMB_PER_SECOND));

        if (seconds < 60) {
            timeEl.textContent = `⚡ ~${seconds} сек`;
        } else if (seconds < 3600) {
            const minutes = Math.ceil(seconds / 60);
            timeEl.textContent = `⏱️ ~${minutes} мин`;
        } else {
            const hours = (seconds / 3600).toFixed(1);
            timeEl.textContent = `⏱️ ~${hours} ч`;
        }

        // Color based on combination count
        if (total > 10000) {
            timeEl.style.color = '#ff6b6b';
        } else if (total > 1000) {
            timeEl.style.color = '#ff9f43';
        } else if (total > 100) {
            timeEl.style.color = '#ffd93d';
        } else {
            timeEl.style.color = '#4ecca3';
        }
    }

    return { total };
}

/**
 * Generate range array from min, max, step
 */
function generateRange(min, max, step) {
    const arr = [];
    for (let i = min; i <= max; i += step) {
        arr.push(i);
    }
    return arr;
}

/**
 * Save optimization best result as backtest for detailed metrics page
 */
async function saveOptimizationAsBacktest(result, strategy, startDate, endDate) {
    const bestParams = result.best_params || {};
    const bestMetrics = result.best_metrics || {};

    // Get trades and equity_curve from best result (first in top_results array)
    const topResults = result.top_results || result.results || [];
    const bestResult = topResults.length > 0 ? topResults[0] : {};
    const trades = bestResult.trades || [];
    const equityCurve = bestResult.equity_curve || null;    // Prepare backtest data matching backend schema
    const backtestData = {
        name: `Оптимизация ${strategy.symbol || 'BTCUSDT'} RSI(${bestParams.rsi_period || bestParams.period || '-'})`,
        strategy_id: strategy.id,  // Link optimization to strategy for metrics update
        config: {
            symbol: strategy.symbol || 'BTCUSDT',
            interval: strategy.timeframe || '30',
            strategy_type: 'rsi',
            direction: strategy.direction || 'both',
            initial_capital: strategy.initial_capital || 10000,
            leverage: strategy.leverage || 10,
            commission: 0.0006,
            start_date: startDate,
            end_date: endDate,
            strategy_params: {
                period: bestParams.rsi_period || bestParams.period,
                overbought: bestParams.rsi_overbought || bestParams.overbought,
                oversold: bestParams.rsi_oversold || bestParams.oversold
            },
            stop_loss_pct: bestParams.stop_loss_pct || 0,
            take_profit_pct: bestParams.take_profit_pct || 0
        },
        results: {
            total_trades: bestMetrics.total_trades || 0,
            winning_trades: bestMetrics.winning_trades || 0,
            losing_trades: bestMetrics.losing_trades || 0,
            win_rate: bestMetrics.win_rate || 0,
            profit_factor: bestMetrics.profit_factor || 0,
            sharpe_ratio: bestMetrics.sharpe_ratio || 0,
            sortino_ratio: bestMetrics.sortino_ratio || 0,
            max_drawdown: Math.abs(bestMetrics.max_drawdown || 0),
            max_drawdown_pct: Math.abs(bestMetrics.max_drawdown || 0),
            max_drawdown_value: bestMetrics.max_drawdown_value || 0,
            total_return: bestMetrics.total_return || 0,
            total_return_pct: bestMetrics.total_return || 0,
            net_profit: bestMetrics.net_profit || bestMetrics.total_pnl || 0,
            gross_profit: bestMetrics.gross_profit || 0,
            gross_loss: bestMetrics.gross_loss || 0,
            avg_trade_return: bestMetrics.avg_trade_return || 0,
            avg_win: bestMetrics.avg_win || 0,
            avg_loss: bestMetrics.avg_loss || 0,
            largest_win: bestMetrics.largest_win || bestMetrics.best_trade || 0,
            largest_loss: bestMetrics.largest_loss || bestMetrics.worst_trade || 0,
            best_trade: bestMetrics.best_trade || bestMetrics.largest_win || 0,
            worst_trade: bestMetrics.worst_trade || bestMetrics.largest_loss || 0,
            best_trade_pct: bestMetrics.best_trade_pct || 0,
            worst_trade_pct: bestMetrics.worst_trade_pct || 0,
            max_consecutive_wins: bestMetrics.max_consecutive_wins || 0,
            max_consecutive_losses: bestMetrics.max_consecutive_losses || 0,
            recovery_factor: bestMetrics.recovery_factor || 0,
            expectancy: bestMetrics.expectancy || 0,
            calmar_ratio: bestMetrics.calmar_ratio || 0,
            // Long/Short statistics - use bestResult as primary source (contains enriched data)
            long_trades: bestResult.long_trades || bestMetrics.long_trades || 0,
            long_winning_trades: bestResult.long_winning_trades || bestMetrics.long_winning_trades || 0,
            long_losing_trades: bestResult.long_losing_trades || bestMetrics.long_losing_trades || 0,
            long_win_rate: bestResult.long_win_rate || bestMetrics.long_win_rate || 0,
            long_gross_profit: bestResult.long_gross_profit || bestMetrics.long_gross_profit || 0,
            long_gross_loss: bestResult.long_gross_loss || bestMetrics.long_gross_loss || 0,
            long_net_profit: bestResult.long_net_profit || bestMetrics.long_net_profit || 0,
            long_profit_factor: bestResult.long_profit_factor || bestMetrics.long_profit_factor || 0,
            long_avg_win: bestResult.long_avg_win || bestMetrics.long_avg_win || 0,
            long_avg_loss: bestResult.long_avg_loss || bestMetrics.long_avg_loss || 0,
            short_trades: bestResult.short_trades || bestMetrics.short_trades || 0,
            short_winning_trades: bestResult.short_winning_trades || bestMetrics.short_winning_trades || 0,
            short_losing_trades: bestResult.short_losing_trades || bestMetrics.short_losing_trades || 0,
            short_win_rate: bestResult.short_win_rate || bestMetrics.short_win_rate || 0,
            short_gross_profit: bestResult.short_gross_profit || bestMetrics.short_gross_profit || 0,
            short_gross_loss: bestResult.short_gross_loss || bestMetrics.short_gross_loss || 0,
            short_net_profit: bestResult.short_net_profit || bestMetrics.short_net_profit || 0,
            short_profit_factor: bestResult.short_profit_factor || bestMetrics.short_profit_factor || 0,
            short_avg_win: bestResult.short_avg_win || bestMetrics.short_avg_win || 0,
            short_avg_loss: bestResult.short_avg_loss || bestMetrics.short_avg_loss || 0,

            // Average bars in trade
            avg_bars_in_trade: bestMetrics.avg_bars_in_trade || 0,
            avg_bars_in_winning: bestMetrics.avg_bars_in_winning || 0,
            avg_bars_in_losing: bestMetrics.avg_bars_in_losing || 0,
            avg_bars_in_long: bestMetrics.avg_bars_in_long || 0,
            avg_bars_in_short: bestMetrics.avg_bars_in_short || 0,
            avg_bars_in_winning_long: bestMetrics.avg_bars_in_winning_long || 0,
            avg_bars_in_losing_long: bestMetrics.avg_bars_in_losing_long || 0,
            avg_bars_in_winning_short: bestMetrics.avg_bars_in_winning_short || 0,
            avg_bars_in_losing_short: bestMetrics.avg_bars_in_losing_short || 0,
            recovery_long: bestMetrics.recovery_long || 0,
            recovery_short: bestMetrics.recovery_short || 0,
            total_commission: bestMetrics.total_commission || 0,
            buy_hold_return: bestMetrics.buy_hold_return || 0,
            buy_hold_return_pct: bestMetrics.buy_hold_return_pct || 0,
            strategy_outperformance: bestMetrics.strategy_outperformance || 0,
            cagr: bestMetrics.cagr || 0,
            cagr_long: bestMetrics.cagr_long || 0,
            cagr_short: bestMetrics.cagr_short || 0,
            // Include trades and equity curve for charts
            trades: trades,
            equity_curve: equityCurve
        },
        status: 'completed',
        metadata: {
            source: 'optimization',
            tested_combinations: result.tested_combinations,
            execution_time: result.execution_time_seconds,
            optimize_metric: result.optimize_metric || 'sharpe_ratio'
        }
    };

    // Debug: log what we're sending
    console.log('[saveOptimizationAsBacktest] topResults:', topResults.length);
    console.log('[saveOptimizationAsBacktest] trades count:', trades.length);
    console.log('[saveOptimizationAsBacktest] equityCurve:', equityCurve);
    console.log('[saveOptimizationAsBacktest] backtestData.results.trades:', backtestData.results.trades?.length);
    console.log('[saveOptimizationAsBacktest] backtestData.results.equity_curve:', backtestData.results.equity_curve);

    const response = await fetch(`${API_BASE}/backtests/save-optimization`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(backtestData)
    });

    if (!response.ok) {
        throw new Error('Failed to save backtest');
    }

    const saved = await response.json();
    return saved.id;
}

/**
 * Run optimization using regular fetch (for smaller parameter spaces < 1M)
 */
async function runOptimizationFetch(payload) {
    const endpoint = `${API_BASE}/optimizations/sync/grid-search`;
    console.log('[runOptimizationFetch] Sending request to:', endpoint);

    // Create AbortController for this optimization
    _optimizationAbortController = new AbortController();

    // Set 15-minute timeout
    const timeoutMs = 900000;
    const timeoutId = setTimeout(() => {
        console.warn(`[runOptimizationFetch] Request timeout after ${timeoutMs/1000}s`);
        _optimizationAbortController?.abort();
    }, timeoutMs);

    try {
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Connection': 'keep-alive'
            },
            body: JSON.stringify(payload),
            signal: _optimizationAbortController.signal
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(errorText || 'Optimization failed');
        }

        return await response.json();
    } finally {
        clearTimeout(timeoutId);
        _optimizationAbortController = null;
    }
}


/**
 * Run optimization using SSE streaming (for large parameter spaces > 1M)
 * Keeps connection alive with heartbeats to prevent browser timeout
 */
async function _runOptimizationSSE(payload, totalCombinations, _estimatedSeconds) {
    return new Promise((resolve, reject) => {
        // Build query string from payload
        const params = new URLSearchParams({
            symbol: payload.symbol,
            interval: payload.interval,
            start_date: payload.start_date,
            end_date: payload.end_date,
            direction: payload.direction || 'both',
            leverage: payload.leverage || 10,
            initial_capital: payload.initial_capital || 10000,
            commission: payload.commission || 0.0006,
            position_size: payload.fixed_amount || 1.0,
            rsi_period_range: payload.rsi_period_range.join(','),
            rsi_overbought_range: payload.rsi_overbought_range.join(','),
            rsi_oversold_range: payload.rsi_oversold_range.join(','),
            stop_loss_range: payload.stop_loss_range.join(','),
            take_profit_range: payload.take_profit_range.join(','),
            optimize_metric: payload.optimize_metric || 'sharpe_ratio',
            weight_return: payload.weight_return || 0.4,
            weight_drawdown: payload.weight_drawdown || 0.3,
            weight_sharpe: payload.weight_sharpe || 0.2,
            weight_win_rate: payload.weight_win_rate || 0.1
        });

        // Add optional filters
        if (payload.min_trades) params.append('min_trades', payload.min_trades);
        if (payload.max_drawdown_limit) params.append('max_drawdown_limit', payload.max_drawdown_limit);
        if (payload.min_profit_factor) params.append('min_profit_factor', payload.min_profit_factor);
        if (payload.min_win_rate) params.append('min_win_rate', payload.min_win_rate);

        const url = `${API_BASE}/optimizations/vectorbt/grid-search-stream?${params}`;
        console.log('[runOptimizationSSE] Connecting to SSE:', url);

        const eventSource = new EventSource(url);

        eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                console.log('[runOptimizationSSE] Event:', data.event);

                if (data.event === 'heartbeat') {
                    // Use progress from server if available
                    const percent = data.percent || 0;
                    const eta = data.eta_seconds ? `ETA: ${Math.round(data.eta_seconds)}s` : '';
                    const elapsed = Math.round(data.elapsed);
                    updateBacktestProgress(
                        `🚀 Оптимизация ${totalCombinations.toLocaleString()} комбинаций... (${percent}%)`,
                        percent,
                        `${elapsed} сек ${eta}`
                    );
                } else if (data.event === 'complete') {
                    eventSource.close();
                    resolve(data);
                } else if (data.event === 'error') {
                    eventSource.close();
                    reject(new Error(data.message));
                }
            } catch (e) {
                console.error('[runOptimizationSSE] Parse error:', e, event.data);
            }
        };

        eventSource.onerror = (error) => {
            console.error('[runOptimizationSSE] EventSource error:', error);
            eventSource.close();
            reject(new Error('SSE connection error'));
        };

        // Store for cancellation
        window._optimizationEventSource = eventSource;
    });
}

/**
 * Run Grid Search optimization
 */
export async function runOptimization(onComplete = null) {
    console.log('[runOptimization] Starting optimization...');
    const strategyId = document.getElementById('backtestStrategyId').value;
    console.log('[runOptimization] strategyId:', strategyId);
    const startDateStr = document.getElementById('backtestStartDate').value;
    const endDateStr = document.getElementById('backtestEndDate').value;
    console.log('[runOptimization] dates:', startDateStr, '-', endDateStr);

    // Date validation
    if (!startDateStr || !endDateStr) {
        showToast('Выберите даты начала и окончания', 'error');
        return;
    }

    // Get optimization parameters
    const periodRange = generateRange(
        parseInt(document.getElementById('optPeriodMin')?.value) || 7,
        parseInt(document.getElementById('optPeriodMax')?.value) || 21,
        parseInt(document.getElementById('optPeriodStep')?.value) || 7
    );

    const overboughtRange = generateRange(
        parseInt(document.getElementById('optOverboughtMin')?.value) || 65,
        parseInt(document.getElementById('optOverboughtMax')?.value) || 80,
        parseInt(document.getElementById('optOverboughtStep')?.value) || 5
    );

    const oversoldRange = generateRange(
        parseInt(document.getElementById('optOversoldMin')?.value) || 20,
        parseInt(document.getElementById('optOversoldMax')?.value) || 35,
        parseInt(document.getElementById('optOversoldStep')?.value) || 5
    );

    // Get TP/SL ranges
    const stopLossRange = generateRange(
        parseFloat(document.getElementById('optStopLossMin')?.value) || 5,
        parseFloat(document.getElementById('optStopLossMax')?.value) || 15,
        parseFloat(document.getElementById('optStopLossStep')?.value) || 5
    );

    const takeProfitRange = generateRange(
        parseFloat(document.getElementById('optTakeProfitMin')?.value) || 1,
        parseFloat(document.getElementById('optTakeProfitMax')?.value) || 3,
        parseFloat(document.getElementById('optTakeProfitStep')?.value) || 1
    );

    // Get selected optimization criteria from checkboxes
    const selectedCriteria = [];
    document.querySelectorAll('input[name="selectionCriteria"]:checked').forEach(cb => {
        selectedCriteria.push(cb.value);
    });

    // Default to net_profit if nothing selected
    if (selectedCriteria.length === 0) {
        selectedCriteria.push('net_profit');
    }

    // For backward compatibility, use first criterion as primary optimize metric
    const optimizeMetric = selectedCriteria[0];

    console.log('[runOptimization] Selected criteria:', selectedCriteria);

    // Load strategy to get symbol/interval
    let strategy;
    try {
        const resp = await fetch(`${API_BASE}/strategies/${strategyId}`);
        strategy = await resp.json();
        console.log('[runOptimization] Strategy loaded:', {
            id: strategy.id,
            symbol: strategy.symbol,
            timeframe: strategy.timeframe,
            parameters: strategy.parameters,
            direction: strategy.parameters?._direction,
            leverage: strategy.parameters?._leverage
        });
    } catch (err) {
        showToast('Ошибка загрузки стратегии', 'error');
        return;
    }

    // Convert timeframe format: "30m" -> "30", "1h" -> "60", etc.
    // Handle empty/null timeframe with proper fallback
    let interval = (strategy.timeframe && strategy.timeframe.trim()) || '60';
    if (interval.endsWith('m')) {
        interval = interval.replace('m', '');
    } else if (interval.endsWith('h')) {
        interval = String(parseInt(interval) * 60);
    } else if (interval.endsWith('d') || interval.endsWith('D')) {
        interval = 'D';
    }


    // Extract parameters from strategy (may be nested in parameters object)
    const params = strategy.parameters || strategy.config || {};

    // Direction: prefer params._direction, fallback to 'both'
    const direction = params._direction || params.direction || strategy.direction || 'both';

    // Leverage: prefer params._leverage, fallback to 10
    const leverage = params._leverage || params.leverage || strategy.leverage || 10;

    // Position size: use initial_capital * position_size or fixed amount
    const positionSize = params._order_amount || strategy.position_size * strategy.initial_capital || 100.0;

    const payload = {
        symbol: strategy.symbol || 'BTCUSDT',
        interval: interval,
        start_date: startDateStr,
        end_date: endDateStr,
        strategy_type: 'rsi',
        direction: direction,
        use_fixed_amount: true,
        fixed_amount: positionSize,
        leverage: leverage,
        initial_capital: strategy.initial_capital || 10000.0,
        commission: 0.0006,
        // RSI parameter ranges
        rsi_period_range: periodRange,
        rsi_overbought_range: overboughtRange,
        rsi_oversold_range: oversoldRange,
        // TP/SL parameter ranges
        stop_loss_range: stopLossRange,
        take_profit_range: takeProfitRange,
        // Selection criteria (new system)
        optimize_metric: optimizeMetric,
        selection_criteria: selectedCriteria,
        // Engine type - use only from strategy settings (selector removed from modal)
        engine_type: params._engine_type || 'auto',
        // Market type - SPOT for TradingView parity, LINEAR for futures
        market_type: params._market_type || 'linear',
        // Bar Magnifier settings - ALWAYS true by default for accurate intrabar simulation
        use_bar_magnifier: params._bar_magnifier ?? (document.getElementById('useBarMagnifier')?.checked ?? true),
        intrabar_ohlc_path: document.getElementById('intrabarOhlcPath')?.value || 'O-HL-heuristic',
        intrabar_subticks: parseInt(document.getElementById('intrabarSubticks')?.value || 0),
        // TradingView-like simulation settings from strategy
        fill_mode: params._fill_mode || 'next_bar_open',
        max_drawdown_trading: params._max_drawdown || 0,  // Stop trading when hit this drawdown %
        // Search method (Grid/Random)
        search_method: document.getElementById('searchMethod')?.value || 'grid',
        max_iterations: parseInt(document.getElementById('maxIterations')?.value || 0),
        // Market Regime Filter (P1) — фильтрация по режиму рынка (требует FallbackV4)
        market_regime_enabled: document.getElementById('marketRegimeEnabled')?.checked ?? false,
        market_regime_filter: document.getElementById('marketRegimeFilter')?.value || 'not_volatile',
        market_regime_lookback: parseInt(document.getElementById('marketRegimeLookback')?.value || 50)
    };

    console.log('[runOptimization] Final payload:', {
        symbol: payload.symbol,
        interval: payload.interval,
        direction: payload.direction,
        leverage: payload.leverage,
        initial_capital: payload.initial_capital,
        engine_type: payload.engine_type,  // For debugging engine selection
        market_type: payload.market_type   // For debugging market type selection
    });

    // Get UI elements
    const btnRun = document.getElementById('btnRunOptimization');
    const btnText = document.getElementById('btnRunOptimizationText');
    const btnSpinner = document.getElementById('btnRunOptimizationSpinner');
    const resultsSection = document.getElementById('backtestResults');

    try {
        // Show progress UI
        if (btnRun) btnRun.disabled = true;
        if (btnText) btnText.textContent = 'Оптимизация...';
        if (btnSpinner) btnSpinner.classList.remove('hidden');
        if (resultsSection) resultsSection.classList.add('hidden');

        const totalCombinations = periodRange.length * overboughtRange.length * oversoldRange.length * stopLossRange.length * takeProfitRange.length;

        // Speed estimate for sync grid-search (CPU-bound)
        const SPEED_ESTIMATE = 3;  // ~3 combinations per second for sync processing
        const estimatedSeconds = Math.max(1, Math.ceil(totalCombinations / SPEED_ESTIMATE));
        const speedEstimate = estimatedSeconds < 60
            ? `~${estimatedSeconds} сек`
            : estimatedSeconds < 3600
                ? `~${Math.ceil(estimatedSeconds / 60)} мин`
                : `~${(estimatedSeconds / 3600).toFixed(1)} ч`;

        // Initialize multi-thread progress with animation
        // Note: numWorkers is for visual progress bars, actual execution uses ProcessPoolExecutor on backend
        const numWorkers = Math.min(navigator.hardwareConcurrency || 4, 4);
        initMultiThreadProgress(numWorkers, totalCombinations, estimatedSeconds);

        updateBacktestProgress(
            `🚀 Оптимизация ${totalCombinations.toLocaleString()} комбинаций...`,
            -1,
            `CPU (${numWorkers} процессов): ${speedEstimate}`
        );

        console.log('[runOptimization] Starting optimization...', totalCombinations, 'combinations');

        // Always use sync/grid-search which auto-loads data from Bybit API
        // SSE streaming (vectorbt) requires pre-loaded data in DB
        console.log('[runOptimization] Using sync grid-search');
        const result = await runOptimizationFetch(payload);

        console.log('[runOptimization] Result:', result);

        // Complete multi-thread progress with actual speed and time from server
        const actualSpeed = Math.round(result.tested_combinations / result.execution_time_seconds);
        completeMultiThreadProgress(actualSpeed, result.execution_time_seconds);

        // Save best result as backtest for detailed metrics page
        let savedBacktestId = null;
        try {
            savedBacktestId = await saveOptimizationAsBacktest(result, strategy, startDateStr, endDateStr);
            console.log('[runOptimization] Saved backtest ID:', savedBacktestId);
        } catch (saveErr) {
            console.warn('[runOptimization] Could not save backtest:', saveErr);
        }

        // Auto-apply best parameters to strategy
        const bestParams = result.best_params || {};
        try {
            await applyBestParamsQuiet(strategyId, bestParams, strategy);
            console.log('[runOptimization] Best params applied to strategy');
        } catch (applyErr) {
            console.warn('[runOptimization] Could not apply params:', applyErr);
        }

        showToast('✅ Оптимизация завершена! Переход к метрикам...', 'success');

        // Close modal and redirect to metrics page
        closeBacktestModal();

        if (savedBacktestId) {
            // Redirect to metrics page with the saved backtest
            console.log('[runOptimization] Redirecting to:', `/frontend/backtest-results.html?id=${savedBacktestId}`);
            setTimeout(() => {
                // Use replace to avoid back button issues, and add timestamp to force cache bypass
                window.location.replace(`/frontend/backtest-results.html?id=${savedBacktestId}&t=${Date.now()}`);
            }, 500);
        } else {
            // Fallback: just reload strategies
            if (typeof window.loadStrategies === 'function') {
                window.loadStrategies();
            }
        }

        if (onComplete) onComplete();
        return; // Exit early, no need to display results panel

    } catch (error) {
        // Check if this was a user-initiated cancellation
        if (error.name === 'AbortError') {
            console.log('[runOptimization] Optimization was cancelled by user');
            resetBacktestProgress();
            // Don't show error toast, cancelOptimization already shows "cancelled" toast
        } else {
            console.error('Optimization error:', error);
            showToast(`Ошибка оптимизации: ${error.message}`, 'error');
            resetBacktestProgress();  // Reset only on error
        }
    } finally {
        // Clear abort controller
        _optimizationAbortController = null;
        // Reset UI buttons only
        if (btnRun) btnRun.disabled = false;
        if (btnText) btnText.textContent = '🔍 Оптимизировать';
        if (btnSpinner) btnSpinner.classList.add('hidden');
        // Don't reset progress here - keep results visible
    }
}

/**
 * Display optimization results with apply button
 */
// eslint-disable-next-line no-unused-vars
function displayOptimizationResults(result, strategy, strategyId, savedBacktestId = null) {
    const resultsSection = document.getElementById('backtestResults');
    if (!resultsSection) return;

    const bestParams = result.best_params || {};
    const bestMetrics = result.best_metrics || {};
    const smartRecs = result.smart_recommendations || {};

    // Build smart recommendations HTML
    let smartRecsHtml = '';
    if (smartRecs.recommendation_text || smartRecs.best_balanced || smartRecs.best_conservative || smartRecs.best_aggressive) {
        smartRecsHtml = `
            <div class="smart-recommendations">
                <h4>🤖 Умные рекомендации</h4>
                ${buildRecommendationCard('🎯', 'Сбалансированный', 'Лучшее соотношение прибыли к риску', smartRecs.best_balanced, strategyId)}
                ${buildRecommendationCard('🛡️', 'Консервативный', 'Минимальная просадка', smartRecs.best_conservative, strategyId)}
                ${buildRecommendationCard('🚀', 'Агрессивный', 'Максимальная прибыль', smartRecs.best_aggressive, strategyId)}
            </div>
        `;
    }

    resultsSection.innerHTML = `
        <h3 class="results-title">🏆 Лучшие параметры найдены!</h3>
        <div class="best-params">
            <div class="param">
                <span class="param-label">RSI Period</span>
                <span class="param-value">${bestParams.rsi_period || bestParams.period || '-'}</span>
            </div>
            <div class="param">
                <span class="param-label">Overbought</span>
                <span class="param-value">${bestParams.rsi_overbought || bestParams.overbought || '-'}</span>
            </div>
            <div class="param">
                <span class="param-label">Oversold</span>
                <span class="param-value">${bestParams.rsi_oversold || bestParams.oversold || '-'}</span>
            </div>
            <div class="param">
                <span class="param-label">Stop Loss</span>
                <span class="param-value">${bestParams.stop_loss_pct || '-'}%</span>
            </div>
            <div class="param">
                <span class="param-label">Take Profit</span>
                <span class="param-value">${bestParams.take_profit_pct || '-'}%</span>
            </div>
        </div>
        <div class="results-grid">
            <div class="result-card">
                <span class="result-label">Доходность</span>
                <span class="result-value ${bestMetrics.total_return >= 0 ? 'positive' : 'negative'}">${(bestMetrics.total_return || 0).toFixed(2)}%</span>
            </div>
            <div class="result-card">
                <span class="result-label">Sharpe Ratio</span>
                <span class="result-value ${bestMetrics.sharpe_ratio >= 1 ? 'positive' : ''}">${(bestMetrics.sharpe_ratio || 0).toFixed(2)}</span>
            </div>
            <div class="result-card">
                <span class="result-label">Win Rate</span>
                <span class="result-value ${bestMetrics.win_rate >= 50 ? 'positive' : ''}">${(bestMetrics.win_rate || 0).toFixed(1)}%</span>
            </div>
            <div class="result-card">
                <span class="result-label">Max DD</span>
                <span class="result-value negative">-${Math.abs(bestMetrics.max_drawdown || 0).toFixed(2)}%</span>
            </div>
            <div class="result-card">
                <span class="result-label">Сделок</span>
                <span class="result-value">${bestMetrics.total_trades || 0}</span>
            </div>
            <div class="result-card">
                <span class="result-label">Profit Factor</span>
                <span class="result-value ${bestMetrics.profit_factor >= 1.5 ? 'positive' : ''}">${(bestMetrics.profit_factor || 0).toFixed(2)}</span>
            </div>
        </div>
        ${smartRecsHtml}
        <div class="results-footer">
            <span>Протестировано: ${result.tested_combinations.toLocaleString()}/${result.total_combinations.toLocaleString()} комбинаций за ${result.execution_time_seconds}с</span>
            <span class="performance-badge">
                ⚡ ${Math.round(result.tested_combinations / result.execution_time_seconds).toLocaleString()} комб/сек
                ${result.num_workers ? `• ${result.num_workers} потоков` : '• Numba JIT'}
            </span>
        </div>
        <div class="results-actions">
            <button class="apply-params-btn" onclick="applyBestParams('${strategyId}', ${JSON.stringify(bestParams).replace(/"/g, '&quot;')})">
                ✅ Применить лучшие параметры
            </button>
            ${savedBacktestId ? `
                <button class="view-metrics-btn" onclick="window.location.href='/frontend/backtest-results.html?id=${savedBacktestId}'">
                    📊 Детальные метрики
                </button>
            ` : ''}
        </div>
    `;

    resultsSection.classList.remove('hidden');
}

/**
 * Build a recommendation card HTML
 */
function buildRecommendationCard(icon, title, subtitle, rec, strategyId) {
    if (!rec || !rec.params) return '';

    const params = rec.params;
    const paramsJson = JSON.stringify(params).replace(/"/g, '&quot;');

    return `
        <div class="recommendation-card" onclick="applyBestParams('${strategyId}', ${paramsJson})">
            <div class="rec-header">
                <span class="rec-icon">${icon}</span>
                <span class="rec-title">${title}</span>
            </div>
            <div class="rec-subtitle">${subtitle}</div>
            <div class="rec-params">
                RSI(${params.rsi_period || '-'}, ${params.rsi_overbought || '-'}, ${params.rsi_oversold || '-'})
                <span class="rec-tpsl">SL: ${params.stop_loss_pct || '-'}% | TP: ${params.take_profit_pct || '-'}%</span>
            </div>
            <div class="rec-metrics">
                <span class="${(rec.total_return || 0) >= 0 ? 'positive' : 'negative'}">
                    ${(rec.total_return || 0).toFixed(1)}%
                </span>
                <span class="separator">|</span>
                <span class="negative">DD: ${Math.abs(rec.max_drawdown || 0).toFixed(1)}%</span>
            </div>
        </div>
    `;
}

/**
 * Apply best parameters to strategy (quiet version - no redirect/reload)
 * Used after optimization to auto-apply before redirecting to metrics
 */
async function applyBestParamsQuiet(strategyId, bestParams, strategy) {
    // Update strategy params
    const updatedParams = {
        ...strategy.strategy_params,
        period: bestParams.rsi_period || bestParams.period,
        overbought: bestParams.rsi_overbought || bestParams.overbought,
        oversold: bestParams.rsi_oversold || bestParams.oversold
    };

    // Update stop loss and take profit
    const stopLossPct = bestParams.stop_loss_pct || strategy.stop_loss_pct;
    const takeProfitPct = bestParams.take_profit_pct || strategy.take_profit_pct;

    // Save strategy
    const updateResp = await fetch(`${API_BASE}/strategies/${strategyId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            ...strategy,
            stop_loss_pct: stopLossPct,
            take_profit_pct: takeProfitPct,
            strategy_params: updatedParams
        })
    });

    if (!updateResp.ok) {
        throw new Error('Failed to update strategy');
    }

    return true;
}

/**
 * Apply best parameters to strategy
 */
export async function applyBestParams(strategyId, bestParams) {
    try {
        // Fetch current strategy
        const resp = await fetch(`${API_BASE}/strategies/${strategyId}`);
        const strategy = await resp.json();

        // Update strategy params
        const updatedParams = {
            ...strategy.strategy_params,
            period: bestParams.rsi_period || bestParams.period,
            overbought: bestParams.rsi_overbought || bestParams.overbought,
            oversold: bestParams.rsi_oversold || bestParams.oversold
        };

        // Update stop loss and take profit
        const stopLossPct = bestParams.stop_loss_pct || strategy.stop_loss_pct;
        const takeProfitPct = bestParams.take_profit_pct || strategy.take_profit_pct;

        // Save strategy
        const updateResp = await fetch(`${API_BASE}/strategies/${strategyId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                ...strategy,
                stop_loss_pct: stopLossPct,
                take_profit_pct: takeProfitPct,
                strategy_params: updatedParams
            })
        });

        if (!updateResp.ok) {
            throw new Error('Failed to update strategy');
        }

        showToast('✅ Параметры стратегии обновлены!', 'success');

        // Close modal and reload strategies
        closeBacktestModal();
        // Use global loadStrategies if available, otherwise reload page
        if (typeof window.loadStrategies === 'function') {
            window.loadStrategies();
        } else {
            window.location.reload();
        }

    } catch (error) {
        console.error('Apply params error:', error);
        showToast(`Ошибка: ${error.message}`, 'error');
    }
}

// Expose applyBestParams globally
if (typeof window !== 'undefined') {
    window.applyBestParams = applyBestParams;
}
