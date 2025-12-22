export interface FundData {
  id: string;
  name: string;
  code: string;
  valuation: number;
  valuationRate: number; // Percentage change
  premiumRate: number; // Percentage
  marketPrice: number;
  marketPriceRate: number; // Percentage change
  limitText?: string; // e.g., "限50万"
  isWatchlisted: boolean;
}

export enum TabCategory {
  STOCK_LOF = '股票型LOF',
  INDEX_LOF = '指数型LOF',
  OTHER = '超多其它',
  QDII_ETF = 'QDII-ETF',
  MY_FUNDS = '我的基金',
}

export enum BottomTab {
  ARBITRAGE = '套利基金',
  ROBOT = '高溢价机器人',
  RECORDER = '折价记录器',
  REAL_OFFER = '套利实盘',
}