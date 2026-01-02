# Product Documentation - ResearchPDFFileRenamerGLM

## Mission

Empower researchers and academics to maintain organized, searchable digital libraries by automating the tedious task of renaming research PDF files with standardized, meaningful filenames derived from AI-powered metadata extraction.

## Vision

A world where every researcher can effortlessly manage their growing collection of academic papers without spending countless hours manually renaming files. The system should understand scientific context, preserve important terminology like acronyms and tool names, and provide a seamless experience that respects user privacy and data ownership.

## User Personas

### Primary Persona: Academic Researcher
- **Profile**: Graduate students, postdoctoral researchers, and faculty members
- **Pain Points**:
  - Download dozens of PDFs weekly with cryptic filenames like "PMC123456.pdf" or "document(1).pdf"
  - Spend significant time manually renaming files to maintain searchable libraries
  - Difficulty finding papers later due to inconsistent naming conventions
  - Need to organize papers by author, year, and topic for literature reviews
- **Goals**:
  - Maintain organized digital library for research workflow
  - Quickly locate papers by author, year, or topic
  - Focus on research rather than file management

### Secondary Persona: Lab Manager
- **Profile**: Lab coordinators managing shared resources and reference collections
- **Pain Points**:
  - Aggregating papers from multiple researchers with inconsistent naming
  - Maintaining shared reference libraries for lab members
  - Ensuring consistent organization across team members
- **Goals**:
  - Standardize naming conventions across the lab
  - Enable easy sharing and discovery of papers
  - Reduce time spent on administrative file management

### Tertiary Persona: Casual Academic Reader
- **Profile**: Professionals who occasionally read academic papers
- **Pain Points**:
  - Small collection that still needs organization
  - Occasional use means they don't want complex setup
  - Want quick results without learning curve
- **Goals**:
  - Simple, one-time file renaming
  - No registration or account management overhead
  - Fast processing for small batches

## Problem Statement

Researchers accumulate hundreds of PDF files with meaningless filenames, making it impossible to locate specific papers quickly. Manual renaming is time-consuming and error-prone, requiring users to open each PDF, extract metadata, and construct consistent filenames. Existing solutions often require complex software installation, subscription fees, or compromise privacy by uploading entire documents to third-party services.

## Solution Approach

ResearchPDFFileRenamerGLM provides a web-based solution that:
- Extracts only the first 1-2 pages of text (not the full document) for privacy
- Uses AI to intelligently parse and extract author, year, title, and key terms
- Generates standardized filenames: `AuthorLastName_Year_KeyWords.pdf`
- Preserves important scientific terminology like acronyms (DPN, NF-kB) and tool names (DeepProfile)
- Processes multiple files in batch for efficiency
- Offers both anonymous access (limited) and registered user tiers
- Automatically cleans up uploaded files after processing

## Core Features

### 1. Drag & Drop Upload Interface
- Modern, intuitive file upload zone
- Visual feedback during drag operations
- Support for multiple files simultaneously
- Real-time upload progress indicators

### 2. AI-Powered Metadata Extraction
- Extracts author last name for filename prefix
- Identifies publication year
- Extracts title and generates meaningful keywords (up to 4)
- Preserves acronyms and scientific tool names
- Intelligent filtering of generic terms

### 3. Batch Processing
- Upload up to 5 files for anonymous users
- Upload up to 30 files for registered users
- Parallel processing for faster results
- Automatic ZIP download for multiple files

### 4. User Management
- Simple registration system
- Admin approval workflow for new users
- Usage tracking and limits
- Secure password storage with bcrypt

### 5. Privacy-First Design
- Only processes text from first 1-2 pages
- Files automatically deleted after download
- No permanent storage of user documents
- Optional local LLM support (Ollama) for complete privacy

## Success Metrics

### User Engagement
- **Daily Active Users**: Number of unique users processing files daily
- **Files Processed**: Total count of PDFs renamed
- **Average Batch Size**: Mean number of files per upload session
- **Return Rate**: Percentage of users who return within 30 days

### Quality Metrics
- **Renaming Accuracy**: User-reported satisfaction with generated filenames (target: 90%+)
- **Processing Success Rate**: Percentage of files successfully renamed (target: 95%+)
- **Keyword Preservation Rate**: Acronyms and tool names correctly preserved (target: 95%+)

### Performance Metrics
- **Processing Time**: Average time per file (target: <10 seconds)
- **API Cost Efficiency**: Cost per 1000 files processed
- **System Uptime**: Application availability percentage

## Business Goals

### Short-Term (3 months)
- Establish user base in academic community
- Achieve 1000+ files processed milestone
- Gather user feedback for feature prioritization
- Refine AI prompts for improved accuracy

### Medium-Term (6-12 months)
- Implement local LLM support for offline/privacy-focused users
- Add support for additional file formats (ePub, Word)
- Develop browser extension for direct web PDF downloads
- Reach 10,000+ files processed milestone

### Long-Term (12+ months)
- Expand to institutional deployments (self-hosted option)
- Integrate with reference management tools (Zotero, Mendeley)
- Develop API for integration with academic platforms
- Consider mobile application for on-the-go processing

## Competitive Differentiation

### vs. Manual Renaming
- **Time Savings**: Process 30 files in minutes vs. hours manually
- **Consistency**: Standardized format eliminates human error
- **Keyword Extraction**: AI identifies meaningful terms automatically

### vs. Competing Tools
- **Privacy Focus**: Only processes first 1-2 pages, not entire document
- **No Subscription**: Free and open-source, no recurring costs
- **Self-Hostable**: Can be deployed on own infrastructure
- **Acronym Preservation**: Unique capability to preserve scientific terminology
- **Simple Setup**: No complex dependencies or installation requirements

### vs. Reference Managers
- **Lightweight**: No full database setup required
- **Quick Batch**: Designed specifically for bulk renaming operations
- **No Commitment**: Can use without adopting entire reference management system

## Constraints and Considerations

### Technical Constraints
- Requires OpenAI API key for AI processing (or local LLM setup)
- PDF must have extractable text (scanned images not supported)
- 50MB file size limit per PDF
- Depends on third-party API availability and pricing

### Operational Constraints
- Anonymous users limited to 5 files per day to prevent abuse
- Requires internet connection for cloud-based processing
- Admin approval workflow for new user registrations
- Server storage limits require file cleanup after processing

### Regulatory Considerations
- No storage of user documents beyond processing window
- Compliance with data protection regulations (GDPR, etc.)
- Clear privacy policy and user agreement
- Optional local processing option for sensitive documents

## HISTORY

### Project Initialization (2025-12-31)
- Initial project documentation created
- Based on existing codebase analysis
- Project type: Web Application (AI-powered utility)
- Language: Python (Flask)
- Status: Active development with core features implemented

### Recent Improvements (December 2025)
- **Keyword Limit Fix**: Fixed issue where filenames had 5-6 keywords instead of 4
- **Acronym Preservation**: Enhanced detection of acronyms (DPN, NF-kB) and Greek letters
- **Tool Name Preservation**: Fixed filtering to preserve tool names like "DeepProfile"
- **Python 3.14 Compatibility**: Updated OpenAI library to v2.9.0 for Pydantic V2 support
