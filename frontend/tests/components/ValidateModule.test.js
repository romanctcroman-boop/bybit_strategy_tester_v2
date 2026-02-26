/**
 * Tests for ValidateModule
 *
 * Covers: validateStrategyCompleteness, validateStrategy, updateValidationPanel,
 *         generateCode, getExitBlockTypes.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { createValidateModule } from '../../js/components/ValidateModule.js';

// ── Helpers ───────────────────────────────────────────────────────────────────

function makeMainBlock() {
    return {
        id: 'main_strategy',
        type: 'strategy',
        category: 'main',
        isMain: true,
        name: 'Strategy',
        params: {}
    };
}

function makeBlock(overrides = {}) {
    return {
        id: `block_${Math.random().toString(36).slice(2, 6)}`,
        type: 'rsi',
        category: 'indicator',
        name: 'RSI',
        isMain: false,
        params: { period: 14 },
        ...overrides
    };
}

function makeConn(sourceId, sourcePt, targetId, targetPt) {
    return {
        id: `conn_${Math.random().toString(36).slice(2, 6)}`,
        source: { blockId: sourceId, portId: sourcePt },
        target: { blockId: targetId, portId: targetPt }
    };
}

/** Set DOM values used by validateStrategyCompleteness/validateStrategy */
function setDom({ symbol = 'BTCUSDT', startDate = '2025-01-01', endDate = '2025-12-31', capital = '10000', direction = 'both' } = {}) {
    const set = (id, val) => {
        const el = document.getElementById(id) || (() => {
            const e = document.createElement('input');
            e.id = id;
            document.body.appendChild(e);
            return e;
        })();
        el.value = val;
    };
    set('backtestSymbol', symbol);
    set('backtestStartDate', startDate);
    set('backtestEndDate', endDate);
    set('backtestCapital', capital);
    const d = document.getElementById('builderDirection') || (() => {
        const e = document.createElement('select');
        e.id = 'builderDirection';
        document.body.appendChild(e);
        return e;
    })();
    d.value = direction;
}

/** Build a module with sensible defaults */
function setup({ blocks = [], connections = [] } = {}) {
    const mocks = {
        getBlockPorts: vi.fn().mockReturnValue(null),
        validateBlockParams: vi.fn().mockReturnValue({ valid: true, errors: [] }),
        updateBlockValidationState: vi.fn(),
        getStrategyIdFromURL: vi.fn().mockReturnValue(null),
        saveStrategy: vi.fn().mockResolvedValue(undefined),
        showNotification: vi.fn(),
        escapeHtml: vi.fn((s) => s)
    };

    const mod = createValidateModule({
        getBlocks: () => blocks,
        getConnections: () => connections,
        ...mocks
    });

    return { mod, mocks };
}

// ── createValidateModule ──────────────────────────────────────────────────────

describe('createValidateModule', () => {
    it('returns all expected public methods', () => {
        const { mod } = setup();
        expect(typeof mod.validateStrategyCompleteness).toBe('function');
        expect(typeof mod.validateStrategy).toBe('function');
        expect(typeof mod.updateValidationPanel).toBe('function');
        expect(typeof mod.generateCode).toBe('function');
        expect(typeof mod.getExitBlockTypes).toBe('function');
    });
});

// ── getExitBlockTypes ─────────────────────────────────────────────────────────

describe('getExitBlockTypes', () => {
    it('returns a Set containing static_sltp', () => {
        const { mod } = setup();
        const set = mod.getExitBlockTypes();
        expect(set).toBeInstanceOf(Set);
        expect(set.has('static_sltp')).toBe(true);
    });

    it('contains all expected exit types', () => {
        const { mod } = setup();
        const set = mod.getExitBlockTypes();
        for (const t of ['static_sltp', 'trailing_stop_exit', 'atr_exit', 'tp_percent', 'sl_percent']) {
            expect(set.has(t)).toBe(true);
        }
    });
});

