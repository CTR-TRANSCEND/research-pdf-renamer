# Technology Documentation - ResearchPDFFileRenamerGLM

## Technology Stack Specifications

### Core Programming Language: Python 3.12+

**Version**: Python 3.12+ (tested up to Python 3.14.2)

**Why Python?**
- Extensive ecosystem for PDF processing and AI integration
- Simple syntax for rapid development
- Strong async/await support for future enhancements
- Wide availability of web frameworks and libraries

**Version Selection**:
- **Minimum**: Python 3.10 (required by modern dependencies)
- **Recommended**: Python 3.12 or 3.14 for latest features and performance
- **Development**: Python 3.12.0 (venv environment)
- **Compatible**: Python 3.14.2+ with OpenAI library v2.9.0+

### Web Framework: Flask 2.3.3

**Version**: Flask 2.3.3

**Why Flask?**
- Lightweight and flexible for single-purpose applications
- Minimal boilerplate for simple REST APIs
- Easy extension system for adding features as needed
- Large community and extensive documentation
- Simpler learning curve compared to Django

**Key Extensions**:
- **Flask-SQLAlchemy 3.0.5**: Database ORM and management
- **Flask-Login 0.6.3**: User session management and authentication
- **Flask-WTF 1.1.1**: Form handling and CSRF protection
- **WTForms 3.0.1**: Form validation and rendering

### Database: SQLite with SQLAlchemy ORM

**Development Database**: SQLite 3

**ORM**: SQLAlchemy 3.0.5 (via Flask-SQLAlchemy)

**Why SQLite for Development?**
- Zero configuration database
- Single-file storage for easy backup and portability
- Sufficient performance for development and small deployments
- Built-in Python support (no external dependencies)

**Production Path**: PostgreSQL 14+
- Migration-ready via SQLAlchemy database URL configuration
- Connection pooling support
- Superior concurrency for multiple users
- Replication and backup capabilities

**Database Schema**:
- **users table**: id, email, password_hash, role, is_approved, created_at
- **usage table**: id, user_id, upload_count, last_upload_date, daily_count

### PDF Processing Libraries

**Primary Library**: pdfplumber 0.9.0
- Purpose: Robust text extraction from PDF files
- Features: Accurate text positioning, font detection, multi-page support
- Used for: Main text extraction from first 1-2 pages

**Secondary Library**: PyPDF2 3.0.1
- Purpose: Additional PDF manipulation capabilities
- Features: Metadata extraction, page merging/splitting
- Used for: Fallback text extraction and PDF metadata

**Processing Strategy**:
1. Try pdfplumber first (more accurate)
2. Fall back to PyPDF2 if pdfplumber fails
3. Extract only first 1-2 pages to minimize data sent to AI
4. Limit extraction to approximately 2000 tokens for API efficiency

### AI/LLM Integration

**Primary Provider**: OpenAI API

**Library**: openai 2.9.0 (upgraded from 1.3.5 for Python 3.14 compatibility)

**Model**: gpt-4o-mini (default, configurable via LLM_MODEL environment variable)

**Why OpenAI?**
- Superior extraction accuracy for scientific metadata
- Fast response times (<5 seconds average)
- Cost-effective for small to medium usage
- Well-documented API with Python SDK
- Structured output support for reliable parsing

**Integration Details**:
- Authentication via API key (APISetting.txt or OPENAI_API_KEY environment variable)
- Retry logic with exponential backoff for transient failures
- Prompt engineering optimized for scientific paper metadata extraction
- Keyword filtering and ranking post-processing
- Acronym and tool name preservation logic

**Alternative Provider**: Ollama (future support)
- Local LLM processing for privacy-focused deployments
- Model: llama3.2 (configurable)
- Status: Infrastructure ready, implementation pending

### Authentication and Security

**Password Hashing**: bcrypt 4.0.1
- Cost factor: 12 (recommended for security/performance balance)
- Automatic salt generation
- Protection against rainbow table attacks

