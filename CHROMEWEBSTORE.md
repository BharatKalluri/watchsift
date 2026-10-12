# Chrome Web Store Listing — WatchSift

Last updated: 2026-10-12. Draft; not submitted or ready for public distribution.

## Store listing

**Extension name:** WatchSift – IMDb Ratings & Vote Count Filter

**Short description:** IMDb ratings and vote counts on Netflix and Prime Video, with a filter to dim titles below your minimums.

**Detailed description:**

See IMDb ratings and vote counts alongside Netflix and Prime Video titles while you browse.

Choose a minimum rating and number of rating votes. Optional filtering dims titles that fall below either minimum. Defaults are 7.0 out of 10 and 1,000 rating votes; filtering starts off. Missing or uncertain ratings leave titles visible. Opening a Netflix detail dialog can help resolve titles with similar names.

WatchSift adds ratings as new cards appear. It does not open dialogs, play videos, or interrupt your browsing. Matching can be uncertain and ratings are fetched through OMDb.

Settings stay in your browser. Rating lookups send provider names and title IDs, titles, and available title metadata to WatchSift's matching service. No usage counts or missing-rating reports are sent. WatchSift does not read streaming-service credentials, cookies, profiles, or viewing history.

IMDb ratings provided through OMDb.

WatchSift is independent and is not affiliated with Netflix, Amazon, or IMDb. A provider account may be required to browse its catalogue.

**Category:** Entertainment.

**Single purpose:** Add IMDb ratings and vote counts to Netflix and Prime Video titles, with an optional minimum-rating and vote-count filter.

**Primary language:** English. Initial validation targets Netflix and Prime Video India with English UI.

## Graphics and assets

| Asset | Dimensions | Status | File |
|---|---|---|---|
| Store icon | 128×128 PNG | Created; verify final branding before submission | extension/public/icons/128.png |
| Toolbar icons | 16×16, 32×32, 48×48 PNG | Created; dimensions covered by tests | extension/public/icons/ |
| Store screenshots | 1280×800 JPEG | Prepared from user-provided Netflix and Prime Video screenshots | extension/artifacts/store-screenshots/netflix.jpg; extension/artifacts/store-screenshots/primevideo.jpg |
| Small promo tile | 440×280 | Required; not prepared | Pending |

Existing fixture screenshots are development evidence, not approved store assets. Capture the actual popup, visible rating badges, and optional filtering for the final release; obtain any needed rights for streaming-site imagery.

## Permissions justification

| Entry | Type | Justification |
|---|---|---|
| storage | permissions | Save rating/filter preferences and connection status locally; retain retry deadlines across worker restarts. No rating-result cache or browser sync. |
| https://backend-production-8d772.up.railway.app/* | host_permissions | Send visible title information to WatchSift's matching service and receive IMDb ratings and vote counts. |
| https://www.netflix.com/* and https://netflix.com/* | content_scripts.matches | Read visible Netflix cards and user-opened title details and add rating badges and optional dimming. Runs only in the top frame. |
| https://www.primevideo.com/* and https://primevideo.com/* | content_scripts.matches | Read visible Prime Video cards and user-opened details and add rating/vote badges and optional dimming. Runs only in the top frame; Amazon shopping domains are excluded. |

No tabs, activeTab, scripting, cookies, history, webRequest, alarms, or all-URLs permissions are requested. Tab IDs are used solely to notify the extension's own content scripts of preference changes; tab URLs and titles are not read.

## Privacy and data use

**Does the extension handle user data?** Yes. Core title lookups transmit current supported-site page content. No usage analytics or missing-rating reports are collected.

| Data type | Handled or collected | Transmitted off-device | Purpose / recipients |
|---|---|---|---|
| Personally identifying information | No account/profile identifier; network IP received transiently | IP inherently accompanies requests | Connection, transient API rate limiting and hosting-provider network processing |
| Health / financial information | No | No | None |
| Authentication information | No credentials, cookies, or tokens | No | None |
| Personal communications | No | No | None |
| Location | Network IP address; no GPS or device-location access | IP inherently accompanies requests | Transient server rate limiting and hosting network processing; Chrome categorizes IP addresses as Location |
| Browsing history | No URL/history log or streaming-site viewing history | No history list | Current supported-site titles are website content, disclosed below |
| Website content | provider names and title IDs, titles, available year/duration/type/row-label text | Yes, to matching API; title/year/type and IMDb IDs are forwarded to OMDb | Return ratings; provider mappings retain submitted title/year/type without user/profile IDs or automatic expiry; shared IMDb data is reused for seven days |
| User activity | No usage counters | No | None |
| Preferences and connection state | Browser-local preferences, connection status and retry deadlines | Stay local | Apply controls and respect retry backoff |

Core lookups are not an optional analytics feature. Do not select “no data collected” in the dashboard. Finalize disclosure categories against the live publisher/service before submission.

The extension sends no telemetry. The PostgreSQL backend stores shared provider mappings and cached IMDb data in the `watchsift` schema. Telemetry submissions, report exports, and remote selector configuration are no longer supported. No persistent extension rating, mapping, metadata or downloaded parser-config cache is maintained.

**Data-use certification to confirm before submission:** no data sale, unrelated use, advertising use, creditworthiness or lending use. The current implementation supports these statements; publisher and hosting practices must match them.

