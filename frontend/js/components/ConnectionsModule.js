/**
 * ConnectionsModule.js — SVG connection system for Strategy Builder canvas.
 *
 * Extracted from strategy_builder.js during P0-1 refactoring (2026-02-26).
 *
 * Responsibilities:
 *   - initConnectionSystem()   — sets up mouse event delegation on canvas
 *   - startConnection()        — begin drag from a port
 *   - completeConnection()     — finalise when released on compatible port
 *   - cancelConnection()       — abort in-progress drag
 *   - renderConnections()      — draw all SVG bezier lines
 *   - normalizeConnection()    — normalise 3 backend formats → canonical
 *   - normalizeAllConnections() — normalise all in-place after API load
 *   - deleteConnection()       — remove by ID
 *   - disconnectPort()         — remove all connections to/from a port
 *   - tryAutoSnapConnection()  — auto-connect nearby compatible ports on drop
 *   - highlightCompatiblePorts() / clearPortHighlights()
 *   - createBezierPath()       — pure SVG path helper
 *   - getPreferredStrategyPort() — config block → preferred Strategy port
 *
 * Usage:
 *   import { createConnectionsModule } from './ConnectionsModule.js';
 *   const conn = createConnectionsModule({ getBlocks, getConnections, pushUndo,
 *                                          showNotification, renderBlocks });
 *   conn.initConnectionSystem();
 */

/**
 * Map config block types to their preferred Strategy node target port.
 * SL/TP blocks → sl_tp, Close conditions → close_cond, DCA/Grid → dca_grid.
 */
const CONFIG_BLOCK_TARGET_PORT = {
    // SL/TP blocks → sl_tp port
    static_sltp: 'sl_tp',
    trailing_stop_exit: 'sl_tp',
    atr_exit: 'sl_tp',
    multi_tp_exit: 'sl_tp',
    // Close condition blocks → close_cond port
    close_by_time: 'close_cond',
    close_channel: 'close_cond',
    close_ma_cross: 'close_cond',
    close_rsi: 'close_cond',
    close_stochastic: 'close_cond',
    close_psar: 'close_cond',
    // DCA/Grid blocks → dca_grid port
    dca: 'dca_grid',
    grid_orders: 'dca_grid'
};

/**
 * @param {Object} deps
 * @param {() => Object[]}  deps.getBlocks         - getter for strategyBlocks array
 * @param {() => Object[]}  deps.getConnections     - getter for connections array
 * @param {(conn: Object) => void} deps.addConnection   - push a new connection
 * @param {(id: string) => void}   deps.removeConnection - remove connection by id
 * @param {() => void}             deps.pushUndo      - snapshot for undo
 * @param {(msg: string, type?: string) => void} deps.showNotification
 * @param {() => void}             deps.renderBlocks  - re-render blocks + ports
 * @returns {Object} public API
 */
