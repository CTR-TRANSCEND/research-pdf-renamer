# Research PDF File Renamer

A web application that automatically renames academic/research PDF files using AI-powered metadata extraction. Upload your research papers and get them renamed with a standardized format: `AuthorLastName_Year_ShortTitle.pdf`

## Features

- **Drag & Drop Interface** - Modern, intuitive file upload with drag-and-drop support
- **AI-Powered Extraction** - Uses GPT-4o-mini to extract author, year, and title from papers
- **Batch Processing** - Upload multiple PDFs at once (up to 30 for registered users)
- **Privacy-First** - Only text from first 1-2 pages is sent to AI; files are deleted after download
- **User Management** - Registration system with admin approval
- **Usage Limits** - Anonymous users: 5 times per day; Registered users: 30 files unlimited

## Quick Start

### Prerequisites

- Python 3.10+
- OpenAI API key

### Installation

```bash
# Clone the repository
git clone https://github.com/windysky/ResearchPDFFileRenamer.git
cd ResearchPDFFileRenamer

# Install dependencies
pip install -r requirements.txt

# Add your OpenAI API key
echo "sk-your-api-key-here" > APISetting.txt
```

### Running the Server

```bash
python run.py
```

Access the application at http://localhost:5000

### Default Admin Account

- **Email:** admin@example.com
- **Password:** admin123

(Change this in production!)

## Project Structure

```
ResearchPDFFileRenamer/
├── backend/
│   ├── app.py              # Flask application
│   ├── config.py           # Configuration
│   ├── models/             # Database models
│   ├── routes/             # API endpoints
│   ├── services/           # Core services (PDF, LLM, File)
│   └── utils/              # Utilities
├── frontend/
│   ├── static/             # CSS and JavaScript
│   └── templates/          # HTML templates
├── run.py                  # Entry point
└── requirements.txt        # Python dependencies
```

## How It Works

1. **Upload** - Drag and drop PDF files onto the upload zone
2. **Extract** - System extracts text from first 1-2 pages (up to abstract)
3. **Analyze** - AI extracts author name, publication year, and title
4. **Rename** - Files are renamed to `AuthorLastName_Year_ShortTitle.pdf`
5. **Download** - Renamed files download automatically (as ZIP if multiple)
6. **Cleanup** - Original files are deleted from server

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_PROVIDER` | LLM provider (`openai` or `ollama`) | `openai` |
| `LLM_MODEL` | Model name | `gpt-4o-mini` |
| `SECRET_KEY` | Flask secret key | Auto-generated |

### Switching to Local LLM

```bash
export LLM_PROVIDER=ollama
export LLM_MODEL=llama3.2
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/upload` | Upload and process PDFs |
| GET | `/api/limits` | Get user's upload limits |
| POST | `/api/auth/login` | User login |
| POST | `/api/auth/register` | User registration |
| GET | `/api/admin/pending` | List pending users (admin) |
| POST | `/api/admin/approve/:id` | Approve user (admin) |

## License

MIT License
# ResearchPDFFileRenamerGLM
