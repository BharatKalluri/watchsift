// @vitest-environment jsdom
import { beforeEach, expect, it } from 'vitest';
import { detailCard, detailMetadata } from '../src/content/enrichment';
import { Card } from '../src/shared/types';

const card: Card = { request_id: '123', provider: 'netflix', provider_id: '123', title: 'East of Eden', year: null, type: null };
const url = 'https://www.netflix.com/browse?jbv=123';
const details = () => `<div role="dialog" data-uia="modal-motion-container-DETAIL_MODAL"><img src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7" alt="East of Eden"><div data-uia="videoMetadata--container"><div class="year">2026</div><span class="duration">Limited Series</span></div><div class="year">1981</div><span data-uia="previewModal-closebtn" role="button" aria-label="close"></span></div>`;
beforeEach(() => { document.body.innerHTML = ''; });

it('reads the main detail year and type, rejecting unrelated IDs, titles and hover previews', () => {
  document.body.innerHTML = details();
  expect(detailMetadata(document, url, card)).toMatchObject({ raw_year: '2026', duration: 'Limited Series' });
  expect(detailMetadata(document, url, { ...card, provider_id: '456' })).toBeNull();
  expect(detailMetadata(document, url, { ...card, title: 'Other' })).toBeNull();
  document.querySelector('.duration')!.textContent = '2h 4m';
  expect(detailMetadata(document, url, card)?.duration).toBe('2h 4m');
  document.querySelector('[data-uia="videoMetadata--container"] .year')!.remove();
  expect(detailMetadata(document, url, card)).toBeNull();
});

it('extracts a user-opened detail card without requiring its grid card', () => {
  document.body.innerHTML = details();
  expect(detailCard(document, url)).toEqual({ ...card, raw_year: '2026', duration: 'Limited Series' });
  expect(detailCard(document, 'https://www.netflix.com/browse')).toBeNull();
  document.querySelector('.year')!.textContent = 'wrong';
  expect(detailCard(document, url)?.raw_year).toBe('wrong');
});


it('skips decorative empty-alt images before the main Netflix title', () => {
  document.body.innerHTML = details();
  const image = document.createElement('img'); image.alt = '';
  document.querySelector('[role="dialog"]')!.prepend(image);
  expect(detailCard(document, url)).toMatchObject({ title: 'East of Eden', raw_year: '2026', duration: 'Limited Series' });
});
