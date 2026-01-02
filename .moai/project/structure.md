# Structure Documentation - ResearchPDFFileRenamerGLM

## Architecture Overview

ResearchPDFFileRenamerGLM follows a **modular monolithic architecture** pattern with clear separation of concerns between backend services, frontend presentation, and business logic layers. The application is built using Flask as the web framework with SQLAlchemy for data persistence and follows a service-oriented design for core functionality.

### Architecture Type: Modular Monolithic Web Application

The system is designed as a single deployable unit with well-defined module boundaries:
- **Backend Layer**: Flask application with RESTful API endpoints
- **Service Layer**: Business logic for PDF processing, LLM integration, and file management
- **Data Layer**: SQLite database with SQLAlchemy ORM (PostgreSQL-ready for production)
- **Frontend Layer**: Static HTML/CSS/JavaScript with drag-and-drop interface
- **Integration Layer**: External AI API integration (OpenAI/Ollama)

### Key Architectural Decisions

**Why Monolithic?**
- **Simplicity**: Single deployment unit reduces operational complexity
- **Development Speed**: Faster iteration without microservice coordination overhead
- **Resource Efficiency**: Lower infrastructure costs for small to medium user base
- **Sufficient Scale**: Expected load doesn't warrant distributed architecture complexity

**Why Modular Design?**
- **Maintainability**: Clear module boundaries enable easier updates and testing
- **Scalability Path**: Modules can be extracted to microservices if needed
- **Team Collaboration**: Multiple developers can work on different modules independently
- **Code Reusability**: Services can be shared across different endpoints

## Directory Structure and Module Relationships

```
ResearchPDFFileRenamerGLM/
├── backend/                      # Backend application layer
│   ├── app.py                    # Flask application factory and initialization
│   ├── config.py                 # Configuration management (dev/prod/test environments)
│   ├── models/                   # Database models (data layer)
│   │   ├── __init__.py           # Models initialization
│   │   ├── user.py               # User model (authentication, roles)
│   │   └── usage.py              # Usage tracking model (limits, statistics)
│   ├── routes/                   # API endpoints (controller layer)
│   │   ├── __init__.py           # Routes initialization
│   │   ├── main.py               # Main application routes (index, health)
│   │   ├── auth.py               # Authentication endpoints (login, register, logout)
│   │   ├── upload.py             # File upload and processing endpoints
│   │   └── admin.py              # Admin panel endpoints (user management)
│   ├── services/                 # Business logic (service layer)
│   │   ├── __init__.py           # Services initialization
│   │   ├── pdf_processor.py      # PDF text extraction (PyPDF2, pdfplumber)
│   │   ├── llm_service.py        # LLM API integration (OpenAI, Ollama)
│   │   └── file_service.py       # File handling (upload, download, cleanup)
│   ├── middleware/               # Request/response processing middleware
│   │   └── db_monitor.py         # Database connection monitoring
│   └── utils/                    # Utility functions and helpers
│       ├── __init__.py           # Utilities initialization
│       ├── auth.py               # Authentication utilities (JWT, password hashing)
│       ├── decorators.py         # Route decorators (login required, admin only)
│       └── validators.py         # Input validation (file types, sizes)
├── frontend/                     # Frontend presentation layer
│   ├── static/                   # Static assets
│   │   └── js/
│   │       └── main.js           # Frontend logic (drag-drop, AJAX)
│   └── templates/                # HTML templates (Jinja2)
│       ├── base.html             # Base template with common elements
│       └── index.html            # Main application page
├── migrations/                   # Database migration scripts
│   └── add_usage_indexes.py      # Performance optimization indexes
├── uploads/                      # Temporary file storage (gitignored)
│   └── downloads/                # Processed files awaiting download
├── temp/                         # Temporary processing files (gitignored)
├── instance/                     # Instance-specific data (gitignored)
│   └── app.db                    # SQLite database (development)
├── run.py                        # Application entry point
├── setup.sh                      # Setup and installation script
├── start.sh                      # Start script (created by setup)
├── requirements.txt              # Python dependencies
├── .gitignore                    # Git ignore patterns
├── README.md                     # User-facing documentation
├── README_DEVELOPMENT.md         # Development guide
├── UPDATE_NOTES.md               # Recent improvements and fixes
└── FIX_NOTES.md                  # Known issues and solutions
```