**JWT Tokens**: PyJWT 2.8.0
- Token-based authentication for API endpoints
- 24-hour expiration for access tokens
- HS256 algorithm for signature verification

**Email Validation**: email-validator 2.0.0
- RFC 5322 compliant email validation
- Domain validation and DNS checking
- Protection against invalid email registrations

### Web Server

**Development Server**: Flask built-in server
- Runs on localhost:5000 by default
- Auto-reload on code changes
- Debug mode enabled in development

**Production Server**: Gunicorn 21.2.0
- WSGI HTTP server for production deployment
- Multi-worker process support
- Automatic worker recycling for memory management
- Graceful shutdown handling

**Gunicorn Configuration** (recommended):
- Workers: 4 (2 x CPU cores + 1)
- Worker class: sync (can be upgraded to gevent for async)
- Worker timeout: 120 seconds
- Max requests: 1000 (recycle workers to prevent memory leaks)
- Max requests jitter: 100 (stagger worker recycling)

### Frontend Technologies

**HTML**: HTML5
- Semantic markup for accessibility
- Drag and Drop API for file uploads
- Form submission via JavaScript fetch API

**CSS**: Tailwind CSS (via CDN)
- Utility-first CSS framework
- Responsive design for mobile/desktop
- Custom styles via style attribute overrides

**JavaScript**: Vanilla JavaScript (ES6+)
- No framework dependencies
- Drag and drop event handling
- AJAX requests via fetch API
- Progress tracking for file uploads
- Dynamic UI updates

**No Build Process Required**:
- Frontend served as static files
- No npm, webpack, or build steps needed
- Simplifies deployment and maintenance

## Development Environment

### Build Tools and Package Management

**Package Manager**: pip (Python package installer)
- Virtual environment: venv module (built-in)
- Requirements file: requirements.txt with pinned versions
- Installation: `pip install -r requirements.txt`

**Virtual Environment**: Python venv
- Location: `./venv/` directory
- Activation: `source venv/bin/activate` (Linux/Mac) or `venv\Scripts\activate` (Windows)
- Isolation: Prevents system Python pollution
- Reproducible: Fixed dependency versions

**Setup Script**: setup.sh
- Automated environment setup
- Dependency installation
- Directory structure creation
- Database initialization
- API key configuration prompt

### Development Tools

**Code Editor**: VS Code (recommended)
- Python extension for IntelliSense
- Flask debugger support
- Git integration
- Terminal integration

**Debugging**: Flask debug mode
- Detailed error pages with stack traces
- Interactive debugger in browser
- Auto-reload on code changes

**Database Management**: SQLite command line
- Direct database inspection
- SQL query execution
- Schema verification

## Testing Strategy and Tools

**Testing Framework**: pytest (recommended for future implementation)

**Coverage Goal**: 80%+ minimum for service layer

**Test Types**:
- **Unit Tests**: Service layer functions (pdf_processor, llm_service, file_service)
- **Integration Tests**: API endpoints with test database
- **End-to-End Tests**: Full upload workflow with mock PDF files

**Testing Tools** (planned):
- **pytest**: Testing framework
- **pytest-cov**: Coverage reporting
- **pytest-flask**: Flask testing fixtures
- **pytest-mock**: Mock external API calls
- **factory-boy**: Test data generation

**Current Status**: Testing infrastructure not yet implemented. Priority for future development.

## CI/CD and Deployment Environment

### Version Control

**System**: Git
- Repository: GitHub
- Main branch: main
- Feature branches: Descriptive names (feature/add-ollama-support)
- Git ignore: Comprehensive .gitignore for Python, Flask, and MoAI files

### Deployment Options

**Option 1: Traditional Server (Current)**
- Platform: Linux VPS (Ubuntu 20.04+, Debian 11+)
- Web server: Nginx (reverse proxy) + Gunicorn (application server)
- Database: SQLite (development) or PostgreSQL (production)
- SSL: Let's Encrypt with certbot

