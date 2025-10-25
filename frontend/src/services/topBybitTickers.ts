// Top 100 Bybit tickers (spot and perp variants). This is a curated starter list and can be adjusted.
// We generate ~50 base assets and expose combined spot and perp arrays to reach ~100 entries.

const BASE_COINS = [
  'BTC',
  'ETH',
  'BNB',
  'SOL',
  'XRP',
  'ADA',
  'DOGE',
  'TRX',
  'TON',
  'LINK',
  'LTC',
  'DOT',
  'MATIC',
  'BCH',
  'ETC',
  'XLM',
  'ATOM',
  'FIL',
  'APT',
  'ARB',
  'OP',
  'PEPE',
  'NEAR',
  'SUI',
  'INJ',
  'IMX',
  'ICP',
  'HBAR',
  'VET',
  'AR',
  'TIA',
  'SEI',
  'RUNE',
  'POL',
  'SAND',
  'MANA',
  'AAVE',
  'ALGO',
  'FTM',
  'DYDX',
  'GALA',
  'GRT',
  'XMR',
  'XTZ',
  'ZEC',
  'EGLD',
  'STX',
  'KAS',
  'RNDR',
  'ORDI',
];

const SPOT = BASE_COINS.map((c) => `${c}USDT`);
const PERP = BASE_COINS.map((c) => `${c}USDT.P`);

export const BYBIT_TOP_TICKERS: string[] = [...SPOT, ...PERP];

// Dynamic fetch: Top Bybit tickers by 24h turnover via public REST API
// Docs: https://bybit-exchange.github.io/docs/v5/market/tickers
export type BybitTickerCategory = 'spot' | 'linear' | 'inverse';
export type BybitTickerRow = {
  symbol: string;
  turnover24h?: string | number;
  volume24h?: string | number;
  price24hPcnt?: string | number;
  lastPrice?: string | number;
};

export async function fetchTopBybitTickersByVolume(opts?: {
  category?: BybitTickerCategory; // default 'linear'
  limit?: number; // default 100
  quote?: string; // optional, e.g. 'USDT'
  timeoutMs?: number; // default 4000
}): Promise<string[]> {
  const category: BybitTickerCategory = opts?.category ?? 'linear';
  const limit = Math.max(1, Math.min(500, opts?.limit ?? 100));
  const quote = (opts?.quote || '').toUpperCase();
  const timeoutMs = Math.max(1000, Math.min(15000, opts?.timeoutMs ?? 4000));

  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const url = new URL('https://api.bybit.com/v5/market/tickers');
    url.searchParams.set('category', category);
    const res = await fetch(url.toString(), { signal: ctrl.signal });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const body: any = await res.json();
    const list: BybitTickerRow[] = body?.result?.list || [];
    let rows = list;
    // Optional filter by quote (e.g., only USDT pairs)
    if (quote) {
      rows = rows.filter((r) => typeof r?.symbol === 'string' && r.symbol.endsWith(quote));
    }
    const sorted = rows
      .map((r) => ({
        symbol: String(r.symbol || '').toUpperCase(),
        turnover: (() => {
          // Prefer quote-value turnover for correct comparable ranking across symbols
          const v = (r as any).turnover24h ?? (r as any).volume24h;
          const n = typeof v === 'number' ? v : parseFloat(String(v || '0'));
          return Number.isFinite(n) ? n : 0;
        })(),
      }))
      // Sort by 24h turnover (descending): bigger notional first
      .sort((a, b) => b.turnover - a.turnover)
      .slice(0, limit);

    // Return symbols only (no suffix). Caller can annotate UI as needed.
    // De-duplicate while preserving order.
    const out: string[] = [];
    for (const r of sorted) {
      if (!out.includes(r.symbol)) out.push(r.symbol);
    }
    // If fewer than requested (e.g., API change), fallback-fill from static list
    if (out.length < limit) {
      for (const s of BYBIT_TOP_TICKERS) {
        if (out.length >= limit) break;
        if (!out.includes(s.replace('.P', ''))) {
          // keep base symbol without .P to avoid duplicates
          out.push(s.replace('.P', ''));
        }
      }
    }
    return out;
  } catch {
    // Network/CORS/timeouts: return static fallback
    const base = BYBIT_TOP_TICKERS.map((s) => s.replace('.P', ''));
    // unique while preserving order
    const seen = new Set<string>();
    const uniq: string[] = [];
    for (const s of base) {
      const u = s.toUpperCase();
      if (!seen.has(u)) {
        uniq.push(u);
        seen.add(u);
      }
      if (uniq.length >= (opts?.limit ?? 100)) break;
    }
    return uniq;
  } finally {
    clearTimeout(t);
  }
}

export default BYBIT_TOP_TICKERS;
