import { FundData } from '../types/fund';
import { getUserFunds } from './userFundService';
import { PRESET_FUNDS, PROXY_CONFIG, REQUEST_CONFIG } from '../data/funds';
import { API_CONFIG } from '../config/api';

const QDII_FUNDS_BASE = PRESET_FUNDS;

const isExchangeTradedCandidate = (code: string, name: string = ''): boolean => {
  if (!code) return false;
  if (code.startsWith('159')) return true;
  if (code.startsWith('15') && !code.startsWith('159')) return true;
  if ([ '50', '51', '52', '53', '58', '59', '16', '12' ].some(prefix => code.startsWith(prefix))) return true;
  if (code.startsWith('5')) return true;
  const upperName = name.toUpperCase();
  if (upperName.includes('LOF')) return true;
  return upperName.includes('ETF') && !name.includes('联接');
};

const getSecidPrefix = (code: string): string => {
  if (code.startsWith('5') || code.startsWith('6') || ['50', '51', '52', '53', '58', '59'].some(prefix => code.startsWith(prefix))) {
    return '1';
  }
  if (code.startsWith('15') && !code.startsWith('159')) {
    return '1';
  }
  return '0';
};

const formatLimitText = (status: string, limit: number): string => {
  if (!status) return '—';
  if (status.includes('暂停')) return '暂停';
  if (status.includes('限制')) {
    if (limit > 0 && limit < 1000000000000) { 
      if (limit >= 100000000) return `限${Number((limit / 100000000).toFixed(2))}亿`;
      if (limit >= 10000) return `限${Number((limit / 10000).toFixed(0))}万`;
      return `限${limit}`;
    }
    return '暂停'; 
  }
  if (status.includes('开放')) return '不限';
  return status;
};

// --- CLIENT-SIDE LOGIC (Fallback) ---

async function fetchWithFallback(targetUrl: string): Promise<any> {
  for (const proxy of PROXY_CONFIG) {
    try {
      const proxyUrl = proxy.getUrl(targetUrl);
      const controller = new AbortController();
      const id = setTimeout(() => controller.abort(), REQUEST_CONFIG.PROXY_TIMEOUT); 
      const res = await fetch(proxyUrl, { cache: 'no-store', signal: controller.signal });
      clearTimeout(id);
      if (!res.ok) continue;
      const text = await res.text();
      try { return JSON.parse(text); } catch { continue; }
    } catch { continue; }
  }
  return null;
}

const fetchBatchLimitsClient = async (codes: string[]): Promise<Record<string, string>> => {
  if (codes.length === 0) return {};
  const codeStr = codes.join(',');
  const targetUrl = `https://fundmobapi.eastmoney.com/FundMApi/FundBaseTypeInformation.ashx?FCODES=${codeStr}&deviceid=Wap&plat=Wap&product=EFund&version=2.0.0&_=${Date.now()}`;
  try {
    const json = await fetchWithFallback(targetUrl);
    if (!json || !json.Datas || !Array.isArray(json.Datas)) return {};
    const batchMap: Record<string, string> = {};
    json.Datas.forEach((item: any) => {
      batchMap[item.FCODE] = formatLimitText(item.SGZT || '', parseFloat(item.MAXSG || '0'));
    });
    return batchMap;
  } catch { return {}; }
};

const fetchFundLimitsClient = async (): Promise<Record<string, string>> => {
  const chunks = [];
  for (let i = 0; i < QDII_FUNDS_BASE.length; i += REQUEST_CONFIG.CHUNK_SIZE) {
    chunks.push(QDII_FUNDS_BASE.slice(i, i + REQUEST_CONFIG.CHUNK_SIZE).map(f => f.code));
  }
  try {
    const results = await Promise.all(chunks.map(chunk => fetchBatchLimitsClient(chunk)));
    return results.reduce((acc, curr) => ({ ...acc, ...curr }), {});
  } catch { return {}; }
};

