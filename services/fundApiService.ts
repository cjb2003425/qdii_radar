/**
 * Fund API Service
 *
 * Centralized API calls for fund management operations.
 * Uses API_CONFIG for consistent backend URL configuration.
 * Includes retry logic with exponential backoff for resilience.
 */

import { API_CONFIG } from '../config/api';

export interface FundLookupResponse {
  found: boolean;
  name: string;
}

export interface FundAddResponse {
  success: boolean;
  message?: string;
}

export interface FundDeleteResponse {
  success: boolean;
  message?: string;
}

/**
 * Retry configuration with exponential backoff
 */
interface RetryConfig {
  maxRetries: number;
  baseDelay: number;
  maxDelay: number;
}

const DEFAULT_RETRY_CONFIG: RetryConfig = {
  maxRetries: 3,
  baseDelay: 1000, // 1 second
  maxDelay: 10000, // 10 seconds
};

/**
 * Sleep utility for delaying retries
 */
const sleep = (ms: number): Promise<void> => {
  return new Promise(resolve => setTimeout(resolve, ms));
};

/**
 * Calculate exponential backoff delay with jitter
 */
const calculateDelay = (attempt: number, baseDelay: number, maxDelay: number): number => {
  const exponentialDelay = baseDelay * Math.pow(2, attempt);
  const jitter = Math.random() * 0.3 * exponentialDelay; // Add 0-30% jitter
  return Math.min(exponentialDelay + jitter, maxDelay);
};

/**
 * Fetch with retry logic and exponential backoff
 */
async function fetchWithRetry(
  url: string,
  options: RequestInit = {},
  retryConfig: RetryConfig = DEFAULT_RETRY_CONFIG
): Promise<Response> {
  let lastError: Error | null = null;

  for (let attempt = 0; attempt <= retryConfig.maxRetries; attempt++) {
    try {
      const response = await fetch(url, options);

      // Retry on server errors (5xx) or network errors
      if (!response.ok && response.status >= 500 && attempt < retryConfig.maxRetries) {
        const delay = calculateDelay(attempt, retryConfig.baseDelay, retryConfig.maxDelay);
        console.warn(`Server error ${response.status}, retrying in ${Math.round(delay)}ms (attempt ${attempt + 1}/${retryConfig.maxRetries})`);
        await sleep(delay);
        continue;
      }

      return response;
    } catch (error) {
      lastError = error instanceof Error ? error : new Error(String(error));

      // Don't retry on client errors (4xx) or if this was the last attempt
      if (attempt < retryConfig.maxRetries) {
        const delay = calculateDelay(attempt, retryConfig.baseDelay, retryConfig.maxDelay);
        console.warn(`Network error, retrying in ${Math.round(delay)}ms (attempt ${attempt + 1}/${retryConfig.maxRetries}):`, lastError.message);
        await sleep(delay);
      }
    }
  }

  throw lastError || new Error('Max retries exceeded');
}

/**
 * Look up a fund by code to get its real name
 *
 * @param code - 6-digit fund code
 * @returns Fund lookup response with found status and name
 */
export async function lookupFund(code: string): Promise<FundLookupResponse> {
  // Replace '/api/funds' with '/api' to get the base API URL
  const baseUrl = API_CONFIG.funds.replace('/api/funds', '/api');
  const url = `${baseUrl}/fund/${code}`;

  try {
    const response = await fetchWithRetry(url, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      console.warn(`Fund lookup failed: ${response.status} ${response.statusText}`);
      return { found: false, name: '' };
    }

    const data: FundLookupResponse = await response.json();
    return data;
  } catch (error) {
    console.error('Fund lookup error:', error);
    return { found: false, name: '' };
  }
}

/**
 * Add a fund to the backend (funds.json)
 *
 * @param code - 6-digit fund code
 * @param name - Fund name
 * @returns Success status and optional message
 */
export async function addFundToBackend(code: string, name: string): Promise<FundAddResponse> {
  // Replace '/api/funds' with '/api' to get the base API URL
  const baseUrl = API_CONFIG.funds.replace('/api/funds', '/api');
  const url = `${baseUrl}/fund?code=${encodeURIComponent(code)}&name=${encodeURIComponent(name)}`;

  try {
    const response = await fetchWithRetry(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (response.ok) {
      console.log(`✅ Fund ${code} added to backend`);
      return { success: true, message: 'Fund added successfully' };
    } else {
      console.warn(`⚠️ Failed to add fund ${code} to backend: ${response.status}`);
      return { success: false, message: `Backend returned ${response.status}` };
    }
  } catch (error) {
    console.error(`❌ Error adding fund ${code} to backend:`, error);
    return { success: false, message: error instanceof Error ? error.message : 'Unknown error' };
  }
}

/**
 * Delete a fund from the backend (funds.json and monitoring database)
 *
 * @param code - 6-digit fund code
 * @returns Success status and optional message
 */
export async function deleteFundFromBackend(code: string): Promise<FundDeleteResponse> {
  // Replace '/api/funds' with '/api' to get the base API URL
  const baseUrl = API_CONFIG.funds.replace('/api/funds', '/api');
  const url = `${baseUrl}/fund/${code}`;

  try {
    const response = await fetchWithRetry(url, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      console.warn(`⚠️ Backend DELETE failed for ${code}: ${response.status}`);
      return { success: false, message: `Backend returned ${response.status}` };
    }

    const result: FundDeleteResponse = await response.json();

    if (result.success) {
      console.log(`✅ Fund ${code} deleted from backend`);
    } else {
      console.warn(`⚠️ Backend returned success=false for ${code}:`, result.message);
    }

    return result;
  } catch (error) {
    console.error(`❌ Error deleting fund ${code} from backend:`, error);
    return { success: false, message: error instanceof Error ? error.message : 'Unknown error' };
  }
}

/**
 * Batch delete funds from the backend
 *
 * @param codes - Array of 6-digit fund codes
 * @returns Object mapping codes to their deletion results
 */
export async function batchDeleteFundsFromBackend(
  codes: string[]
): Promise<Record<string, FundDeleteResponse>> {
  const results: Record<string, FundDeleteResponse> = {};

  // Execute all deletions in parallel
  const deletePromises = codes.map(async (code) => {
    const result = await deleteFundFromBackend(code);
    return { code, result };
  });

  try {
    const settledResults = await Promise.all(deletePromises);

    for (const { code, result } of settledResults) {
      results[code] = result;
    }
  } catch (error) {
    console.error('❌ Batch delete error:', error);
  }

  return results;
}
