# QDII Fund Radar - Configuration Guide

This guide explains how to configure the QDII Fund Radar application.

## Table of Contents

1. [Server Configuration](#server-configuration)
2. [API Configuration](#api-configuration)
3. [Proxy Configuration](#proxy-configuration)
4. [Email Notifications](#email-notifications)
5. [Monitoring Configuration](#monitoring-configuration)

---

## Server Configuration

The server host and port can be configured in `data/funds.json`.

### Configuration File

Edit `data/funds.json`:

```json
{
  "config": {
    "server": {
      "host": "127.0.0.1",
      "port": 8000
    }
  }
}
```

### Changing the Port

To run the backend on a different port:

1. Edit `data/funds.json`
2. Change the `port` value
3. Restart the server

**Example - Run on port 9000:**

```json
{
  "config": {
    "server": {
      "host": "0.0.0.0",
      "port": 9000
    }
  }
}
```

**Important:** If you change the port, you must also update:
- The `api.backendUrl` in `data/funds.json`
- Frontend API calls (if running frontend separately)
- Nginx proxy configuration (if using Nginx)

### External Network Access

To make the server accessible from other machines:

```json
{
  "config": {
    "server": {
      "host": "0.0.0.0",
      "port": 8000
    }
  }
}
```

**Security Warning:** Only bind to `0.0.0.0` if you're behind a firewall or using Nginx as a reverse proxy.

---

## API Configuration

API settings control how the backend fetches fund data.

### Configuration File: `data/funds.json`

```json
{
  "config": {
    "api": {
      "backendUrl": "http://127.0.0.1:8000/api/funds",
      "requestTimeout": 20000,
      "userAgent": "Mozilla/5.0 ..."
    }
  }
}
```

### Settings

- **`backendUrl`**: Base URL for the backend API (used by frontend)
- **`requestTimeout`**: Request timeout in milliseconds (default: 20000)
- **`userAgent`**: User agent string for HTTP requests

### Data Source URLs

```json
{
  "config": {
    "dataSourceUrls": {
      "eastmoneyApi": "https://push2.eastmoney.com/api/qt/ulist.np/get",
      "fundDetail": "https://fundf10.eastmoney.com/jjfl_{code}.html"
    }
  }
}
```

**Warning:** Do not change these URLs unless you know what you're doing.

---

## Proxy Configuration

The application supports proxy configuration for fetching fund data through CORS proxies.

### Configuration File: `data/funds.json`

```json
{
  "config": {
    "proxy": [
      {
        "name": "AllOrigins",
        "urlTemplate": "https://api.allorigins.win/raw?url={url}"
      },
      {
        "name": "CodeTabs",
        "urlTemplate": "https://api.codetabs.com/v1/proxy?quest={url}"
      }
    ]
  }
}
```

### Adding Custom Proxies

To add a custom proxy:

```json
{
  "config": {
    "proxy": [
      {
        "name": "MyProxy",
        "urlTemplate": "https://my-proxy.com/proxy?url={url}"
      }
    ]
  }
}
```

The `{url}` placeholder will be replaced with the target URL.

### Request Settings

```json
{
  "config": {
    "request": {
      "proxyTimeout": 3000,
      "chunkSize": 20,
      "scriptTimeout": 4000
    }
  }
}
```

- **`proxyTimeout`**: Proxy request timeout in milliseconds
- **`chunkSize`**: Number of funds to fetch per request
- **`scriptTimeout`**: Script execution timeout

---

## Email Notifications

Email notifications are configured in the `config/` directory.

### SMTP Configuration

Create `config/smtp.json`:

```json
{
  "host": "smtp.gmail.com",
  "port": 587,
  "username": "your-email@gmail.com",
  "password": "your-app-password",
  "from_email": "your-email@gmail.com",
  "use_tls": true
}
```

### Common SMTP Providers

**Gmail:**
```json
{
  "host": "smtp.gmail.com",
  "port": 587,
  "use_tls": true
}
```

**Outlook/Office365:**
```json
{
  "host": "smtp-mail.outlook.com",
  "port": 587,
  "use_tls": true
}
```

**Amazon SES:**
```json
{
  "host": "email-smtp.us-east-1.amazonaws.com",
  "port": 587,
  "use_tls": true
}
```

### Recipients Configuration

Create `config/recipients.json`:

```json
[
  {
    "email": "user1@example.com",
    "active": true
  },
  {
    "email": "user2@example.com",
    "active": true
  }
]
```

Set `"active": false` to temporarily disable a recipient.

### Testing Email Configuration

```bash
# Send test email
curl -X POST http://127.0.0.1:8000/api/notifications/test-email
```

---

## Monitoring Configuration

Monitoring settings are stored in the SQLite database (`data/notifications.db` and can be configured via the web UI or API.

### Configuration Keys

- **`premium_threshold_high`**: Default premium rate threshold (default: 5.0%)
- **`debounce_minutes`**: Minimum time between same alerts (default: 1 minute)
- **`check_interval_seconds`**: Monitoring check interval (default: 180 seconds)
- **`alert_time_period`**: "all_day" or "trading_hours"
- **`monitoring_enabled`**: Master monitoring switch (true/false)
- **`smtp_enabled`**: Email notifications switch (true/false)

### Updating Configuration via API

```bash
# Update premium threshold
curl -X POST http://127.0.0.1:8000/api/notifications/config/premium_threshold_high \
  -H "Content-Type: application/json" \
  -d '{"value": 10.0}'

# Update check interval
curl -X POST http://127.0.0.1:8000/api/notifications/config/check_interval_seconds \
  -H "Content-Type: application/json" \
  -d '{"value": 300}'
```

### Trading Hours

When `alert_time_period` is set to `"trading_hours"`, alerts are only sent during:
- **Days**: Monday to Friday (excluding holidays)
- **Hours**: 9:30 - 15:00 Beijing Time (UTC+8)

The system uses the `is_trading_day()` function to exclude weekends and holidays.

---

## Environment Variables (Optional)

You can also use environment variables for configuration. Create a `.env` file in the project root:

```bash
# Server
QDII_HOST=127.0.0.1
QDII_PORT=8000

# Email
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
```

Then modify `server.py` to load these variables (this feature is planned for future versions).

---

## Configuration File Priority

1. **Database configuration** (highest priority) - runtime settings
2. **`data/funds.json`** - application settings
3. **`config/*.json`** - email and recipients
4. **Environment variables** - (future feature)
5. **Default values** - hardcoded fallbacks

---

## Troubleshooting

### Server Won't Start on New Port

```bash
# Check if port is in use
lsof -i :PORT

# Kill process using the port
lsof -ti:PORT | xargs kill -9

# Check server logs
tail -f /tmp/server_fixed.log
```

### Configuration Not Loading

```bash
# Verify JSON syntax
python3 -m json.tool data/funds.json

# Check file permissions
ls -la data/funds.json

# Restart server
lsof -ti:8000 | xargs kill -9
python3 server.py
```

### Email Not Sending

```bash
# Verify SMTP config
cat config/smtp.json

# Check recipients
cat config/recipients.json

# Send test email
curl -X POST http://127.0.0.1:8000/api/notifications/test-email

# Check database for config
sqlite3 data/notifications.db "SELECT * FROM notification_config WHERE key LIKE 'smtp%';"
```

---

## Security Best Practices

1. **Never commit `config/smtp.json`** to version control (contains passwords)
2. **Use app-specific passwords** for Gmail, not your main password
3. **Restrict file permissions**:
   ```bash
   chmod 600 config/smtp.json
   chmod 600 config/recipients.json
   ```
4. **Use environment variables** in production for sensitive data
5. **Don't bind to 0.0.0.0** unless behind a firewall/Nginx
6. **Use HTTPS** in production (Let's Encrypt with Nginx)

---

## Example Configurations

### Development Setup

```json
{
  "config": {
    "server": {
      "host": "127.0.0.1",
      "port": 8000
    },
    "api": {
      "backendUrl": "http://127.0.0.1:8000/api/funds",
      "requestTimeout": 20000
    }
  }
}
```

### Production Setup (with Nginx)

```json
{
  "config": {
    "server": {
      "host": "127.0.0.1",
      "port": 8000
    },
    "api": {
      "backendUrl": "/api/funds",
      "requestTimeout": 30000
    }
  }
}
```

Nginx handles SSL and reverse proxy, backend stays on localhost.

### Docker Setup

```json
{
  "config": {
    "server": {
      "host": "0.0.0.0",
      "port": 8000
    }
  }
}
```

Bind to all interfaces for Docker networking.

---

## Need Help?

- **Documentation**: See `DEPLOYMENT.md` for deployment guide
- **Architecture**: See `CLAUDE.md` for technical details
- **Issues**: https://github.com/cjb2003425/qdii_radar/issues

---

**Last Updated**: 2025-12-30
**Version**: 1.0
