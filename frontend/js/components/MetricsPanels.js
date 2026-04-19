/**

 * 📊 MetricsPanels — Компонент метрик бэктеста

 *

 * Инкапсулирует логику заполнения четырёх вкладок результатов:

 *   Tab 1 — Summary Cards      (updateTVSummaryCards)

 *   Tab 2 — Dynamics           (updateTVDynamicsTab)

 *   Tab 3 — Trade Analysis     (updateTVTradeAnalysisTab)

 *   Tab 4 — Risk/Return        (updateTVRiskReturnTab)

 *

 * Extracted from backtest_results.js as part of P0-2 Phase 3 refactoring.

 * All functions are pure DOM-writers — no module state, no side-effects beyond

 * setting element innerHTML/textContent/className.

 *

 * @module MetricsPanels

 * @version 1.0.0

 * @date 2026-02-26

 * @migration P0-2 Phase 3: Extract MetricsPanels

 */


// ─── Formatters ───────────────────────────────────────────────────────────────


/**

 * Format a currency value (USD) with optional percentage, TradingView style.

 *

 * @param {number}         value    - USD value

 * @param {number|null}    pct      - Optional percentage companion

 * @param {boolean}        showSign - Prefix '+' for positive values

 * @returns {string} HTML string with optional dual-value wrapper

 */

export function formatTVCurrency(value, pct, showSign = true) {

    if (value === null || value === undefined) return '--';

    const formatted = value.toLocaleString('ru-RU', {

        minimumFractionDigits: 2,

        maximumFractionDigits: 2

    });

    const cleanFormatted = formatted === '-0,00' ? '0,00' : formatted;

    const sign = showSign && value > 0 ? '+' : '';

    const dollarVal = `${sign}${cleanFormatted} USD`;

    if (pct !== undefined && pct !== null) {

        const pctFormatted = pct.toFixed(2);

        const cleanPct = pctFormatted === '-0.00' ? '0.00' : pctFormatted;

        const pctSign = showSign && pct > 0 ? '+' : '';

        return `<div class="tv-dual-value"><span class="tv-main-value">${dollarVal}</span><span class="tv-pct-value">${pctSign}${cleanPct}%</span></div>`;

    }

    return dollarVal;

}


/**

 * Format a percentage value, TradingView style.

 *

 * @param {number}  value    - Percentage value

 * @param {boolean} showSign - Prefix '+' for positive values

 * @returns {string}

 */

export function formatTVPercent(value, showSign = true) {

    if (value === null || value === undefined) return '--';

    const formatted = value.toFixed(2);

    const cleanFormatted = formatted === '-0.00' ? '0.00' : formatted;

    const sign = showSign && value > 0 ? '+' : '';

    return `${sign}${cleanFormatted}%`;

}


// ─── Tab 1 — Summary Cards ────────────────────────────────────────────────────


/**

 * Update the TradingView-style summary cards (Tab 1).

 *

 * @param {object} metrics - Metrics object from backtest API response

 */

