/**
 * Tests for SaveLoadModule
 *
 * Covers: migrateLegacyBlocks, buildStrategyPayload, saveStrategy,
 *         autoSaveStrategy, loadStrategy, openVersionsModal,
 *         closeVersionsModal, revertToVersion.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { createSaveLoadModule } from '../../js/components/SaveLoadModule.js';

// ── Helpers ───────────────────────────────────────────────────────────────────

function makeMainBlock(overrides = {}) {
    return {
        id: 'main_strategy',
        type: 'strategy',
        category: 'main',
        isMain: true,
        name: 'Strategy',
        icon: 'diagram-3',
        x: 800,
        y: 300,
        params: {},
        ...overrides
    };
}

function makeBlock(overrides = {}) {
    return {
        id: `block_${Math.random().toString(36).slice(2, 6)}`,
        type: 'rsi',
        category: 'indicator',
        name: 'RSI',
        x: 100,
        y: 100,
        isMain: false,
        params: { period: 14 },
        ...overrides
    };
}

/** Set DOM form fields */
function setDom({ name = 'Test Strategy', symbol = 'BTCUSDT', capital = '10000' } = {}) {
    const set = (id, val, tag = 'input') => {
        let el = document.getElementById(id);
        if (!el) {
            el = document.createElement(tag);
            el.id = id;
            document.body.appendChild(el);
        }
        el.value = val;
    };
    set('strategyName', name);
    set('backtestSymbol', symbol);
    set('backtestCapital', capital);
    set('strategyTimeframe', '15');
    set('builderMarketType', 'linear', 'select');
    set('builderDirection', 'both', 'select');
    set('backtestLeverage', '10');
    set('backtestPositionSizeType', 'percent', 'select');
    set('backtestPositionSize', '100');
    set('backtestCommission', '0.07');
    set('backtestSlippage', '0');
    set('backtestPyramiding', '1');
    set('backtestStartDate', '2025-01-01');
    set('backtestEndDate', '2025-12-31');
}

/** Build module with mocked deps */
function setup({ blocks = [], connections = [] } = {}) {
    let _blocks = [...blocks];
    let _conns = [...connections];
    let _lastAutoSave = null;
    let _skipNext = false;

    const mocks = {
        getStrategyIdFromURL: vi.fn().mockReturnValue(null),
        showNotification: vi.fn(),
        renderBlocks: vi.fn(),
        renderConnections: vi.fn(),
        normalizeAllConnections: vi.fn(),
        syncStrategyNameDisplay: vi.fn(),
        renderBlockProperties: vi.fn(),
        pushUndo: vi.fn(),
        createMainStrategyNode: vi.fn(),
        getBlockLibrary: vi.fn().mockReturnValue({}),
        updateRunButtonsState: vi.fn(),
        runCheckSymbolDataForProperties: vi.fn(),
        updateBacktestLeverageDisplay: vi.fn(),
        updateBacktestPositionSizeInput: vi.fn(),
        updateBacktestLeverageRisk: vi.fn(),
        setNoTradeDaysInUI: vi.fn(),
        getNoTradeDaysFromUI: vi.fn().mockReturnValue([]),
        normalizeTimeframeForDropdown: vi.fn((tf) => tf),
        getLastAutoSavePayload: vi.fn(() => _lastAutoSave),
        setLastAutoSavePayload: vi.fn((v) => { _lastAutoSave = v; }),
        getSkipNextAutoSave: vi.fn(() => _skipNext),
        setSkipNextAutoSave: vi.fn((v) => { _skipNext = v; }),
        closeBlockParamsPopup: vi.fn(),
        wsValidation: null,
        getZoom: vi.fn().mockReturnValue(1),
        escapeHtml: vi.fn((s) => s),
        formatDate: vi.fn((d) => d)
    };

    const mod = createSaveLoadModule({
        getBlocks: () => _blocks,
        getConnections: () => _conns,
        setBlocks: (arr) => { _blocks = arr; },
        setConnections: (arr) => { _conns = arr; },
        ...mocks
    });

    return { mod, mocks, getBlocks: () => _blocks, getConns: () => _conns };
}

// ── migrateLegacyBlocks ───────────────────────────────────────────────────────

