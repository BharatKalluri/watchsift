# WatchSift

IMDb ratings and vote counts on Netflix and Prime Video, with an optional AND filter. Defaults are **7.0 / 1,000 votes**, badges on, filtering off. Unknown or ambiguous titles stay visible.

Matching uses exact IMDb aliases and available year/type, including explicit film/series hints and row labels shared across duplicate cards. Exact primary titles retain meaningful punctuation and take precedence over conflicting aliases when that does not narrow away an unrated primary namesake. If the exact lookup has no candidates, limited Unicode cleanup, Latin accent folding, descriptive subtitle removal, and a trailing part-I variant are tried; these fallbacks require one unique rated candidate. IMDb TV specials have their own catalogue kind and can match in film or show rows. Other name collisions still require at least 1,000 votes and 100 times the next candidate's votes. These title and popularity heuristics can select a wrong namesake; closer ties remain unbadged.

Local development uses a localhost API. Production packaging requires an HTTPS API origin; backend startup and packaging do not require a data-permission confirmation flag.

## Run locally

Requires Node 22.12+ (or a newer supported Node release), Python 3.11+, and uv.

From `backend/`:

```sh
rtk proxy uv sync --frozen
rtk proxy uv run python -m src.catalogue.importer ../datasets/imdb-datasets-2026-10-11 --date 2026-10-11
rtk proxy uv run uvicorn src.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

The full supplied dataset has already been imported locally into `backend/data/`. Skip the import unless rebuilding the catalogue. The API's `/health` reports availability; `/docs` describes the local API.

From `extension/`:

```sh
rtk proxy npm ci
rtk proxy npm run build
```

Open `chrome://extensions`, enable Developer mode, choose **Load unpacked**, and select `extension/dist/`. Open Netflix or Prime Video in Chrome, then use WatchSift's popup. Keep the local API running. Refresh the streaming site after reloading an extension build.

## Structure

