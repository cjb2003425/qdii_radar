# QDII Fund Radar - Simple Deployment Guide

This guide helps you deploy QDII Fund Radar using your current user and home directory.

**Prerequisites**:
- Ubuntu 20.04 or 22.04 LTS server
- SSH access with sudo privileges
- Domain name pointed to your server (optional)

---

## STEP 1: Install System Dependencies

```bash
# Update package lists
sudo apt update

# Install required packages
sudo apt install -y python3 python3-pip python3-venv nodejs npm nginx sqlite3 curl ufw
```

**Verify installations**:
```bash
python3 --version  # Should be 3.8+
node --version     # Should be 18+
```

---

## STEP 2: Setup Application Directory

Use your home directory for deployment:

```bash
# Create application directory in your home
mkdir -p ~/qdii-radar
cd ~/qdii-radar
```

---

## STEP 3: Deploy Application Files

**Option A: Clone from GitHub**

```bash
cd ~/qdii-radar
git clone https://github.com/cjb2003425/qdii_radar.git .
```

**Option B: Upload from Local Machine**

On your local machine:
```bash
# Upload files to server
rsync -av \
  --exclude='node_modules' \
  --exclude='venv' \
  --exclude='dist' \
  --exclude='.git' \
  ./ user@your-server-ip:~/qdii-radar/
```

---

## STEP 4: Setup Python Backend

```bash
# Navigate to application directory
cd ~/qdii-radar

# Create Python virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

**Verify installation**:
```bash
python -c "import fastapi, akshare; print('✓ Dependencies OK')"
```

Deactivate when done:
```bash
deactivate
```

---

## STEP 5: Build Frontend

```bash
# Still in ~/qdii-radar
cd ~/qdii-radar

# Install Node dependencies
npm install

# Build for production
npm run build
```

**Verify build**:
```bash
ls -lh dist/
```

---

## STEP 6: Configure Application

Edit configuration for your setup:

```bash
cd ~/qdii-radar
vim data/funds.json
```

**Update the config section**:

```json
{
  "config": {
    "server": {
      "host": "127.0.0.1",
      "port": 8088
    },
    "api": {
      "backendUrl": "/api/funds",
      "requestTimeout": 20000
    }
  }
}
```

---

## STEP 7: Create Systemd Service

Create service file:

```bash
sudo vim /etc/systemd/system/qdii-radar-backend.service
```

**Replace YOUR_USERNAME with your actual username** and paste:

```ini
[Unit]
Description=QDII Fund Radar Backend Service
After=network.target

[Service]
Type=simple
User=YOUR_USERNAME
Group=YOUR_USERNAME
WorkingDirectory=/home/YOUR_USERNAME/qdii-radar
Environment="PATH=/home/YOUR_USERNAME/qdii-radar/venv/bin"
ExecStart=/home/YOUR_USERNAME/qdii-radar/venv/bin/python3 /home/YOUR_USERNAME/qdii-radar/server.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# Security
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

**Get your username**:
```bash
whoami
```

**Example for user 'john'**:
```ini
User=john
Group=john
WorkingDirectory=/home/john/qdii-radar
Environment="PATH=/home/john/qdii-radar/venv/bin"
ExecStart=/home/john/qdii-radar/venv/bin/python3 /home/john/qdii-radar/server.py
```

**Save and exit** (`:wq`)

Reload systemd:
```bash
sudo systemctl daemon-reload
```

---

## STEP 8: Configure Nginx

Create nginx configuration:

```bash
sudo vim /etc/nginx/sites-available/qdii-radar
```

**Replace YOUR_USERNAME and your-domain.com**:

```nginx
server {
    listen 80;
    server_name your-domain.com;  # Replace with your domain or IP

    # Logging
    access_log /var/log/nginx/qdii-radar-access.log;
    error_log /var/log/nginx/qdii-radar-error.log;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Backend API proxy
    location /api/ {
        proxy_pass http://127.0.0.1:8088;
        proxy_http_version 1.1;

        # Headers
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;

        # Disable buffering
        proxy_buffering off;
    }

    # Health check endpoint
    location /health {
        proxy_pass http://127.0.0.1:8088/health;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        access_log off;
    }

    # Frontend static files
    location / {
        root /home/YOUR_USERNAME/qdii-radar/dist;
        try_files $uri $uri/ /index.html;

        # Cache static assets
        location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
    }
}
```

**Enable the site**:
```bash
# Create symbolic link
sudo ln -s /etc/nginx/sites-available/qdii-radar /etc/nginx/sites-enabled/

# Remove default site
sudo rm /etc/nginx/sites-enabled/default

# Test nginx configuration
sudo nginx -t
```

---

## STEP 9: Configure Firewall

