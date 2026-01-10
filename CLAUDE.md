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
- Runs on port **8088** (not 8000 as README suggests)
- **Important**: README.md mentions port 8000, but actual port is 8088

**Notification System (`notifications/`)**:
- `models.py`: SQLite database models for triggers, config, history
- `monitor.py`: Background monitoring loop with configurable intervals
- `state_tracker.py`: Tracks fund data changes and triggers alerts
- `email_service.py`: SMTP/SES email delivery with templates
- Alert types: `premium_high` (溢价率超限), `premium_low` (溢价率下限), `limit_change` (限额变更)
- Trading hours awareness: only sends alerts during 9:30-15:00 Beijing time if configured
- Debounce mechanism: prevents duplicate alerts within configured interval

**Frontend Service Layer**:
- `services/fundService.ts`: Backend-first data fetching with client-side fallback, user fund management via localStorage, dynamic fund code passing to backend API, data merging between backend responses and user funds
- `services/fundApiService.ts`: Centralized API calls with retry logic for fund operations (lookup, add, delete)

**React Components**:
- `components/ControlPanel.tsx`: Main monitoring control panel with toggle switches, system health display, market overview
- `components/FundRow.tsx`: Individual fund display with monitoring toggle, settings button, separate desktop/mobile views
- `components/FundManager.tsx`: Floating UI for adding/removing custom funds with real-time fund name resolution
- `components/FundTriggerSettings.tsx`: Modal for configuring per-fund notification triggers
- `components/Footer.tsx`: Application footer with information

**UI Architecture**:
- `App.tsx`: Uses `max-w-6xl` container for wider layout, implements tab-based filtering (全部/纳斯达克/场内基金), separates mobile and desktop rendering to avoid HTML validation errors, handles monitoring toggle with database persistence
- Responsive design: Mobile-first with `md:` breakpoints for tablet/desktop
- Tailwind CSS for all styling (no separate CSS files)
- Frontend runs on port **3000** (Vite dev server), not 3002 as README suggests

### Database Schema (`data/notifications.db`)

**Tables**:
- `monitored_funds`: Stores individual fund monitoring toggle status (fund_code, enabled, updated_at)
- `fund_triggers`: Per-fund notification trigger configurations (fund_code, trigger_type, threshold_value, enabled)
- `notification_config`: System settings (monitoring_enabled, smtp_enabled, check_interval_seconds, alert_time_period)
- `notification_history`: Alert history (fund_code, fund_name, alert_type, old_value, new_value, sent_at, recipient_email)
- `email_recipients`: Email notification recipients
- `fund_states`: Historical fund data snapshots
- `historical_nav_cache`: 1-year NAV data cache with 24-hour expiration (fund_code, nav_1_year_ago, percentage_change, days_calculated, cached_at)

## Development Commands

### Starting the Application
```bash
# Start Python backend (port 8088)
python3 server.py

# Start React frontend (port 3000, uses Vite)
npm run dev

# Build for production
npm run build

# Kill backend if needed
lsof -ti:8088 | xargs kill -9

# Initialize database (creates tables if missing)
python3 -c "from notifications.models import init_db; init_db()"
```

**Port Notes**:
- Backend: **8088** (README incorrectly states 8000)
- Frontend dev: **3000** (README incorrectly states 3002)

**Known Issues**:
- `datetime.utcnow()` deprecation warning in cache functions (line 552 of server.py) - harmless, functionality works correctly

### Running Tests
```bash
# Activate virtual environment
source venv/bin/activate

# Install test dependencies (first time only)
pip install pytest pytest-asyncio httpx boto3 playwright pytest-playwright
playwright install chromium

# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_purchase_limit_002732.py -v
python -m pytest tests/test_delete_fund_161129.py -v

# Run frontend test (Playwright)
python tests/frontend_delete_fund_simple.py

# Run with detailed output
python -m pytest tests/test_delete_fund_161129.py -v -s
```

