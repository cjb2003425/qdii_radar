export interface Fund {
  id: string;
  code: string;
  name: string;
  price: number;
  priceChangePercent: number;
  netValue: number;
  netValueChangePercent: number;
  premiumRate: number;
  limitTag?: string; // e.g., "限1000", "暂停"
  limitStatus: 'warning' | 'danger' | 'neutral' | 'info'; // Determines badge color
  isMonitorEnabled: boolean;
  hasSettings?: boolean;
}

export interface StatItem {
  label: string;
  value: string | number;
  changeType?: 'up' | 'down' | 'neutral';
  colorClass?: string;
}