// ── validateStrategyCompleteness ─────────────────────────────────────────────

describe('validateStrategyCompleteness', () => {
    beforeEach(() => {
        document.body.innerHTML = '';
    });

    it('fails when no main node', () => {
        setDom();
        const { mod } = setup({ blocks: [] });
        const r = mod.validateStrategyCompleteness();
        expect(r.valid).toBe(false);
        expect(r.errors.some(e => e.includes('Main strategy node'))).toBe(true);
    });

    it('fails when symbol is missing', () => {
        setDom({ symbol: '' });
        const main = makeMainBlock();
        const entryConn = makeConn('sig1', 'signal', main.id, 'entry_long');
        const slBlock = makeBlock({ type: 'static_sltp' });
        const { mod } = setup({ blocks: [main, slBlock], connections: [entryConn] });
        const r = mod.validateStrategyCompleteness();
        expect(r.valid).toBe(false);
        expect(r.errors.some(e => e.includes('Symbol'))).toBe(true);
    });

    it('fails when capital is 0', () => {
        setDom({ capital: '0' });
        const main = makeMainBlock();
        const entryConn = makeConn('sig1', 'signal', main.id, 'entry_long');
        const slBlock = makeBlock({ type: 'static_sltp' });
        const { mod } = setup({ blocks: [main, slBlock], connections: [entryConn] });
        const r = mod.validateStrategyCompleteness();
        expect(r.valid).toBe(false);
        expect(r.errors.some(e => e.includes('Capital'))).toBe(true);
    });

    it('fails when no entry connections', () => {
        setDom();
        const main = makeMainBlock();
        const slBlock = makeBlock({ type: 'static_sltp' });
        const { mod } = setup({ blocks: [main, slBlock], connections: [] });
        const r = mod.validateStrategyCompleteness();
        expect(r.valid).toBe(false);
        expect(r.errors.some(e => e.includes('Вход'))).toBe(true);
    });

    it('fails when no exit conditions', () => {
        setDom();
        const main = makeMainBlock();
        const sig = makeBlock();
        const entryConn = makeConn(sig.id, 'signal', main.id, 'entry_long');
        const { mod } = setup({ blocks: [main, sig], connections: [entryConn] });
        const r = mod.validateStrategyCompleteness();
        expect(r.valid).toBe(false);
        expect(r.errors.some(e => e.includes('Выход'))).toBe(true);
    });

    it('passes with valid structure', () => {
        setDom();
        const main = makeMainBlock();
        const sig = makeBlock();
        const slBlock = makeBlock({ type: 'static_sltp' });
        const entryConn = makeConn(sig.id, 'signal', main.id, 'entry_long');
        const { mod } = setup({ blocks: [main, sig, slBlock], connections: [entryConn] });
        const r = mod.validateStrategyCompleteness();
        expect(r.valid).toBe(true);
        expect(r.errors).toHaveLength(0);
    });

    it('warns when date range > 10 years', () => {
        setDom({ startDate: '2010-01-01', endDate: '2025-01-01' });
        const main = makeMainBlock();
        const sig = makeBlock();
        const slBlock = makeBlock({ type: 'static_sltp' });
        const entryConn = makeConn(sig.id, 'signal', main.id, 'entry_long');
        const { mod } = setup({ blocks: [main, sig, slBlock], connections: [entryConn] });
        const r = mod.validateStrategyCompleteness();
        expect(r.warnings.some(w => w.includes('10 лет'))).toBe(true);
    });

    it('warns when no SL/TP block but has exit signals', () => {
        setDom();
        const main = makeMainBlock();
        const sig = makeBlock();
        const entryConn = makeConn(sig.id, 'signal', main.id, 'entry_long');
        const exitConn = makeConn(sig.id, 'signal', main.id, 'exit_long');
        const { mod } = setup({
            blocks: [main, sig],
            connections: [entryConn, exitConn]
        });
        const r = mod.validateStrategyCompleteness();
        expect(r.valid).toBe(true); // exit signals satisfy exit requirement
        expect(r.warnings.some(w => w.includes('SL/TP'))).toBe(true);
    });
});

