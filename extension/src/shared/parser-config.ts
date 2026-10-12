import { z } from 'zod';
import bundled from '../../../backend/src/catalogue/netflix.json';
import primevideo from '../../../backend/src/catalogue/primevideo.json';
import { providerForUrl, validProviderId } from './providers';

z.config({ jitless: true });
const selector = z.string().min(1).max(1000);
const attribute = z.string().regex(/^[a-zA-Z][a-zA-Z0-9_-]{0,63}$/);
const SourceSchema = z.discriminatedUnion('read', [
  z.object({ selector, read: z.literal('text'), attribute: attribute.optional() }),
  z.object({ selector, read: z.literal('attribute'), attribute }),
]);
type Source = z.infer<typeof SourceSchema>;
const sources = z.array(SourceSchema).min(1).max(8);
export const ParserSchema = z.object({
  schema_version: z.literal(1),
  config_version: z.int().positive(),
  provider: z.enum(['netflix', 'primevideo']),
  identity: z.object({
    path_prefixes: z.array(attribute).min(1).max(8),
    query_parameter: attribute.optional(),
  }),
  cards: z.object({
    selector,
    badge_container: selector.optional(),
    title: sources,
    link: sources,
    id: z.array(SourceSchema).max(8),
    year: sources,
    explicit_type: sources,
    row_selector: selector,
    row_label: sources,
  }),
  detail: z.object({
    selector,
    title: sources,
    year: sources,
    duration: sources,
    badge_container: selector,
  }),
  watched_attributes: z
    .array(attribute)
    .max(32)
    .refine((attributes) => !attributes.includes('class')),
});
export type ParserConfig = z.infer<typeof ParserSchema>;
export const DEFAULT_CONFIG = ParserSchema.parse(bundled);
export const DEFAULT_CONFIGS = {
  netflix: DEFAULT_CONFIG,
  primevideo: ParserSchema.parse(primevideo),
};
export const parserConfig =
  DEFAULT_CONFIGS[(typeof location !== 'undefined' && providerForUrl(location.href)) || 'netflix'];
export function readField(
  element: Element | null,
  sources: Source[],
  maxLength = 300,
): string | null {
  if (!element) return null;
  for (const source of sources) {
    const target = source.selector === ':scope' ? element : element.querySelector(source.selector);
    const value = (
      source.read === 'text' ? target?.textContent : target?.getAttribute(source.attribute!)
    )?.trim();
    if (value && value.length <= maxLength) return value;
  }
  return null;
}

export function providerId(url: string): string | null {
  if (!url) return null;
  try {
    const current = new URL(url, location.href);
    if (providerForUrl(current.href) !== parserConfig.provider) return null;
    const parts = current.pathname.split('/');
    if (parserConfig.provider === 'primevideo' && parts[1] === 'region') parts.splice(1, 2);
    const id = parserConfig.identity.path_prefixes.includes(parts[1])
      ? parts[2]
      : parserConfig.identity.query_parameter
        ? current.searchParams.get(parserConfig.identity.query_parameter)
        : null;
    return id && validProviderId(parserConfig.provider, id) ? id : null;
  } catch {
    return null;
  }
}
