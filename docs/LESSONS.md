# Lessons Learned

## Recent Major Lessons

### 1. Widespread `valuation=0` was a provider problem first

Symptom:

- many exchange-like QDII funds showed `valuation = 0`
- NAV data was still present

What this taught us:

- do not assume merge logic is broken first
- quote-source outages and disconnects can fail independently from NAV fetching

Practical rule:

- when many funds lose live price at once but NAV remains normal, verify upstream quote endpoints before rewriting local business logic

### 2. Heuristic classification can create fake exchange funds in the UI

Symptom:

- funds like `160213` and `539001` appeared in the exchange tab
- they had no stable real-time quote source
- users experienced this as “bad exchange data”

Root issue:

- heuristic candidate logic leaked into user-visible classification

Fix direction:

- keep candidate detection internal
- only expose `isExchangeTraded=true` after a real quote is successfully fetched

## Pitfalls to Avoid

### Don’t equate name/code patterns with confirmed tradability

These are useful only as fetch hints:

- code prefixes
- `ETF`
- `LOF`
- old docs or legacy labels

They are not enough for user-visible classification.

### Don’t use `valuation > 0` as the type definition

`valuation` can carry different meanings depending on the data path.

Using `valuation > 0` as shorthand for “exchange-traded” is too loose and causes drift between docs, backend logic, and frontend fallback.

### Don’t fix backend only

If the frontend fallback keeps looser semantics, the same bug can come back whenever backend calls fail.

Always check:

- backend classification
- frontend fallback classification
- tab filtering and counts
- documentation wording

## Debug Checklist

When fund display looks wrong, use this order.

1. **Check API output first**
   - inspect `/api/funds?codes=...`
   - compare `valuation`, `marketPrice`, `premiumRate`, `isExchangeTraded`

2. **Decide which failure class this is**
   - quote missing
   - NAV missing
   - classification wrong
   - premium calculation wrong

3. **Test provider raw responses**
   - do not rely only on app-level merged output
   - verify whether the quote source actually returns data for the target symbols

4. **Check ambiguous funds explicitly**
   - `160213`
   - `539001`

5. **Only then change local logic**
   - if provider is dead, replacing the source may be the real fix
   - if provider is healthy, inspect merge and classification flow next

## Verification Checklist

After touching quote or classification logic:

### Backend

- verify `/api/funds?codes=...` for representative funds
- confirm exchange funds still show live `valuation`
- confirm NAV-style funds still show `premiumRate = 0`

### Frontend

- run `npm run build`
- verify exchange tab membership matches `isExchangeTraded`
- verify counts do not rely on stale heuristics

### Representative symbols

Use a mixed regression set.

Confirmed exchange-traded examples:

- `161226`
- `513100`
- `159659`

NAV-style / ambiguous examples:

- `160213`
- `539001`

## Operational Cautions

### Service restart has side effects

Restarting the backend is not a harmless local-only action.

It can trigger:

- monitoring loops
- state saves
- real notification emails

So before restart:

- use the smallest verification scope possible
- expect monitoring to run again
- avoid unnecessary restart churn

### Prefer narrow-scope validation first

Before rolling a provider or classification change across all funds:

- test a handful of representative symbols
- confirm raw provider output
- confirm merged API output
- then restart or broaden validation

## Rules Worth Preserving

### Confirmed classification

User-visible classification must reflect confirmed data availability, not heuristic eligibility.

### Fallback semantic parity

If backend is the source of truth, frontend fallback must preserve the same visible semantics.

### Provider-first diagnosis

When many exchange-like funds fail together but NAV still works, suspect the upstream quote source before suspecting field-mapping bugs.
