/**
 * API Configuration
 *
 * Determines whether to use relative or absolute URLs based on environment:
 * - Development: Uses absolute URL (http://127.0.0.1:8088) only for true local development
 * - Production: Uses relative paths (/api/*) to leverage nginx reverse proxy
 */

import { API_CONFIG as FUNDS_API_CONFIG } from '../data/funds';

/**
 * Checks if the application is running in true local development mode.
 * Only localhost / 127.0.0.1 (or Vite dev server) should bypass nginx and call the backend directly.
 * Access via LAN IP or production host must still use relative /api paths.
 */
function isDevelopment(): boolean {
  const hostname = window.location.hostname;

  // Vite dev server
  if (import.meta.env.DEV) {
    return true;
  }

  // True local development only
  return hostname === 'localhost' || hostname === '127.0.0.1';
}

/**
 * Computes the appropriate base URL for API requests.
 *
 * In development: Returns the backend's absolute URL (e.g., "http://127.0.0.1:8088")
 * In production: Returns empty string to use relative paths (e.g., "/api/funds")
 */
function getBaseUrl(): string {
  // Production: always use relative paths (nginx handles proxying)
  if (!isDevelopment()) {
    return '';
  }

  // Development: use backend URL from config directly
  const backendUrl = FUNDS_API_CONFIG.BACKEND_URL;

  // If config already has relative path, respect it
  if (!backendUrl.startsWith('http://') && !backendUrl.startsWith('https://')) {
    return '';
  }

  // Extract base URL (e.g., "http://127.0.0.1:8088/api/funds" -> "http://127.0.0.1:8088")
  const urlParts = backendUrl.split('/api/');
  let baseUrl = urlParts[0];

  return baseUrl;
}

/**
 * API endpoint configuration
 *
 * Examples:
 * - Development: "http://127.0.0.1:8088/api/funds"
 * - Production: "/api/funds"
 */
const baseUrl = getBaseUrl();

export const API_CONFIG = {
  notifications: `${baseUrl}/api/notifications`,
  funds: `${baseUrl}/api/funds`
} as const;