The backend follows [zhanymkanov's domain-based FastAPI structure](https://github.com/zhanymkanov/fastapi-best-practices): `backend/src/catalogue/` contains its router, request/response schemas, and services; shared config, dependencies, connections, and application setup live at `backend/src/`. SQLite tables are defined with SQLModel in `catalogue/models.py`. Synchronous sessions run inside FastAPI's thread pool; catalogue sessions are read-only and operations sessions commit or roll back as one transaction. The importer uses batched table inserts rather than per-title ORM objects. Existing catalogue snapshots need no reimport. Backend startup transactionally removes obsolete usage metrics, receipts, and missing-rating report tables, preserving shared provider mappings. Restart the backend to apply this cleanup.

The extension groups code by context: `src/background/` owns API transport and message handling; `src/content/` reads Netflix and Prime Video DOM and renders badges; `src/popup/` owns popup controls; `src/shared/` contains validated settings, response types and selector configuration. `manifest.json` is the editable manifest source; the build scopes its API host and CSP to the configured backend. Packaged entry-point paths stay stable. Chrome 116+ is required. The extension uses a DOM adapter, a content script, an event-driven service worker, and a React popup styled with Tailwind. Preferences and connection status survive worker restarts; ratings and title metadata are not cached. Retry deadlines survive service-worker restarts; only short-lived operation sequencing live in worker memory. Content DOM updates yield across animation frames in groups of 20. Only extension contexts can read the local storage; streaming-site content scripts obtain preferences and ratings through validated messages.

The extension bundles Zod locally for card, settings, rating-response, message, and parser-configuration validation. TypeScript types are inferred from those schemas, so field definitions and validation stay together. Zod runs with `jitless: true` for Manifest V3 CSP compatibility; builds include its MIT license. There is no CDN or remote library loading. Card tracking uses one retry timestamp: zero means unresolved, a future timestamp means retry later, and infinity means resolved for the current page. Backend matching and provider mappings remain authoritative.

## Formatting

Python uses Ruff with the backend's existing 100-column configuration. TypeScript and CSS in `extension/src/` use Prettier with two-space indentation, single quotes, and a 100-column target. CI checks formatting for both projects.

From `backend/`, apply formatting with `rtk proxy uv run ruff format src tests`.
From `extension/`, use `rtk proxy npm run format`; `rtk proxy npm run format:check` checks without changing files.

## Checks

From `backend/`:

```sh
rtk proxy uv run ruff check src tests
rtk proxy uv run ruff format --check src tests
rtk proxy uv run pytest -q
```

From `extension/`, with the API running and the extension built:

```sh
rtk proxy npm run format:check
rtk proxy npm test
rtk proxy npm exec playwright install chromium
rtk proxy npm run test:e2e
```

Browser tests use **synthetic Netflix and Prime Video DOM** served by Playwright at intercepted provider URLs, with a fresh temporary Chrome profile. They do not log in, navigate the real streaming applications, or play anything. They exercise the packaged extension, filtering, settings, legacy telemetry cleanup, bundled selectors, lazy/reused cards, service failures, and worker restart. CI uses a tiny synthetic catalogue; the local prototype uses the full supplied index.

### Live validation still required

An authenticated Netflix browser was not available to this session. Before release, verify 100 Netflix India titles in English UI, including Indian-language alternatives, remakes, series, and duplicate names. Record *independently verified* IMDb IDs in CSV with these columns:

```csv
netflix_id,title,year,type,expected_imdb_id
```

Use `movie` or `series` when visible metadata provides it; leave absent fields empty. A blank expected IMDb ID means no trusted rating should be displayed. Run `rtk proxy uv run python -m src.catalogue.evaluate /absolute/path/verified.csv` from `backend/`. The command fails unless there are at least 100 titles, no wrong badges, and at least 80% correct badge coverage of recognized rated titles. Record DOM extraction success separately and manually check hover previews, keyboard navigation, search, carousels, and playback. A matcher-only evaluation cannot establish live adapter reliability.

## Catalogue maintenance

Imports stream all three gzipped TSVs. The index contains movies, TV movies, series, miniseries, and TV specials with all available aliases. Unrated titles remain in the matching candidate set; only rated matches return badges. Low-vote titles remain available. Matching follows the primary-title, context, limited fallback, and popularity rules above. No fuzzy or transliteration guesses.

Import creates a validated immutable snapshot, atomically switches `current.sqlite3`, and keeps `previous.sqlite3` for rollback. Existing requests finish on their opened snapshot. From `backend/`:

```sh
rtk proxy uv run python -m src.catalogue.manage rollback
```

Every page load and newly visible card batch makes fresh rating lookups. The extension keeps no persistent rating or metadata cache; legacy browser caches are removed. The backend shares year-qualified provider-to-IMDb mappings across requests. API errors back off; missing ratings are left visible.

## Telemetry

The extension sends only rating lookups. Usage counts, missing-rating reports, sharing controls, and local report history have been removed. On worker startup, legacy reporting queues/history and sharing settings are cleared while rating/filter preferences and retry deadlines are preserved. The backend removes telemetry endpoints, report exports, and retention jobs. Restarting the updated backend removes previously stored telemetry tables while preserving shared provider mappings. Older extensions can still resolve ratings using their bundled selectors, but reporting and remote selector configuration are no longer available.

## Prepare the public release

[CHROMEWEBSTORE.md](CHROMEWEBSTORE.md) tracks listing copy, permission justifications, privacy disclosures, assets and outstanding release requirements.

1. Obtain rights covering hosted lookups, derived mappings/aliases, redistribution of ratings/votes, refreshes, and intended extension use. [IMDb's public export terms](https://data.imdb.com/non-commercial-datasets/) are personal/non-commercial; possession of the files is not production permission.
2. Complete the live validation above. Prime Video support covers primevideo.com, including regional paths; Amazon shopping domains and JioHotstar are outside scope.
3. Create one Railway service with its root set to `backend/`, using the included Dockerfile/config. Mount a persistent volume at `/data`. Load the catalogue snapshots into that volume. Configure `WATCHSIFT_ENVIRONMENT=production`. Keep one replica/process; use an HTTPS service domain. The health endpoint fails until a catalogue is loaded.
4. Enable Railway volume backups and test a restore on an isolated environment. Keep previous catalogue snapshots. After permission, refresh weekly with the importer; do not build unlicensed dataset downloads into deployment images.
5. Replace the local prototype privacy document with final publisher/contact information, API address, Railway processing/retention disclosures, and permitted IMDb attribution. Host a public privacy/support page. Supply store icons, actual extension screenshots, narrowly scoped permission explanations, remote-code declarations, and reviewer instructions. There is no public privacy/support URL or publisher contact configured yet.
6. Build from `extension/` with `WATCHSIFT_API_URL=https://YOUR_API_ORIGIN rtk proxy npm run build`. Then run `rtk proxy npm run package`. This produces `extension/artifacts/watchsift-0.1.0.zip`; it refuses a localhost or non-HTTPS build. Submit that ZIP through Chrome Web Store and retain each released build for rollback.

Production costs, hosted p95, volume restore, publisher details, and authenticated Netflix compatibility have not been verified. The API is intentionally one process: move rate limiting to shared storage before adding replicas. Hosting credentials are never embedded in the extension.

### Passive detail enrichment and shared mappings

Visible grid cards resolve in the background without a loader, navigation, focus changes, or interruption. WatchSift never opens or closes Netflix dialogs or navigates Prime Video automatically. When the user opens a Netflix detail dialog or Prime Video detail page, it reads the main title’s year and duration/type and retries matching. A rating appears in the detail metadata and on matching grid cards. Unknown or ambiguous titles remain unbadged.

The backend stores `provider_mapping(provider, provider_id, imdb_id)` in `operations.sqlite3`, keyed by `(provider, provider_id)`. Only year-qualified unique matches or clearly dominant matches qualified by both year and type are saved; title-only popularity guesses and negative results are not. Subsequent users can resolve the same provider ID without opening its detail dialog. Every hit checks the supplied title and available year/type against the current catalogue and reads current ratings/votes; conflicting metadata falls back to matching and can correct the mapping. Mappings survive backend restarts and catalogue replacement. They contain no user or profile identifiers and have no automatic expiry.

`/v1/resolve` accepts generic `provider` and `provider_id` fields, with `provider` defaulting to `netflix`. Existing `netflix_id` requests remain compatible; conflicting identities are rejected. Offline evaluation bypasses the shared mappings so previous lookups cannot inflate matching accuracy.

The browser retains only the current page’s display state, preferences, and connection status/retry deadlines. There are no additional permissions, private streaming-site API calls, background tabs, backend streaming-site scraping, or TMDB integration. Synthetic packaged tests cover passive dialog enrichment and uninterrupted scrolling; authenticated extension execution still needs live verification.


### Bundled provider selectors

`backend/src/catalogue/netflix.json` and `primevideo.json` are the selector sources bundled into the extension. Each page selects its provider's bundled configuration. The extension makes no configuration request and supports no runtime replacement; selector fixes require rebuilding and updating the extension. Host and provider ID validation remain bundled code.

`schema_version` identifies the reader format; `config_version` identifies the selector revision. Configuration supports fixed text/attribute reads, ordered fallbacks, ID URL locations, and selectors. Bundled configurations are schema-validated, with CSS selector syntax covered by tests. The backend no longer serves configuration endpoints; the JSON files remain as extension build inputs.

The extension sends bounded raw year, duration, explicit type, and row-label text alongside the provider identity and title. The backend validates years, interprets movie/series hints, shares consistent type hints across duplicate IDs in a request, resolves IMDb matches, and maintains shared provider mappings. The extension only retains the current page's tracked elements and results to render badges and avoid duplicate requests. No telemetry queues or report history are maintained.

### Prime Video support

On primevideo.com, WatchSift reads standard and search cards, poster carousels, and hero titles using stable data attributes. Explicit events, trailers, and episode tiles are excluded. User-opened details provide release year and runtime or season-count hints; the WatchSift rating/vote badge sits alongside Prime’s native metadata. Settings apply to both providers. Unknown or ambiguous titles remain visible. Prime may show season-specific release years, so conservative matching can leave series unbadged.

No account data, page URLs, tracking parameters, or hydration scripts are sent. Both bare and www hosts and regional paths are supported. Deploy the backend with both JSON files and the diagnostic migration before releasing the extension.
