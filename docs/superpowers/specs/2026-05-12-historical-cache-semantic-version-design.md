# Historical Cache Semantic Version Design

## Goal
Prevent `historical_nav_cache` from reusing stale data when the business meaning of the metric changes (for example, from 1-year change to YTD change).

## Chosen Approach
Add a cache semantic version field to `historical_nav_cache` and require reads to match the current metric semantic.

Current semantic target:
- `ytd_v1`

## Scope
In scope:
- Add semantic/version field to cached historical metric records
- Treat missing or mismatched semantic versions as cache misses
- Write new cache entries using the current semantic version
- Add regression coverage proving old-semantic cache is ignored
- Lightweight runtime schema backfill for existing SQLite databases

Out of scope:
- Renaming unrelated tables or broad database refactors
- Reworking the YTD calculation itself
- Changing API fields again

## Design

### Data model
Add a new field to `HistoricalNavCache`:
- `metric_semantic: String`

Value written by current code:
- `ytd_v1`

### Runtime constant
Define a single source of truth constant in backend code:
- `CURRENT_HISTORICAL_METRIC_SEMANTIC = "ytd_v1"`

### Cache read behavior
`get_historical_cache()` should:
1. Load the row by `fund_code`
2. Check cache age as before
3. Check `cached.metric_semantic == CURRENT_HISTORICAL_METRIC_SEMANTIC`
4. Return cache hit only when both age and semantic match
5. Otherwise treat it as a miss

Backward compatibility rule:
- Old rows without a populated semantic version must be treated as mismatched and ignored

### Cache write behavior
`set_historical_cache()` should always write:
- latest `percentage_change`
- `days_calculated`
- `cached_at`
- `metric_semantic = ytd_v1`

### Migration strategy
Keep this lightweight and self-healing:
- Add the new ORM column
- During `init_db()`, inspect `historical_nav_cache`
- If `metric_semantic` column is missing, run:
  - `ALTER TABLE historical_nav_cache ADD COLUMN metric_semantic VARCHAR(32)`
- Do not rely on manual cache clearing for correctness
- Existing rows become effectively invalid until refreshed because their semantic will not match

### Testing
Add regression coverage for:
1. Old semantic cache row exists → request must recompute instead of reusing row
2. Current semantic cache row exists → request may reuse cached row
3. Recomputed row is written back with `metric_semantic = ytd_v1`

For minimal impact, unit tests may focus first on cache read/write behavior around `get_historical_cache()` and `set_historical_cache()`.

## Risks
- SQLite schema migration must be handled carefully if the column does not exist yet
- Tests must avoid depending on preexisting DB state

## Success criteria
- Old one-year semantic cache no longer contaminates YTD results
- Manual cache clearing is no longer required after semantic changes
- Existing YTD behavior remains unchanged for fresh matching cache rows
