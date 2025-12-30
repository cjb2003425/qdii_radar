/**
 * Notification system types
 */

export interface FundTrigger {
  id: number;
  fund_code: string;
  trigger_type: 'premium_high' | 'premium_low' | 'limit_change';
  threshold_value: number | null;
  enabled: boolean;
  updated_at: string;
}

export interface FundTriggersResponse {
  fund_code: string;
  triggers: FundTrigger[];
}

export interface AllTriggersResponse {
  [fund_code: string]: FundTrigger[];
}

export interface CreateTriggerRequest {
  trigger_type: 'premium_high' | 'premium_low' | 'limit_change';
  threshold_value?: number | null;  // Optional for limit_change
  enabled?: boolean;
}

export interface UpdateTriggerRequest {
  trigger_type?: 'premium_high' | 'premium_low' | 'limit_change';
  threshold_value?: number | null;
  enabled?: boolean;
}