describe('migrateLegacyBlocks', () => {
    it('returns unchanged when no legacy blocks', () => {
        const { mod } = setup();
        const blocks = [makeBlock({ type: 'rsi' })];
        const result = mod.migrateLegacyBlocks(blocks);
        expect(result).toHaveLength(1);
        expect(result[0].type).toBe('rsi');
    });

    it('converts tp_percent + sl_percent into a single static_sltp', () => {
        const { mod } = setup();
        const tp = makeBlock({ type: 'tp_percent', params: { take_profit_percent: 2.0 }, x: 50, y: 50 });
        const sl = makeBlock({ type: 'sl_percent', params: { stop_loss_percent: 1.0 } });
        const result = mod.migrateLegacyBlocks([tp, sl]);

        expect(result).toHaveLength(1);
        const merged = result[0];
        expect(merged.type).toBe('static_sltp');
        expect(merged.params.take_profit_percent).toBe(2.0);
        expect(merged.params.stop_loss_percent).toBe(1.0);
    });

    it('converts only tp_percent when sl_percent absent', () => {
        const { mod } = setup();
        const tp = makeBlock({ type: 'tp_percent', params: { take_profit_percent: 3.0 } });
        const result = mod.migrateLegacyBlocks([tp]);
        expect(result).toHaveLength(1);
        expect(result[0].type).toBe('static_sltp');
        expect(result[0].params.stop_loss_percent).toBe(1.5); // default
    });

    it('converts only sl_percent when tp_percent absent', () => {
        const { mod } = setup();
        const sl = makeBlock({ type: 'sl_percent', params: { stop_loss_percent: 0.8 } });
        const result = mod.migrateLegacyBlocks([sl]);
        expect(result).toHaveLength(1);
        expect(result[0].type).toBe('static_sltp');
        expect(result[0].params.stop_loss_percent).toBe(0.8);
        expect(result[0].params.take_profit_percent).toBe(1.5); // default
    });

    it('preserves position from reference block', () => {
        const { mod } = setup();
        const tp = makeBlock({ type: 'tp_percent', x: 200, y: 350 });
        const result = mod.migrateLegacyBlocks([tp]);
        expect(result[0].x).toBe(200);
        expect(result[0].y).toBe(350);
    });

    it('keeps non-legacy blocks alongside the merged block', () => {
        const { mod } = setup();
        const rsi = makeBlock({ type: 'rsi' });
        const tp = makeBlock({ type: 'tp_percent' });
        const result = mod.migrateLegacyBlocks([rsi, tp]);
        expect(result).toHaveLength(2);
        expect(result.find(b => b.type === 'rsi')).toBeTruthy();
        expect(result.find(b => b.type === 'static_sltp')).toBeTruthy();
    });
});

// ── buildStrategyPayload ──────────────────────────────────────────────────────

