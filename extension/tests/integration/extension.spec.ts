import { chromium, expect, test, BrowserContext, Page } from '@playwright/test';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { resolve, join } from 'node:path';

let context: BrowserContext;
let profile: string;
let page: Page;
let popup: Page;
const apiOrigin = process.env.WATCHSIFT_API_URL || 'http://127.0.0.1:8000';

test.beforeEach(async ({}, testInfo) => {
  profile = await mkdtemp(join(tmpdir(), 'watchsift-test-'));
  const extension = resolve('dist');
  context = await chromium.launchPersistentContext(profile, {
    channel: 'chromium', headless: true, viewport: { width: 1050, height: 720 },
    args: [`--disable-extensions-except=${extension}`, `--load-extension=${extension}`],
  });
  const worker = context.serviceWorkers()[0] || await context.waitForEvent('serviceworker');
  const id = new URL(worker.url()).hostname;
  const fixture = await readFile('tests/fixtures/netflix.html', 'utf8');
  await context.route('https://www.netflix.com/**', route => route.fulfill({ contentType: 'text/html', body: fixture }));
  await context.route('https://netflix.com/**', route => route.fulfill({ contentType: 'text/html', body: fixture }));
  if (testInfo.title.startsWith('loading badges')) {
    await context.route(`${apiOrigin}/health`, route => route.fulfill({ json: { status: 'ok' } }));
    await context.route(`${apiOrigin}/v1/resolve`, route => route.fulfill({ json: { results: [] } }));
  }
  page = await context.newPage();
  popup = await context.newPage();
  await popup.goto(`chrome-extension://${id}/popup.html`);
  await expect(popup.locator('#status')).not.toHaveText('Checking connection…');
  await page.goto('https://www.netflix.com/browse');
});

test.afterEach(async () => { await context?.close(); await rm(profile, { recursive: true, force: true }); });

for (const outcome of ['matched', 'not_found', 'failure']) {
  test(`loading badges clear after ${outcome} and respect reduced motion`, async () => {
    let release!: () => void;
    const waiting = new Promise<void>(resolve => { release = resolve; });
    await context.route(`${apiOrigin}/v1/resolve`, async route => {
      await waiting;
      if (outcome === 'failure') {
        await route.fulfill({ status: 503, headers: { 'Retry-After': '30' } });
        return;
      }
      const { cards } = route.request().postDataJSON();
      await route.fulfill({ json: {
        results: cards.map((card: { request_id: string }) => ({
          request_id: card.request_id, status: outcome,
          rating: outcome === 'matched' ? { imdb_id: 'tt0111161', rating: 9.3, votes: 10000 } : null,
        })),
        dataset_version: 'loading-fixture', dataset_date: '2026-10-12', matcher_version: '9',
      } });
    });
    await page.reload();
    const badge = page.locator('#good .watchsift-badge');
    await expect(badge).toHaveAttribute('role', 'status');
    await expect(badge).toHaveAttribute('aria-label', 'Loading IMDb rating');
    await expect(badge).not.toHaveAttribute('href');
    await expect(badge).toHaveCSS('background-color', 'rgb(242, 204, 97)');
    await expect(badge.locator('.watchsift-spinner')).toBeVisible();
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await expect(badge.locator('.watchsift-spinner')).toHaveCSS('animation-duration', '6s');
    if (outcome === 'matched') await page.screenshot({ path: '../.impeccable/review/loading.png' });
    release();
    await expect(page.locator('.watchsift-spinner')).toHaveCount(0);
    if (outcome === 'matched') {
      await expect(badge).toHaveText('9.3 · 10K votes');
      await expect(badge).toHaveAttribute('href', 'https://www.imdb.com/title/tt0111161/');
      await expect(badge).not.toHaveAttribute('role');
    } else {
      await expect(page.locator('.watchsift-badge')).toHaveCount(0);
    }
  });
}

test('packaged extension applies inclusive AND filtering and preserves unknowns', async () => {
  await expect(page.locator('#good .watchsift-badge')).toHaveCount(1);
  await expect(page.locator('#low .watchsift-badge')).toHaveCount(1);
  await expect(popup.locator('#minRating')).toHaveValue('7');
  await expect(popup.locator('#minVotes')).toHaveValue('1000');
  await expect(popup.locator('#analytics, #diagnostics, #reports')).toHaveCount(0);
  await popup.locator('#filtering').check();
  await expect(page.locator('#low')).toHaveClass(/watchsift-dimmed/);
  await expect(page.locator('#good')).not.toHaveClass(/watchsift-dimmed/);
  await expect(page.locator('#unknown .watchsift-badge')).toHaveCount(0);
  await expect(page.locator('#unknown')).not.toHaveClass(/watchsift-dimmed/);
  await popup.locator('#enabled').uncheck();
  await expect(page.locator('.watchsift-badge')).toHaveCount(0);
  await expect(page.locator('#low')).not.toHaveClass(/watchsift-dimmed/);
});

