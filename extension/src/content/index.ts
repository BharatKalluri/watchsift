import { groupBy, throttle } from 'lodash-es';
import { parserConfig } from '../shared/parser-config';
import { extractCard, extractCards } from './cards';
import { detailCard, detailMetadata } from './enrichment';
import {
  Card,
  DEFAULTS,
  metadataKey,
  passes,
  Rating,
  Resolution,
  Settings,
  validSettings,
} from '../shared/types';

interface Tracked {
  card: Card;
  key: string;
  visible: boolean;
  rating: Rating | null;
  retryAt: number;
  pending: boolean;
  rendered?: string;
}
let settings = { ...DEFAULTS };
const cards = new Map<HTMLElement, Tracked>();
let flushing = false;
let scanning = false;

function clear(element: HTMLElement) {
  element.querySelector('.watchsift-badge')?.remove();
  element.classList.remove('watchsift-card', 'watchsift-dimmed');
}

function render(element: HTMLElement, tracked: Tracked) {
  if (!settings.enabled || !tracked.rating) {
    clear(element);
    tracked.rendered = undefined;
    return;
  }
  const container =
    (parserConfig.cards.badge_container &&
      element.querySelector(parserConfig.cards.badge_container)) ||
    element;
  let badge = element.querySelector<HTMLAnchorElement>('.watchsift-badge');
  const dimmed = settings.filtering && !passes(tracked.rating, settings);
  // React can replace the host's classes while keeping our badge node.
  if (!element.classList.contains('watchsift-card')) element.classList.add('watchsift-card');
  if (element.classList.contains('watchsift-dimmed') !== dimmed)
    element.classList.toggle('watchsift-dimmed', dimmed);
  const rendered = JSON.stringify([
    tracked.rating,
    settings.filtering,
    settings.minRating,
    settings.minVotes,
  ]);
  // Hover mutations must not rewrite every badge or restart its transition.
  if (badge?.parentElement === container && tracked.rendered === rendered) return;
  if (!badge) {
    badge = document.createElement('a');
    badge.className = 'watchsift-badge';
    badge.target = '_blank';
    badge.rel = 'noopener noreferrer';
    badge.addEventListener('click', (event) => event.stopPropagation());
  }
  if (badge.parentElement !== container) container.append(badge);
  const { rating, votes, imdb_id } = tracked.rating;
  const compactVotes = new Intl.NumberFormat('en', {
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(votes);
  badge.href = `https://www.imdb.com/title/${imdb_id}/`;
  badge.textContent = `${rating.toFixed(1)} · ${compactVotes} votes`;
  badge.setAttribute(
    'aria-label',
    `IMDb ${rating.toFixed(1)} out of 10, ${votes.toLocaleString('en')} rating votes. Open IMDb in a new tab.`,
  );
  badge.title = `IMDb ${rating.toFixed(1)} · ${votes.toLocaleString('en')} votes`;
  tracked.rendered = rendered;
}

const schedule = throttle(
  () => {
    void (async () => {
      if (scanning) {
        schedule();
        return;
      }
      scanning = true;
      try {
        await nextFrame();
        await scan();
      } finally {
        scanning = false;
      }
      await flush();
    })().catch(() => {
      /* Extension may have been reloaded. */
    });
  },
  120,
  { leading: false },
);

const visibility = new IntersectionObserver(
  (entries) => {
    for (const entry of entries) {
      const tracked = cards.get(entry.target as HTMLElement);
      if (tracked) tracked.visible = entry.isIntersecting;
    }
    schedule();
  },
  { rootMargin: '0px' },
);

async function nextFrame() {
  await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));
}

async function scan() {
  let writes = 0;
  const discovered = extractCards(document);
  const detail = detailCard(document, location.href);
  if (detail) {
    const metadata = [
      ...(document
        .querySelector(parserConfig.detail.selector)
        ?.querySelectorAll<HTMLElement>(parserConfig.detail.badge_container) || []),
    ].find((element) => element.getClientRects().length > 0);
    if (metadata) {
      let rating = metadata.querySelector<HTMLElement>(':scope > .watchsift-detail-rating');
      if (!rating) {
        rating = document.createElement('div');
        rating.className = 'watchsift-detail-rating';
        metadata.append(rating);
      }
      discovered.set(rating, detail);
      for (const [element, card] of discovered) {
        if (
          card.provider === detail.provider &&
          card.provider_id === detail.provider_id &&
          card.title === detail.title
        )
          discovered.set(element, {
            ...card,
            raw_year: detail.raw_year,
            duration: detail.duration,
          });
      }
    }
  }
  for (const [element] of cards) {
    if (!discovered.has(element)) {
      clear(element);
      visibility.unobserve(element);
      cards.delete(element);
      if (++writes % 20 === 0) await nextFrame();
    }
  }
  for (const [element, card] of discovered) {
    const previous = cards.get(element);
    const key = metadataKey(card);
    if (!previous || previous.key !== key) {
      clear(element);
      const tracked = {
        card,
        key,
        visible:
          element.classList.contains('watchsift-detail-rating') || (previous?.visible ?? false),
        rating: null,
        retryAt: 0,
        pending: false,
      };
      cards.set(element, tracked);
      visibility.observe(element);
    }
    render(element, cards.get(element)!);
    if (++writes % 20 === 0) await nextFrame();
  }
}