describe('buildStrategyPayload', () => {
    beforeEach(() => { document.body.innerHTML = ''; });

    it('returns correct symbol and name from DOM', () => {
        setDom({ name: 'My Strat', symbol: 'ETHUSDT' });
        const { mod } = setup({ blocks: [makeMainBlock()] });
        const payload = mod.buildStrategyPayload();
        expect(payload.name).toBe('My Strat');
        expect(payload.symbol).toBe('ETHUSDT');
    });

    it('serialises blocks correctly', () => {
        setDom();
        const main = makeMainBlock();
        const b = makeBlock({ params: { period: 21 } });
        const { mod } = setup({ blocks: [main, b] });
        const payload = mod.buildStrategyPayload();
        expect(payload.blocks).toHaveLength(2);
        expect(payload.blocks[1].params.period).toBe(21);
    });

    it('serialises connections correctly', () => {
        setDom();
        const main = makeMainBlock();
        const conn = { id: 'c1', source: { blockId: 'b1', portId: 'sig' }, target: { blockId: main.id, portId: 'entry_long' } };
        const { mod } = setup({ blocks: [main], connections: [conn] });
        const payload = mod.buildStrategyPayload();
        expect(payload.connections).toHaveLength(1);
        expect(payload.connections[0].id).toBe('c1');
    });

    it('converts percent position size to fraction', () => {
        setDom();
        const { mod } = setup();
        const payload = mod.buildStrategyPayload();
        // positionSizeVal=100, posType='percent' → 100/100 = 1.0
        expect(payload.position_size).toBeCloseTo(1.0);
    });

    it('includes uiState with zoom', () => {
        setDom();
        const mocks = {
            getStrategyIdFromURL: vi.fn().mockReturnValue(null),
            showNotification: vi.fn(),
            renderBlocks: vi.fn(),
            normalizeAllConnections: vi.fn(),
            syncStrategyNameDisplay: vi.fn(),
            renderBlockProperties: vi.fn(),
            pushUndo: vi.fn(),
            createMainStrategyNode: vi.fn(),
            getBlockLibrary: vi.fn().mockReturnValue({}),
            updateRunButtonsState: vi.fn(),
            runCheckSymbolDataForProperties: vi.fn(),
            updateBacktestLeverageDisplay: vi.fn(),
            updateBacktestPositionSizeInput: vi.fn(),
            updateBacktestLeverageRisk: vi.fn(),
            setNoTradeDaysInUI: vi.fn(),
            getNoTradeDaysFromUI: vi.fn().mockReturnValue([]),
            normalizeTimeframeForDropdown: vi.fn((tf) => tf),
            getLastAutoSavePayload: vi.fn().mockReturnValue(null),
            setLastAutoSavePayload: vi.fn(),
            getSkipNextAutoSave: vi.fn().mockReturnValue(false),
            setSkipNextAutoSave: vi.fn(),
            closeBlockParamsPopup: vi.fn(),
            wsValidation: null,
            getZoom: vi.fn().mockReturnValue(1.5),
            escapeHtml: vi.fn((s) => s),
            formatDate: vi.fn((d) => d)
        };
        const mod = createSaveLoadModule({
            getBlocks: () => [],
            getConnections: () => [],
            setBlocks: vi.fn(),
            setConnections: vi.fn(),
            ...mocks
        });
        const payload = mod.buildStrategyPayload();
        expect(payload.uiState.zoom).toBe(1.5);
    });
});

// ── saveStrategy ──────────────────────────────────────────────────────────────