test('injects and resolves accessible cards on the bare Netflix hostname', async () => {
  await page.goto('https://netflix.com/browse');
  await expect(page.locator('#good .watchsift-badge')).toHaveCount(1);
  await page.evaluate(() => {
    const card = document.getElementById('good')!;
    card.querySelector('.fallback-text')!.textContent = ' ';
    card.querySelector('a.native')!.setAttribute('aria-label', 'The Shawshank Redemption');
  });
  await expect(page.locator('#good .watchsift-badge')).toHaveCount(1);
});

test('renders sibling badges on current Netflix cards and clears recycled accessible titles', async () => {
  await expect(page.locator('#modern > .watchsift-badge')).toHaveCount(1);
  await expect(page.locator('#ranked > .watchsift-badge')).toHaveCount(1);
  await expect(page.locator('a[data-uia] .watchsift-badge')).toHaveCount(0);
  await expect(page.locator('#episode .watchsift-badge')).toHaveCount(0);
  await page.locator('#modern > a[data-uia]').evaluate(element => {
    element.setAttribute('aria-label', 'WatchSift unknown recycled modern card');
    element.setAttribute('href', 'https://www.netflix.com/browse?jbv=2005');
  });
  await expect(page.locator('#modern .watchsift-badge')).toHaveCount(0);
});

test('handles lazy cards, SPA navigation and recycled card metadata', async () => {
  await expect(page.locator('#good .watchsift-badge')).toHaveCount(1);
  await expect(page.locator('#lazy .watchsift-badge')).toHaveCount(0);
  await page.locator('#lazy').scrollIntoViewIfNeeded();
  await expect(page.locator('#lazy .watchsift-badge')).toHaveCount(1);
  await page.locator('#good').scrollIntoViewIfNeeded();
  await page.evaluate(() => {
    history.pushState({}, '', '/search?q=film');
    const card = document.getElementById('good')!;
    card.querySelector('.fallback-text')!.textContent = 'WatchSift unknown recycled';
    card.querySelector('a.native')!.setAttribute('href', 'https://www.netflix.com/title/2001');
  });
  await expect(page.locator('#good .watchsift-badge')).toHaveCount(0);
  await expect(page.locator('#good')).not.toHaveClass(/watchsift-dimmed/);
});

test('worker upgrade clears old telemetry while retaining filter preferences and retry backoff', async () => {
  await expect(page.locator('#good .watchsift-badge')).toHaveCount(1);
  await popup.evaluate(async () => {
    const stored = await chrome.storage.local.get(['settings', 'engine']);
    await chrome.storage.local.set({
      settings: { ...(stored.settings as object), filtering: true, analytics: true, diagnostics: true },
      engine: { status: 'Connected', retryAt: Date.now() + 60000, metrics: [{}], pending: [{ title: 'Old report' }], history: [{}], daily: { keys: ['Old title'] }, telemetryRetryAt: 123 },
    });
  });
  const session = await context.newCDPSession(page);
  const { targetInfos } = await session.send('Target.getTargets');
  const worker = targetInfos.find(target => target.type === 'service_worker');
  await session.send('Target.closeTarget', { targetId: worker!.targetId });
  await popup.reload();
  await expect(popup.locator('#filtering')).toBeChecked();
  await expect.poll(async () => popup.evaluate(async () => {
    const stored = await chrome.storage.local.get(['settings', 'engine']);
    return { settings: Object.keys(stored.settings as object).sort(), engine: Object.keys(stored.engine as object).sort() };
  })).toEqual({ settings: ['enabled', 'filtering', 'minRating', 'minVotes'], engine: ['retryAt', 'status'] });
  const state = await popup.evaluate(async () => (await chrome.storage.local.get('engine')).engine);
  expect((state as { retryAt: number }).retryAt).toBeGreaterThan(Date.now());
});

