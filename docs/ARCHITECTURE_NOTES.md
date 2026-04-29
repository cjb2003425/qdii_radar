# Architecture Notes

## Overview

QDII Radar uses a backend-first model.

- The Python backend is the source of truth for fund data.
- The frontend should prefer backend responses.
- Client-side fallback exists only as a degraded path and must stay semantically conservative.

The main design constraint is that quote availability and fund naming are not the same thing. A fund may look like an ETF/LOF candidate but still lack a stable real-time quote source.

## Market Data Model

The system combines two data channels:

1. **NAV channel**
   - Used for open-end style display and as the baseline for premium calculations.
   - Can remain healthy even when real-time exchange quotes fail.

2. **Real-time exchange quote channel**
   - Used only when a live trading quote is actually available.
   - Current repair work moved the primary exchange quote path away from the old Eastmoney aggregate endpoint after repeated disconnects.

Important consequence:

- `valuation = 0` on many exchange-like funds does **not** automatically mean local merge logic is wrong.
- First check whether the upstream quote provider is returning usable data.

## Classification Model

### Candidate vs confirmed

The codebase intentionally separates two ideas:

- **Exchange-traded candidate**: a fund looks eligible based on code prefix and/or name heuristics.
- **Confirmed exchange-traded**: the system actually fetched a usable live trading quote for that fund.

Only the confirmed status is user-visible.

### Public meaning of `isExchangeTraded`

`isExchangeTraded: true` means:

- a real-time trading quote was successfully fetched
- the fund is being displayed with exchange-traded behavior
- premium calculation can use live trading price versus NAV

`isExchangeTraded: false` means:

- display should fall back to NAV-style behavior
- the fund may still be an internal candidate for exchange quote fetching
- name/code heuristics alone are not enough to expose exchange-traded status to users

This rule prevents false positives such as funds that look like LOF/ETF candidates but do not have a stable quote source.

## Field Semantics

These fields are easy to confuse and must be interpreted carefully.

### `valuation`

- For confirmed exchange-traded funds: current trading price.
- For NAV-style funds: may fall back to NAV-style display value.
- Do **not** use `valuation > 0` alone as a type signal.

### `marketPrice`

- Used as the NAV channel in current UI/data flow.
- For confirmed exchange-traded funds, this is the NAV baseline used beside the live trading price.

### `premiumRate`

- Meaningful only when both of these exist:
  - confirmed exchange-traded quote
  - usable NAV baseline
- For NAV-style funds, premium should remain `0`.

## Quote Reliability Rules

A candidate fund is not promoted to confirmed exchange-traded unless quote retrieval succeeds.

Additional safety rule:

- If the trading price differs from NAV by more than 50%, treat the quote as suspicious and suppress premium display rather than trusting obviously bad output.

This is a data-quality guard, not a type-definition rule.

## Fallback Semantic Parity

The frontend fallback must preserve the same user-visible semantics as the backend.

That means:

- backend source of truth: confirmed classification
- frontend fallback: also confirmed classification
- fallback must not directly expose heuristic eligibility as `isExchangeTraded`

Why this matters:

- if backend behavior is fixed but fallback still uses loose heuristics, the old bug can reappear whenever backend requests fail
- this creates inconsistent tabs, counts, and premium behavior across failure modes

## Known Ambiguous Cases

### `160213`

This fund may look like an exchange-traded candidate from naming or legacy descriptions, but if no stable live quote source is available it must be displayed as NAV-style:

- `isExchangeTraded = false`
- `valuation` follows NAV-style behavior
- `premiumRate = 0`

### `539001`

Same principle as `160213`.

Do not present it as exchange-traded unless a stable live quote is actually confirmed.

## Maintainer Rules

When changing quote providers or classification logic:

1. keep candidate detection internal
2. expose only confirmed classification to the UI
3. verify representative exchange funds and representative NAV-style funds
4. check ambiguous cases like `160213` and `539001`
5. keep README / CLAUDE / fallback behavior aligned with runtime behavior