## Privacy policy

Public policy URL: https://github.com/BharatKalluri/watchsift/blob/main/PRIVACY.md. Source: PRIVACY.md, mirrored in extension/public/privacy.html and packaged as privacy.html. Updated for the production service, publisher/support, transmitted title content, shared database retention, IP processing and diagnostic logs.

The privacy draft declares Website content and Location (network IP), no remote code, the single purpose, storage/host permission justifications, and the three data-use certifications.

## Distribution and developer information

Visibility: planned public release; currently local development only. Initial region: India. Publisher name, monitored contact email, support channel and homepage: pending user-supplied details.

## Version history

| Version | Date | Changes | Status |
|---|---|---|---|
| 0.1.0 | 2026-10-12 | Local MVP; React/Tailwind popup; bundled provider selectors; removed extension/backend telemetry, report exports and configuration endpoints; preserved backoff, bounded responses, and frame-batched badges; replaced the popup dataset date with a linked IMDb data credit | Draft, never submitted |

## Review notes and release blockers

The manifest uses MV3, a module service worker, Chrome 116+ and packaged JavaScript. Extension pages restrict scripts to the package, disallow objects, and connect only to the configured backend. Provider selectors and text/attribute readers are bundled; no remote configuration or code is downloaded.

The worker registers listeners synchronously. Persistent preferences/status/backoff live in chrome.storage.local; Promise sequencing is transient coordination only. Network timeouts use abort signals, not scheduled background jobs. No unnecessary side-panel, offscreen, identity, capture, userScripts, context-menu or DevTools features are added.

The production API is https://backend-production-8d772.up.railway.app, deployed in Bharat Kalluri's Projects on Railway. Health and a live rating lookup passed. The 0.1.0 ZIP was built with this origin in its worker, host permission and CSP; local development still defaults to localhost. Public release still requires OMDb data-use terms, a complete live privacy policy and support details, approved store screenshots, and the existing human-verified 100-title matching/adapter validation. Heuristic title matching can select the wrong namesake; selector fixes require an extension update.

Packaging rejects local/non-HTTPS API origins. Backend startup and packaging require no data-license confirmation flag. Packaging ships only built runtime files and creates a fresh ZIP before replacing an existing artifact. No store upload, publication, developer account registration, or rights approval has been performed.

The Chrome Web Store draft (item ID `ojlaekjpcpiagblpckjpomnjlhfcdodp`) has its description, Entertainment category, English language, existing 128×128 icon, GitHub homepage and GitHub Issues support link filled. The description identifies WatchSift as free and open source and discloses title lookups and shared caching. Two store screenshots are uploaded; the production privacy policy is published in the public repository. No submission has been made.

No rejection history.

## Ordered publishing todo

- [ ] Check [OMDb data-use terms](https://www.omdbapi.com/) for the planned public hosted service, ratings/votes display, mappings and distribution.
- [ ] Complete authenticated Netflix India validation with 100 independently verified titles: no wrong badges and at least 80% correct coverage of recognized rated titles. Verify extraction separately, including search, carousels, hover/details, keyboard navigation and uninterrupted playback. Test Prime Video's real cards, details and regional paths too; current browser tests use synthetic pages.
- [ ] Deploy the backend with an OMDb API key, one process/replica, an HTTPS origin and the PostgreSQL `DATABASE_URL`. Verify health, latency, expected-load behavior, outages and rate limiting. Enable backups, test an isolated mapping restore, and establish the OMDb quota and hosting budget.
- [ ] Finalize publisher/contact details and publish privacy/support pages. Replace the prototype policy with the production API, hosting processing/log-retention practices and required attribution. Disclose transmitted website content and persistent shared mappings; no telemetry does not mean no data handling.
- [ ] Prepare final branding, the 128×128 PNG icon, a required 440×280 promotional image and at least one real 1280×800 or 640×400 screenshot. Capture badges, filtering and popup controls. [Chrome image requirements](https://developer.chrome.com/docs/webstore/images).
- [ ] Register/configure the developer account if needed, pay the registration fee, complete account security/verification prompts, and choose publisher details and distribution countries. [Account registration](https://developer.chrome.com/docs/webstore/register).
- [x] Build using `rtk proxy env WATCHSIFT_API_URL=https://backend-production-8d772.up.railway.app npm run build` from `extension/`. TypeScript checks and 43 extension unit tests passed.
- [ ] Smoke-test this exact build against the hosted API in a clean Chrome profile. Confirm preferences, unknown titles, disabled providers, API failures and worker restart behavior; complete browser checks from README.
- [ ] Package using `rtk proxy npm run package`. Inspect `extension/artifacts/watchsift-0.1.0.zip` and its manifest: production HTTPS permission/CSP, runtime files only, no localhost endpoint or secrets. Retain the released ZIP.
- [ ] Fill in listing copy, single purpose, storage/site/API permission justifications, website-content disclosures, data-use certifications and the public privacy URL. Declare no remotely hosted code for the current bundled implementation. [Privacy fields](https://developer.chrome.com/docs/webstore/cws-dashboard-privacy).
- [ ] Provide reproducible reviewer steps for supported streaming sites and any necessary authorized test access. Upload the ZIP, select distribution and submit for review; use deferred publishing if you want to control launch timing. [Submission instructions](https://developer.chrome.com/docs/webstore/publish).
