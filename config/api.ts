/**
 * API Configuration
 *
 * Determines whether to use relative or absolute URLs based on environment:
 * - Development: Uses absolute URL (http://127.0.0.1:8088) to connect directly to backend
 * - Production: Uses relative paths (/api/*) to leverage nginx reverse proxy
 */

import { API_CONFIG as FUNDS_API_CONFIG } from '../data/funds';

/**
 * Checks if the application is running in development mode.
 * Development mode is detected when accessed via localhost, local network IPs, or running in Vite dev server.
 */
function isDevelopment(): boolean {
  const hostname = window.location.hostname;

  // Vite dev server
  if (import.meta.env.DEV) {
    return true;
  }

  // Localhost access
  if (hostname === 'localhost' || hostname === '127.0.0.1') {
    return true;
  }

  // Local network access (10.x.x.x, 192.168.x.x, 172.16-31.x.x)
  if (
    /^10\./.test(hostname) ||
    /^192\.168\./.test(hostname) ||
    /^172\.(1[6-9]|2[0-9]|3[01])\./.test(hostname)
  ) {
    return true;
  }

  return false;
}

/**
 * Computes the appropriate base URL for API requests.
 *
 * In development: Returns the backend's absolute URL (e.g., "http://127.0.0.1:8088" or "http://10.0.0.9:8088")
 * In production: Returns empty string to use relative paths (e.g., "/api/funds")
 */
function getBaseUrl(): string {
  // Production: always use relative paths (nginx handles proxying)
  if (!isDevelopment()) {
    return '';
  }

  // Development: use backend URL from config but replace host if accessing from network
  const backendUrl = FUNDS_API_CONFIG.BACKEND_URL;

  // If config already has relative path, respect it
  if (!backendUrl.startsWith('http://') && !backendUrl.startsWith('https://')) {
    return '';
  }

  // Extract base URL (e.g., "http://127.0.0.1:8088/api/funds" -> "http://127.0.0.1:8088")
  const urlParts = backendUrl.split('/api/');
  let baseUrl = urlParts[0];

  // If accessing from local network, replace 127.0.0.1 with actual hostname
  const currentHostname = window.location.hostname;
  if (currentHostname !== 'localhost' && currentHostname !== '127.0.0.1') {
    // Replace the host in backend URL with current hostname
    const url = new URL(baseUrl);
    baseUrl = `${url.protocol}//${currentHostname}:${url.port || (url.protocol === 'https:' ? '443' : '80')}`;
  }

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
