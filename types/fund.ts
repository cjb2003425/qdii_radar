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
  monitoringEnabled?: boolean;  // New field for notification checkbox
}