## Module Dependencies and Relationships

### Core Dependency Graph

```
                    ┌─────────────────┐
                    │     run.py      │
                    │  (Entry Point)  │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │   backend/app   │
                    │  (Flask Factory) │
                    └────────┬────────┘
                             │
            ┌────────────────┼────────────────┐
            │                │                │
            ▼                ▼                ▼
    ┌───────────────┐ ┌──────────────┐ ┌──────────────┐
    │    routes/    │ │   models/    │ │  services/   │
    │ (Controllers) │ │ (Data Layer) │ │ (Business    │
    └───────┬───────┘ └──────┬───────┘ │  Logic)     │
            │                 │         └──────┬───────┘
            │                 │                │
            ▼                 ▼                ▼
    ┌──────────────────────────────────────────────────┐
    │              utils/ and middleware/              │
    │         (Shared utilities and decorators)        │
    └──────────────────────────────────────────────────┘
```

### Layer Dependencies

**Routes Layer** (Controllers)
- Depends on: Models, Services, Utils
- Responsibility: HTTP request/response handling, routing
- Key Modules: main.py, auth.py, upload.py, admin.py

**Services Layer** (Business Logic)
- Depends on: Utils, External APIs (OpenAI, Ollama)
- Responsibility: Core business logic, data processing
- Key Modules: pdf_processor.py, llm_service.py, file_service.py

**Models Layer** (Data Access)
- Depends on: SQLAlchemy ORM
- Responsibility: Database schema, data persistence
- Key Modules: user.py, usage.py

**Utils Layer** (Shared Helpers)
- Depends on: External libraries (bcrypt, JWT, validators)
- Responsibility: Reusable utility functions
- Key Modules: auth.py, decorators.py, validators.py

## External System Integration

### OpenAI API Integration

**Purpose**: Extract metadata from PDF text (author, year, title, keywords)

**Integration Details**:
- **Protocol**: HTTPS REST API
- **Authentication**: API key (stored in APISetting.txt or environment variable)
- **Model**: gpt-4o-mini (configurable via LLM_MODEL environment variable)
- **Error Handling**: Retry logic with exponential backoff
- **Fallback**: Supports switching to Ollama for local LLM processing

**Data Flow**:
1. PDF text extracted from first 1-2 pages
2. Text sent to OpenAI API with structured prompt
3. Response parsed for author, year, title, keywords
4. Keywords filtered and ranked (acronym preservation, title overlap removal)
5. Metadata returned to file service for renaming

**Security Considerations**:
- Only first 1-2 pages sent (not full document)
- API key stored securely with restricted file permissions
- Rate limiting to prevent abuse
- No user document content stored permanently

### File System Integration

**Purpose**: Temporary storage for uploaded and processed files

**Directory Structure**:
- `uploads/`: Incoming user uploads
- `uploads/downloads/`: Processed files awaiting download
- `temp/`: Temporary processing artifacts

**Lifecycle Management**:
- Uploads stored for maximum 1 hour
- Download files stored for maximum 30 minutes
- Automatic cleanup via cron job or admin trigger
- Files deleted immediately after download

**Security Measures**:
- File type validation (PDF only)
- File size limits (50MB maximum)
- Sanitized filenames to prevent path traversal
- Restricted file permissions on upload directories

### Database Integration

**Current**: SQLite for development
- File: `instance/app.db`
- Benefits: Zero configuration, portable, simple backup
- Limitations: Single writer, no built-in replication

**Production Path**: PostgreSQL (migration-ready)
- Configuration via DATABASE_URL environment variable
- SQLAlchemy ORM abstracts database-specific SQL
- Migration scripts prepared for schema changes
- Connection pooling support via db_monitor.py

