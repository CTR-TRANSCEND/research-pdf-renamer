# Research PDF File Renamer

Managing large collections of research papers often means dealing with unhelpful filenames like `document.pdf`, `1-s2.0-S0123456789.pdf`, or `manuscript_final_v3.pdf`. Manually renaming each file by looking up author names, publication years, and journal titles is tedious and error-prone, especially when working with dozens or hundreds of papers across multiple research projects.

Research PDF File Renamer solves this problem by using large language models (LLMs) to automatically extract bibliographic metadata from your PDF files. Simply upload your papers through the drag-and-drop web interface, and the system reads the first one to two pages of each document, sends the extracted text to an AI model of your choice, and parses the response to identify the first author, publication year, journal name, and relevant keywords. The files are then renamed into a clean, standardized format such as `Author_Year_Journal_Keywords.pdf` and returned for download -- as individual files or as a ZIP archive for batch uploads.

The application supports multiple LLM providers including OpenAI, LM Studio, Ollama, and any OpenAI-compatible API server, making it suitable for both cloud-based and fully local, privacy-conscious deployments. It includes a complete user management system with registration, admin approval workflows, role-based access controls, and per-user upload limits. An admin dashboard provides system monitoring, LLM configuration, and user management capabilities. Deployment options range from a single Docker command to a production-grade systemd + Apache reverse proxy setup with SSL/TLS support.

![Main Page](docs/screenshots/01_main_page.png)

## Features

- **Drag & Drop Upload** -- Modern interface with drag-and-drop and batch processing (up to 30 files)
- **AI-Powered Extraction** -- Uses LLM to extract author, year, title, journal, and keywords
- **Multi-Provider LLM Support** -- OpenAI, Ollama, LM Studio, or any OpenAI-compatible server
- **Privacy-First** -- Only text from first 1-2 pages is sent to AI; files are deleted after download
- **User Management** -- Registration with admin approval, role-based access, usage tracking
- **Admin Dashboard** -- User management, LLM configuration, system monitoring
- **Flexible Deployment** -- Docker, systemd + Apache reverse proxy, or standalone Flask

## Quick Start

### Option 1: Docker -- Zero Config (Recommended)

No `.env` file needed. Includes a built-in Ollama LLM server that auto-downloads a model on first start.

```bash
git clone https://github.com/CTR-TRANSCEND/research-pdf-renamer.git
cd research-pdf-renamer
docker compose up -d
```

Open http://localhost:5000 and log in with the default admin credentials below. The first startup takes a few minutes while the AI model downloads (~2 GB).

### Option 2: Pre-built Docker Image

No need to clone the repository. Requires your own LLM provider (OpenAI API key or local Ollama).

```bash
# With OpenAI
docker run -p 5000:5000 -e OPENAI_API_KEY=sk-... ghcr.io/ctr-transcend/research-pdf-renamer

# With local Ollama (already running on host)
docker run -p 5000:5000 -e LLM_PROVIDER=ollama -e OLLAMA_URL=http://host.docker.internal:11434 \
  ghcr.io/ctr-transcend/research-pdf-renamer
```

### Option 3: Local Installation

Works with any Python 3.10+ environment (conda, venv, or system Python). The setup script auto-creates a virtual environment if needed.

```bash
git clone https://github.com/CTR-TRANSCEND/research-pdf-renamer.git
cd research-pdf-renamer
./setup.sh
./start.sh
```

On first startup with no existing users, the app auto-creates an admin account and prints the credentials to the console.

Access the application at http://localhost:5000

### Default Admin Account (Docker)

| | |
|---|---|
| **Email** | `admin@local` |
| **Password** | `changeme123` |

> **Important:** Change the default credentials after first login. For local installations (Option 3), credentials are auto-generated and printed to the console on first startup.

---

## User Guide

### Uploading PDFs

The main page provides a drag-and-drop area for uploading PDF files. You can also click **Browse Files** to select files from your computer.

1. Drag your PDF files onto the upload area (or click Browse)
2. Click **Process Files** to start AI extraction
3. The system extracts metadata from the first 1-2 pages
4. Files are automatically renamed to `Author_Year_Journal_Keywords.pdf`
5. Download starts automatically (ZIP for multiple files)

**Upload limits:**
- Anonymous users: 5 files per submission, 5 submissions per year
- Registered users: 30 files per submission, unlimited submissions

### Registration and Login

Click **Register** in the top navigation to create an account. Registration requires admin approval before you can log in.

| Login | Registration |
|:---:|:---:|
| ![Login](docs/screenshots/02_login_modal.png) | ![Register](docs/screenshots/03_register_modal.png) |

After logging in, the upload limit increases and you gain access to folder upload and your profile page.

![Logged In](docs/screenshots/04_logged_in.png)

### User Profile

Access your profile from the navigation bar to:

- Update your display name
- Choose a filename format (e.g., `Author_Year_Journal_Keywords`, `Author_Year_Title`, or custom)
- Toggle automatic downloads
- View your usage statistics and recent activity

![Profile Page](docs/screenshots/07_profile_page.png)

### Admin Panel

Administrators have access to the admin panel at `/admin` with the following tabs:

**Dashboard** -- Overview of user statistics, usage metrics, and system status.

![Admin Dashboard](docs/screenshots/05_admin_dashboard.png)

**Users** -- Manage all registered users. Approve, deactivate, promote to admin, or delete accounts. Adjust per-user file limits.