describe('saveStrategy', () => {
    beforeEach(() => {
        document.body.innerHTML = '';
        vi.stubGlobal('fetch', vi.fn());
        vi.stubGlobal('navigator', { onLine: true });
    });

    it('shows warning when strategy has no blocks', async () => {
        setDom({ name: 'Valid Name' });
        // Make fetch succeed (POST new strategy)
        fetch
            .mockResolvedValueOnce({ ok: false, text: vi.fn().mockResolvedValue('not found') })
            .mockResolvedValueOnce({
                ok: true,
                json: vi.fn().mockResolvedValue({ id: 'new-1', updated_at: new Date().toISOString() })
            });
        const { mod, mocks } = setup({ blocks: [] });
        await mod.saveStrategy();
        const allCalls = mocks.showNotification.mock.calls;
        const hasBlocksWarning = allCalls.some(
            ([msg, type]) => msg.includes('блок') && type === 'warning'
        );
        expect(hasBlocksWarning).toBe(true);
    }); it('shows offline warning when navigator.onLine is false', async () => {
        vi.stubGlobal('navigator', { onLine: false });
        setDom();
        const { mod, mocks } = setup({ blocks: [makeMainBlock()] });
        await mod.saveStrategy();
        expect(mocks.showNotification).toHaveBeenCalledWith(
            expect.stringContaining('сети'),
            'warning'
        );
    });

    it('calls POST when no strategy ID in URL', async () => {
        setDom();
        // First fetch (check) fails, second (save) succeeds
        fetch
            .mockResolvedValueOnce({ ok: false, text: vi.fn().mockResolvedValue('not found') })
            .mockResolvedValueOnce({
                ok: true,
                json: vi.fn().mockResolvedValue({ id: 'new-42', updated_at: new Date().toISOString() })
            });

        const mocks = {
            getStrategyIdFromURL: vi.fn().mockReturnValue('existing-id'),
            showNotification: vi.fn(),
            renderBlocks: vi.fn(),
            normalizeAllConnections: vi.fn(),
            syncStrategyNameDisplay: vi.fn(),
            renderBlockProperties: vi.fn(),
            pushUndo: vi.fn(),
            createMainStrategyNode: vi.fn(),
            getBlockLibrary: vi.fn().mockReturnValue({}),
            updateRunButtonsState: vi.fn(),
            runCheckSymbolDataForProperties: vi.fn(),
            updateBacktestLeverageDisplay: vi.fn(),
            updateBacktestPositionSizeInput: vi.fn(),
            updateBacktestLeverageRisk: vi.fn(),
            setNoTradeDaysInUI: vi.fn(),
            getNoTradeDaysFromUI: vi.fn().mockReturnValue([]),
            normalizeTimeframeForDropdown: vi.fn((tf) => tf),
            getLastAutoSavePayload: vi.fn().mockReturnValue(null),
            setLastAutoSavePayload: vi.fn(),
            getSkipNextAutoSave: vi.fn().mockReturnValue(false),
            setSkipNextAutoSave: vi.fn(),
            closeBlockParamsPopup: vi.fn(),
            wsValidation: null,
            getZoom: vi.fn().mockReturnValue(1),
            escapeHtml: vi.fn((s) => s),
            formatDate: vi.fn((d) => d)
        };
        const mod = createSaveLoadModule({
            getBlocks: () => [makeMainBlock()],
            getConnections: () => [],
            setBlocks: vi.fn(),
            setConnections: vi.fn(),
            ...mocks
        });

        await mod.saveStrategy();
        expect(mocks.showNotification).toHaveBeenCalledWith(
            expect.stringContaining('успешно сохранена'),
            'success'
        );
    });

    it('shows error notification on HTTP failure', async () => {
        setDom();
        // Check passes, save fails
        fetch
            .mockResolvedValueOnce({ ok: true, text: vi.fn().mockResolvedValue('ok') })
            .mockResolvedValueOnce({
                ok: false,
                status: 500,
                text: vi.fn().mockResolvedValue('{"detail":"Internal error"}')
            });

        const mocks = {
            getStrategyIdFromURL: vi.fn().mockReturnValue('sid-1'),
            showNotification: vi.fn(),
            renderBlocks: vi.fn(),
            normalizeAllConnections: vi.fn(),
            syncStrategyNameDisplay: vi.fn(),
            renderBlockProperties: vi.fn(),
            pushUndo: vi.fn(),
            createMainStrategyNode: vi.fn(),
            getBlockLibrary: vi.fn().mockReturnValue({}),
            updateRunButtonsState: vi.fn(),
            runCheckSymbolDataForProperties: vi.fn(),
            updateBacktestLeverageDisplay: vi.fn(),
            updateBacktestPositionSizeInput: vi.fn(),
            updateBacktestLeverageRisk: vi.fn(),
            setNoTradeDaysInUI: vi.fn(),
            getNoTradeDaysFromUI: vi.fn().mockReturnValue([]),
            normalizeTimeframeForDropdown: vi.fn((tf) => tf),
            getLastAutoSavePayload: vi.fn().mockReturnValue(null),
            setLastAutoSavePayload: vi.fn(),
            getSkipNextAutoSave: vi.fn().mockReturnValue(false),
            setSkipNextAutoSave: vi.fn(),
            closeBlockParamsPopup: vi.fn(),
            wsValidation: null,
            getZoom: vi.fn().mockReturnValue(1),
            escapeHtml: vi.fn((s) => s),
            formatDate: vi.fn((d) => d)
        };
        const mod = createSaveLoadModule({
            getBlocks: () => [makeMainBlock()],
            getConnections: () => [],
            setBlocks: vi.fn(),
            setConnections: vi.fn(),
            ...mocks
        });

        await mod.saveStrategy();
        expect(mocks.showNotification).toHaveBeenCalledWith(
            expect.stringContaining('Ошибка сохранения'),
            'error'
        );
    });
});

// ── autoSaveStrategy ──────────────────────────────────────────────────────────