test('a fresh lookup failure after reload does not reuse a previous rating', async () => {
  await expect(page.locator('#good .watchsift-badge')).toHaveCount(1);
  await context.route(`${apiOrigin}/v1/resolve`, route => route.fulfill({ status: 503, contentType: 'application/json', body: '{"detail":"Unavailable"}', headers: { 'Retry-After': '30' } }));
  await page.reload();
  await expect.poll(async () => {
    await popup.reload();
    return popup.locator('#status').textContent();
  }).toContain('Ratings unavailable');
  await expect(page.locator('.watchsift-badge')).toHaveCount(0);
});

test('captures the real popup and card rendering', async () => {
  await expect(page.locator('#good .watchsift-badge')).toHaveCount(1);
  await popup.setViewportSize({ width: 360, height: 700 });
  await popup.locator('body').screenshot({ path: '../.impeccable/review/popup.png' });
  await popup.locator('#filtering').check();
  await expect(page.locator('#low')).toHaveClass(/watchsift-dimmed/);
  await page.screenshot({ path: '../.impeccable/review/cards.png' });
});

test('popup controls cannot race a pending settings save', async () => {
  await popup.evaluate(() => {
    const original = chrome.runtime.sendMessage.bind(chrome.runtime);
    const delayed = async (message: { action: string }) => {
      if (message.action === 'settings') await new Promise(resolve => setTimeout(resolve, 500));
      return original(message);
    };
    chrome.runtime.sendMessage = delayed as typeof chrome.runtime.sendMessage;
  });
  await popup.locator('#filtering').check();
  await expect(popup.locator('#enabled')).toBeDisabled();
  await expect(popup.locator('#message')).toHaveText('Saved');
  await popup.locator('#enabled').uncheck();
  await expect(popup.locator('#message')).toHaveText('Saved');
  await popup.reload();
  await expect(popup.locator('#filtering')).toBeChecked();
  await expect(popup.locator('#enabled')).not.toBeChecked();
});

test('failed popup saves retain preferences and re-enable controls for retry', async () => {
  await popup.evaluate(() => {
    const original = chrome.runtime.sendMessage.bind(chrome.runtime);
    let fail = true;
    chrome.runtime.sendMessage = (async (message: { action: string }) => {
      if (message.action === 'settings' && fail) {
        fail = false;
        return { saved: false };
      }
      return original(message);
    }) as typeof chrome.runtime.sendMessage;
  });
  await popup.locator('#enabled').click();
  await expect(popup.locator('#message')).toContainText('Could not save');
  await expect(popup.locator('#enabled')).toBeChecked();
  await expect(popup.locator('#save')).toBeEnabled();
  await popup.locator('#enabled').uncheck();
  await expect(popup.locator('#message')).toHaveText('Saved');
  await popup.reload();
  await expect(popup.locator('#enabled')).not.toBeChecked();
});

test('a restarted service worker makes a fresh lookup instead of reusing ratings', async () => {
  let lookups = 0;
  await context.route(`${apiOrigin}/v1/resolve`, route => { if (route.request().postDataJSON().cards.some((card: { provider_id: string }) => card.provider_id === '1001')) lookups++; return route.continue(); });
  await expect(page.locator('#good .watchsift-badge')).toHaveCount(1);
  const before = lookups;
  const session = await context.newCDPSession(page);
  const { targetInfos } = await session.send('Target.getTargets');
  const target = targetInfos.find(target => target.type === 'service_worker');
  expect(target).toBeDefined();
  await session.send('Target.closeTarget', { targetId: target!.targetId });
  await page.reload();
  await expect(page.locator('#good .watchsift-badge')).toHaveCount(1);
  await expect.poll(() => lookups).toBeGreaterThan(before);
});

const enrichmentFixture = `<!doctype html><html><body>
<div id="enrich" style="width:250px;height:145px"><a data-uia="standard-card" href="/browse?jbv=81611854" aria-label="East of Eden"><img alt="" width="250" height="145" src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"></a></div>
<script>
document.querySelector('#enrich a').onclick = event => {
  const originalUrl = location.href, stalled = new URL(location.href).searchParams.has('stalled');
  event.preventDefault(); document.body.dataset.opens = String(Number(document.body.dataset.opens || 0) + 1);
  history.pushState({}, '', '/browse?jbv=81611854');
  const dialog = document.createElement('div'); dialog.setAttribute('role', 'dialog');
  dialog.dataset.uia = 'modal-motion-container-DETAIL_MODAL';
  dialog.innerHTML = '<img alt="East of Eden" src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"><div data-uia="videoMetadata--container"><span class="duration">Limited Series</span></div><button data-uia="previewModal-closebtn">close</button>';
  document.body.append(dialog);
  dialog.querySelector('button').focus();
  dialog.querySelector('button').onclick = () => { dialog.remove(); history.replaceState({}, '', originalUrl); };
  if (!stalled) setTimeout(() => { const year = document.createElement('div'); year.className = 'year'; year.textContent = '2026'; dialog.querySelector('[data-uia="videoMetadata--container"]').append(year); }, 700);
};
</script></body></html>`;