**Option 2: Container Deployment (Future)**
- Containerization: Docker (Dockerfile to be created)
- Registry: Docker Hub or GitHub Container Registry
- Orchestration: Docker Compose for single-server deployment
- Kubernetes path: Available for scaling requirements

**Option 3: PaaS Deployment (Future)**
- Platform: Railway, Render, or Heroku
- Benefits: Zero infrastructure management
- Limitations: Less control over environment, potential egress costs

### Deployment Pipeline (Recommended)

**Staging Environment**:
- Branch: develop or staging
- Automatic deployment on push
- Database: Separate PostgreSQL instance
- Testing: Automated smoke tests

**Production Environment**:
- Branch: main
- Manual deployment approval required
- Database backups: Daily automated backups
- Monitoring: Uptime and error tracking
- Rollback: Previous version restoration capability

## Performance and Security Requirements

### Performance Requirements

**Response Times**:
- Page load: <2 seconds
- File upload response: <5 seconds
- Processing time: <10 seconds per file
- API response: <500ms for non-processing endpoints

**Throughput**:
- 10 concurrent uploads
- 100 files per day per instance
- 1000+ concurrent users (with horizontal scaling)

**Optimizations**:
- Database indexing on user_id, email, created_at
- Connection pooling for database connections
- Static asset caching via browser cache
- Gzip compression for API responses

### Security Requirements

**Authentication Security**:
- Password hashing: bcrypt with cost factor 12
- JWT token expiration: 24 hours
- Secure session management
- Protection against session fixation

**API Security**:
- API key storage: File with restricted permissions (chmod 600)
- Environment variable support: OPENAI_API_KEY
- No hardcoded credentials in source code
- Rate limiting: Usage limits per user tier

**Data Protection**:
- File storage: Temporary only (auto-delete after 1 hour)
- Download storage: Auto-delete after 30 minutes
- No permanent user document storage
- Privacy-first: Only first 1-2 pages processed

**Input Validation**:
- File type validation: PDF only
- File size limit: 50MB maximum
- SQL injection prevention: Parameterized queries
- XSS prevention: Template escaping

**HTTPS/TLS**:
- Required in production
- TLS 1.2+ only
- Strong cipher suites
- HSTS header enabled

### Security Best Practices

**Secrets Management**:
- SECRET_KEY: Environment variable or strong random value
- API keys: Never commit to version control
- Password reset tokens: Secure random generation
- Database credentials: Environment-specific configuration

**Dependencies**:
- Regular security updates: `pip install --upgrade <package>`
- Vulnerability scanning: pip-audit or safety
- Pinned versions in requirements.txt
- Dependency review for new packages

**File Security**:
- Upload directory: Outside web root
- Filename sanitization: Prevent path traversal
- File permissions: Restricted read/write for application only
- Cleanup jobs: Regular deletion of expired files

## Technical Constraints and Considerations

### Browser Compatibility

**Minimum Requirements**:
- Chrome 90+, Firefox 88+, Safari 14+, Edge 90+
- JavaScript ES6+ support
- Drag and Drop API support
- Fetch API support

**Graceful Degradation**:
- Fallback to file input if drag-drop not available
- Error messages for unsupported browsers
- Mobile-responsive design

### PDF Processing Constraints

**Supported PDFs**:
- Text-based PDFs (not scanned images)
- PDF version 1.4+ (PDF 2.0 support varies)
- Maximum file size: 50MB
- Maximum pages: Unlimited (only first 1-2 pages processed)

**Unsupported PDFs**:
- Scanned images without OCR layer
- Password-protected PDFs
- Corrupted or invalid PDF format
- PDFs with non-extractable text (image-only)

### LLM API Constraints

**OpenAI API**:
- Rate limits: 3,000 RPM for gpt-4o-mini
- Token limits: 128,000 tokens per request
- Cost: Approximately $0.15 per 1M input tokens
- Availability: 99.9% uptime SLA
- Requires internet connection

