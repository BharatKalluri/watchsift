# Chrome Web Store Listing — WatchSift

Last updated: 2026-10-12. Draft; not submitted or ready for public distribution.

## Store listing

**Extension name:** WatchSift – IMDb Ratings & Vote Count Filter

**Short description:** IMDb ratings and vote counts on Netflix and Prime Video, with a filter to dim titles below your minimums.

**Detailed description:**

See IMDb ratings and vote counts alongside Netflix and Prime Video titles while you browse.

Choose a minimum rating and number of rating votes. Optional filtering dims titles that fall below either minimum. Defaults are 7.0 out of 10 and 1,000 rating votes; filtering starts off. Missing or uncertain ratings leave titles visible. Opening a Netflix detail dialog can help resolve titles with similar names.

WatchSift adds ratings as new cards appear. It does not open dialogs, play videos, or interrupt your browsing. Matching can be uncertain and ratings depend on the available IMDb dataset.

Settings stay in your browser. Rating lookups send provider names and title IDs, titles, and available title metadata to WatchSift's matching service. No usage counts or missing-rating reports are sent. WatchSift does not read streaming-service credentials, cookies, profiles, or viewing history.

Rating data courtesy of IMDb.

WatchSift is independent and is not affiliated with Netflix, Amazon, or IMDb. A provider account may be required to browse its catalogue.

**Category:** Fun.

**Single purpose:** Add IMDb ratings and vote counts to Netflix and Prime Video titles, with an optional minimum-rating and vote-count filter.

**Primary language:** English. Initial validation targets Netflix and Prime Video India with English UI.

## Graphics and assets

| Asset | Dimensions | Status | File |
|---|---|---|---|
| Store icon | 128×128 PNG | Created; verify final branding before submission | extension/public/icons/128.png |
| Toolbar icons | 16×16, 32×32, 48×48 PNG | Created; dimensions covered by tests | extension/public/icons/ |
| Store screenshot | 1280×800 or 640×400 | Required; not prepared | Pending |
| Small promo tile | 440×280 | Required; not prepared | Pending |

Existing fixture screenshots are development evidence, not approved store assets. Capture the actual popup, visible rating badges, and optional filtering for the final release; obtain any needed rights for streaming-site imagery.

## Permissions justification

| Entry | Type | Justification |
|---|---|---|
| storage | permissions | Save rating/filter preferences and connection status locally; retain retry deadlines across worker restarts. No rating-result cache or browser sync. |
| Configured WatchSift API origin only | host_permissions | Send visible title information for matching, receive ratings. Development uses http://127.0.0.1:8000/*; replace with the licensed production HTTPS origin before submission. |
| https://www.netflix.com/* and https://netflix.com/* | content_scripts.matches | Read visible Netflix cards and user-opened title details and add rating badges and optional dimming. Runs only in the top frame. |
| https://www.primevideo.com/* and https://primevideo.com/* | content_scripts.matches | Read visible Prime Video cards and user-opened details and add rating/vote badges and optional dimming. Runs only in the top frame; Amazon shopping domains are excluded. |

No tabs, activeTab, scripting, cookies, history, webRequest, alarms, or all-URLs permissions are requested. Tab IDs are used solely to notify the extension's own content scripts of preference changes; tab URLs and titles are not read.

## Privacy and data use

**Does the extension handle user data?** Yes. Core title lookups transmit current supported-site page content. No usage analytics or missing-rating reports are collected.

| Data type | Handled or collected | Transmitted off-device | Purpose / recipients |
|---|---|---|---|
| Personally identifying information | No account/profile identifier; network IP received transiently | IP inherently accompanies requests | Connection and transient API rate limiting; finalize hosting-provider practices before release |
| Health / financial information | No | No | None |
| Authentication information | No credentials, cookies, or tokens | No | None |
| Personal communications | No | No | None |
| Location | No location collection | No location fields | None |
| Browsing history | No URL/history log or streaming-site viewing history | No history list | Current supported-site titles are website content, disclosed below |
| Website content | provider names and title IDs, titles, available year/duration/type/row-label text | Yes, to matching API | Return ratings; shared provider-to-IMDb mappings have no user/profile ID and no automatic expiry |
| User activity | No usage counters | No | None |
| Preferences and connection state | Browser-local preferences, connection status and retry deadlines | Stay local | Apply controls and respect retry backoff |

Core lookups are not an optional analytics feature. Do not select “no data collected” in the dashboard. Finalize disclosure categories against the live publisher/service before submission.

The extension sends no telemetry. Upgrading clears obsolete browser-local reporting queues/history and sharing settings while preserving rating/filter preferences and retry deadlines. Starting the updated backend removes previously stored telemetry tables while preserving shared provider mappings. Telemetry submissions, report exports, and remote selector configuration are no longer supported. No persistent extension rating, mapping, metadata or downloaded parser-config cache is maintained.

