# WatchSift popup

Mode: Operate. A viewer adjusts IMDb rating and vote-count minimums, then returns to Netflix.

## Direction contract
Build directly in code, as confirmed by the user. The visual world is a compact cinema control panel: charcoal-green surface, warm gold active controls and measured tabular numerals, an editorial serif wordmark, plain readable labels. The popup prioritizes the two thresholds and their AND relationship. Optional sharing stays in a disclosure with precise consent copy. Gold also carries the on-card rating badge.

## Constraints
360 px Chrome popup, scrollable when consent details expand. Native number-input validation and keyboard interaction. No motion beyond a short switch-state transition, with reduced-motion respected. Diagnostic metadata must remain readable and wrap. Unknown ratings remain visible, and card interaction must remain intact.

## Verification
Packaged Chromium popup, expanded consent, and card screenshots in .impeccable/review. Synthetic Netflix fixture is explicit; no live-site reliability claim. The manual detector returned no findings in degraded regex mode; computed contrast and selector analysis were unavailable.
