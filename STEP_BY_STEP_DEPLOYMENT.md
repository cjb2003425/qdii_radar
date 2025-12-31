# QDII Fund Radar - Step-by-Step Production Deployment

This manual guides you through deploying QDII Fund Radar to production on an Ubuntu server step by step.

**Estimated Time**: 20-30 minutes

**Prerequisites**:
- Ubuntu 20.04 or 22.04 LTS server
- SSH access to the server
- Domain name pointed to your server (optional)

---

## STEP 1: Install System Dependencies

SSH into your server and run:

```bash
# Update package lists
sudo apt update

# Install all required packages
sudo apt install -y python3 python3-pip python3-venv nodejs npm nginx git sqlite3 curl ufw
```

**Verify installations**:
```bash
python3 --version  # Should be 3.8+
node --version     # Should be 18+
npm --version
nginx -v
```

**Expected output**:
- Python 3.8.10 or higher
- Node v18.x.x or higher
- npm 9.x.x or higher

---

## STEP 2: Create Application User

Create a dedicated user for security:

```bash
# Create user named 'qdii-radar'
sudo useradd -m -s /bin/bash qdii-radar

# Verify user was created
id qdii-radar
```

**Expected output**:
```
uid=1001(qdii-radar) gid=1001(qdii-radar) groups=1001(qdii-radar)
```

---

## STEP 3: Setup Application Directory

Create the application directory:

```bash
# Create main directory
sudo mkdir -p /opt/qdii-radar

# Set ownership to qdii-radar user
sudo chown -R qdii-radar:qdii-radar /opt/qdii-radar

# Verify permissions
ls -la /opt/ | grep qdii
```

**Expected output**:
```
drwxr-xr-x  2 qdii-radar qdii-radar 4096 ...
```

---

## STEP 4: Deploy Application Files

**Option A: Using Git (Recommended)**

```bash
# Clone repository
sudo -u qdii-radar git clone https://github.com/cjb2003425/qdii_radar.git /opt/qdii-radar

# Verify files were copied
ls -la /opt/qdii-radar/
```

**Option B: Upload from Local Machine**

On your local machine:
```bash
# Upload files using rsync
rsync -av \
  --exclude='node_modules' \
  --exclude='venv' \
  --exclude='dist' \
  --exclude='.git' \
  ./ user@your-server-ip:/opt/qdii-radar/
```

