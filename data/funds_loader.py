import json
from pathlib import Path
from typing import List, Dict, Any

# Load data from JSON file
DATA_FILE = Path(__file__).parent / 'funds.json'

def load_funds_data() -> Dict[str, Any]:
    """Load funds data from JSON file"""
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

# Load data once at module import
_funds_data = load_funds_data()

# Extract funds list
QDII_FUNDS = _funds_data['funds']

# Extract API config
API_CONFIG = {
    "USER_AGENT": _funds_data['config']['api']['userAgent'],
    "REQUEST_TIMEOUT": _funds_data['config']['api']['requestTimeout'],
    "CHUNK_SIZE": _funds_data['config']['request']['chunkSize'],
}

# Extract data source URLs
DATA_SOURCE_URLS = _funds_data['config']['dataSourceUrls']


def reload_funds():
    """重新加载基金数据，用于在添加新基金后更新全局变量"""
    global QDII_FUNDS
    _funds_data = load_funds_data()
    QDII_FUNDS = _funds_data['funds']