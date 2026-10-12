import { expect, it } from 'vitest';
import { senderRole } from '../src/background/messages';

const id = 'our-extension';
const popup = `chrome-extension://${id}/popup.html`;
const netflix = { id, url: 'https://www.netflix.com/browse', frameId: 0, tab: { id: 1 } } as chrome.runtime.MessageSender;

it('accepts only the exact popup or our top-frame Netflix content script', () => {
  expect(senderRole({ id, url: popup }, id, popup)).toBe('popup');
  expect(senderRole({ ...netflix, url: popup }, id, popup)).toBe('popup');
  expect(senderRole(netflix, id, popup)).toBe('netflix');
  expect(senderRole({ ...netflix, url: 'https://netflix.com/browse' }, id, popup)).toBe('netflix');
  for (const sender of [
    { ...netflix, id: 'other-extension' }, { ...netflix, frameId: 1 },
    { ...netflix, url: 'https://netflix.com.evil.example/browse' },
    { ...netflix, url: 'http://netflix.com/browse' },
    { id, url: `chrome-extension://${id}/other.html` },
    { id, url: 'https://www.netflix.com/browse' },
    { id: 'other-extension', url: popup },
  ]) expect(senderRole(sender, id, popup)).toBeNull();
});

it('authorizes only Prime top frames and rejects cross-provider resolve batches', async () => {
  const { cardsForProvider } = await import('../src/background/messages');
  const { validCard } = await import('../src/shared/types');
  expect(senderRole({...netflix, url: 'https://www.primevideo.com/region/eu/storefront'}, id, popup)).toBe('primevideo');
  expect(senderRole({...netflix, url: 'https://primevideo.com/detail/B000000001'}, id, popup)).toBe('primevideo');
  for (const sender of [
    {...netflix, url: 'https://primevideo.com.evil.example/'},
    {...netflix, url: 'https://www.primevideo.com/', frameId: 1},
    {...netflix, url: 'http://primevideo.com/'},
    {...netflix, url: 'https://primevideo.com:8443/'},
  ]) expect(senderRole(sender, id, popup)).toBeNull();
  const card = {request_id: '0', provider: 'primevideo' as const, provider_id: 'B000000001', title: 'Film', year: null, type: null};
  expect(validCard(card)).toBe(true);
  expect(validCard({...card, provider_id: '123'})).toBe(false);
  expect(cardsForProvider([card], 'primevideo')).toBe(true);
  expect(cardsForProvider([card], 'netflix')).toBe(false);
});