export function updateTVSummaryCards(metrics) {

    if (!metrics) return;


    // Net Profit (TV-style: closed net profit + unrealized open position PnL)

    const netProfit = document.getElementById('tvNetProfit');

    const netProfitPct = document.getElementById('tvNetProfitPct');

    if (netProfit) {

        const closedVal = metrics.net_profit || 0;

        const openVal = metrics.open_pnl || 0;

        const val = closedVal + openVal;

        const valFormatted = val.toLocaleString('ru-RU', {

            minimumFractionDigits: 2,

            maximumFractionDigits: 2

        });

        const cleanVal = valFormatted === '-0,00' ? '0,00' : valFormatted;

        netProfit.textContent = `${val > 0 ? '+' : ''}${cleanVal} USD`;

        netProfit.className = `tv-summary-card-value ${val >= 0 ? 'tv-value-positive' : 'tv-value-negative'}`;

    }

    if (netProfitPct) {

        const closedPct = metrics.net_profit_pct ?? 0;

        const openPct = metrics.open_pnl_pct ?? 0;

        const pct = closedPct + openPct;

        const pctFormatted = pct.toFixed(2);

        const cleanPct = pctFormatted === '-0.00' ? '0.00' : pctFormatted;

        netProfitPct.textContent = `${pct > 0 ? '+' : ''}${cleanPct}%`;

    }


    // Max Drawdown (TV-style: intrabar drawdown, same as TradingView's "Max Drawdown" display)

    const maxDD = document.getElementById('tvMaxDrawdown');

    const maxDDPct = document.getElementById('tvMaxDrawdownPct');

    if (maxDD) {

        // Use intrabar value when available (matches TradingView), fall back to close-to-close

        const val = metrics.max_drawdown_intrabar_value || metrics.max_drawdown_value || 0;

        maxDD.textContent = `${Math.abs(val).toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} USD`;

    }

    if (maxDDPct) {

        // Use intrabar % when available (matches TradingView), fall back to close-to-close

        const pct = metrics.max_drawdown_intrabar || metrics.max_drawdown || 0;

        maxDDPct.textContent = `${Math.abs(pct).toFixed(2)}%`;

    }


    // Total Trades

    const totalTrades = document.getElementById('tvTotalTrades');

    if (totalTrades) {

        totalTrades.textContent = metrics.total_trades || 0;

    }


    // Open Trades count

    const openTradesEl = document.getElementById('tvOpenTrades');

    if (openTradesEl) openTradesEl.textContent = `открытых: ${metrics.open_trades || 0}`;


    // Winning Trades + Win Rate

    const winningTrades = document.getElementById('tvWinningTrades');

    const winRate = document.getElementById('tvWinRate');

    if (winningTrades) winningTrades.textContent = metrics.winning_trades || 0;

    if (winRate) winRate.textContent = `${(metrics.win_rate || 0).toFixed(2)}%`;


    // Profit Factor

    const profitFactor = document.getElementById('tvProfitFactor');

    if (profitFactor) profitFactor.textContent = (metrics.profit_factor || 0).toFixed(3);

}


// ─── Tab 2 — Dynamics ─────────────────────────────────────────────────────────


/**

 * Update the Dynamics tab (Tab 2).

 *

 * @param {object}        metrics     - Metrics from backtest API

 * @param {object|null}   config      - Backtest config (used for initial_capital)

 * @param {object[]|null} trades      - Trades array (fallback equity curve)

 * @param {object|null}   equityCurve - Equity curve data

 */

