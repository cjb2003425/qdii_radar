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
from data.funds_loader import API_CONFIG
import data.funds_loader
import akshare as ak
import pandas as pd
import json
import os
from pathlib import Path

# SMTP config file path
SMTP_CONFIG_FILE = Path(__file__).parent / "config" / "smtp.json"

# Recipients config file path
RECIPIENTS_FILE = Path(__file__).parent / "config" / "recipients.json"

# Import notification modules
from notifications.models import init_db, get_db, NotificationConfig, EmailRecipient, NotificationHistory
from notifications.monitor import monitor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Chinese stock trading date cache
_trading_dates_cache = {}
_cache_date = None


def get_chinese_stock_dates(start_date: str = None, end_date: str = None) -> Dict:
    """
    Fetch Chinese stock market trading dates using AKShare.

    Args:
        start_date: Start date in YYYYMMDD format (default: 30 days ago)
        end_date: End date in YYYYMMDD format (default: today)

    Returns:
        Dict with trading dates info
    """
    from datetime import datetime, timedelta

    global _trading_dates_cache, _cache_date

    today = datetime.now()
    cache_key = f"{start_date}_{end_date}"

    # Check if cache is valid (refresh daily)
    if _cache_date == today.date() and cache_key in _trading_dates_cache:
        return _trading_dates_cache[cache_key]

    try:
        # Default date range: past 30 days to 30 days in future
        if not start_date:
            start_date = (today - timedelta(days=30)).strftime('%Y%m%d')
        if not end_date:
            end_date = (today + timedelta(days=30)).strftime('%Y%m%d')

        # Fetch trading calendar from AKShare
        # ak.tool_trade_date_hist_sina() returns historical trading dates
        df = ak.tool_trade_date_hist_sina()

        # Filter by date range
        df['trade_date'] = pd.to_datetime(df['trade_date'])
        start_dt = datetime.strptime(start_date, '%Y%m%d')
        end_dt = datetime.strptime(end_date, '%Y%m%d')

        mask = (df['trade_date'] >= start_dt) & (df['trade_date'] <= end_dt)
        filtered_df = df[mask]

        # Convert to list of date strings
        trading_dates = filtered_df['trade_date'].dt.strftime('%Y-%m-%d').tolist()

        # Check if today is a trading day
        today_str = today.strftime('%Y-%m-%d')
        is_trading_day = today_str in trading_dates

        # Get next trading day
        future_dates = [d for d in trading_dates if d > today_str]
        next_trading_day = future_dates[0] if future_dates else None

        # Get previous trading day
        past_dates = [d for d in trading_dates if d < today_str]
        previous_trading_day = past_dates[-1] if past_dates else None

        result = {
            'trading_dates': trading_dates,
            'is_trading_day': is_trading_day,
            'next_trading_day': next_trading_day,
            'previous_trading_day': previous_trading_day,
            'total_trading_days': len(trading_dates),
            'start_date': start_dt.strftime('%Y-%m-%d'),
            'end_date': end_dt.strftime('%Y-%m-%d'),
            'query_date': today_str
        }

        # Update cache
        _trading_dates_cache[cache_key] = result
        _cache_date = today.date()

        logger.info(f"Fetched {len(trading_dates)} trading dates from {start_date} to {end_date}")
        return result

    except Exception as e:
        logger.error(f"Failed to fetch trading dates: {e}")
        return {
            'trading_dates': [],
            'is_trading_day': True,  # Assume trading day on error
            'next_trading_day': None,
            'previous_trading_day': None,
            'total_trading_days': 0,
            'start_date': start_date,
            'end_date': end_date,
            'error': str(e)
        }


def is_trading_day(date: str = None) -> bool:
    """
    Check if a specific date is a Chinese stock trading day.

    Args:
        date: Date string in YYYY-MM-DD format (default: today)

    Returns:
        True if it's a trading day, False otherwise
    """
    from datetime import datetime

    if not date:
        date = datetime.now().strftime('%Y-%m-%d')

    try:
        trading_info = get_chinese_stock_dates()
        return date in trading_info['trading_dates']
    except Exception as e:
        logger.error(f"Failed to check trading day: {e}")
        return True  # Assume trading day on error


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    # Startup: Initialize database and monitor
    logger.info("Starting up QDII Fund Radar API...")
    init_db()  # Initialize notification database

    # Load SMTP config from file
    load_smtp_config_from_file()

    # Load recipients from file
    load_recipients_from_file()

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


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def load_smtp_config_from_file():
    """Load SMTP configuration from file and update database."""
    try:
        if not SMTP_CONFIG_FILE.exists():
            logger.warning(f"SMTP config file not found: {SMTP_CONFIG_FILE}")
            return False

        with open(SMTP_CONFIG_FILE, 'r', encoding='utf-8') as f:
            smtp_config = json.load(f)

        # Update database with file values
        session = get_db()
        try:
            for key, value in smtp_config.items():
                if key.startswith('_'):
                    continue  # Skip comment fields

                existing = session.query(NotificationConfig).filter_by(config_key=key).first()
                if existing:
                    existing.config_value = str(value)
                else:
                    config = NotificationConfig(config_key=key, config_value=str(value))
                    session.add(config)

            session.commit()
            logger.info(f"Loaded SMTP config from {SMTP_CONFIG_FILE}")
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to update SMTP config in database: {e}")
            return False
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Failed to load SMTP config file: {e}")
        return False


