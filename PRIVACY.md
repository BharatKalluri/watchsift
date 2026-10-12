# WatchSift privacy policy

Updated 12 October 2026.

## About WatchSift

WatchSift is a free, open-source Chrome extension published by Bharat Kalluri. It displays IMDb ratings and vote counts on Netflix and Prime Video and optionally dims titles below your chosen thresholds. Source code and support are available at https://github.com/BharatKalluri/watchsift. For privacy questions, contact the publisher through https://github.com/BharatKalluri/watchsift/issues. Issues are public; do not include credentials or other private information.

## Information used for rating lookups

On supported Netflix and Prime Video pages, WatchSift reads visible title cards and details you open. It sends the provider name, provider title ID, title, a request identifier, and available year, duration, movie/series and carousel-row text to https://backend-production-8d772.up.railway.app/v1/resolve over HTTPS. This website content helps match titles and return ratings. WatchSift does not read or send streaming-service credentials, cookies, account or profile details, playback activity, or viewing history. It does not collect a general browsing-history list or send page URLs. It does not open dialogs or navigate pages for you.

## Information kept in your browser

Preferences (including enabled providers, filtering and minimum ratings/votes), connection status and retry deadlines are stored locally in your browser, without browser sync. Current-page title information and rating results are held in memory rather than a persistent extension cache. WatchSift sends no usage analytics, usage counters or missing-rating reports. Scripts and provider selectors are bundled with the extension; it does not download executable code or selector configuration.

## Backend storage and retention

The backend stores shared provider-to-IMDb mappings and submitted title/year/type context for successful matches in a PostgreSQL database hosted by PlanetScale. These records contain no user or profile identifiers and have no automatic expiry. Shared IMDb metadata, ratings and vote counts are reused for seven days after a successful fetch, then refreshed on demand. Seven days is a freshness window, not a deletion deadline: older records remain, including when refresh fails. Missing-title results are not cached.

## Service providers and logs

Railway hosts the matching API and processes network requests. The server receives your IP address and uses it transiently for rate limiting; WatchSift does not request GPS or device-location access. Railway may process IP addresses and HTTP request metadata in infrastructure logs. Application logs include OMDb lookup titles, IMDb IDs and year/type hints for diagnostics. Logs are managed by the hosting provider and their retention depends on the service plan and provider practices; WatchSift does not promise a fixed deletion period for them.

## OMDb and external links

The backend sends titles, year/type hints and IMDb IDs to OMDb (https://www.omdbapi.com/) to retrieve metadata and ratings. Provider names, streaming-service title IDs and raw duration/row text are not forwarded to OMDb. OMDb receives the backend server IP rather than your browser IP. Railway and PlanetScale process data to operate the hosted service. If you click an IMDb badge or an external link, the destination handles that visit under its own policies.

## Use and security

Information is used to provide, maintain and diagnose WatchSift’s rating and filtering features. It is not sold, used for advertising, used for unrelated purposes, or used to determine creditworthiness or lending eligibility. Transfers are limited to the service providers described here for these purposes. WatchSift’s use of information complies with the Chrome Web Store User Data Policy, including its Limited Use requirements. Production lookup requests use HTTPS and omit browser credentials. No transmission or storage system can guarantee absolute security.

## Your controls and policy updates

Disable a provider or pause WatchSift in the popup to stop its future rating lookups; uninstall the extension to remove its browser-local settings. Shared title mappings and IMDb cache records are not tied to an individual account and are not removed by uninstalling. Privacy questions and requests can be raised through the support link above. Changes to this policy will be published with an updated date. WatchSift is independent and is not affiliated with Netflix, Amazon, IMDb or OMDb.