export function updateTVDynamicsTab(metrics, config, trades, equityCurve) {

    if (!metrics) return;


    const setValue = (id, value, format = 'currency') => {

        const el = document.getElementById(id);

        if (!el) return;

        if (value === null || value === undefined) { el.textContent = '--'; return; }

        if (format === 'currency') {

            el.innerHTML = formatTVCurrency(value, null, true);

            el.className = value > 0 ? 'tv-value-positive' : value < 0 ? 'tv-value-negative' : 'tv-value-neutral';

        } else if (format === 'currency-pct') {

            el.innerHTML = formatTVCurrency(value.val, value.pct, true);

            el.className = value.val > 0 ? 'tv-value-positive' : value.val < 0 ? 'tv-value-negative' : 'tv-value-neutral';

        } else if (format === 'percent') {

            el.textContent = formatTVPercent(value, true);

            el.className = value > 0 ? 'tv-value-positive' : value < 0 ? 'tv-value-negative' : 'tv-value-neutral';

        } else if (format === 'number') {

            el.textContent = value.toLocaleString('ru-RU');

            el.className = 'tv-value-neutral';

        } else if (format === 'days') {

            el.textContent = `${value} дня`;

            el.className = 'tv-value-neutral';

        } else {

            el.textContent = value;

        }

    };


    const initialCapital = config?.initial_capital || 10000;


    console.log('[Dynamics Tab] Using backend metrics directly');

    console.log(

        `[Dynamics Tab] Long: ${metrics.long_trades || 0} trades, Short: ${metrics.short_trades || 0} trades`

    );

    console.log(

        `[Dynamics Tab] GP=${(metrics.gross_profit || 0).toFixed(2)}, GL=${(metrics.gross_loss || 0).toFixed(2)}, Comm=${(metrics.total_commission || 0).toFixed(2)}`

    );


    setValue('dyn-initial-capital', config?.initial_capital || 10000, 'number');

    setValue('dyn-unrealized', { val: metrics.open_pnl || 0, pct: metrics.open_pnl_pct || 0 }, 'currency-pct');


    // Net Profit

    setValue('dyn-net-profit', { val: metrics.net_profit || 0, pct: metrics.net_profit_pct || 0 }, 'currency-pct');

    setValue('dyn-net-profit-long', { val: metrics.long_net_profit || 0, pct: metrics.long_pnl_pct || 0 }, 'currency-pct');

    setValue('dyn-net-profit-short', { val: metrics.short_net_profit || 0, pct: metrics.short_pnl_pct || 0 }, 'currency-pct');


    // Gross Profit

    setValue('dyn-gross-profit', { val: metrics.gross_profit || 0, pct: metrics.gross_profit_pct || 0 }, 'currency-pct');

    setValue('dyn-gross-profit-long', { val: metrics.long_gross_profit || 0, pct: metrics.long_gross_profit_pct || 0 }, 'currency-pct');

    setValue('dyn-gross-profit-short', { val: metrics.short_gross_profit || 0, pct: metrics.short_gross_profit_pct || 0 }, 'currency-pct');


    // Gross Loss

    setValue('dyn-gross-loss', { val: -(metrics.gross_loss || 0), pct: -(metrics.gross_loss_pct || 0) }, 'currency-pct');

    setValue('dyn-gross-loss-long', { val: -(metrics.long_gross_loss || 0), pct: -(metrics.long_gross_loss_pct || 0) }, 'currency-pct');

    setValue('dyn-gross-loss-short', { val: -(metrics.short_gross_loss || 0), pct: -(metrics.short_gross_loss_pct || 0) }, 'currency-pct');


    // Profit Factor

    const profitFactor = metrics.profit_factor || 0;

    setValue('dyn-profit-factor', profitFactor, 'number');

    setValue('dyn-profit-factor-long', metrics.long_profit_factor === Infinity ? '∞' : metrics.long_profit_factor || 0, 'number');

    setValue('dyn-profit-factor-short', metrics.short_profit_factor === Infinity ? '∞' : metrics.short_profit_factor || 0, 'number');


    // Commission

    setValue('dyn-commission', metrics.total_commission || 0, 'currency');

    setValue('dyn-commission-long', metrics.long_commission || 0, 'currency');

    setValue('dyn-commission-short', metrics.short_commission || 0, 'currency');


    // Expectancy

    setValue('dyn-expectancy', metrics.expectancy || 0, 'currency');

    setValue('dyn-expectancy-long', metrics.long_expectancy || 0, 'currency');

    setValue('dyn-expectancy-short', metrics.short_expectancy || 0, 'currency');


    // Buy & Hold

    const buyHoldValue = metrics.buy_hold_return || 0;

    let buyHoldPct = metrics.buy_hold_return_pct || 0;

    if (buyHoldPct === 0 && buyHoldValue !== 0 && initialCapital > 0) {

        buyHoldPct = (buyHoldValue / initialCapital) * 100;

    }

    setValue('dyn-buy-hold', { val: buyHoldValue, pct: buyHoldPct }, 'currency-pct');


    // Strategy vs Buy & Hold

    // TV "Опережающая динамика" = net_profit_usd - buy_hold_return_usd (absolute USD value)

    let strategyOutperformance = metrics.strategy_outperformance;

    if (strategyOutperformance == null || strategyOutperformance === 0) {

        // Fallback: net_profit minus buy_hold_return in USD

        strategyOutperformance = (metrics.net_profit || 0) - buyHoldValue;

    }

    setValue('dyn-strategy-vs-bh', strategyOutperformance, 'currency');


    // CAGR

    setValue('dyn-cagr', metrics.cagr || 0, 'percent');

    setValue('dyn-cagr-long', metrics.cagr_long || 0, 'percent');

    setValue('dyn-cagr-short', metrics.cagr_short || 0, 'percent');


    // Return on Capital — use net_profit_pct (already in %, backend-authoritative)
    // total_return is a decimal fraction (0-1) — do NOT multiply by 100 here

    setValue('dyn-return-capital', metrics.net_profit_pct ?? (metrics.total_return || 0) * 100, 'percent');

    setValue('dyn-return-capital-long', metrics.long_pnl_pct || 0, 'percent');

    setValue('dyn-return-capital-short', metrics.short_pnl_pct || 0, 'percent');


    // Parse equity curve

    let equityValues = [];

    if (equityCurve) {

        if (Array.isArray(equityCurve)) {

            equityValues = equityCurve.map((p) => p.equity);

        } else if (equityCurve.equity) {

            equityValues = equityCurve.equity;

        }

    }

    if (equityValues.length < 2 && trades && trades.length > 0) {

        equityValues = [initialCapital];

        let cumPnl = initialCapital;

        trades.forEach((t) => {

            cumPnl += t.pnl || 0;

            equityValues.push(cumPnl);

        });

    }


    // Compute runup/drawdown duration stats from equity curve

    let avgGrowthDuration = metrics.avg_runup_duration_bars || 0;

    let avgDrawdownDuration = metrics.avg_drawdown_duration_bars || 0;

    let maxRunupValue = metrics.max_runup_value || 0;

    let maxRunupPct = metrics.max_runup || 0;

    let avgRunupValue = 0;

    let avgRunupPct = 0;

    let avgDrawdownValue = metrics.avg_drawdown_value || 0;

    let avgDrawdownPct = metrics.avg_drawdown || 0;


    if (equityValues.length > 1) {

        const growthPeriods = [];

        const drawdownPeriods = [];

        const runupValues = [];

        const runupBases = [];

        const drawdownValues = [];

        const drawdownPeaks = [];

        let runningMax = equityValues[0];

        let localLow = equityValues[0];

        let periodStartLow = equityValues[0];

        let currentGrowthBars = 0;

        let currentDrawdownBars = 0;

        let inDrawdown = false;

        let currentDrawdownDepth = 0;

        let currentDrawdownPeak = equityValues[0];


        for (let i = 1; i < equityValues.length; i++) {

            const eq = equityValues[i];

            if (eq >= runningMax) {

                if (inDrawdown && currentDrawdownBars > 0) {

                    drawdownPeriods.push(currentDrawdownBars);

                    if (currentDrawdownDepth > 0) {

                        drawdownValues.push(currentDrawdownDepth);

                        drawdownPeaks.push(currentDrawdownPeak);

                    }

                    currentDrawdownBars = 0;

                    currentDrawdownDepth = 0;

                    periodStartLow = localLow;

                }

                runningMax = eq;

                currentGrowthBars++;

                inDrawdown = false;

            } else {

                const dd = runningMax - eq;

                if (dd > currentDrawdownDepth) currentDrawdownDepth = dd;

                if (!inDrawdown && currentGrowthBars > 0) {

                    growthPeriods.push(currentGrowthBars);

                    const runup = runningMax - periodStartLow;

                    if (runup > 0) { runupValues.push(runup); runupBases.push(periodStartLow); }

                    currentGrowthBars = 0;

                    currentDrawdownPeak = runningMax;

                }

                currentDrawdownBars++;

                inDrawdown = true;

                if (eq < localLow) localLow = eq;

            }

        }

        if (currentGrowthBars > 0) {

            growthPeriods.push(currentGrowthBars);

            const totalRunup = runningMax - periodStartLow;

            if (totalRunup > 0) { runupValues.push(totalRunup); runupBases.push(periodStartLow); }

        }

        if (currentDrawdownBars > 0) {

            drawdownPeriods.push(currentDrawdownBars);

            if (currentDrawdownDepth > 0) { drawdownValues.push(currentDrawdownDepth); drawdownPeaks.push(currentDrawdownPeak); }

        }


        if (avgGrowthDuration === 0 && growthPeriods.length > 0) {

            avgGrowthDuration = Math.round(growthPeriods.reduce((a, b) => a + b, 0) / growthPeriods.length);

        }

        if (avgDrawdownDuration === 0 && drawdownPeriods.length > 0) {

            avgDrawdownDuration = Math.round(drawdownPeriods.reduce((a, b) => a + b, 0) / drawdownPeriods.length);

        }

        if (maxRunupValue === 0 && runupValues.length > 0) {

            const maxIdx = runupValues.indexOf(Math.max(...runupValues));

            maxRunupValue = runupValues[maxIdx];

            const base = runupBases[maxIdx] || initialCapital;

            maxRunupPct = base > 0 ? (maxRunupValue / base) * 100 : 0;

        }

        if (runupValues.length > 0) {

            avgRunupValue = runupValues.reduce((a, b) => a + b, 0) / runupValues.length;

            const avgRunupPctSum = runupValues.reduce((sum, v, i) => {

                const base = runupBases[i] || initialCapital;

                return sum + (base > 0 ? (v / base) * 100 : 0);

            }, 0);

            avgRunupPct = avgRunupPctSum / runupValues.length;

        }

        if (avgDrawdownValue === 0 && drawdownValues.length > 0) {

            avgDrawdownValue = drawdownValues.reduce((a, b) => a + b, 0) / drawdownValues.length;

            const avgDDPctSum = drawdownValues.reduce((sum, v, i) => {

                const peak = drawdownPeaks[i] || initialCapital;

                return sum + (peak > 0 ? (v / peak) * 100 : 0);

            }, 0);

            avgDrawdownPct = avgDDPctSum / drawdownValues.length;

        }

    }


    setValue('dyn-avg-growth-duration', avgGrowthDuration, 'number');

    setValue('dyn-avg-equity-growth', { val: avgRunupValue, pct: avgRunupPct }, 'currency-pct');

    setValue('dyn-max-equity-growth', { val: maxRunupValue, pct: maxRunupPct }, 'currency-pct');

    setValue('dyn-avg-dd-duration', avgDrawdownDuration, 'number');

    setValue('dyn-max-drawdown', { val: -(metrics.max_drawdown_value || 0), pct: -(metrics.max_drawdown || 0) }, 'currency-pct');

    setValue('dyn-avg-drawdown', { val: -avgDrawdownValue, pct: -avgDrawdownPct }, 'currency-pct');


    // Intrabar drawdown

    const intrabarValue = metrics.max_drawdown_intrabar_value || 0;

    const intrabarPct = metrics.max_drawdown_intrabar || 0;

    if (intrabarValue > 0 || intrabarPct > 0) {

        setValue('dyn-max-dd-intrabar', { val: -intrabarValue, pct: -intrabarPct }, 'currency-pct');

    } else {

        const intrabarEl = document.getElementById('dyn-max-dd-intrabar');

        if (intrabarEl) {

            intrabarEl.textContent = '--';

            intrabarEl.className = 'tv-value-neutral';

            intrabarEl.title = 'Нет данных (сделки отсутствуют или Bar Magnifier не использовался)';

        }

    }


    // Recovery / Return on Drawdown

    setValue('dyn-return-on-dd', metrics.recovery_factor ?? 0, 'number');

    setValue('dyn-return-on-dd-long', metrics.recovery_long ?? 0, 'number');

    setValue('dyn-return-on-dd-short', metrics.recovery_short ?? 0, 'number');


    // Net Profit vs Max Loss

    const maxLoss = Math.abs(metrics.largest_loss || metrics.worst_trade || 1);

    setValue('dyn-profit-vs-max-loss', maxLoss > 0 ? (metrics.net_profit || 0) / maxLoss : 0, 'number');

    setValue('dyn-profit-vs-max-loss-long', maxLoss > 0 ? (metrics.long_net_profit || 0) / maxLoss : 0, 'number');

    setValue('dyn-profit-vs-max-loss-short', maxLoss > 0 ? (metrics.short_net_profit || 0) / maxLoss : 0, 'number');

}


