# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

QDII Fund Radar is a real-time Chinese fund tracking application that monitors Net Asset Values (NAV) and purchase limits for NASDAQ-focused QDII funds. The system uses a dual-backend architecture with Python (FastAPI) for data fetching and React + TypeScript for the frontend.

## Architecture

### Data Flow Architecture

**Backend-Priority System**: The frontend always attempts to use the Python backend first, falling back to client-side fetching only if the backend is unavailable. This dual approach ensures reliability while optimizing for data accuracy.

**AKShare Integration**: The Python backend uses the AKShare library to fetch comprehensive NAV data for funds that don't have real-time market data. This data is cached for 1 hour to optimize performance.

**Dynamic Fund Loading**: The system supports both preset funds (stored in `data/funds.json`) and user-added funds (stored in localStorage). The backend dynamically processes requested fund codes via query parameters.

### Key Components

**Python Backend (`server.py`)**:
- Primary data source with AKShare integration for NAV data
- HTML scraping from fundf10.eastmoney.com for purchase limits
- Real-time quotes from Eastmoney push API for LOF/ETF funds
- Fund persistence via POST /api/fund endpoint
- Global caching for AKShare data (1-hour duration)
- Background monitoring system with asyncio and SQLite

**Notification System (`notifications/`)**:
- `models.py`: SQLite database models for triggers, config, history
- `monitor.py`: Background monitoring loop with configurable intervals
- `state_tracker.py`: Tracks fund data changes and triggers alerts
- `email_service.py`: SMTP/SES email delivery with templates
- Alert types: `premium_high` (溢价率超限), `limit_change` (限额变更)
- Trading hours awareness: only sends alerts during 9:30-15:00 Beijing time if configured
- Debounce mechanism: prevents duplicate alerts within configured interval

**Frontend Service Layer (`services/fundService.ts`)**:
- Backend-first data fetching with client-side fallback
- User fund management via localStorage
- Dynamic fund code passing to backend API
- Data merging between backend responses and user funds

**Fund Management (`components/FundManager.tsx`)**:
- User interface for adding/removing custom funds
- Real-time fund name resolution via backend API
- Automatic persistence to both localStorage and funds.json

**UI Layout Patterns**:
- `App.tsx`: Uses `max-w-3xl` container to create dashboard-like centered layout
- `FundList.tsx`: Implements tab-based filtering (全部/纳斯达克/场内基金)
- `MonitoringControl.tsx`: Status cards using custom grid layouts with `grid-cols-[auto_auto_auto_minmax(140px,1.5fr)_minmax(140px,1.5fr)]`
- Responsive design: Mobile-first with `sm:` breakpoints for tablet/desktop
- Tailwind CSS for all styling (no separate CSS files)

### Data Architecture

**Fund Storage**: 
- `data/funds.json`: Master fund list with 21 preset QDII funds
- `localStorage`: User-added custom funds
- Backend dynamically processes both sources

**Data Sources**:
1. AKShare library: Comprehensive NAV database (cached)
2. Eastmoney HTML scraping: Purchase limits and status
3. Eastmoney push API: Real-time LOF fund quotes

## Development Commands

### Starting the Application
```bash
# Start Python backend (port 8000)
python3 server.py

# Start React frontend (port 3001, uses Vite)
npm run dev

# Build for production
npm run build
```

### Backend Management
```bash
# Kill existing backend on port 8000
lsof -ti:8000 | xargs kill -9

# Test backend health
curl http://127.0.0.1:8000/health

# Test specific fund data
curl "http://127.0.0.1:8000/api/funds?codes=015299,006105"

# Verify exchange-traded funds
curl -s http://127.0.0.1:8000/api/funds | python3 -c \
  "import sys, json; funds = json.load(sys.stdin); lof = [f for f in funds if f['valuation'] > 0]; \
  print(f\"Exchange-traded: {len(lof)} funds\"); \
  [print(f\"{f['id']} | {f['valuation']:.4f} | {f['name']}\") for f in lof]"
```

### Debugging Fund Data Issues
```bash
# Check if fund is in ETF spot data (AKShare)
python3 -c "import akshare as ak; df = ak.fund_etf_spot_em(); print(df[df['代码'] == '159659'])"

# Check if fund has open-end NAV data (AKShare)
python3 -c "import akshare as ak; print(ak.fund_open_fund_daily_em(symbol='f012870').tail())"

# Verify market prefix used by Eastmoney API
# Shanghai: prefix 1 | Shenzhen: prefix 0
curl -s "https://push2.eastmoney.com/api/qt/ulist.np/get?secids=0.159659&fields=f12,f14,f2,f3"
```

