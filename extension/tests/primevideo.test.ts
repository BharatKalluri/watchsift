// @vitest-environment jsdom
import { readFileSync } from 'node:fs';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
let { extractCard, extractCards } = await import('../src/content/cards');
let { detailCard, detailMetadata } = await import('../src/content/enrichment');
let { providerId } = await import('../src/shared/parser-config');
import { metadataKey, validCard } from '../src/shared/types';

beforeEach(async () => {
  vi.stubGlobal('location', {href: 'https://www.primevideo.com/region/eu/storefront'});
  vi.resetModules();
  ({ extractCard, extractCards } = await import('../src/content/cards'));
  ({ detailCard, detailMetadata } = await import('../src/content/enrichment'));
  ({ providerId } = await import('../src/shared/parser-config'));
  document.body.innerHTML = readFileSync('tests/fixtures/primevideo.html', 'utf8');
});
afterEach(() => { document.body.innerHTML = ''; vi.unstubAllGlobals(); });

it('reads standard, poster and hero titles without season-art labels or unsupported tiles', () => {
  const cards = extractCards(document);
  expect([...cards.keys()].map(e => e.id)).toEqual(['prime-good', 'prime-low', 'prime-unknown', 'prime-poster', 'prime-hero', 'prime-lazy']);
  expect([...cards.values()].every(validCard)).toBe(true);
  expect(cards.get(document.getElementById('prime-poster')!)?.title).toBe('The Shawshank Redemption');
  expect(cards.get(document.getElementById('prime-hero')!)?.title).toBe('The Shawshank Redemption');
  expect(cards.get(document.getElementById('prime-good')!)).toMatchObject({provider: 'primevideo', provider_id: '0SC64NC24QA7M9AFWBEK87WWS0', explicit_type: 'Movie', row_label: 'Movies'});
  for (const entity of ['EVENT', 'Episode', 'Trailer']) {
    const element = document.getElementById('prime-hero')!;
    element.setAttribute('data-card-entity-type', entity);
    expect(extractCard(element)).toBeNull();
  }
});

it('uses scoped title fallbacks and notices recycled titles, IDs and entity types', () => {
  const element = document.getElementById('prime-good')!;
  element.removeAttribute('data-card-title');
  expect(extractCard(element)?.title).toBe('The Shawshank Redemption');
  element.querySelector('button')!.remove();
  expect(extractCard(element)?.title).toBe('The Shawshank Redemption');
  const original = metadataKey(extractCard(element)!);
  element.querySelector('a')!.setAttribute('href', 'https://primevideo.com/detail/B000000009?tracking=private');
  expect(metadataKey(extractCard(element)!)).not.toBe(original);
  expect(JSON.stringify(extractCard(element))).not.toContain('tracking');
  element.setAttribute('data-card-entity-type', 'TV Show');
  expect(extractCard(element)?.explicit_type).toBe('TV Show');
});

it('accepts regional and bare-host identities but rejects malformed and foreign URLs', () => {
  for (const url of ['https://www.primevideo.com/detail/B000000001?ref_=x', 'https://primevideo.com/dp/B000000001', 'https://www.primevideo.com/region/eu/detail/B000000001']) expect(providerId(url)).toBe('B000000001');
  for (const url of ['https://www.primevideo.com/detail/lowercase1', 'https://www.primevideo.com/detail/short', 'https://primevideo.com.evil.example/detail/B000000001', 'http://primevideo.com/detail/B000000001', 'https://netflix.com/title/123', 'https://primevideo.com/search?phrase=B000000001']) expect(providerId(url)).toBeNull();
});

it('reads movie and series details and attaches metadata only to the same provider, ID and title', () => {
  document.body.innerHTML = '<main data-testid="detailpage-main"><h1><img alt="The Matrix"></h1><div data-testid="dp-atf-badges"><span data-automation-id="release-year-badge">1999</span><span data-automation-id="runtime-badge">2 h 10 min</span></div></main>';
  const url = 'https://primevideo.com/region/eu/detail/B000000001';
  const card = detailCard(document, url)!;
  expect(card).toMatchObject({provider: 'primevideo', provider_id: 'B000000001', title: 'The Matrix', raw_year: '1999', duration: '2 h 10 min'});
  expect(detailMetadata(document, url, {...card, provider_id: 'B000000002'})).toBeNull();
  expect(detailMetadata(document, url, {...card, provider: 'netflix'})).toBeNull();
  expect(detailMetadata(document, url, {...card, title: 'Another title'})).toBeNull();
  document.querySelector('h1')!.innerHTML = 'The Terminal List';
  document.querySelector('[data-automation-id="runtime-badge"]')!.outerHTML = '<span aria-label="2 seasons">2 seasons</span>';
  expect(detailCard(document, url)).toMatchObject({title: 'The Terminal List', duration: '2 seasons'});
});


it('keeps lookup metadata stable when hover details appear and disappear', () => {
  const element = document.getElementById('prime-good')!;
  const before = metadataKey(extractCard(element)!);
  const details = document.createElement('div');
  details.dataset.testid = 'standard-mini-details';
  details.innerHTML = '<span data-automation-id="release-year-badge">1994</span>';
  element.append(details);
  expect(metadataKey(extractCard(element)!)).toBe(before);
  details.remove();
  expect(metadataKey(extractCard(element)!)).toBe(before);
});