// ─── Tab 3 — Trade Analysis ───────────────────────────────────────────────────


/**

 * Update the Trade Analysis tab (Tab 3).

 *

 * @param {object}        metrics  - Metrics from backtest API

 * @param {object|null}   config   - Backtest config

 * @param {object[]|null} _trades  - Unused, reserved for future use

 */

export function updateTVTradeAnalysisTab(metrics, config, _trades) {

    if (!metrics) return;


    const _initialCapital = config?.initial_capital || 10000; // Reserved for future use


    const setValue = (id, value, format = 'number') => {

        const el = document.getElementById(id);

        if (!el) return;

        if (value === null || value === undefined) { el.textContent = '--'; return; }

        if (format === 'currency') {

            el.innerHTML = formatTVCurrency(value, null, true);

            el.className = value >= 0 ? 'tv-value-positive' : 'tv-value-negative';

        } else if (format === 'currency-pct') {

            el.innerHTML = formatTVCurrency(value.val, value.pct, true);

            el.className = value.val >= 0 ? 'tv-value-positive' : 'tv-value-negative';

        } else if (format === 'percent') {

            el.textContent = formatTVPercent(value, false);

            el.className = 'tv-value-neutral';

        } else if (format === 'decimal') {

            el.textContent = typeof value === 'number'

                ? value.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

                : value;

            el.className = 'tv-value-neutral';

        } else {

            el.textContent = value.toLocaleString ? value.toLocaleString('ru-RU') : value;

            el.className = 'tv-value-neutral';

        }

    };


    // Trade counts — All

    setValue('ta-open-trades', metrics.open_trades || 0);

    setValue('ta-total-trades', metrics.total_trades || 0);

    setValue('ta-winning-trades', metrics.winning_trades || 0);

    setValue('ta-losing-trades', metrics.losing_trades || 0);

    setValue('ta-breakeven-trades', metrics.breakeven_trades || 0);


    // Trade counts — Long

    setValue('ta-open-trades-long', 0);

    setValue('ta-total-trades-long', metrics.long_trades || 0);

    setValue('ta-winning-trades-long', metrics.long_winning_trades || 0);

    setValue('ta-losing-trades-long', metrics.long_losing_trades || 0);

    setValue('ta-breakeven-trades-long', metrics.long_breakeven_trades || 0);


    // Trade counts — Short

    setValue('ta-open-trades-short', 0);

    setValue('ta-total-trades-short', metrics.short_trades || 0);

    setValue('ta-winning-trades-short', metrics.short_winning_trades || 0);

    setValue('ta-losing-trades-short', metrics.short_losing_trades || 0);

    setValue('ta-breakeven-trades-short', metrics.short_breakeven_trades || 0);


    // Win rate

    setValue('ta-win-rate', metrics.win_rate || 0, 'percent');

    setValue('ta-win-rate-long', metrics.long_win_rate || 0, 'percent');

    setValue('ta-win-rate-short', metrics.short_win_rate || 0, 'percent');


    // Avg P&L — All

    setValue('ta-avg-pnl', { val: metrics.avg_trade_value || 0, pct: metrics.avg_trade_pct || 0 }, 'currency-pct');

    setValue('ta-avg-win', { val: metrics.avg_win_value || 0, pct: metrics.avg_win || 0 }, 'currency-pct');

    setValue('ta-avg-loss', { val: metrics.avg_loss_value || 0, pct: metrics.avg_loss || 0 }, 'currency-pct');


    // Avg P&L — Long

    // Avg P&L — Long (fallback to overall if no long-specific data and no short trades)
    const isLongOnly = (metrics.short_trades || 0) === 0;
    const longAvgTradeVal = metrics.long_avg_trade_value || (isLongOnly ? metrics.avg_trade_value || 0 : 0);
    const longAvgTradePct = metrics.long_avg_trade_pct || (isLongOnly ? metrics.avg_trade_pct || 0 : 0);
    const longAvgWinVal = metrics.long_avg_win_value || (isLongOnly ? metrics.avg_win_value || 0 : 0);
    const longAvgWinPct = metrics.long_avg_win_pct || (isLongOnly ? metrics.avg_win || 0 : 0);
    const longAvgLossVal = metrics.long_avg_loss_value || (isLongOnly ? metrics.avg_loss_value || 0 : 0);
    const longAvgLossPct = metrics.long_avg_loss_pct || (isLongOnly ? metrics.avg_loss || 0 : 0);
    setValue('ta-avg-pnl-long', { val: longAvgTradeVal, pct: longAvgTradePct }, 'currency-pct');
    setValue('ta-avg-win-long', { val: longAvgWinVal, pct: longAvgWinPct }, 'currency-pct');
    setValue('ta-avg-loss-long', { val: longAvgLossVal, pct: longAvgLossPct }, 'currency-pct');


    // Avg P&L — Short

    setValue('ta-avg-pnl-short', { val: metrics.short_avg_trade_value || metrics.short_avg_trade || 0, pct: metrics.short_avg_trade_pct || 0 }, 'currency-pct');

    setValue('ta-avg-win-short', { val: metrics.short_avg_win_value || metrics.short_avg_win || 0, pct: metrics.short_avg_win_pct || 0 }, 'currency-pct');

    setValue('ta-avg-loss-short', { val: metrics.short_avg_loss_value || metrics.short_avg_loss || 0, pct: metrics.short_avg_loss_pct || 0 }, 'currency-pct');


    // Payoff ratio

    setValue('ta-payoff-ratio', metrics.avg_win_loss_ratio || metrics.payoff_ratio || 0, 'number');

    setValue('ta-payoff-ratio-long', metrics.long_payoff_ratio || 0, 'number');

    setValue('ta-payoff-ratio-short', metrics.short_payoff_ratio || 0, 'number');


    // Largest trades — All

    setValue('ta-largest-win', metrics.largest_win_value || metrics.best_trade || 0, 'currency');

    setValue('ta-largest-win-pct', metrics.largest_win || 0, 'percent');

    setValue('ta-largest-loss', metrics.largest_loss_value || metrics.worst_trade || 0, 'currency');

    setValue('ta-largest-loss-pct', metrics.largest_loss || 0, 'percent');


    // Largest trades — Long

    // Fallback: if no long-specific data but all trades are long, use overall

    const longLargestWin = metrics.long_largest_win_value ?? metrics.long_largest_win ?? (metrics.short_trades === 0 ? metrics.largest_win_value || metrics.best_trade || 0 : 0);

    setValue('ta-largest-win-long', longLargestWin, 'currency');

    setValue('ta-largest-win-pct-long', metrics.long_largest_win_pct || metrics.long_largest_win || 0, 'percent');

    const longLargestLoss = metrics.long_largest_loss_value ?? metrics.long_largest_loss ?? (metrics.short_trades === 0 ? metrics.largest_loss_value || metrics.worst_trade || 0 : 0);

    setValue('ta-largest-loss-long', longLargestLoss, 'currency');

    setValue('ta-largest-loss-pct-long', metrics.long_largest_loss || 0, 'percent');


    // Largest trades — Short

    setValue('ta-largest-win-short', metrics.short_largest_win_value || 0, 'currency');

    setValue('ta-largest-win-pct-short', metrics.short_largest_win || 0, 'percent');

    setValue('ta-largest-loss-short', metrics.short_largest_loss_value || 0, 'currency');

    setValue('ta-largest-loss-pct-short', metrics.short_largest_loss || 0, 'percent');


    // Bars in trade

    setValue('ta-avg-bars', metrics.avg_bars_in_trade || 0, 'decimal');

    setValue('ta-avg-bars-win', metrics.avg_bars_in_winning || 0, 'decimal');

    setValue('ta-avg-bars-loss', metrics.avg_bars_in_losing || 0, 'decimal');

    setValue('ta-avg-bars-long', metrics.avg_bars_in_long || 0, 'decimal');

    setValue('ta-avg-bars-short', metrics.avg_bars_in_short || 0, 'decimal');

    setValue('ta-avg-bars-win-long', metrics.avg_bars_in_winning_long || 0, 'decimal');

    setValue('ta-avg-bars-win-short', metrics.avg_bars_in_winning_short || 0, 'decimal');

    setValue('ta-avg-bars-loss-long', metrics.avg_bars_in_losing_long || 0, 'decimal');

    setValue('ta-avg-bars-loss-short', metrics.avg_bars_in_losing_short || 0, 'decimal');


    // Consecutive

    setValue('ta-max-consec-wins', metrics.max_consecutive_wins || 0);

    setValue('ta-max-consec-losses', metrics.max_consecutive_losses || 0);

    setValue('ta-max-consec-wins-long', metrics.long_max_consec_wins || 0);

    setValue('ta-max-consec-wins-short', metrics.short_max_consec_wins || 0);

    setValue('ta-max-consec-losses-long', metrics.long_max_consec_losses || 0);

    setValue('ta-max-consec-losses-short', metrics.short_max_consec_losses || 0);

}


