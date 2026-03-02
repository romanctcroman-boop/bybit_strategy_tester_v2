/**
 * Toolbar Module — Инструменты
 * 
 * Undo/Redo, Align, Auto Layout, Zoom controls
 */

import { getStore } from '../core/StateManager.js';

const store = getStore();

export function createToolbarModule(toolbarElement) {
  // State
  let canUndo = false;
  let canRedo = false;
  let currentTool = 'select';
  
  // Initialize from store
  function initialize() {
    if (!store) return;
    
    store.subscribe('strategyBuilder.history.canUndo', (v) => { canUndo = !!v; });
    store.subscribe('strategyBuilder.history.canRedo', (v) => { canRedo = !!v; });
    store.subscribe('strategyBuilder.toolbar.activeTool', (v) => { currentTool = v ?? 'select'; });
    
    updateToolbar();
  }
  
  // Update toolbar state
  function updateToolbar() {
    if (!toolbarElement) return;
    
    // Update undo/redo buttons
    const undoBtn = toolbarElement.querySelector('[data-action="undo"]');
    const redoBtn = toolbarElement.querySelector('[data-action="redo"]');
    
    if (undoBtn) undoBtn.disabled = !canUndo;
    if (redoBtn) redoBtn.disabled = !canRedo;
    
    // Update active tool
    toolbarElement.querySelectorAll('[data-tool]').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.tool === currentTool);
    });
  }
  
  // Undo
  function undo() {
    if (canUndo) {
      store.dispatch('history/undo');
    }
  }
  
  // Redo
  function redo() {
    if (canRedo) {
      store.dispatch('history/redo');
    }
  }
  
  // Set tool
  function setTool(tool) {
    currentTool = tool;
    store.set('strategyBuilder.toolbar.activeTool', tool);
    updateToolbar();
  }
  
  // Align blocks
  function alignBlocks(alignment) {
    store.dispatch('blocks/align', alignment);
  }
  
  // Auto layout
  function autoLayout() {
    store.dispatch('blocks/autoLayout');
  }
  
  // Zoom in
  function zoomIn() {
    const currentZoom = store.get('strategyBuilder.viewport.zoom') || 1;
    const newZoom = Math.min(5, currentZoom + 0.1);
    store.set('strategyBuilder.viewport.zoom', newZoom);
  }
  
  // Zoom out
  function zoomOut() {
    const currentZoom = store.get('strategyBuilder.viewport.zoom') || 1;
    const newZoom = Math.max(0.1, currentZoom - 0.1);
    store.set('strategyBuilder.viewport.zoom', newZoom);
  }
  
  // Reset zoom
  function resetZoom() {
    store.set('strategyBuilder.viewport.zoom', 1);
    store.set('strategyBuilder.viewport.panOffset', { x: 0, y: 0 });
  }
  
  // Attach event listeners
  function attachEventListeners() {
    if (!toolbarElement) return;
    
    toolbarElement.querySelectorAll('[data-action]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const action = e.target.dataset.action;
        
        switch (action) {
          case 'undo':
            undo();
            break;
          case 'redo':
            redo();
            break;
          case 'align-horizontal':
            alignBlocks('horizontal');
            break;
          case 'align-vertical':
            alignBlocks('vertical');
            break;
          case 'auto-layout':
            autoLayout();
            break;
          case 'zoom-in':
            zoomIn();
            break;
          case 'zoom-out':
            zoomOut();
            break;
          case 'reset-zoom':
            resetZoom();
            break;
        }
      });
    });
    
    toolbarElement.querySelectorAll('[data-tool]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        setTool(e.target.dataset.tool);
      });
    });
  }
  
  // Initialize
  initialize();
  attachEventListeners();
  
  return {
    updateToolbar,
    undo,
    redo,
    setTool,
    alignBlocks,
    autoLayout,
    zoomIn,
    zoomOut,
    resetZoom
  };
}