**Expected files in /opt/qdii-radar/**:
```
-rw-r--r--  server.py
-rw-r--r--  package.json
-rw-r--r--  data/funds.json
drwxr-xr-x  components/
drwxr-xr-x  services/
```

---

## STEP 5: Setup Python Backend

Create virtual environment and install dependencies:

```bash
# Navigate to application directory
cd /opt/qdii-radar

# Create Python virtual environment
sudo -u qdii-radar python3 -m venv venv

# Upgrade pip
sudo -u qdii-radar venv/bin/pip install --upgrade pip

# Install Python dependencies
sudo -u qdii-radar venv/bin/pip install -r requirements.txt
```

**Verify installation**:
```bash
sudo -u qdii-radar venv/bin/python3 -c "import fastapi, akshare, httpx; print('✓ All dependencies installed')"
```

**Expected output**:
```
✓ All dependencies installed
```

---

## STEP 6: Build Frontend

Install Node dependencies and build:

```bash
# Still in /opt/qdii-radar
cd /opt/qdii-radar

# Install Node dependencies
sudo -u qdii-radar npm install

# Build for production
sudo -u qdii-radar npm run build
```

**Verify build**:
```bash
ls -lh /opt/qdii-radar/dist/
```

**Expected output**:
```
total 1.2M
-rw-r--r-- 1 qdii-radar qdii-radar 1.2M assets/index-abc123.js
-rw-r--r--  qdii-radar qdii-radar 2.5K assets/index-def456.css
-rw-r--r--  qdii-radar qdii-radar 1.8K index.html
```

---

## STEP 7: Configure Application for Production

Edit the configuration file:

```bash
sudo vim /opt/qdii-radar/data/funds.json
```

**Update the config section to match these settings**:

```json
{
  "config": {
    "server": {
      "host": "127.0.0.1",
      "port": 8088
    },
    "api": {
      "backendUrl": "/api/funds",
      "note": "Make sure backendUrl matches server.host:server.port",
      "requestTimeout": 20000,
      "userAgent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.38"
    }
  }
}
```

**Key changes**:
- `server.host`: `127.0.0.1` (local only, behind nginx)
- `server.port`: `8088` (backend port)
- `api.backendUrl`: `/api/funds` (relative path for nginx)

**Save and exit** (in vim: `:wq`)

---

## STEP 8: Create Systemd Service

Create the systemd service file:

```bash
sudo vim /etc/systemd/system/qdii-radar-backend.service
```

**Paste the following content**:

```ini
[Unit]
Description=QDII Fund Radar Backend Service
After=network.target

[Service]
Type=simple
User=qdii-radar
Group=qdii-radar
WorkingDirectory=/opt/qdii-radar
Environment="PATH=/opt/qdii-radar/venv/bin"
ExecStart=/opt/qdii-radar/venv/bin/python3 /opt/qdii-radar/server.py
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

**Save and exit** (`:wq`)

Reload systemd:
```bash
sudo systemctl daemon-reload
```

---

## STEP 9: Configure Nginx

Create nginx configuration:

```bash
sudo vim /etc/nginx/sites-available/qdii-radar
```

**Paste the following content** (replace `your-domain.com` with your domain or server IP):

```nginx
server {
    listen 80;
    server_name your-domain.com;  # Replace with your domain or IP address

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
        root /opt/qdii-radar/dist;
        try_files $uri $uri/ /index.html;

        # Cache static assets
        location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
    }
}
```

**Save and exit** (`:wq`)

**Enable the site**:
```bash
# Create symbolic link
sudo ln -s /etc/nginx/sites-available/qdii-radar /etc/nginx/sites-enabled/

# Remove default site (optional but recommended)
sudo rm /etc/nginx/sites-enabled/default

# Test nginx configuration
sudo nginx -t
```

**Expected output**:
```
nginx: the configuration file /etc/nginx/nginx.conf syntax is ok
nginx: configuration file /etc/nginx/sites-enabled/qdii-radar test is successful
```

---

## STEP 10: Configure Firewall

Set up UFW firewall:

```bash
# Allow SSH (important - don't lock yourself out!)
sudo ufw allow 22/tcp

# Allow HTTP
sudo ufw allow 80/tcp

# Allow HTTPS (for future SSL setup)
sudo ufw allow 443/tcp

# Enable firewall
sudo ufw --force enable

# Check firewall status
sudo ufw status
```

**Expected output**:
```
Status: active

To                         Action      From
--                         ------      ----
22/tcp                     ALLOW       Anywhere
80/tcp                     ALLOW       Anywhere
443/tcp                    ALLOW       Anywhere
```

---

## STEP 11: Start Services

Start all services:

```bash
# Start backend service
sudo systemctl start qdii-radar-backend

# Enable backend to start on boot
sudo systemctl enable qdii-radar-backend

# Restart nginx
sudo systemctl restart nginx

# Wait a few seconds for services to start
sleep 3
```

---

## STEP 12: Verify Deployment

Check if everything is running:

```bash
# 1. Check backend service status
sudo systemctl status qdii-radar-backend
```

**Expected output** (should show "active (running)"):
```
● qdii-radar-backend.service - QDII Fund Radar Backend Service
     Loaded: loaded (/etc/systemd/system/qdii-radar-backend.service; enabled)
     Active: active (running) since ...
```

```bash
# 2. Test backend health locally
curl http://127.0.0.1:8088/health
```

**Expected output**:
```json
{"status":"healthy"}
```

```bash
# 3. Test from external (replace with your domain/IP)
curl http://your-domain.com/health
```

**Expected output**:
```json
{"status":"healthy"}
```

```bash
# 4. Check nginx status
sudo systemctl status nginx
```

**Expected output** (should show "active (running)"):
```
● nginx.service - A high performance web server and a reverse proxy server
   Loaded: loaded (/lib/systemd/system/nginx.service; enabled)
   Active: active (running) since ...
```

---

## STEP 13: Access Your Application

Open your browser and navigate to:

**If you have a domain**:
```
http://your-domain.com
```

**If using IP address**:
```
http://your-server-ip
```

You should see the QDII Fund Radar dashboard with fund data loading!

---

## Optional Steps

### A. Configure Email Notifications

If you want email alerts for premium rate changes:

```bash
# Create config directory
sudo mkdir -p /opt/qdii-radar/config
sudo chown qdii-radar:qdii-radar /opt/qdii-radar/config
sudo chmod 700 /opt/qdii-radar/config

# Create SMTP config
sudo -u qdii-radar vim /opt/qdii-radar/config/smtp.json
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
sudo -u qdii-radar vim /opt/qdii-radar/config/recipients.json
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
sudo chmod 600 /opt/qdii-radar/config/*.json

# Restart service
sudo systemctl restart qdii-radar-backend
```

### B. Add HTTPS with Let's Encrypt (Free SSL)

If you have a domain name:

```bash
# Install Certbot
sudo apt install -y certbot python3-certbot-nginx

# Obtain SSL certificate
sudo certbot --nginx -d your-domain.com
```

Follow the prompts:
1. Enter email address for renewal notices
2. Agree to Terms of Service
3. Choose whether to redirect HTTP to HTTPS (recommended: Yes)

Your site will be accessible at:
```
https://your-domain.com
```

---

## Service Management Commands

### View Logs

```bash
# Backend logs (real-time)
sudo journalctl -u qdii-radar-backend -f

# Backend logs (last 50 lines)
sudo journalctl -u qdii-radar-backend -n 50

# Nginx access logs
sudo tail -f /var/log/nginx/qdii-radar-access.log

# Nginx error logs
sudo tail -f /var/log/nginx/qdii-radar-error.log
```

### Restart Services

```bash
# Restart backend
sudo systemctl restart qdii-radar-backend

# Restart nginx
sudo systemctl restart nginx

# Restart both
sudo systemctl restart qdii-radar-backend nginx
```

### Check Status

```bash
# Backend status
sudo systemctl status qdii-radar-backend

# Nginx status
sudo systemctl status nginx
```

---

## Updating the Application

When you need to update to a new version:

```bash
# Navigate to application directory
cd /opt/qdii-radar

# Stop the service
sudo systemctl stop qdii-radar-backend

# Pull latest changes
sudo -u qdii-radar git pull origin main

# Update Python dependencies (if requirements.txt changed)
sudo -u qdii-radar venv/bin/pip install -r requirements.txt

# Rebuild frontend (if frontend changed)
sudo -u qdii-radar npm install
sudo -u qdii-radar npm run build

# Start the service
sudo systemctl start qdii-radar-backend

# Verify
sudo systemctl status qdii-radar-backend
```

---

## Troubleshooting

### Backend won't start

```bash
# Check service status
sudo systemctl status qdii-radar-backend

# View logs
sudo journalctl -u qdii-radar-backend -n 50

# Check if port is already in use
sudo lsof -i :8088

# Kill process if needed
sudo kill -9 <PID>

# Restart service
sudo systemctl restart qdii-radar-backend
```

### 502 Bad Gateway error

```bash
# Check if backend is running
curl http://127.0.0.1:8088/health

# If it returns {"status":"healthy"}, backend is OK, issue is nginx

# Test nginx config
sudo nginx -t

# Reload nginx
sudo systemctl reload nginx
```

### Can't access from external browser

```bash
# Check firewall
sudo ufw status

# Should show:
# 80/tcp                     ALLOW       Anywhere

# If not, allow HTTP
sudo ufw allow 80/tcp
sudo ufw reload
```

### Frontend not loading

```bash
# Check if frontend was built
ls -la /opt/qdii-radar/dist/

# Should show index.html and assets/ directory

# If missing, rebuild
cd /opt/qdii-radar
sudo -u qdii-radar npm run build
```

---

## Security Checklist

- [x] Created dedicated user (qdii-radar)
- [x] Application files owned by qdii-radar user
- [x] Firewall enabled (UFW)
- [x] Only necessary ports open (22, 80, 443)
- [x] Backend binding to localhost only (127.0.0.1)
- [x] Nginx reverse proxy configured
- [x] Security headers added in nginx
- [ ] SSL/TLS configured (optional - see Step B above)
- [ ] Regular updates: `sudo apt update && sudo apt upgrade`
- [ ] Log monitoring configured
- [ ] Backup strategy in place

---

## Next Steps

1. **Test the application**: Add funds, set up monitoring
2. **Configure email**: Set up SMTP for notifications
3. **Add SSL**: Install HTTPS certificate
4. **Set up monitoring**: Use the monitoring features in the app
5. **Configure backup**: Set up automated backups

---

## Support

- GitHub Issues: https://github.com/cjb2003425/qdii_radar/issues
- Documentation: See README.md and CONFIGURATION.md

---

**Congratulations! Your QDII Fund Radar is now in production! 🎉**

**Last Updated**: 2025-12-30
**Version**: 1.0
