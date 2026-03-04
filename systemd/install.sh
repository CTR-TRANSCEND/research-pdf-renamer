#!/bin/bash
# Research PDF Renamer Production Installation Script
#
# ========================================================================
# SUDO REQUIRED ACTIONS:
# - Installing system packages (Python, pip, virtualenv, git)
# - Creating installation directory (/opt/pdf-renamer)
# - Creating systemd service file (/etc/systemd/system/)
# - Creating log directories (/var/log/pdf-renamer)
# - Creating lib directories (/var/lib/pdf-renamer)
# - Setting up logrotate configuration
# - Setting up Apache configuration (optional)
#
# USER-LEVEL ACTIONS (no sudo required):
# - Creating Python virtual environment
# - Installing Python packages from requirements.txt
# - Creating .env file
# - Setting database configuration
# ========================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
INSTALL_DIR="${INSTALL_DIR:-/opt/pdf-renamer}"
SERVICE_NAME="pdf-renamer"
LOG_DIR="/var/log/pdf-renamer"
LIB_DIR="/var/lib/pdf-renamer"
CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Research PDF Renamer - Production Install${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Function to print colored output
print_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
print_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check for required system dependencies
check_dependencies() {
    print_info "Checking system dependencies..."

    local missing_deps=()

    if ! command_exists python3; then
        missing_deps+=("python3")
    fi

    if ! command_exists pip3 && ! command_exists pip; then
        missing_deps+=("python3-pip")
    fi

    if ! command_exists git; then
        missing_deps+=("git")
    fi

    if [ ${#missing_deps[@]} -gt 0 ]; then
        print_error "Missing dependencies: ${missing_deps[*]}"
        echo ""
        echo -e "${YELLOW}The following actions require SUDO privileges:${NC}"
        echo "  - Install system packages: ${missing_deps[*]}"
        echo ""
        read -p "$(echo -e "${YELLOW}Install missing dependencies now? (y/N): ${NC}")" -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            sudo apt-get update
            sudo apt-get install -y python3 python3-pip python3-venv git
        else
            print_error "Cannot proceed without required dependencies."
            exit 1
        fi
    fi

    print_info "All dependencies are installed."
}

# Create installation directory
create_install_dir() {
    print_info "Creating installation directory at $INSTALL_DIR"

    if [ -d "$INSTALL_DIR" ]; then
        print_warn "Directory already exists. Updating existing installation."
    else
        echo ""
        echo -e "${YELLOW}The following actions require SUDO privileges:${NC}"
        echo "  - Create directory: $INSTALL_DIR"
        echo "  - Set ownership to www-data:www-data"
        echo ""
        read -p "$(echo -e "${YELLOW}Proceed? (y/N): ${NC}")" -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            sudo mkdir -p "$INSTALL_DIR"
            sudo chown -R www-data:www-data "$INSTALL_DIR"
            sudo chmod 755 "$INSTALL_DIR"
        else
            print_error "Cannot proceed without installation directory."
            exit 1
        fi
    fi

    # Copy application files
    print_info "Copying application files..."
    sudo rsync -av --exclude='venv' --exclude='__pycache__' --exclude='*.pyc' \
        --exclude='.git' --exclude='node_modules' --exclude='uploads' \
        --exclude='instance' --exclude='temp' \
        "$CURRENT_DIR/" "$INSTALL_DIR/"
    sudo chown -R www-data:www-data "$INSTALL_DIR"
}

# Create log and lib directories
create_system_dirs() {
    print_info "Creating system directories..."

    echo ""
    echo -e "${YELLOW}The following actions require SUDO privileges:${NC}"
    echo "  - Create log directory: $LOG_DIR"
    echo "  - Create lib directory: $LIB_DIR"
    echo "  - Set ownership to www-data:www-data"
    echo ""
    read -p "$(echo -e "${YELLOW}Proceed? (y/N): ${NC}")" -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sudo mkdir -p "$LOG_DIR" "$LIB_DIR"
        sudo chown -R www-data:www-data "$LOG_DIR" "$LIB_DIR"
        sudo chmod 755 "$LOG_DIR" "$LIB_DIR"
    else
        print_error "Cannot proceed without system directories."
        exit 1
    fi
}

# Setup Python virtual environment
setup_venv() {
    print_info "Setting up Python virtual environment..."

    if [ ! -d "$INSTALL_DIR/venv" ]; then
        print_info "Creating virtual environment..."
        sudo -u www-data python3 -m venv "$INSTALL_DIR/venv"
        print_info "Virtual environment created."
    else
        print_info "Virtual environment already exists."
    fi

    # Activate venv and install dependencies (user-level, no sudo)
    print_info "Installing Python dependencies..."
    source "$INSTALL_DIR/venv/bin/activate"
    pip install --upgrade pip wheel setuptools
    pip install -r "$INSTALL_DIR/requirements.txt"
    print_info "Python dependencies installed."
}

# Create .env file
create_env_file() {
    print_info "Creating environment configuration..."

    if [ ! -f "$INSTALL_DIR/.env" ]; then
        if [ -f "$INSTALL_DIR/.env.example" ]; then
            cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env"
        else
            cat > "$INSTALL_DIR/.env" << 'EOF'
# Flask Configuration
FLASK_APP=backend.app:create_app
FLASK_ENV=production
SECRET_KEY=CHANGE_THIS_TO_RANDOM_STRING

# Database Configuration (default: SQLite)
# For PostgreSQL: postgresql://user:password@localhost/dbname
# For MySQL: mysql+pymysql://user:password@localhost/dbname
DATABASE_URL=sqlite:///pdf-renamer.db

# LLM Provider Configuration
LLM_PROVIDER=openai
OPENAI_COMPATIBLE_API_KEY=your_api_key_here
OPENAI_COMPATIBLE_API_BASE=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini

# Ollama Configuration (if using local LLM)
OLLAMA_URL=http://localhost:11434

# SSRF Protection (DEPLOY-001)
# Set to 'true' to allow private IP addresses for LLM servers
# WARNING: Only enable in trusted environments
ALLOW_PRIVATE_IPS=false

# Admin Account Creation
# Set to 'true' to create default admin on first start
ADMIN_CREATE=false
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=change_me_immediately

# Application Settings
APPLICATION_ROOT=/pdf-renamer
MAX_CONTENT_LENGTH=104857600
INACTIVITY_TIMEOUT_MINUTES=30

# Session Security
SESSION_COOKIE_SECURE=false
SESSION_COOKIE_HTTPONLY=true
SESSION_COOKIE_SAMESITE=Lax
EOF
        fi

        print_warn ".env file created. Please edit with your configuration:"
        echo "  sudo nano $INSTALL_DIR/.env"
    else
        print_info ".env file already exists."
    fi
}

# Setup systemd service
setup_systemd() {
    print_info "Setting up systemd service..."

    echo ""
    echo -e "${YELLOW}The following actions require SUDO privileges:${NC}"
    echo "  - Copy systemd service file to /etc/systemd/system/"
    echo "  - Copy logrotate configuration to /etc/logrotate.d/"
    echo "  - Reload systemd daemon"
    echo "  - Enable service"
    echo ""
    read -p "$(echo -e "${YELLOW}Proceed? (y/N): ${NC}")" -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # Update paths in service file
        sed "s|/opt/pdf-renamer|$INSTALL_DIR|g" "$INSTALL_DIR/systemd/pdf-renamer.service" | \
        sudo tee /etc/systemd/system/$SERVICE_NAME.service >/dev/null

        # Install logrotate configuration
        if [ -f "$INSTALL_DIR/systemd/pdf-renamer.logrotate" ]; then
            sed "s|/opt/pdf-renamer|$INSTALL_DIR|g" "$INSTALL_DIR/systemd/pdf-renamer.logrotate" | \
            sudo tee /etc/logrotate.d/$SERVICE_NAME >/dev/null
        fi

        sudo systemctl daemon-reload
        sudo systemctl enable $SERVICE_NAME
        print_info "Systemd service installed and enabled."
    fi
}

# Setup Apache configuration (optional)
setup_apache() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}Apache Reverse Proxy Setup${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    print_info "Apache configuration is available in: $INSTALL_DIR/apache-pdf-renamer-enhanced.conf"
    echo ""
    echo -e "${YELLOW}To enable Apache reverse proxy:${NC}"
    echo "  1. Update paths in apache-pdf-renamer-enhanced.conf"
    echo "  2. Copy to /etc/apache2/sites-available/:"
    echo "     sudo cp $INSTALL_DIR/apache-pdf-renamer-enhanced.conf /etc/apache2/sites-available/"
    echo "  3. Enable required modules:"
    echo "     sudo a2enmod proxy proxy_http rewrite headers"
    echo "  4. Enable the site:"
    echo "     sudo a2ensite apache-pdf-renamer-enhanced.conf"
    echo "  5. Reload Apache:"
    echo "     sudo systemctl reload apache2"
    echo ""
}

# Print next steps
print_next_steps() {
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}Installation Complete!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo "Next steps:"
    echo ""
    echo "1. Edit .env file with your configuration:"
    echo "   sudo nano $INSTALL_DIR/.env"
    echo ""
    echo "2. Set proper SECRET_KEY (generate with: python3 -c 'import secrets; print(secrets.token_hex(32))')"
    echo ""
    echo "3. Start the service:"
    echo "   sudo systemctl start $SERVICE_NAME"
    echo ""
    echo "4. Check service status:"
    echo "   sudo systemctl status $SERVICE_NAME"
    echo ""
    echo "5. View logs:"
    echo "   sudo journalctl -u $SERVICE_NAME -f"
    echo "   tail -f $LOG_DIR/error.log"
    echo ""
    echo "6. Setup Apache reverse proxy (see above)"
    echo ""
    echo "For more information, see: $INSTALL_DIR/docs/deployment.md"
}

# Main installation flow
main() {
    check_dependencies
    create_install_dir
    create_system_dirs
    setup_venv
    create_env_file
    setup_systemd
    setup_apache
    print_next_steps
}

# Run main function
main
