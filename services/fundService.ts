import { FundData } from '../types';

const BACKEND_URL = 'http://127.0.0.1:8000/api/funds';

// Expanded configuration to match the richness of the reference image
const QDII_FUNDS_BASE = [
  { code: '513050', name: '中概互联ETF' },
  { code: '159941', name: '纳指ETF' },
  { code: '513100', name: '纳指ETF' },
  { code: '513500', name: '标普500ETF' },
  { code: '513180', name: '恒生科技指数ETF' },
  { code: '513330', name: '恒生互联网ETF' },
  { code: '159920', name: '恒生ETF' },
  { code: '161129', name: '原油LOF' },
  { code: '513030', name: '德国30ETF' },
  { code: '513520', name: '日经ETF' },
  { code: '513880', name: '日经225ETF' },
  { code: '159985', name: '豆粕ETF' },
  { code: '162411', name: '华宝油气LOF' },
  { code: '164906', name: '中国互联LOF' },
  { code: '513220', name: '游戏传媒ETF' },
  { code: '159740', name: '恒生科技ETF' },
  { code: '159792', name: '港股通互联网ETF' },
  { code: '513060', name: '恒生医疗ETF' },
  { code: '513130', name: '恒生科技ETF' },
  { code: '159954', name: 'H股ETF' },
  { code: '513090', name: '港股通50ETF' },
  { code: '513120', name: '恒生科技30ETF' },
  { code: '159866', name: '日经ETF' },
  { code: '513000', name: '225ETF' },
  { code: '513400', name: '道琼斯ETF' },
  { code: '513010', name: '恒生港股通ETF' },
  { code: '513110', name: '纳指科技ETF' },
  { code: '159981', name: '能源化工ETF' },
  { code: '008763', name: '天弘越南市场' },
  { code: '006105', name: '宏利印度机会' },
  { code: '020712', name: '三菱日联日经' },
];

// Fallback limits to prevent empty UI
const FALLBACK_LIMITS: Record<string, string> = {
  '513050': '不限', '159941': '暂停', '513100': '暂停', '513500': '不限',
  '513180': '不限', '513330': '不限', '159920': '不限', '161129': '限2万',
  '513030': '限3000', '513520': '限10万', '513880': '限10万', '159985': '限2000',
  '162411': '限500', '164906': '不限', '513220': '不限', '159740': '不限',
  '159792': '不限', '513060': '不限', '513130': '不限', '159954': '不限',
  '513090': '不限', '513120': '不限', '159866': '限10万', '513000': '限100',
  '513400': '暂停', '513010': '不限', '513110': '暂停', '159981': '限200',
  '008763': '暂停', '006105': '限100', '020712': '暂停'
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
    // Add a very short timeout for localhost check so it doesn't block UI for long if backend is missing
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 1000);
    
    const response = await fetch(BACKEND_URL, { signal: controller.signal });
    clearTimeout(timeoutId);

    if (response.ok) {
      console.log("Using Python Backend Data");
      return await response.json();
    }
  } catch (error) {
    // Backend fetch failed (server not running), proceed to client-side fallback
    console.log("Python Backend unavailable, switching to Client-side Mode.");
  }

  // 2. Fallback to Client Side
  return fetchClientSide();
};