# Knowledge Capture Design for QDII Radar

## Goal

Add two durable project documents under `docs/` so future maintenance is faster and less error-prone:

- `docs/ARCHITECTURE_NOTES.md`
- `docs/LESSONS.md`

These documents should capture both the stable design rules and the hard-earned debugging lessons from the exchange-traded fund classification and quote-source repair work.

## Why this is needed

Recent work exposed a pattern that is easy to forget and easy to regress:

- exchange-traded candidate detection is not the same thing as confirmed exchange-traded availability
- a live quote source can fail while NAV data remains healthy
- frontend fallback can silently reintroduce a backend-fixed bug if semantics drift
- names like `LOF` / `ETF` are not sufficient for user-visible classification

That knowledge currently exists in commit history, code, and human memory. It should become explicit project documentation.

## Scope

In scope:

1. Create `docs/ARCHITECTURE_NOTES.md`
2. Create `docs/LESSONS.md`
3. Align both documents with the current implementation and recent fixes
4. Keep both docs concise, practical, and easy to update

Out of scope:

- changing runtime behavior
- refactoring code further
- adding a third runbook document
- changing APIs or field contracts

## Approach options

### Option A — Single combined document
Put architecture notes and lessons learned into one file.

- Pros: everything in one place
- Cons: mixes stable design rules with incident-style lessons; will get noisy over time

### Option B — Two focused documents in `docs/` (recommended)
Use one stable design doc and one operational lessons doc.

- Pros: clear separation of concerns; easier maintenance; matches how people actually look things up
- Cons: small amount of cross-reference between files

### Option C — Full documentation split with extra runbook
Use architecture notes, lessons, and a separate runbook.

- Pros: most structured
- Cons: overkill for current project size and likely to rot faster

## Recommendation

Use **Option B**.

It gives the project two lookup paths:

- “Why is this designed this way?” → `ARCHITECTURE_NOTES.md`
- “Weird behavior happened; what bit us before?” → `LESSONS.md`

## Proposed design

### 1. `docs/ARCHITECTURE_NOTES.md`

Purpose: explain the current system rules and intended semantics.

Planned sections:

1. **Overview**
   - backend as source of truth
   - frontend fallback exists, but must remain semantically conservative

2. **Market Data Model**
   - NAV data path
   - exchange-traded real-time quote path
   - why quote-source reliability matters independently from NAV health

3. **Classification Model**
   - exchange-traded candidate vs confirmed exchange-traded
   - user-visible meaning of `isExchangeTraded`
   - why heuristic eligibility must stay internal

4. **Field Semantics**
   - `valuation`
   - `marketPrice`
   - `premiumRate`
   - difference in meaning for NAV-only vs confirmed exchange-traded funds

5. **Fallback Semantic Parity**
   - frontend fallback must not publish a looser meaning than backend
   - classification flags are especially sensitive to drift

6. **Known Ambiguous Cases**
   - `160213`
   - `539001`
   - principle: if stable real-time quote availability is not confirmed, present as NAV-style

### 2. `docs/LESSONS.md`

Purpose: capture pitfalls, debugging heuristics, and verification habits.

Planned sections:

1. **Recent Major Lessons**
   - quote source outage causing `valuation=0`
   - heuristic classification causing false exchange-tab entries

2. **Pitfalls to Avoid**
   - don’t assume `valuation=0` means merge logic is broken
   - don’t expose heuristic candidate logic to users
   - don’t fix backend only and forget fallback behavior

3. **Debug Checklist**
   - inspect `/api/funds?codes=...`
   - separate quote failure from NAV failure
   - test provider raw responses before changing business logic

4. **Verification Checklist**
   - build frontend
   - validate representative exchange funds
   - validate representative NAV-style funds
   - confirm ambiguous funds stay out of confirmed exchange classification

5. **Operational Cautions**
   - service restart can trigger monitoring and real email sends
   - verify on a narrow symbol set before broad rollout

## Writing style

Both docs should follow the same pattern:

- short sections
- high signal, low fluff
- explain rules before examples
- include concrete examples only where they sharpen judgment

## Success criteria

This work is successful if:

1. a future maintainer can understand why `isExchangeTraded` is a confirmed-status field
2. a debugger can quickly distinguish provider failure from local merge failure
3. frontend fallback behavior is documented as needing semantic parity with backend
4. ambiguous funds like `160213` and `539001` are documented without overstating tradability

## Risks

- Over-documenting transient provider details that may change
- Repeating code-level details that will drift quickly
- Mixing stable design principles with time-specific incident chatter

Mitigation:

- keep architecture doc principle-oriented
- keep lessons doc operational and example-driven
- avoid copying large code snippets unless necessary

## Expected output files

- `docs/ARCHITECTURE_NOTES.md`
- `docs/LESSONS.md`

## Review note

After these docs are written, they should be checked for:

- semantic consistency with current code
- no leftover `valuation > 0 means exchange-traded` wording
- clear distinction between candidate detection and confirmed classification
- no contradiction with current README / CLAUDE guidance
