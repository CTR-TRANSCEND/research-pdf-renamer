# Research PDF File Renamer

**Version 0.2.1** | A web application that automatically renames academic/research PDF files using AI-powered metadata extraction.

## Features

- **Drag & Drop Interface** - Modern, intuitive file upload with drag-and-drop support
- **AI-Powered Extraction** - Uses LLM (OpenAI GPT-4o-mini, Ollama, or OpenAI-compatible) to extract author, year, and title from papers
- **Local LLM Support** - Full support for LocalLLM, Ollama, and OpenAI-compatible API servers
- **Batch Processing** - Upload multiple PDFs at once (up to 30 for registered users)
- **Privacy-First** - Only text from first 1-2 pages is sent to AI; files are deleted after download
- **User Management** - Registration system with admin approval workflow
- **Usage Limits** - Anonymous users: 5 files × 5/year; Registered users: 30 files unlimited
- **Admin Panel** - Complete admin dashboard for user management, LLM settings, and system monitoring
- **Apache Reverse Proxy** - Production-ready deployment with Apache + SSL support

## What's New in v0.2.1

### Admin Panel Enhancements
- ✅ **System Status Enhancement**: Added LLM provider and model display in System Status tab
- ✅ **Native Ollama Fix**: Fixed loaded models detection for LocalLLM servers when using "Ollama - Native Ollama server" provider

### LLM Integration
- ✅ **Fallback Endpoint**: Added automatic fallback from `/api/ps` to `/models/status` for LocalLLM compatibility
- ✅ **Model Discovery**: Fixed "Fetch Models" to properly detect loaded models across all provider types

## What's New in v0.2.0

### Admin Panel
- ✅ Fixed "Loading users..." issue - Users tab now loads correctly
- ✅ Fixed session authentication for reverse proxy deployments
- ✅ Added proper cookie path configuration (`/pdf-renamer`)
- ✅ Fixed API path routing for admin endpoints

### LLM Integration
- ✅ **Dual Provider Support**: Both Ollama native and OpenAI-compatible modes fully functional
- ✅ **Fetch Models**: Working model discovery for LocalLLM servers (port 8000)
- ✅ **API Key Management**: Save and reload API keys via admin panel
- ✅ **Provider Selection**: Seamlessly switch between OpenAI, Ollama, and OpenAI-compatible providers

### Architecture
- ✅ Apache reverse proxy configuration with security headers
- ✅ Application middleware for path stripping and proxy fixes
- ✅ Database health monitoring and connection pooling
- ✅ Session cookie configuration for reverse proxy compatibility

## Quick Start

### Prerequisites

- Python 3.10+
- OpenAI API key OR LocalLLM/Ollama server

### Installation

```bash
# Clone the repository
git clone https://github.com/hurlab/research-pdf-renamer.git
cd ResearchPDFFileRenamerGLM

# Run the setup script
./setup.sh

# Set your API key
echo "sk-your-api-key-here" > APISetting.txt
# Or for LocalLLM:
echo "llm_sk_your_local_llm_key" > .env
```

### Configuration

Edit `.env` file:

```bash
# OpenAI Configuration
OPENAI_API_KEY=sk-your-key-here
OPENAI_COMPATIBLE_API_KEY=sk-your-key-here

# LocalLLM Configuration (if using LocalLLM)
OLLAMA_API_KEY=llm_sk_your_local_llm_key
OLLAMA_URL=http://localhost:8000

# Provider Selection (openai, ollama, openai-compatible)
LLM_PROVIDER=openai-compatible
LLM_MODEL=gemma-2-9b-it
```

### Running the Server

```bash
# Development mode (Flask dev server)
./start.sh

# Or with Apache reverse proxy (production)
# Apache is configured to proxy /pdf-renamer/ to Flask on port 5000
```

Access the application at:
- Direct: http://localhost:5000
- Via Apache: http://localhost/pdf-renamer/

### Default Admin Account

- **Email:** admin@example.com
- **Password:** admin123

**IMPORTANT:** Change this in production!

## Project Structure

