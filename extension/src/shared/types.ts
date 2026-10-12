import { z } from 'zod';
import { validProviderId } from './providers';

// MV3 forbids generated code; use Zod's interpreted validators.
z.config({ jitless: true });

export const SettingsSchema = z.object({
  enabled: z.boolean(),
  filtering: z.boolean(),
  minRating: z.number().min(0).max(10),
  minVotes: z.int().min(0).max(1000000000),
});
export type Settings = z.infer<typeof SettingsSchema>;
export const DEFAULTS: Settings = {
  enabled: true,
  filtering: false,
  minRating: 7,
  minVotes: 1000,
};

const raw = z.string().max(300).nullish();
export const CardSchema = z
  .object({
    request_id: z.string().min(1).max(64),
    provider: z.enum(['netflix', 'primevideo']),
    provider_id: z.string().min(1).max(26),
    title: z
      .string()
      .max(300)
      .refine((title) => title.trim().length > 0),
    year: z.int().min(1870).max(2100).nullable(),
    type: z.enum(['movie', 'series']).nullable(),
    raw_year: raw,
    duration: raw,
    row_label: raw,
    explicit_type: raw,
  })
  .refine((card) => validProviderId(card.provider, card.provider_id));
export type Card = z.infer<typeof CardSchema>;

const RatingSchema = z.object({
  imdb_id: z.string().regex(/^tt\d+$/),
  rating: z.number().min(0).max(10),
  votes: z.int().min(0),
});
export type Rating = z.infer<typeof RatingSchema>;
const ResolutionSchema = z.discriminatedUnion('status', [
  z.object({ request_id: z.string(), status: z.literal('matched'), rating: RatingSchema }),
  z.object({
    request_id: z.string(),
    status: z.enum(['ambiguous', 'not_found']),
    rating: z.null(),
  }),
]);
export type Resolution = z.infer<typeof ResolutionSchema>;
const ResponseSchema = z.object({
  results: z.array(ResolutionSchema),
  dataset_version: z.string().min(1).max(100),
  dataset_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
  matcher_version: z.string().min(1).max(32),
});
export type ResolveResponse = z.infer<typeof ResponseSchema>;

export const validSettings = (value: unknown): value is Settings =>
  SettingsSchema.safeParse(value).success;
export const validCard = (value: unknown): value is Card => CardSchema.safeParse(value).success;

export function metadataKey(c: Card): string {
  return JSON.stringify([
    c.provider,
    c.provider_id,
    c.title,
    c.year,
    c.type,
    c.raw_year,
    c.duration,
    c.row_label,
    c.explicit_type,
  ]);
}

export function passes(rating: Rating, settings: Settings): boolean {
  return rating.rating >= settings.minRating && rating.votes >= settings.minVotes;
}

export function validResponse(value: unknown, cards: Card[]): value is ResolveResponse {
  const response = ResponseSchema.safeParse(value);
  if (!response.success || response.data.results.length !== cards.length) return false;
  const ids = new Set(cards.map((card) => card.request_id));
  return (
    ids.size === cards.length &&
    response.data.results.every((result) => ids.delete(result.request_id))
  );
}
