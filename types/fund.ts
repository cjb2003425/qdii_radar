export interface UserFund {
  code: string;
  name: string;
  addedAt: string;
}

export interface FundData {
  id: string;
  name: string;
  code: string;
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
  oneYearChange?: number;  // 1-year percentage change
  oneYearChangeAvailable?: boolean;  // True if 1-year data exists
}