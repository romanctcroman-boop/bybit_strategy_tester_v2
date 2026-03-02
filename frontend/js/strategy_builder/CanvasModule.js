/**
 * Canvas Module — Управление canvas
 * 
 * Отрисовка, zoom, pan, marquee selection
 */

import { getStore } from '../core/StateManager.js';

const store = getStore();

export function createCanvasModule(canvas) {
  const ctx = canvas?.getContext('2d');
  
  // State
  let isDragging = false;
  let dragOffset = { x: 0, y: 0 };
  let zoom = 1;
  let isMarqueeSelecting = false;
  let marqueeStart = { x: 0, y: 0 };
  
  // Initialize from store
  function initialize() {
    if (!store) return;
    
    store.subscribe('strategyBuilder.viewport.zoom', (v) => { zoom = v ?? 1; });
    store.subscribe('strategyBuilder.viewport.isDragging', (v) => { isDragging = !!v; });
    store.subscribe('strategyBuilder.viewport.dragOffset', (v) => { dragOffset = v ?? { x: 0, y: 0 }; });
    store.subscribe('strategyBuilder.viewport.isMarqueeSelecting', (v) => { isMarqueeSelecting = !!v; });
    store.subscribe('strategyBuilder.viewport.marqueeStart', (v) => { marqueeStart = v ?? { x: 0, y: 0 }; });
  }
  
  // Render canvas
  function render(blocks, connections) {
    if (!ctx) return;
    
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // Apply transform
    ctx.save();
    ctx.translate(dragOffset.x, dragOffset.y);
    ctx.scale(zoom, zoom);
    
    // Draw grid
    drawGrid();
    
    // Draw connections
    connections.forEach(conn => drawConnection(conn));
    
    // Draw blocks
    blocks.forEach(block => drawBlock(block));
    
    // Draw marquee
    if (isMarqueeSelecting) {
      drawMarquee(marqueeStart);
    }
    
    ctx.restore();
  }
  
  function drawGrid() {
    const gridSize = 20;
    const width = canvas.width / zoom;
    const height = canvas.height / zoom;
    
    ctx.strokeStyle = '#e0e0e0';
    ctx.lineWidth = 1 / zoom;
    
    for (let x = 0; x < width; x += gridSize) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);
      ctx.stroke();
    }
    
    for (let y = 0; y < height; y += gridSize) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
    }
  }
  
  function drawConnection(connection) {
    const fromBlock = connection.from;
    const toBlock = connection.to;
    
    if (!fromBlock || !toBlock) return;
    
    ctx.strokeStyle = '#2196F3';
    ctx.lineWidth = 2 / zoom;
    ctx.beginPath();
    ctx.moveTo(fromBlock.x + fromBlock.width, fromBlock.y + fromBlock.height / 2);
    ctx.lineTo(toBlock.x, toBlock.y + toBlock.height / 2);
    ctx.stroke();
  }
  
  function drawBlock(block) {
    const { x, y, width, height, type, label } = block;
    
    // Background
    ctx.fillStyle = getTypeColor(type);
    ctx.fillRect(x, y, width, height);
    
    // Border
    ctx.strokeStyle = '#333';
    ctx.lineWidth = 1 / zoom;
    ctx.strokeRect(x, y, width, height);
    
    // Label
    ctx.fillStyle = '#fff';
    ctx.font = `${12 * zoom}px Arial`;
    ctx.fillText(label, x + 10, y + 20);
  }
  
  function drawMarquee(start) {
    const current = store.get('strategyBuilder.viewport.marqueeCurrent') || { x: 0, y: 0 };
    
    ctx.strokeStyle = '#2196F3';
    ctx.lineWidth = 1 / zoom;
    ctx.setLineDash([5, 5]);
    ctx.strokeRect(start.x, start.y, current.x - start.x, current.y - start.y);
    ctx.setLineDash([]);
  }
  
  function getTypeColor(type) {
    const colors = {
      'input': '#4CAF50',
      'indicator': '#2196F3',
      'condition': '#FF9800',
      'action': '#F44336',
      'exit': '#9C27B0'
    };
    return colors[type] || '#757575';
  }
  
  // Event handlers
  function handleMouseDown(e) {
    if (e.button === 1 || (e.button === 0 && e.altKey)) {
      isDragging = true;
      dragOffset = {
        x: e.clientX - dragOffset.x,
        y: e.clientY - dragOffset.y
      };
      store.set('strategyBuilder.viewport.isDragging', true);
      store.set('strategyBuilder.viewport.dragOffset', dragOffset);
    }
  }
  
  function handleMouseMove(e) {
    if (isDragging) {
      dragOffset = {
        x: e.clientX - dragOffset.x,
        y: e.clientY - dragOffset.y
      };
      store.set('strategyBuilder.viewport.dragOffset', dragOffset);
    }
    
    if (isMarqueeSelecting) {
      store.set('strategyBuilder.viewport.marqueeCurrent', { x: e.clientX, y: e.clientY });
    }
  }
  
  function handleMouseUp() {
    isDragging = false;
    isMarqueeSelecting = false;
    store.set('strategyBuilder.viewport.isDragging', false);
    store.set('strategyBuilder.viewport.isMarqueeSelecting', false);
  }
  
  function handleWheel(e) {
    e.preventDefault();
    const delta = e.deltaY < 0 ? 0.1 : -0.1;
    zoom = Math.max(0.1, Math.min(5, zoom + delta));
    store.set('strategyBuilder.viewport.zoom', zoom);
  }
  
  // Attach events
  function attachEvents() {
    if (!canvas) return;
    
    canvas.addEventListener('mousedown', handleMouseDown);
    canvas.addEventListener('mousemove', handleMouseMove);
    canvas.addEventListener('mouseup', handleMouseUp);
    canvas.addEventListener('wheel', handleWheel, { passive: false });
  }
  
  // Initialize
  initialize();
  attachEvents();
  
  return {
    render,
    getZoom: () => zoom,
    setZoom: (z) => { zoom = z; store.set('strategyBuilder.viewport.zoom', z); },
    getDragOffset: () => dragOffset,
    reset: () => {
      zoom = 1;
      dragOffset = { x: 0, y: 0 };
      store.set('strategyBuilder.viewport.zoom', 1);
      store.set('strategyBuilder.viewport.dragOffset', { x: 0, y: 0 });
    }
  };
}
