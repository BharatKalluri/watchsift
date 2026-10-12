import { Card } from '../shared/types';
import { validProviderId } from '../shared/providers';
import { parserConfig, providerId, readField } from '../shared/parser-config';

export function extractCard(element: HTMLElement): Card | null {
  const config = parserConfig.cards;
  if (parserConfig.provider === 'primevideo') {
    const entity = element
      .closest('[data-card-entity-type]')
      ?.getAttribute('data-card-entity-type');
    if (entity && !['Movie', 'TV Show'].includes(entity)) return null;
  }
  const id =
    readField(element, config.id) || providerId(readField(element, config.link, 2048) || '');
  const title = readField(element, config.title);
  if (!id || !validProviderId(parserConfig.provider, id) || !title) return null;
  return {
    request_id: id,
    provider: parserConfig.provider,
    provider_id: id,
    title,
    year: null,
    type: null,
    raw_year: readField(element, config.year),
    explicit_type: readField(element, config.explicit_type),
    row_label: readField(element.closest(config.row_selector), config.row_label),
  };
}

export function extractCards(document: Document): Map<HTMLElement, Card> {
  const cards = new Map<HTMLElement, Card>();
  for (const element of document.querySelectorAll<HTMLElement>(parserConfig.cards.selector)) {
    const card = extractCard(element);
    if (card) cards.set(element, card);
  }
  return cards;
}
