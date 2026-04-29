# QDII Radar Seed Cache Staleness Logging Design

## Background

QDII Radar now persists `limit + nav + nav_rate` to `data/fund_limit_cache.json` so `/api/funds` can avoid returning `0` for first-screen fields after restart. This fixes correctness on restart and fresh-clone style startup, but introduces a new operational question: the seed cache may become old.

The current system prioritizes "avoid showing 0 on first screen" over minute-level freshness during process startup. That tradeoff is acceptable, but stale seed-cache age is currently invisible.

## Problem

When `fund_limit_cache.json` is old, the service still loads it and serves cached values on first request, then relies on background refresh to update values. This behavior is intentional, but operators currently get no clear signal that startup depended on stale seed data.

## Goal

Make seed-cache staleness visible in logs without changing `/api/funds` response shape, frontend behavior, or startup fast-path semantics.

## Non-Goals

- No frontend changes
- No API contract changes
- No new health endpoint fields
- No synchronous refresh added to `/api/funds`
- No startup-triggered bulk refresh in this change

## Chosen Approach

Implement startup-time seed-cache age inspection with warning-only logging.

After `load_limit_cache_store()` reads `data/fund_limit_cache.json`, the service should inspect cache timestamps and emit:

- an info log summarizing cache entry count and age range
- a warning log when the cache is older than a relaxed seed-cache threshold

This preserves the current behavior:

- first request still prefers cached values over `0`
- background refresh still updates values asynchronously
- no user-facing interface changes occur

## Alternatives Considered

### Option A1 — Warning-only startup logging (chosen)

Pros:
- smallest possible change
- no frontend/API risk
- immediately improves operational visibility

Cons:
- does not actively refresh data sooner
- relies on logs instead of structured monitoring

### Option A2 — Warning + startup background refresh

Pros:
- cache becomes fresh sooner after process start

Cons:
- increases startup-time upstream traffic
- adds behavior change and potential rate-limit risk
- no longer a pure observability patch

### Option A3 — Warning + health/metrics exposure

Pros:
- stronger monitoring integration

Cons:
- expands surface area beyond the minimal need
- may require downstream consumers or monitoring updates

## Detailed Design

### New stale threshold

Keep the existing meanings separate:

- `LIMIT_CACHE_DURATION = 15 minutes` remains the request-path freshness threshold
- add a separate seed-cache staleness threshold for startup observability, recommended at `24 hours`

Reasoning:
- request-path freshness determines whether cached values are considered current for serving logic
- seed-cache staleness only answers whether the bootstrapped disk cache is operationally old
- the seed cache exists primarily to avoid first-screen zeros, not to guarantee minute-level freshness at boot

### Startup inspection behavior

During startup, after disk cache load:

1. Count cache entries
2. Collect valid timestamps from cache records
3. Compute oldest and newest timestamps
4. Compare oldest timestamp age against the seed stale threshold
5. Emit logs:
   - `info` summary when cache exists and timestamps are valid
   - `warning` when cache age exceeds threshold
   - `warning` when cache entries exist but timestamps are missing/invalid

### Logging semantics

#### Normal informational log

Example:

`Loaded limit cache from disk: 48 entries, oldest=2026-04-28T09:12:00, newest=2026-04-29T08:57:00`

#### Stale warning log

Example:

`Seed limit cache is stale (>24h): 48 entries, oldest=2026-04-27T07:10:00, newest=2026-04-27T07:12:00; serving cached values first and relying on background refresh`

#### Invalid timestamp warning

Example:

`Seed limit cache loaded with 48 entries but no valid timestamps were found; serving cached values first and relying on background refresh`

## Error Handling

- If cache file does not exist: keep current behavior, no crash
- If cache file is malformed: keep current load error handling, log warning/error, continue startup
- If some entries have bad timestamps: ignore invalid timestamps for aggregation; warn if none are usable
- Logging must never block startup or change API behavior

## Testing Strategy

### Manual verification

1. Start service with recent `fund_limit_cache.json`
   - confirm info log prints entry count and age range
   - confirm no API behavior changes
2. Modify cache timestamps to older than threshold
   - restart service
   - confirm stale warning log appears
3. Corrupt or remove timestamps in cache entries
   - restart service
   - confirm invalid timestamp warning appears
4. Remove cache file entirely
   - confirm service still starts without crash

## Acceptance Criteria

- Startup logs cache entry count and age range when valid timestamps exist
- Startup logs a warning when seed cache is older than threshold
- `/api/funds` response structure remains unchanged
- Existing restart-first-request fix remains intact
- No synchronous startup fetch or request-path slowdown is introduced

## Rollback

Rollback is trivial:
- revert the logging-only code change
- keep existing cache persistence behavior intact

## Files Expected to Change

- `server.py` only
