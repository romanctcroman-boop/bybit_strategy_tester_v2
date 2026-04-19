/**
 * ApiClient.js Unit Tests
 *
 * Covers bugs fixed in B-11:
 *   B-11 — Retry-After header is honoured on 429 responses
 *
 * Also covers core retry logic and error handling.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { ApiClient, ApiError } from '../../js/core/ApiClient.js';

// ─── helpers ──────────────────────────────────────────────────────────────────

function makeJsonResponse(body, status = 200, headers = {}) {
    return new Response(JSON.stringify(body), {
        status,
        headers: {
            'Content-Type': 'application/json',
            ...headers
        }
    });
}

function makeClient(overrides = {}) {
    // ApiClient(baseUrl, options) — baseUrl is the first arg, options second.
    // Keep timeout high so the abort signal never fires during fake-timer tests.
    return new ApiClient('', {
        timeout: 999999,
        retries: 2,
        retryDelay: 10,
        ...overrides
    });
}

// ─── Retry-After handling (B-11) ──────────────────────────────────────────────
describe('ApiClient Retry-After (B-11)', () => {
    let fetchMock;

    beforeEach(() => {
        vi.useFakeTimers();
        fetchMock = vi.fn();
        vi.stubGlobal('fetch', fetchMock);
    });

    afterEach(() => {
        vi.useRealTimers();
        vi.restoreAllMocks();
    });

    it('waits Retry-After seconds before retrying on 429', async () => {
        const retryAfterSeconds = 2; // 2000 ms

        // First call → 429 with Retry-After header; second call → 200
        fetchMock
            .mockResolvedValueOnce(
                makeJsonResponse({ detail: 'rate limited' }, 429, {
                    'Retry-After': String(retryAfterSeconds)
                })
            )
            .mockResolvedValueOnce(makeJsonResponse({ ok: true }, 200));

        const client = makeClient({ retries: 1, retryDelay: 50 });
        const requestPromise = client.get('/rate-limited');

        // Advance time by less than Retry-After — should NOT have retried yet
        await vi.advanceTimersByTimeAsync(1500);
        expect(fetchMock).toHaveBeenCalledTimes(1);

        // Advance past Retry-After — retry fires
        await vi.advanceTimersByTimeAsync(600);
        const result = await requestPromise;

        expect(fetchMock).toHaveBeenCalledTimes(2);
        expect(result).toEqual({ ok: true });
    });

    it('falls back to exponential backoff when Retry-After is absent on 429', async () => {
        fetchMock
            .mockResolvedValueOnce(makeJsonResponse({ detail: 'rate limited' }, 429))
            .mockResolvedValueOnce(makeJsonResponse({ ok: true }, 200));

        const retryDelay = 50;
        const client = makeClient({ retries: 1, retryDelay });
        const requestPromise = client.get('/no-retry-after');

        // Advance past the exponential delay for attempt 0: retryDelay * 2^0 = 50ms
        await vi.advanceTimersByTimeAsync(retryDelay + 10);
        const result = await requestPromise;

        expect(fetchMock).toHaveBeenCalledTimes(2);
        expect(result).toEqual({ ok: true });
    });

    it('attaches retryAfterMs to the ApiError', async () => {
        fetchMock.mockResolvedValue(
            makeJsonResponse({ detail: 'rate limited' }, 429, { 'Retry-After': '5' })
        );

        const client = makeClient({ retries: 0 }); // no retries → throws immediately
        await expect(client.get('/fail')).rejects.toMatchObject({
            status: 429,
            retryAfterMs: 5000
        });
    });

    it('does NOT retry on 400 Bad Request (client error, non-429)', async () => {
        fetchMock.mockResolvedValue(makeJsonResponse({ detail: 'bad input' }, 400));

        const client = makeClient({ retries: 3 });
        await expect(client.get('/bad')).rejects.toMatchObject({ status: 400 });

        // Should have been called exactly once — no retries for 400
        expect(fetchMock).toHaveBeenCalledTimes(1);
    });
});

// ─── Core request behaviour ───────────────────────────────────────────────────
describe('ApiClient core', () => {
    let fetchMock;

    beforeEach(() => {
        vi.useFakeTimers();
        fetchMock = vi.fn();
        vi.stubGlobal('fetch', fetchMock);
    });

    afterEach(() => {
        vi.useRealTimers();
        vi.restoreAllMocks();
    });

    it('returns parsed JSON on 200', async () => {
        fetchMock.mockResolvedValue(makeJsonResponse({ value: 42 }));
        const client = makeClient();
        const result = await client.get('/data');
        expect(result).toEqual({ value: 42 });
    });

    it('throws ApiError on 500', async () => {
        fetchMock.mockResolvedValue(makeJsonResponse({ detail: 'server error' }, 500));
        const client = makeClient({ retries: 0 });
        await expect(client.get('/fail')).rejects.toBeInstanceOf(ApiError);
    });

    it('retries on 500 up to maxRetries times', async () => {
        fetchMock.mockResolvedValue(makeJsonResponse({ detail: 'server error' }, 500));

        // retries: 2, retryDelay: 10 → delays are 10ms and 20ms (2^0 and 2^1)
        const client = makeClient({ retries: 2, retryDelay: 10 });

        // Attach rejection handler immediately to avoid "unhandled rejection" warning
        const p = client.get('/fail');
        const settled = p.catch((e) => e); // swallow for now

        // Advance through both retry delays: 10 + 20 = 30ms, add buffer
        await vi.advanceTimersByTimeAsync(200);

        // Now assert on the settled error
        const err = await settled;
        expect(err).toBeInstanceOf(ApiError);

        // Initial call + 2 retries = 3 total
        expect(fetchMock).toHaveBeenCalledTimes(3);
    });

    it('does not retry on abort', async () => {
        fetchMock.mockRejectedValue(
            Object.assign(new Error('Aborted'), { name: 'AbortError' })
        );
        const client = makeClient({ retries: 3 });
        await expect(client.get('/abort')).rejects.toThrow();
        expect(fetchMock).toHaveBeenCalledTimes(1);
    });
});

// ─── ApiError helpers ─────────────────────────────────────────────────────────
describe('ApiError', () => {
    it('isClientError returns true for 4xx', () => {
        expect(new ApiError(404, 'Not Found').isClientError()).toBe(true);
        expect(new ApiError(500, 'Server Error').isClientError()).toBe(false);
    });

    it('isServerError returns true for 5xx', () => {
        expect(new ApiError(503, 'Unavailable').isServerError()).toBe(true);
        expect(new ApiError(400, 'Bad').isServerError()).toBe(false);
    });
});
