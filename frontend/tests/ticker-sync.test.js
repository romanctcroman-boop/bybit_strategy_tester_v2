/**
 * Ticker selection and sync flow tests.
 *
 * Покрытие:
 * - Unit: построение URL sync-all-tf-stream, парсинг SSE (progress/complete), debounce.cancel().
 * - Integration (syncSymbolData): пустой символ не дергает sync; первый выбор тикера — fetch с верным URL;
 *   смена тикера — новый запрос; при смене тикера во время загрузки предыдущий запрос отменяется (abort);
 *   market_type spot в URL; отмена потока (cancelled: true); runCheckSymbolDataForProperties(forceRefresh);
 *   повторный вызов для того же символа во время загрузки не создаёт дубликат запроса.
 *
 * Запуск: из frontend/ — npx vitest run tests/ticker-sync.test.js
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { debounce } from '../js/utils.js';

const API_BASE = '/api/v1';

/** Build sync stream URL (same formula as strategy_builder) */
function buildSyncStreamUrl(symbol, marketType = 'linear') {
  return `${API_BASE}/marketdata/symbols/sync-all-tf-stream?symbol=${encodeURIComponent(symbol)}&market_type=${marketType}`;
}

/** Parse SSE line "data: {...}" to event object */
function parseSSELine(line) {
  const match = line.match(/^data:\s*(.+)$/m);
  if (!match) return null;
  try {
    return JSON.parse(match[1]);
  } catch {
    return null;
  }
}

/** Create minimal DOM required for syncSymbolData and for strategy_builder init */
function createSyncDOM() {
  document.body.innerHTML = `
    <input id="backtestSymbol" type="text" value="" />
    <select id="builderMarketType"><option value="linear" selected>linear</option><option value="spot">spot</option></select>
    <div id="propertiesDataStatusRow" class="hidden"></div>
    <div id="propertiesDataStatusIndicator"></div>
    <div id="propertiesCandleLoadingProgress" class="hidden"><div id="propertiesCandleLoadingBar" role="progressbar" aria-valuenow="0"></div></div>
    <div id="globalLoadingIndicator" class="hidden"><span class="loading-text"></span></div>
    <select id="strategyTimeframe"><option value="15" selected>15</option></select>
    <div id="blockCategories"></div>
    <div id="templatesGrid"></div>
    <div id="blocksContainer"></div>
    <div id="canvasContainer"></div>
    <button id="btnVersions" style="display:none"></button>
    <input id="backtestLeverageRange" value="10" />
    <input id="backtestLeverage" value="10" />
    <input id="strategyName" />
    <span id="strategyNameDisplay"></span>
    <div id="blockSearch"></div>
    <div id="propertiesPanel"></div>
    <div id="backtestPositionSizeType"></div>
    <div id="backtestPositionSize"></div>
    <div id="backtestCapital"></div>
    <div id="backtestLeverageRiskIndicator"></div>
    <div id="backtestPositionSizeTypeLabel"></div>
    <div id="backtestPositionSizeLabel"></div>
    <div id="backtestLeverageValue"></div>
  `;
}

