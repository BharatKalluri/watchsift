import { Engine } from './engine';
import { request } from './api';
import { cardsForProvider, senderRole } from './messages';
import { z } from 'zod';
import { CardSchema, SettingsSchema } from '../shared/types';

// Only transient coordination lives in Engine; preferences and backoff live in storage.
const engine = new Engine(chrome.storage.local, request);
const storageReady = (async () => {
  await chrome.storage.local.setAccessLevel({ accessLevel: 'TRUSTED_CONTEXTS' });
  await chrome.storage.local.remove('netflixMetadata');
  await engine.run(() => engine.initialize());
})();
void storageReady.catch(() => console.warn('WatchSift storage initialization failed'));

const allowed = {
  netflix: ['preferences', 'resolve'],
  primevideo: ['preferences', 'resolve'],
  popup: ['settings', 'status'],
};
const CardsSchema = z.array(CardSchema).min(1).max(50);

chrome.runtime.onMessage.addListener((message, sender, reply) => {
  const role = senderRole(sender, chrome.runtime.id, chrome.runtime.getURL('popup.html'));
  if (!role || !allowed[role].includes(message?.action)) return;
  let operation: () => Promise<unknown>;
  switch (message.action) {
    case 'preferences':
      operation = () => engine.preferences();
      break;
    case 'resolve': {
      const cards = CardsSchema.safeParse(message.cards);
      if (!cards.success || role === 'popup' || !cardsForProvider(cards.data, role)) return;
      operation = () => engine.run(() => engine.resolve(cards.data));
      break;
    }
    case 'settings': {
      const settings = SettingsSchema.safeParse(message.settings);
      if (!settings.success) return;
      operation = async () => {
        await chrome.storage.local.set({ settings: settings.data });
        return { saved: true };
      };
      break;
    }
    case 'status':
      operation = () => engine.run(() => engine.status());
      break;
    default:
      return;
  }
  void (async () => {
    try {
      await storageReady;
      reply(await operation());
    } catch {
      reply({ error: 'WatchSift could not complete this request' });
    }
  })();
  return true;
});

chrome.storage.onChanged.addListener((changes, area) => {
  if (area !== 'local' || !changes.settings) return;
  void (async () => {
    await storageReady;
    const settings = await engine.preferences();
    const tabs = await chrome.tabs.query({});
    await Promise.allSettled(
      tabs.map(async (tab) => {
        if (tab.id === undefined) return;
        // Only our statically injected streaming-site scripts can receive this message; no URL access needed.
        await chrome.tabs.sendMessage(tab.id, { action: 'preferences', settings }, { frameId: 0 });
      }),
    );
  })().catch(() => console.warn('WatchSift could not update preferences'));
});