async function prepareEnrichment() {
  const requests: Array<{ raw_year: string | null; duration: string | null }> = [];
  await context.route('https://www.netflix.com/**', route => route.fulfill({ contentType: 'text/html', body: enrichmentFixture }));
  await context.route(`${apiOrigin}/v1/resolve`, async route => {
    const cards = route.request().postDataJSON().cards;
    for (const card of cards) if (card.provider_id === '81611854') requests.push({ raw_year: card.raw_year ?? null, duration: card.duration ?? null });
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({
      results: cards.map((card: { request_id: string; raw_year: string | null }) => ({ request_id: card.request_id,
        status: card.raw_year === '2026' ? 'matched' : 'ambiguous',
        rating: card.raw_year === '2026' ? { imdb_id: 'tt21097264', rating: 8.1, votes: 12356 } : null })),
      dataset_version: 'enrichment-fixture', dataset_date: '2026-10-11', matcher_version: '4',
    }) });
  });
  return requests;
}

test('never navigates automatically; enriches only the user-opened detail and keeps it open', async () => {
  const requests = await prepareEnrichment();
  await page.reload();
  await expect.poll(() => requests.length).toBe(1);
  expect(requests).toEqual([{ raw_year: null, duration: null }]);
  await expect(page.locator('.watchsift-loading')).toHaveCount(0);
  await expect(page).toHaveURL('https://www.netflix.com/browse');
  expect(await page.locator('body').getAttribute('data-opens')).toBeNull();
  await page.locator('#enrich a[data-uia]').click();
  await expect(page.locator('#enrich .watchsift-badge')).toHaveText('8.1 · 12.4K votes');
  await expect(page.locator('.watchsift-detail-rating .watchsift-badge')).toHaveText('8.1 · 12.4K votes');
  await expect(page.locator('[data-uia="modal-motion-container-DETAIL_MODAL"]')).toBeVisible();
  await expect(page).toHaveURL('https://www.netflix.com/browse?jbv=81611854');
  expect(requests).toEqual([{ raw_year: null, duration: null }, { raw_year: '2026', duration: 'Limited Series' }]);
  expect(await page.locator('body').getAttribute('data-opens')).toBe('1');
  await page.locator('[data-uia="previewModal-closebtn"]').click();
  await expect(page).toHaveURL('https://www.netflix.com/browse');
  await page.reload();
  await expect.poll(() => requests.length).toBeGreaterThan(2);
  await expect(page.locator('[data-uia="modal-motion-container-DETAIL_MODAL"]')).toHaveCount(0);
  const persisted = await popup.evaluate(() => chrome.storage.local.get(['engine', 'netflixMetadata']));
  expect(persisted).not.toHaveProperty('netflixMetadata');
  expect(persisted.engine).not.toHaveProperty('cache');
});

test('keeps scrolling usable during a slow background rating lookup', async () => {
  await expect(page.locator('#good .watchsift-badge')).toHaveCount(1);
  let lazyLookups = 0;
  await context.route(`${apiOrigin}/v1/resolve`, async route => {
    if (route.request().postDataJSON().cards.some((card: { provider_id: string }) => card.provider_id === '1004')) {
      lazyLookups++;
      await new Promise(resolve => setTimeout(resolve, 700));
    }
    await route.continue();
  });
  await page.locator('#lazy').scrollIntoViewIfNeeded();
  await expect.poll(() => lazyLookups).toBe(1);
  await expect(page.locator('.watchsift-loading')).toHaveCount(0);
  expect(await page.evaluate(() => [...document.body.children].some(element => (element as HTMLElement).inert))).toBe(false);
  await expect(page.locator('#lazy .watchsift-badge')).toHaveCount(1);
});