**Pending Approvals** -- Review and approve new user registrations.

**LLM Settings** -- Configure the AI provider. Select from LM Studio, Ollama, OpenAI, or any OpenAI-compatible server. Fetch available models, set context window size, and test connectivity.

![LLM Settings](docs/screenshots/06_admin_llm_settings.png)

**System Status** -- Monitor database health, LLM service status, and storage.

---

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure:

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Flask secret key for sessions | Auto-generated |
| `LLM_PROVIDER` | LLM provider (`openai`, `ollama`, `lm-studio`, `openai-compatible`) | `openai` |
| `LLM_MODEL` | Model name | `gpt-4o-mini` |
| `OPENAI_API_KEY` | OpenAI API key | Required for OpenAI provider |
| `OLLAMA_URL` | Ollama/LM Studio server URL | `http://localhost:11434` |
| `ALLOW_PRIVATE_IPS` | Allow private IPs for LLM server URLs | `false` |
| `RATE_LIMIT_STORAGE_URL` | Redis URL for persistent rate limiting | `memory://` |
| `INACTIVITY_TIMEOUT_MINUTES` | Session inactivity timeout | `30` |
| `TALISMAN_FORCE_HTTPS` | Force HTTPS redirects | `true` (set `false` for Docker) |

### LLM Provider Setup

#### OpenAI

```bash
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
OPENAI_API_KEY=sk-...
```

#### LM Studio

```bash
LLM_PROVIDER=lm-studio
LLM_MODEL=your-model-name
OLLAMA_URL=http://localhost:1234
```

Context window is auto-detected from the LM Studio API. No API key required.

#### Ollama

```bash
LLM_PROVIDER=ollama
LLM_MODEL=llama3.2
OLLAMA_URL=http://localhost:11434
```

#### OpenAI-Compatible Server

```bash
LLM_PROVIDER=openai-compatible
LLM_MODEL=your-model-name
OPENAI_COMPATIBLE_API_KEY=your-api-key
OLLAMA_URL=http://localhost:8000
```

> **Note:** If your LLM server runs on a private network (e.g., Tailscale), set `ALLOW_PRIVATE_IPS=true` in your `.env` file.

---

## Production Deployment

### Docker

```bash
cp .env.example .env
# Edit .env with production settings (SECRET_KEY, LLM config)
docker compose up -d
```

### Systemd + Apache

```bash
sudo systemd/install.sh
```

This creates a systemd service with Gunicorn (3 workers) and configures log rotation. See the [Deployment Guide](docs/deployment.md) for Apache reverse proxy and SSL/TLS setup with Let's Encrypt.

### Security Checklist

- [x] XSS protection (Jinja2 auto-escaping + `escapeHtml()`)
- [x] CSRF protection for state-changing endpoints
- [x] SQL injection prevention (SQLAlchemy ORM)
- [x] Password hashing (werkzeug)
- [x] Rate limiting (Flask-Limiter, optional Redis backend)
- [x] SSRF protection for LLM server URLs
- [x] File type validation (magic bytes)
- [ ] HTTPS in production (`certbot --apache -d your-domain.com`)
- [ ] Strong `SECRET_KEY` (`python3 -c 'import secrets; print(secrets.token_hex(32))'`)

---

## Development

### Running Tests

```bash
source venv/bin/activate

# Unit and integration tests (256 tests)
pytest tests/ -v -m "not e2e"

# E2E workflow tests (14 tests)
pytest tests/e2e/ -v

# With coverage
pytest --cov=backend tests/
```

### Project Structure

```
research-pdf-renamer/
├── backend/
│   ├── app.py                  # Flask application factory
│   ├── models/                 # SQLAlchemy models (user, usage, settings)
│   ├── routes/                 # API endpoints (auth, upload, admin, main)
│   ├── services/               # Business logic (PDF processing, LLM, files)
│   └── utils/                  # Auth, validators, metrics, logging
├── frontend/
│   ├── static/js/main.js       # Frontend logic
│   └── templates/              # Jinja2 templates (index, admin, profile)
├── tests/                      # 270 tests (unit, integration, E2E)
├── docs/                       # Deployment guide, screenshots
├── systemd/                    # Systemd service and install script
├── Dockerfile                  # Docker container definition
├── docker-compose.yml          # Docker Compose configuration
├── run.py                      # Entry point
├── setup.sh                    # Local setup script
└── requirements.txt            # Python dependencies
```

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Main application page |
| `GET` | `/api/health` | Health check with uptime and dependencies |
| `GET` | `/api/metrics` | Application metrics (admin) |
| `POST` | `/api/auth/register` | User registration |
| `POST` | `/api/auth/login` | User login |
| `POST` | `/api/auth/logout` | User logout |
| `POST` | `/api/upload` | Upload and process PDFs |
| `GET` | `/api/download/<filename>` | Download processed file |
| `GET` | `/api/admin/users` | List all users (admin) |
| `POST` | `/api/admin/approve/<id>` | Approve user (admin) |
| `GET/POST` | `/api/admin/llm-settings` | LLM configuration (admin) |
| `GET` | `/api/admin/system-status` | System health (admin) |

## License

MIT License. See [LICENSE](LICENSE) for details.

---

Developed by [Dr. Junguk Hur](https://med.und.edu/research/labs/hur/index.html), Associate Professor, University of North Dakota School of Medicine and Health Sciences

*Last updated: March 22, 2026*
