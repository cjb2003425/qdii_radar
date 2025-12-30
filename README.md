# QDII Fund Radar (QDII基金雷达)

<div align="center">
  <h3>实时追踪中国QDII基金净值、溢价率和申购限制</h3>
  <p>Real-time tracking of Chinese QDII fund NAV, premium rates, and purchase limits</p>
</div>

## ✨ Features

- **📊 Real-time Fund Data**
  - Live NAV (Net Asset Value) updates from Eastmoney API
  - Premium/Discount rate calculation
  - Purchase limit tracking (限购/暂停/开放)
  - Support for 24+ NASDAQ-focused QDII funds

- **🔔 Smart Monitoring & Alerts**
  - Premium rate threshold alerts (溢价率警报)
  - Purchase limit change notifications (限制变更通知)
  - Configurable trading hours alerts (交易时间提醒)
  - Email notifications via SMTP/SES
  - Debounce mechanism to prevent spam

- **⚙️ Flexible Configuration**
  - Per-fund trigger customization
  - Alert time period selection (全天/交易时间)
  - Trading day awareness (excludes weekends & holidays)
  - Database-backed persistence

- **🎯 User-Friendly Interface**
  - Responsive design (mobile & desktop)
  - Real-time status indicators
  - One-click monitoring toggle
  - Fund watchlist management
  - Custom fund addition

## 🏗️ Architecture

```
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│                 │      │                 │      │                 │
│  React Frontend │◄────►│  FastAPI Backend │◄────►│  Data Sources   │
│  (TypeScript)   │      │  (Python)       │      │  (AKShare,      │
│  Port: 3002     │      │  Port: 8000     │      │   Eastmoney)    │
│                 │      │                 │      │                 │
└─────────────────┘      └─────────────────┘      └─────────────────┘
                                 │
                                 ▼
                        ┌─────────────────┐
                        │  SQLite Database │
                        │  (Triggers,      │
                        │   Config,        │
                        │   History)       │
                        └─────────────────┘
```

### Components

**Backend (`server.py`)**
- FastAPI application with async support
- AKShare integration for comprehensive NAV data
- Eastmoney API for real-time quotes and purchase limits
- Background monitoring with asyncio
- SQLite database for configuration and history

**Frontend (React + TypeScript)**
- Vite for fast development
- Tailwind CSS for styling
- Headless UI components
- Real-time data fetching and display

## 📋 Prerequisites

- **Python 3.8+**
  ```bash
  python3 --version
  ```
- **Node.js 18+**
  ```bash
  node --version
  npm --version
  ```
- **SQLite 3** (usually included with Python)

## 🚀 Installation

### 1. Clone the Repository

```bash
git clone https://github.com/cjb2003425/qdii_radar.git
cd qdii_radar
```

### 2. Backend Setup

```bash
# Install Python dependencies
pip3 install -r requirements.txt

# Verify installation
python3 -c "import fastapi, akshare; print('✓ Dependencies installed')"
```

### 3. Frontend Setup

```bash
# Install Node dependencies
npm install

# Verify installation
npm run build
```

### 4. Configuration (Optional)

Configure SMTP for email notifications:

```bash
mkdir -p config
cat > config/smtp.json << EOF
{
  "host": "smtp.gmail.com",
  "port": 587,
  "username": "your-email@gmail.com",
  "password": "your-app-password",
  "from_email": "your-email@gmail.com",
  "use_tls": true
}
EOF

cat > config/recipients.json << EOF
[
  {
    "email": "recipient@example.com",
    "active": true
  }
]
EOF
```

## 🎮 Usage

### Start the Backend

```bash
python3 server.py
```

Backend will start at http://127.0.0.1:8000

### Start the Frontend

```bash
npm run dev
```

Frontend will start at http://localhost:3002

### Access the Application

Open your browser and navigate to:
```
http://localhost:3002
```

## 📖 API Endpoints

### Fund Data

- `GET /api/funds` - Get all fund data
- `GET /api/funds?codes=161226,160216` - Get specific funds
- `POST /api/fund` - Add a new fund
- `GET /api/fund/{code}` - Get fund info by code
- `DELETE /api/fund/{code}` - Delete a fund

### Monitoring Control

- `GET /api/notifications/monitoring/status` - Get monitoring status
- `POST /api/notifications/monitoring/toggle` - Start/stop monitoring
- `GET /api/notifications/monitoring/config` - Get monitoring configuration
- `POST /api/notifications/config/{key}` - Update configuration

### Trigger Management

- `GET /api/notifications/funds/{code}/triggers` - Get fund triggers
- `POST /api/notifications/funds/{code}/triggers` - Create/update trigger
- `PUT /api/notifications/funds/{code}/triggers/{id}` - Update trigger
- `DELETE /api/notifications/funds/{code}/triggers/{id}` - Delete trigger

### Monitored Funds

- `GET /api/notifications/monitored-funds` - Get monitored funds list
- `POST /api/notifications/monitored-funds` - Update monitored funds list

### Notifications

- `GET /api/notifications/history` - Get notification history
- `GET /api/notifications/stats` - Get notification statistics
- `POST /api/notifications/test-email` - Send test email

## ⚙️ Configuration

### Database Schema

**`fund_triggers`** - Trigger configurations
- `fund_code` - Fund code
- `trigger_type` - premium_high or limit_change
- `threshold_value` - Premium rate threshold (e.g., 5.0 for 5%)
- `enabled` - Active status

**`notification_config`** - System settings
- `premium_threshold_high` - Default premium threshold (default: 5.0%)
- `debounce_minutes` - Minimum time between same alerts (default: 1 minute)
- `check_interval_seconds` - Monitoring check interval (default: 180 seconds)
- `alert_time_period` - all_day or trading_hours
- `monitoring_enabled` - Master monitoring switch
- `smtp_enabled` - Email notifications switch