test('resolves a user-opened dialog even when its grid card is absent', async () => {
  const requests = await prepareEnrichment();
  await page.reload();
  await expect.poll(() => requests.length).toBe(1);
  await page.locator('#enrich a[data-uia]').click();
  await page.locator('#enrich').evaluate(element => element.remove());
  await expect(page.locator('.watchsift-detail-rating .watchsift-badge')).toHaveText('8.1 · 12.4K votes');
  await expect(page.locator('[data-uia="modal-motion-container-DETAIL_MODAL"]')).toBeVisible();
  await expect(page.locator('.watchsift-loading')).toHaveCount(0);
  await expect(page).toHaveURL('https://www.netflix.com/browse?jbv=81611854');
});


test('uses bundled selectors on both providers and makes only rating requests', async () => {
  const worker = context.serviceWorkers()[0];
  await worker.evaluate(() => {
    const original = fetch;
    const requests: string[] = [];
    (globalThis as unknown as { lookupRequests: string[] }).lookupRequests = requests;
    globalThis.fetch = (input, init) => {
      requests.push(String(input instanceof Request ? input.url : input));
      return original(input, init);
    };
  });
  await page.reload();
  await expect(page.locator('#good .watchsift-badge')).toHaveCount(1);
  await openPrime();
  const requests = await worker.evaluate(() => (globalThis as unknown as { lookupRequests: string[] }).lookupRequests);
  expect(requests.length).toBeGreaterThan(0);
  expect(requests.every(url => url === `${apiOrigin}/v1/resolve`)).toBe(true);
  expect(await popup.evaluate(() => chrome.storage.local.get(null))).not.toHaveProperty('parserConfig');
});

test('renders a large visible card batch over multiple animation frames', async () => {
  await expect(page.locator('#good .watchsift-badge')).toHaveCount(1);
  const batches: string[][] = [];
  await context.route(`${apiOrigin}/v1/resolve`, route => {
    batches.push(route.request().postDataJSON().cards.map((card: { provider_id: string }) => card.provider_id));
    return route.continue();
  });
  await page.evaluate(() => {
    const container = document.createElement('section');
    container.id = 'bulk';
    container.style.cssText = 'position:fixed;inset:0;z-index:999;display:grid;grid-template-columns:repeat(15,60px);grid-auto-rows:40px;align-content:start';
    const template = document.getElementById('good')!;
    for (let i = 0; i < 100; i++) {
      const card = template.cloneNode(true) as HTMLElement;
      card.id = `bulk-${i}`;
      card.style.cssText = 'width:60px;height:40px';
      card.querySelector('.watchsift-badge')?.remove();
      card.querySelector('a.native')!.setAttribute('href', `https://www.netflix.com/title/${4000+i%75}`);
      container.append(card);
    }
    let frame = 0;
    const frames = new Set<number>();
    function tick() { frame++; requestAnimationFrame(tick); }
    requestAnimationFrame(tick);
    new MutationObserver(mutations => {
      if (mutations.some(mutation => [...mutation.addedNodes].some(node =>
        node instanceof Element && node.classList.contains('watchsift-badge')))) {
        frames.add(frame);
        container.dataset.frames = String(frames.size);
      }
    }).observe(container, { childList: true, subtree: true });
    document.body.prepend(container);
  });
  await expect(page.locator('#bulk .watchsift-badge')).toHaveCount(100);
  expect(Number(await page.locator('#bulk').getAttribute('data-frames'))).toBeGreaterThan(1);
  expect(batches.every(batch => batch.length <= 50)).toBe(true);
  const bulkIds = batches.flat().filter(id => Number(id) >= 4000 && Number(id) < 4075);
  expect(bulkIds).toHaveLength(75);
  expect(new Set(bulkIds).size).toBe(75);
});

async function openPrime(url = 'https://www.primevideo.com/region/eu/storefront') {
  const fixture = await readFile('tests/fixtures/primevideo.html', 'utf8');
  await context.route('https://www.primevideo.com/**', route => route.fulfill({ contentType: 'text/html', body: fixture }));
  await context.route('https://primevideo.com/**', route => route.fulfill({ contentType: 'text/html', body: fixture }));
  await page.goto(url);
  await expect(page.locator('#prime-good .watchsift-badge')).toHaveCount(1);
}

