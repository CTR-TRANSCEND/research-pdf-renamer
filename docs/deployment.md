# Research PDF Renamer - Deployment Guide

This guide covers production deployment of the Research PDF Renamer application.

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Database Configuration](#database-configuration)
3. [Environment Variables](#environment-variables)
4. [Production Installation](#production-installation)
5. [Apache Configuration](#apache-configuration)
6. [Systemd Service](#systemd-service)
7. [Security Considerations](#security-considerations)
8. [Troubleshooting](#troubleshooting)

---

## System Requirements

### Minimum Requirements

- **OS**: Ubuntu 20.04+ or Debian 11+
- **Python**: 3.9+
- **RAM**: 2GB+
- **Disk**: 10GB+
- **Web Server**: Apache 2.4+

### Recommended for Production

- **OS**: Ubuntu 22.04 LTS
- **Python**: 3.11+
- **RAM**: 4GB+
- **Disk**: 20GB+
- **Database**: PostgreSQL 14+ or MariaDB 10.6+
- **Web Server**: Apache 2.4 with mod_proxy, mod_wsgi

---

## Database Configuration

### Default: SQLite (Development/Small Deployments)

SQLite is the default database and requires no additional configuration.

**Environment Variable:**
```bash
DATABASE_URL=sqlite:///pdf-renamer.db
```

**Location:** By default, the SQLite database is created in the application's `instance` directory.

**Limitations:**
- Not suitable for high-concurrency scenarios
- No built-in replication
- Limited write performance

**Recommended For:**
- Development environments
- Single-user deployments
- Testing and evaluation

---

### Production: PostgreSQL

For production deployments with multiple users, PostgreSQL is recommended.

**Installation:**
```bash
sudo apt-get install postgresql postgresql-contrib
```

**Create Database:**
```bash
sudo -u postgres psql
CREATE DATABASE pdfrenamer;
CREATE USER pdfrenamer WITH PASSWORD 'secure_password_here';
GRANT ALL PRIVILEGES ON DATABASE pdfrenamer TO pdfrenamer;
\q
```

**Environment Variable:**
```bash
DATABASE_URL=postgresql://pdfrenamer:secure_password_here@localhost:5432/pdfrenamer
```

**Enable PostgreSQL Extensions (Optional):**
```bash
sudo -u postgres psql pdfrenamer
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
\q
```

---

### Production: MariaDB/MySQL

MariaDB or MySQL can also be used for production deployments.

**Installation:**
```bash
sudo apt-get install mariadb-server
```

**Create Database:**
```bash
sudo mysql
CREATE DATABASE pdfrenamer CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'pdfrenamer'@'localhost' IDENTIFIED BY 'secure_password_here';
GRANT ALL PRIVILEGES ON pdfrenamer.* TO 'pdfrenamer'@'localhost';
FLUSH PRIVILEGES;
\q
```

**Environment Variable:**
```bash
DATABASE_URL=mysql+pymysql://pdfrenamer:secure_password_here@localhost:3306/pdfrenamer
```

**Install Python MySQL Driver:**
```bash
pip install pymysql
```

---

### Migration Procedures

#### From SQLite to PostgreSQL

1. **Export SQLite data:**
```bash
sqlite3 instance/pdf-renamer.db .dump > backup.sql
```

2. **Convert to PostgreSQL format:**
Use a tool like `pgloader` or manually convert the SQL.

3. **Import to PostgreSQL:**
```bash
psql -U pdfrenamer -d pdfrenamer < backup_converted.sql
```

4. **Update .env file:**
```bash
DATABASE_URL=postgresql://pdfrenamer:password@localhost:5432/pdfrenamer
```

#### From SQLite to MariaDB/MySQL

1. **Export SQLite data:**
```bash
sqlite3 instance/pdf-renamer.db .dump > backup.sql
```

2. **Convert to MySQL format:**
Modify AUTOINCREMENT to AUTO_INCREMENT in the SQL file.

3. **Import to MySQL:**
```bash
mysql -u pdfrenamer -p pdfrenamer < backup_converted.sql
```

4. **Update .env file:**
```bash
DATABASE_URL=mysql+pymysql://pdfrenamer:password@localhost:3306/pdfrenamer
```

---

## Environment Variables

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `SECRET_KEY` | Flask secret key for sessions | `openssl rand -hex 32` |
| `DATABASE_URL` | Database connection string | See [Database Configuration](#database-configuration) |
| `OPENAI_COMPATIBLE_API_KEY` | LLM API key | `sk-...` |

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `FLASK_ENV` | Flask environment | `production` |
| `APPLICATION_ROOT` | URL path prefix | `/pdf-renamer` |
| `MAX_CONTENT_LENGTH` | Max upload size (bytes) | `104857600` (100MB) |
| `INACTIVITY_TIMEOUT_MINUTES` | Session timeout | `30` |
| `ALLOW_PRIVATE_IPS` | Allow private IPs for LLM URLs | `false` |

### LLM Provider Configuration

**OpenAI-compatible API:**
```bash
LLM_PROVIDER=openai
OPENAI_COMPATIBLE_API_KEY=your_api_key
OPENAI_COMPATIBLE_API_BASE=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
```

**Ollama (Local LLM):**
```bash
LLM_PROVIDER=ollama
OLLAMA_URL=http://localhost:11434
LLM_MODEL=llama2
```

**Azure OpenAI:**
```bash
LLM_PROVIDER=azure
AZURE_OPENAI_API_KEY=your_api_key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
LLM_MODEL=gpt-4
```

### SSRF Protection (DEPLOY-001)

The `ALLOW_PRIVATE_IPS` variable controls whether private IP addresses are allowed for LLM server URLs.

**Default (secure):**
```bash
ALLOW_PRIVATE_IPS=false
```

This rejects:
- Private IP ranges (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
- Link-local addresses (169.254.0.0/16)
- Reserved ranges

**For local LLM servers:**
```bash
ALLOW_PRIVATE_IPS=true
```

**WARNING**: Only enable in trusted environments. This allows connections to internal network services.

---

## Production Installation

### Automated Installation

Use the provided installation script:

```bash
# Clone repository
git clone https://github.com/yourusername/research-pdf-renamer.git
cd research-pdf-renamer

# Run production installation
sudo systemd/install.sh
```

The script will:
1. Check system dependencies
2. Create installation directory (`/opt/pdf-renamer`)
3. Set up Python virtual environment
4. Create systemd service
5. Configure logrotate
6. Prompt for Apache configuration

### Manual Installation

1. **Create installation directory:**
```bash
sudo mkdir -p /opt/pdf-renamer
sudo chown www-data:www-data /opt/pdf-renamer
```

2. **Copy application files:**
```bash
sudo rsync -av --exclude='venv' --exclude='.git' \
    /path/to/source/ /opt/pdf-renamer/
```

3. **Create virtual environment:**
```bash
sudo -u www-data python3 -m venv /opt/pdf-renamer/venv
source /opt/pdf-renamer/venv/bin/activate
pip install -r /opt/pdf-renamer/requirements.txt
```

4. **Create .env file:**
```bash
sudo cp /opt/pdf-renamer/.env.example /opt/pdf-renamer/.env
sudo nano /opt/pdf-renamer/.env
```

5. **Create log directories:**
```bash
sudo mkdir -p /var/log/pdf-renamer /var/lib/pdf-renamer
sudo chown www-data:www-data /var/log/pdf-renamer /var/lib/pdf-renamer
```

---

## Apache Configuration

### Installation

1. **Copy Apache configuration:**
```bash
sudo cp /opt/pdf-renamer/apache-pdf-renamer-enhanced.conf \
    /etc/apache2/sites-available/pdf-renamer.conf
```

2. **Update paths in configuration:**
```bash
sudo nano /etc/apache2/sites-available/pdf-renamer.conf
# Update Alias paths to match your installation directory
```

3. **Enable required modules:**
```bash
sudo a2enmod proxy proxy_http proxy_wstunnel rewrite headers expires deflate
```

4. **Enable the site:**
```bash
sudo a2ensite pdf-renamer.conf
sudo systemctl reload apache2
```

### Configuration File

The Apache configuration file includes:

- **Reverse Proxy**: Routes `/pdf-renamer/` to the Flask backend
- **Static Files**: Serves static content directly from Apache
- **Security Headers**: X-Frame-Options, CSP, HSTS (if HTTPS)
- **Compression**: mod_deflate for text content
- **Logging**: Separate access/error logs

### SSL/HTTPS Configuration

For production, enable HTTPS with Let's Encrypt:

```bash
# Install certbot
sudo apt-get install certbot python3-certbot-apache

# Obtain certificate
sudo certbot --apache -d yourdomain.com

# Auto-renewal is configured automatically
```

---

## Systemd Service

### Service File Location

`/etc/systemd/system/pdf-renamer.service`

### Service Management

**Start service:**
```bash
sudo systemctl start pdf-renamer
```

**Enable on boot:**
```bash
sudo systemctl enable pdf-renamer
```

**Check status:**
```bash
sudo systemctl status pdf-renamer
```

**Restart service:**
```bash
sudo systemctl restart pdf-renamer
```

**View logs:**
```bash
sudo journalctl -u pdf-renamer -f
```

### Service Configuration

The systemd service is configured with:

- **User/Group**: www-data
- **Workers**: 3 (adjust based on CPU cores)
- **Threads**: 4 per worker
- **Timeout**: 300 seconds
- **Auto-restart**: Always

**Adjust worker count:**
```bash
sudo nano /etc/systemd/system/pdf-renamer.service
# Modify --workers value (recommend: 2 x CPU cores + 1)
sudo systemctl daemon-reload
sudo systemctl restart pdf-renamer
```

---

## Security Considerations

### CSRF Protection (DEPLOY-002)

State-changing endpoints require CSRF tokens:

**Protected endpoints:**
- POST /api/auth/change-password
- POST /api/auth/update-profile
- POST /api/admin/* (all admin actions)
- DELETE /api/admin/*

**Exempt endpoints:**
- /api/auth/login (JWT + session protection)
- /api/auth/register
- /api/auth/logout
- /api/upload/* (multipart/form-data)

### Session Security

Default session configuration:
- HttpOnly: true (XSS protection)
- Secure: false (set to true with HTTPS)
- SameSite: Lax (CSRF protection)
- Timeout: 30 minutes inactivity

### File Upload Security

- Max file size: 100MB
- Allowed types: PDF only
- Virus scanning: Recommended for production

### Rate Limiting

Default limits:
- 200 requests per day
- 50 requests per hour

Configure Redis for multi-worker deployments:
```bash
pip install redis
# Set in .env:
RATE_LIMIT_STORAGE_URL=redis://localhost:6379
```

### Security Headers

Enabled by Flask-Talisman:
- X-Frame-Options: SAMEORIGIN
- X-Content-Type-Options: nosniff
- Content-Security-Policy: default-src 'self'
- Strict-Transport-Security: Enabled with HTTPS

---

## Troubleshooting

### Service won't start

**Check logs:**
```bash
sudo journalctl -u pdf-renamer -n 50
```

**Common issues:**
1. **Port 5000 already in use:**
```bash
sudo lsof -i :5000
sudo kill <PID>
```

2. **Database connection error:**
- Verify DATABASE_URL in .env
- Check database is running
- Verify credentials

3. **Permission errors:**
```bash
sudo chown -R www-data:www-data /opt/pdf-renamer
sudo chown -R www-data:www-data /var/log/pdf-renamer
```

### 502 Bad Gateway (Apache)

**Check backend is running:**
```bash
curl http://localhost:5000/
```

**Check Apache error log:**
```bash
sudo tail -f /var/log/apache2/pdf-renamer-error.log
```

### Database errors

**SQLite locked:**
- Ensure only one worker for SQLite
- Consider PostgreSQL for multi-user deployments

**Connection pool exhausted:**
- Increase pool size in backend/config.py
- Check for connection leaks

### LLM connection errors

**Check API key:**
```bash
echo $OPENAI_COMPATIBLE_API_KEY
```

**Test Ollama connection:**
```bash
curl http://localhost:11434/api/tags
```

**SSRF blocking:**
- If using local LLM, set `ALLOW_PRIVATE_IPS=true`
- Check firewall rules

### Performance issues

**Enable database query logging:**
```bash
# In .env:
SQLALCHEMY_ECHO=true
```

**Check rate limiting:**
```bash
# View current limits in backend/app.py
# Adjust default_limits as needed
```

**Database optimization:**
- Add indexes for frequently queried columns
- Use connection pooling (configure in DATABASE_URL)
- Enable query caching

---

## Additional Resources

- [README.md](../README.md) - General project information
- [OLLAMA_INTEGRATION_TEST_REPORT.md](OLLAMA_INTEGRATION_TEST_REPORT.md) - Ollama testing details
- [DATABASE_POOLING.md](DATABASE_POOLING.md) - Database configuration options

---

## Support

For issues or questions:
1. Check the logs (see [Troubleshooting](#troubleshooting))
2. Review this deployment guide
3. Check GitHub Issues
4. Contact system administrator
