import { FundData } from '../types/fund';
import { getUserFunds } from './userFundService';
import { PRESET_FUNDS, API_CONFIG, PROXY_CONFIG, REQUEST_CONFIG } from '../data/funds';

const QDII_FUNDS_BASE = PRESET_FUNDS;

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
      const prefix = (f.code.startsWith('5') || f.code.startsWith('6')) ? '1' : '0';
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
      id: base.code, name: base.name, code: base.code, valuation: 0, valuationRate: 0, premiumRate: 0, marketPrice: 0, marketPriceRate: 0, limitText: '—', isWatchlisted: false
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
        const preClose = quote.f18 === '-' ? 0 : parseFloat(quote.f18);
        const valuation = preClose > 0 ? preClose : price;
        const marketPriceRate = quote.f3 === '-' ? 0 : parseFloat(quote.f3);
        const premiumRate = (price > 0 && valuation > 0) ? ((price - valuation) / valuation) * 100 : 0;
        item.marketPrice = Number(price.toFixed(3));
        item.marketPriceRate = Number(marketPriceRate.toFixed(2));
        item.valuation = Number(valuation.toFixed(4));
        item.premiumRate = Number(premiumRate.toFixed(2));
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
  const userFunds = getUserFunds();

  console.log("📊 fetchQDIIFunds: userFunds from localStorage =", userFunds.length, "funds");

  // getUserFunds already includes all preset funds (from initializeFunds) + user-added funds
  if (userFunds.length === 0) {
    console.warn("⚠️ No funds found in localStorage. Please clear localStorage and refresh.");
    return [];
  }

  const fundCodes = userFunds.map(f => f.code);
  console.log("📋 Fetching codes:", fundCodes.join(','));

  // 1. Try Backend for data
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), API_CONFIG.REQUEST_TIMEOUT);

    const backendUrl = `${API_CONFIG.BACKEND_URL}?codes=${fundCodes.join(',')}`;
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
      let data = await response.json();
      console.log("📦 Raw backend data:", data.length, "funds");

      // Merge backend data with user funds
      data = mergeUserFundsWithBackendData(userFunds, data);
      console.log("✨ Merged data:", data.length, "funds");
      return data;
    } else {
      console.warn("⚠️ Backend response not OK:", response.status);
    }
  } catch (error) {
    console.log("❌ Python Backend unavailable, using client-side fallback.", error);
  }

  // 2. Fallback to Client Side
  console.log("🔄 Falling back to client-side data");
  const clientData = await fetchClientSide();
  return mergeUserFundsWithBackendData(userFunds, clientData);
};

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
        isUserAdded: true
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
        isUserAdded: true
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