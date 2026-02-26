/**
 * 📦 UndoRedoModule
 *
 * Manages undo/redo history and block manipulation actions for the Strategy Builder canvas.
 * Extracted from strategy_builder.js during P0-1 refactoring.
 *
 * @module UndoRedoModule
 * @version 1.0.0
 * @date 2026-02-26
 */

const MAX_UNDO_HISTORY = 50;

/**
 * Create an UndoRedoModule instance.
 *
 * @param {object} deps
 * @param {function(): object[]} deps.getBlocks       - Returns current strategyBlocks array
 * @param {function(): object[]} deps.getConnections  - Returns current connections array
 * @param {function(object[]): void} deps.setBlocks   - Replaces strategyBlocks in state
 * @param {function(object[]): void} deps.setConnections - Replaces connections in state
 * @param {function(): string|null} deps.getSelectedBlockId  - Returns currently selected block ID
 * @param {function(string|null): void} deps.setSelectedBlockId - Sets selected block ID
 * @param {function(): void} deps.renderBlocks        - Re-renders all blocks (and connections)
 * @param {function(): void} deps.renderBlockProperties - Re-renders block properties panel
 * @param {function(): void} deps.dispatchBlocksChanged - Fires strategyBlocksChanged event
 * @param {function(): void} deps.validateStrategy    - Triggers strategy validation
 * @param {function(string, string): void} deps.showNotification - Shows a toast notification
 * @param {function(string): void} deps.selectBlock   - Selects a block by ID
 * @param {function(string|null): void} deps.setLastAutoSavePayload - Updates last autosave payload
 * @returns {object} Public API
 */
