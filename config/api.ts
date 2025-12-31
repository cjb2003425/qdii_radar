/**
 * API Configuration
 *
 * Centralized API endpoint configuration.
 * Reads from data/funds.json to get backend URL.
 */

import { API_CONFIG as FUNDS_API_CONFIG } from '../data/funds';

/**
 * Detect if running in development mode
 */
function isDevelopment(): boolean {
  return import.meta.env.DEV || window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
}

/**
 * Get backend base URL from funds.json config
 */
function getBackendBaseUrl(): string {
  // Extract base URL from backendUrl (e.g., "http://127.0.0.1:8000/api/funds" -> "http://127.0.0.1:8000")
  const backendUrl = FUNDS_API_CONFIG.BACKEND_URL;
  const urlParts = backendUrl.split('/api/'); // Split at /api/
  const baseUrl = urlParts[0]; // Get "http://127.0.0.1:8000"

  if (isDevelopment()) {
    return baseUrl;
  } else {
    // In production, use relative path (nginx handles routing)
    return '';
  }
}

/**
 * API base URLs (computed from config)
 */
const baseUrl = getBackendBaseUrl();

export const API_CONFIG = {
  notifications: `${baseUrl}/api/notifications`,
  funds: `${baseUrl}/api/funds`
};

/**
 * Get API URLs (function for compatibility)
 */
export function getApiUrls() {
  return {
    notifications: API_CONFIG.notifications,
    funds: API_CONFIG.funds
  };
}

/**
 * Initialize API configuration (async for future use)
 * Currently this is a no-op since config is loaded synchronously
 */
export async function initApiConfig(): Promise<void> {
  // Config is loaded synchronously from data/funds.ts
  // This function exists for future async initialization needs
  console.log('API Config loaded from data/funds.json:', getApiUrls());
}
