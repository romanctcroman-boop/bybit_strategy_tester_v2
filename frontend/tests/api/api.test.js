/**
 * api.js Unit Tests
 *
 * Covers bugs fixed in B-09 and B-10:
 *   B-09 — LRU cache eviction (MAX_CACHE_SIZE = 100)
 *   B-10 — AbortSignal fallback correctly bridges caller signal + timeout signal
 *
 * NOTE: api.js depends on `fetch` (provided by happy-dom) and
 *       `AbortSignal.any` (available in happy-dom ≥13 / Node ≥21).
 *       We polyfill AbortSignal.any absence so B-10 fallback path is tested.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// ─── helpers ──────────────────────────────────────────────────────────────────

/**
 * Import the module under test.
 * api.js is not a pure-ESM default-export — it exports named symbols and
 * attaches window.API; we re-import per suite to get a fresh module state.
 */
async function loadModule() {
    // Use a cache-busting query param so vitest re-evaluates the module
    return import('../../js/api.js');
}

// ─── LRU cache (B-09) ─────────────────────────────────────────────────────────
describe('api.js LRU cache (B-09)', () => {
    let fetchMock;

    function makeOkResponse(body = { ok: true }) {
        return new Response(JSON.stringify(body), {
            status: 200,
            headers: { 'Content-Type': 'application/json' }
        });
    }

    beforeEach(() => {
        // Use mockImplementation so each call gets a fresh Response instance
        // (Response bodies can only be consumed once in happy-dom).
        fetchMock = vi.fn().mockImplementation(() => Promise.resolve(makeOkResponse()));
        vi.stubGlobal('fetch', fetchMock);
    });

    afterEach(() => {
        vi.restoreAllMocks();
    });

    it('returns cached data on repeated requests within TTL', async () => {
        const { api } = await loadModule();
        api.clearCache();

        // First call — hits the network
        await api.get('/test-cache', { useCache: true, cacheTime: 60000 });
        // Second call within TTL — must NOT call fetch again
        await api.get('/test-cache', { useCache: true, cacheTime: 60000 });

        expect(fetchMock).toHaveBeenCalledTimes(1);
    });

    it('evicts oldest entry when cache exceeds MAX_CACHE_SIZE', async () => {
        const { api } = await loadModule();
        api.clearCache();

        // Fill the cache with 100 unique endpoints
        for (let i = 0; i < 100; i++) {
            const body = { i };
            fetchMock.mockImplementationOnce(() =>
                Promise.resolve(makeOkResponse(body))
            );
            await api.get(`/endpoint-${i}`, { useCache: true, cacheTime: 60000 });
        }

        const callsBefore = fetchMock.mock.calls.length; // = 100

        // Adding one more entry should evict endpoint-0 (LRU / oldest)
        fetchMock.mockImplementationOnce(() => Promise.resolve(makeOkResponse({ i: 100 })));
        await api.get('/endpoint-100', { useCache: true, cacheTime: 60000 });

        // endpoint-0 was evicted — fetching it again must go to network
        fetchMock.mockImplementationOnce(() => Promise.resolve(makeOkResponse({ i: 0 })));
        await api.get('/endpoint-0', { useCache: true, cacheTime: 60000 });

        // Expect 3 extra fetch calls: +1 for endpoint-100, +1 for re-fetched endpoint-0
        expect(fetchMock.mock.calls.length).toBe(callsBefore + 2);
    });

    it('invalidates expired cache entries', async () => {
        // The TTL check is pure timestamp arithmetic — no timers are actually
        // needed at runtime.  We stub Date.now() to fast-forward time instead
        // of using fake timers, which avoids potential hangs from api.js's
        // internal setTimeout-based abort guard.
        const { api } = await loadModule();
        api.clearCache();

        const startMs = Date.now();
        let currentMs = startMs;
        vi.spyOn(Date, 'now').mockImplementation(() => currentMs);

        fetchMock.mockImplementation(() => Promise.resolve(makeOkResponse({ v: 1 })));

        await api.get('/ttl-test', { useCache: true, cacheTime: 1000 });
        expect(fetchMock).toHaveBeenCalledTimes(1);

        // Fast-forward Date.now by 2 seconds — entry is now expired
        currentMs = startMs + 2000;

        await api.get('/ttl-test', { useCache: true, cacheTime: 1000 });
        expect(fetchMock).toHaveBeenCalledTimes(2);

        vi.restoreAllMocks();
    });
});

// ─── AbortSignal fallback (B-10) ───────────────────────────────────────────────
describe('api.js AbortSignal fallback (B-10)', () => {
    let originalAbortSignalAny;

    beforeEach(() => {
        originalAbortSignalAny = AbortSignal.any;
    });

    afterEach(() => {
        // Restore AbortSignal.any
        if (originalAbortSignalAny) {
            AbortSignal.any = originalAbortSignalAny;
        } else {
            delete AbortSignal.any;
        }
        vi.restoreAllMocks();
    });

    it('aborts on timeout using the bridge fallback when AbortSignal.any is absent', async () => {
        // Simulate an environment that lacks AbortSignal.any (B-10 fallback path)
        delete AbortSignal.any;
        vi.useFakeTimers();

        // Hang the request indefinitely so only the timeout triggers rejection
        const fetchMock = vi.fn().mockImplementation(
            (_url, opts) =>
                new Promise((_resolve, reject) => {
                    opts?.signal?.addEventListener('abort', () =>
                        reject(new DOMException('Aborted', 'AbortError'))
                    );
                })
        );
        vi.stubGlobal('fetch', fetchMock);

        const { api } = await loadModule();
        // Override timeout to a short value for the test
        api.config = { ...api.config, timeout: 500, retryAttempts: 1 };

        const requestPromise = api.request('/hang');
        const settled = requestPromise.catch((e) => e);

        // Advance past the configured timeout
        await vi.advanceTimersByTimeAsync(600);

        const err = await settled;
        expect(err).toBeInstanceOf(Error);

        vi.useRealTimers();
    });

    it('aborts on timeout when AbortSignal.any is present', async () => {
        // Keep AbortSignal.any intact — tests the normal path
        vi.useFakeTimers();

        const fetchMock = vi.fn().mockImplementation(
            (_url, opts) =>
                new Promise((_resolve, reject) => {
                    opts?.signal?.addEventListener('abort', () =>
                        reject(new DOMException('Aborted', 'AbortError'))
                    );
                })
        );
        vi.stubGlobal('fetch', fetchMock);

        const { api } = await loadModule();
        api.config = { ...api.config, timeout: 500, retryAttempts: 1 };

        const requestPromise = api.request('/slow');
        const settled = requestPromise.catch((e) => e);

        await vi.advanceTimersByTimeAsync(600);
        const err = await settled;
        expect(err).toBeInstanceOf(Error);

        vi.useRealTimers();
    });
});
