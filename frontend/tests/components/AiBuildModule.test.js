/**
 * AiBuildModule.test.js — Unit tests for AiBuildModule.js
 * Run: npx vitest run tests/components/AiBuildModule.test.js
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { AI_PRESETS, createAiBuildModule } from '../../js/components/AiBuildModule.js';

// ── Helpers ──────────────────────────────────────────────────────────────────

function makeDOM() {
    document.body.innerHTML = `
    <div id="aiBuildModal" class="hidden" style="display:none">
      <div class="ai-build-modal-content">
        <div class="ai-build-header"><h3></h3></div>
        <div class="ai-build-preset-heading"></div>
        <div id="aiBuildConfig"></div>
        <div id="aiBuildProgress" class="hidden"></div>
        <div id="aiBuildResults" class="hidden"></div>
        <div id="aiBuildResultContent"></div>
        <div id="aiBuildSummary"></div>
        <div id="agentMonitor" class="hidden">
          <div id="agentColumns"></div>
          <div id="agentFeed-deepseek"></div>
          <div id="agentFeed-qwen"></div>
          <div id="agentFeed-perplexity"></div>
          <span id="agentBadge-deepseek">0</span>
          <span id="agentBadge-qwen">0</span>
          <span id="agentBadge-perplexity">0</span>
          <button id="btnToggleAgentMonitor"></button>
        </div>
        <div id="aiBuildStage"></div>
      </div>
    </div>
    <input id="aiPreset" value="rsi" />
    <div id="aiBlocksPreview"></div>
    <button id="btnRunAiBuild"></button>
    <input id="aiName" value="" />
    <textarea id="aiDescription"></textarea>
    <input id="aiMaxIter" value="3" />
    <input id="aiMinSharpe" value="0.5" />
    <input id="aiDeliberation" type="checkbox" />
    <input id="aiUseOptimizer" type="checkbox" />
    <select id="aiExistingStrategy"><option value="">— Создать новую —</option></select>
    <div id="aiExistingStrategyHint" style="display:none"></div>
    <span id="aiNameHint"></span>
    <input id="strategyName" value="Test Strategy" />
    <input id="backtestSymbol" value="BTCUSDT" />
    <input id="strategyTimeframe" value="15" />
    <select id="builderDirection"><option value="both" selected>both</option></select>
    <input id="backtestCapital" value="10000" />
    <input id="backtestLeverage" value="10" />
    <input id="backtestStartDate" value="2025-01-01" />
    <input id="backtestEndDate" value="2025-06-01" />
    <select id="builderMarketType"><option value="linear" selected>linear</option></select>
  `;
}

function makeDeps(overrides = {}) {
    return {
        getStrategyIdFromURL: vi.fn(() => null),
        getBlocks: vi.fn(() => []),
        getConnections: vi.fn(() => []),
        displayBacktestResults: vi.fn(),
        loadStrategy: vi.fn(() => Promise.resolve()),
        escapeHtml: (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'),
        ...overrides
    };
}

// ── AI_PRESETS ────────────────────────────────────────────────────────────────

describe('AI_PRESETS', () => {
    it('exports named presets', () => {
        expect(Object.keys(AI_PRESETS)).toEqual(expect.arrayContaining(['rsi', 'ema_cross', 'macd', 'bb', 'custom']));
    });

    it('each preset has blocks and connections arrays', () => {
        for (const [key, preset] of Object.entries(AI_PRESETS)) {
            expect(Array.isArray(preset.blocks), `${key}.blocks`).toBe(true);
            expect(Array.isArray(preset.connections), `${key}.connections`).toBe(true);
        }
    });

    it('rsi preset has 4 blocks', () => {
        expect(AI_PRESETS.rsi.blocks).toHaveLength(4);
    });

    it('custom preset is empty', () => {
        expect(AI_PRESETS.custom.blocks).toHaveLength(0);
        expect(AI_PRESETS.custom.connections).toHaveLength(0);
    });
});

// ── createAiBuildModule factory ───────────────────────────────────────────────

describe('createAiBuildModule', () => {
    it('returns expected public API', () => {
        const mod = createAiBuildModule(makeDeps());
        expect(typeof mod.openAiBuildModal).toBe('function');
        expect(typeof mod.closeAiBuildModal).toBe('function');
        expect(typeof mod.applyAiPreset).toBe('function');
        expect(typeof mod.resetAiBuild).toBe('function');
        expect(typeof mod.runAiBuild).toBe('function');
        expect(typeof mod.showAiBuildResults).toBe('function');
        expect(typeof mod.toggleAgentMonitor).toBe('function');
        expect(typeof mod.viewAiBacktestFullResults).toBe('function');
    });
});

// ── openAiBuildModal ──────────────────────────────────────────────────────────

describe('openAiBuildModal', () => {
    beforeEach(makeDOM);

    it('removes hidden class and sets display flex', () => {
        const mod = createAiBuildModule(makeDeps());
        mod.openAiBuildModal();
        const modal = document.getElementById('aiBuildModal');
        expect(modal.classList.contains('hidden')).toBe(false);
        expect(modal.style.display).toBe('flex');
    });

    it('sets build mode when no existing strategy', async () => {
        const deps = makeDeps({ getStrategyIdFromURL: () => null });
        const mod = createAiBuildModule(deps);
        mod.openAiBuildModal();
        // Title is set inside a .then() callback — flush microtask queue
        await new Promise((r) => setTimeout(r, 0));
        const title = document.querySelector('.ai-build-header h3');
        expect(title.innerHTML).toContain('AI Strategy Builder');
    });

    it('sets optimize mode when strategy exists with canvas blocks', async () => {
        const deps = makeDeps({
            getStrategyIdFromURL: () => 'abc123',
            getBlocks: () => [{ type: 'rsi' }]
        });
        const mod = createAiBuildModule(deps);
        mod.openAiBuildModal();
        // Title is set inside a .then() callback — flush microtask queue
        await new Promise((r) => setTimeout(r, 0));
        const title = document.querySelector('.ai-build-header h3');
        expect(title.innerHTML).toContain('AI Strategy Optimizer');
    });

    it('populates summary with symbol', () => {
        const mod = createAiBuildModule(makeDeps());
        mod.openAiBuildModal();
        const summary = document.getElementById('aiBuildSummary').innerHTML;
        expect(summary).toContain('BTCUSDT');
    });

    it('shows warning when symbol is empty', () => {
        document.getElementById('backtestSymbol').value = '';
        const mod = createAiBuildModule(makeDeps());
        mod.openAiBuildModal();
        const summary = document.getElementById('aiBuildSummary').innerHTML;
        expect(summary).toContain('summary-warning');
    });
});

// ── closeAiBuildModal ─────────────────────────────────────────────────────────

describe('closeAiBuildModal', () => {
    beforeEach(makeDOM);

    it('adds hidden class and clears display', () => {
        const mod = createAiBuildModule(makeDeps());
        mod.openAiBuildModal();
        mod.closeAiBuildModal();
        const modal = document.getElementById('aiBuildModal');
        expect(modal.classList.contains('hidden')).toBe(true);
        expect(modal.style.display).toBe('');
    });
});

// ── applyAiPreset ─────────────────────────────────────────────────────────────

describe('applyAiPreset', () => {
    beforeEach(makeDOM);

    it('populates preview with preset blocks JSON', () => {
        document.getElementById('aiPreset').value = 'rsi';
        const mod = createAiBuildModule(makeDeps());
        mod.applyAiPreset();
        const preview = document.getElementById('aiBlocksPreview').textContent;
        expect(preview).toContain('rsi');
    });

    it('does nothing when preset select not found', () => {
        document.getElementById('aiPreset').remove();
        const mod = createAiBuildModule(makeDeps());
        expect(() => mod.applyAiPreset()).not.toThrow();
    });
});

// ── resetAiBuild ──────────────────────────────────────────────────────────────

describe('resetAiBuild', () => {
    beforeEach(makeDOM);

    it('shows config panel and hides progress + results', () => {
        document.getElementById('aiBuildConfig').classList.add('hidden');
        document.getElementById('aiBuildProgress').classList.remove('hidden');
        document.getElementById('aiBuildResults').classList.remove('hidden');

        const mod = createAiBuildModule(makeDeps());
        mod.resetAiBuild();

        expect(document.getElementById('aiBuildConfig').classList.contains('hidden')).toBe(false);
        expect(document.getElementById('aiBuildProgress').classList.contains('hidden')).toBe(true);
        expect(document.getElementById('aiBuildResults').classList.contains('hidden')).toBe(true);
    });
});

// ── toggleAgentMonitor ────────────────────────────────────────────────────────

describe('toggleAgentMonitor', () => {
    beforeEach(makeDOM);

    it('toggles hidden class on agentColumns', () => {
        const mod = createAiBuildModule(makeDeps());
        const cols = document.getElementById('agentColumns');
        expect(cols.classList.contains('hidden')).toBe(false);
        mod.toggleAgentMonitor();
        expect(cols.classList.contains('hidden')).toBe(true);
        mod.toggleAgentMonitor();
        expect(cols.classList.contains('hidden')).toBe(false);
    });

    it('does not throw when agentColumns not found', () => {
        document.getElementById('agentColumns').remove();
        const mod = createAiBuildModule(makeDeps());
        expect(() => mod.toggleAgentMonitor()).not.toThrow();
    });
});

// ── viewAiBacktestFullResults ─────────────────────────────────────────────────

describe('viewAiBacktestFullResults', () => {
    it('opens window with correct URL when backtestId provided', () => {
        const openSpy = vi.spyOn(window, 'open').mockImplementation(() => { });
        const mod = createAiBuildModule(makeDeps());
        mod.viewAiBacktestFullResults('test-id-123');
        expect(openSpy).toHaveBeenCalledWith(
            '/frontend/backtest-results.html?backtest_id=test-id-123',
            '_blank'
        );
        openSpy.mockRestore();
    });

    it('does not open window when backtestId is falsy', () => {
        const openSpy = vi.spyOn(window, 'open').mockImplementation(() => { });
        const mod = createAiBuildModule(makeDeps());
        mod.viewAiBacktestFullResults(null);
        expect(openSpy).not.toHaveBeenCalled();
        openSpy.mockRestore();
    });
});

// ── showAiBuildResults ────────────────────────────────────────────────────────

describe('showAiBuildResults', () => {
    beforeEach(makeDOM);

    it('makes aiBuildResults visible', async () => {
        const mod = createAiBuildModule(makeDeps());
        await mod.showAiBuildResults({ success: true, workflow: {} });
        expect(document.getElementById('aiBuildResults').classList.contains('hidden')).toBe(false);
    });

    it('renders success alert when data.success is true', async () => {
        const mod = createAiBuildModule(makeDeps());
        await mod.showAiBuildResults({
            success: true,
            workflow: { status: 'done', duration_seconds: 5, iterations: [], errors: [] }
        });
        const html = document.getElementById('aiBuildResultContent').innerHTML;
        expect(html).toContain('alert-success');
        expect(html).toContain('Strategy Built');
    });

    it('renders warning alert when data.success is false', async () => {
        const mod = createAiBuildModule(makeDeps());
        await mod.showAiBuildResults({
            success: false,
            workflow: { status: 'below_target', duration_seconds: 3, iterations: [] }
        });
        const html = document.getElementById('aiBuildResultContent').innerHTML;
        expect(html).toContain('alert-warning');
        expect(html).toContain('Below Target');
    });

    it('renders iteration table when iterations present', async () => {
        const mod = createAiBuildModule(makeDeps());
        await mod.showAiBuildResults({
            success: true,
            workflow: {
                status: 'done',
                duration_seconds: 2,
                iterations: [
                    { iteration: 1, sharpe_ratio: 1.2, win_rate: 0.55, net_profit: 500, max_drawdown: 8, total_trades: 30, acceptable: true }
                ]
            }
        });
        const html = document.getElementById('aiBuildResultContent').innerHTML;
        expect(html).toContain('Iterations');
        expect(html).toContain('1.200');
    });

    it('shows zero-trades warning when totalTrades is 0', async () => {
        const mod = createAiBuildModule(makeDeps());
        await mod.showAiBuildResults({
            success: false,
            workflow: {
                status: 'no_trades',
                duration_seconds: 1,
                iterations: [{ iteration: 1, total_trades: 0, sharpe_ratio: 0, win_rate: 0, net_profit: 0, max_drawdown: 0, acceptable: false }]
            }
        });
        const html = document.getElementById('aiBuildResultContent').innerHTML;
        expect(html).toContain('0 Trades Detected');
    });

    it('calls displayBacktestResults when backtestId present and fetch succeeds', async () => {
        const displayFn = vi.fn();
        const deps = makeDeps({ displayBacktestResults: displayFn });
        const mod = createAiBuildModule(deps);

        vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ trades: [], equity_curve: [] })
        })));

        await mod.showAiBuildResults({
            success: true,
            workflow: {
                status: 'done',
                duration_seconds: 1,
                backtest_results: { backtest_id: 'bt-abc' },
                iterations: []
            }
        });

        expect(displayFn).toHaveBeenCalled();
        vi.unstubAllGlobals();
    });
});

// ── runAiBuild validation ─────────────────────────────────────────────────────

describe('runAiBuild', () => {
    beforeEach(makeDOM);

    it('alerts and returns early when symbol is empty', async () => {
        document.getElementById('backtestSymbol').value = '';
        const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => { });
        const mod = createAiBuildModule(makeDeps());
        await mod.runAiBuild();
        expect(alertSpy).toHaveBeenCalled();
        alertSpy.mockRestore();
    });

    it('shows progress panel when symbol is set', async () => {
        const mod = createAiBuildModule(makeDeps());
        // Mock fetch to hang — we only want to check DOM side-effects synchronously
        vi.stubGlobal('fetch', vi.fn(() => new Promise(() => { }))); // never resolves
        mod.runAiBuild(); // do not await
        expect(document.getElementById('aiBuildProgress').classList.contains('hidden')).toBe(false);
        vi.unstubAllGlobals();
    });
});
