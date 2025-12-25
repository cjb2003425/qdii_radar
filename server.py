from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import httpx
import asyncio
import re
from datetime import datetime
from typing import List, Dict, Optional
import logging
from html import unescape
from data.funds_loader import QDII_FUNDS, API_CONFIG
import akshare as ak
import json
import os
from pathlib import Path

# Import notification modules
from notifications.models import init_db, get_db, NotificationConfig, EmailRecipient, NotificationHistory
from notifications.monitor import monitor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    # Startup: Initialize database and monitor
    logger.info("Starting up QDII Fund Radar API...")
    init_db()  # Initialize notification database
    await monitor.initialize()

    # Auto-start monitoring if enabled
    if monitor.is_enabled():
        logger.info("Auto-starting notification monitor...")
        asyncio.create_task(monitor.start_monitoring())

    yield

    # Shutdown: Stop monitoring
    logger.info("Shutting down QDII Fund Radar API...")
    await monitor.stop_monitoring()


app = FastAPI(title="QDII Fund Radar API", lifespan=lifespan)

# 全局缓存AKShare数据
akshare_cache = None
akshare_cache_time = None
AKSHARE_CACHE_DURATION = 3600  # 缓存1小时

# 添加常量定义
FALLBACK_LIMITS = {
    "161130": "开放",
    "002732": "开放"
}


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def format_limit_text(status: str, limit: float) -> str:
    if not status:
        return "—"

    # 如果有具体的限额数值，优先显示限额（包括暂停状态的基金）
    if 0 < limit < 1000000000000:
        if limit >= 100000000:
            return f"限{round(limit / 100000000, 2)}亿"
        if limit >= 10000:
            return f"限{round(limit / 10000)}万"
        # 对于小于1万的限额，如果是整数则不显示小数点
        if limit == int(limit):
            return f"限{int(limit)}"
        return f"限{limit}"

    # 没有具体限额时，根据状态显示
    if "暂停" in status:
        return "暂停"
    if "限制" in status or "限大额" in status:
        return "暂停"  # 有状态但无限额数值，显示暂停
    if "开放" in status:
        return "不限"
    return status


def parse_fund_limit_from_html(html_content: str) -> Dict[str, str]:
    """从东方财富网页解析基金限额信息"""
    limits = {}

    if not html_content:
        return limits

    try:
        # 查找申购状态
        purchase_status_pattern = r'<td class="th w110">申购状态</td>\s*<td class="w135">([^<]+)</td>'
        purchase_limit_pattern = r'<td class="th w110">日累计申购限额</td>\s*<td class="w135">([\d.]+)(万元|元)</td>'

        purchase_status_match = re.search(
            purchase_status_pattern, html_content)
        purchase_limit_match = re.search(purchase_limit_pattern, html_content)

        if purchase_status_match:
            status = unescape(purchase_status_match.group(1).strip())

            if "限大额" in status:
                # 如果是限大额，查找具体限额
                if purchase_limit_match:
                    limit_value = float(purchase_limit_match.group(1))
                    unit = purchase_limit_match.group(2) if len(purchase_limit_match.groups()) > 1 else "元"
                    # 如果是万元，转换为元
                    if unit == "万元":
                        limit_value = limit_value * 10000
                    limits["status"] = "限制"
                    limits["limit"] = limit_value
                else:
                    limits["status"] = "限制"
                    limits["limit"] = 0
            elif "暂停" in status:
                # 即使是暂停状态，也要检查是否有具体限额
                if purchase_limit_match:
                    limit_value = float(purchase_limit_match.group(1))
                    unit = purchase_limit_match.group(2) if len(purchase_limit_match.groups()) > 1 else "元"
                    # 如果是万元，转换为元
                    if unit == "万元":
                        limit_value = limit_value * 10000
                    limits["status"] = "暂停"
                    limits["limit"] = limit_value  # 保留限额数值
                else:
                    limits["status"] = "暂停"
                    limits["limit"] = 0
            elif "开放" in status:
                limits["status"] = "开放"
                limits["limit"] = 0
            elif status in ("---", "——", "—"):
                # 如果状态显示为破折号，表示暂无数据，使用默认"开放"状态
                limits["status"] = "开放"
                limits["limit"] = 0
            else:
                limits["status"] = status
                limits["limit"] = 0

    except Exception as e:
        logger.warning(f"Failed to parse HTML fund limits: {e}")

    return limits

