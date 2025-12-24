import { FundData } from '../types';

const BACKEND_URL = 'http://127.0.0.1:8000/api/funds';

// Expanded configuration to match the richness of the reference image
const QDII_FUNDS_BASE = [
  // 一、纳斯达克100相关（11只）
  { code: '015299', name: '华夏纳指100ETF联接A' },
  { code: '019547', name: '招商纳指100ETF联接A' },
  { code: '018043', name: '天弘纳指100指数A' },
  { code: '160213', name: '国泰纳指100指数' },
  { code: '270042', name: '广发纳指100ETF联接A' },
  { code: '000834', name: '大成纳指100ETF联接A' },
  { code: '040046', name: '华安纳指100ETF联接A' },
  { code: '019441', name: '万家纳指100指数A' },
  { code: '019172', name: '摩根纳指100指数A' },
  { code: '002732', name: '易方达纳指100ETF联接美元A' },
  { code: '161130', name: '易方达纳指100ETF联接A' },
  // 二、股票精选/区域市场QDII（5只）
  { code: '017436', name: '华宝纳指精选股票A' },
  { code: '007280', name: '摩根日本精选股票A' },
  { code: '008763', name: '天弘越南市场股票A' },
  { code: '006105', name: '宏利印度机会股票A' },
  { code: '006282', name: '摩根欧洲动力策略股票A' },
  // 三、日本/亚太ETF联接（4只）
  { code: '020712', name: '华安日经225ETF联接A' },
  { code: '021189', name: '南方亚太精选ETF联接A' },
  { code: '021190', name: '南方亚太精选ETF联接C' },
];

// Fallback limits to prevent empty UI
const FALLBACK_LIMITS: Record<string, string> = {
  // 纳斯达克100相关
  '015299': '暂停', '019547': '限100', '018043': '暂停', '160213': '暂停',
  '270042': '暂停', '000834': '暂停', '040046': '暂停', '019441': '暂停',
  '019172': '暂停', '002732': '暂停', '161130': '暂停',
  // 股票精选/区域市场
  '017436': '暂停', '007280': '暂停', '008763': '暂停', '006105': '暂停', '006282': '暂停',
  // 日本/亚太ETF联接
  '020712': '暂停', '021189': '暂停', '021190': '暂停',
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
  const proxies = [
    { getUrl: (url: string) => `https://api.allorigins.win/raw?url=${encodeURIComponent(url)}`, name: 'AllOrigins' },
    { getUrl: (url: string) => `https://api.codetabs.com/v1/proxy?quest=${encodeURIComponent(url)}`, name: 'CodeTabs' }
  ];

  for (const proxy of proxies) {
    try {
      const proxyUrl = proxy.getUrl(targetUrl);
      const controller = new AbortController();
      const id = setTimeout(() => controller.abort(), 3000); 
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
  const chunkSize = 20;
  const chunks = [];
  for (let i = 0; i < QDII_FUNDS_BASE.length; i += chunkSize) {
    chunks.push(QDII_FUNDS_BASE.slice(i, i + chunkSize).map(f => f.code));
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
    timeoutId = setTimeout(() => { resolve([]); cleanup(); }, 4000); 
    document.head.appendChild(script);
  });
};

const fetchClientSide = async (): Promise<FundData[]> => {
  // 1. Init Base Data
  const fundsMap = new Map<string, FundData>();
  QDII_FUNDS_BASE.forEach(base => {
    fundsMap.set(base.code, {
      id: base.code, name: base.name, code: base.code, valuation: 0, valuationRate: 0, premiumRate: 0, marketPrice: 0, marketPriceRate: 0, limitText: FALLBACK_LIMITS[base.code] || '—', isWatchlisted: false
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
  // 1. Try Backend
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 5000);
    
    const response = await fetch(BACKEND_URL, { 
      signal: controller.signal,
      headers: {
        'Accept': 'application/json',
      }
    });
    clearTimeout(timeoutId);

    if (response.ok) {
      console.log("Using Python Backend Data");
      const data = await response.json();
      console.log("Backend response:", data);
      return data;
    }
  } catch (error) {
    console.log("Python Backend unavailable, switching to Client-side Mode.", error);
  }

  // 2. Fallback to Client Side
  return fetchClientSide();
};