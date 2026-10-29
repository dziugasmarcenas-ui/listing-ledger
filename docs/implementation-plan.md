# Implementation plan

## Goal

Make listing history reproducible when observations arrive late, exact events are retried, or a source observation is corrected. The demo uses synthetic data and reports asking prices only.

## Components

1. Validate and normalize event payloads at the API boundary, including strict integer minor-unit prices and timezone-aware observation times.
2. Persist immutable receipts in SQLite with per-stream sequence numbers and idempotent event IDs.
3. Project listing state at an optional receipt-sequence cutoff by resolving corrections before ordering effective observations by observation time.
4. Present the stored event timeline and server-derived projection in a same-origin, buildless reviewer interface.

## Failure behavior

Malformed events and invalid references return validation errors; unknown streams or listings return not found; conflicting reuse of an event ID returns conflict. A retry with the same normalized event returns the original receipt and does not add a sequence. A correction is a new receipt and does not replace its target in storage.

## Checks

The backend suite covers duplicate submissions, conflicting IDs, late arrivals, correction chains and sequence cutoffs, missing versus zero prices, timezone normalization, stream isolation, and persistence. The browser reads projections from the API instead of calculating them. Run the local checks with `./scripts/check.sh`.