def parse_fund_nav_from_html(html_content: str) -> tuple:
    """从东方财富网页解析基金净值信息"""
    try:
        # 查找净值数据
        nav_patterns = [
            r'<span class="ui-font-large[^"]*">([\d.]+)</span>',
            r'单位净值（[\s\S]*?<b[^>]*>\s*([\d.]+)',
            r'单位净值[：:]\s*<span[^>]*>([\d.]+)</span>',
            r'单位净值\([\s\S]*?<b[^>]*>\s*([\d.]+)',
            r'"DWJZ":"([\d.]+)"',
            r'DWJZ[：:]["\']?([\d.]+)["\']?',
        ]

        nav_rate_patterns = [
            r'<span class="ui-font-middle[^"]*">([-\d.]+)%</span>',
            r'<b[^>]*>[\s\S]*?\(\s*([-\d.]+)\s*%\s*\)',
            r'日增长率[（\(][^）)]*[）)]：\s*<span[^>]*>([-\d.]+)%</span>',
            r'日增长率[：:]\s*<span[^>]*>([-\d.]+)%</span>',
            r'"JZZZL":"([-\d.]+)"',
            r'JZZZL[：:]["\']?([-\d.]+)["\']?',
        ]

        nav = None
        nav_rate = None

        for pattern in nav_patterns:
            match = re.search(pattern, html_content)
            if match:
                try:
                    nav = float(match.group(1))
                    break
                except ValueError:
                    continue

        for pattern in nav_rate_patterns:
            match = re.search(pattern, html_content)
            if match:
                try:
                    nav_rate = float(match.group(1))
                    break
                except ValueError:
                    continue

        if nav is not None:
            logger.info(f"Successfully parsed NAV: {nav}, {nav_rate}")
            return nav, nav_rate if nav_rate is not None else 0
        else:
            logger.warning("Failed to find NAV in HTML")

    except Exception as e:
        logger.warning(f"Failed to parse HTML fund NAV: {e}")

    return None, None


def fetch_nav_from_akshare(code: str) -> tuple:
    """使用AKShare获取基金净值数据（带缓存）"""
    global akshare_cache, akshare_cache_time
    
    try:
        current_time = datetime.now().timestamp()
        
        # 检查缓存是否过期
        if akshare_cache is None or (current_time - akshare_cache_time > AKSHARE_CACHE_DURATION):
            logger.info("AKShare: Refreshing cache...")
            akshare_cache = ak.fund_open_fund_daily_em()
            akshare_cache_time = current_time
        
        fund_data = akshare_cache[akshare_cache['基金代码'] == code]
        
        if not fund_data.empty:
            # 尝试获取最新的单位净值（可能今天或昨天的数据）
            nav = None
            nav_rate = 0.0
            
            # 按日期优先级尝试获取NAV
            for col in akshare_cache.columns:
                if '单位净值' in col and '累计净值' not in col and '日增长值' not in col:
                    nav_str = fund_data[col].values[0]
                    if nav_str and str(nav_str).strip() and str(nav_str) != '-':
                        try:
                            nav = float(nav_str)
                            break
                        except (ValueError, TypeError):
                            continue
            
            # 获取日增长率
            if '日增长率' in fund_data.columns:
                rate_str = fund_data['日增长率'].values[0]
                if rate_str and str(rate_str).strip() and str(rate_str) != '-':
                    # 去掉百分号并转换为float
                    rate_str = str(rate_str).replace('%', '').strip()
                    try:
                        nav_rate = float(rate_str)
                    except (ValueError, TypeError):
                        nav_rate = 0.0
            
            if nav is not None:
                logger.info(f"AKShare fetched NAV for {code}: {nav}, {nav_rate}%")
                return nav, nav_rate
        
        logger.warning(f"AKShare: No NAV data found for {code}")
        return None, None
        
    except Exception as e:
        logger.warning(f"AKShare failed to fetch NAV for {code}: {e}")
        return None, None