// ─── Tab 4 — Risk / Return ────────────────────────────────────────────────────


/**

 * Update the Risk/Return tab (Tab 4).

 *

 * @param {object}        metrics  - Metrics from backtest API

 * @param {object[]|null} _trades  - Unused, reserved

 * @param {object|null}   _config  - Unused, reserved

 */

export function updateTVRiskReturnTab(metrics, _trades, _config) {

    if (!metrics) return;


    const ratioThresholds = {

        sharpe: { red: 0, green: 1 },

        sortino: { red: 0, green: 1.5 },

        calmar: { red: 0, green: 1 },

        pf: { red: 1, green: 1 },

        recovery: { red: 1, green: 2 },

        kelly: { red: 0, green: 0 },

        default: { red: 0, green: 0 }

    };


    const getColorClass = (value, thresholdKey) => {

        const t = ratioThresholds[thresholdKey] || ratioThresholds.default;

        if (value < t.red) return 'tv-value-negative';

        if (value > t.green) return 'tv-value-positive';

        return 'tv-value-neutral';

    };


    const setValue = (id, value, thresholdKey) => {

        const el = document.getElementById(id);

        if (!el) return;

        if (value === null || value === undefined || isNaN(value)) {

            el.textContent = '--';

            el.className = 'tv-value-neutral';

            return;

        }

        el.textContent = value.toFixed(3);

        el.className = thresholdKey ? getColorClass(value, thresholdKey) : 'tv-value-neutral';

    };


    // All

    setValue('rr-sharpe', metrics.sharpe_ratio, 'sharpe');
    // Adaptive-Sharpe method tooltip + inline note
    const _sharpeEl = document.getElementById('rr-sharpe');
    if (_sharpeEl) {
        const _method = metrics.sharpe_method || 'fallback';
        const _N = Number(metrics.sharpe_samples ?? 0);
        const _tips = {
            monthly: 'Monthly returns, RFR=2%/yr — TV-parity',
            weekly: 'Weekly returns, RFR=2%/yr — window <12 mo',
            'per-trade': 'Trade-by-trade mean/std, non-annualized',
            fallback: 'Hourly-annualized fallback — not TV-parity',
        };
        _sharpeEl.title = `Method: ${_method} (N=${_N})\n${_tips[_method] || _tips.fallback}`;
        if (_method && _method !== 'fallback' && _N > 0) {
            _sharpeEl.textContent = `${_sharpeEl.textContent}  ·  ${_method} N=${_N}`;
        }
    }

    setValue('rr-sortino', metrics.sortino_ratio, 'sortino');

    setValue('rr-profit-factor', metrics.profit_factor, 'pf');

    setValue('rr-calmar', metrics.calmar_ratio, 'calmar');

    setValue('rr-recovery', metrics.recovery_factor, 'recovery');


    // Advanced metrics

    setValue('rr-ulcer', metrics.ulcer_index);

    setValue('rr-ulcer-long', metrics.ulcer_index_long || null);

    setValue('rr-ulcer-short', metrics.ulcer_index_short || null);

    setValue('rr-margin-eff', metrics.margin_efficiency);

    setValue('rr-margin-eff-long', metrics.margin_efficiency_long || null);

    setValue('rr-margin-eff-short', metrics.margin_efficiency_short || null);

    setValue('rr-stability', metrics.stability);

    setValue('rr-stability-long', metrics.stability_long || null);

    setValue('rr-stability-short', metrics.stability_short || null);

    setValue('rr-sqn', metrics.sqn);

    setValue('rr-sqn-long', metrics.sqn_long || null);

    setValue('rr-sqn-short', metrics.sqn_short || null);


    // Long — show '--' when no long trades exist (N4 fix)
    setValue('rr-sharpe-long', metrics.long_trades > 0 ? metrics.sharpe_long : null, 'sharpe');
    setValue('rr-sortino-long', metrics.long_trades > 0 ? metrics.sortino_long : null, 'sortino');
    setValue('rr-profit-factor-long', metrics.long_trades > 0 ? metrics.long_profit_factor : null, 'pf');
    setValue('rr-calmar-long', metrics.long_trades > 0 ? metrics.calmar_long : null, 'calmar');
    setValue('rr-recovery-long', metrics.long_trades > 0 ? metrics.recovery_long : null, 'recovery');

    // Short — show '--' when no short trades exist (N4 fix)
    setValue('rr-sharpe-short', metrics.short_trades > 0 ? metrics.sharpe_short : null, 'sharpe');
    setValue('rr-sortino-short', metrics.short_trades > 0 ? metrics.sortino_short : null, 'sortino');
    setValue('rr-profit-factor-short', metrics.short_trades > 0 ? metrics.short_profit_factor : null, 'pf');
    setValue('rr-calmar-short', metrics.short_trades > 0 ? metrics.calmar_short : null, 'calmar');
    setValue('rr-recovery-short', metrics.short_trades > 0 ? metrics.recovery_short : null, 'recovery');


    // Kelly

    setValue('rr-kelly', (metrics.kelly_percent || 0) * 100, 'kelly');

    setValue('rr-kelly-long', (metrics.kelly_percent_long || 0) * 100, 'kelly');

    setValue('rr-kelly-short', (metrics.kelly_percent_short || 0) * 100, 'kelly');


    // Payoff ratio

    const payoff = metrics.payoff_ratio ||

        (metrics.avg_win && metrics.avg_loss ? Math.abs(metrics.avg_win / metrics.avg_loss) : 0);

    setValue('rr-payoff', payoff);

    setValue('rr-payoff-long', metrics.long_payoff_ratio || 0);

    setValue('rr-payoff-short', metrics.short_payoff_ratio || 0);


    // Consecutive wins/losses (integer display)

    const setIntValue = (id, value) => {

        const el = document.getElementById(id);

        if (!el) return;

        el.textContent = value !== null && value !== undefined ? value : '--';

        el.className = 'tv-value-neutral';

    };

    setIntValue('rr-max-consec-wins', metrics.max_consecutive_wins);

    setIntValue('rr-max-consec-wins-long', metrics.long_max_consec_wins);

    setIntValue('rr-max-consec-wins-short', metrics.short_max_consec_wins);

    setIntValue('rr-max-consec-losses', metrics.max_consecutive_losses);

    setIntValue('rr-max-consec-losses-long', metrics.long_max_consec_losses);

    setIntValue('rr-max-consec-losses-short', metrics.short_max_consec_losses);

}

