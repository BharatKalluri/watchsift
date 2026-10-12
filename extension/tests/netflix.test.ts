// @vitest-environment jsdom
import { beforeEach, expect, it } from 'vitest';
import { extractCard, extractCards } from '../src/content/cards';
import { parserConfig } from '../src/shared/parser-config';

beforeEach(() => { document.body.innerHTML = ''; });
it('extracts fallback text and jbv IDs without guessing absent metadata', () => {
  document.body.innerHTML = '<div class="title-card"><a href="https://www.netflix.com/browse?jbv=123"><img alt=""><span class="fallback-text">കുമ്പളങ്ങി നൈറ്റ്സ്</span></a></div>';
  expect(extractCard(document.querySelector('div')!)).toMatchObject({ request_id: '123', provider: 'netflix', provider_id: '123', title: 'കുമ്പളങ്ങി നൈറ്റ്സ്', year: null, type: null });
});
it('reads title links and explicit year/type, including changed cards', () => {
  document.body.innerHTML = '<div class="title-card" data-year="2019" data-type="movie"><a href="https://www.netflix.com/title/123"><img alt="Super Deluxe"></a></div>';
  const card = document.querySelector('div')!;
  expect(extractCard(card)?.title).toBe('Super Deluxe');
  card.querySelector('img')!.alt = 'Another Film';
  card.querySelector('a')!.href = 'https://www.netflix.com/watch/456';
  expect(extractCard(card)?.provider_id).toBe('456');
  expect(extractCard(card)?.raw_year).toBe('2019');
});
it('leaves unsupported or nameless cards alone', () => {
  document.body.innerHTML = '<div><a href="https://www.netflix.com/browse"><img alt="Film"></a></div>';
  expect(extractCard(document.querySelector('div')!)).toBeNull();
});
it('reads accessible card titles when fallback text and image alt are empty', () => {
  document.body.innerHTML = '<div class="title-card"><a href="https://netflix.com/browse?jbv=123" aria-label="Better Call Saul"><span class="fallback-text"> </span><img alt=""></a></div>';
  expect(extractCard(document.querySelector('div')!)?.title).toBe('Better Call Saul');
});
it('detects current Netflix standard and ranked wrappers without treating episodes as titles', () => {
  document.body.innerHTML = '<div><a data-uia="standard-card" href="https://www.netflix.com/browse?jbv=80021955" aria-label="Better Call Saul"><div><img alt=""></div></a></div><div><a data-uia="ranked-card" href="https://www.netflix.com/browse?jbv=82787383" aria-label="Mandaadi"><div><img alt=""></div></a></div><div><a data-uia="episodic-card" href="https://www.netflix.com/browse?jbv=80021956" aria-label="Uno"><img alt=""></a></div>';
  const cards = [...document.querySelectorAll<HTMLElement>(parserConfig.cards.selector)];
  expect(cards.map(element => extractCard(element)?.title)).toEqual(['Better Call Saul', 'Mandaadi']);
  expect(cards.every(element => element.tagName === 'DIV')).toBe(true);
});
it('sends row labels and explicit types without interpreting them locally', () => {
  document.body.innerHTML = '<section class="carousel-row"><h2>Critically Acclaimed TV Shows</h2><div class="title-card" data-type="series"><a href="https://www.netflix.com/browse?jbv=123" aria-label="Suits"></a></div></section>';
  expect([...extractCards(document).values()][0]).toMatchObject({ type: null, explicit_type: 'series', row_label: 'Critically Acclaimed TV Shows' });
});
it('isolates malformed links rather than breaking the card scan', () => {
  document.body.innerHTML = '<div><a href="http://[/watch/123"><img alt="Film"></a></div>';
  expect(extractCard(document.querySelector('div')!)).toBeNull();
});

it('reads provider IDs from long tracked links without transmitting the URL', () => {
  document.body.innerHTML = `<div class="title-card"><a href="https://www.netflix.com/browse?jbv=123&tracking=${'x'.repeat(500)}" aria-label="Film"></a></div>`;
  const card = extractCard(document.querySelector('div')!);
  expect(card?.provider_id).toBe('123');
  expect(JSON.stringify(card)).not.toContain('tracking');
});