## Data Flow and API Design

### Request Flow Architecture

```
┌─────────┐      HTTP      ┌──────────────┐      Route      ┌─────────────┐
│ Browser │ ──────────────> │   Flask App  │ ──────────────> │   Routes    │
└─────────┘                 └──────────────┘                └──────┬──────┘
                                                                   │
                            ┌──────────────────────────────────────┘
                            │
                            ▼
                    ┌───────────────┐
                    │   Services    │
                    └───────┬───────┘
                            │
            ┌───────────────┼───────────────┐
            │               │               │
            ▼               ▼               ▼
    ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
    │ PDF Service  │ │ LLM Service  │ │ File Service │
    └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
           │                │                │
           ▼                ▼                ▼
    ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
    │  pdfplumber  │ │   OpenAI     │ │  File System │
    │   PyPDF2     │ │    API       │ │              │
    └──────────────┘ └──────────────┘ └──────────────┘
```

### Key API Endpoints

**Public Endpoints**
- `GET /`: Main application page
- `GET /api/limits`: Get current user upload limits (anonymous/authenticated)
- `GET /api/health`: Health check for monitoring

**Authentication Endpoints**
- `POST /api/auth/register`: User registration (creates pending user)
- `POST /api/auth/login`: User authentication (returns JWT token)
- `POST /api/auth/logout`: User session termination
- `GET /api/auth/me`: Get current user information (requires auth)
- `POST /api/auth/change-password`: Change user password (requires auth)

**File Processing Endpoints**
- `POST /api/upload`: Upload and process PDF files
  - Supports multiple files (5 anonymous, 30 authenticated)
  - Returns renamed files as download or ZIP
  - Enforces usage limits
  - Tracks usage statistics
- `GET /api/download/<filename>`: Download processed file
- `GET /api/usage-stats`: Get user usage statistics (requires auth)

**Admin Endpoints** (requires admin role)
- `GET /api/admin/pending`: List pending user registrations
- `POST /api/admin/approve/<id>`: Approve pending user
- `DELETE /api/admin/reject/<id>`: Reject pending user
- `GET /api/admin/users`: List all users with statistics
- `GET /api/admin/stats`: Admin dashboard statistics
- `POST /api/admin/cleanup`: Trigger manual file cleanup

### Request-Response Flow Example: File Upload

1. **Client Request**
   - Browser uploads PDF files via drag-and-drop
   - JavaScript sends FormData to `/api/upload` with authentication token

2. **Route Handler** (upload.py)
   - Validates authentication and usage limits
   - Validates file types and sizes
   - Calls file_service to save uploads

3. **Service Layer Processing**
   - pdf_processor extracts text from first 1-2 pages
   - llm_service sends text to OpenAI API
   - Response parsed for metadata (author, year, title, keywords)
   - file_service generates new filename and renames file

4. **Response**
   - Returns download URLs for processed files
   - Browser triggers automatic download (ZIP for multiple files)
   - Cleanup job scheduled for file deletion

## Non-Functional Requirements

### Performance Requirements

**Response Times**
- File upload response: <5 seconds for small files (<1MB)
- Processing time: <10 seconds per file average
- Page load time: <2 seconds for initial page load
- API response time: <500ms for non-processing endpoints

**Throughput**
- Support 10 concurrent file uploads
- Process 100 files per day per server instance
- Handle 1000+ registered users

**Resource Limits**
- Maximum file size: 50MB per PDF
- Maximum concurrent uploads: 5 files per request
- Memory usage: <512MB per worker process

### Security Requirements

**Authentication**
- Password hashing with bcrypt (cost factor 12)
- JWT token-based authentication
- Token expiration: 24 hours
- Secure session management

**Authorization**
- Role-based access control (user, admin)
- Admin-only endpoints protected
- User data isolation (usage tracking per user)

