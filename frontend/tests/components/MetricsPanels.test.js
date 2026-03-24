/**
 * 🧪 MetricsPanels.test.js — Unit tests for MetricsPanels component
 *
 * Tests: formatTVCurrency, formatTVPercent,
 *        updateTVSummaryCards, updateTVDynamicsTab,
 *        updateTVTradeAnalysisTab, updateTVRiskReturnTab
 *
 * @group P0-2 Phase 3
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import {
    formatTVCurrency,
    formatTVPercent,
    updateTVSummaryCards,
    updateTVDynamicsTab,
    updateTVTradeAnalysisTab,
    updateTVRiskReturnTab
} from '../../js/components/MetricsPanels.js';

// ─── Helpers ──────────────────────────────────────────────────────────────────

function el(id, tag = 'span') {
    const e = document.createElement(tag);
    e.id = id;
    document.body.appendChild(e);
    return e;
}

// ─── formatTVCurrency ─────────────────────────────────────────────────────────

describe('formatTVCurrency', () => {
    it('returns "--" for null', () => {
        expect(formatTVCurrency(null)).toBe('--');
    });

    it('returns "--" for undefined', () => {
        expect(formatTVCurrency(undefined)).toBe('--');
    });

    it('formats positive value with + sign', () => {
        const result = formatTVCurrency(100.5, null, true);
        expect(result).toContain('+');
        expect(result).toContain('USD');
    });

    it('formats negative value without + sign', () => {
        const result = formatTVCurrency(-50.25, null, true);
        expect(result).not.toMatch(/\+/);
        expect(result).toContain('USD');
    });

    it('cleans up -0,00 display', () => {
        const result = formatTVCurrency(-0.001, null, true);
        expect(result).not.toContain('-0,00');
    });

    it('returns dual-value HTML when pct provided', () => {
        const result = formatTVCurrency(100, 1.5, true);
        expect(result).toContain('tv-dual-value');
        expect(result).toContain('tv-main-value');
        expect(result).toContain('tv-pct-value');
        expect(result).toContain('%');
    });

    it('cleans up -0.00% in pct', () => {
        const result = formatTVCurrency(-0.001, -0.001, true);
        expect(result).not.toContain('-0.00%');
    });

    it('no + sign when showSign=false', () => {
        const result = formatTVCurrency(200, null, false);
        expect(result).not.toContain('+');
    });
});

// ─── formatTVPercent ──────────────────────────────────────────────────────────

describe('formatTVPercent', () => {
    it('returns "--" for null', () => {
        expect(formatTVPercent(null)).toBe('--');
    });

    it('formats positive with + sign', () => {
        expect(formatTVPercent(5.25, true)).toBe('+5.25%');
    });

    it('formats negative without + sign', () => {
        expect(formatTVPercent(-3.5, true)).toBe('-3.50%');
    });

    it('cleans -0.00%', () => {
        expect(formatTVPercent(-0.001)).toBe('0.00%');
    });

    it('no + sign when showSign=false', () => {
        expect(formatTVPercent(10, false)).toBe('10.00%');
    });
});

// ─── updateTVSummaryCards ─────────────────────────────────────────────────────

describe('updateTVSummaryCards', () => {
    beforeEach(() => {
        el('tvNetProfit');
        el('tvNetProfitPct');
        el('tvMaxDrawdown');
        el('tvMaxDrawdownPct');
        el('tvTotalTrades');
        el('tvWinningTrades');
        el('tvWinRate');
        el('tvProfitFactor');
    });

    afterEach(() => { document.body.innerHTML = ''; });

    it('does nothing when metrics is null', () => {
        expect(() => updateTVSummaryCards(null)).not.toThrow();
    });

    it('sets net profit text', () => {
        updateTVSummaryCards({ net_profit: 500 });
        expect(document.getElementById('tvNetProfit').textContent).toContain('500');
    });

    it('adds positive class for positive net profit', () => {
        updateTVSummaryCards({ net_profit: 100 });
        expect(document.getElementById('tvNetProfit').className).toContain('tv-value-positive');
    });

    it('adds negative class for negative net profit', () => {
        updateTVSummaryCards({ net_profit: -100 });
        expect(document.getElementById('tvNetProfit').className).toContain('tv-value-negative');
    });

    it('sets net profit pct', () => {
        updateTVSummaryCards({ net_profit: 100, net_profit_pct: 1.5 });
        expect(document.getElementById('tvNetProfitPct').textContent).toContain('1.50');
    });

    it('sets total trades', () => {
        updateTVSummaryCards({ total_trades: 42 });
        expect(document.getElementById('tvTotalTrades').textContent).toBe('42');
    });

    it('sets win rate', () => {
        updateTVSummaryCards({ win_rate: 62.5 });
        expect(document.getElementById('tvWinRate').textContent).toContain('62.50%');
    });

    it('sets profit factor with 3 decimals', () => {
        updateTVSummaryCards({ profit_factor: 1.2 });
        expect(document.getElementById('tvProfitFactor').textContent).toBe('1.200');
    });
});

// ─── updateTVDynamicsTab ──────────────────────────────────────────────────────

describe('updateTVDynamicsTab', () => {
    beforeEach(() => {
        ['dyn-initial-capital', 'dyn-net-profit', 'dyn-gross-profit', 'dyn-gross-loss',
            'dyn-commission', 'dyn-expectancy', 'dyn-buy-hold', 'dyn-strategy-vs-bh',
            'dyn-cagr', 'dyn-return-capital', 'dyn-max-drawdown', 'dyn-avg-drawdown',
            'dyn-return-on-dd', 'dyn-avg-growth-duration', 'dyn-max-equity-growth',
            'dyn-avg-equity-growth', 'dyn-avg-dd-duration', 'dyn-max-dd-intrabar',
            'dyn-profit-factor', 'dyn-unrealized', 'dyn-profit-vs-max-loss'
        ].forEach((id) => el(id));
    });

    afterEach(() => { document.body.innerHTML = ''; });

    it('does nothing when metrics is null', () => {
        expect(() => updateTVDynamicsTab(null, null, null, null)).not.toThrow();
    });

    it('sets initial capital from config', () => {
        updateTVDynamicsTab({}, { initial_capital: 15000 }, [], null);
        expect(document.getElementById('dyn-initial-capital').textContent).toContain('15');
    });

    it('sets net profit as dual value', () => {
        updateTVDynamicsTab({ net_profit: 1000, net_profit_pct: 10 }, null, [], null);
        const el = document.getElementById('dyn-net-profit');
        expect(el.innerHTML).toContain('tv-dual-value');
    });

    it('sets positive class for positive net profit', () => {
        updateTVDynamicsTab({ net_profit: 500, net_profit_pct: 5 }, null, [], null);
        expect(document.getElementById('dyn-net-profit').className).toContain('tv-value-positive');
    });

    it('sets negative class for negative net profit', () => {
        updateTVDynamicsTab({ net_profit: -200, net_profit_pct: -2 }, null, [], null);
        expect(document.getElementById('dyn-net-profit').className).toContain('tv-value-negative');
    });

    it('shows "--" for intrabar when no data', () => {
        updateTVDynamicsTab({}, null, [], null);
        expect(document.getElementById('dyn-max-dd-intrabar').textContent).toBe('--');
    });

    it('sets intrabar drawdown when data present', () => {
        updateTVDynamicsTab({ max_drawdown_intrabar_value: 500, max_drawdown_intrabar: 5 }, null, [], null);
        expect(document.getElementById('dyn-max-dd-intrabar').innerHTML).toContain('tv-dual-value');
    });

    it('builds equity values from trades when equityCurve absent', () => {
        const trades = [{ pnl: 100 }, { pnl: -50 }, { pnl: 200 }];
        // Should not throw — just processes
        expect(() => updateTVDynamicsTab({}, { initial_capital: 10000 }, trades, null)).not.toThrow();
    });
});

// ─── updateTVTradeAnalysisTab ─────────────────────────────────────────────────

describe('updateTVTradeAnalysisTab', () => {
    beforeEach(() => {
        ['ta-total-trades', 'ta-winning-trades', 'ta-losing-trades', 'ta-win-rate',
            'ta-avg-pnl', 'ta-avg-win', 'ta-avg-loss', 'ta-largest-win',
            'ta-largest-loss', 'ta-avg-bars', 'ta-max-consec-wins', 'ta-max-consec-losses',
            'ta-open-trades', 'ta-breakeven-trades', 'ta-payoff-ratio'
        ].forEach((id) => el(id));
    });

    afterEach(() => { document.body.innerHTML = ''; });

    it('does nothing when metrics is null', () => {
        expect(() => updateTVTradeAnalysisTab(null)).not.toThrow();
    });

    it('sets total trades', () => {
        updateTVTradeAnalysisTab({ total_trades: 55 });
        expect(document.getElementById('ta-total-trades').textContent).toBe('55');
    });

    it('sets win rate as percent (no sign)', () => {
        updateTVTradeAnalysisTab({ win_rate: 60 });
        const text = document.getElementById('ta-win-rate').textContent;
        expect(text).toBe('60.00%');
        expect(text).not.toContain('+');
    });

    it('sets avg pnl as dual currency-pct', () => {
        updateTVTradeAnalysisTab({ avg_trade_value: 50, avg_trade_pct: 0.5 });
        expect(document.getElementById('ta-avg-pnl').innerHTML).toContain('tv-dual-value');
    });

    it('sets largest win as currency', () => {
        updateTVTradeAnalysisTab({ largest_win_value: 1500 });
        const html = document.getElementById('ta-largest-win').innerHTML;
        expect(html).toContain('USD');
    });

    it('sets max consec wins as integer', () => {
        updateTVTradeAnalysisTab({ max_consecutive_wins: 7 });
        expect(document.getElementById('ta-max-consec-wins').textContent).toBe('7');
    });

    it('sets payoff ratio as number', () => {
        updateTVTradeAnalysisTab({ avg_win_loss_ratio: 2.5 });
        expect(document.getElementById('ta-payoff-ratio').textContent).toContain('2');
    });
});

// ─── updateTVRiskReturnTab ────────────────────────────────────────────────────

describe('updateTVRiskReturnTab', () => {
    beforeEach(() => {
        ['rr-sharpe', 'rr-sortino', 'rr-profit-factor', 'rr-calmar', 'rr-recovery',
            'rr-sharpe-long', 'rr-sharpe-short', 'rr-kelly', 'rr-payoff',
            'rr-max-consec-wins', 'rr-max-consec-losses',
            'rr-ulcer', 'rr-sqn', 'rr-stability', 'rr-margin-eff'
        ].forEach((id) => el(id));
    });

    afterEach(() => { document.body.innerHTML = ''; });

    it('does nothing when metrics is null', () => {
        expect(() => updateTVRiskReturnTab(null)).not.toThrow();
    });

    it('shows "--" for null sharpe', () => {
        updateTVRiskReturnTab({});
        expect(document.getElementById('rr-sharpe').textContent).toBe('--');
    });

    it('shows "--" for NaN value', () => {
        updateTVRiskReturnTab({ sharpe_ratio: NaN });
        expect(document.getElementById('rr-sharpe').textContent).toBe('--');
    });

    it('sets sharpe with 3 decimals', () => {
        updateTVRiskReturnTab({ sharpe_ratio: 1.2567 });
        expect(document.getElementById('rr-sharpe').textContent).toBe('1.257');
    });

    it('adds positive class for sharpe > 1', () => {
        updateTVRiskReturnTab({ sharpe_ratio: 1.5 });
        expect(document.getElementById('rr-sharpe').className).toContain('tv-value-positive');
    });

    it('adds negative class for sharpe < 0', () => {
        updateTVRiskReturnTab({ sharpe_ratio: -0.5 });
        expect(document.getElementById('rr-sharpe').className).toContain('tv-value-negative');
    });

    it('neutral class for sharpe between 0 and 1', () => {
        updateTVRiskReturnTab({ sharpe_ratio: 0.8 });
        expect(document.getElementById('rr-sharpe').className).toContain('tv-value-neutral');
    });

    it('sets kelly * 100', () => {
        updateTVRiskReturnTab({ kelly_percent: 0.25 });
        expect(document.getElementById('rr-kelly').textContent).toBe('25.000');
    });

    it('sets max consec wins as integer', () => {
        updateTVRiskReturnTab({ max_consecutive_wins: 10 });
        expect(document.getElementById('rr-max-consec-wins').textContent).toBe('10');
    });

    it('profit-factor negative class when < 1', () => {
        updateTVRiskReturnTab({ profit_factor: 0.8 });
        expect(document.getElementById('rr-profit-factor').className).toContain('tv-value-negative');
    });

    it('profit-factor positive class when > 1', () => {
        updateTVRiskReturnTab({ profit_factor: 1.5 });
        expect(document.getElementById('rr-profit-factor').className).toContain('tv-value-positive');
    });
});