### Backend API Testing
```bash
# Test backend health
curl http://127.0.0.1:8088/health

# Get all funds with monitoring status
curl http://127.0.0.1:8088/api/funds

# Get specific funds
curl "http://127.0.0.1:8088/api/funds?codes=015299,006105"

# Get market indices (NASDAQ, S&P 500, average premium, exchange-traded count)
curl http://127.0.0.1:8088/api/market-indices | python3 -m json.tool

# Get/Update fund monitoring status
curl http://127.0.0.1:8088/api/notifications/monitored-funds/015299
curl -X PUT http://127.0.0.1:8088/api/notifications/monitored-funds/015299 \
  -H 'Content-Type: application/json' -d '{"enabled":true}'

# Get monitoring status
curl http://127.0.0.1:8088/api/notifications/monitoring/status

# Get fund triggers
curl http://127.0.0.1:8088/api/notifications/funds/015299/triggers
```

### Market Indices API

**Endpoint**: `GET /api/market-indices`

**Returns**: NASDAQ value, S&P 500 value, average premium rate, exchange-traded fund count, total fund count

**Dynamic Calculation** (server.py lines 1182-1201):
- Fetches fund data by calling `get_qdii_funds()`
- Calculates `total_funds` from actual fund count
- Calculates `exchange_traded_count` from funds with `valuation > 0`
- Calculates `avg_premium` as average of all exchange-traded funds' premium rates
- Cached for 1 minute to optimize performance

**Critical**: Do not hardcode these values. Always calculate dynamically from actual fund data.

### Database Operations
```bash
# Access SQLite database
sqlite3 data/notifications.db

# View monitored funds
SELECT * FROM monitored_funds ORDER BY updated_at DESC;

# View triggers
SELECT fund_code, trigger_type, threshold_value, enabled
FROM fund_triggers
ORDER BY fund_code, trigger_type;

# View notification history
SELECT * FROM notification_history
ORDER BY sent_at DESC
LIMIT 20;

# View configuration
SELECT * FROM notification_config;

# View historical NAV cache (1-year change data)
SELECT fund_code, percentage_change, days_calculated,
       datetime(cached_at, 'localtime') as cached_time
FROM historical_nav_cache
ORDER BY cached_at DESC;

# Clear historical NAV cache (to force refresh)
DELETE FROM historical_nav_cache;
DELETE FROM historical_nav_cache WHERE fund_code = '159659';
```

**Historical Cache Note**: The `historical_nav_cache` table stores 1-year NAV performance data with 24-hour expiration. Cache is automatically refreshed when expired. Manually clear cache to force immediate refresh.

### Debugging Fund Data
```bash
# Check if fund is in ETF spot data (AKShare)
python3 -c "import akshare as ak; df = ak.fund_etf_spot_em(); print(df[df['代码'] == '159659'])"

# Check if fund has open-end NAV data (AKShare)
python3 -c "import akshare as ak; print(ak.fund_open_fund_daily_em(symbol='f012870').tail())"

# Verify market prefix for Eastmoney API
# Shanghai: prefix 1 | Shenzhen: prefix 0
curl -s "https://push2.eastmoney.com/api/qt/ulist.np/get?secids=0.159659&fields=f12,f14,f2,f3"
```

## Critical Implementation Details

### Fund Monitoring Status Persistence

**Database Storage**: Individual fund monitoring toggle is stored in `monitored_funds` table, not just in React state.

**API Endpoints**:
- `GET /api/notifications/monitored-funds/{fund_code}` - Returns monitoring status
- `PUT /api/notifications/monitored-funds/{fund_code}` - Updates monitoring status (enabled=true/false)

**Frontend Integration**:
- `App.tsx` handleToggle: Calls backend API before updating local state
- `services/fundService.ts` mergeUserFundsWithBackendData: Must include `isMonitorEnabled` field when merging
- `App.tsx` mapFundDataToFund: Must use `data.isMonitorEnabled` from backend (not hardcoded)