test('Prime packaged badges preserve native links, unknowns, filtering and shared preferences', async () => {
  await openPrime();
  await expect(page.locator('#prime-low .watchsift-badge')).toHaveCount(1);
  await expect(page.locator('#prime-poster > .watchsift-badge')).toHaveCount(1);
  await page.locator('#prime-hero').scrollIntoViewIfNeeded();
  await expect(page.locator('#prime-hero > .watchsift-badge')).toHaveCount(1);
  expect(await page.locator('#prime-hero > .watchsift-badge').evaluate(e => {const r=e.getBoundingClientRect();return document.elementFromPoint(r.x+r.width/2,r.y+r.height/2)===e;})).toBe(true);
  await expect(page.locator('#prime-event .watchsift-badge, [data-testid="episode-list-item"] .watchsift-badge')).toHaveCount(0);
  await expect(page.locator('[data-testid="packshot"] a .watchsift-badge')).toHaveCount(0);
  await popup.locator('#filtering').check();
  await expect(page.locator('#prime-low')).toHaveClass(/watchsift-dimmed/);
  await expect(page.locator('#prime-good')).not.toHaveClass(/watchsift-dimmed/);
  await expect(page.locator('#prime-unknown')).not.toHaveClass(/watchsift-dimmed/);
  await page.locator('#prime-good').scrollIntoViewIfNeeded();
  const badge = page.locator('#prime-good .watchsift-badge');
  await expect(badge).toHaveAttribute('href', 'https://www.imdb.com/title/tt0111161/');
  await badge.focus();
  await expect(badge).toBeFocused();
  const hit = await badge.evaluate(e => { const r = e.getBoundingClientRect(); return document.elementFromPoint(r.x+r.width/2,r.y+r.height/2) === e; });
  expect(hit).toBe(true);
  await popup.locator('#enabled').uncheck();
  await expect(page.locator('.watchsift-badge')).toHaveCount(0);
  await expect(page.locator('#prime-low')).not.toHaveClass(/watchsift-dimmed/);
});

test('badges stay readable against host link styles while filtering dims only card content', async () => {
  await context.route(`${apiOrigin}/v1/resolve`, async route => {
    const { cards } = route.request().postDataJSON();
    await route.fulfill({ json: {
      results: cards.map((card: { request_id: string }) => ({
        request_id: card.request_id, status: 'matched',
        rating: { imdb_id: 'tt0052077', rating: 3.9, votes: 12345 },
      })),
      dataset_version: 'badge-fixture', dataset_date: '2026-10-12', matcher_version: '9',
    } });
  });
  for (const provider of ['netflix', 'primevideo']) {
    if (provider === 'primevideo') await openPrime();
    else await page.reload();
    const card = page.locator(provider === 'primevideo' ? '#prime-low' : '#low');
    const badge = card.locator('.watchsift-badge');
    const native = card.locator('a:not(.watchsift-badge)');
    await page.addStyleTag({ content: 'body article a, body .title-card a { color: white; }' });
    await popup.locator('#filtering').check();
    await page.mouse.move(0, 0);
    await expect(card).toHaveClass(/watchsift-dimmed/);
    await expect(card).toHaveCSS('opacity', '1');
    await expect(native).toHaveCSS('opacity', '0.4');
    await expect(badge).toHaveCSS('color', 'rgb(23, 22, 17)');
    await expect(badge).toHaveCSS('font-size', '12px');
    expect(await badge.evaluate(element => {
      for (let node: Element | null = element; node; node = node.parentElement)
        if (Number(getComputedStyle(node).opacity) < 1) return false;
      return true;
    })).toBe(true);
    await page.screenshot({ path: `/tmp/watchsift-badge-${provider}.png` });
    await badge.hover();
    await expect(native).toHaveCSS('opacity', '1');
    await expect(badge).toHaveCSS('color', 'rgb(23, 22, 17)');
    await page.mouse.move(0, 0);
    await badge.focus();
    await expect(native).toHaveCSS('opacity', '1');
    await expect(badge).toHaveCSS('outline-style', 'solid');
    expect(await badge.evaluate(element => {
      const rect = element.getBoundingClientRect();
      return document.elementFromPoint(rect.x + rect.width / 2, rect.y + rect.height / 2) === element;
    })).toBe(true);
  }
});

test('Prime handles bare host, search navigation, lazy cards and recycled identity', async () => {
  await openPrime('https://primevideo.com/search?phrase=Film');
  await expect(page.locator('#prime-lazy .watchsift-badge')).toHaveCount(0);
  await page.locator('#prime-lazy').scrollIntoViewIfNeeded();
  await expect(page.locator('#prime-lazy .watchsift-badge')).toHaveCount(1);
  await page.locator('#prime-good').scrollIntoViewIfNeeded();
  await page.evaluate(() => {
    history.pushState({}, '', '/region/eu/search?phrase=Another');
    const card = document.getElementById('prime-good')!;
    card.setAttribute('data-card-title', 'WatchSift unknown recycled prime');
    card.querySelector('button')!.setAttribute('aria-label', 'WatchSift unknown recycled prime');
    card.querySelector('a')!.textContent = 'WatchSift unknown recycled prime';
    card.querySelector('a')!.setAttribute('href', '/detail/B000000009');
  });
  await expect(page.locator('#prime-good .watchsift-badge')).toHaveCount(0);
  await expect(page).toHaveURL('https://primevideo.com/region/eu/search?phrase=Another');
});