/** Create a ReadableStream that emits SSE events (progress + complete) */
function createSSEStream(events = null) {
  const defaultEvents = [
    { event: 'progress', step: 0, totalSteps: 9, percent: 0, message: 'Синхронизация 1m...' },
    { event: 'progress', step: 1, totalSteps: 9, percent: 11, tf: '1', message: 'Синхронизация 1 минута...' },
    { event: 'complete', totalNew: 100, results: {}, message: 'Синхронизировано', cancelled: false }
  ];
  const list = events ?? defaultEvents;
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const ev of list) {
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(ev)}\n\n`));
      }
      controller.close();
    }
  });
}

/** Mock fetch that returns 200 + SSE stream */
function mockFetchSSESuccess(overrides = {}) {
  return vi.fn((url, options = {}) => {
    return Promise.resolve(
      new Response(createSSEStream(overrides.events), {
        status: 200,
        headers: { 'Content-Type': 'text/event-stream' }
      })
    );
  });
}

describe('Ticker sync — URL and parsing (unit)', () => {
  it('builds sync stream URL for symbol and market type', () => {
    expect(buildSyncStreamUrl('DOGEUSDT', 'linear')).toBe(
      '/api/v1/marketdata/symbols/sync-all-tf-stream?symbol=DOGEUSDT&market_type=linear'
    );
    expect(buildSyncStreamUrl('BTCUSDT')).toBe(
      '/api/v1/marketdata/symbols/sync-all-tf-stream?symbol=BTCUSDT&market_type=linear'
    );
    expect(buildSyncStreamUrl('BNBUSDT', 'spot')).toBe(
      '/api/v1/marketdata/symbols/sync-all-tf-stream?symbol=BNBUSDT&market_type=spot'
    );
  });

  it('parses SSE data line to event object', () => {
    const line = 'data: {"event":"progress","step":1,"totalSteps":9,"percent":11}\n\n';
    const parsed = parseSSELine(line);
    expect(parsed).toEqual({ event: 'progress', step: 1, totalSteps: 9, percent: 11 });
  });

  it('parses complete event', () => {
    const line = 'data: {"event":"complete","totalNew":50,"cancelled":false}\n\n';
    const parsed = parseSSELine(line);
    expect(parsed?.event).toBe('complete');
    expect(parsed?.totalNew).toBe(50);
    expect(parsed?.cancelled).toBe(false);
  });

  it('returns null for non-JSON or missing data', () => {
    expect(parseSSELine('')).toBeNull();
    expect(parseSSELine('foo: bar')).toBeNull();
  });
});

describe('Debounce cancel (unit)', () => {
  it('debounced function has cancel method', () => {
    const fn = vi.fn();
    const debounced = debounce(fn, 200);
    expect(typeof debounced.cancel).toBe('function');
  });

  it('cancel prevents pending invocation', async () => {
    const fn = vi.fn();
    const debounced = debounce(fn, 200);
    debounced('a');
    debounced.cancel();
    await new Promise((r) => setTimeout(r, 250));
    expect(fn).not.toHaveBeenCalled();
  });

  it('after cancel, new call is scheduled again', async () => {
    const fn = vi.fn();
    const debounced = debounce(fn, 50);
    debounced('a');
    debounced.cancel();
    debounced('b');
    await new Promise((r) => setTimeout(r, 100));
    expect(fn).toHaveBeenCalledTimes(1);
    expect(fn).toHaveBeenCalledWith('b');
  });
});

describe('Ticker sync — integration (syncSymbolData)', () => {
  let originalFetch;
  let strategyBuilderModule;

  beforeEach(() => {
    originalFetch = global.fetch;
    createSyncDOM();
  });

  afterEach(async () => {
    global.fetch = originalFetch;
    vi.clearAllMocks();
  });

  it('does not call fetch for sync when symbol is empty', async () => {
    const fetchMock = vi.fn(() => Promise.resolve({ ok: true }));
    global.fetch = fetchMock;
    strategyBuilderModule = await import('../js/pages/strategy_builder.js');
    document.getElementById('backtestSymbol').value = '';
    await strategyBuilderModule.syncSymbolData(true);
    const syncCalls = fetchMock.mock.calls.filter(([url]) => url && url.includes('sync-all-tf-stream'));
    expect(syncCalls).toHaveLength(0);
  });

  it('calls fetch with correct URL when symbol is set (first ticker)', async () => {
    const fetchMock = mockFetchSSESuccess();
    global.fetch = fetchMock;
    strategyBuilderModule = await import('../js/pages/strategy_builder.js');
    document.getElementById('backtestSymbol').value = 'DOGEUSDT';
    document.getElementById('builderMarketType').value = 'linear';
    await strategyBuilderModule.syncSymbolData(true);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toContain('sync-all-tf-stream');
    expect(url).toContain('symbol=DOGEUSDT');
    expect(url).toContain('market_type=linear');
    expect(options?.signal).toBeDefined();
  });

  it('after sync, status row is visible and indicator shows synced state', async () => {
    const fetchMock = mockFetchSSESuccess();
    global.fetch = fetchMock;
    strategyBuilderModule = await import('../js/pages/strategy_builder.js');
    document.getElementById('backtestSymbol').value = 'BNBUSDT';
    await strategyBuilderModule.syncSymbolData(true);

    const statusRow = document.getElementById('propertiesDataStatusRow');
    const indicator = document.getElementById('propertiesDataStatusIndicator');
    expect(statusRow?.classList.contains('hidden')).toBe(false);
    expect(indicator?.innerHTML).toMatch(/Синхронизировано|актуальны|свечей/);
  });

  it('changing ticker starts new sync with new symbol (second request)', async () => {
    const fetchMock = mockFetchSSESuccess();
    global.fetch = fetchMock;
    strategyBuilderModule = await import('../js/pages/strategy_builder.js');
    document.getElementById('backtestSymbol').value = 'DOGEUSDT';
    await strategyBuilderModule.syncSymbolData(true);
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('symbol=DOGEUSDT'),
      expect.any(Object)
    );

    fetchMock.mockClear();
    document.getElementById('backtestSymbol').value = 'BTCUSDT';
    await strategyBuilderModule.syncSymbolData(true);
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('symbol=BTCUSDT'),
      expect.any(Object)
    );
  });

  it('when second sync starts for different symbol, first request is aborted', async () => {
    let firstSignal;
    const fetchMock = vi.fn((url, options = {}) => {
      if (url.includes('DOGEUSDT')) {
        firstSignal = options.signal;
        return Promise.resolve(
          new Response(createSSEStream(), { status: 200 })
        );
      }
      if (url.includes('BTCUSDT')) {
        return Promise.resolve(
          new Response(createSSEStream(), { status: 200 })
        );
      }
      return Promise.resolve(new Response('', { status: 404 }));
    });
    global.fetch = fetchMock;

    strategyBuilderModule = await import('../js/pages/strategy_builder.js');
    document.getElementById('backtestSymbol').value = 'DOGEUSDT';
    const firstSyncPromise = strategyBuilderModule.syncSymbolData(true);
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    document.getElementById('backtestSymbol').value = 'BTCUSDT';
    const secondSyncPromise = strategyBuilderModule.syncSymbolData(true);
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));

    expect(firstSignal).toBeDefined();
    expect(firstSignal?.aborted).toBe(true);

    await firstSyncPromise;
    await secondSyncPromise;
  });

  it('market_type spot is passed in URL', async () => {
    const fetchMock = mockFetchSSESuccess();
    global.fetch = fetchMock;
    strategyBuilderModule = await import('../js/pages/strategy_builder.js');
    document.getElementById('backtestSymbol').value = 'ETHUSDT';
    document.getElementById('builderMarketType').value = 'spot';
    await strategyBuilderModule.syncSymbolData(true);

    const [url] = fetchMock.mock.calls[0];
    expect(url).toContain('market_type=spot');
  });

  it('handles cancelled stream (cancelled: true in complete)', async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(
        new Response(
          createSSEStream([
            { event: 'progress', step: 0, totalSteps: 9, percent: 0 },
            { event: 'complete', totalNew: 0, results: {}, cancelled: true }
          ]),
          { status: 200 }
        )
      )
    );
    global.fetch = fetchMock;
    strategyBuilderModule = await import('../js/pages/strategy_builder.js');
    document.getElementById('backtestSymbol').value = 'XRPUSDT';
    await strategyBuilderModule.syncSymbolData(true);
    expect(fetchMock).toHaveBeenCalled();
    const indicator = document.getElementById('propertiesDataStatusIndicator');
    expect(indicator).toBeTruthy();
  });

  it('runCheckSymbolDataForProperties(forceRefresh) triggers sync for current symbol', async () => {
    const fetchMock = mockFetchSSESuccess();
    global.fetch = fetchMock;
    strategyBuilderModule = await import('../js/pages/strategy_builder.js');
    document.getElementById('backtestSymbol').value = 'ADAUSDT';
    await strategyBuilderModule.runCheckSymbolDataForProperties(true);
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('symbol=ADAUSDT'),
      expect.any(Object)
    );
  });

  it('second sync for same symbol while first is in progress does not start duplicate request', async () => {
    let resolveFirst;
    const firstSyncPromise = new Promise((resolve) => { resolveFirst = resolve; });
    const fetchMock = vi.fn((url) => {
      if (url.includes('sync-all-tf-stream')) return firstSyncPromise;
      return Promise.resolve({ ok: true });
    });
    global.fetch = fetchMock;
    strategyBuilderModule = await import('../js/pages/strategy_builder.js');
    document.getElementById('backtestSymbol').value = 'SOLUSDT';
    const sync1 = strategyBuilderModule.syncSymbolData(true);
    await vi.waitFor(() => expect(fetchMock.mock.calls.some(([u]) => u?.includes('sync-all-tf-stream'))).toBe(true));
    const syncCallsBefore = fetchMock.mock.calls.filter(([u]) => u?.includes('sync-all-tf-stream')).length;
    strategyBuilderModule.syncSymbolData(true);
    await new Promise((r) => setTimeout(r, 50));
    const syncCallsAfter = fetchMock.mock.calls.filter(([u]) => u?.includes('sync-all-tf-stream')).length;
    expect(syncCallsAfter).toBe(syncCallsBefore);
    resolveFirst(
      new Response(createSSEStream(), { status: 200 })
    );
    await sync1;
  });
});
