/**
 * Properties Module — Панель свойств
 *
 * Отображение и редактирование свойств блоков
 */

import { getStore } from '../core/StateManager.js';

const store = getStore();

export function createPropertiesModule(panelElement) {
  // State
  let selectedBlockId = null;
  let selectedBlock = null;

  // Initialize from store
  function initialize() {
    if (!store) return;

    store.subscribe('strategyBuilder.selection.selectedBlockId', (id) => {
      selectedBlockId = id;
      updatePanel();
    });

    store.subscribe('strategyBuilder.graph.blocks', (blocks) => {
      if (selectedBlockId) {
        selectedBlock = blocks.find(b => b.id === selectedBlockId);
        updatePanel();
      }
    });
  }

  // Update panel
  function updatePanel() {
    if (!panelElement) return;

    if (!selectedBlockId || !selectedBlock) {
      panelElement.innerHTML = '<div class="empty-state">No block selected</div>';
      return;
    }

    panelElement.innerHTML = `
      <div class="properties-panel">
        <h3>${selectedBlock.label}</h3>
        <div class="property-group">
          <label>Type:</label>
          <span>${selectedBlock.type}</span>
        </div>
        <div class="property-group">
          <label>Position:</label>
          <span>(${Math.round(selectedBlock.x)}, ${Math.round(selectedBlock.y)})</span>
        </div>
        <div class="property-group">
          <label>Parameters:</label>
          ${renderParameters(selectedBlock.parameters)}
        </div>
        <div class="actions">
          <button class="btn btn-delete" data-action="delete">Delete</button>
          <button class="btn btn-duplicate" data-action="duplicate">Duplicate</button>
        </div>
      </div>
    `;

    attachEventListeners();
  }

  function renderParameters(params) {
    if (!params || Object.keys(params).length === 0) {
      return '<span class="text-muted">No parameters</span>';
    }

    return Object.entries(params).map(([key, value]) => `
      <div class="parameter-row">
        <label>${key}:</label>
        <input type="text" value="${value}" data-param="${key}" />
      </div>
    `).join('');
  }

  function attachEventListeners() {
    panelElement.querySelectorAll('button').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const action = e.target.dataset.action;
        if (action === 'delete') {
          deleteBlock();
        } else if (action === 'duplicate') {
          duplicateBlock();
        }
      });
    });

    panelElement.querySelectorAll('input[data-param]').forEach(input => {
      input.addEventListener('change', (e) => {
        const param = e.target.dataset.param;
        const value = e.target.value;
        updateParameter(param, value);
      });
    });
  }

  function deleteBlock() {
    if (selectedBlockId) {
      store.dispatch('blocks/delete', selectedBlockId);
    }
  }

  function duplicateBlock() {
    if (selectedBlockId) {
      store.dispatch('blocks/duplicate', selectedBlockId);
    }
  }

  function updateParameter(key, value) {
    if (selectedBlockId) {
      store.dispatch('blocks/updateParameter', {
        blockId: selectedBlockId,
        key,
        value
      });
    }
  }

  // Show panel
  function show() {
    if (panelElement) {
      panelElement.style.display = 'block';
      updatePanel();
    }
  }

  // Hide panel
  function hide() {
    if (panelElement) {
      panelElement.style.display = 'none';
    }
  }

  // Initialize
  initialize();

  return {
    updatePanel,
    show,
    hide
  };
}