test('Prime user-opened movie and series details resolve without changing native metadata', async () => {
  await openPrime();
  const detail = '<main data-testid="detailpage-main"><h1><img alt="The Shawshank Redemption"></h1><div data-testid="dp-atf-badges"><span data-automation-id="imdb-rating-badge">IMDb 7.0</span><span data-automation-id="release-year-badge">1994</span><span data-automation-id="runtime-badge">2 h 22 min</span></div></main>';
  await context.route('https://www.primevideo.com/region/eu/detail/**', route => route.fulfill({contentType:'text/html', body:detail}));
  await page.locator('#prime-good [data-testid="packshot"] a[href*="/detail/"]').click();
  const rating = page.locator('[data-testid="dp-atf-badges"] .watchsift-badge');
  await expect(rating).toHaveText('7.0 · 1K votes');
  await expect(page.locator('[data-automation-id="imdb-rating-badge"]')).toHaveText('IMDb 7.0');
  await expect(page).toHaveURL('https://www.primevideo.com/region/eu/detail/0SC64NC24QA7M9AFWBEK87WWS0');
  await context.route(`${apiOrigin}/v1/resolve`, async route => {
    const cards = route.request().postDataJSON().cards;
    expect(cards[0]).toMatchObject({provider:'primevideo', duration:'2 seasons', raw_year:'2022'});
    await route.fulfill({contentType:'application/json', body:JSON.stringify({results:cards.map((card:{request_id:string})=>({request_id:card.request_id,status:'matched',rating:{imdb_id:'tt11743610',rating:7.9,votes:12345}})),dataset_version:'series-fixture',dataset_date:'2026-10-11',matcher_version:'4'})});
  });
  await page.evaluate(() => {
    document.querySelector('h1 img')!.setAttribute('alt','The Terminal List');
    document.querySelector('[data-automation-id="release-year-badge"]')!.textContent='2022';
    document.querySelector('[data-automation-id="runtime-badge"]')!.outerHTML='<span aria-label="2 seasons">2 seasons</span>';
    history.pushState({},'', '/region/eu/detail/0NGB908JKDOZ29WLQ2GS45USOV');
  });
  await expect(rating).toHaveText('7.9 · 12.3K votes');
});

test('Prime API failure never reuses stale ratings', async () => {
  await openPrime();
  await context.route(`${apiOrigin}/v1/resolve`, route=>route.fulfill({status:503,headers:{'Retry-After':'30'}}));
  await page.reload();
  await expect.poll(async()=> {await popup.reload(); return popup.locator('#status').textContent();}).toContain('Ratings unavailable');
  await expect(page.locator('.watchsift-badge')).toHaveCount(0);
});