**Common Pitfall**: Forgetting to include `isMonitorEnabled` in the merge function causes monitoring status to not persist across page refreshes.

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

### NAV Data Display
**Column Mapping** (FundRow.tsx):
- `fund.valuation` → 价格 column (Trading price for exchange-traded funds, or "—" for NAV funds)
- `fund.marketPrice` → 净值 column (Current NAV from Eastmoney/AKShare)
- Premium rate only calculated when both valuation > 0 AND marketPrice > 0

**Critical**: Ensure valuation shows in Column 2 (价格) and marketPrice in Column 3 (净值).

### Fund Type Filtering
**NASDAQ Tab**: Only shows funds with '纳斯达克' or '纳指' in name
- Filter logic: `fund.name.includes('纳斯达克') || fund.name.includes('纳指')`
- Dynamic badge count updates based on filtered results

**Exchange-Traded Tab**: Only shows funds with `valuation > 0`
- These funds have real-time trading prices
- LOF and ETF funds

### Fund Deletion Behavior

**Critical: localStorage Cleanup** - When deleting a fund, you MUST remove it from both backend AND localStorage:

```typescript
// In handleDelete function
if (result.success) {
  console.log(`✅ Fund ${fundToDelete.code} deleted from backend`);

  // CRITICAL: Also remove from localStorage to prevent reappearance after refresh
  const { removeUserFund } = await import('./services/userFundService');
  const removed = removeUserFund(fundToDelete.code);
  if (removed) {
    console.log(`✅ Fund ${fundToDelete.code} removed from localStorage`);
  }
}
```

**Why This Matters**: If you only delete from backend, the fund will reappear after page refresh because localStorage still contains it. The frontend merges funds from both sources.

**FundManager Deletion**: Temporary, UI-only, removes from localStorage
**FundList Deletion**: Permanent, calls backend DELETE API, removes from funds.json
- App.tsx handleDelete: Always calls `DELETE /api/fund/{code}` then `removeUserFund()`
- Includes confirmation dialog with fund details
- Database also removes fund from `monitored_funds` table

### URL Construction in API Services

**Critical Bug Pattern**: `API_CONFIG.funds` is `http://127.0.0.1:8088/api/funds`, so `${API_CONFIG.funds}/fund/${code}` becomes `http://127.0.0.1:8088/api/funds/fund/161129` (WRONG)

**Correct Pattern**:
```typescript
const baseUrl = API_CONFIG.funds.replace('/api/funds', '/api');
const url = `${baseUrl}/fund/${code}`;  // → http://127.0.0.1:8088/api/fund/161129
```

This pattern is used in `services/fundApiService.ts` for lookup and add operations.

### HTML Structure Validation

**Critical**: `<div>` (mobile cards) cannot be direct child of `<tbody>`

**Solution**: Separate mobile and desktop rendering in App.tsx:
```typescript
{/* Mobile Cards - OUTSIDE table */}
<div className="md:hidden flex flex-col gap-3 p-3 bg-slate-50">
  {filteredFunds.map((fund) => (
    <FundRow key={`mobile-${fund.id}`} fund={fund} />
  ))}
</div>

{/* Desktop Table */}
<div className="hidden md:block">
  <table>
    <tbody>
      {filteredFunds.map((fund) => (
        <FundRow key={`desktop-${fund.id}`} fund={fund} />
      ))}
    </tbody>
  </table>
</div>
```

### React Component Imports

**FundTriggerSettings**: Uses default export, not named export
- ✅ `import FundTriggerSettings from './FundTriggerSettings';`
- ❌ `import { FundTriggerSettings } from './FundTriggerSettings';`

### Column Sorting Implementation

**Default Sorting Behavior**:
- Initial page load: Sorts by NAV percentage change descending (`netValue` column, `netValueChangePercent` field)
- 全部基金 tab: NAV% descending
- 纳斯达克 tab: NAV% descending
- 场内基金 tab: Premium rate descending
- **1年期 (1-Year)**: Sorts by NAV-based 1-year percentage change