**Data Protection**
- API key stored with restricted permissions (chmod 600)
- No permanent storage of user documents
- Files auto-deleted after processing
- HTTPS required in production

**Input Validation**
- File type validation (PDF only)
- File size limits enforced
- SQL injection prevention via parameterized queries
- XSS prevention via template escaping

### Reliability Requirements

**Availability**
- Target uptime: 99% for development
- Graceful degradation if external APIs unavailable
- Database connection pooling with automatic retry

**Error Handling**
- Graceful error messages for users
- Detailed error logging for debugging
- Automatic cleanup of failed uploads
- Retry logic for transient API failures

**Data Integrity**
- Database transactions for multi-step operations
- Unique constraints on user email
- Atomic file operations (rename/delete)
- Usage tracking accuracy

### Maintainability Requirements

**Code Organization**
- Clear module boundaries
- DRY principle adherence
- Comprehensive code comments
- Consistent naming conventions

**Testing**
- Unit tests for service layer
- Integration tests for API endpoints
- Database test fixtures
- Mock external API calls

**Documentation**
- Inline documentation for complex logic
- API documentation
- Setup and deployment guides
- Changelog for version history

### Scalability Considerations

**Horizontal Scaling Path**
- Stateless application design enables multiple instances
- Session storage can be externalized (Redis)
- Database connection pooling supports increased load
- Static assets can be served via CDN

**Vertical Scaling Path**
- Gunicorn worker processes (multi-core utilization)
- Database indexing on frequently queried fields
- Caching layer for repeated queries
- Async processing for file operations (future enhancement)

## Architecture Decision Background

### Why Flask over Django?
- **Decision**: Flask framework selected
- **Rationale**:
  - Simpler for single-purpose application
  - More flexibility in architecture choices
  - Lower learning curve for small team
  - Sufficient built-in features without Django overhead
- **Trade-offs**: Less built-in admin, manual ORM setup (SQLAlchemy)

### Why SQLite over PostgreSQL (initially)?
- **Decision**: Start with SQLite, PostgreSQL-ready
- **Rationale**:
  - Zero configuration for development
  - Single-file database for easy backup/restore
  - Sufficient performance for initial user base
  - Easy migration path to PostgreSQL via SQLAlchemy
- **Trade-offs**: Single-writer limitation, no replication

### Why Client-Side JavaScript over Framework?
- **Decision**: Vanilla JavaScript for frontend
- **Rationale**:
  - Simple drag-and-drop requirements
  - No complex state management needs
  - Faster page loads without framework overhead
  - Easier debugging and maintenance
- **Trade-offs**: Manual DOM manipulation, no component reusability

### Why OpenAI API over Local-Only Processing?
- **Decision**: OpenAI API with optional local LLM support
- **Rationale**:
  - Superior extraction accuracy with GPT-4o-mini
  - Faster processing without local GPU requirements
  - Lower infrastructure costs for small deployments
  - Privacy preserved by only sending first 1-2 pages
- **Trade-offs**: API dependency, ongoing costs, requires internet

## Technical Constraints

### Browser Compatibility
- Modern browsers with Drag and Drop API support
- JavaScript ES6+ features
- Minimum browser versions: Chrome 90+, Firefox 88+, Safari 14+

### Python Version
- Python 3.10+ required
- Tested on Python 3.12 and 3.14
- OpenAI library v2.9.0+ for Pydantic V2 compatibility

### File Constraints
- PDF format only (no scanned images without OCR)
- Maximum file size: 50MB
- Text must be extractable (no password-protected PDFs)

### Deployment Constraints
- Linux-based servers (Ubuntu 20.04+, Debian 11+)
- Minimum 1GB RAM, 10GB disk space
- Python package manager (pip or uv)

## HISTORY

### Architecture Evolution (2025)
- **Initial Design**: Modular monolithic with Flask + SQLite
- **December 2025**: Database pooling optimization with db_monitor.py
- **December 2025**: Usage indexing added for performance
- **Current**: Production-ready with PostgreSQL migration path
