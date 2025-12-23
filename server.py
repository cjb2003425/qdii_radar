from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx
import asyncio
from datetime import datetime
from typing import List, Dict, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="QDII Fund Radar API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

QDII_FUNDS = [
    {"code": "513050", "name": "中概互联ETF"},
    {"code": "159941", "name": "纳指ETF"},
    {"code": "513100", "name": "纳指ETF"},
    {"code": "513500", "name": "标普500ETF"},
    {"code": "513180", "name": "恒生科技指数ETF"},
    {"code": "513330", "name": "恒生互联网ETF"},
    {"code": "159920", "name": "恒生ETF"},
    {"code": "161129", "name": "原油LOF"},
    {"code": "513030", "name": "德国30ETF"},
    {"code": "513520", "name": "日经ETF"},
    {"code": "513880", "name": "日经225ETF"},
    {"code": "159985", "name": "豆粕ETF"},
    {"code": "162411", "name": "华宝油气LOF"},
    {"code": "164906", "name": "中国互联LOF"},
    {"code": "513220", "name": "游戏传媒ETF"},
    {"code": "159740", "name": "恒生科技ETF"},
    {"code": "159792", "name": "港股通互联网ETF"},
    {"code": "513060", "name": "恒生医疗ETF"},
    {"code": "513130", "name": "恒生科技ETF"},
    {"code": "159954", "name": "H股ETF"},
    {"code": "513090", "name": "港股通50ETF"},
    {"code": "513120", "name": "恒生科技30ETF"},
    {"code": "159866", "name": "日经ETF"},
    {"code": "513000", "name": "225ETF"},
    {"code": "513400", "name": "道琼斯ETF"},
    {"code": "513010", "name": "恒生港股通ETF"},
    {"code": "513110", "name": "纳指科技ETF"},
    {"code": "159981", "name": "能源化工ETF"},
    {"code": "008763", "name": "天弘越南市场"},
    {"code": "006105", "name": "宏利印度机会"},
    {"code": "020712", "name": "三菱日联日经"},
]

FALLBACK_LIMITS = {
    "513050": "不限", "159941": "暂停", "513100": "暂停", "513500": "不限",
    "513180": "不限", "513330": "不限", "159920": "不限", "161129": "限2万",
    "513030": "限3000", "513520": "限10万", "513880": "限10万", "159985": "限2000",
    "162411": "限500", "164906": "不限", "513220": "不限", "159740": "不限",
    "159792": "不限", "513060": "不限", "513130": "不限", "159954": "不限",
    "513090": "不限", "513120": "不限", "159866": "限10万", "513000": "限100",
    "513400": "暂停", "513010": "不限", "513110": "暂停", "159981": "限200",
    "008763": "暂停", "006105": "限100", "020712": "暂停"
}


def generate_mock_quotes() -> List[Dict]:
    import random
    mock_data = []
    for fund in QDII_FUNDS:
        price = round(random.uniform(0.8, 2.5), 3)
        rate = round(random.uniform(-3, 3), 2)
        mock_data.append({
            "f12": fund["code"],
            "f2": price,
            "f3": rate,
            "f18": round(price * (1 - rate / 100), 4)
        })
    return mock_data


def format_limit_text(status: str, limit: float) -> str:
    if not status:
        return "—"
    if "暂停" in status:
        return "暂停"
    if "限制" in status:
        if 0 < limit < 1000000000000:
            if limit >= 100000000:
                return f"限{round(limit / 100000000, 2)}亿"
            if limit >= 10000:
                return f"限{round(limit / 10000)}万"
            return f"限{limit}"
        return "暂停"
    if "开放" in status:
        return "不限"
    return status


