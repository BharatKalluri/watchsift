// @vitest-environment jsdom
import { expect, it, vi } from 'vitest';
import { DEFAULT_CONFIGS, ParserSchema } from '../src/shared/parser-config';

it.each(Object.entries(DEFAULT_CONFIGS))('bundles valid selectors for %s', (provider, config) => {
  expect(ParserSchema.parse(config).provider).toBe(provider);
  for (const section of [config.cards, config.detail]) {
    document.querySelector(section.selector);
    for (const field of Object.values(section))
      if (Array.isArray(field))
        for (const source of field) document.querySelector(source.selector);
  }
  document.querySelector(config.cards.row_selector);
  if (config.cards.badge_container) document.querySelector(config.cards.badge_container);
  document.querySelector(config.detail.badge_container);
});

it.each(['netflix', 'primevideo'] as const)('selects bundled %s configuration from the page URL', async provider => {
  vi.stubGlobal('location', { href: `https://www.${provider}.com/` });
  try {
    vi.resetModules();
    const { parserConfig } = await import('../src/shared/parser-config');
    expect(parserConfig).toEqual(DEFAULT_CONFIGS[provider]);
  } finally {
    vi.unstubAllGlobals();
  }
});