describe('autoSaveStrategy', () => {
    beforeEach(() => {
        document.body.innerHTML = '';
        vi.stubGlobal('fetch', vi.fn());
        vi.stubGlobal('navigator', { onLine: true });
        const ls = { store: {}, setItem: vi.fn(), removeItem: vi.fn() };
        vi.stubGlobal('localStorage', ls);
    });

    it('skips when skipNextAutoSave is true', async () => {
        setDom();
        const { mod, mocks } = setup({ blocks: [makeMainBlock()] });
        mocks.getSkipNextAutoSave.mockReturnValue(true);
        await mod.autoSaveStrategy();
        expect(mocks.setLastAutoSavePayload).not.toHaveBeenCalled();
    });

    it('skips when blocks are empty', async () => {
        setDom();
        const { mod } = setup({ blocks: [], connections: [] });
        await mod.autoSaveStrategy();
        expect(fetch).not.toHaveBeenCalled();
    });

    it('skips when clean initial state (single strategy node, no connections)', async () => {
        setDom();
        const { mod } = setup({ blocks: [makeMainBlock()], connections: [] });
        await mod.autoSaveStrategy();
        expect(fetch).not.toHaveBeenCalled();
    });

    it('does not call remote PUT for draft strategies', async () => {
        setDom();
        const b = makeBlock();
        const { mod, mocks } = setup({
            blocks: [makeMainBlock(), b],
            connections: [{ id: 'c1', source: { blockId: b.id, portId: 'sig' }, target: { blockId: 'main_strategy', portId: 'entry_long' } }]
        });
        mocks.getStrategyIdFromURL.mockReturnValue(null); // draft
        await mod.autoSaveStrategy();
        expect(fetch).not.toHaveBeenCalled();
        expect(mocks.setLastAutoSavePayload).toHaveBeenCalled();
    });
});

// ── loadStrategy ─────────────────────────────────────────────────────────────

describe('loadStrategy', () => {
    beforeEach(() => {
        document.body.innerHTML = '';
        vi.stubGlobal('fetch', vi.fn());
    });

    it('shows error when 404 returned', async () => {
        fetch.mockResolvedValue({ ok: false, status: 404, text: vi.fn().mockResolvedValue('Not found') });
        const { mod, mocks } = setup();
        await mod.loadStrategy('nonexistent');
        expect(mocks.showNotification).toHaveBeenCalledWith(
            expect.stringContaining('не найдена'),
            'error'
        );
    });

    it('shows success notification on successful load', async () => {
        setDom();
        const strategy = {
            id: 'strat-99',
            name: 'Loaded Strategy',
            timeframe: '15',
            symbol: 'BTCUSDT',
            market_type: 'linear',
            direction: 'both',
            initial_capital: 10000,
            leverage: 10,
            position_size: 1.0,
            parameters: {},
            blocks: [makeMainBlock()],
            connections: [],
            updated_at: new Date().toISOString()
        };
        fetch.mockResolvedValue({
            ok: true,
            json: vi.fn().mockResolvedValue(strategy)
        });

        const { mod, mocks } = setup();
        await mod.loadStrategy('strat-99');
        expect(mocks.showNotification).toHaveBeenCalledWith(
            expect.stringContaining('загружена'),
            'success'
        );
        expect(mocks.renderBlocks).toHaveBeenCalled();
    });

    it('calls migrateLegacyBlocks during load', async () => {
        setDom();
        const tp = makeBlock({ type: 'tp_percent', params: { take_profit_percent: 2.0 } });
        const strategy = {
            id: 'strat-mig',
            name: 'Migration Test',
            timeframe: '15',
            symbol: 'BTCUSDT',
            market_type: 'linear',
            direction: 'both',
            initial_capital: 10000,
            leverage: 10,
            position_size: 1.0,
            parameters: {},
            blocks: [makeMainBlock(), tp],
            connections: [],
            updated_at: new Date().toISOString()
        };
        fetch.mockResolvedValue({ ok: true, json: vi.fn().mockResolvedValue(strategy) });

        const { mod, getBlocks } = setup();
        await mod.loadStrategy('strat-mig');

        const loadedBlocks = getBlocks();
        expect(loadedBlocks.some(b => b.type === 'static_sltp')).toBe(true);
        expect(loadedBlocks.every(b => b.type !== 'tp_percent')).toBe(true);
    });
});

// ── openVersionsModal / closeVersionsModal ────────────────────────────────────