test('Prime hover anchors badges to expanding artwork without rewriting or resolving again', async () => {
  let requests = 0;
  await context.route(`${apiOrigin}/v1/resolve`, async route => {
    requests++;
    const {cards} = route.request().postDataJSON();
    await route.fulfill({json:{results:cards.map((card:{request_id:string})=>({request_id:card.request_id,status:'matched',rating:{imdb_id:'tt0111161',rating:9.3,votes:10000}})),dataset_version:'hover-fixture',dataset_date:'2026-10-11',matcher_version:'4'}});
  });
  await openPrime();
  const badge = page.locator('#prime-good [data-testid="packshot"] > .watchsift-badge');
  await expect(badge).toHaveCount(1);
  await page.evaluate(() => {
    const badge = document.querySelector('#prime-good .watchsift-badge')!;
    (window as unknown as {hoverBadge:Element}).hoverBadge=badge;
    document.documentElement.setAttribute('data-badge-writes','0');
    new MutationObserver(records => {
      const count = Number(document.documentElement.getAttribute('data-badge-writes'));
      document.documentElement.setAttribute('data-badge-writes', String(count+records.length));
    }).observe(badge,{attributes:true,childList:true,characterData:true,subtree:true});
  });
  // Wait until initially visible cards have finished their first lookup.
  await expect(page.locator('#prime-hero .watchsift-badge')).toHaveCount(1);
  const before = requests;
  await page.locator('#prime-good').hover();
  await page.evaluate(() => {
    const details = document.createElement('div');
    details.dataset.testid='standard-mini-details';
    details.innerHTML='<span data-automation-id="release-year-badge">1994</span>';
    document.querySelector('#prime-good')!.append(details);
  });
  await expect.poll(async()=>badge.evaluate(e=> {
    const art=e.parentElement!.getBoundingClientRect(), r=e.getBoundingClientRect();
    return Math.abs(r.left-art.left-6*1.56)<1 && Math.abs(art.bottom-r.bottom-6*1.56)<1;
  })).toBe(true);
  expect(await badge.evaluate(e=>e===(window as unknown as {hoverBadge:Element}).hoverBadge)).toBe(true);
  await badge.focus();
  await expect(badge).toBeFocused();
  expect(await badge.evaluate(e=>{const r=e.getBoundingClientRect();return document.elementFromPoint(r.x+r.width/2,r.y+r.height/2)===e;})).toBe(true);
  // Prime's React hover update replaces the host class attribute.
  await popup.locator('#filtering').check();
  await popup.locator('#minRating').fill('10');
  await popup.locator('#thresholds button').click();
  await expect(page.locator('#prime-good')).toHaveClass(/watchsift-dimmed/);
  await page.evaluate(() => { document.querySelector('#prime-good')!.className='prime-native-expanded'; });
  await expect(page.locator('#prime-good')).toHaveClass(/watchsift-dimmed/);
  await expect(badge).toHaveCSS('position','absolute');
  await expect(badge).toHaveCSS('background-color','rgb(242, 204, 97)');
  await page.screenshot({path:'../.impeccable/review/prime-hover-fixed.png'});
  await page.evaluate(()=>document.documentElement.setAttribute('data-badge-writes','0'));
  await page.mouse.move(0,0);
  await page.evaluate(()=>document.querySelector('[data-testid="standard-mini-details"]')!.remove());
  await expect.poll(async()=>badge.evaluate(e=> {
    const art=e.parentElement!.getBoundingClientRect(), r=e.getBoundingClientRect();
    return Math.abs(r.left-art.left-6)<1 && Math.abs(art.bottom-r.bottom-6)<1;
  })).toBe(true);
  await page.waitForTimeout(400);
  expect(requests).toBe(before);
  expect(await page.locator('html').getAttribute('data-badge-writes')).toBe('0');
});


test('Prime detail badge selects the visible responsive metadata row', async () => {
  await context.route(`${apiOrigin}/v1/resolve`, async route=>{
    const {cards}=route.request().postDataJSON();
    await route.fulfill({json:{results:cards.map((c:{request_id:string})=>({request_id:c.request_id,status:'matched',rating:{imdb_id:'tt14526318',rating:7.4,votes:9155}})),dataset_version:'responsive-fixture',dataset_date:'2026-10-11',matcher_version:'8'}});
  });
  const metadata='<span data-automation-id="imdb-rating-badge">IMDb 7.4/10</span><span data-automation-id="release-year-badge">2022</span><span data-automation-id="runtime-badge">2 h 43 min</span>';
  const fixture=`<style>#mobile{display:none}@media(max-width:700px){#mobile{display:block}#desktop{display:none}}</style><main data-testid="detailpage-main"><div data-testid="atf-component-next-gen"><h1>Sardar</h1><div id="mobile" data-testid="dp-atf-badges">${metadata}</div><div id="desktop">${metadata}</div></div></main>`;
  await context.route('https://www.primevideo.com/**',route=>route.fulfill({contentType:'text/html',body:fixture}));
  await page.goto('https://www.primevideo.com/region/eu/detail/0MU5L71EX45LALFAZ46EXOW8FV');
  await expect(page.locator('#desktop .watchsift-badge')).toHaveText('7.4 · 9.2K votes');
  await expect(page.locator('#desktop .watchsift-badge')).toBeVisible();
  await expect(page.locator('#mobile .watchsift-badge')).toHaveCount(0);
  await page.setViewportSize({width:600,height:720});
  await expect(page.locator('#mobile .watchsift-badge')).toBeVisible();
  await expect(page.locator('#desktop .watchsift-badge')).toHaveCount(0);
  await expect(page.locator('#mobile [data-automation-id="imdb-rating-badge"]')).toHaveText('IMDb 7.4/10');
});