async def fetch_quotes_for_codes(client: httpx.AsyncClient, codes: List[str]) -> List[Dict]:
    """获取指定基金代码的实时行情"""
    quotes = []

    # 尝试获取场内基金数据（LOF基金）
    # 自动检测LOF基金：尝试从Eastmoney API获取实时数据
    try:
        secids = []
        for code in codes:
            prefix = "1" if code.startswith(("5", "6")) else "0"
            secids.append(f"{prefix}.{code}")

        secid_str = ",".join(secids)
        url = f"https://push2.eastmoney.com/api/qt/ulist.np/get?fltt=2&invt=2&fields=f12,f14,f2,f3,f15,f16,f17,f18&secids={
            secid_str}&_={int(datetime.now().timestamp() * 1000)}"

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
                            "f17": item.get('f17', item.get('f2', 0)),
                            "f18": item.get('f18', item.get('f2', 0))
                        })
                logger.info(
                    f"Fetched {len(quotes)} real-time quotes from Eastmoney API")

    except Exception as e:
        logger.warning(f"Failed to fetch from market API: {e}")

    return quotes


async def fetch_quotes(client: httpx.AsyncClient) -> List[Dict]:
    quotes = []

    # 尝试获取所有基金的实时数据（自动检测LOF基金）
    try:
        codes = [fund['code'] for fund in QDII_FUNDS]
        secids = []
        for code in codes:
            prefix = "1" if code.startswith(("5", "6")) else "0"
            secids.append(f"{prefix}.{code}")

        secid_str = ",".join(secids)
        url = f"https://push2.eastmoney.com/api/qt/ulist.np/get?fltt=2&invt=2&fields=f12,f14,f2,f3,f15,f16,f17,f18&secids={
            secid_str}&_={int(datetime.now().timestamp() * 1000)}"

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
                            "f17": item.get('f17', item.get('f2', 0)),
                            "f18": item.get('f18', item.get('f2', 0))
                        })
                logger.info(
                    f"Fetched {len(quotes)} real-time quotes from Eastmoney API")

    except Exception as e:
        logger.warning(f"Failed to fetch from market API: {e}")

    # 为其他基金获取净值数据（从东方财富移动API）
    try:
        lof_codes = {q["f12"] for q in quotes}
        nav_codes = [fund['code'] for fund in QDII_FUNDS if fund['code'] not in lof_codes]
        
        for code in nav_codes:
            try:
                # 使用东方财富移动API获取净值数据
                url = f"https://fundmobapi.eastmoney.com/FundMApi/FundNetValue.ashx?FCODES={code}&deviceid=Wap&plat=Wap&product=EFund&version=2.0.0&_={int(datetime.now().timestamp())}"
                response = await client.get(url, headers={
                    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.38"
                }, timeout=10.0)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("Datas") and len(data["Datas"]) > 0:
                        fund_data = data["Datas"][0]
                        nav = float(fund_data.get("NAV", "0"))
                        nav_rate = float(fund_data.get("DAYGROWTHRATE", "0"))
                        
                        if nav > 0:
                            quotes.append({
                                "f12": code,
                                "f2": nav,
                                "f3": nav_rate,
                                "f17": nav,
                                "f18": nav
                            })
                            logger.info(f"Fetched NAV for {code}: {nav}, {nav_rate}%")
                
            except Exception as e:
                logger.warning(f"Failed to fetch NAV for {code}: {e}")
                continue

    except Exception as e:
        logger.warning(f"Failed to fetch NAV data: {e}")

    return quotes


async def fetch_fund_limits(client: httpx.AsyncClient, codes: List[str]) -> Dict[str, str]:
    if not codes:
        return {}

    limits = {}

    for code in codes:
        try:
            url = f"https://fundf10.eastmoney.com/jjfl_{code}.html"
            response = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.38"
            }, timeout=10.0)

            if response.status_code == 200:
                html_content = response.text
                parsed_limits = parse_fund_limit_from_html(html_content)

                if parsed_limits:
                    status = parsed_limits.get("status", "")
                    limit_value = parsed_limits.get("limit", 0)
                    limits[code] = format_limit_text(status, limit_value)
                    logger.info(f"Fetched limit for {code}: {limits[code]}")

        except Exception as e:
            logger.warning(f"Failed to fetch limit for {code}: {e}")
            continue

    return limits


