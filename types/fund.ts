export interface UserFund {
  code: string;
  name: string;
  addedAt: string;
}

export interface FundData {
  id: string;
  name: string;
  code: string;
  isPreset?: boolean;
  valuation: number;
  valuationRate: number;
  premiumRate: number;
  marketPrice: number;
  marketPriceRate: number;
  limitText: string;
  isWatchlisted: boolean;
  isUserAdded?: boolean;
  isMonitorEnabled?: boolean;  // Monitoring status from backend database
  monitoringEnabled?: boolean;  // Deprecated: use isMonitorEnabled instead
  ytdChange?: number;  // YTD percentage change
  ytdChangeAvailable?: boolean;  // True if YTD data exists
  isExchangeTraded?: boolean;
}