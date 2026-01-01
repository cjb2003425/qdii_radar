/**
 * Notification service - API wrapper for notification endpoints
 */

import { FundTrigger, AllTriggersResponse, CreateTriggerRequest, UpdateTriggerRequest } from '../types/notifications';
import { API_CONFIG } from '../config/api';

/**
 * Get all triggers for a specific fund
 */
export async function getFundTriggers(fundCode: string): Promise<FundTrigger[]> {
  const response = await fetch(`${API_CONFIG.notifications}/funds/${fundCode}/triggers`);
  if (!response.ok) {
    throw new Error(`Failed to get triggers for fund ${fundCode}`);
  }
  const data = await response.json();
  return data || [];
}

/**
 * Get all triggers grouped by fund
 */
export async function getAllTriggers(): Promise<AllTriggersResponse> {
  const response = await fetch(`${API_CONFIG.notifications}/triggers`);
  if (!response.ok) {
    throw new Error('Failed to get all triggers');
  }
  return await response.json();
}

/**
 * Create a new trigger for a fund
 */
export async function createTrigger(
  fundCode: string,
  trigger: CreateTriggerRequest
): Promise<FundTrigger> {
  const response = await fetch(`${API_CONFIG.notifications}/funds/${fundCode}/triggers`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(trigger)
  });

  if (!response.ok) {
    throw new Error(`Failed to create trigger for fund ${fundCode}`);
  }

  return await response.json();
}

/**
 * Update an existing trigger
 */
export async function updateTrigger(
  fundCode: string,
  triggerId: number,
  updates: UpdateTriggerRequest
): Promise<FundTrigger> {
  const response = await fetch(`${API_CONFIG.notifications}/funds/${fundCode}/triggers/${triggerId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updates)
  });

  if (!response.ok) {
    throw new Error(`Failed to update trigger ${triggerId}`);
  }

  const result = await response.json();
  return result.data || result;
}

/**
 * Delete a trigger
 */
export async function deleteTrigger(fundCode: string, triggerId: number): Promise<void> {
  const response = await fetch(`${API_CONFIG.notifications}/funds/${fundCode}/triggers/${triggerId}`, {
    method: 'DELETE'
  });

  if (!response.ok) {
    throw new Error(`Failed to delete trigger ${triggerId}`);
  }
}

/**
 * Enable/disable a trigger
 */
export async function toggleTrigger(
  fundCode: string,
  triggerId: number,
  enabled: boolean
): Promise<FundTrigger> {
  return updateTrigger(fundCode, triggerId, { enabled });
}