async def fetch_limits_for_codes(client: httpx.AsyncClient, codes: List[str]) -> Dict[str, str]:
    """获取指定基金代码的限额信息"""
    if not codes:
        return {}

    # 分批处理，每批5个基金
    chunk_size = 5
    all_limits = {}

    chunks = [codes[i:i + chunk_size]
              for i in range(0, len(codes), chunk_size)]

    for chunk in chunks:
        tasks = [fetch_single_fund_limit(client, code) for code in chunk]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, dict) and result:
                all_limits.update(result)

    return all_limits


async def fetch_all_limits(client: httpx.AsyncClient) -> Dict[str, str]:
    # 为每个基金单独创建任务
    all_codes = [fund["code"] for fund in QDII_FUNDS]

    # 分批处理，每批5个基金
    chunk_size = 5
    all_limits = {}

    chunks = [all_codes[i:i + chunk_size]
              for i in range(0, len(all_codes), chunk_size)]

    for chunk in chunks:
        tasks = [fetch_single_fund_limit(client, code) for code in chunk]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, dict) and result:
                all_limits.update(result)

    return all_limits


async def fetch_single_fund_limit(client: httpx.AsyncClient, code: str) -> Dict[str, str]:
    """获取单个基金的限额信息"""
    try:
        url = f"https://fundf10.eastmoney.com/jjfl_{code}.html"
        response = await client.get(url, headers={
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.38"
        }, timeout=10.0)

        if response.status_code == 200:
            html_content = response.text
            parsed_limits = parse_fund_limit_from_html(html_content)
            nav, nav_rate = parse_fund_nav_from_html(html_content)

            result = {}
            if parsed_limits:
                status = parsed_limits.get("status", "")
                limit_value = parsed_limits.get("limit", 0)
                limit_text = format_limit_text(status, limit_value)
                result["limit"] = limit_text
                logger.info(f"Fetched limit for {code}: {limit_text}")
            
            if nav is not None:
                result["nav"] = nav
                result["nav_rate"] = nav_rate
                logger.info(f"Fetched NAV for {code}: {nav}, {nav_rate}%")
            
            # 如果HTML解析没有获取到NAV，尝试使用AKShare
            if nav is None:
                akshare_nav, akshare_nav_rate = fetch_nav_from_akshare(code)
                if akshare_nav is not None:
                    result["nav"] = akshare_nav
                    result["nav_rate"] = akshare_nav_rate
                    logger.info(f"AKShare fallback NAV for {code}: {akshare_nav}, {akshare_nav_rate}%")
            
            if result:
                result["code"] = code
                return {code: result}

    except Exception as e:
        logger.warning(f"Failed to fetch limit for {code}: {e}")

    return {}