export function createConnectionsModule(deps) {
    const {
        getBlocks,
        getConnections,
        addConnection,
        removeConnection,
        pushUndo,
        showNotification,
        renderBlocks,
        getZoom = () => 1
    } = deps;

    // ── Module state ──────────────────────────────────────────────────────────
    let _isConnecting = false;
    let _connectionStart = null;
    let _tempLine = null;
    let _diagDone = false; // reset each renderConnections call for zoom diag

    // ── Getters (used by strategy_builder.js shim) ────────────────────────────
    function getIsConnecting() { return _isConnecting; }
    function getConnectionStart() { return _connectionStart; }

    // ── getPreferredStrategyPort ──────────────────────────────────────────────
    function getPreferredStrategyPort(blockType) {
        return CONFIG_BLOCK_TARGET_PORT[blockType] || null;
    }

    // ── initConnectionSystem ──────────────────────────────────────────────────
    function initConnectionSystem() {
        const container = document.getElementById('canvasContainer');
        if (!container) return;

        // Port mousedown — start connection drag
        container.addEventListener('mousedown', (e) => {
            const port = e.target.closest('.port');
            if (port) {
                e.stopPropagation();
                startConnection(port, e);
            }
        });

        // Right-click on port → disconnect; right-click on line → delete
        container.addEventListener('contextmenu', (e) => {
            const port = e.target.closest('.port');
            if (port) {
                e.preventDefault();
                e.stopPropagation();
                disconnectPort(port);
                return;
            }
            const connLine = e.target.closest('.connection-line');
            if (connLine && connLine.dataset.connectionId) {
                e.preventDefault();
                e.stopPropagation();
                deleteConnection(connLine.dataset.connectionId);
            }
        });

        // Left-click on connection line → delete
        container.addEventListener('click', (e) => {
            const connLine = e.target.closest('.connection-line:not(.temp)');
            if (connLine && connLine.dataset.connectionId) {
                deleteConnection(connLine.dataset.connectionId);
            }
        });

        // Mouse move during drag
        container.addEventListener('mousemove', (e) => {
            if (_isConnecting) updateTempConnection(e);
        });

        // Mouse up → complete or cancel
        container.addEventListener('mouseup', (e) => {
            if (_isConnecting) {
                const port = e.target.closest('.port');
                if (port && port !== _connectionStart.element) {
                    completeConnection(port);
                } else {
                    cancelConnection();
                }
            }
        });
    }

    // ── startConnection ───────────────────────────────────────────────────────
    function startConnection(portElement, _event) {
        _isConnecting = true;
        const zoom = getZoom();
        const rect = portElement.getBoundingClientRect();
        const containerRect = document.getElementById('canvasContainer').getBoundingClientRect();

        _connectionStart = {
            element: portElement,
            blockId: portElement.dataset.blockId,
            portId: portElement.dataset.portId,
            portType: portElement.dataset.portType,
            direction: portElement.dataset.direction,
            x: (rect.left + rect.width / 2 - containerRect.left) / zoom,
            y: (rect.top + rect.height / 2 - containerRect.top) / zoom
        };

        const svg = document.getElementById('connectionsCanvas');
        _tempLine = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        _tempLine.classList.add('connection-line', 'temp');
        svg.appendChild(_tempLine);

        portElement.classList.add('connecting');
        highlightCompatiblePorts(_connectionStart);
    }

    // ── highlightCompatiblePorts ──────────────────────────────────────────────
    function highlightCompatiblePorts(startInfo) {
        const allPorts = document.querySelectorAll('.port');
        const compatibleType = startInfo.portType;
        const oppositeDirection = startInfo.direction === 'output' ? 'input' : 'output';

        let preferredTargetPortId = null;
        if (compatibleType === 'config') {
            const sourceBlock = getBlocks().find(b => b.id === startInfo.blockId);
            if (sourceBlock) preferredTargetPortId = getPreferredStrategyPort(sourceBlock.type);
        }

        allPorts.forEach(port => {
            if (port === startInfo.element) return;

            const portType = port.dataset.portType;
            const portDirection = port.dataset.direction;
            const portBlockId = port.dataset.blockId;
            const portId = port.dataset.portId;

            let isCompatible =
                portType === compatibleType &&
                portDirection === oppositeDirection &&
                portBlockId !== startInfo.blockId;

            if (isCompatible && compatibleType === 'config' && preferredTargetPortId) {
                const targetBlock = getBlocks().find(b => b.id === portBlockId);
                if (targetBlock && targetBlock.isMain) {
                    isCompatible = (portId === preferredTargetPortId);
                }
            }

            port.classList.toggle('port-compatible', isCompatible);
            port.classList.toggle('port-incompatible', !isCompatible);
        });
    }

    // ── clearPortHighlights ───────────────────────────────────────────────────
    function clearPortHighlights() {
        document.querySelectorAll('.port').forEach(port => {
            port.classList.remove('port-compatible', 'port-incompatible');
        });
    }

    // ── updateTempConnection ──────────────────────────────────────────────────
    function updateTempConnection(event) {
        if (!_tempLine || !_connectionStart) return;
        const zoom = getZoom();
        const containerRect = document.getElementById('canvasContainer').getBoundingClientRect();
        const endX = (event.clientX - containerRect.left) / zoom;
        const endY = (event.clientY - containerRect.top) / zoom;
        const path = createBezierPath(
            _connectionStart.x, _connectionStart.y, endX, endY,
            _connectionStart.direction === 'output'
        );
        _tempLine.setAttribute('d', path);
    }

    // ── completeConnection ────────────────────────────────────────────────────
    function completeConnection(endPortElement) {
        const endDirection = endPortElement.dataset.direction;

        if (_connectionStart.direction === endDirection) { cancelConnection(); return; }
        if (_connectionStart.blockId === endPortElement.dataset.blockId) { cancelConnection(); return; }

        const startType = _connectionStart.portType;
        const endType = endPortElement.dataset.portType;
        if (startType !== endType) {
            cancelConnection();
            showNotification('Несовместимые типы портов', 'error');
            return;
        }

        let source, target;
        if (_connectionStart.direction === 'output') {
            source = { blockId: _connectionStart.blockId, portId: _connectionStart.portId };
            target = { blockId: endPortElement.dataset.blockId, portId: endPortElement.dataset.portId };
        } else {
            source = { blockId: endPortElement.dataset.blockId, portId: endPortElement.dataset.portId };
            target = { blockId: _connectionStart.blockId, portId: _connectionStart.portId };
        }

        // Smart config redirect
        if (startType === 'config') {
            const sourceBlock = getBlocks().find(b => b.id === source.blockId);
            const targetBlock = getBlocks().find(b => b.id === target.blockId);
            if (sourceBlock && targetBlock?.isMain) {
                const preferred = getPreferredStrategyPort(sourceBlock.type);
                if (preferred) target.portId = preferred;
            }
        }

        const connections = getConnections();
        const exists = connections.some(
            c =>
                c.source.blockId === source.blockId &&
                c.source.portId === source.portId &&
                c.target.blockId === target.blockId &&
                c.target.portId === target.portId
        );

        if (!exists) {
            pushUndo();
            addConnection({
                id: `conn_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
                source,
                target,
                type: startType
            });
        }

        cancelConnection();
        renderConnections();
    }

    // ── cancelConnection ──────────────────────────────────────────────────────
    function cancelConnection() {
        _isConnecting = false;
        if (_tempLine) { _tempLine.remove(); _tempLine = null; }
        if (_connectionStart?.element) _connectionStart.element.classList.remove('connecting');
        _connectionStart = null;
        clearPortHighlights();
    }

    // ── normalizeConnection ───────────────────────────────────────────────────
    function normalizeConnection(conn) {
        // Already canonical
        if (conn.source && typeof conn.source === 'object' && conn.source.blockId) {
            return {
                id: conn.id || `conn_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
                source: { blockId: conn.source.blockId, portId: conn.source.portId || 'out' },
                target: { blockId: conn.target.blockId, portId: conn.target.portId || 'in' },
                type: conn.type || 'data'
            };
        }
        // Format: { source_block, source_output, target_block, target_input }
        if (conn.source_block && conn.target_block) {
            return {
                id: conn.id || `conn_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
                source: { blockId: conn.source_block, portId: conn.source_output || 'out' },
                target: { blockId: conn.target_block, portId: conn.target_input || 'in' },
                type: conn.type || 'data'
            };
        }
        // Format: { from, fromPort, to, toPort } — used by GraphConverter (AI pipeline)
        // or { from, to } — legacy minimal format
        if (conn.from && conn.to) {
            return {
                id: conn.id || `conn_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
                source: { blockId: conn.from, portId: conn.fromPort || 'out' },
                target: { blockId: conn.to, portId: conn.toPort || 'in' },
                type: conn.type || 'data'
            };
        }
        console.warn('[Connections] Unknown connection format:', conn);
        return {
            id: conn.id || `conn_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
            source: { blockId: conn.source || '', portId: 'out' },
            target: { blockId: conn.target || '', portId: 'in' },
            type: conn.type || 'data'
        };
    }

    // ── normalizeAllConnections ───────────────────────────────────────────────
    function normalizeAllConnections() {
        const connections = getConnections();
        for (let i = 0; i < connections.length; i++) {
            connections[i] = normalizeConnection(connections[i]);
        }
    }

    // ── _getPortCentre* ───────────────────────────────────────────────────────
    // Walk the offsetParent chain from a port element up to (but not including)
    // ── renderConnections ─────────────────────────────────────────────────────
    function renderConnections() {
        const svg = document.getElementById('connectionsCanvas');
        if (!svg) return;

        _diagDone = false; // reset so first wire of THIS render is logged

        // Remove all non-temp wires AND their pulse overlays
        svg.querySelectorAll('.connection-line:not(.temp), .wire-pulse').forEach(el => el.remove());

        const connections = getConnections();
        connections.forEach(conn => {
            const sourceBlock = document.getElementById(conn.source.blockId);
            const targetBlock = document.getElementById(conn.target.blockId);

            if (!sourceBlock || !targetBlock) {
                console.warn('[renderConnections] Block not found:', {
                    sourceBlockId: conn.source.blockId, targetBlockId: conn.target.blockId,
                    sourceFound: !!sourceBlock, targetFound: !!targetBlock
                });
                return;
            }

            // Port name aliases: AI pipeline generates names like "filter_long" but
            // blocks render ports as "long". Fall back to the base signal name.
            const PORT_FALLBACKS = {
                'filter_long': ['long', 'bullish', 'buy', 'value', 'out'],
                'filter_short': ['short', 'bearish', 'sell', 'value', 'out'],
                'entry_long': ['long', 'bullish', 'buy', 'out'],
                'entry_short': ['short', 'bearish', 'sell', 'out'],
                // AI pipeline uses "sl_tp" as source port name on config blocks,
                // but those blocks render a generic "config" output port.
                'sl_tp': ['config', 'out', 'value'],
                'close_cond': ['config', 'out', 'value'],
                'dca_grid': ['config', 'out', 'value'],
                // When source port is "long" but block only has band ports (donchian, bollinger, etc.)
                'long': ['out', 'upper', 'value', 'signal'],
                'short': ['out', 'lower', 'value', 'signal']
            };

            function findPort(block, portId, direction) {
                let el = block.querySelector(
                    `[data-port-id="${portId}"][data-direction="${direction}"]`
                );
                if (el) return el;
                const fallbacks = PORT_FALLBACKS[portId] || [];
                for (const alias of fallbacks) {
                    el = block.querySelector(
                        `[data-port-id="${alias}"][data-direction="${direction}"]`
                    );
                    if (el) return el;
                }
                return null;
            }

            const sourcePort = findPort(sourceBlock, conn.source.portId, 'output');
            const targetPort = findPort(targetBlock, conn.target.portId, 'input');

            if (!sourcePort || !targetPort) {
                console.error('[renderConnections] ❌ Invisible connection — port missing in DOM:', {
                    connection: `${conn.source.blockId}.${conn.source.portId} → ${conn.target.blockId}.${conn.target.portId}`,
                    sourcePortFound: !!sourcePort, targetPortFound: !!targetPort,
                    availableSourcePorts: Array.from(
                        sourceBlock.querySelectorAll('[data-direction="output"]')
                    ).map(p => p.dataset.portId),
                    availableTargetPorts: Array.from(
                        targetBlock.querySelectorAll('[data-direction="input"]')
                    ).map(p => p.dataset.portId)
                });
                // Mark block visually so user knows there's an invisible connection
                const badBlock = !sourcePort ? sourceBlock : targetBlock;
                badBlock.classList.add('has-invisible-connection');
                return;
            }

            // SVG is NOT scaled — it draws in native canvasContainer pixels.
            // getBoundingClientRect() returns screen-space (CSS-scaled) coords.
            // Dividing by zoom converts them to SVG logical coordinates.
            const zoom = getZoom();
            const containerRect = document.getElementById('canvasContainer').getBoundingClientRect();
            const sourceRect = sourcePort.getBoundingClientRect();
            const targetRect = targetPort.getBoundingClientRect();

            const startX = (sourceRect.left + sourceRect.width / 2 - containerRect.left) / zoom;
            const startY = (sourceRect.top + sourceRect.height / 2 - containerRect.top) / zoom;
            const endX = (targetRect.left + targetRect.width / 2 - containerRect.left) / zoom;
            const endY = (targetRect.top + targetRect.height / 2 - containerRect.top) / zoom;

            // ── Diagnostic (first wire of every render) ──────────────────────
            if (!_diagDone) {
                _diagDone = true;
                console.log('[ConnDiag] zoom:', zoom,
                    '\n  containerRect:', Math.round(containerRect.left), Math.round(containerRect.top), Math.round(containerRect.width), 'x', Math.round(containerRect.height),
                    '\n  sourcePort screen left/top:', Math.round(sourceRect.left), Math.round(sourceRect.top),
                    '\n  raw offset (before /zoom):', Math.round(sourceRect.left - containerRect.left), Math.round(sourceRect.top - containerRect.top),
                    '\n  SVG startX/startY:', Math.round(startX), Math.round(startY),
                    '\n  SVG endX/endY:', Math.round(endX), Math.round(endY));
            }

            const bezierD = createBezierPath(startX, startY, endX, endY, true);

            // ── Base (dim) wire ──────────────────────────────────────────────
            const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            path.classList.add('connection-line', conn.type);

            // Per-config-port colour
            if (conn.type === 'config') {
                const tPortId = conn.target.portId;
                if (tPortId === 'sl_tp') path.classList.add('config-sltp');
                else if (tPortId === 'close_cond') path.classList.add('config-close');
                else if (tPortId === 'dca_grid') path.classList.add('config-dca');

            }

            // Direction-mismatch detection
            const direction = document.getElementById('builderDirection')?.value || 'both';
            const targetPortId = conn.target.portId;
            const sourcePortId = conn.source.portId;
            const isLongTarget = targetPortId === 'entry_long' || targetPortId === 'exit_long';
            const isShortTarget = targetPortId === 'entry_short' || targetPortId === 'exit_short';
            const isLongSource = sourcePortId === 'long' || sourcePortId === 'bullish';
            const isShortSource = sourcePortId === 'short' || sourcePortId === 'bearish';

            const isMismatch =
                (direction === 'long' && isShortTarget) ||
                (direction === 'short' && isLongTarget) ||
                (isLongSource && isShortTarget) ||
                (isShortSource && isLongTarget);

            if (isMismatch) {
                path.classList.add('direction-mismatch');
                const titleEl = document.createElementNS('http://www.w3.org/2000/svg', 'title');
                if (direction !== 'both' && (isLongTarget || isShortTarget)) {
                    const portDir = isLongTarget ? 'Long' : 'Short';
                    const selDir = direction === 'long' ? 'Long' : 'Short';
                    titleEl.textContent = `⚠ Несоответствие: направление "${selDir}", но провод подключён к "${portDir}" порту`;
                } else {
                    titleEl.textContent = `⚠ Несоответствие: сигнал "${sourcePortId}" подключён к "${targetPortId}" порту`;
                }
                path.appendChild(titleEl);
            }

            // ── Validation-error wire (red) when source or target block is invalid ──
            if (!isMismatch) {
                const sourceInvalid = sourceBlock.classList.contains('block-invalid');
                const targetInvalid = targetBlock.classList.contains('block-invalid');
                if (sourceInvalid || targetInvalid) {
                    path.classList.add('validation-error-wire');
                    const titleEl = document.createElementNS('http://www.w3.org/2000/svg', 'title');
                    const badName = sourceInvalid
                        ? (sourceBlock.querySelector('.block-title')?.textContent || conn.source.blockId)
                        : (targetBlock.querySelector('.block-title')?.textContent || conn.target.blockId);
                    titleEl.textContent = `⚠ Блок "${badName}" содержит ошибку валидации`;
                    path.appendChild(titleEl);
                }
            }

            path.setAttribute('d', bezierD);
            path.dataset.connectionId = conn.id;
            svg.appendChild(path);

            sourcePort.classList.add('connected');
            targetPort.classList.add('connected');

            // ── Signal-pulse overlay (skip for mismatch — it has its own anim) ──
            if (!isMismatch) {
                _appendWirePulse(svg, bezierD, path.classList);
            }
        });
    }

    /**
     * Appends a glowing pulse <path> that travels along the same bezier curve.
     * Uses getTotalLength() so the pulse always follows the exact wire shape
     * regardless of length or curvature, and the animation never freezes.
     *
     * @param {SVGSVGElement} svg
     * @param {string}        bezierD   - SVG "d" attribute string
     * @param {DOMTokenList}  baseClasses - classList of the base wire (to copy type)
     */
    function _appendWirePulse(svg, bezierD, baseClasses) {
        const pulse = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        pulse.classList.add('wire-pulse');

        // Copy type/colour classes from the base wire
        const typeClasses = ['data', 'flow', 'condition', 'config',
            'config-sltp', 'config-close', 'config-dca'];
        typeClasses.forEach(cls => {
            if (baseClasses.contains(cls)) pulse.classList.add(cls);
        });

        pulse.setAttribute('d', bezierD);

        // Add to DOM first so getTotalLength() returns a real value
        svg.appendChild(pulse);

        const totalLen = pulse.getTotalLength();
        if (totalLen < 1) { pulse.remove(); return; }

        // Pulse segment = ~8% of wire length, clamped to 12–40px (thin needle)
        const pulseLen = Math.min(40, Math.max(12, totalLen * 0.08));
        // gap fills the rest so only one needle is visible per loop
        const gap = totalLen - pulseLen;

        // Set dasharray once — one thin bright needle + long invisible gap
        pulse.style.strokeDasharray = `${pulseLen} ${gap}`;

        // Speed: constant ~60 px/s → very slow, smooth signal crawl
        const durationMs = Math.max(2000, (totalLen / 60) * 1000);

        // Web Animations API — from: segment is just past the end (off-screen right)
        //                       to:   segment has travelled past the start (off-screen left)
        // dashoffset positive = shift segment toward start, negative = toward end
        pulse.animate(
            [
                { strokeDashoffset: totalLen },           // start: pulse is off the far end
                { strokeDashoffset: -(totalLen - pulseLen + 4) }  // end: pulse exits the near end
            ],
            {
                duration: durationMs,
                iterations: Infinity,
                easing: 'linear'
            }
        );
    }

    // ── createBezierPath ──────────────────────────────────────────────────────
    function createBezierPath(x1, y1, x2, y2, fromOutput) {
        const dx = Math.abs(x2 - x1);
        const controlOffset = Math.max(50, dx * 0.5);
        if (fromOutput) {
            return `M ${x1} ${y1} C ${x1 + controlOffset} ${y1}, ${x2 - controlOffset} ${y2}, ${x2} ${y2}`;
        }
        return `M ${x1} ${y1} C ${x1 - controlOffset} ${y1}, ${x2 + controlOffset} ${y2}, ${x2} ${y2}`;
    }

    // ── deleteConnection ──────────────────────────────────────────────────────
    function deleteConnection(connectionId) {
        const connections = getConnections();
        const index = connections.findIndex(c => c.id === connectionId);
        if (index !== -1) {
            pushUndo();
            removeConnection(connectionId);
            renderBlocks();
        }
    }

    // ── disconnectPort ────────────────────────────────────────────────────────
    function disconnectPort(portElement) {
        const blockId = portElement.dataset.blockId;
        const portId = portElement.dataset.portId;
        const direction = portElement.dataset.direction;
        if (!blockId || !portId) return;

        const connections = getConnections();
        const toRemove = connections.filter(c => {
            if (direction === 'output') return c.source.blockId === blockId && c.source.portId === portId;
            return c.target.blockId === blockId && c.target.portId === portId;
        });

        if (toRemove.length === 0) return;

        pushUndo();
        toRemove.forEach(c => removeConnection(c.id));

        renderConnections();
        renderBlocks();
        console.log(`[Connections] Disconnected ${toRemove.length} connection(s) from port ${portId} on block ${blockId}`);
    }

    // ── tryAutoSnapConnection ─────────────────────────────────────────────────
    function tryAutoSnapConnection(droppedBlockId) {
        const droppedBlock = document.getElementById(droppedBlockId);
        if (!droppedBlock) return;

        const SNAP_DISTANCE = 50;
        const droppedPorts = droppedBlock.querySelectorAll('.port');
        const otherPorts = document.querySelectorAll(`.port:not([data-block-id="${droppedBlockId}"])`);

        let bestMatch = null;
        let bestDistance = SNAP_DISTANCE;

        droppedPorts.forEach(droppedPort => {
            const droppedRect = droppedPort.getBoundingClientRect();
            const droppedCenterX = droppedRect.left + droppedRect.width / 2;
            const droppedCenterY = droppedRect.top + droppedRect.height / 2;
            const droppedType = droppedPort.dataset.portType;
            const droppedDirection = droppedPort.dataset.direction;
            const droppedPortId = droppedPort.dataset.portId;

            otherPorts.forEach(otherPort => {
                const otherType = otherPort.dataset.portType;
                const otherDirection = otherPort.dataset.direction;
                const otherBlockId = otherPort.dataset.blockId;
                const otherPortId = otherPort.dataset.portId;

                if (otherType !== droppedType || otherDirection === droppedDirection) return;

                if (droppedType === 'config') {
                    const droppedBlockData = getBlocks().find(b => b.id === droppedBlockId);
                    const otherBlockData = getBlocks().find(b => b.id === otherBlockId);
                    if (droppedBlockData && otherBlockData?.isMain) {
                        const preferred = getPreferredStrategyPort(droppedBlockData.type);
                        if (preferred && otherPortId !== preferred) return;
                    }
                }

                const connections = getConnections();
                const alreadyConnected = connections.some(c => {
                    const matchesDropped =
                        (c.source.blockId === droppedBlockId && c.source.portId === droppedPortId) ||
                        (c.target.blockId === droppedBlockId && c.target.portId === droppedPortId);
                    const matchesOther =
                        (c.source.blockId === otherBlockId && c.source.portId === otherPortId) ||
                        (c.target.blockId === otherBlockId && c.target.portId === otherPortId);
                    return matchesDropped && matchesOther;
                });
                if (alreadyConnected) return;

                const otherRect = otherPort.getBoundingClientRect();
                const otherCenterX = otherRect.left + otherRect.width / 2;
                const otherCenterY = otherRect.top + otherRect.height / 2;
                const distance = Math.sqrt(
                    Math.pow(droppedCenterX - otherCenterX, 2) +
                    Math.pow(droppedCenterY - otherCenterY, 2)
                );

                if (distance < bestDistance) {
                    bestDistance = distance;
                    bestMatch = {
                        droppedPort: { blockId: droppedBlockId, portId: droppedPortId, direction: droppedDirection },
                        otherPort: { blockId: otherBlockId, portId: otherPortId, direction: otherDirection },
                        type: droppedType
                    };
                }
            });
        });

        if (bestMatch) {
            const source = bestMatch.droppedPort.direction === 'output' ? bestMatch.droppedPort : bestMatch.otherPort;
            const target = bestMatch.droppedPort.direction === 'output' ? bestMatch.otherPort : bestMatch.droppedPort;

            const connections = getConnections();
            const exists = connections.some(
                c =>
                    c.source.blockId === source.blockId && c.source.portId === source.portId &&
                    c.target.blockId === target.blockId && c.target.portId === target.portId
            );

            if (!exists) {
                pushUndo();
                addConnection({
                    id: `conn_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
                    source: { blockId: source.blockId, portId: source.portId },
                    target: { blockId: target.blockId, portId: target.portId },
                    type: bestMatch.type
                });
                showNotification('Соединение создано автоматически', 'success');
            }
        }
    }

    // ── Public API ────────────────────────────────────────────────────────────
    return {
        initConnectionSystem,
        startConnection,
        completeConnection,
        cancelConnection,
        updateTempConnection,
        renderConnections,
        normalizeConnection,
        normalizeAllConnections,
        deleteConnection,
        disconnectPort,
        tryAutoSnapConnection,
        highlightCompatiblePorts,
        clearPortHighlights,
        createBezierPath,
        getPreferredStrategyPort,
        // State getters needed by strategy_builder shim
        getIsConnecting,
        getConnectionStart
    };
}