async function flush() {
  if (flushing || !settings.enabled) return;
  const batch = Object.values(
    groupBy(
      [...cards].filter(([, card]) => card.visible && !card.pending && card.retryAt <= Date.now()),
      ([, card]) => card.key,
    ),
  ).slice(0, 50);
  if (!batch.length) return;
  flushing = true;
  const payload = batch.map((group, index) => ({ ...group[0][1].card, request_id: String(index) }));
  for (const group of batch) for (const [, tracked] of group) tracked.pending = true;
  try {
    const reply = (await chrome.runtime.sendMessage({ action: 'resolve', cards: payload })) as {
      results?: Resolution[];
    };
    const resolved = reply.results || [];
    const results = new Map(resolved.map((result) => [result.request_id, result]));
    await nextFrame();
    let writes = 0;
    for (let index = 0; index < batch.length; index++) {
      const result = results.get(String(index));
      for (const [element, tracked] of batch[index]) {
        let current = element.classList.contains('watchsift-detail-rating')
          ? detailCard(document, location.href)
          : extractCard(element);
        if (current) {
          const detail = detailMetadata(document, location.href, current);
          if (detail) current = { ...current, ...detail };
        }
        if (cards.get(element) !== tracked || !current || metadataKey(current) !== tracked.key) {
          clear(element);
          continue;
        }
        tracked.rating = result?.rating || null;
        tracked.retryAt = result ? Infinity : Date.now() + 30000;
        render(element, tracked);
        if (++writes % 20 === 0) await nextFrame();
      }
    }
  } catch {
    for (const group of batch)
      for (const [element, tracked] of group) {
        tracked.rating = null;
        tracked.retryAt = Date.now() + 30000;
        if (cards.get(element) === tracked) clear(element);
      }
  } finally {
    for (const group of batch) for (const [, tracked] of group) tracked.pending = false;
    flushing = false;
  }
  const immediate = [...cards.values()].some((c) => c.visible && !c.pending && c.retryAt === 0);
  if (immediate) schedule();
}

chrome.runtime.onMessage.addListener((message, sender) => {
  if (sender.id !== chrome.runtime.id) return;
  if (message?.action === 'preferences' && validSettings(message.settings)) {
    settings = message.settings;
    for (const tracked of cards.values()) {
      tracked.rendered = undefined;
    }
    schedule();
  }
});

async function initialize() {
  try {
    const preferences = await chrome.runtime.sendMessage({ action: 'preferences' });
    if (validSettings(preferences)) settings = preferences;
  } catch {
    /* Use defaults if preferences are unavailable. */
  }
  observe();
  schedule();
}

function observe() {
  new MutationObserver((mutations) => {
    if (
      mutations.some((mutation) => {
        const target =
          mutation.target instanceof Element ? mutation.target : mutation.target.parentElement;
        if (mutation.type === 'attributes' && mutation.attributeName === 'class') {
          const tracked = cards.get(target as HTMLElement);
          if (tracked?.rating && settings.enabled) render(target as HTMLElement, tracked);
          return false;
        }
        if (target?.closest('.watchsift-badge, .watchsift-detail-rating')) return false;
        // Prime's preview player updates continuously without changing title identity.
        if (
          parserConfig.provider === 'primevideo' &&
          target?.closest('[data-testid="draper-player"]')
        )
          return false;
        if (
          mutation.type === 'childList' &&
          [...mutation.addedNodes, ...mutation.removedNodes].every(
            (node) =>
              node instanceof Element &&
              (node.classList.contains('watchsift-badge') ||
                node.classList.contains('watchsift-detail-rating')),
          )
        )
          return false;
        return true;
      })
    )
      schedule();
  }).observe(document.body, {
    childList: true,
    characterData: true,
    subtree: true,
    attributes: true,
    attributeFilter: [...parserConfig.watched_attributes, 'class'],
  });
}

void initialize().catch(() => {
  /* Keep the streaming site usable if the extension is reloaded. */
});

setInterval(schedule, 30000);
window.addEventListener('popstate', schedule);
window.addEventListener('resize', schedule);
document.addEventListener('visibilitychange', schedule);
