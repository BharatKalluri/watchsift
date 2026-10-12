import { Provider, providerForUrl } from '../shared/providers';
import { Card } from '../shared/types';

export function senderRole(
  sender: chrome.runtime.MessageSender,
  extensionId: string,
  popupUrl: string,
): 'popup' | Provider | null {
  if (sender.id !== extensionId) return null;
  if (sender.url === popupUrl) return 'popup';
  return sender.tab && sender.frameId === 0 ? providerForUrl(sender.url || '') : null;
}

export function cardsForProvider(cards: Card[], provider: Provider): boolean {
  return cards.every((card) => card.provider === provider);
}
