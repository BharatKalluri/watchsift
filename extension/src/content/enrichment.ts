import { Card } from '../shared/types';
import { parserConfig, providerId, readField } from '../shared/parser-config';

export function detailMetadata(
  document: Document,
  url: string,
  card: Card,
): Pick<Card, 'raw_year' | 'duration'> | null {
  if (card.provider !== parserConfig.provider || providerId(url) !== card.provider_id) return null;
  const dialog = document.querySelector(parserConfig.detail.selector);
  if (readField(dialog, parserConfig.detail.title) !== card.title) return null;
  const raw_year = readField(dialog, parserConfig.detail.year);
  return raw_year ? { raw_year, duration: readField(dialog, parserConfig.detail.duration) } : null;
}

export function detailCard(document: Document, url: string): Card | null {
  const id = providerId(url);
  const title = readField(
    document.querySelector(parserConfig.detail.selector),
    parserConfig.detail.title,
  );
  if (!id || !title) return null;
  const card: Card = {
    request_id: id,
    provider: parserConfig.provider,
    provider_id: id,
    title,
    year: null,
    type: null,
  };
  const metadata = detailMetadata(document, url, card);
  return metadata ? { ...card, ...metadata } : null;
}