// ── validateStrategy (async) ──────────────────────────────────────────────────

describe('validateStrategy', () => {
    beforeEach(() => {
        document.body.innerHTML = '';
    });

    it('calls showNotification with "info" at start', async () => {
        setDom();
        const { mod, mocks } = setup({ blocks: [makeMainBlock()] });
        await mod.validateStrategy();
        expect(mocks.showNotification).toHaveBeenCalledWith(
            expect.stringContaining('Валидация'),
            'info'
        );
    });

    it('calls updateBlockValidationState for each non-main block', async () => {
        setDom();
        const main = makeMainBlock();
        const b1 = makeBlock();
        const b2 = makeBlock();
        const slBlock = makeBlock({ type: 'static_sltp' });
        const entryConn = makeConn(b1.id, 'signal', main.id, 'entry_long');
        const { mod, mocks } = setup({
            blocks: [main, b1, b2, slBlock],
            connections: [entryConn]
        });

        await mod.validateStrategy();
        // Called for b1, b2, slBlock (not main)
        expect(mocks.updateBlockValidationState).toHaveBeenCalledTimes(3);
    });

    it('reports block param errors from validateBlockParams', async () => {
        setDom();
        const main = makeMainBlock();
        const b = makeBlock({ name: 'BadBlock' });
        const slBlock = makeBlock({ type: 'static_sltp' });
        const entryConn = makeConn(b.id, 'signal', main.id, 'entry_long');

        const mocks = {
            getBlockPorts: vi.fn().mockReturnValue(null),
            validateBlockParams: vi.fn((block) =>
                block.name === 'BadBlock'
                    ? { valid: false, errors: ['period must be > 0'] }
                    : { valid: true, errors: [] }
            ),
            updateBlockValidationState: vi.fn(),
            getStrategyIdFromURL: vi.fn().mockReturnValue(null),
            saveStrategy: vi.fn().mockResolvedValue(undefined),
            showNotification: vi.fn(),
            escapeHtml: vi.fn((s) => s)
        };

        const mod = createValidateModule({
            getBlocks: () => [main, b, slBlock],
            getConnections: () => [entryConn],
            ...mocks
        });

        await mod.validateStrategy();
        // updateValidationPanel fallback notification contains the error text
        const allCalls = mocks.showNotification.mock.calls;
        const hasBlockError = allCalls.some(([msg]) =>
            typeof msg === 'string' && msg.includes('BadBlock')
        );
        expect(hasBlockError).toBe(true);
    });

    it('does not throw on empty blocks array', async () => {
        setDom();
        const { mod } = setup({ blocks: [], connections: [] });
        await expect(mod.validateStrategy()).resolves.toBeUndefined();
    });
});

// ── updateValidationPanel ─────────────────────────────────────────────────────

describe('updateValidationPanel', () => {
    beforeEach(() => {
        document.body.innerHTML = '';
    });

    it('falls back to showNotification when DOM elements missing', () => {
        const { mod, mocks } = setup();
        mod.updateValidationPanel({
            valid: false,
            errors: ['something wrong'],
            warnings: []
        });
        expect(mocks.showNotification).toHaveBeenCalledWith(
            expect.stringContaining('Валидация'),
            'warning'
        );
    });

    it('shows success notification when valid with no warnings', () => {
        const status = document.createElement('div');
        status.id = 'validationStatus';
        const list = document.createElement('ul');
        list.id = 'validationList';
        document.body.appendChild(status);
        document.body.appendChild(list);

        const { mod, mocks } = setup();
        mod.updateValidationPanel({ valid: true, errors: [], warnings: [] });
        expect(mocks.showNotification).toHaveBeenCalledWith(
            'Стратегия валидна!',
            'success'
        );
    });

    it('shows error notification when there are errors', () => {
        const status = document.createElement('div');
        status.id = 'validationStatus';
        const list = document.createElement('ul');
        list.id = 'validationList';
        document.body.appendChild(status);
        document.body.appendChild(list);

        const { mod, mocks } = setup();
        mod.updateValidationPanel({ valid: false, errors: ['Missing entry'], warnings: [] });
        expect(mocks.showNotification).toHaveBeenCalledWith(
            expect.stringContaining('не пройдена'),
            'error'
        );
    });

    it('shows warning notification when valid but has warnings', () => {
        const status = document.createElement('div');
        status.id = 'validationStatus';
        const list = document.createElement('ul');
        list.id = 'validationList';
        document.body.appendChild(status);
        document.body.appendChild(list);

        const { mod, mocks } = setup();
        mod.updateValidationPanel({ valid: true, errors: [], warnings: ['No SL/TP'] });
        expect(mocks.showNotification).toHaveBeenCalledWith(
            expect.stringContaining('Предупреждения'),
            'warning'
        );
    });
});

