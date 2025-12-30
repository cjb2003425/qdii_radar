import fundsData from './funds.json';

export interface Fund {
  code: string;
  name: string;
}

export interface FundsData {
  funds: Fund[];
  config: {
    api: {
      backendUrl: string;
      requestTimeout: number;
      userAgent: string;
    };
    proxy: Array<{
      name: string;
      urlTemplate: string;
    }>;
    request: {
      proxyTimeout: number;
      chunkSize: number;
      scriptTimeout: number;
    };
    dataSourceUrls: {
      eastmoneyApi: string;
      fundDetail: string;
    };
  };
}

// Export funds array
export const PRESET_FUNDS = fundsData.funds;

// Export API config
export const API_CONFIG = {
  BACKEND_URL: fundsData.config.api.backendUrl,
  REQUEST_TIMEOUT: fundsData.config.api.requestTimeout,
  USER_AGENT: fundsData.config.api.userAgent,
};

// Export proxy config
export const PROXY_CONFIG = fundsData.config.proxy.map(proxy => ({
  name: proxy.name,
  getUrl: (url: string) => proxy.urlTemplate.replace('{url}', encodeURIComponent(url))
}));

// Export request config
export const REQUEST_CONFIG = {
  PROXY_TIMEOUT: fundsData.config.api.requestTimeout,
  CHUNK_SIZE: fundsData.config.request.chunkSize,
  SCRIPT_TIMEOUT: fundsData.config.request.scriptTimeout,
};

// Export data source URLs
export const DATA_SOURCE_URLS = fundsData.config.dataSourceUrls;