@app.post("/api/fund")
async def add_fund(code: str, name: str):
    """添加基金到funds.json文件"""
    try:
        # 获取funds.json文件路径
        funds_file_path = Path(__file__).parent / "data" / "funds.json"
        
        # 读取现有数据
        with open(funds_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 检查基金是否已存在
        existing_fund = next((f for f in data["funds"] if f["code"] == code), None)
        if existing_fund:
            logger.info(f"Fund {code} already exists in funds.json")
            return {"success": True, "message": "基金已存在", "fund": existing_fund}
        
        # 添加新基金
        new_fund = {"code": code, "name": name}
        data["funds"].append(new_fund)
        
        # 保存到文件
        with open(funds_file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Added fund {code} - {name} to funds.json")
        
        # 更新全局QDII_FUNDS
        from data.funds_loader import reload_funds
        reload_funds()
        
        return {"success": True, "message": "基金添加成功", "fund": new_fund}
        
    except Exception as e:
        logger.error(f"Failed to add fund {code}: {e}")
        raise HTTPException(status_code=500, detail=f"添加基金失败: {str(e)}")


@app.get("/api/fund/{code}")
async def get_fund_info(code: str):
    """获取单个基金信息"""
    global akshare_cache, akshare_cache_time
    
    try:
        current_time = datetime.now().timestamp()
        
        # 确保缓存存在
        if akshare_cache is None or (current_time - akshare_cache_time > AKSHARE_CACHE_DURATION):
            logger.info("AKShare: Refreshing cache for fund info...")
            akshare_cache = ak.fund_open_fund_daily_em()
            akshare_cache_time = current_time
        
        fund_data = akshare_cache[akshare_cache['基金代码'] == code]
        
        if not fund_data.empty:
            fund_name = fund_data['基金简称'].values[0]
            return {"found": True, "code": code, "name": fund_name}
        else:
            return {"found": False, "code": code}
    except Exception as e:
        logger.warning(f"Failed to fetch fund info for {code}: {e}")
        return {"found": False, "code": code}


@app.get("/api/funds")
async def get_qdii_funds(codes: str = None):
    """
    获取基金数据
    codes: 可选的基金代码列表，逗号分隔。如果提供，只返回这些基金的数据
    """
    # 确定要处理的基金列表
    if codes:
        requested_codes = [code.strip() for code in codes.split(',')]
        funds_to_process = []
        for code in requested_codes:
            # 从QDII_FUNDS中查找，如果找不到则创建基本信息
            fund_info = next((f for f in QDII_FUNDS if f['code'] == code), None)
            if fund_info:
                funds_to_process.append(fund_info)
            else:
                # 从AKShare获取基金名称
                fund_name = f"基金{code}"
                try:
                    global akshare_cache, akshare_cache_time
                    current_time = datetime.now().timestamp()
                    if akshare_cache is None or (current_time - akshare_cache_time > AKSHARE_CACHE_DURATION):
                        akshare_cache = ak.fund_open_fund_daily_em()
                        akshare_cache_time = current_time
                    
                    fund_data = akshare_cache[akshare_cache['基金代码'] == code]
                    if not fund_data.empty:
                        fund_name = fund_data['基金简称'].values[0]
                except:
                    pass
                
                funds_to_process.append({'code': code, 'name': fund_name})
    else:
        funds_to_process = QDII_FUNDS
    
    async with httpx.AsyncClient() as client:
        # 获取所有需要处理的基金代码
        all_codes = [fund['code'] for fund in funds_to_process]
        
        quotes, limits = await asyncio.gather(
            fetch_quotes_for_codes(client, all_codes),
            fetch_limits_for_codes(client, all_codes),
            return_exceptions=True
        )

        if isinstance(quotes, Exception):
            quotes = []
        if isinstance(limits, Exception):
            limits = {}

    funds_map = {}

    for fund in funds_to_process:
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
        pre_close_nav = quote.get("f17", "-")
        rate = quote.get("f3", "-")

        try:
            price_val = float(price) if price != "-" else 0
            nav_val = float(pre_close_nav) if pre_close_nav != "-" else 0
            rate_val = float(rate) if rate != "-" else 0

            valuation = price_val if price_val > 0 else nav_val

            fund["valuation"] = round(valuation, 4)
            fund["valuationRate"] = round(rate_val, 2)  # Add valuation rate
            fund["marketPrice"] = round(price_val, 4)
            fund["marketPriceRate"] = round(rate_val, 2)
            fund["premiumRate"] = 0  # Will be calculated after NAV is fetched
        except (ValueError, ZeroDivisionError):
            pass

    for code, limit_data in limits.items():
        if isinstance(limit_data, dict) and code in funds_map:
            if "limit" in limit_data:
                funds_map[code]["limitText"] = limit_data["limit"]
            if "nav" in limit_data:
                nav = limit_data["nav"]
                nav_rate = limit_data.get("nav_rate", 0)

                # NAV data should go to marketPrice (净值) not valuation (估值)
                funds_map[code]["marketPrice"] = round(nav, 4)
                funds_map[code]["marketPriceRate"] = round(nav_rate, 2)

                # Recalculate premium rate after NAV update
                valuation = funds_map[code].get("valuation", 0)
                if valuation > 0 and nav > 0:
                    premium_rate = ((valuation - nav) / nav) * 100
                    funds_map[code]["premiumRate"] = round(premium_rate, 2)

    funds = list(funds_map.values())
    funds.sort(key=lambda x: (-x["marketPrice"] == 0, -x["premiumRate"]))

    return funds


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


# ============================================================================
# Notification API Endpoints
# ============================================================================

from pydantic import BaseModel


class NotificationConfigModel(BaseModel):
    smtp_enabled: bool = False
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    premium_threshold_high: float = 5.0
    premium_threshold_low: float = -5.0
    check_interval_seconds: int = 300
    debounce_minutes: int = 60


@app.get("/api/notifications/config")
async def get_notification_config():
    """Get notification configuration (excluding password)."""
    session = get_db()
    try:
        configs = session.query(NotificationConfig).all()
        config_dict = {c.config_key: c.config_value for c in configs}

        # Don't return password
        if 'smtp_password' in config_dict:
            config_dict['smtp_password'] = '******' if config_dict['smtp_password'] else ''

        # Convert boolean and numeric fields
        result = {
            'smtp_enabled': config_dict.get('smtp_enabled', 'false').lower() == 'true',
            'smtp_host': config_dict.get('smtp_host', 'smtp.gmail.com'),
            'smtp_port': int(config_dict.get('smtp_port', '587')),
            'smtp_username': config_dict.get('smtp_username', ''),
            'smtp_password': config_dict.get('smtp_password', ''),
            'smtp_from_email': config_dict.get('smtp_from_email', ''),
            'premium_threshold_high': float(config_dict.get('premium_threshold_high', '5.0')),
            'premium_threshold_low': float(config_dict.get('premium_threshold_low', '-5.0')),
            'check_interval_seconds': int(config_dict.get('check_interval_seconds', '300')),
            'debounce_minutes': int(config_dict.get('debounce_minutes', '60')),
        }

        return result

    except Exception as e:
        logger.error(f"Failed to get notification config: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@app.post("/api/notifications/config")
async def update_notification_config(config: NotificationConfigModel):
    """Update notification configuration."""
    session = get_db()
    try:
        updates = {
            'smtp_enabled': str(config.smtp_enabled).lower(),
            'smtp_host': config.smtp_host,
            'smtp_port': str(config.smtp_port),
            'smtp_username': config.smtp_username,
            'smtp_from_email': config.smtp_from_email,
            'premium_threshold_high': str(config.premium_threshold_high),
            'premium_threshold_low': str(config.premium_threshold_low),
            'check_interval_seconds': str(config.check_interval_seconds),
            'debounce_minutes': str(config.debounce_minutes),
        }

        # Only update password if provided (not empty or masked)
        if config.smtp_password and config.smtp_password != '******':
            updates['smtp_password'] = config.smtp_password

        for key, value in updates.items():
            existing = session.query(NotificationConfig).filter_by(config_key=key).first()
            if existing:
                existing.config_value = value
            else:
                new_config = NotificationConfig(config_key=key, config_value=value)
                session.add(new_config)

        session.commit()

        # Reload monitor configuration
        monitor._load_config()

        logger.info("Notification configuration updated")
        return {"status": "success"}

    except Exception as e:
        session.rollback()
        logger.error(f"Failed to update notification config: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


class TestEmailModel(BaseModel):
    recipient: str


@app.post("/api/notifications/test-email")
async def send_test_email(data: TestEmailModel):
    """Send a test email."""
    from notifications.email_service import EmailService

    email_service = EmailService()
    success = await email_service.send_test_email(data.recipient)

    if success:
        return {"status": "success", "message": "Test email sent"}
    else:
        raise HTTPException(status_code=500, detail="Failed to send test email")


class VerifyConfigModel(BaseModel):
    pass


@app.post("/api/notifications/verify-config")
async def verify_smtp_config():
    """Verify SMTP configuration."""
    from notifications.email_service import EmailService

    email_service = EmailService()
    result = await email_service.verify_smtp_config()

    if result.get('success'):
        return {"status": "success", "message": result.get('message')}
    else:
        raise HTTPException(status_code=400, detail=result.get('error'))


@app.get("/api/notifications/recipients")
async def get_recipients():
    """Get list of email recipients."""
    session = get_db()
    try:
        recipients = session.query(EmailRecipient).all()
        return [
            {
                'id': r.id,
                'email': r.email,
                'is_active': r.is_active,
                'added_at': r.added_at.isoformat()
            }
            for r in recipients
        ]
    except Exception as e:
        logger.error(f"Failed to get recipients: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


class AddRecipientModel(BaseModel):
    email: str


@app.post("/api/notifications/recipients")
async def add_recipient(data: AddRecipientModel):
    """Add a new email recipient."""
    session = get_db()
    try:
        # Check if already exists
        existing = session.query(EmailRecipient).filter_by(email=data.email).first()
        if existing:
            # Reactivate if exists but inactive
            existing.is_active = True
        else:
            new_recipient = EmailRecipient(email=data.email, is_active=True)
            session.add(new_recipient)

        session.commit()
        logger.info(f"Added recipient: {data.email}")
        return {"status": "success"}

    except Exception as e:
        session.rollback()
        logger.error(f"Failed to add recipient: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@app.delete("/api/notifications/recipients/{email}")
async def remove_recipient(email: str):
    """Remove an email recipient."""
    session = get_db()
    try:
        recipient = session.query(EmailRecipient).filter_by(email=email).first()
        if not recipient:
            raise HTTPException(status_code=404, detail="Recipient not found")

        session.delete(recipient)
        session.commit()
        logger.info(f"Removed recipient: {email}")
        return {"status": "success"}

    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to remove recipient: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@app.post("/api/notifications/monitoring/start")
async def start_monitoring():
    """Start the notification monitor."""
    success = await monitor.start_monitoring()
    if success:
        return {"status": "success", "message": "Monitoring started"}
    else:
        raise HTTPException(
            status_code=400,
            detail="Failed to start monitoring. Check if email notifications are enabled."
        )


@app.post("/api/notifications/monitoring/stop")
async def stop_monitoring():
    """Stop the notification monitor."""
    await monitor.stop_monitoring()
    return {"status": "success", "message": "Monitoring stopped"}


@app.get("/api/notifications/monitoring/status")
async def get_monitoring_status():
    """Get monitoring status."""
    return monitor.get_status()


@app.get("/api/notifications/history")
async def get_notification_history(limit: int = 20, offset: int = 0):
    """Get notification history."""
    from notifications.state_tracker import StateTracker

    tracker = StateTracker()
    history = await tracker.get_notification_history(limit=limit, offset=offset)
    return history


@app.get("/api/notifications/history/stats")
async def get_notification_stats():
    """Get notification statistics."""
    from notifications.state_tracker import StateTracker

    tracker = StateTracker()
    stats = await tracker.get_notification_stats()
    return stats


# ============================================================================
# Monitored Funds Management
# ============================================================================

class MonitoredFundsModel(BaseModel):
    """Model for monitored funds list."""
    funds: List[str]  # List of fund codes


@app.get("/api/notifications/monitored-funds")
async def get_monitored_funds():
    """Get list of monitored fund codes."""
    from notifications.models import get_db, MonitoredFund

    session = get_db()
    try:
        # Create table if not exists
        from sqlalchemy import text
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS monitored_funds (
                fund_code TEXT PRIMARY KEY,
                enabled BOOLEAN NOT NULL DEFAULT 1,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """))
        session.commit()

        monitored = session.query(MonitoredFund).filter_by(enabled=True).all()
        return [f.fund_code for f in monitored]

    except Exception as e:
        logger.error(f"Failed to get monitored funds: {e}")
        return []
    finally:
        session.close()


@app.post("/api/notifications/monitored-funds")
async def update_monitored_funds(data: MonitoredFundsModel):
    """Update the list of monitored funds."""
    from notifications.models import get_db, MonitoredFund
    from sqlalchemy import text

    session = get_db()
    try:
        # Create table if not exists
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS monitored_funds (
                fund_code TEXT PRIMARY KEY,
                enabled BOOLEAN NOT NULL DEFAULT 1,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """))
        session.commit()

        # Clear existing monitored funds
        session.execute(text("DELETE FROM monitored_funds"))

        # Insert new monitored funds
        for fund_code in data.funds:
            monitored = MonitoredFund(fund_code=fund_code, enabled=True)
            session.add(monitored)

        session.commit()
        logger.info(f"Updated monitored funds: {len(data.funds)} funds")
        return {"status": "success", "count": len(data.funds)}

    except Exception as e:
        session.rollback()
        logger.error(f"Failed to update monitored funds: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