**Ollama (Future)**:
- Local processing only
- Requires sufficient RAM: 8GB+ for llama3.2
- No internet required
- Slower processing than OpenAI API
- No API costs

### Deployment Constraints

**Server Requirements**:
- Operating System: Linux (Ubuntu 20.04+, Debian 11+, RHEL 8+)
- Python: 3.10+ (3.12+ recommended)
- RAM: 1GB minimum, 2GB recommended
- Disk: 10GB minimum for logs and temporary files
- CPU: 2 cores minimum, 4 cores recommended

**Network Requirements**:
- Outbound HTTPS for OpenAI API (api.openai.com:443)
- Inbound HTTPS/HTTP for user access (port 80/443)
- Optional: SMTP server for email notifications

**Storage Requirements**:
- Database: 100MB for 10,000 users
- Uploads: Variable (based on user activity, auto-cleanup)
- Logs: 100MB per month (with 30-day retention)
- Application: 500MB including virtual environment

## Dependency Versions

### Core Dependencies (requirements.txt)

```
Flask==2.3.3                    # Web framework
Flask-SQLAlchemy==3.0.5         # Database ORM
Flask-Login==0.6.3              # User authentication
Flask-WTF==1.1.1                # Form handling
WTForms==3.0.1                  # Form validation
Werkzeug==2.3.7                 # WSGI utility library
PyPDF2==3.0.1                   # PDF processing (secondary)
pdfplumber==0.9.0               # PDF processing (primary)
openai==2.9.0                   # OpenAI API client (upgraded for Python 3.14)
python-dotenv==1.0.0            # Environment variable management
bcrypt==4.0.1                   # Password hashing
PyJWT==2.8.0                    # JWT token handling
email-validator==2.0.0          # Email validation
gunicorn==21.2.0                # Production WSGI server
```

### Development Tools (Optional)

```
pytest==7.4.0                   # Testing framework (recommended)
pytest-cov==4.1.0               # Coverage reporting (recommended)
pytest-flask==1.2.0             # Flask testing fixtures (recommended)
pytest-mock==3.11.1             # Mock utilities (recommended)
black==23.7.0                   # Code formatting (recommended)
flake8==6.0.0                   # Linting (recommended)
mypy==1.4.1                     # Type checking (recommended)
```

## Monitoring and Observability

### Current Monitoring

**Application Logging**:
- Flask development server logs
- Error output to console
- No structured logging yet

**Database Monitoring**:
- db_monitor.py middleware for connection health
- Usage tracking via database queries

### Future Enhancements

**Application Performance Monitoring (APM)**:
- Sentry for error tracking
- Datadog or New Relic for performance metrics
- Application logs aggregation

**Infrastructure Monitoring**:
- Prometheus for metrics collection
- Grafana for dashboards
- Alertmanager for notifications

**User Analytics**:
- Files processed per day
- User registration trends
- Processing success rates
- API usage statistics

## Backup and Recovery

### Database Backup Strategy

**Development (SQLite)**:
- Manual backup: Copy `instance/app.db` file
- Automated backup: Cron job to copy to backup directory
- Retention: 7 days

**Production (PostgreSQL)**:
- Automated daily backups via pg_dump
- Point-in-time recovery enabled
- Off-site backup storage (S3 or similar)
- Backup retention: 30 days

### Disaster Recovery

**Recovery Time Objective (RTO)**: 4 hours
**Recovery Point Objective (RPO)**: 24 hours

**Recovery Steps**:
1. Restore database from latest backup
2. Redeploy application from version control
3. Configure environment variables
4. Test system functionality
5. Switch DNS to recovered instance

## HISTORY

### Technology Evolution (2025)
- **Initial Setup**: Flask 2.3.3 + SQLite + OpenAI 1.3.5
- **December 2025**: OpenAI library upgraded to 2.9.0 for Python 3.14 compatibility
- **December 2025**: Database pooling optimization implemented
- **December 2025**: Usage indexing added for performance
- **Current**: Stable stack with Python 3.12+ support
