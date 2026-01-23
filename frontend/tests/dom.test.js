/**
 * DOM Interaction Tests
 * Tests for UI components and DOM manipulation
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// DOM Helper Functions

/**
 * Create DOM element with attributes
 */
function createElement(tag, attributes = {}, textContent = '') {
  const element = document.createElement(tag);
  
  Object.entries(attributes).forEach(([key, value]) => {
    if (key === 'class') {
      element.className = value;
    } else if (key.startsWith('data-')) {
      element.dataset[key.slice(5)] = value;
    } else {
      element.setAttribute(key, value);
    }
  });
  
  if (textContent) {
    element.textContent = textContent;
  }
  
  return element;
}

/**
 * Show/hide loading overlay
 */
function showLoading(show) {
  const overlay = document.getElementById('loadingOverlay');
  if (!overlay) return;
  
  if (show) {
    overlay.classList.remove('hidden');
  } else {
    overlay.classList.add('hidden');
  }
}

/**
 * Update connection status indicator
 */
function updateConnectionStatus(status) {
  const dot = document.getElementById('connectionDot');
  const text = document.getElementById('connectionStatus');
  
  if (!dot || !text) return;
  
  switch(status) {
    case 'connected':
      dot.style.backgroundColor = 'var(--accent-green)';
      text.textContent = 'Connected';
      break;
    case 'connecting':
      dot.style.backgroundColor = 'var(--accent-yellow)';
      text.textContent = 'Connecting...';
      break;
    case 'disconnected':
      dot.style.backgroundColor = 'var(--accent-red)';
      text.textContent = 'Disconnected';
      break;
    default:
      dot.style.backgroundColor = 'gray';
      text.textContent = 'Unknown';
  }
}

/**
 * Render strategy card
 */
function renderStrategyCard(strategy) {
  const card = document.createElement('div');
  card.className = 'strategy-card';
  card.dataset.id = strategy.id;
  
  card.innerHTML = `
    <div class="card-header">
      <h4>${strategy.name}</h4>
      <span class="badge ${strategy.status}">${strategy.status}</span>
    </div>
    <div class="card-body">
      <p class="type">${strategy.type}</p>
      <div class="metrics">
        <span class="return">${strategy.performance?.total_return?.toFixed(2) || '--'}%</span>
        <span class="sharpe">${strategy.performance?.sharpe_ratio?.toFixed(2) || '--'}</span>
      </div>
    </div>
    <div class="card-footer">
      <button class="btn-edit" data-action="edit">Edit</button>
      <button class="btn-backtest" data-action="backtest">Backtest</button>
    </div>
  `;
  
  return card;
}

/**
 * Render orderbook row
 */
function renderOrderBookRow(order, type) {
  const row = document.createElement('div');
  row.className = `orderbook-row ${type}`;
  
  row.innerHTML = `
    <span class="bg-bar" style="width: ${order.depth || 0}%"></span>
    <span class="price">${order.price.toFixed(2)}</span>
    <span class="size">${order.size.toFixed(4)}</span>
    <span class="total">${order.total.toFixed(4)}</span>
  `;
  
  return row;
}

/**
 * Toggle modal visibility
 */
function toggleModal(modalId, show) {
  const modal = document.getElementById(modalId);
  if (!modal) return false;
  
  if (show) {
    modal.classList.add('active');
    modal.classList.remove('hidden');
  } else {
    modal.classList.remove('active');
    modal.classList.add('hidden');
  }
  
  return true;
}