```bash
# Allow SSH
sudo ufw allow 22/tcp

# Allow HTTP
sudo ufw allow 80/tcp

# Allow HTTPS (for future SSL)
sudo ufw allow 443/tcp

# Enable firewall
sudo ufw --force enable

# Check status
sudo ufw status
```

---

## STEP 10: Start Services

```bash
# Start backend service
sudo systemctl start qdii-radar-backend

# Enable on boot
sudo systemctl enable qdii-radar-backend

# Restart nginx
sudo systemctl restart nginx

# Wait for startup
sleep 3
```

---

## STEP 11: Verify Deployment

```bash
# Check backend service
sudo systemctl status qdii-radar-backend
```

**Expected**: Active: active (running)

```bash
# Test backend health
curl http://127.0.0.1:8088/health
```

**Expected**: `{"status":"healthy"}`

```bash
# Test from external
curl http://your-domain.com/health
```

**Expected**: `{"status":"healthy"}`

---

## STEP 12: Access Application

Open your browser:
```
http://your-domain.com
```

or

```
http://your-server-ip
```

---

## Service Management

### View Logs

```bash
# Backend logs (real-time)
sudo journalctl -u qdii-radar-backend -f

# Backend logs (last 50 lines)
sudo journalctl -u qdii-radar-backend -n 50

# Nginx logs
sudo tail -f /var/log/nginx/qdii-radar-access.log
sudo tail -f /var/log/nginx/qdii-radar-error.log
```

### Restart Services

```bash
# Restart backend
sudo systemctl restart qdii-radar-backend

# Restart nginx
sudo systemctl restart nginx
```

### Check Status

```bash
# Backend status
sudo systemctl status qdii-radar-backend

# Nginx status
sudo systemctl status nginx
```

---

## Updating Application

When you need to update:

```bash
# Navigate to application directory
cd ~/qdii-radar

# Stop service
sudo systemctl stop qdii-radar-backend

# Pull latest changes
git pull origin main

# Update Python dependencies
source venv/bin/activate
pip install -r requirements.txt
deactivate

# Rebuild frontend
npm install
npm run build

# Start service
sudo systemctl start qdii-radar-backend

# Verify
sudo systemctl status qdii-radar-backend
```

---

## Optional: Email Notifications

```bash
# Create config directory
mkdir -p ~/qdii-radar/config

# Create SMTP config
vim ~/qdii-radar/config/smtp.json
```

Add:
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

```bash
# Create recipients config
vim ~/qdii-radar/config/recipients.json
```

Add:
```json
[
  {
    "email": "user@example.com",
    "active": true
  }
]
```

```bash
# Set secure permissions
chmod 600 ~/qdii-radar/config/*.json

# Restart service
sudo systemctl restart qdii-radar-backend
```

---

## Optional: Add HTTPS

If you have a domain:

```bash
# Install Certbot
sudo apt install -y certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d your-domain.com
```

Follow the prompts to enable HTTPS.

---

## Troubleshooting

### Backend won't start

```bash
# Check logs
sudo journalctl -u qdii-radar-backend -n 50

# Check port
sudo lsof -i :8088

# Kill if needed
sudo kill -9 <PID>

# Restart
sudo systemctl restart qdii-radar-backend
```

### 502 Bad Gateway

```bash
# Check if backend is running
curl http://127.0.0.1:8088/health

# Test nginx config
sudo nginx -t

# Reload nginx
sudo systemctl reload nginx
```

### Permission issues

```bash
# Fix ownership
sudo chown -R $USER:$USER ~/qdii-radar

# Fix permissions
chmod 755 ~/qdii-radar
chmod 600 ~/qdii-radar/config/*.json  # If exists
```

---

## File Structure

```
/home/YOUR_USERNAME/
└── qdii-radar/
    ├── server.py
    ├── requirements.txt
    ├── package.json
    ├── data/
    │   └── funds.json
    ├── dist/          # Frontend build output
    ├── venv/          # Python virtual environment
    ├── config/        # Optional: SMTP config
    │   ├── smtp.json
    │   └── recipients.json
    └── notifications.db  # SQLite database
```

---

## Quick Reference

**Application Directory**: `~/qdii-radar`
**Service Name**: `qdii-radar-backend`
**Backend Port**: `8088`
**Nginx Config**: `/etc/nginx/sites-available/qdii-radar`
**Systemd Service**: `/etc/systemd/system/qdii-radar-backend.service`

---

## Security Notes

- Backend runs on localhost only (127.0.0.1:8088) - secured by nginx
- Firewall configured to allow only HTTP/HTTPS
- Application runs under your user account
- Make sure to set proper file permissions on config files

---

**Last Updated**: 2025-12-30
**Version**: 1.0