```
ResearchPDFFileRenamerGLM/
├── backend/
│   ├── __init__.py          # Version info export
│   ├── version.py           # Version 0.2.0
│   ├── app.py              # Flask application factory
│   ├── config.py           # Configuration with session cookie settings
│   ├── models/             # Database models
│   │   ├── user.py         # User model with approval workflow
│   │   ├── usage.py        # Usage tracking
│   │   └── settings.py     # System settings (LLM config)
│   ├── routes/             # API endpoints
│   │   ├── main.py         # Main routes, admin panel
│   │   ├── auth.py         # Authentication endpoints
│   │   ├── upload.py       # File upload/processing
│   │   └── admin.py        # Admin panel endpoints
│   ├── services/           # Business logic
│   │   ├── pdf_processor.py    # PDF text extraction
│   │   ├── llm_service.py      # LLM integration (multi-provider)
│   │   └── file_service.py     # File handling
│   ├── middleware/         # Custom middleware
│   │   └── db_monitor.py   # Database health monitoring
│   └── utils/              # Utilities
│       ├── auth.py         # Auth decorators (@auth_required)
│       └── db_health.py    # Database health utilities
├── frontend/
│   ├── static/             # CSS and JavaScript
│   │   └── js/
│   │       └── main.js     # Frontend logic
│   └── templates/          # HTML templates
│       ├── base.html       # Base template
│       ├── index.html      # Main page
│       ├── admin.html      # Admin panel
│       ├── profile.html    # User profile
│       └── terms.html      # Terms and conditions
├── docs/                   # Documentation
│   └── DATABASE_POOLING.md
├── run.py                  # Entry point
├── setup.sh                # Setup script
├── start.sh                # Start script
└── requirements.txt        # Python dependencies
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `FLASK_ENV` | Environment (development/production) | `development` |
| `OPENAI_API_KEY` | OpenAI API key | Required (for OpenAI provider) |
| `OPENAI_COMPATIBLE_API_KEY` | API key for OpenAI-compatible servers | Required |
| `OLLAMA_API_KEY` | API key for Ollama/LocalLLM | Required |
| `OLLAMA_URL` | Ollama/LocalLLM server URL | `http://localhost:11434` |
| `LLM_PROVIDER` | LLM provider | `openai-compatible` |
| `LLM_MODEL` | Model name | `gemma-2-9b-it` |
| `SECRET_KEY` | Flask secret key | Auto-generated |
| `DATABASE_URL` | Database URL | `sqlite:///instance/app.db` |
| `APPLICATION_ROOT` | Reverse proxy path | `/pdf-renamer` |
| `INACTIVITY_TIMEOUT_MINUTES` | Auto-logout after inactivity | `30` |

### LLM Provider Configuration

#### OpenAI (Cloud)
```bash
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
OPENAI_API_KEY=sk-...
```

#### LocalLLM (OpenAI-Compatible)
```bash
LLM_PROVIDER=openai-compatible
LLM_MODEL=gemma-2-9b-it
OPENAI_COMPATIBLE_API_KEY=llm_sk_...
OLLAMA_URL=http://localhost:8000
```

#### Ollama (Native)
```bash
LLM_PROVIDER=ollama
LLM_MODEL=llama3.2
OLLAMA_API_KEY=llm_sk_...
OLLAMA_URL=http://localhost:11434
```

## API Endpoints

### Public
- `GET /` - Main application page
- `GET /api/limits` - Get user upload limits
- `GET /api/health` - Health check

### Authentication
- `POST /api/auth/register` - User registration
- `POST /api/auth/login` - User login
- `POST /api/auth/logout` - User logout
- `GET /api/auth/me` - Get current user info

### File Processing
- `POST /api/upload` - Upload and process PDFs
- `GET /api/download/<filename>` - Download processed file

### Admin
- `GET /admin` - Admin panel dashboard
- `GET /api/admin/pending` - List pending users
- `POST /api/admin/approve/<id>` - Approve user
- `DELETE /api/admin/reject/<id>` - Reject user
- `GET /api/admin/users` - List all users
- `PUT /api/admin/users/<id>/limits` - Update user limits
- `POST /api/admin/test-ollama-connection` - Test LLM connection
- `POST /api/admin/save-api-key` - Save API key to .env
- `GET /api/admin/llm-settings` - Get LLM settings
- `POST /api/admin/llm-settings` - Update LLM settings
- `GET /api/admin/system-status` - System health status

## Port Usage

| Port | Service | Notes |
|------|---------|-------|
| 5000 | Flask (PDF Renamer) | Main application server |
| 8000 | LocalLLM API | External - do not use |
| 8080 | LocalLLM Admin UI | External - do not use |

## Development

### Running Tests