def load_recipients_from_file():
    """Load email recipients from file and update database."""
    try:
        if not RECIPIENTS_FILE.exists():
            logger.warning(f"Recipients config file not found: {RECIPIENTS_FILE}")
            return False

        with open(RECIPIENTS_FILE, 'r', encoding='utf-8') as f:
            recipients_list = json.load(f)

        # Get existing recipients
        session = get_db()
        try:
            # Mark all existing as inactive first
            session.query(EmailRecipient).update({'is_active': False})

            # Update or add recipients from file
            for recipient_data in recipients_list:
                email = recipient_data.get('email')
                active = recipient_data.get('active', True)

                if not email:
                    continue

                existing = session.query(EmailRecipient).filter_by(email=email).first()
                if existing:
                    existing.is_active = active
                else:
                    new_recipient = EmailRecipient(email=email, is_active=active)
                    session.add(new_recipient)

            session.commit()
            logger.info(f"Loaded {len(recipients_list)} recipients from {RECIPIENTS_FILE}")
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to update recipients in database: {e}")
            return False
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Failed to load recipients file: {e}")
        return False


def save_recipients_to_file():
    """Save all recipients from database to JSON file."""
    try:
        session = get_db()
        recipients = session.query(EmailRecipient).all()

        # Convert to list of dicts
        recipients_list = []
        for r in recipients:
            recipients_list.append({
                'email': r.email,
                'active': r.is_active
            })

        # Save to JSON file
        with open(RECIPIENTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(recipients_list, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved {len(recipients_list)} recipients to {RECIPIENTS_FILE}")
        session.close()
        return True
    except Exception as e:
        logger.error(f"Failed to save recipients to file: {e}")
        session.close()
        return False


def format_limit_text(status: str, limit: float) -> str:
    if not status:
        return "—"

    # 首先检查申购状态：如果是暂停申购，直接显示"暂停"
    if "暂停申购" in status:
        return "暂停"

    # 如果有具体的限额数值，显示限额
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


def extract_limit_value(limit_text: str) -> int:
    """
    Extract numeric limit value from limit text.
    Returns limit value in yuan, or 0 if no limit.

    Examples:
    - "限10" → 10
    - "限5000" → 5000
    - "限100万" → 1000000
    - "限10亿" → 1000000000
    - "暂停" → 0
    - "不限" → -1 (unlimited)
    """
    if not limit_text or limit_text == "—":
        return 0

    # Suspended
    if "暂停" in limit_text:
        return 0

    # Unlimited
    if "不限" in limit_text:
        return -1

    # Extract numeric value and unit
    import re

    # Match patterns like "限100", "限50万", "限10亿"
    match = re.search(r'限([\d.]+)(万|亿)?', limit_text)
    if match:
        value = float(match.group(1))
        unit = match.group(2)

        if unit == '万':
            return int(value * 10000)
        elif unit == '亿':
            return int(value * 100000000)
        else:
            return int(value)

    return 0


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
                # 暂停状态不保留限额数值，因为无法购买
                limits["status"] = status  # 保留完整状态（如"暂停申购"）
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


# ============================================================================
# Historical NAV Data Fetching (for 1-Year Percentage Change)
# ============================================================================

HISTORICAL_CACHE_DURATION = 86400  # 24 hours


def get_historical_cache(session, fund_code: str):
    """Get cached historical NAV data from database."""
    from notifications.models import HistoricalNavCache
    from datetime import datetime, timedelta

    try:
        cached = session.query(HistoricalNavCache).filter_by(fund_code=fund_code).first()
        if cached:
            # Check if cache is still valid (24 hours)
            cache_age = (datetime.utcnow() - cached.cached_at).total_seconds()
            if cache_age < HISTORICAL_CACHE_DURATION:
                logger.debug(f"Using cached historical data for {fund_code} ({cache_age:.0f}s old)")
                return {
                    'percentage_change': cached.percentage_change,
                    'days_calculated': cached.days_calculated
                }
            else:
                logger.debug(f"Historical cache expired for {fund_code}")
        return None
    except Exception as e:
        logger.warning(f"Failed to get historical cache for {fund_code}: {e}")
        return None


def set_historical_cache(session, fund_code: str, nav_1_year_ago: float, percentage_change: float, days_calculated: int):
    """Cache historical NAV data in database."""
    from notifications.models import HistoricalNavCache

    try:
        existing = session.query(HistoricalNavCache).filter_by(fund_code=fund_code).first()
        if existing:
            existing.nav_1_year_ago = nav_1_year_ago
            existing.percentage_change = percentage_change
            existing.days_calculated = days_calculated
            existing.cached_at = datetime.utcnow()
        else:
            new_cache = HistoricalNavCache(
                fund_code=fund_code,
                nav_1_year_ago=nav_1_year_ago,
                percentage_change=percentage_change,
                days_calculated=days_calculated
            )
            session.add(new_cache)
        session.commit()
        logger.info(f"Cached historical data for {fund_code}: {percentage_change:.2f}% over {days_calculated} days")
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to cache historical data for {fund_code}: {e}")


def fetch_historical_nav_eastmoney(code: str, days: int = 365) -> dict:
    """
    Fetch historical NAV data from AKShare.

    Returns:
        {
            'nav_1_year_ago': float,
            'percentage_change': float,
            'days_found': int
        }
        or None if fetch fails.
    """
    from datetime import datetime, timedelta

    try:
        # Use AKShare to get historical cumulative NAV data
        # Using cumulative NAV to avoid dividend distribution effects
        # Data is returned with OLDEST first, NEWEST last
        df = ak.fund_open_fund_info_em(symbol=code, indicator="累计净值走势", period="三年")

        if df is not None and not df.empty and len(df) > 1:
            # Convert date strings to datetime for comparison
            df['净值日期_dt'] = pd.to_datetime(df['净值日期'])

            # Filter to only get data from approximately the last 'days' (365)
            # Get the newest date first
            newest_date = df.iloc[-1]['净值日期_dt']
            cutoff_date = newest_date - timedelta(days=days + 30)  # Add buffer to ensure we get enough data

            # Filter to keep only recent data (within cutoff + buffer)
            df_filtered = df[df['净值日期_dt'] >= cutoff_date].copy()

            if df_filtered.empty or len(df_filtered) < 2:
                logger.warning(f"Not enough recent data for {code}")
                return None

            # Get current cumulative NAV from the LAST row (newest)
            nav_current = float(df_filtered.iloc[-1]['累计净值'])
            current_date = df_filtered.iloc[-1]['净值日期']

            # Find cumulative NAV from approximately 1 year ago
            one_year_ago_target = datetime.now() - timedelta(days=days)
            df_filtered['time_diff'] = abs(df_filtered['净值日期_dt'] - one_year_ago_target)
            closest_idx = df_filtered['time_diff'].idxmin()
            nav_1_year_ago = float(df_filtered.loc[closest_idx, '累计净值'])
            past_date = df_filtered.loc[closest_idx, '净值日期']

            if nav_1_year_ago > 0:
                # Calculate percentage change: (current - old) / old * 100
                # The BASE is nav_1_year_ago (NAV from 1 year ago)
                percentage_change = ((nav_current - nav_1_year_ago) / nav_1_year_ago) * 100
                days_found = len(df_filtered)

                logger.info(f"Fetched historical cumulative NAV for {code}: {nav_1_year_ago:.4f} ({past_date}) → {nav_current:.4f} ({current_date}) = {percentage_change:.2f}% over {days_found} trading days")
                return {
                    'nav_1_year_ago': nav_1_year_ago,
                    'percentage_change': round(percentage_change, 2),
                    'days_found': days_found
                }

        logger.warning(f"Could not fetch historical NAV data for {code}")
        return None

    except Exception as e:
        logger.warning(f"Failed to fetch historical NAV for {code}: {e}")
        return None


def fetch_historical_etf_price(code: str, days: int = 365) -> dict:
    """
    Fetch historical trading price for ETF/LOF funds using AKShare.

    Returns:
        {
            'price_1_year_ago': float,
            'percentage_change': float,
            'days_found': int
        }
        or None if fetch fails.
    """
    from datetime import datetime, timedelta

    try:
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')

        df = ak.fund_etf_hist_em(
            symbol=code,
            period='daily',
            start_date=start_date,
            end_date=end_date
        )

        if df is not None and not df.empty and len(df) > 1:
            # Use closing price from oldest row
            price_1_year_ago = df.iloc[-1]['收盘']
            current_price = df.iloc[0]['收盘']
            percentage_change = ((current_price - price_1_year_ago) / price_1_year_ago) * 100

            logger.info(f"Fetched historical ETF price for {code}: {percentage_change:.2f}% over {len(df)} days")
            return {
                'price_1_year_ago': price_1_year_ago,
                'percentage_change': round(percentage_change, 2),
                'days_found': len(df)
            }

    except Exception as e:
        logger.warning(f"Failed to fetch historical ETF price for {code}: {e}")
        return None


def get_one_year_change(code: str, is_exchange_traded: bool) -> dict:
    """
    Get 1-year percentage change for a fund based on NAV, using cache if available.

    Args:
        code: Fund code
        is_exchange_traded: True if fund is ETF/LOF (ignored - always uses NAV)

    Returns:
        {
            'percentage_change': float or 0,
            'available': bool
        }
    """
    from notifications.models import get_db

    session = get_db()
    try:
        # Check cache first
        cached = get_historical_cache(session, code)
        if cached:
            return {
                'percentage_change': cached['percentage_change'],
                'available': True
            }

        # Cache miss or expired - fetch fresh NAV data (always use NAV, not trading price)
        hist_data = fetch_historical_nav_eastmoney(code)

        if hist_data:
            # Cache the result
            set_historical_cache(
                session,
                code,
                hist_data.get('nav_1_year_ago', 0),
                hist_data['percentage_change'],
                hist_data['days_found']
            )
            return {
                'percentage_change': hist_data['percentage_change'],
                'available': True
            }
        else:
            return {
                'percentage_change': 0,
                'available': False
            }
    except Exception as e:
        logger.error(f"Error getting 1-year change for {code}: {e}")
        return {
            'percentage_change': 0,
            'available': False
        }
    finally:
        session.close()


async def fetch_quotes_for_codes(client: httpx.AsyncClient, codes: List[str]) -> List[Dict]:
    """获取指定基金代码的实时行情"""
    quotes = []

    # 尝试获取场内基金数据（LOF基金）
    # 自动检测LOF基金：尝试从Eastmoney API获取实时数据
    try:
        secids = []
        for code in codes:
            # Determine market prefix:
            # Shanghai (1): 5xxxx, 50xxxx, 51xxxx, 52xxxx, 53xxxx, 58xxxx, 59xxx, 15xxxx (but not 159xxx)
            # Shenzhen (0): 16xxxx, 159xxx, 12xxxx
            if code.startswith(("5", "6")) or code[:2].startswith(("50", "51", "52", "53", "58", "59")):
                prefix = "1"  # Shanghai market
            elif code.startswith("15") and not code.startswith("159"):
                prefix = "1"  # Shanghai market (15xxxx but not 159xxx)
            else:
                prefix = "0"  # Shenzhen market (includes 159xxx, 16xxxx, 12xxxx)
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
        codes = [fund['code'] for fund in data.funds_loader.QDII_FUNDS]
        secids = []
        for code in codes:
            # Determine market prefix:
            # Shanghai (1): 5xxxx, 50xxxx, 51xxxx, 52xxxx, 53xxxx, 58xxxx, 59xxx, 15xxxx (but not 159xxx)
            # Shenzhen (0): 16xxxx, 159xxx, 12xxxx
            if code.startswith(("5", "6")) or code[:2].startswith(("50", "51", "52", "53", "58", "59")):
                prefix = "1"  # Shanghai market
            elif code.startswith("15") and not code.startswith("159"):
                prefix = "1"  # Shanghai market (15xxxx but not 159xxx)
            else:
                prefix = "0"  # Shenzhen market (includes 159xxx, 16xxxx, 12xxxx)
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
        nav_codes = [fund['code'] for fund in data.funds_loader.QDII_FUNDS if fund['code'] not in lof_codes]
        
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
    all_codes = [fund["code"] for fund in data.funds_loader.QDII_FUNDS]

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

        # 添加到监控数据库
        try:
            from notifications.models import get_db, MonitoredFund
            session = get_db()
            try:
                monitored_fund = MonitoredFund(fund_code=code, enabled=True)
                session.merge(monitored_fund)  # Use merge to avoid duplicate key errors
                session.commit()
                logger.info(f"Added fund {code} to monitoring database")
            finally:
                session.close()
        except Exception as e:
            logger.warning(f"Failed to add fund {code} to monitoring database: {e}")

        # 更新全局data.funds_loader.QDII_FUNDS
        from data.funds_loader import reload_funds
        reload_funds()

        return {"success": True, "message": "基金添加成功", "fund": new_fund}
        
    except Exception as e:
        logger.error(f"Failed to add fund {code}: {e}")
        raise HTTPException(status_code=500, detail=f"添加基金失败: {str(e)}")


@app.delete("/api/fund/{code}")
async def delete_fund(code: str):
    """从funds.json文件删除基金"""
    try:
        # 获取funds.json文件路径
        funds_file_path = Path(__file__).parent / "data" / "funds.json"

        # 读取现有数据
        with open(funds_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 检查基金是否存在
        existing_fund = next((f for f in data["funds"] if f["code"] == code), None)
        if not existing_fund:
            return {"success": False, "message": "基金不存在"}

        # 从funds.json中删除
        data["funds"] = [f for f in data["funds"] if f["code"] != code]

        # 保存到文件
        with open(funds_file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"Deleted fund {code} from funds.json")

        # 从监控数据库中删除
        try:
            from notifications.models import get_db, MonitoredFund
            session = get_db()
            try:
                monitored_fund = session.query(MonitoredFund).filter_by(fund_code=code).first()
                if monitored_fund:
                    session.delete(monitored_fund)
                    session.commit()
                    logger.info(f"Deleted fund {code} from monitoring database")
            finally:
                session.close()
        except Exception as e:
            logger.warning(f"Failed to delete fund {code} from monitoring database: {e}")

        # 更新全局data.funds_loader.QDII_FUNDS
        from data.funds_loader import reload_funds
        reload_funds()

        return {"success": True, "message": "基金删除成功"}

    except Exception as e:
        logger.error(f"Failed to delete fund {code}: {e}")
        raise HTTPException(status_code=500, detail=f"删除基金失败: {str(e)}")


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

    except Exception as e:
        logger.warning(f"Failed to fetch fund info from AKShare for {code}: {e}")

    # Fallback: Try to get fund name from Eastmoney for ETF/LOF funds
    try:
        eastmoney_url = f"https://fundf10.eastmoney.com/jjfl_{code}.html"
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(eastmoney_url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })

            if response.status_code == 200:
                html = response.text
                # Try to find fund name in the HTML
                # Look for title or meta tags with fund name
                import re
                title_match = re.search(r'<title>([^<]+?)</title>', html)
                if title_match:
                    title = title_match.group(1)
                    # Extract fund name from title
                    # Title format: "国泰纳斯达克100ETF(513100)基金费率 _ 基金档案 _ 天天基金网"
                    # We want: "国泰纳斯达克100ETF"

                    # Remove everything after first '_'
                    fund_name = title.split('_')[0].strip()

                    # Remove '(code)' suffix like (513100), (QDII), etc.
                    fund_name = re.sub(r'\([^)]*\)', '', fund_name).strip()

                    # Remove known suffixes
                    fund_name = fund_name.replace('基金净值', '').replace('基金费率', '').strip()

                    if fund_name and fund_name != f"基金{code}" and not fund_name.startswith('基金'):
                        logger.info(f"Found fund name from Eastmoney for {code}: {fund_name}")
                        return {"found": True, "code": code, "name": fund_name}

    except Exception as e:
        logger.warning(f"Failed to fetch fund info from Eastmoney for {code}: {e}")

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
            # 从data.funds_loader.QDII_FUNDS中查找，如果找不到则创建基本信息
            fund_info = next((f for f in data.funds_loader.QDII_FUNDS if f['code'] == code), None)
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
        funds_to_process = data.funds_loader.QDII_FUNDS
    
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
            "limitText": "—",
            "isWatchlisted": False,
            "oneYearChange": 0,
            "oneYearChangeAvailable": False
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
                    # Validate that the trading price (valuation) is reasonable
                    # If it's more than 50% different from NAV, it's likely bad data
                    price_diff_ratio = abs(valuation - nav) / nav
                    if price_diff_ratio > 0.5:
                        # Trading price is unreliable, reset it
                        funds_map[code]["valuation"] = 0
                        funds_map[code]["valuationRate"] = 0
                        funds_map[code]["premiumRate"] = 0
                    else:
                        premium_rate = ((valuation - nav) / nav) * 100
                        funds_map[code]["premiumRate"] = round(premium_rate, 2)

    funds = list(funds_map.values())

    # Add monitoring status to each fund
    from notifications.models import get_db, MonitoredFund
    session = get_db()
    try:
        monitored_funds = session.query(MonitoredFund).filter_by(enabled=True).all()
        monitored_codes = {mf.fund_code for mf in monitored_funds}

        for fund in funds:
            fund["isMonitorEnabled"] = fund["code"] in monitored_codes
    except Exception as e:
        logger.warning(f"Failed to fetch monitoring status: {e}")
        # Default to False if there's an error
        for fund in funds:
            fund["isMonitorEnabled"] = False
    finally:
        session.close()

    # Add 1-year percentage change data (use non-blocking approach for performance)
    for fund in funds:
        is_exchange_traded = fund.get("valuation", 0) > 0
        one_year_data = get_one_year_change(fund["code"], is_exchange_traded)
        fund["oneYearChange"] = one_year_data["percentage_change"]
        fund["oneYearChangeAvailable"] = one_year_data["available"]

    funds.sort(key=lambda x: (-x["marketPrice"] == 0, -x["premiumRate"]))

    return funds


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


# ============================================================================
# Market Indices API Endpoints
# ============================================================================

# Cache for market indices data
market_indices_cache = {
    "data": None,
    "timestamp": None,
    "cache_duration": 60  # 1 minute cache for real-time data
}

@app.get("/api/market-indices")
async def get_market_indices():
    """
    Get US market indices data (NASDAQ, S&P 500).

    Returns real-time data from Eastmoney API.
    Cached for 1 minute to reduce API calls while keeping data fresh.
    """
    import time
    import httpx

    current_time = time.time()

    # Check if we have valid cached data
    if (market_indices_cache["data"] is not None and
        market_indices_cache["timestamp"] is not None and
        current_time - market_indices_cache["timestamp"] < market_indices_cache["cache_duration"]):
        logger.debug("Using cached market indices data")
        return market_indices_cache["data"]

    # Initialize with fallback values
    nasdaq_data = {
        "name": "纳斯达克",
        "value": 23235.63,
        "change": 0.0
    }
    sp500_data = {
        "name": "标普500",
        "value": 6858.47,
        "change": 0.0
    }

    # Fetch real-time data from Eastmoney API
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Fetch NASDAQ (100.NDX) and S&P 500 (100.SPX) data
            url = "https://push2.eastmoney.com/api/qt/ulist.np/get?fltt=2&invt=2&fields=f12,f14,f2,f3&secids=100.NDX,100.SPX"

            response = await client.get(url, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            })

            if response.status_code == 200:
                data = response.json()

                if data.get('data') and data['data'].get('diff'):
                    for item in data['data']['diff']:
                        symbol = item.get('f12', '')
                        name = item.get('f14', '')
                        value = item.get('f2', 0)
                        change = item.get('f3', 0)

                        if symbol == 'NDX':
                            nasdaq_data = {
                                "name": name,
                                "value": round(value, 2),
                                "change": round(change, 2)
                            }
                        elif symbol == 'SPX':
                            sp500_data = {
                                "name": name,
                                "value": round(value, 2),
                                "change": round(change, 2)
                            }

                    logger.info(f"Successfully fetched market indices: NASDAQ {nasdaq_data['value']} ({nasdaq_data['change']:.2f}%), S&P 500 {sp500_data['value']} ({sp500_data['change']:.2f}%)")

    except Exception as e:
        logger.error(f"Error fetching market indices from Eastmoney: {e}")

    # Calculate fund statistics dynamically
    funds = await get_qdii_funds()
    total_funds = len(funds)
    exchange_traded = [f for f in funds if f.get("valuation", 0) > 0]
    exchange_traded_count = len(exchange_traded)

    # Calculate average premium rate (only for exchange-traded funds)
    premiums = [f.get("premiumRate", 0) for f in exchange_traded]
    avg_premium = round(sum(premiums) / len(premiums), 2) if premiums else 0

    logger.info(f"Fund statistics: {exchange_traded_count}/{total_funds} exchange-traded, avg premium: {avg_premium}%")

    # Build response
    response_data = {
        "nasdaq": nasdaq_data,
        "sp500": sp500_data,
        "avg_premium": avg_premium,
        "exchange_traded_count": exchange_traded_count,
        "total_funds": total_funds
    }

    # Cache the results
    market_indices_cache["data"] = response_data
    market_indices_cache["timestamp"] = current_time

    return response_data


# ============================================================================
# Trading Dates API Endpoints
# ============================================================================

@app.get("/api/trading-dates")
async def get_trading_dates(start_date: str = None, end_date: str = None):
    """
    Get Chinese stock market trading dates.

    Query parameters:
    - start_date: Start date in YYYYMMDD format (optional)
    - end_date: End date in YYYYMMDD format (optional)

    Returns trading calendar info including whether today is a trading day.
    """
    return get_chinese_stock_dates(start_date, end_date)


@app.get("/api/trading-dates/today")
async def check_today_trading():
    """Check if today is a Chinese stock trading day."""
    from datetime import datetime

    today = datetime.now().strftime('%Y-%m-%d')
    is_trading = is_trading_day(today)

    trading_info = get_chinese_stock_dates()

    return {
        "date": today,
        "is_trading_day": is_trading,
        "next_trading_day": trading_info.get('next_trading_day'),
        "previous_trading_day": trading_info.get('previous_trading_day')
    }


@app.get("/api/trading-dates/check/{date}")
async def check_specific_date(date: str):
    """
    Check if a specific date is a trading day.

    Path parameter:
    - date: Date in YYYY-MM-DD format
    """
    # Validate date format
    try:
        datetime.strptime(date, '%Y-%m-%d')
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    is_trading = is_trading_day(date)
    trading_info = get_chinese_stock_dates()

    return {
        "date": date,
        "is_trading_day": is_trading,
        "in_trading_calendar": date in trading_info.get('trading_dates', [])
    }


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


class ConfigValueModel(BaseModel):
    value: str


@app.post("/api/notifications/config/{config_key}")
async def update_config_value(config_key: str, data: ConfigValueModel):
    """Update a single configuration value."""
    session = get_db()
    try:
        existing = session.query(NotificationConfig).filter_by(config_key=config_key).first()
        if existing:
            existing.config_value = data.value
        else:
            new_config = NotificationConfig(config_key=config_key, config_value=data.value)
            session.add(new_config)

        session.commit()

        # Reload monitor configuration
        monitor._load_config()

        logger.info(f"Config updated: {config_key} = {data.value}")
        return {"status": "success", "config_key": config_key, "value": data.value}

    except Exception as e:
        session.rollback()
        logger.error(f"Failed to update config value: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@app.post("/api/notifications/config/alert_time_period")
async def update_alert_time_period(data: ConfigValueModel):
    """Update alert time period configuration."""
    return await update_config_value("alert_time_period", data)


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
        save_recipients_to_file()  # Save to config file
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
        save_recipients_to_file()  # Save to config file
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


@app.post("/api/notifications/monitoring/toggle")
async def toggle_monitoring():
    """Toggle monitoring enabled/disabled via config."""
    from notifications.models import get_db, NotificationConfig

    session = get_db()
    try:
        # Get current value
        config = session.query(NotificationConfig).filter_by(config_key='monitoring_enabled').first()

        if not config:
            # Create if doesn't exist
            new_config = NotificationConfig(config_key='monitoring_enabled', config_value='true')
            session.add(new_config)
            session.commit()
            new_value = 'true'
        else:
            # Toggle value
            current_value = config.config_value.lower()
            new_value = 'false' if current_value == 'true' else 'true'
            config.config_value = new_value
            session.commit()

        return {
            "status": "success",
            "monitoring_enabled": new_value == 'true',
            "message": f"Monitoring {'enabled' if new_value == 'true' else 'disabled'}"
        }
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@app.get("/api/notifications/monitoring/config")
async def get_monitoring_config():
    """Get monitoring configuration."""
    from notifications.models import get_db, NotificationConfig

    session = get_db()
    try:
        configs = session.query(NotificationConfig).filter(
            NotificationConfig.config_key.in_([
                'monitoring_enabled',
                'smtp_enabled',
                'check_interval_seconds',
                'alert_time_period'
            ])
        ).all()

        config_dict = {c.config_key: c.config_value for c in configs}
        return config_dict
    finally:
        session.close()


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


class FundMonitoringModel(BaseModel):
    """Model for individual fund monitoring toggle."""
    enabled: bool


@app.get("/api/notifications/monitored-funds/{fund_code}")
async def get_fund_monitoring_status(fund_code: str):
    """Get monitoring status for a specific fund."""
    from notifications.models import get_db, MonitoredFund

    session = get_db()
    try:
        monitored = session.query(MonitoredFund).filter_by(fund_code=fund_code).first()
        if monitored:
            return {"fund_code": fund_code, "enabled": monitored.enabled}
        else:
            # Fund not in database, default to not monitored
            return {"fund_code": fund_code, "enabled": False}
    except Exception as e:
        logger.error(f"Failed to get fund monitoring status: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@app.put("/api/notifications/monitored-funds/{fund_code}")
async def update_fund_monitoring_status(fund_code: str, data: FundMonitoringModel):
    """Update monitoring status for a specific fund."""
    from notifications.models import get_db, MonitoredFund

    session = get_db()
    try:
        if data.enabled:
            # Enable monitoring - use merge to handle duplicates
            monitored = MonitoredFund(fund_code=fund_code, enabled=True)
            session.merge(monitored)
            logger.info(f"Enabled monitoring for fund {fund_code}")
        else:
            # Disable monitoring - delete from database
            monitored = session.query(MonitoredFund).filter_by(fund_code=fund_code).first()
            if monitored:
                session.delete(monitored)
                logger.info(f"Disabled monitoring for fund {fund_code}")

        session.commit()
        return {"fund_code": fund_code, "enabled": data.enabled}

    except Exception as e:
        session.rollback()
        logger.error(f"Failed to update fund monitoring status: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@app.post("/api/notifications/test-triggers")
async def test_triggers():
    """Test triggers by manually checking current fund data against triggers and sending emails."""
    from notifications.models import get_db, FundTrigger, MonitoredFund, EmailRecipient
    from notifications.state_tracker import StateTracker
    from notifications.email_service import EmailService

    try:
        # Fetch current fund data
        funds = await get_qdii_funds()

        # Get monitored funds
        session = get_db()
        monitored_funds = session.query(MonitoredFund).filter_by(enabled=True).all()
        monitored_codes = {f.fund_code for f in monitored_funds}
        session.close()

        # Filter to monitored funds
        monitored_funds_list = [f for f in funds if f.get('id') in monitored_codes]

        # Get triggers for monitored funds
        session = get_db()
        triggers = session.query(FundTrigger).filter(
            FundTrigger.fund_code.in_(monitored_codes),
            FundTrigger.enabled == True
        ).all()
        session.close()

        # Get active recipients
        session = get_db()
        recipients = session.query(EmailRecipient).filter_by(is_active=True).all()
        recipient_emails = [r.email for r in recipients]
        session.close()

        tracker = StateTracker()
        email_service = EmailService()
        email_service._load_config()

        results = []
        emails_sent = 0

        # Check each monitored fund
        for fund in monitored_funds_list:
            fund_code = fund.get('id')
            fund_name = fund.get('name')
            premium_rate = fund.get('premiumRate', 0)
            market_price = fund.get('marketPrice', 0)
            nav = fund.get('valuation', 0)
            limit_text = fund.get('limitText', '')

            # Get custom thresholds for this fund
            fund_triggers = [t for t in triggers if t.fund_code == fund_code]

            for trigger in fund_triggers:
                if trigger.trigger_type in ['premium_high', 'premium_low']:
                    threshold = trigger.threshold_value

                    # Check if threshold is breached
                    would_trigger = False
                    if trigger.trigger_type == 'premium_high' and premium_rate > threshold:
                        would_trigger = True
                    elif trigger.trigger_type == 'premium_low' and premium_rate < threshold:
                        would_trigger = True

                    results.append({
                        'fund_code': fund_code,
                        'fund_name': fund_name,
                        'trigger_type': trigger.trigger_type,
                        'threshold': threshold,
                        'current_value': premium_rate,
                        'would_trigger': would_trigger,
                        'market_price': market_price,
                        'nav': nav
                    })

                    # Send email if triggered
                    if would_trigger and recipient_emails:
                        # Use old_rate = 0 for test emails
                        success = await email_service.send_premium_alert(
                            fund_code=fund_code,
                            fund_name=fund_name,
                            old_rate=0.0,
                            new_rate=premium_rate,
                            market_price=market_price,
                            nav=nav,
                            limit_text=limit_text,
                            recipients=recipient_emails
                        )
                        if success:
                            emails_sent += 1
                            logger.info(f"Test trigger email sent for {fund_code} ({trigger.trigger_type})")

        return {
            'test_results': results,
            'total_triggers_tested': len(results),
            'would_fire': len([r for r in results if r['would_trigger']]),
            'emails_sent': emails_sent
        }

    except Exception as e:
        logger.error(f"Failed to test triggers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Fund Triggers Management (User-defined thresholds per fund)
# ============================================================================

class FundTriggerModel(BaseModel):
    """Model for fund trigger configuration."""
    fund_code: Optional[str] = None  # Optional, will use path parameter if not provided
    trigger_type: str  # 'premium_high', 'premium_low'
    threshold_value: Optional[float] = None  # Optional for limit_change triggers
    enabled: bool = True


@app.get("/api/notifications/funds/{fund_code}/triggers")
async def get_fund_triggers(fund_code: str):
    """Get all triggers for a specific fund."""
    from notifications.models import get_db, FundTrigger

    session = get_db()
    try:
        # Get all triggers, not just enabled ones
        triggers = session.query(FundTrigger).filter_by(
            fund_code=fund_code
        ).all()

        return [
            {
                'id': t.id,
                'fund_code': t.fund_code,
                'trigger_type': t.trigger_type,
                'threshold_value': t.threshold_value,
                'enabled': t.enabled
            }
            for t in triggers
        ]

    except Exception as e:
        logger.error(f"Failed to get triggers for {fund_code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@app.post("/api/notifications/funds/{fund_code}/triggers")
async def create_fund_trigger(fund_code: str, trigger: FundTriggerModel):
    """Create a new trigger for a fund. If trigger type exists, update it."""
    from notifications.models import get_db, FundTrigger

    session = get_db()
    try:
        # Check if trigger of this type already exists
        existing = session.query(FundTrigger).filter_by(
            fund_code=fund_code,
            trigger_type=trigger.trigger_type
        ).first()

        if existing:
            # Update existing trigger
            existing.threshold_value = trigger.threshold_value
            existing.enabled = trigger.enabled
            session.commit()
            logger.info(f"Updated trigger for {fund_code}: {trigger.trigger_type} @ {trigger.threshold_value}")
            return {"status": "updated", "id": existing.id}
        else:
            # Create new trigger
            new_trigger = FundTrigger(
                fund_code=fund_code,
                trigger_type=trigger.trigger_type,
                threshold_value=trigger.threshold_value,
                enabled=trigger.enabled
            )
            session.add(new_trigger)
            session.commit()
            logger.info(f"Created trigger for {fund_code}: {trigger.trigger_type} @ {trigger.threshold_value}")
            return {"status": "created", "id": new_trigger.id}

    except Exception as e:
        session.rollback()
        logger.error(f"Failed to create trigger: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@app.put("/api/notifications/funds/{fund_code}/triggers/{trigger_id}")
async def update_fund_trigger(fund_code: str, trigger_id: int, trigger: FundTriggerModel):
    """Update an existing trigger."""
    from notifications.models import get_db, FundTrigger

    session = get_db()
    try:
        existing = session.query(FundTrigger).filter_by(id=trigger_id, fund_code=fund_code).first()
        if not existing:
            raise HTTPException(status_code=404, detail="Trigger not found")

        existing.trigger_type = trigger.trigger_type
        existing.threshold_value = trigger.threshold_value
        existing.enabled = trigger.enabled
        existing.updated_at = datetime.utcnow()

        session.commit()
        logger.info(f"Updated trigger {trigger_id} for {fund_code}")
        return {"status": "success"}

    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to update trigger: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@app.delete("/api/notifications/funds/{fund_code}/triggers/{trigger_id}")
async def delete_fund_trigger(fund_code: str, trigger_id: int):
    """Delete a trigger."""
    from notifications.models import get_db, FundTrigger

    session = get_db()
    try:
        trigger = session.query(FundTrigger).filter_by(id=trigger_id, fund_code=fund_code).first()
        if not trigger:
            raise HTTPException(status_code=404, detail="Trigger not found")

        session.delete(trigger)
        session.commit()

        logger.info(f"Deleted trigger {trigger_id} for {fund_code}")
        return {"status": "success"}

    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to delete trigger: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@app.get("/api/notifications/triggers")
async def get_all_triggers():
    """Get all triggers for all funds."""
    from notifications.models import get_db, FundTrigger

    session = get_db()
    try:
        triggers = session.query(FundTrigger).filter_by(enabled=True).all()

        # Group by fund_code
        result = {}
        for t in triggers:
            if t.fund_code not in result:
                result[t.fund_code] = []
            result[t.fund_code].append({
                'id': t.id,
                'trigger_type': t.trigger_type,
                'threshold_value': t.threshold_value
            })

        return result

    except Exception as e:
        logger.error(f"Failed to get all triggers: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


def load_server_config():
    """Load server configuration from funds.json"""
    try:
        funds_file_path = Path(__file__).parent / "data" / "funds.json"
        with open(funds_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        server_config = data.get("config", {}).get("server", {})
        host = server_config.get("host", "127.0.0.1")
        port = server_config.get("port", 8000)

        logger.info(f"Loaded server config: host={host}, port={port}")
        return host, port
    except Exception as e:
        logger.warning(f"Failed to load server config, using defaults: {e}")
        return "127.0.0.1", 8000


if __name__ == "__main__":
    import uvicorn

    host, port = load_server_config()
    uvicorn.run(app, host=host, port=port)
