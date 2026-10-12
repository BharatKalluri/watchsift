# WatchSift Netflix extension plan
## Summary
Build a Chrome Manifest V3 extension for Netflix India, initially supporting English UI and Indian-language titles. Show IMDb rating and vote-count badges, with an optional AND filter that dims cards below either threshold.

Default thresholds: **IMDb rating ≥ 7.0 AND vote count ≥ 1,000**. IMDb counts rating votes, not written reviews. Badges start enabled; filtering starts disabled.

Use TypeScript/Vite for the extension and Python/FastAPI with SQLite for matching. Develop locally with the supplied datasets. Public hosting and Chrome Web Store publication require appropriate data permission first.
## Extension
- Preserve Netflix clicks, hover previews, keyboard navigation, playback, and carousel layout. Add accessible IMDb links and rating/vote badges.
  
- Popup controls: extension enabled, filtering enabled, rating/vote thresholds, analytics consent, diagnostics consent, service status, and locally submitted diagnostic reports. Store preferences in chrome.storage.local.
  
- Dim known failures to 40% opacity, restoring visibility on hover/focus. Unknown, ambiguous, unrated, expired, and unavailable results remain undimmed.
  
- One Netflix DOM adapter extracts card ID, title, and available year/type. No private API interception, credentials, or playback automation.
  
- MutationObserver handles dynamic/reused cards; IntersectionObserver limits lookups to visible cards. Rendering is idempotent and requests are deduplicated.
  
- Content script → service worker → API → badge/filter renderer. No browser rating or metadata caching. Grid lookups run in the background; user-opened dialogs supply year/type. The backend shares year-qualified provider-to-IMDb mappings.
  
- Minimal permissions: storage, Netflix content-script matches, API host access. All executable code is bundled; remote responses are data only.
  
## Data and API
- Stream ratings, basics, and alternate-title gzipped TSV exports into indexed SQLite. Retain rated movies, TV movies, series, and miniseries, including low-vote titles.
  
- Normalize Unicode, case, punctuation, and whitespace consistently; preserve scripts. Narrow exact aliases by available year/type, using explicit Netflix film/series row labels shared across duplicate cards. Prefer punctuation-preserving exact primary titles when that does not narrow away an unrated primary namesake. When exact lookup is empty, try limited Unicode cleanup, Latin accent folding, descriptive subtitle removal, and trailing part-I removal; fallback matches must be unique and rated. Include IMDb TV specials independently of film/show row labels. Other collisions require at least 1,000 votes and 100 times the next candidate's votes. These title/popularity heuristics can select a wrong namesake; closer ties stay unknown.
  
- Netflix IDs identify cards, not IMDb titles. Use title/year/type evidence and keep results only for the current rendered page; do not persist lookup results.
  
- Versioned validated catalogue snapshots with atomic activation and previous-snapshot rollback. Manual refresh locally; weekly refresh after data permission.
  
- POST /v1/resolve accepts at most 50 bounded card records and returns matched/ambiguous/not_found results with IMDb ID, rating, votes, and dataset version/date.
  
- No browser result caches; shared backend mappings use `(provider, provider_id)` and current IMDb ratings. Five-second request timeout; backoff and Retry-After support. Only results obtained for the current rendered card may dim it. Lookups are nonblocking. Year/type enrichment occurs only in user-opened Netflix dialogs.
  
- One FastAPI service on Railway with a persistent volume, read-only catalogue, separate operational database, backups, and restore checks. API v1 remains compatible with installed extensions. Bounded per-IP rate limiting; no embedded secrets or accounts.
  
## Analytics and diagnostics
- Independent explicit opt-ins, both off initially. Turning either off clears its upload queue.
  
- POST /v1/metrics receives daily lookup/match/badge/failure/filter counters and extension version. No titles, URLs, or persistent user ID. Retain aggregates for 90 days.
  
- POST /v1/unmatched receives Netflix ID, title/year/type, failure category, and extension/matcher versions, only after separate consent. Locally and server-side deduplicate, with at most 100 distinct reports daily. Retain deduplicated reports for 30 days.
  
- Prominent Help fix missing ratings feature explains exact fields and potential human review; local report history is visible. Export developer reports for regression fixtures, never automatically trust reports as mappings.
  
- No lookup-body logging, cookies, profiles, or full page URLs. Privacy disclosures include hosting-provider handling and retention.
  
## Delivery and acceptance
1. Inspect authenticated Netflix India and save sanitized DOM fixtures. Verify 100 titles covering Indian-language aliases, remakes, duplicate names, movies, and series.
  
2. Local importer, API, extension, filtering, popup, automatic detail lookups.
  
3. Consent flows, diagnostics, metrics, outages, packaged-extension integration tests.
  
4. Only after data permission: Railway deployment, privacy/support pages, store assets, disclosures, reviewer instructions, and ZIP submission. Advertise Netflix only.
  

- Zero wrong badges in the verified 100-title set; report extraction and matching coverage separately. Target 80% coverage of rated supported titles.
  
- Unit tests for aliases, missing fields, ambiguity, series versus episodes, TSV nulls, and inclusive thresholds: 7.0/1,000 passes; falling below either fails.
  
- Fixture/integration tests for lazy loading, SPA navigation, recycled/duplicate cards, fresh lookup failures, worker restarts without cache reuse, malformed responses, timeouts, rate limits, consent isolation/revocation, deduplication, and sensitive-field absence.
  
- Live manual checks for Netflix search, browsing, hover, keyboard, and playback.
  
- Load test 20 simultaneous 50-card requests, targeting API p95 below 500 ms. Verify catalogue rollback and backup restoration.
  
## Boundaries
No Prime Video/JioHotstar, hiding, accounts, recommendations, payments, or fuzzy matching in v1.

Live Netflix DOM, full data integrity, index size, and hosting costs need verification. IMDb data permission blocks public release. Netflix layout changes require maintenance.