const fetchEastmoneyQuotesClient = async (): Promise<any[]> => {
  return new Promise<any[]>((resolve) => {
    const secIds = QDII_FUNDS_BASE.map(f => {
      const prefix = getSecidPrefix(f.code);
      return `${prefix}.${f.code}`;
    }).join(',');
    const cbName = `cb_em_q_${Math.floor(Math.random() * 100000)}`;
    const scriptUrl = `https://push2.eastmoney.com/api/qt/ulist.get?invt=2&fltt=2&fields=f12,f14,f2,f3,f18&secids=${secIds}&cb=${cbName}&_=${Date.now()}`;
    let timeoutId: any;

    // @ts-ignore
    window[cbName] = (data: any) => {
      clearTimeout(timeoutId);
      cleanup();
      resolve((data && data.data && data.data.diff) ? (Array.isArray(data.data.diff) ? data.data.diff : Object.values(data.data.diff)) : []);
    };
    function cleanup() {
      // @ts-ignore
      delete window[cbName];
      const script = document.getElementById(cbName);
      if (script && script.parentNode) script.parentNode.removeChild(script);
    }
    const script = document.createElement('script');
    script.id = cbName;
    script.src = scriptUrl;
    script.onerror = () => { clearTimeout(timeoutId); resolve([]); cleanup(); };
    timeoutId = setTimeout(() => { resolve([]); cleanup(); }, REQUEST_CONFIG.SCRIPT_TIMEOUT); 
    document.head.appendChild(script);
  });
};

const fetchClientSide = async (): Promise<FundData[]> => {
  // 1. Init Base Data
  const fundsMap = new Map<string, FundData>();
  QDII_FUNDS_BASE.forEach(base => {
    fundsMap.set(base.code, {
      id: base.code,
      name: base.name,
      code: base.code,
      valuation: 0,
      valuationRate: 0,
      premiumRate: 0,
      marketPrice: 0,
      marketPriceRate: 0,
      limitText: '—',
      isWatchlisted: false,
      isExchangeTraded: false
    });
  });

  try {
    const [quoteList, limitMap] = await Promise.all([
      fetchEastmoneyQuotesClient().catch(() => []), 
      fetchFundLimitsClient().catch(() => ({} as Record<string, string>))
    ]);

    quoteList.forEach((quote: any) => {
      const code = quote.f12;
      const item = fundsMap.get(code);
      if (item) {
        const price = quote.f2 === '-' ? 0 : parseFloat(quote.f2);
        const fallbackValue = quote.f18 === '-' ? 0 : parseFloat(quote.f18);
        const rate = quote.f3 === '-' ? 0 : parseFloat(quote.f3);

        const currentValue = price > 0 ? price : fallbackValue;
        if (currentValue > 0 && isExchangeTradedCandidate(code, item.name)) {
          item.isExchangeTraded = true;
          item.valuation = Number(currentValue.toFixed(4));
          item.valuationRate = Number(rate.toFixed(2));
        } else {
          const navValue = price > 0 ? price : fallbackValue;
          item.valuation = Number(navValue.toFixed(4));
          item.valuationRate = Number(rate.toFixed(2));
          item.marketPrice = Number(navValue.toFixed(4));
          item.marketPriceRate = Number(rate.toFixed(2));
        }
      }
    });

    Object.keys(limitMap).forEach(code => {
      const item = fundsMap.get(code);
      if (item) item.limitText = limitMap[code];
    });

  } catch (error) {
    console.error("Client side fetch failed", error);
  }

  const funds = Array.from(fundsMap.values());
  return funds.sort((a, b) => {
     if (a.marketPrice === 0 && b.marketPrice !== 0) return 1;
     if (a.marketPrice !== 0 && b.marketPrice === 0) return -1;
     return b.premiumRate - a.premiumRate;
  });
};

// --- MAIN EXPORT ---