```bash
# Activate virtual environment
source venv/bin/activate

# Run tests
pytest tests/ -v

# Run with coverage
pytest --cov=backend tests/
```

### Code Quality

```bash
# Run linter
ruff check backend/

# Format code
ruff format backend/
```

## Production Deployment

### Quick Deployment

For production deployment, use the provided installation script:

```bash
# Clone the repository
git clone https://github.com/hurlab/research-pdf-renamer.git
cd research-pdf-renamer

# Run production installation
sudo systemd/install.sh
```

The installation script will:
1. Check system dependencies (Python, pip, git)
2. Create installation directory (`/opt/pdf-renamer`)
3. Set up Python virtual environment
4. Create systemd service
5. Configure logrotate
6. Prompt for Apache configuration

### Manual Deployment

For manual deployment or custom configurations, see the full [Deployment Guide](docs/deployment.md).

#### Apache Configuration

The application includes Apache configuration for reverse proxy. See `apache-pdf-renamer-enhanced.conf` for the complete configuration with security headers, static file serving, and WebSocket support.

#### Systemd Service

A systemd service unit file is provided in `systemd/pdf-renamer.service`. Key features:
- Runs as `www-data` user
- Gunicorn WSGI server with 3 workers
- Auto-restart on failure
- Log rotation configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Flask secret key for sessions | Auto-generated (change in production!) |
| `DATABASE_URL` | Database connection string | `sqlite:///pdf-renamer.db` |
| `FLASK_ENV` | Environment (development/production) | `production` |
| `APPLICATION_ROOT` | Reverse proxy path | `/pdf-renamer` |
| `ALLOW_PRIVATE_IPS` | Allow private IPs for LLM URLs | `false` (see SSRF Protection below) |
| `OPENAI_COMPATIBLE_API_KEY` | API key for OpenAI-compatible servers | Required |
| `LLM_PROVIDER` | LLM provider (openai, ollama, openai-compatible) | `openai` |
| `LLM_MODEL` | Model name | `gpt-4o-mini` |

### SSRF Protection (DEPLOY-001)

The application validates LLM server URLs to prevent SSRF attacks. By default, private IP addresses are rejected.

To allow local LLM servers (Ollama, LM Studio):
```bash
ALLOW_PRIVATE_IPS=true
```

**WARNING**: Only enable in trusted environments. This allows connections to internal network services.

### CSRF Protection (DEPLOY-002)

State-changing API endpoints require CSRF tokens:
- `POST /api/auth/change-password`
- `POST /api/auth/update-profile`
- `POST /api/admin/*` (all admin actions)
- `DELETE /api/admin/*`

Exempt endpoints (JWT + session protection):
- `POST /api/auth/login`
- `POST /api/auth/register`
- `POST /api/auth/logout`

### Database Options

**SQLite** (default - for development/small deployments):
```bash
DATABASE_URL=sqlite:///pdf-renamer.db
```

**PostgreSQL** (recommended for production):
```bash
DATABASE_URL=postgresql://user:password@localhost/dbname
```

**MariaDB/MySQL**:
```bash
DATABASE_URL=mysql+pymysql://user:password@localhost/dbname
```

See the [Deployment Guide](docs/deployment.md) for detailed database setup instructions.

### Security Checklist

- [x] Strong session management with proper cookie paths
- [x] SQL injection prevention (SQLAlchemy ORM)
- [x] XSS protection (Jinja2 auto-escaping)
- [x] CSRF protection for state-changing endpoints (Flask-WTF)
- [x] Password hashing (werkzeug)
- [x] File type validation (magic bytes)
- [x] Rate limiting (Flask-Limiter)
- [x] SSRF protection for LLM URLs
- [ ] HTTPS in production (use Let's Encrypt with certbot)
- [ ] Strong SECRET_KEY in production (use: `python3 -c 'import secrets; print(secrets.token_hex(32))'`)
- [ ] PostgreSQL instead of SQLite (recommended for multi-user deployments)

## Troubleshooting

### "Loading users..." never ends
**Fixed in v0.2.0** - Session cookie path was misconfigured for reverse proxy.

### Fetch Models button doesn't work
**Fixed in v0.2.0** - Provider-aware endpoint selection and proper API key handling.

### Admin panel redirects to login
**Fixed in v0.2.0** - Changed from `@auth_required` to `@login_required` for page routes.

## License

MIT License

---

**Version 0.2.1** - Released January 14, 2025
