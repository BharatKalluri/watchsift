import { expect, it, vi } from 'vitest';
import { Engine } from '../src/background/engine';
import { Card, DEFAULTS } from '../src/shared/types';

const card: Card = { request_id: '0', provider: 'netflix', provider_id: '123', title: 'Unmatched Film', year: null, type: null };
const response = { results: [{ request_id: '0', status: 'not_found', rating: null }], dataset_version: 'test', dataset_date: '2026-10-11', matcher_version: '4' };

function storage() {
  const values: Record<string, unknown> = {};
  return { values, get: async () => structuredClone(values), set: async (next: Record<string, unknown>) => { Object.assign(values, structuredClone(next)); } };
}

it('looks up ratings on every call and after a worker restart without storing a cache', async () => {
  const store = storage(); const transport = vi.fn(async (_path: string) => response);
  const engine = new Engine(store, transport);
  expect((await engine.resolve([card])).status).toBe('Connected');
  await new Engine(store, transport).resolve([card]);
  expect(transport).toHaveBeenCalledTimes(2);
  expect(store.values.engine).not.toHaveProperty('cache');
  expect(transport.mock.calls[0][0]).toBe('/v1/resolve');
});

it('refreshes old ambiguous results after the matcher upgrade', async () => {
  const store = storage();
  await new Engine(store, async () => ({ ...response, matcher_version: '2' })).resolve([card]);
  const transport = vi.fn(async () => ({ ...response, results: [{ request_id: '0', status: 'matched', rating: { imdb_id: 'tt123', rating: 9, votes: 100000 } }] }));
  const result = await new Engine(store, transport).resolve([card]);
  expect(transport).toHaveBeenCalledTimes(1);
  expect(result.results[0].rating?.imdb_id).toBe('tt123');
});

it('backs off after a timeout and never fabricates results', async () => {
  const transport = vi.fn(async () => { throw new Error('timeout'); });
  const engine = new Engine(storage(), transport, () => 1000);
  expect((await engine.resolve([card])).results).toEqual([]);
  expect((await engine.resolve([card])).results).toEqual([]);
  expect(transport).toHaveBeenCalledTimes(1);
});
it('does not reuse a previously matched result when a fresh lookup fails', async () => {
  const store = storage();
  let offline = false;
  const engine = new Engine(store, async () => {
    if (offline) throw new Error('offline');
    return { ...response, results: [{ request_id: '0', status: 'matched', rating: { imdb_id: 'tt123', rating: 7, votes: 1000 } }] };
  }, () => 1000);
  await engine.resolve([card]);
  offline = true;
  const reply = await engine.resolve([card, { ...card, request_id: '1', provider_id: '456', title: 'Another Film' }]);
  expect(reply.results).toEqual([]);
  expect(store.values.engine).not.toHaveProperty('cache');
});

it('removes legacy telemetry and cache data while preserving preferences and backoff', async () => {
  const store = storage();
  store.values.engine = { status: 'Connected · IMDb data 2026-10-11', retryAt: 30000, cache: {}, metrics: [{}], pending: [card], history: [{ report: card }], daily: { day: '2026-10-12', keys: ['title'] }, telemetryRetryAt: 90000 };
  store.values.settings = { ...DEFAULTS, filtering: true, analytics: true, diagnostics: true };
  const transport = vi.fn(async () => response);
  const engine = new Engine(store, transport, () => 1000);
  await engine.initialize();
  expect(store.values.engine).toEqual({ status: 'Connected', retryAt: 30000 });
  expect(store.values.settings).toEqual({ ...DEFAULTS, filtering: true });
  await engine.resolve([card]);
  expect(transport).not.toHaveBeenCalled();

});


it('keeps rating retry backoff across service worker restarts', async () => {
  const store = storage();
  let time = 1000;
  const failed = vi.fn(async () => { throw new Error('offline'); });
  await new Engine(store, failed, () => time).resolve([card]);
  const transport = vi.fn(async () => response);
  const restarted = new Engine(store, transport, () => time);
  expect((await restarted.resolve([card])).results).toEqual([]);
  expect(transport).not.toHaveBeenCalled();
  time += 30000;
  expect((await restarted.resolve([card])).results).toHaveLength(1);
  expect(transport).toHaveBeenCalledTimes(1);
});

it('serializes operations and keeps the queue usable after a failed operation', async () => {
  const engine = new Engine(storage(), async () => response);
  const order: number[] = [];
  const failed = engine.run(async () => { order.push(1); throw new Error('failed'); });
  const next = engine.run(async () => { order.push(2); return 2; });
  await expect(failed).rejects.toThrow('failed');
  await expect(next).resolves.toBe(2);
  expect(order).toEqual([1, 2]);
});

it('falls back to safe defaults for invalid stored preferences', async () => {
  const store = storage(); store.values.settings = { ...DEFAULTS, minRating: 99 };
  expect(await new Engine(store, async () => response).preferences()).toEqual(DEFAULTS);
});

it('makes only rating requests even with legacy sharing preferences', async () => {
  const store = storage();
  store.values.settings = { ...DEFAULTS, analytics: true, diagnostics: true };
  const transport = vi.fn(async (_path: string) => response);
  const engine = new Engine(store, transport);
  await engine.resolve([card]);
  await engine.resolve([card]);
  expect(transport.mock.calls.map(call => call[0])).toEqual(['/v1/resolve', '/v1/resolve']);
  expect(Object.keys(store.values.engine as object).sort()).toEqual(['retryAt', 'status']);
});