// ── generateCode ──────────────────────────────────────────────────────────────

describe('generateCode', () => {
    beforeEach(() => {
        document.body.innerHTML = '';
        vi.stubGlobal('fetch', vi.fn());
        vi.stubGlobal('confirm', vi.fn().mockReturnValue(false));
        vi.stubGlobal('open', vi.fn());
    });

    it('shows warning when symbol not selected', async () => {
        setDom({ symbol: '' });
        const { mod, mocks } = setup();
        await mod.generateCode();
        expect(mocks.showNotification).toHaveBeenCalledWith(
            expect.stringContaining('тикер'),
            'warning'
        );
        expect(fetch).not.toHaveBeenCalled();
    });

    it('prompts to save when no strategy ID in URL', async () => {
        setDom();
        const { mod, mocks } = setup();
        await mod.generateCode();
        expect(mocks.showNotification).toHaveBeenCalledWith(
            expect.stringContaining('Сохраните'),
            'warning'
        );
    });

    it('calls API and shows success on valid response', async () => {
        setDom();
        const mocks = {
            getBlockPorts: vi.fn(),
            validateBlockParams: vi.fn(),
            updateBlockValidationState: vi.fn(),
            getStrategyIdFromURL: vi.fn().mockReturnValue('strat-42'),
            saveStrategy: vi.fn().mockResolvedValue(undefined),
            showNotification: vi.fn(),
            escapeHtml: vi.fn((s) => s)
        };
        const mod = createValidateModule({
            getBlocks: () => [],
            getConnections: () => [],
            ...mocks
        });

        vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
            ok: true,
            json: vi.fn().mockResolvedValue({ success: true, code: 'print("hello")' })
        }));
        vi.stubGlobal('open', vi.fn().mockReturnValue(null)); // popup blocked

        await mod.generateCode();

        expect(fetch).toHaveBeenCalledWith(
            expect.stringContaining('strat-42'),
            expect.objectContaining({ method: 'POST' })
        );
        expect(mocks.showNotification).toHaveBeenCalledWith(
            expect.stringContaining('успешно'),
            'success'
        );
    });

    it('shows error notification on HTTP failure', async () => {
        setDom();
        const mocks = {
            getBlockPorts: vi.fn(),
            validateBlockParams: vi.fn(),
            updateBlockValidationState: vi.fn(),
            getStrategyIdFromURL: vi.fn().mockReturnValue('strat-7'),
            saveStrategy: vi.fn().mockResolvedValue(undefined),
            showNotification: vi.fn(),
            escapeHtml: vi.fn((s) => s)
        };
        const mod = createValidateModule({
            getBlocks: () => [],
            getConnections: () => [],
            ...mocks
        });

        vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
            ok: false,
            status: 500,
            text: vi.fn().mockResolvedValue('Internal Server Error')
        }));

        await mod.generateCode();
        expect(mocks.showNotification).toHaveBeenCalledWith(
            expect.stringContaining('не удалась'),
            'error'
        );
    });
});