**`monitored_funds`** - Funds to monitor
- `fund_code` - Fund code
- `enabled` - Monitoring status

**`notification_history`** - Alert history
- `fund_code`, `fund_name`, `alert_type`
- `old_value`, `new_value`
- `sent_at`, `recipient_email`

### Alert Types

**1. Premium Rate Alert (溢价率警报)**
- Triggers when fund premium rate exceeds threshold
- Email includes: fund name, premium rate, market price, NAV, threshold
- Requires `premium_high` trigger enabled for the fund

**2. Limit Change Alert (限制变更通知)**
- Triggers when purchase limit changes
- Email includes: fund name, old limit, new limit
- Requires `limit_change` trigger enabled for the fund
- **Skips**: Transitions to/from "暂停" (suspended status)

### Time Period Options

**全天 (All Day)**
- Alerts sent 24/7
- No time restrictions

**交易时间 (Trading Hours)**
- Alerts only sent during:
  - Trading days (excludes weekends & holidays)
  - 9:30-15:00 Beijing time (UTC+8)
- Uses `is_trading_day()` function for holiday detection

## 🔧 Development

### Project Structure

```
qdii_radar/
├── server.py                 # FastAPI backend
├── requirements.txt          # Python dependencies
├── components/               # React components
│   ├── FundList.tsx         # Fund list with triggers
│   ├── FundRow.tsx          # Individual fund row
│   ├── MonitoringControl.tsx # Monitoring controls
│   ├── FundManager.tsx      # Add/remove funds
│   ├── FundTriggerSettings.tsx # Trigger configuration
│   └── ...
├── services/                 # Frontend services
│   ├── fundService.ts       # Fund data fetching
│   └── notificationService.ts # Notification API calls
├── notifications/            # Notification system
│   ├── models.py            # Database models
│   ├── state_tracker.py     # Change detection
│   ├── monitor.py           # Background monitoring
│   └── email_service.py     # Email sending
├── data/                     # Data files
│   ├── funds.json           # Fund list
│   └── notifications.db     # SQLite database
└── config/                   # Configuration files
    ├── smtp.json            # SMTP settings
    └── recipients.json      # Email recipients
```

### Backend Management

```bash
# Check backend health
curl http://127.0.0.1:8000/health

# View all funds
curl http://127.0.0.1:8000/api/funds

# View monitoring status
curl http://127.0.0.1:8000/api/notifications/monitoring/status

# View notification history
curl http://127.0.0.1:8000/api/notifications/history
```

### Frontend Development

```bash
# Development server (port 3002)
npm run dev

# Production build
npm run build

# Preview production build
npm run preview
```

### Database Operations

```bash
# Access SQLite database
sqlite3 data/notifications.db

# View triggers
SELECT fund_code, trigger_type, threshold_value, enabled
FROM fund_triggers
ORDER BY fund_code, trigger_type;

# View notification history
SELECT * FROM notification_history
ORDER BY sent_at DESC
LIMIT 20;

# View configuration
SELECT * FROM notification_config;
```

## 📊 Monitored Funds

Current preset funds include:

| Code | Name | Type |
|------|------|------|
| 015299 | 招商国证生物医药指数 | LOF |
| 019547 | 广发纳斯达克100指数A | QDII |
| 018043 | 华安纳斯达克100ETF联接A | QDII |
| 160213 | 国泰纳指100 | LOF |
| 270042 | 广发纳斯达克100ETF联接A | QDII |
| 000834 | 大成纳斯达克100 | QDII |
| 040046 | 华安纳斯达克100ETF联接C | QDII |
| 019441 | 嘉实纳斯达克100ETF联接A | QDII |
| 019442 | 嘉实纳斯达克100ETF联接C | QDII |
| 019172 | 汇添富纳斯达克100ETF联接A | QDII |
| 002732 | 广发纳斯达克100指数A | QDII |
| 161130 | 纳指生物科技ETF | LOF |
| 017436 | 华安纳斯达克100ETF联接A | QDII |
| 007280 | 广发纳斯达克100指数A | QDII |
| 008763 | 广发纳斯达克100指数A | QDII |
| 006105 | 华夏纳斯达克100ETF联接A | QDII |
| 006282 | 广发纳斯达克100指数 | QDII |
| 020712 | 广发纳斯达克100指数 | QDII |
| 021190 | 广发纳斯达克100指数A | QDII |
| 021189 | 华安纳斯达克100ETF联接A | QDII |
| 012870 | 华安纳斯达克100ETF联接A | QDII |
| 160216 | 纳斯达克100 | LOF |
| 161226 | 国投瑞银白银期货(LOF)A | LOF |
| 164701 | 汇添富纳斯达克100ETF联接A | QDII |

## 🐛 Troubleshooting

### Backend Issues

**Port 8000 already in use:**
```bash
lsof -ti:8000 | xargs kill -9
python3 server.py
```

**Database locked:**
```bash
rm data/notifications.db
python3 server.py  # Will recreate database
```

### Frontend Issues

**Port 3002 already in use:**
```bash
lsof -ti:3002 | xargs kill -9
npm run dev
```

**Build errors:**
```bash
rm -rf node_modules dist
npm install
npm run build
```

### No Email Received

1. Check SMTP configuration: `cat config/smtp.json`
2. Verify recipients: `cat config/recipients.json`
3. Check if monitoring is enabled in UI
4. Verify fund has triggers configured
5. Check database: `sqlite3 data/notifications.db "SELECT * FROM notification_history ORDER BY sent_at DESC LIMIT 10;"`

## 📝 License

MIT License

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📧 Contact

For issues and questions, please open an issue on GitHub.

---

**Built with ❤️ using FastAPI, React, and Tailwind CSS**
