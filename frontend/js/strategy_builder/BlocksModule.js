/**
 * Blocks Module — Управление блоками
 *
 * Создание, перемещение, удаление блоков
 */

import { getStore } from '../core/StateManager.js';

const store = getStore();

export function createBlocksModule() {
  // State
  let blocks = [];
  let selectedBlockId = null;
  let selectedBlockIds = [];

  // Initialize from store
  function initialize() {
    if (!store) return;

    store.subscribe('strategyBuilder.graph.blocks', (v) => { blocks = v ?? []; });
    store.subscribe('strategyBuilder.selection.selectedBlockId', (v) => { selectedBlockId = v; });
    store.subscribe('strategyBuilder.selection.selectedBlockIds', (v) => { selectedBlockIds = v ?? []; });
  }

  // Create block
  function createBlock(type, x, y, label) {
    const block = {
      id: `block_${Date.now()}_${Math.random().toString(36).substring(2, 11)}`,
      type,
      x,
      y,
      width: 150,
      height: 80,
      label,
      parameters: {},
      inputs: [],
      outputs: []
    };

    blocks.push(block);
    store.set('strategyBuilder.graph.blocks', blocks);

    return block;
  }

  // Delete block
  function deleteBlock(blockId) {
    blocks = blocks.filter(b => b.id !== blockId);
    store.set('strategyBuilder.graph.blocks', blocks);

    // Also remove from selection
    selectedBlockIds = selectedBlockIds.filter(id => id !== blockId);
    store.set('strategyBuilder.selection.selectedBlockIds', selectedBlockIds);

    if (selectedBlockId === blockId) {
      selectedBlockId = null;
      store.set('strategyBuilder.selection.selectedBlockId', null);
    }
  }

  // Move block
  function moveBlock(blockId, x, y) {
    const block = blocks.find(b => b.id === blockId);
    if (block) {
      block.x = x;
      block.y = y;
      store.set('strategyBuilder.graph.blocks', [...blocks]);
    }
  }

  // Update block parameters
  function updateBlockParameters(blockId, parameters) {
    const block = blocks.find(b => b.id === blockId);
    if (block) {
      block.parameters = { ...block.parameters, ...parameters };
      store.set('strategyBuilder.graph.blocks', [...blocks]);
    }
  }

  // Select block
  function selectBlock(blockId) {
    selectedBlockId = blockId;
    selectedBlockIds = blockId ? [blockId] : [];
    store.set('strategyBuilder.selection.selectedBlockId', blockId);
    store.set('strategyBuilder.selection.selectedBlockIds', selectedBlockIds);
  }

  // Multi-select
  function selectBlocks(blockIds) {
    selectedBlockIds = blockIds;
    store.set('strategyBuilder.selection.selectedBlockIds', blockIds);
  }

  // Get selected blocks
  function getSelectedBlocks() {
    return blocks.filter(b => selectedBlockIds.includes(b.id));
  }

  // Get block by ID
  function getBlock(blockId) {
    return blocks.find(b => b.id === blockId);
  }

  // Get all blocks
  function getAllBlocks() {
    return [...blocks];
  }

  // Duplicate block
  function duplicateBlock(blockId) {
    const block = blocks.find(b => b.id === blockId);
    if (block) {
      const newBlock = {
        ...block,
        id: `block_${Date.now()}_${Math.random().toString(36).substring(2, 11)}`,
        x: block.x + 20,
        y: block.y + 20
      };
      blocks.push(newBlock);
      store.set('strategyBuilder.graph.blocks', [...blocks]);
      return newBlock;
    }
    return null;
  }

  // Align blocks
  function alignBlocks(alignment) {
    const selected = getSelectedBlocks();

    if (selected.length < 2) return;

    switch (alignment) {
      case 'horizontal':
        const avgY = selected.reduce((sum, b) => sum + b.y, 0) / selected.length;
        selected.forEach(b => {
          b.y = avgY;
          store.set('strategyBuilder.graph.blocks', [...blocks]);
        });
        break;
      case 'vertical':
        const avgX = selected.reduce((sum, b) => sum + b.x, 0) / selected.length;
        selected.forEach(b => {
          b.x = avgX;
          store.set('strategyBuilder.graph.blocks', [...blocks]);
        });
        break;
    }
  }

  // Initialize
  initialize();

  return {
    createBlock,
    deleteBlock,
    moveBlock,
    updateBlockParameters,
    selectBlock,
    selectBlocks,
    getSelectedBlocks,
    getBlock,
    getAllBlocks,
    duplicateBlock,
    alignBlocks
  };
}