## Critical Implementation Details

### Exchange-Traded Fund Classification

**Key Principle**: Funds are classified as exchange-traded (LOF/ETF) based on **actual trading data**, not just naming.

**Detection Logic**:
- `fund.valuation > 0` indicates real-time trading price exists → exchange-traded
- `fund.valuation === 0` indicates no trading price → NAV-based fund only

**Market Prefix Rules** (server.py):
- Shanghai (prefix 1): 5xxxx, 6xxxx, 50xxxx, 51xxxx, 52xxxx, 53xxxx, 58xxxx, 59xxxx, 15xxxx (but NOT 159xxx)
- Shenzhen (prefix 0): 16xxxx, 159xxx, 12xxxx
- Critical: 159xxx funds (Shenzhen ETFs) must use prefix "0", not "1"

**Price Validation**:
- If trading price differs >50% from NAV, price is considered unreliable and reset to 0
- This prevents displaying bad data for non-exchange-traded funds

**Common Pitfalls**:
- ETF联接 funds are NOT exchange-traded (they're funds that invest in ETFs)
- Fund 160213 is open-end, not exchange-traded (valuation = 0)
- Fund 012870 is ETF联接, not exchange-traded despite "LOF" in name
- 159xxx ETF funds require Shenzhen market prefix (0), not Shanghai (1)
- Price/NAV columns were swapped in earlier versions - verify Column 2 shows valuation, Column 3 shows marketPrice

### NAV Data Display
**Column Mapping** (FundRow.tsx):
- `fund.valuation` → 价格 column (Trading price for exchange-traded funds, or "—" for NAV funds)
- `fund.marketPrice` → 净值 column (Current NAV from Eastmoney/AKShare)
- Premium rate only calculated when both valuation > 0 AND marketPrice > 0

**Critical**: The columns were swapped in earlier versions. Ensure valuation shows in Column 2 (价格) and marketPrice in Column 3 (净值).

### Purchase Limit Parsing
The system handles Chinese fund purchase limits with complex parsing logic:
- Supports both `万元` (10,000 yuan) and `元` units
- Handles funds with "暂停申购" status but specific daily limits
- Examples: Fund 006105 shows "限10万" (100,000 yuan limit) despite being "暂停申购"

### Dynamic Fund Processing
When users add new funds, the system:
1. Frontend calls `/api/fund/{code}` to get real fund name from AKShare
2. Frontend calls `POST /api/fund?code={code}&name={name}` to persist to funds.json
3. Backend reloads fund list using `reload_funds()` from funds_loader.py
4. Frontend triggers immediate data refresh via `onFundAdded` callback

### Caching Strategy
- **AKShare Cache**: Global cache with 1-hour expiration, shared across all requests
- **Cache Invalidation**: Automatically refreshes when expired or on server restart
- **Performance**: Critical for handling multiple fund requests without overwhelming AKShare API

## Data Structure

### FundData Type
```typescript
{
  id: string;           // Fund code
  name: string;         // Fund name
  code: string;         // Fund code
  valuation: number;    // Trading price (场内价格) for exchange-traded funds, 0 for NAV funds
  valuationRate: number; // Trading price daily change %
  premiumRate: number;  // Premium/discount rate (only if valuation > 0)
  marketPrice: number;  // Current NAV from Eastmoney/AKShare (最新净值)
  marketPriceRate: number; // NAV daily change %
  limitText: string;    // Formatted purchase limit text
  isWatchlisted: boolean;
  monitoringEnabled?: boolean; // Per-fund monitoring toggle
  isUserAdded?: boolean; // User-added vs preset fund
}
```

**Critical Distinctions**:
- `valuation > 0` → Fund is exchange-traded (LOF or ETF) with real-time trading price
- `valuation === 0` → Fund is NAV-based only (no trading price, like ETF联接 funds)
- `marketPrice > 0` → Fund has NAV data (all funds should have this)

### Backend Response Structure
- Returns array of funds with NAV in `marketPrice` field
- Exchange-traded funds also have `valuation` (trading price) from Eastmoney API
- Purchase limits formatted as Chinese text: "限10万", "暂停", "不限"
- Price validation: unreliable prices (>50% diff from NAV) are reset to 0