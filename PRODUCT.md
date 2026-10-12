# WatchSift

<!-- impeccable:product-schema 1 -->

## Platform
Web: Chrome Manifest V3 extension, distributed on Chrome Web Store after data permission.

## Stack
Confirmed: TypeScript/Vite extension, Python/FastAPI API, SQLite, Railway hosting.

## Users and purpose
Netflix and Prime Video India viewers using English UI, including Indian-language movies and series. Reduce browsing effort with IMDb ratings and vote-count badges and an optional AND filter.

## Confirmed behavior
Badges enabled, filtering disabled initially. Thresholds are IMDb 7.0 and 1,000 rating votes. Unknown titles stay visible. Two independent opt-ins: aggregate counters and automatic unmatched-title diagnostics. No accounts, recommendations, or playback automation.

## Constraints
Correct matching takes priority over coverage. No private API or credential access. Local prototype first; public IMDb distribution permission is unresolved. Preserve streaming-site layout, clicks, and accessibility.