export const fetchQDIIFunds = async (): Promise<FundData[]> => {
  console.log("📊 fetchQDIIFunds: Fetching from backend (source of truth)");

  // 1. Try Backend for data (backend is the source of truth)
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), REQUEST_CONFIG.PROXY_TIMEOUT);

    const backendUrl = API_CONFIG.funds;
    console.log("🌐 Requesting:", backendUrl);

    const response = await fetch(backendUrl, {
      signal: controller.signal,
      headers: {
        'Accept': 'application/json',
      }
    });
    clearTimeout(timeoutId);

    if (response.ok) {
      console.log("✅ Using Python Backend Data");
      const data = await response.json();
      console.log("📦 Backend returned:", data.length, "funds");

      // Sync localStorage with backend data
      syncLocalStorageWithBackend(data);

      return data;
    } else {
      console.warn("⚠️ Backend response not OK:", response.status);
    }
  } catch (error) {
    console.log("❌ Python Backend unavailable, using client-side fallback.", error);
  }

  // 2. Fallback to localStorage + Client Side
  console.log("🔄 Falling back to localStorage + client-side data");
  const userFunds = getUserFunds();

  if (userFunds.length === 0) {
    console.warn("⚠️ No funds found in localStorage. Initializing with preset funds.");
    initializeFunds();
    return [];
  }

  const clientData = await fetchClientSide();
  return mergeUserFundsWithBackendData(userFunds, clientData);
};

/**
 * Sync localStorage with backend data to keep them consistent
 */
function syncLocalStorageWithBackend(backendData: FundData[]): void {
  try {
    const currentLocalStorage = getUserFunds();
    const backendCodes = new Set(backendData.map(f => f.code));

    // Funds in backend but not in localStorage - add them
    const missingInLocalStorage = backendData.filter(f => !currentLocalStorage.some(lf => lf.code === f.code));

    // Funds in localStorage but not in backend - remove them (unless they're user-added temporarily)
    const extraInLocalStorage = currentLocalStorage.filter(lf => !backendCodes.has(lf.code));

    if (missingInLocalStorage.length > 0 || extraInLocalStorage.length > 0) {
      console.log("🔄 Syncing localStorage with backend:");

      if (missingInLocalStorage.length > 0) {
        console.log(`  Adding ${missingInLocalStorage.length} funds from backend to localStorage`);
        missingInLocalStorage.forEach(fund => {
          addUserFund(fund.code, fund.name);
        });
      }

      if (extraInLocalStorage.length > 0) {
        console.log(`  Removing ${extraInLocalStorage.length} funds from localStorage (not in backend)`);
        extraInLocalStorage.forEach(fund => {
          removeUserFund(fund.code);
        });
      }

      console.log("✅ LocalStorage synced with backend");
    }
  } catch (error) {
    console.error("❌ Failed to sync localStorage with backend:", error);
  }
}

function mergeUserFundsWithBackendData(userFunds: ReturnType<typeof getUserFunds>, backendData: FundData[]): FundData[] {
  const backendMap = new Map(backendData.map(fund => [fund.code, fund]));

  const merged = userFunds.map(userFund => {
    const backendFund = backendMap.get(userFund.code);

    if (backendFund) {
      // 如果后端有数据，使用后端的名称、净值和限额信息
      return {
        id: userFund.code,
        name: backendFund.name,
        code: userFund.code,
        valuation: backendFund.valuation,
        valuationRate: backendFund.valuationRate,
        premiumRate: backendFund.premiumRate,
        marketPrice: backendFund.marketPrice,
        marketPriceRate: backendFund.marketPriceRate,
        limitText: backendFund.limitText,
        isWatchlisted: false,
        isMonitorEnabled: backendFund.isMonitorEnabled || false,
        isUserAdded: true,
        ytdChange: backendFund.ytdChange || 0,
        ytdChangeAvailable: backendFund.ytdChangeAvailable || false,
        isExchangeTraded: backendFund.isExchangeTraded || false
      };
    } else {
      // 如果后端没有数据，使用基础数据
      console.warn(`⚠️ No backend data for fund ${userFund.code} ${userFund.name}`);
      return {
        id: userFund.code,
        name: userFund.name,
        code: userFund.code,
        valuation: 0,
        valuationRate: 0,
        premiumRate: 0,
        marketPrice: 0,
        marketPriceRate: 0,
        limitText: '—',
        isWatchlisted: false,
        isMonitorEnabled: false,
        isUserAdded: true,
        ytdChange: 0,
        ytdChangeAvailable: false,
        isExchangeTraded: false
      };
    }
  });

  // Log first few funds for debugging
  console.log("🔍 Sample merged funds:");
  merged.slice(0, 3).forEach(f => {
    console.log(`  ${f.code} ${f.name}: marketPrice=${f.marketPrice}, premiumRate=${f.premiumRate}`);
  });

  return merged;
}