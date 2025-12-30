# QDII Fund Radar - Ubuntu Deployment Manual

This guide provides step-by-step instructions for deploying QDII Fund Radar on an Ubuntu server.

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Initial Server Setup](#initial-server-setup)
3. [Backend Deployment](#backend-deployment)
4. [Frontend Deployment](#frontend-deployment)
5. [Nginx Configuration](#nginx-configuration)
6. [Systemd Services](#systemd-services)
7. [Security Hardening](#security-hardening)
8. [Monitoring and Maintenance](#monitoring-and-maintenance)
9. [Troubleshooting](#troubleshooting)

---

## System Requirements

- **OS**: Ubuntu 20.04 LTS or 22.04 LTS
- **RAM**: Minimum 1GB, recommended 2GB
- **CPU**: Minimum 1 core, recommended 2 cores
- **Disk**: Minimum 10GB free space
- **Network**: Open ports 80 (HTTP), 443 (HTTPS)

---

## Initial Server Setup

### 1. Update System

```bash
# Update package lists and upgrade packages
sudo apt update && sudo apt upgrade -y

# Install essential tools
sudo apt install -y curl wget git vim ufw fail2ban
```

### 2. Create Application User

```bash
# Create dedicated user for the application
sudo useradd -m -s /bin/bash qdii-radar
sudo usermod -aG sudo qdii-radar

# Set password
sudo passwd qdii-radar

# Switch to application user
sudo su - qdii-radar
```

### 3. Install Python 3.10+

```bash
# Install Python and development tools
sudo apt install -y python3 python3-pip python3-venv

# Verify installation
python3 --version  # Should be 3.8 or higher
pip3 --version
```

### 4. Install Node.js 18+

```bash
# Install Node.js using NodeSource repository
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs

# Verify installation
node --version  # Should be 18.x or higher
npm --version
```

### 5. Install SQLite3

```bash
sudo apt install -y sqlite3

# Verify installation
sqlite3 --version
```

---

## Backend Deployment

### 1. Clone Repository

```bash
# Navigate to home directory
cd ~

# Clone repository
git clone https://github.com/cjb2003425/qdii_radar.git

# Navigate to project directory
cd qdii_radar
```

### 2. Create Python Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip
```

### 3. Install Python Dependencies

```bash
# Install requirements
pip install -r requirements.txt

# Verify critical packages
python3 -c "import fastapi, akshare, httpx; print('✓ Dependencies installed successfully')"
```

### 4. Create Data Directory

```bash
# Create data directory if it doesn't exist
mkdir -p data
mkdir -p config

# Set proper permissions
chmod 755 data
chmod 700 config
```

### 5. Test Backend Locally

```bash
# Start backend in development mode
python3 server.py
```

Expected output:
```
INFO:     Started server process
INFO:     Uvicorn running on http://0.0.0.0:8000
```

Test the API:
```bash
# From another terminal
curl http://localhost:8000/health

# Expected output: {"status":"healthy"}
```

Stop the server with `Ctrl+C`.

---

## Frontend Deployment

### 1. Install Node Dependencies

```bash
# Navigate to project root
cd ~/qdii_radar

# Install dependencies
npm install
```

### 2. Build Frontend for Production

```bash
# Build production bundle
npm run build

# Verify build output
ls -lh dist/
```

Expected output:
```
total 1.2M
-rw-r--r-- 1 qdii-radar qdii-radar 1.2M Dec 30 12:00 assets/index-abc123.js
-rw-r--r--  qdii-radar qdii-radar 2.5K Dec 30 12:00 assets/index-def456.css
-rw-r--r--  qdii-radar qdii-radar 1.8K Dec 30 12:00 index.html
```

### 3. Configure Backend URL

If your frontend needs to point to a different backend URL, update the API endpoint:

```bash
# Edit the frontend configuration (if needed)
# By default, it uses http://127.0.0.1:8000/api/funds
# For production, you may want to use relative paths or configure nginx
```

---

## Nginx Configuration

### 1. Install Nginx

```bash
sudo apt install -y nginx

# Start and enable Nginx
sudo systemctl start nginx
sudo systemctl enable nginx

# Verify status
sudo systemctl status nginx
```

### 2. Configure Nginx Reverse Proxy

Create Nginx configuration file:

```bash
sudo vim /etc/nginx/sites-available/qdii-radar
```

Add the following configuration:

```nginx
# Upstream backend server
upstream qdii_backend {
    server 127.0.0.1:8000;
    keepalive 64;
}

# HTTP server - redirect to HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name your-domain.com;  # Replace with your domain or IP

    # Redirect all HTTP traffic to HTTPS
    return 301 https://$server_name$request_uri;
}

# HTTPS server
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name your-domain.com;  # Replace with your domain or IP

    # SSL certificate (use Let's Encrypt - see section below)
    ssl_certificate /etc/ssl/certs/qdii-radar.crt;
    ssl_certificate_key /etc/ssl/private/qdii-radar.key;

    # SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Backend API proxy
    location /api/ {
        proxy_pass http://qdii_backend;
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

        # Disable buffering for real-time updates
        proxy_buffering off;
    }

    # Health check endpoint
    location /health {
        proxy_pass http://qdii_backend/health;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        access_log off;
    }

    # Frontend static files
    location / {
        root /home/qdii-radar/qdii_radar/dist;
        try_files $uri $uri/ /index.html;

        # Cache static assets
        location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
    }

    # Logging
    access_log /var/log/nginx/qdii-radar-access.log;
    error_log /var/log/nginx/qdii-radar-error.log;
}
```

### 3. Enable Configuration

```bash
# Create symbolic link
sudo ln -s /etc/nginx/sites-available/qdii-radar /etc/nginx/sites-enabled/

# Remove default site (optional)
sudo rm /etc/nginx/sites-enabled/default

# Test configuration
sudo nginx -t

# Expected output: syntax is ok, test is successful

# Reload Nginx
sudo systemctl reload nginx
```

---

## SSL Certificate with Let's Encrypt (Optional but Recommended)

### 1. Install Certbot

```bash
sudo apt install -y certbot python3-certbot-nginx
```

### 2. Obtain SSL Certificate

```bash
# Replace with your domain name
sudo certbot --nginx -d your-domain.com

# Follow the prompts:
# - Enter email address for renewal notices
# - Agree to Terms of Service
# - Choose whether to redirect HTTP to HTTPS (recommended: Yes)
```

### 3. Auto-Renewal Setup

```bash
# Test auto-renewal
sudo certbot renew --dry-run

# Certbot automatically creates a systemd timer
# Verify timer is active
sudo systemctl status certbot.timer
```

### 4. Update Nginx Configuration

Certbot will automatically update your Nginx configuration. If you manually configured SSL paths earlier, update them:

```nginx
ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
```

Reload Nginx:
```bash
sudo systemctl reload nginx
```

---

## Systemd Services

### 1. Create Backend Service

Create systemd service file:

```bash
sudo vim /etc/systemd/system/qdii-radar-backend.service
```

Add the following:

```ini
[Unit]
Description=QDII Fund Radar Backend Service
After=network.target

[Service]
Type=simple
User=qdii-radar
Group=qdii-radar
WorkingDirectory=/home/qdii-radar/qdii_radar
Environment="PATH=/home/qdii-radar/qdii_radar/venv/bin"
ExecStart=/home/qdii-radar/qdii_radar/venv/bin/python3 server.py
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

### 2. Start and Enable Backend Service

```bash
# Reload systemd
sudo systemctl daemon-reload

# Start service
sudo systemctl start qdii-radar-backend

# Enable service to start on boot
sudo systemctl enable qdii-radar-backend

# Check status
sudo systemctl status qdii-radar-backend

# View logs
sudo journalctl -u qdii-radar-backend -f
```

### 3. Verify Backend is Running

```bash
# Test API
curl http://localhost:8000/health

# Test from external (replace with your domain/IP)
curl https://your-domain.com/health
```

---

## Security Hardening

### 1. Configure UFW Firewall

```bash
# Allow SSH
sudo ufw allow 22/tcp

# Allow HTTP/HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Enable firewall
sudo ufw enable

# Check status
sudo ufw status
```

### 2. Install and Configure Fail2Ban

```bash
# Install Fail2Ban
sudo apt install -y fail2ban

# Create local configuration
sudo cp /etc/fail2ban/jail.conf /etc/fail2ban/jail.local

# Edit configuration
sudo vim /etc/fail2ban/jail.local
```

Add/Edit these settings:

```ini
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5

[sshd]
enabled = true
port = ssh
logpath = /var/log/auth.log

[nginx-http-auth]
enabled = true
port = http,https
logpath = /var/log/nginx/error.log
```

Restart Fail2Ban:
```bash
sudo systemctl restart fail2ban
sudo systemctl enable fail2ban
```

### 3. Set File Permissions

```bash
# Set proper ownership
sudo chown -R qdii-radar:qdii-radar /home/qdii-radar/qdii_radar

# Restrict config directory
chmod 700 /home/qdii-radar/qdii_radar/config

# Restrict database
chmod 600 /home/qdii-radar/qdii_radar/data/notifications.db

# Restrict SSL certificates
sudo chmod 600 /etc/ssl/private/qdii-radar.key
sudo chmod 644 /etc/ssl/certs/qdii-radar.crt
```

---

## Monitoring and Maintenance

### 1. Log Monitoring

**Backend Logs**:
```bash
# View real-time logs
sudo journalctl -u qdii-radar-backend -f

# View last 100 lines
sudo journalctl -u qdii-radar-backend -n 100

# View logs from today
sudo journalctl -u qdii-radar-backend --since today
```

**Nginx Logs**:
```bash
# Access logs
sudo tail -f /var/log/nginx/qdii-radar-access.log

# Error logs
sudo tail -f /var/log/nginx/qdii-radar-error.log
```

### 2. Disk Space Monitoring

```bash
# Check disk usage
df -h

# Check large files
du -sh /home/qdii-radar/qdii_radar/data/*

# Clean old logs if needed (keep last 7 days)
sudo journalctl --vacuum-time=7d
```

### 3. Database Backup

Create backup script:

```bash
vim ~/backup-db.sh
```

Add the following:

```bash
#!/bin/bash
# Backup script for QDII Radar database

BACKUP_DIR="/home/qdii-radar/backups"
DB_PATH="/home/qdii-radar/qdii_radar/data/notifications.db"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/notifications_$DATE.db"

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup database
cp $DB_PATH $BACKUP_FILE

# Compress backup
gzip $BACKUP_FILE

# Remove backups older than 30 days
find $BACKUP_DIR -name "notifications_*.db.gz" -mtime +30 -delete

echo "Backup completed: $BACKUP_FILE.gz"
```

Make it executable and add to cron:

```bash
chmod +x ~/backup-db.sh

# Edit crontab
crontab -e

# Add this line to backup daily at 2 AM
0 2 * * * /home/qdii-radar/backup-db.sh >> /home/qdii-radar/backup.log 2>&1
```

### 4. Update Application

```bash
# Switch to application user
sudo su - qdii-radar

# Navigate to project directory
cd qdii_radar

# Stop service
sudo systemctl stop qdii-radar-backend

# Pull latest changes
git pull origin main

# Activate virtual environment
source venv/bin/activate

# Update Python dependencies
pip install -r requirements.txt

# Rebuild frontend
npm install
npm run build

# Start service
sudo systemctl start qdii-radar-backend

# Verify
sudo systemctl status qdii-radar-backend
```

---

## Troubleshooting

### Backend Service Won't Start

```bash
# Check service status
sudo systemctl status qdii-radar-backend

# View logs
sudo journalctl -u qdii-radar-backend -n 50

# Common issues:
# 1. Port 8000 already in use
sudo lsof -i :8000

# 2. Missing dependencies
source venv/bin/activate
pip install -r requirements.txt

# 3. Database locked
rm data/notifications.db
# Service will recreate on restart
```

### Nginx 502 Bad Gateway

```bash
# Check if backend is running
curl http://localhost:8000/health

# Check Nginx error logs
sudo tail -f /var/log/nginx/qdii-radar-error.log

# Verify upstream configuration
sudo nginx -t

# Common issue: Backend not running
sudo systemctl restart qdii-radar-backend
```

### Frontend Not Loading

```bash
# Check if frontend build exists
ls -lh ~/qdii_radar/dist/

# Rebuild if needed
cd ~/qdii_radar
npm run build

# Check Nginx configuration
sudo nginx -t

# Verify file permissions
ls -l ~/qdii_radar/dist/
```

### SSL Certificate Issues

```bash
# Test SSL configuration
sudo openssl s_client -connect your-domain.com:443

# Renew certificate manually
sudo certbot renew

# Check certificate expiration
sudo certbot certificates

# Force renewal
sudo certbot renew --force-renewal
```

### Database Corruption

```bash
# Check database integrity
sqlite3 ~/qdii_radar/data/notifications.db "PRAGMA integrity_check;"

# If corrupted, restore from backup
cp ~/backups/notifications_YYYYMMDD_HHMMSS.db.gz ~/qdii_radar/data/notifications.db.gz
gunzip ~/qdii_radar/data/notifications.db.gz

# Restart service
sudo systemctl restart qdii-radar-backend
```

---

## Performance Tuning

### 1. Increase Uvicorn Workers

Edit `server.py` or create a startup script to use multiple workers:

```bash
# Install gunicorn (production WSGI server)
pip install gunicorn

# Update systemd service
sudo vim /etc/systemd/system/qdii-radar-backend.service
```

Update `ExecStart`:
```ini
ExecStart=/home/qdii-radar/qdii_radar/venv/bin/gunicorn server:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### 2. Enable Nginx Caching

Add to Nginx server block:

```nginx
# Cache API responses
proxy_cache_path /var/cache/nginx/qdii-api levels=1:2 keys_zone=api_cache:10m max_size=100m inactive=60m;

location /api/funds {
    proxy_cache api_cache;
    proxy_cache_valid 200 5m;
    proxy_pass http://qdii_backend;
}
```

Create cache directory:
```bash
sudo mkdir -p /var/cache/nginx/qdii-api
sudo chown -R www-data:www-data /var/cache/nginx
```

---

## Environment-Specific Configurations

### Production Environment Variables

Create `.env` file:

```bash
vim ~/qdii_radar/.env
```

Add:
```bash
# Backend
API_HOST=0.0.0.0
API_PORT=8000
LOG_LEVEL=info

# Email (optional)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM_EMAIL=your-email@gmail.com
```

Update `server.py` to load environment variables.

---

## Final Checklist

Before going live, verify:

- [ ] Backend service is running: `sudo systemctl status qdii-radar-backend`
- [ ] Nginx is running: `sudo systemctl status nginx`
- [ ] SSL certificate is valid: `sudo certbot certificates`
- [ ] Firewall is enabled: `sudo ufw status`
- [ ] Database backup is scheduled: `crontab -l`
- [ ] Logs are being written: `sudo journalctl -u qdii-radar-backend -n 20`
- [ ] API is accessible: `curl https://your-domain.com/health`
- [ ] Frontend loads: Visit https://your-domain.com in browser

---

## Support

For issues and questions:
- GitHub Issues: https://github.com/cjb2003425/qdii_radar/issues
- Documentation: See README.md and CLAUDE.md

---

**Last Updated**: 2025-12-30
**Version**: 1.0
