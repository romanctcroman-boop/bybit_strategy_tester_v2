/**
 * Tests for UndoRedoModule
 *
 * Covers: pushUndo, undo, redo, deleteSelected, duplicateSelected,
 *         getStateSnapshot, restoreStateSnapshot, updateUndoRedoButtons,
 *         alignBlocks, autoLayout, stack accessors.
 */
import { describe, it, expect, vi } from 'vitest';
import { createUndoRedoModule } from '../../js/components/UndoRedoModule.js';

// ── Test helpers ─────────────────────────────────────────────────────────────

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

function makeMainBlock(overrides = {}) {
    return makeBlock({ id: 'main_strategy', type: 'strategy', isMain: true, ...overrides });
}

function makeConn(sourceId, targetId) {
    return {
        id: `conn_${Math.random().toString(36).slice(2, 6)}`,
        source: { blockId: sourceId, portId: 'signal' },
        target: { blockId: targetId, portId: 'entry_long' }
    };
}

/** Build a standard module + in-memory state for testing */
function setup({ blocks = [], connections = [] } = {}) {
    let _blocks = [...blocks];
    let _conns = [...connections];
    let _selectedId = null;
    let _lastAutoSave = null;

    const mocks = {
        renderBlocks: vi.fn(),
        renderBlockProperties: vi.fn(),
        dispatchBlocksChanged: vi.fn(),
        validateStrategy: vi.fn().mockResolvedValue(undefined),
        showNotification: vi.fn(),
        selectBlock: vi.fn((id) => { _selectedId = id; }),
        setLastAutoSavePayload: vi.fn((v) => { _lastAutoSave = v; })
    };

    const mod = createUndoRedoModule({
        getBlocks: () => _blocks,
        getConnections: () => _conns,
        setBlocks: (b) => { _blocks = b; },
        setConnections: (c) => { _conns = c; },
        getSelectedBlockId: () => _selectedId,
        setSelectedBlockId: (id) => { _selectedId = id; },
        ...mocks
    });

    return { mod, mocks, getBlocks: () => _blocks, getConns: () => _conns, getSelectedId: () => _selectedId };
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('createUndoRedoModule', () => {
    it('returns all expected public methods', () => {
        const { mod } = setup();
        expect(typeof mod.pushUndo).toBe('function');
        expect(typeof mod.undo).toBe('function');
        expect(typeof mod.redo).toBe('function');
        expect(typeof mod.updateUndoRedoButtons).toBe('function');
        expect(typeof mod.deleteSelected).toBe('function');
        expect(typeof mod.duplicateSelected).toBe('function');
        expect(typeof mod.alignBlocks).toBe('function');
        expect(typeof mod.autoLayout).toBe('function');
        expect(typeof mod.getStateSnapshot).toBe('function');
        expect(typeof mod.restoreStateSnapshot).toBe('function');
        expect(typeof mod.getUndoStackDepth).toBe('function');
        expect(typeof mod.getRedoStackDepth).toBe('function');
    });
});

// ── getStateSnapshot ──────────────────────────────────────────────────────────

describe('getStateSnapshot', () => {
    it('captures deep clone of blocks and connections', () => {
        const b = makeBlock();
        const c = makeConn(b.id, 'main_strategy');
        const { mod, getBlocks, getConns } = setup({ blocks: [b], connections: [c] });

        const snap = mod.getStateSnapshot();

        expect(snap.blocks).toHaveLength(1);
        expect(snap.connections).toHaveLength(1);
        expect(snap.blocks).not.toBe(getBlocks()); // deep clone
        expect(snap.connections).not.toBe(getConns());
    });

    it('snapshot is independent from subsequent mutations', () => {
        const b = makeBlock({ params: { period: 14 } });
        const { mod, getBlocks } = setup({ blocks: [b] });
        const snap = mod.getStateSnapshot();

        // Mutate the live block
        getBlocks()[0].params.period = 99;

        expect(snap.blocks[0].params.period).toBe(14); // clone unaffected
    });
});

// ── pushUndo / stack depths ───────────────────────────────────────────────────

describe('pushUndo', () => {
    it('increments undo stack depth', () => {
        const { mod } = setup({ blocks: [makeBlock()] });
        expect(mod.getUndoStackDepth()).toBe(0);
        mod.pushUndo();
        expect(mod.getUndoStackDepth()).toBe(1);
        mod.pushUndo();
        expect(mod.getUndoStackDepth()).toBe(2);
    });

    it('clears redo stack on new push', () => {
        const b = makeBlock();
        const { mod } = setup({ blocks: [b] });
        mod.pushUndo();
        // Simulate undo so redo stack has entry
        mod.undo();
        expect(mod.getRedoStackDepth()).toBe(1);
        // Now push again
        mod.pushUndo();
        expect(mod.getRedoStackDepth()).toBe(0);
    });

    it('caps undo stack at MAX_UNDO_HISTORY (50)', () => {
        const { mod } = setup({ blocks: [makeBlock()] });
        for (let i = 0; i < 60; i++) mod.pushUndo();
        expect(mod.getUndoStackDepth()).toBe(50);
    });
});

// ── undo / redo ───────────────────────────────────────────────────────────────

describe('undo', () => {
    it('restores previous state and calls renderBlocks', () => {
        const b = makeBlock();
        const { mod, mocks, getBlocks } = setup({ blocks: [b] });

        mod.pushUndo(); // snapshot: [b]
        // Add another block to "current" state
        getBlocks().push(makeBlock());
        expect(getBlocks()).toHaveLength(2);

        mod.undo();

        expect(getBlocks()).toHaveLength(1);
        expect(mocks.renderBlocks).toHaveBeenCalled();
    });

    it('shows notification after undo', () => {
        const { mod, mocks } = setup({ blocks: [makeBlock()] });
        mod.pushUndo();
        mod.undo();
        expect(mocks.showNotification).toHaveBeenCalledWith(
            expect.stringContaining('Отмена'),
            'info'
        );
    });

    it('does nothing when undo stack is empty', () => {
        const { mod, mocks } = setup({ blocks: [makeBlock()] });
        mod.undo();
        expect(mocks.renderBlocks).not.toHaveBeenCalled();
    });

    it('moves state to redo stack after undo', () => {
        const { mod } = setup({ blocks: [makeBlock()] });
        mod.pushUndo();
        mod.undo();
        expect(mod.getRedoStackDepth()).toBe(1);
    });
});

describe('redo', () => {
    it('re-applies the undone state and calls renderBlocks', () => {
        const b = makeBlock();
        const { mod, mocks, getBlocks } = setup({ blocks: [b] });

        mod.pushUndo();               // snap0: [b]  — goes to undo stack
        getBlocks().push(makeBlock()); // _blocks = [b, b2]
        mod.undo();                    // pops snap0=[b], restores to [b]; pushes current [b,b2] to redo
        expect(getBlocks()).toHaveLength(1);

        mod.redo();                    // pops redo entry [b,b2], restores to [b,b2]
        expect(getBlocks()).toHaveLength(2);
        expect(mocks.renderBlocks).toHaveBeenCalled();
    });

    it('shows notification after redo', () => {
        const { mod, mocks } = setup({ blocks: [makeBlock()] });
        mod.pushUndo();
        mod.undo();
        mocks.showNotification.mockClear();
        mod.redo();
        expect(mocks.showNotification).toHaveBeenCalledWith(
            expect.stringContaining('Повтор'),
            'info'
        );
    });

    it('does nothing when redo stack is empty', () => {
        const { mod, mocks } = setup({ blocks: [makeBlock()] });
        mod.redo();
        expect(mocks.renderBlocks).not.toHaveBeenCalled();
    });
});

// ── restoreStateSnapshot ──────────────────────────────────────────────────────

describe('restoreStateSnapshot', () => {
    it('ignores snapshots without blocks', () => {
        const { mod, mocks } = setup({ blocks: [makeBlock()] });
        mod.restoreStateSnapshot({});
        mod.restoreStateSnapshot(null);
        expect(mocks.renderBlocks).not.toHaveBeenCalled();
    });

    it('clears selectedBlockId if selection no longer exists', () => {
        const b = makeBlock();
        let _selectedId = b.id;
        const mod = createUndoRedoModule({
            getBlocks: () => [b],
            getConnections: () => [],
            setBlocks: vi.fn(),
            setConnections: vi.fn(),
            getSelectedBlockId: () => _selectedId,
            setSelectedBlockId: (id) => { _selectedId = id; },
            renderBlocks: vi.fn(),
            renderBlockProperties: vi.fn(),
            dispatchBlocksChanged: vi.fn(),
            validateStrategy: vi.fn().mockResolvedValue(undefined),
            showNotification: vi.fn(),
            selectBlock: vi.fn(),
            setLastAutoSavePayload: vi.fn()
        });

        // Restore to a snapshot with no blocks — selection should clear
        mod.restoreStateSnapshot({ blocks: [], connections: [] });
        expect(_selectedId).toBeNull();
    });

    it('resets lastAutoSavePayload to null', () => {
        const { mod, mocks } = setup({ blocks: [makeBlock()] });
        mod.restoreStateSnapshot({ blocks: [makeBlock()], connections: [] });
        expect(mocks.setLastAutoSavePayload).toHaveBeenCalledWith(null);
    });

    it('calls dispatchBlocksChanged after restore', () => {
        const { mod, mocks } = setup({ blocks: [makeBlock()] });
        mod.restoreStateSnapshot({ blocks: [makeBlock()], connections: [] });
        expect(mocks.dispatchBlocksChanged).toHaveBeenCalled();
    });
});

// ── deleteSelected ────────────────────────────────────────────────────────────

describe('deleteSelected', () => {
    it('removes selected block and its connections', () => {
        const main = makeMainBlock();
        const b = makeBlock();
        const c = makeConn(b.id, main.id);
        let _selectedId = b.id;
        let _blocks = [main, b];
        let _conns = [c];

        const mod = createUndoRedoModule({
            getBlocks: () => _blocks,
            getConnections: () => _conns,
            setBlocks: (arr) => { _blocks = arr; },
            setConnections: (arr) => { _conns = arr; },
            getSelectedBlockId: () => _selectedId,
            setSelectedBlockId: (id) => { _selectedId = id; },
            renderBlocks: vi.fn(),
            renderBlockProperties: vi.fn(),
            dispatchBlocksChanged: vi.fn(),
            validateStrategy: vi.fn().mockResolvedValue(undefined),
            showNotification: vi.fn(),
            selectBlock: vi.fn(),
            setLastAutoSavePayload: vi.fn()
        });

        mod.deleteSelected();

        expect(_blocks.find(bl => bl.id === b.id)).toBeUndefined();
        expect(_conns).toHaveLength(0);
        expect(_selectedId).toBeNull();
    });

    it('does not delete the main strategy node', () => {
        const main = makeMainBlock();
        const _selectedId = main.id;
        let _blocks = [main];

        const mod = createUndoRedoModule({
            getBlocks: () => _blocks,
            getConnections: () => [],
            setBlocks: (arr) => { _blocks = arr; },
            setConnections: vi.fn(),
            getSelectedBlockId: () => _selectedId,
            setSelectedBlockId: vi.fn(),
            renderBlocks: vi.fn(),
            renderBlockProperties: vi.fn(),
            dispatchBlocksChanged: vi.fn(),
            validateStrategy: vi.fn().mockResolvedValue(undefined),
            showNotification: vi.fn(),
            selectBlock: vi.fn(),
            setLastAutoSavePayload: vi.fn()
        });

        mod.deleteSelected();
        expect(_blocks).toHaveLength(1); // main still there
    });

    it('does nothing when no block is selected', () => {
        const { mod, mocks } = setup({ blocks: [makeBlock()] });
        // No selection set
        mod.deleteSelected();
        expect(mocks.renderBlocks).not.toHaveBeenCalled();
    });
});

// ── duplicateSelected ─────────────────────────────────────────────────────────

describe('duplicateSelected', () => {
    it('creates a copy of the selected block with offset position', () => {
        const b = makeBlock({ x: 50, y: 80 });
        let _blocks = [b];
        let _selectedId = b.id;

        const mod = createUndoRedoModule({
            getBlocks: () => _blocks,
            getConnections: () => [],
            setBlocks: (arr) => { _blocks = arr; },
            setConnections: vi.fn(),
            getSelectedBlockId: () => _selectedId,
            setSelectedBlockId: (id) => { _selectedId = id; },
            renderBlocks: vi.fn(),
            renderBlockProperties: vi.fn(),
            dispatchBlocksChanged: vi.fn(),
            validateStrategy: vi.fn().mockResolvedValue(undefined),
            showNotification: vi.fn(),
            selectBlock: vi.fn((id) => { _selectedId = id; }),
            setLastAutoSavePayload: vi.fn()
        });

        mod.duplicateSelected();

        expect(_blocks).toHaveLength(2);
        const dup = _blocks[1];
        expect(dup.id).not.toBe(b.id);
        expect(dup.x).toBe(b.x + 30);
        expect(dup.y).toBe(b.y + 30);
        expect(dup.isMain).toBe(false);
        expect(dup.params).toEqual(b.params);
    });

    it('does not duplicate main block', () => {
        const main = makeMainBlock();
        let _blocks = [main];
        const _selectedId = main.id;

        const mod = createUndoRedoModule({
            getBlocks: () => _blocks,
            getConnections: () => [],
            setBlocks: (arr) => { _blocks = arr; },
            setConnections: vi.fn(),
            getSelectedBlockId: () => _selectedId,
            setSelectedBlockId: vi.fn(),
            renderBlocks: vi.fn(),
            renderBlockProperties: vi.fn(),
            dispatchBlocksChanged: vi.fn(),
            validateStrategy: vi.fn().mockResolvedValue(undefined),
            showNotification: vi.fn(),
            selectBlock: vi.fn(),
            setLastAutoSavePayload: vi.fn()
        });

        mod.duplicateSelected();
        expect(_blocks).toHaveLength(1);
    });

    it('does nothing when no block is selected', () => {
        const { mod, mocks } = setup({ blocks: [makeBlock()] });
        mod.duplicateSelected();
        expect(mocks.renderBlocks).not.toHaveBeenCalled();
    });
});

// ── alignBlocks / autoLayout ──────────────────────────────────────────────────

describe('alignBlocks', () => {
    it('runs without error for any direction string', () => {
        const { mod } = setup();
        expect(() => mod.alignBlocks('left')).not.toThrow();
        expect(() => mod.alignBlocks('right')).not.toThrow();
        expect(() => mod.alignBlocks('center')).not.toThrow();
    });
});

describe('autoLayout', () => {
    it('runs without error', () => {
        const { mod } = setup();
        expect(() => mod.autoLayout()).not.toThrow();
    });
});

// ── updateUndoRedoButtons ─────────────────────────────────────────────────────

describe('updateUndoRedoButtons', () => {
    it('runs without error when buttons are not in DOM', () => {
        const { mod } = setup();
        expect(() => mod.updateUndoRedoButtons()).not.toThrow();
    });
});
