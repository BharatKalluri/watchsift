import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { request } from '../src/background/api';
import { ResponseSizeError } from 'ky';

beforeEach(() => vi.stubGlobal('__API_ORIGIN__', 'http://127.0.0.1:8000'));
afterEach(() => vi.unstubAllGlobals());

it('fetches only its backend with no credentials, caching or redirects', async () => {
  const fetchMock = vi.fn(async (sent: Request) => {
    expect(await sent.json()).toEqual({});
    return new Response(JSON.stringify({ accepted: 1 }));
  });
  vi.stubGlobal('fetch', fetchMock);
  expect(await request('/v1/resolve', {}, AbortSignal.timeout(5000))).toEqual({ accepted: 1 });
  const sent = fetchMock.mock.calls[0][0];
  expect(sent).toMatchObject({ url: 'http://127.0.0.1:8000/v1/resolve', method: 'POST', credentials: 'omit', cache: 'no-store', redirect: 'error', referrerPolicy: 'no-referrer' });
  expect(sent.headers.get('Content-Type')).toBe('application/json');
});

it.each(['Wed, 21 Oct 2099 07:28:00 GMT', 'invalid', null])('handles Retry-After %s without retrying in memory', async retry => {
  const headers = new Headers();
  if (retry) headers.set('Retry-After', retry);
  const fetchMock = vi.fn(async () => new Response('', { status: 503, headers }));
  vi.stubGlobal('fetch', fetchMock);
  const seconds = retry?.includes('GMT') ? (Date.parse(retry) - Date.now()) / 1000 : 30;
  await expect(request('/v1/resolve', {}, AbortSignal.timeout(5000))).rejects.toMatchObject({ retrySeconds: expect.closeTo(seconds, 0) });
  expect(fetchMock).toHaveBeenCalledTimes(1);
});

it('forwards caller cancellation while reading a stalled response body', async () => {
  vi.stubGlobal('fetch', vi.fn(async (sent: Request) => new Response(new ReadableStream({
    start(controller) {
      controller.enqueue(new TextEncoder().encode('{'));
      sent.signal.addEventListener('abort', () => controller.error(sent.signal.reason), { once: true });
    },
  }))));
  await expect(request('/v1/resolve', {}, AbortSignal.timeout(20))).rejects.toMatchObject({ name: 'TimeoutError' });
});

it('bounds response bytes while reading rather than after downloading the body', async () => {
  let cancelled = false;
  const body = new ReadableStream({
    start(controller) { controller.enqueue(new Uint8Array(100001)); },
    cancel() { cancelled = true; },
  });
  vi.stubGlobal('fetch', vi.fn(async () => new Response(body)));
  await expect(request('/v1/resolve', {}, AbortSignal.timeout(5000))).rejects.toBeInstanceOf(ResponseSizeError);
  expect(cancelled).toBe(true);
});

it('honors numeric Retry-After', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response('', { status: 429, headers: { 'Retry-After': '60' } })));
  await expect(request('/v1/resolve', {}, AbortSignal.timeout(5000))).rejects.toMatchObject({ retrySeconds: 60 });
});