async def fetch_quotes(client: httpx.AsyncClient) -> List[Dict]:
    quotes = []
    
    try:
        codes = [fund['code'] for fund in QDII_FUNDS]
        secids = []
        for code in codes:
            prefix = "1" if code.startswith(("5", "6")) else "0"
            secids.append(f"{prefix}.{code}")
        
        secid_str = ",".join(secids)
        url = f"https://push2.eastmoney.com/api/qt/ulist.np/get?fltt=2&invt=2&fields=f12,f14,f2,f3,f15,f16,f17,f18&secids={secid_str}&_={int(datetime.now().timestamp() * 1000)}"
        
        response = await client.get(url, headers={
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.38"
        }, timeout=10.0)
        
        if response.status_code == 200:
            data = response.json()
            if data and 'data' in data and 'diff' in data['data']:
                for item in data['data']['diff']:
                    if item.get('f12') and item.get('f2'):
                        quotes.append({
                            "f12": item.get('f12'),
                            "f2": item.get('f2', 0),
                            "f3": item.get('f3', 0),
                            "f18": item.get('f18', item.get('f2', 0))
                        })
                logger.info(f"Fetched {len(quotes)} real-time quotes from Eastmoney API")
        
        if quotes:
            return quotes
            
    except Exception as e:
        logger.warning(f"Failed to fetch from API: {e}")
    
    logger.warning("Using mock data as fallback")
    return generate_mock_quotes()


async def fetch_fund_limits(client: httpx.AsyncClient, codes: List[str]) -> Dict[str, str]:
    if not codes:
        return {}
    
    code_str = ",".join(codes)
    url = f"https://fundmobapi.eastmoney.com/FundMApi/FundBaseTypeInformation.ashx?FCODES={code_str}&deviceid=Wap&plat=Wap&product=EFund&version=2.0.0&_={int(datetime.now().timestamp() * 1000)}"
    
    try:
        response = await client.get(url, timeout=10.0)
        response.raise_for_status()
        data = response.json()
        
        limits = {}
        datas = data.get("Datas")
        if datas is None:
            return {}
        if not isinstance(datas, list):
            return {}
            
        for item in datas:
            if not isinstance(item, dict):
                continue
            code = item.get("FCODE")
            status = item.get("SGZT", "")
            limit = float(item.get("MAXSG", 0))
            limits[code] = format_limit_text(status, limit)
        return limits
    except Exception as e:
        logger.error(f"Failed to fetch fund limits: {e}")
        return {}


async def fetch_all_limits(client: httpx.AsyncClient) -> Dict[str, str]:
    chunk_size = 20
    all_limits = {}
    
    chunks = [QDII_FUNDS[i:i + chunk_size] for i in range(0, len(QDII_FUNDS), chunk_size)]
    code_chunks = [[fund["code"] for fund in chunk] for chunk in chunks]
    
    tasks = [fetch_fund_limits(client, codes) for codes in code_chunks]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for result in results:
        if isinstance(result, dict):
            all_limits.update(result)
    
    return all_limits


@app.get("/api/funds")
async def get_qdii_funds():
    async with httpx.AsyncClient() as client:
        quotes, limits = await asyncio.gather(
            fetch_quotes(client),
            fetch_all_limits(client),
            return_exceptions=True
        )
        
        if isinstance(quotes, Exception):
            quotes = []
        if isinstance(limits, Exception):
            limits = {}
    
    funds_map = {}
    
    for fund in QDII_FUNDS:
        funds_map[fund["code"]] = {
            "id": fund["code"],
            "name": fund["name"],
            "code": fund["code"],
            "valuation": 0,
            "valuationRate": 0,
            "premiumRate": 0,
            "marketPrice": 0,
            "marketPriceRate": 0,
            "limitText": FALLBACK_LIMITS.get(fund["code"], "—"),
            "isWatchlisted": False
        }
    
    for quote in quotes:
        code = quote.get("f12")
        if code not in funds_map:
            continue
        
        fund = funds_map[code]
        price = quote.get("f2", "-")
        pre_close = quote.get("f18", "-")
        rate = quote.get("f3", "-")
        
        try:
            price_val = float(price) if price != "-" else 0
            pre_close_val = float(pre_close) if pre_close != "-" else 0
            rate_val = float(rate) if rate != "-" else 0
            
            valuation = pre_close_val if pre_close_val > 0 else price_val
            premium_rate = ((price_val - valuation) / valuation * 100) if price_val > 0 and valuation > 0 else 0
            
            fund["marketPrice"] = round(price_val, 3)
            fund["marketPriceRate"] = round(rate_val, 2)
            fund["valuation"] = round(valuation, 4)
            fund["premiumRate"] = round(premium_rate, 2)
        except (ValueError, ZeroDivisionError):
            pass
    
    for code, limit_text in limits.items():
        if code in funds_map:
            funds_map[code]["limitText"] = limit_text
    
    funds = list(funds_map.values())
    funds.sort(key=lambda x: (-x["marketPrice"] == 0, -x["premiumRate"]))
    
    return funds


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
