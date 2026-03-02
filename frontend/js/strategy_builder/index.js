/**
 * Strategy Builder — Главный модуль
 * 
 * Объединяет все модули в единую систему
 */

import { getStore } from '../core/StateManager.js';
import { createCanvasModule } from './CanvasModule.js';
import { createBlocksModule } from './BlocksModule.js';
import { createPropertiesModule } from './PropertiesModule.js';
import { createToolbarModule } from './ToolbarModule.js';

const store = getStore();

export function createStrategyBuilder(config = {}) {
  const { canvasElement, toolbarElement, propertiesPanel } = config;
  
  // Initialize modules
  const canvas = createCanvasModule(canvasElement);
  const blocks = createBlocksModule();
  const properties = createPropertiesModule(propertiesPanel);
  const toolbar = createToolbarModule(toolbarElement);
  
  // Render loop
  function render() {
    const blocksData = blocks.getAllBlocks();
    // Connections would be retrieved from a connections module
    const connections = [];
    canvas.render(blocksData, connections);
  }
  
  // Auto-save
  let lastAutoSave = 0;
  const AUTOSAVE_INTERVAL = 30000;
  
  function autoSave() {
    const now = Date.now();
    if (now - lastAutoSave > AUTOSAVE_INTERVAL) {
      const state = {
        blocks: blocks.getAllBlocks(),
        viewport: {
          zoom: canvas.getZoom(),
          panOffset: canvas.getDragOffset()
        }
      };
      localStorage.setItem('strategy_builder_autosave', JSON.stringify(state));
      lastAutoSave = now;
    }
  }
  
  // Animation loop
  function animate() {
    render();
    autoSave();
    requestAnimationFrame(animate);
  }
  
  // Load from autosave
  function loadFromAutosave() {
    const saved = localStorage.getItem('strategy_builder_autosave');
    if (saved) {
      try {
        const state = JSON.parse(saved);
        // Restore state
      } catch (e) {
        console.error('Failed to load autosave:', e);
      }
    }
  }
  
  // Initialize
  function initialize() {
    loadFromAutosave();
    animate();
    console.log('[StrategyBuilder] Initialized');
  }
  
  // Public API
  return {
    initialize,
    canvas,
    blocks,
    properties,
    toolbar,
    render,
    undo: () => toolbar.undo(),
    redo: () => toolbar.redo(),
    zoomIn: () => toolbar.zoomIn(),
    zoomOut: () => toolbar.zoomOut(),
    resetZoom: () => toolbar.resetZoom()
  };
}