**Data-use certification to confirm before submission:** no data sale, unrelated use, advertising use, creditworthiness or lending use. The current implementation supports these statements; publisher and hosting practices must match them.

## Privacy policy

Source: extension/public/privacy.html; packaged as privacy.html. Public policy URL: pending. Publisher, contact channel, hosted API and infrastructure processing details must be completed and the URL verified before submission.

## Distribution and developer information

Visibility: planned public release; currently local development only. Initial region: India. Publisher name, monitored contact email, support channel and homepage: pending user-supplied details.

## Version history

| Version | Date | Changes | Status |
|---|---|---|---|
| 0.1.0 | 2026-10-12 | Local MVP; React/Tailwind popup; bundled provider selectors; removed extension/backend telemetry, report exports and configuration endpoints; preserved backoff, bounded responses, and frame-batched badges; replaced the popup dataset date with a linked IMDb data credit | Draft, never submitted |

## Review notes and release blockers

The manifest uses MV3, a module service worker, Chrome 116+ and packaged JavaScript. Extension pages restrict scripts to the package, disallow objects, and connect only to the configured backend. Provider selectors and text/attribute readers are bundled; no remote configuration or code is downloaded.

The worker registers listeners synchronously. Persistent preferences/status/backoff live in chrome.storage.local; Promise sequencing is transient coordination only. Network timeouts use abort signals, not scheduled background jobs. No unnecessary side-panel, offscreen, identity, capture, userScripts, context-menu or DevTools features are added.

Public release still requires IMDb data/distribution rights, production HTTPS API, a complete live privacy policy and support details, approved store screenshots, and the existing human-verified 100-title matching/adapter validation. Heuristic title matching can select the wrong namesake; selector fixes require an extension update.

Packaging rejects local/non-HTTPS API origins. Backend startup and packaging require no data-license confirmation flag. Packaging ships only built runtime files and creates a fresh ZIP before replacing an existing artifact. No store upload, publication, developer account registration, or rights approval has been performed.

No rejection history.

## Ordered publishing todo

- [ ] Confirm IMDb rights for the public hosted service, ratings/votes display, derived mappings, refreshes and intended distribution. The supplied files are not cleared for this release. [IMDb dataset terms](https://data.imdb.com/non-commercial-datasets/).
- [ ] Complete authenticated Netflix India validation with 100 independently verified titles: no wrong badges and at least 80% correct coverage of recognized rated titles. Verify extraction separately, including search, carousels, hover/details, keyboard navigation and uninterrupted playback. Test Prime Video's real cards, details and regional paths too; current browser tests use synthetic pages.
- [ ] Deploy the backend with a licensed catalogue, one process/replica, an HTTPS origin and persistent `/data` volume. Verify health, latency, expected-load behavior, outages and rate limiting. Enable backups, test an isolated restore and catalogue rollback, and establish the licensed refresh schedule and hosting budget.
- [ ] Finalize publisher/contact details and publish privacy/support pages. Replace the prototype policy with the production API, hosting processing/log-retention practices and required attribution. Disclose transmitted website content and persistent shared mappings; no telemetry does not mean no data handling.
- [ ] Prepare final branding, the 128×128 PNG icon, a required 440×280 promotional image and at least one real 1280×800 or 640×400 screenshot. Capture badges, filtering and popup controls. [Chrome image requirements](https://developer.chrome.com/docs/webstore/images).
- [ ] Register/configure the developer account if needed, pay the registration fee, complete account security/verification prompts, and choose publisher details and distribution countries. [Account registration](https://developer.chrome.com/docs/webstore/register).
- [ ] Build using `WATCHSIFT_API_URL=https://YOUR_API_ORIGIN rtk proxy npm run build` from `extension/`. Run extension formatting/unit/browser checks and backend checks from README, then smoke-test this exact build against the hosted API in a clean Chrome profile. Confirm preferences, unknown titles, disabled providers, API failures and worker restart behavior.
- [ ] Package using `rtk proxy npm run package`. Inspect `extension/artifacts/watchsift-0.1.0.zip` and its manifest: production HTTPS permission/CSP, runtime files only, no localhost endpoint or secrets. Retain the released ZIP.
- [ ] Fill in listing copy, single purpose, storage/site/API permission justifications, website-content disclosures, data-use certifications and the public privacy URL. Declare no remotely hosted code for the current bundled implementation. [Privacy fields](https://developer.chrome.com/docs/webstore/cws-dashboard-privacy).
- [ ] Provide reproducible reviewer steps for supported streaming sites and any necessary authorized test access. Upload the ZIP, select distribution and submit for review; use deferred publishing if you want to control launch timing. [Submission instructions](https://developer.chrome.com/docs/webstore/publish).