export function createUndoRedoModule({
    getBlocks,
    getConnections,
    setBlocks,
    setConnections,
    getSelectedBlockId,
    setSelectedBlockId,
    renderBlocks,
    renderBlockProperties,
    dispatchBlocksChanged,
    validateStrategy,
    showNotification,
    selectBlock,
    setLastAutoSavePayload
}) {
    const undoStack = [];
    const redoStack = [];

    // -----------------------------------------------
    // State snapshots
    // -----------------------------------------------

    /**
     * Capture a deep-clone of current blocks + connections.
     * @returns {{ blocks: object[], connections: object[] }}
     */
    function getStateSnapshot() {
        return {
            blocks: JSON.parse(JSON.stringify(getBlocks())),
            connections: JSON.parse(JSON.stringify(getConnections()))
        };
    }

    /**
     * Restore blocks + connections from a snapshot, then re-render.
     * @param {{ blocks: object[], connections: object[] }} snapshot
     */
    function restoreStateSnapshot(snapshot) {
        if (!snapshot?.blocks) return;

        const blocks = getBlocks();
        const conns = getConnections();

        blocks.length = 0;
        blocks.push(...snapshot.blocks);
        conns.length = 0;
        conns.push(...(snapshot.connections || []));

        setBlocks(blocks);
        setConnections(conns);

        const selId = getSelectedBlockId();
        if (selId && !blocks.some((b) => b.id === selId)) {
            setSelectedBlockId(null);
        }

        // Reset autosave payload so the restored state gets persisted
        setLastAutoSavePayload(null);

        renderBlocks(); // renderBlocks calls renderConnections() internally
        renderBlockProperties();
        dispatchBlocksChanged();

        // Re-validate if the validation panel is currently visible (BUG#11)
        const vp = document.querySelector('.validation-panel');
        if (vp && vp.classList.contains('visible')) {
            validateStrategy().catch((err) =>
                console.warn('[UndoRedoModule] Re-validate error:', err)
            );
        }
    }

    // -----------------------------------------------
    // Push / Undo / Redo
    // -----------------------------------------------

    /**
     * Save current state to the undo stack; clear redo stack.
     */
    function pushUndo() {
        const snapshot = getStateSnapshot();
        if (undoStack.length >= MAX_UNDO_HISTORY) undoStack.shift();
        undoStack.push(snapshot);
        redoStack.length = 0;
        updateUndoRedoButtons();
    }

    /**
     * Undo the last action.
     */
    function undo() {
        if (undoStack.length === 0) return;
        redoStack.push(getStateSnapshot());
        const prev = undoStack.pop();
        restoreStateSnapshot(prev);
        updateUndoRedoButtons();
        showNotification(`Отмена (осталось: ${undoStack.length})`, 'info');
    }

    /**
     * Redo the previously undone action.
     */
    function redo() {
        if (redoStack.length === 0) return;
        undoStack.push(getStateSnapshot());
        const next = redoStack.pop();
        restoreStateSnapshot(next);
        updateUndoRedoButtons();
        showNotification(`Повтор (осталось: ${redoStack.length})`, 'info');
    }

    /**
     * Update disabled state and tooltips for undo/redo toolbar buttons.
     */
    function updateUndoRedoButtons() {
        const undoBtn = document.querySelector('button[onclick="undo()"]');
        const redoBtn = document.querySelector('button[onclick="redo()"]');

        if (undoBtn) {
            undoBtn.disabled = undoStack.length === 0;
            undoBtn.title =
                undoStack.length > 0
                    ? `Отмена (${undoStack.length} шагов)`
                    : 'Отмена (нет действий)';
            undoBtn.classList.toggle('btn-disabled', undoStack.length === 0);
        }

        if (redoBtn) {
            redoBtn.disabled = redoStack.length === 0;
            redoBtn.title =
                redoStack.length > 0
                    ? `Повтор (${redoStack.length} шагов)`
                    : 'Повтор (нет действий)';
            redoBtn.classList.toggle('btn-disabled', redoStack.length === 0);
        }
    }

    // -----------------------------------------------
    // Block manipulation
    // -----------------------------------------------

    /**
     * Delete the currently selected block and its connections.
     */
    function deleteSelected() {
        const selectedBlockId = getSelectedBlockId();
        if (!selectedBlockId) return;

        const blocks = getBlocks();
        const block = blocks.find((b) => b.id === selectedBlockId);
        if (block && block.isMain) {
            console.log('[UndoRedoModule] Cannot delete main Strategy node');
            return;
        }

        pushUndo();

        const conns = getConnections();
        // Remove all connections involving this block
        const toRemove = conns.filter(
            (c) =>
                c.source.blockId === selectedBlockId ||
                c.target.blockId === selectedBlockId
        );
        toRemove.forEach((c) => {
            const idx = conns.indexOf(c);
            if (idx !== -1) conns.splice(idx, 1);
        });

        const newBlocks = blocks.filter((b) => b.id !== selectedBlockId);
        newBlocks.forEach((b, i) => { blocks[i] = b; });
        blocks.length = newBlocks.length;

        setBlocks(blocks);
        setConnections(conns);
        setSelectedBlockId(null);
        renderBlocks();
        renderBlockProperties();
    }

    /**
     * Duplicate the currently selected block (non-main blocks only).
     */
    function duplicateSelected() {
        const selectedBlockId = getSelectedBlockId();
        if (!selectedBlockId) return;

        const blocks = getBlocks();
        const block = blocks.find((b) => b.id === selectedBlockId);
        if (!block || block.isMain) return;

        pushUndo();
        const newBlock = {
            ...block,
            id: `block_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
            x: block.x + 30,
            y: block.y + 30,
            isMain: false,
            params: { ...block.params }
        };
        blocks.push(newBlock);
        setBlocks(blocks);
        renderBlocks();
        selectBlock(newBlock.id);
    }

    /**
     * Align selected blocks (stub — future feature).
     * @param {string} direction
     */
    function alignBlocks(direction) {
        console.log(`[UndoRedoModule] alignBlocks: ${direction}`);
    }

    /**
     * Auto-layout all blocks (stub — future feature).
     */
    function autoLayout() {
        console.log('[UndoRedoModule] autoLayout');
    }

    // -----------------------------------------------
    // Accessors (for testing and delegate wrappers)
    // -----------------------------------------------

    /**
     * Returns the current undo stack depth.
     * @returns {number}
     */
    function getUndoStackDepth() {
        return undoStack.length;
    }

    /**
     * Returns the current redo stack depth.
     * @returns {number}
     */
    function getRedoStackDepth() {
        return redoStack.length;
    }

    return {
        getStateSnapshot,
        restoreStateSnapshot,
        pushUndo,
        undo,
        redo,
        updateUndoRedoButtons,
        deleteSelected,
        duplicateSelected,
        alignBlocks,
        autoLayout,
        getUndoStackDepth,
        getRedoStackDepth
    };
}