**Sorting Implementation** (App.tsx):
```typescript
const [sortColumn, setSortColumn] = useState<string | null>('netValue');
const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');

// All numeric columns sort by PERCENTAGE CHANGE, not absolute values:
switch (sortColumn) {
  case 'price': aValue = a.priceChangePercent; break;      // NOT a.price
  case 'netValue': aValue = a.netValueChangePercent; break;  // NOT a.netValue
  case 'premiumRate': aValue = a.premiumRate; break;
  case 'oneYearChange':  // 1-year NAV percentage change
    aValue = a.oneYearChangeAvailable ? a.oneYearChange || 0 : -999;
    bValue = b.oneYearChangeAvailable ? b.oneYearChange || 0 : -999;
    break;
  case 'name': aValue = a.name; break;  // Only text column sorts by value
}

// Click handler with tab-specific defaults
const handleTabChange = (tabId: string) => {
  setActiveTab(tabId);
  if (tabId === 'all' || tabId === 'nasdaq') {
    setSortColumn('netValue');  // NAV% descending
    setSortDirection('desc');
  } else if (tabId === 'exchange') {
    setSortColumn('premiumRate');  // Premium% descending
    setSortDirection('desc');
  }
};
```

**Critical**: When adding sortable columns, determine if it should sort by percentage change or absolute value. Users expect percentage-based sorting for price/NAV columns to quickly identify best/worst performers.

### 1-Year Percentage Change Column

**Purpose**: Display annual NAV performance for all funds using consistent NAV-based calculation.

**Calculation**:
- Formula: `(current_NAV - NAV_1yr_ago) / NAV_1yr_ago × 100`
- **Base (denominator)**: NAV from one year ago (not current NAV)
- All funds use NAV-based change (ETFs use NAV, not trading price)
- Data cached for 24 hours in `historical_nav_cache` table
- Fetched via `fetch_historical_nav_eastmoney()` using AKShare's `fund_open_fund_info_em()`

**Data Flow**:
1. Backend calls `get_one_year_change(code, is_exchange_traded)` for each fund
2. Checks `historical_nav_cache` table for valid cache (< 24 hours old)
3. On cache miss: fetches from AKShare, stores in database
4. Frontend displays with color coding (red=positive, green=negative)
5. Funds without data show "—" and sort to bottom (-999 sentinel value)

**Implementation Notes**:
- AKShare's `fund_open_fund_info_em()` returns data with **oldest first, newest last**
- Use `df.iloc[-1]` for current NAV (newest row)
- Find closest date to target (1 year ago) using time difference calculation
- Sorting places funds without data at bottom when descending

## Data Structures

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
  isMonitorEnabled?: boolean;  // Monitoring status from database (CRITICAL: persists to DB)
  isUserAdded?: boolean; // User-added vs preset fund
  oneYearChange?: number;  // 1-year NAV percentage change
  oneYearChangeAvailable?: boolean;  // True if historical data exists
}
```

**Critical Field**: `isMonitorEnabled` - Must be included in all data merging operations or monitoring status won't persist.

**Critical Distinctions**:
- `valuation > 0` → Fund is exchange-traded (LOF or ETF) with real-time trading price
- `valuation === 0` → Fund is NAV-based only (no trading price, like ETF联接 funds)
- `marketPrice > 0` → Fund has NAV data (all funds should have this)
- `oneYearChange` → NAV-based 1-year performance, calculated as (current_NAV - NAV_1yr_ago) / NAV_1yr_ago × 100

### Backend Response Structure
- Returns array of funds with NAV in `marketPrice` field
- Exchange-traded funds also have `valuation` (trading price) from Eastmoney API
- Purchase limits formatted as Chinese text: "限10万", "暂停", "不限"
- Price validation: unreliable prices (>50% diff from NAV) are reset to 0
- **Always includes** `isMonitorEnabled` field for each fund