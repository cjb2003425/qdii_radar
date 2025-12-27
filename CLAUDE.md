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
- Real-time quotes from Eastmoney push API for LOF funds
- Fund persistence via POST /api/fund endpoint
- Global caching for AKShare data (1-hour duration)

**Frontend Service Layer (`services/fundService.ts`)**:
- Backend-first data fetching with client-side fallback
- User fund management via localStorage
- Dynamic fund code passing to backend API
- Data merging between backend responses and user funds

**Fund Management (`components/FundManager.tsx`)**:
- User interface for adding/removing custom funds
- Real-time fund name resolution via backend API
- Automatic persistence to both localStorage and funds.json

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
```

## Critical Implementation Details

### Purchase Limit Parsing
The system handles Chinese fund purchase limits with complex parsing logic:
- Supports both `万元` (10,000 yuan) and `元` units
- Handles funds with "暂停申购" status but specific daily limits
- Examples: Fund 006105 shows "限10万" (100,000 yuan limit) despite being "暂停申购"

### NAV Data Display
**Column Mapping**: 
- `fund.marketPrice` → 净值 column (Net Asset Value display)
- `fund.valuation` → 估值 column (Valuation display)
- NAV data from AKShare must map to `marketPrice` field for correct display

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
  valuation: number;    // Previous close NAV (估值 column)
  valuationRate: number; // Daily change %
  premiumRate: number;  // Premium/discount rate
  marketPrice: number;  // Current NAV (净值 column) - primary display
  marketPriceRate: number; // NAV daily change %
  limitText: string;    // Formatted purchase limit text
  isWatchlisted: boolean;
  isUserAdded?: boolean; // User-added vs preset fund
}
```

### Backend Response Structure
- Returns array of funds with NAV in `marketPrice` field
- Purchase limits formatted as Chinese text: "限10万", "暂停", "不限"
- LOF funds include real-time market data, others use AKShare NAV data