describe('DOM Interactions', () => {

  describe('createElement', () => {
    it('should create element with correct tag', () => {
      const element = createElement('div');
      expect(element.tagName).toBe('DIV');
    });

    it('should set attributes correctly', () => {
      const element = createElement('button', {
        id: 'testBtn',
        type: 'submit',
        disabled: 'true'
      });
      
      expect(element.id).toBe('testBtn');
      expect(element.type).toBe('submit');
      expect(element.getAttribute('disabled')).toBe('true');
    });

    it('should set class correctly', () => {
      const element = createElement('div', { class: 'card primary' });
      expect(element.className).toBe('card primary');
    });

    it('should set data attributes', () => {
      const element = createElement('div', {
        'data-id': '123',
        'data-type': 'strategy'
      });
      
      expect(element.dataset.id).toBe('123');
      expect(element.dataset.type).toBe('strategy');
    });

    it('should set text content', () => {
      const element = createElement('span', {}, 'Hello World');
      expect(element.textContent).toBe('Hello World');
    });
  });

  describe('showLoading', () => {
    beforeEach(() => {
      document.body.innerHTML = `
        <div id="loadingOverlay" class="hidden">Loading...</div>
      `;
    });

    it('should show loading overlay', () => {
      const overlay = document.getElementById('loadingOverlay');
      expect(overlay.classList.contains('hidden')).toBe(true);
      
      showLoading(true);
      expect(overlay.classList.contains('hidden')).toBe(false);
    });

    it('should hide loading overlay', () => {
      const overlay = document.getElementById('loadingOverlay');
      overlay.classList.remove('hidden');
      
      showLoading(false);
      expect(overlay.classList.contains('hidden')).toBe(true);
    });

    it('should handle missing overlay element', () => {
      document.body.innerHTML = '';
      expect(() => showLoading(true)).not.toThrow();
    });
  });

  describe('updateConnectionStatus', () => {
    beforeEach(() => {
      document.body.innerHTML = `
        <span id="connectionDot"></span>
        <span id="connectionStatus"></span>
      `;
    });

    it('should show connected status', () => {
      updateConnectionStatus('connected');
      
      const dot = document.getElementById('connectionDot');
      const text = document.getElementById('connectionStatus');
      
      expect(dot.style.backgroundColor).toBe('var(--accent-green)');
      expect(text.textContent).toBe('Connected');
    });

    it('should show connecting status', () => {
      updateConnectionStatus('connecting');
      
      const text = document.getElementById('connectionStatus');
      expect(text.textContent).toBe('Connecting...');
    });

    it('should show disconnected status', () => {
      updateConnectionStatus('disconnected');
      
      const dot = document.getElementById('connectionDot');
      expect(dot.style.backgroundColor).toBe('var(--accent-red)');
    });

    it('should handle unknown status', () => {
      updateConnectionStatus('unknown');
      
      const text = document.getElementById('connectionStatus');
      expect(text.textContent).toBe('Unknown');
    });

    it('should handle missing elements', () => {
      document.body.innerHTML = '';
      expect(() => updateConnectionStatus('connected')).not.toThrow();
    });
  });

  describe('renderStrategyCard', () => {
    it('should create card with correct structure', () => {
      const strategy = testUtils.createMockStrategy();
      const card = renderStrategyCard(strategy);
      
      expect(card.classList.contains('strategy-card')).toBe(true);
      expect(card.dataset.id).toBe(strategy.id);
    });

    it('should display strategy name', () => {
      const strategy = testUtils.createMockStrategy({ name: 'My Strategy' });
      const card = renderStrategyCard(strategy);
      
      expect(card.querySelector('h4').textContent).toBe('My Strategy');
    });

    it('should display status badge', () => {
      const strategy = testUtils.createMockStrategy({ status: 'active' });
      const card = renderStrategyCard(strategy);
      
      const badge = card.querySelector('.badge');
      expect(badge.classList.contains('active')).toBe(true);
      expect(badge.textContent).toBe('active');
    });

    it('should display performance metrics', () => {
      const strategy = testUtils.createMockStrategy({
        performance: {
          total_return: 25.55,
          sharpe_ratio: 2.1
        }
      });
      const card = renderStrategyCard(strategy);
      
      expect(card.querySelector('.return').textContent).toContain('25.55');
      expect(card.querySelector('.sharpe').textContent).toContain('2.10');
    });

    it('should handle missing performance data', () => {
      const strategy = testUtils.createMockStrategy({ performance: null });
      const card = renderStrategyCard(strategy);
      
      expect(card.querySelector('.return').textContent).toContain('--');
    });

    it('should include action buttons', () => {
      const strategy = testUtils.createMockStrategy();
      const card = renderStrategyCard(strategy);
      
      const editBtn = card.querySelector('[data-action="edit"]');
      const backtestBtn = card.querySelector('[data-action="backtest"]');
      
      expect(editBtn).not.toBeNull();
      expect(backtestBtn).not.toBeNull();
    });
  });

  describe('renderOrderBookRow', () => {
    it('should create row with correct class', () => {
      const order = { price: 50000, size: 1.5, total: 3.0 };
      const row = renderOrderBookRow(order, 'ask');
      
      expect(row.classList.contains('orderbook-row')).toBe(true);
      expect(row.classList.contains('ask')).toBe(true);
    });

    it('should display price correctly', () => {
      const order = { price: 50000.50, size: 1, total: 1 };
      const row = renderOrderBookRow(order, 'bid');
      
      expect(row.querySelector('.price').textContent).toBe('50000.50');
    });

    it('should display size with 4 decimals', () => {
      const order = { price: 50000, size: 1.23456789, total: 2 };
      const row = renderOrderBookRow(order, 'ask');
      
      expect(row.querySelector('.size').textContent).toBe('1.2346');
    });

    it('should set depth bar width', () => {
      const order = { price: 50000, size: 1, total: 1, depth: 75 };
      const row = renderOrderBookRow(order, 'bid');
      
      const bar = row.querySelector('.bg-bar');
      expect(bar.style.width).toBe('75%');
    });
  });

  describe('toggleModal', () => {
    beforeEach(() => {
      document.body.innerHTML = `
        <div id="testModal" class="modal hidden"></div>
      `;
    });

    it('should show modal', () => {
      const result = toggleModal('testModal', true);
      const modal = document.getElementById('testModal');
      
      expect(result).toBe(true);
      expect(modal.classList.contains('active')).toBe(true);
      expect(modal.classList.contains('hidden')).toBe(false);
    });

    it('should hide modal', () => {
      const modal = document.getElementById('testModal');
      modal.classList.add('active');
      modal.classList.remove('hidden');
      
      toggleModal('testModal', false);
      
      expect(modal.classList.contains('active')).toBe(false);
      expect(modal.classList.contains('hidden')).toBe(true);
    });

    it('should return false for non-existent modal', () => {
      const result = toggleModal('nonExistent', true);
      expect(result).toBe(false);
    });
  });

  describe('Event Handling', () => {
    it('should handle click events', () => {
      const handler = vi.fn();
      const button = createElement('button', { id: 'testBtn' }, 'Click Me');
      document.body.appendChild(button);
      
      button.addEventListener('click', handler);
      button.click();
      
      expect(handler).toHaveBeenCalledTimes(1);
    });

    it('should handle input events', () => {
      const handler = vi.fn();
      const input = createElement('input', { type: 'text' });
      document.body.appendChild(input);
      
      input.addEventListener('input', handler);
      input.value = 'test';
      input.dispatchEvent(new Event('input'));
      
      expect(handler).toHaveBeenCalledTimes(1);
    });

    it('should handle keyboard events', () => {
      const handler = vi.fn();
      const input = createElement('input', { type: 'text' });
      document.body.appendChild(input);
      
      input.addEventListener('keydown', handler);
      input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));
      
      expect(handler).toHaveBeenCalledTimes(1);
      expect(handler.mock.calls[0][0].key).toBe('Enter');
    });

    it('should handle form submission', () => {
      const handler = vi.fn((e) => e.preventDefault());
      
      document.body.innerHTML = `
        <form id="testForm">
          <input type="text" name="test" value="value">
          <button type="submit">Submit</button>
        </form>
      `;
      
      const form = document.getElementById('testForm');
      form.addEventListener('submit', handler);
      form.dispatchEvent(new Event('submit'));
      
      expect(handler).toHaveBeenCalledTimes(1);
    });
  });

  describe('Accessibility', () => {
    it('should have proper ARIA labels', () => {
      const button = createElement('button', {
        'aria-label': 'Close modal',
        'aria-pressed': 'false'
      });
      
      expect(button.getAttribute('aria-label')).toBe('Close modal');
      expect(button.getAttribute('aria-pressed')).toBe('false');
    });

    it('should handle focus management', () => {
      const input1 = createElement('input', { id: 'input1', type: 'text' });
      const input2 = createElement('input', { id: 'input2', type: 'text' });
      document.body.append(input1, input2);
      
      input1.focus();
      expect(document.activeElement).toBe(input1);
      
      input2.focus();
      expect(document.activeElement).toBe(input2);
    });
  });
});