describe('openVersionsModal', () => {
    beforeEach(() => {
        document.body.innerHTML = '';
        vi.stubGlobal('fetch', vi.fn());
    });

    it('shows warning when no strategy ID', async () => {
        const { mod, mocks } = setup();
        await mod.openVersionsModal();
        expect(mocks.showNotification).toHaveBeenCalledWith(
            expect.stringContaining('существующую'),
            'warning'
        );
    });

    it('does nothing when DOM modal missing', async () => {
        const mocks = {
            getStrategyIdFromURL: vi.fn().mockReturnValue('strat-55'),
            showNotification: vi.fn(),
            renderBlocks: vi.fn(),
            normalizeAllConnections: vi.fn(),
            syncStrategyNameDisplay: vi.fn(),
            renderBlockProperties: vi.fn(),
            pushUndo: vi.fn(),
            createMainStrategyNode: vi.fn(),
            getBlockLibrary: vi.fn().mockReturnValue({}),
            updateRunButtonsState: vi.fn(),
            runCheckSymbolDataForProperties: vi.fn(),
            updateBacktestLeverageDisplay: vi.fn(),
            updateBacktestPositionSizeInput: vi.fn(),
            updateBacktestLeverageRisk: vi.fn(),
            setNoTradeDaysInUI: vi.fn(),
            getNoTradeDaysFromUI: vi.fn().mockReturnValue([]),
            normalizeTimeframeForDropdown: vi.fn((tf) => tf),
            getLastAutoSavePayload: vi.fn().mockReturnValue(null),
            setLastAutoSavePayload: vi.fn(),
            getSkipNextAutoSave: vi.fn().mockReturnValue(false),
            setSkipNextAutoSave: vi.fn(),
            closeBlockParamsPopup: vi.fn(),
            wsValidation: null,
            getZoom: vi.fn().mockReturnValue(1),
            escapeHtml: vi.fn((s) => s),
            formatDate: vi.fn((d) => d)
        };
        const mod = createSaveLoadModule({
            getBlocks: () => [],
            getConnections: () => [],
            setBlocks: vi.fn(),
            setConnections: vi.fn(),
            ...mocks
        });
        // No DOM modal element — should not throw
        await expect(mod.openVersionsModal()).resolves.toBeUndefined();
        expect(fetch).not.toHaveBeenCalled();
    });
});

describe('closeVersionsModal', () => {
    it('removes active class from versions modal', () => {
        const modal = document.createElement('div');
        modal.id = 'versionsModal';
        modal.classList.add('active');
        document.body.appendChild(modal);

        const { mod } = setup();
        mod.closeVersionsModal();
        expect(modal.classList.contains('active')).toBe(false);
    });

    it('does not throw when modal not in DOM', () => {
        document.body.innerHTML = '';
        const { mod } = setup();
        expect(() => mod.closeVersionsModal()).not.toThrow();
    });
});

// ── revertToVersion ───────────────────────────────────────────────────────────

describe('revertToVersion', () => {
    beforeEach(() => {
        document.body.innerHTML = '';
        vi.stubGlobal('fetch', vi.fn());
        vi.stubGlobal('confirm', vi.fn());
    });

    it('does nothing when user cancels confirm', async () => {
        vi.mocked(confirm).mockReturnValue(false);
        const { mod } = setup();
        await mod.revertToVersion('strat-1', 5);
        expect(fetch).not.toHaveBeenCalled();
    });

    it('calls revert API and loads strategy on confirm', async () => {
        vi.mocked(confirm).mockReturnValue(true);
        fetch
            .mockResolvedValueOnce({ ok: true, text: vi.fn().mockResolvedValue('ok') })
            .mockResolvedValueOnce({
                ok: true,
                json: vi.fn().mockResolvedValue({
                    id: 'strat-1',
                    name: 'Reverted',
                    timeframe: '15',
                    symbol: 'BTCUSDT',
                    market_type: 'linear',
                    direction: 'both',
                    initial_capital: 10000,
                    leverage: 10,
                    position_size: 1.0,
                    parameters: {},
                    blocks: [makeMainBlock()],
                    connections: [],
                    updated_at: new Date().toISOString()
                })
            });
        setDom();

        const { mod, mocks } = setup();
        await mod.revertToVersion('strat-1', 5);

        expect(fetch).toHaveBeenCalledTimes(2);
        expect(mocks.showNotification).toHaveBeenCalledWith(
            expect.stringContaining('восстановлена'),
            'success'
        );
    });
});
