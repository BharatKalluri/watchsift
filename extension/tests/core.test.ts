import { describe, expect, it, vi } from 'vitest';
import { Card, DEFAULTS, passes, validCard, validResponse, validSettings } from '../src/shared/types';

const card: Card = { request_id: '0', provider: 'netflix', provider_id: '123', title: 'A Film', year: 2020, type: 'movie' };
const response = { results: [{ request_id: '0', status: 'matched' as const, rating: { imdb_id: 'tt123', rating: 7, votes: 1000 } }], dataset_version: 'test', dataset_date: '2026-10-11', matcher_version: '1' };

describe('inclusive AND filter', () => {
  it('defaults to badges on, filtering and consent off, 7.0 and 1,000 votes', () => {
    expect(DEFAULTS).toEqual({ enabled: true, filtering: false, minRating: 7, minVotes: 1000 });
    expect(passes({ imdb_id: 'tt1', rating: 7, votes: 1000 }, DEFAULTS)).toBe(true);
    expect(passes({ imdb_id: 'tt1', rating: 6.9, votes: 100000 }, DEFAULTS)).toBe(false);
    expect(passes({ imdb_id: 'tt1', rating: 9, votes: 999 }, DEFAULTS)).toBe(false);
  });
  it('rejects invalid thresholds and malformed/duplicate API results', () => {
    expect(validSettings({ ...DEFAULTS, minRating: NaN })).toBe(false);
    expect(validSettings({ ...DEFAULTS, minVotes: -1 })).toBe(false);
    expect(validResponse(response, [card])).toBe(true);
    expect(validResponse({ ...response, results: [{ ...response.results[0], rating: { imdb_id: 'javascript:alert(1)', rating: 7, votes: 1000 } }] }, [card])).toBe(false);
    expect(validResponse({ ...response, results: [] }, [card])).toBe(false);
  });
});


it('validates untrusted data without generated code or losing boundary checks', () => {
  const dynamicCode = vi.spyOn(globalThis, 'Function').mockImplementation(() => {
    throw new Error('MV3 blocks generated code');
  });
  try {
    expect(validCard({ ...card, raw_year: null, duration: '1h 30m' })).toBe(true);
    for (const invalid of [
      { ...card, request_id: '' }, { ...card, provider_id: '123x' },
      { ...card, title: ' ' }, { ...card, year: 2020.5 },
      { ...card, year: 2101 }, { ...card, duration: 'x'.repeat(301) },
      { ...card, type: 'episode' },
    ]) expect(validCard(invalid)).toBe(false);
    for (const minVotes of [Infinity, 1.5, Number.MAX_SAFE_INTEGER + 1])
      expect(validSettings({ ...DEFAULTS, minVotes })).toBe(false);
    expect(validResponse(response, [card])).toBe(true);
    for (const rating of [
      { imdb_id: 'tt1', rating: Infinity, votes: 1 },
      { imdb_id: 'tt1', rating: 7, votes: 1.5 },
      { imdb_id: 'tt1', rating: -1, votes: 1 },
    ]) expect(validResponse({ ...response, results: [{ request_id: '0', status: 'matched', rating }] }, [card])).toBe(false);
    expect(validResponse({ ...response, results: [{ request_id: '0', status: 'ambiguous', rating: response.results[0].rating }] }, [card])).toBe(false);
    const second = { ...card, request_id: '1' };
    expect(validResponse({ ...response, results: [response.results[0], response.results[0]] }, [card, second])).toBe(false);
    expect(dynamicCode).not.toHaveBeenCalled();
  } finally { dynamicCode.mockRestore(); }
});
