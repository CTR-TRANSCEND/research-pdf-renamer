#!/bin/bash

# Color definitions
RED='\e[0;31m'
GREEN='\e[0;32m'
YELLOW='\e[1;33m'
BLUE='\e[0;34m'
NC='\e[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Research PDF File Renamer Setup${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# ==============================================
# System Package Detection
# ==============================================

detect_package_manager() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        if command -v brew >/dev/null 2>&1; then
            echo "brew"
            return 0
        fi
    fi

    for pkgman in apt yum dnf pacman; do
        if command -v "$pkgman" >/dev/null 2>&1; then
            echo "$pkgman"
            return 0
        fi
    done

    echo "unknown"
    return 1
}

check_system_package() {
    local package="$1"
    local pkg_manager="$2"

    case $pkg_manager in
        "apt")
            dpkg -s "$package" >/dev/null 2>&1
            ;;
        "yum"|"dnf")
            rpm -q "$package" >/dev/null 2>&1
            ;;
        "pacman")
            pacman -Q "$package" >/dev/null 2>&1
            ;;
        "brew")
            brew list | grep -q "$package"
            ;;
        *)
            return 1
            ;;
    esac
}

# Optional system package installation
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}System Package Check${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

PACKAGE_MANAGER=$(detect_package_manager)
echo -e "Detected package manager: ${GREEN}$PACKAGE_MANAGER${NC}"
echo ""

# System packages that may be needed
SYSTEM_PACKAGES=("python3-venv" "python3-dev" "build-essential" "git")
MISSING_PACKAGES=()

for pkg in "${SYSTEM_PACKAGES[@]}"; do
    if ! check_system_package "$pkg" "$PACKAGE_MANAGER"; then
        MISSING_PACKAGES+=("$pkg")
    fi
done

if [ ${#MISSING_PACKAGES[@]} -gt 0 ]; then
    echo -e "${YELLOW}The following system packages are missing:${NC}"
    for pkg in "${MISSING_PACKAGES[@]}"; do
        echo "  - $pkg"
    done
    echo ""
    echo -e "${YELLOW}These may be required for full functionality.${NC}"
    echo ""
    read -p "$(echo -e "${YELLOW}Install missing packages now? (y/n): ${NC}")" -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${GREEN}Installing system packages...${NC}"
        case $PACKAGE_MANAGER in
            "apt")
                sudo apt-get update
                sudo apt-get install -y "${MISSING_PACKAGES[@]}"
                ;;
            "yum")
                sudo yum install -y "${MISSING_PACKAGES[@]}"
                ;;
            "dnf")
                sudo dnf install -y "${MISSING_PACKAGES[@]}"
                ;;
            "pacman")
                sudo pacman -S --noconfirm "${MISSING_PACKAGES[@]}"
                ;;
            "brew")
                brew install "${MISSING_PACKAGES[@]}"
                ;;
        esac
        echo -e "${GREEN}System packages installed successfully${NC}"
    else
        echo -e "${YELLOW}Skipping system package installation${NC}"
    fi
else
    echo -e "${GREEN}All required system packages are installed${NC}"
fi
echo ""

# Ask about Apache configuration upfront
echo -e "${YELLOW}Apache Reverse Proxy Configuration${NC}"
echo "This application can be accessed through Apache at:"
echo "  http://localhost/pdf-renamer/"
echo ""
echo "This requires sudo access to:"
echo "  - Create Apache configuration file"
echo "  - Enable required modules (proxy, proxy_http)"
echo "  - Restart Apache service"
echo ""
read -p "$(echo -e "${YELLOW}Do you want to set up Apache reverse proxy? (y/n): ${NC}")" -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    SETUP_APACHE=true
    echo -e "${GREEN}Apache configuration will be set up.${NC}"
else
    SETUP_APACHE=false
    echo -e "${YELLOW}Apache configuration skipped.${NC}"
fi
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is not installed${NC}"
    exit 1
fi

# ==============================================
# Conda Environment Check (Mandatory)
# ==============================================

if [ -z "$CONDA_DEFAULT_ENV" ]; then
    # Not in any conda environment
    echo -e "${RED}Error: Not in a conda environment${NC}"
    echo ""
    echo "This script requires a conda environment (not 'base')."
    echo ""
    echo "Options:"
    echo "1. Create and activate a new conda environment:"
    echo "   conda create -n pdf-renamer python=3.12"
    echo "   conda activate pdf-renamer"
    echo "   ./setup.sh"
    echo ""
    echo "2. Activate an existing conda environment:"
    echo "   conda activate <your-env-name>"
    echo "   ./setup.sh"
    exit 1
elif [ "$CONDA_DEFAULT_ENV" = "base" ]; then
    # In base environment - not allowed
    echo -e "${RED}Error: You are in the 'base' conda environment${NC}"
    echo ""
    echo "Using the 'base' environment is not recommended to avoid conflicts."
    echo ""
    echo "Would you like to create a dedicated environment?"
    read -p "$(echo -e "${YELLOW}Create new conda environment 'pdf-renamer'? (y/n): ${NC}")" -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        ENV_NAME="pdf-renamer"
        echo -e "${GREEN}Creating conda environment '${ENV_NAME}' with Python 3.12...${NC}"
        conda create -n "$ENV_NAME" python=3.12 -y
        echo ""
        echo -e "${GREEN}Environment created! Please activate it and run setup again:${NC}"
        echo "  conda activate $ENV_NAME"
        echo "  ./setup.sh"
        exit 0
    else
        echo -e "${YELLOW}Please activate a non-base conda environment and run setup again:${NC}"
        echo "  conda create -n pdf-renamer python=3.12"
        echo "  conda activate pdf-renamer"
        echo "  ./setup.sh"
        exit 1
    fi
else
    echo -e "${GREEN}Using conda environment: ${CONDA_DEFAULT_ENV}${NC}"
fi
echo ""

# ==============================================
# Python Environment Setup (Conda-Aware)
# ==============================================

# We're in a conda environment (non-base), use it directly
echo -e "${GREEN}Installing packages in current conda environment (${CONDA_DEFAULT_ENV})${NC}"
echo ""

# Upgrade pip
echo -e "${GREEN}Upgrading pip...${NC}"
pip install --upgrade pip

# Install dependencies
echo -e "${GREEN}Installing dependencies...${NC}"

# ERROR-PROOFING: Validate requirements.txt before installation
echo -e "${BLUE}Validating package versions...${NC}"
if python scripts/validate_requirements.py requirements.txt; then
    echo -e "${GREEN}All packages validated successfully${NC}"
else
    echo -e "${RED}Package validation failed. Please fix requirements.txt and try again.${NC}"
    echo ""
    echo -e "${YELLOW}Tip: Run 'python scripts/validate_requirements.py' to see detailed errors${NC}"
    exit 1
fi
echo -e "${GREEN}Installing dependencies...${NC}"
pip install -r requirements.txt

# Create necessary directories
echo -e "${GREEN}Creating directories...${NC}"
mkdir -p uploads/downloads
mkdir -p temp
mkdir -p instance

# Check .env file and API key
if [ ! -f ".env" ]; then
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}Environment Configuration${NC}"
    echo -e "${BLUE}========================================${NC}"

    if [ -f ".env.example" ]; then
        echo -e "${GREEN}Creating .env from .env.example template...${NC}"
        cp .env.example .env

        # Check if API key needs to be set
        if grep -q "sk-your-openai-api-key-here" .env 2>/dev/null || grep -q "your-api-key-here" .env 2>/dev/null; then
            echo ""
            echo -e "${YELLOW}IMPORTANT: You need to set your API key.${NC}"
            echo ""
            echo "Options:"
            echo "1. Edit .env file and add your API key"
            echo "2. Set API_KEY environment variable manually"
            echo ""
            read -p "Do you want to edit .env now? (y/n): " -n 1 -r
            echo ""
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                ${EDITOR:-nano} .env
            fi
        fi
    else
        echo -e "${YELLOW}Warning: .env.example not found. Creating minimal .env file...${NC}"
        cat > .env << 'EOF'
# Environment Variables for Research PDF File Renamer
# Set your API key below
API_KEY=your-api-key-here
EOF
        echo -e "${YELLOW}Created minimal .env file. Please edit it to add your API key.${NC}"
    fi
    echo ""
fi

# Initialize database
echo ""
echo -e "${GREEN}Initializing database...${NC}"
export FLASK_APP=run.py
if flask db --help >/dev/null 2>&1; then
    flask db init 2>/dev/null || true
    flask db migrate -m "Initial migration" 2>/dev/null || true
    flask db upgrade
else
    echo -e "${YELLOW}Flask-Migrate not installed; skipping 'flask db' steps.${NC}"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Setup Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "To run the application:"
echo "  ./start.sh"
echo ""

# Apache configuration
if [ "$SETUP_APACHE" = true ]; then
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}Apache Reverse Proxy Setup${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""

    # Check if Apache is installed
    if ! command -v apache2 &> /dev/null && ! command -v httpd &> /dev/null; then
        echo -e "${RED}Error: Apache is not installed${NC}"
        echo "Please install Apache first:"
        echo "  sudo apt install apache2  # For Debian/Ubuntu"
        echo "  sudo yum install httpd    # For RHEL/CentOS"
        exit 1
    fi

    # Detect Apache command
    APACHE_CMD="apache2"
    if command -v httpd &> /dev/null; then
        APACHE_CMD="httpd"
    fi

    # Determine Apache config directory
    if [ -d "/etc/apache2/sites-available" ]; then
        APACHE_CONF_DIR="/etc/apache2/sites-available"
        APACHE_ENABLE_CMD="a2ensite"
        APACHE_MODULE_CMD="a2enmod"
    elif [ -d "/etc/httpd/conf.d" ]; then
        APACHE_CONF_DIR="/etc/httpd/conf.d"
        APACHE_ENABLE_CMD=""
        APACHE_MODULE_CMD=""
    else
        echo -e "${RED}Error: Cannot determine Apache configuration directory${NC}"
        exit 1
    fi

    # Get the directory where this script is located
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

    # Apache configuration template
    APACHE_CONF_CONTENT="<VirtualHost *:80>
    ServerName localhost
    ServerAlias 127.0.0.1
    DocumentRoot /var/www/html
    # Research PDF File Renamer - Reverse Proxy Configuration
    # This routes requests from http://localhost/pdf-renamer/ to the Flask app

    # Enable proxy modules
    ProxyPreserveHost On

    # Proxy configuration for the application
    ProxyPass /pdf-renamer/ http://localhost:5000/pdf-renamer/
    ProxyPassReverse /pdf-renamer/ http://localhost:5000/pdf-renamer/

    # Set proper headers
    <Location /pdf-renamer/>
        ProxyPassReverse /
    </Location>

    # Optional: Enable for HTTPS (uncomment and configure)
    # <IfModule mod_ssl.c>
    #     <VirtualHost *:443>
    #         ServerName your-domain.com
    #         SSLEngine on
    #         SSLCertificateFile /path/to/cert.pem
    #         SSLCertificateKeyFile /path/to/key.pem
    #         ProxyPass /pdf-renamer/ https://localhost:5000/
    #         ProxyPassReverse /pdf-renamer/ https://localhost:5000/
    #     </VirtualHost>
    # </IfModule>
</VirtualHost>"

    # Create Apache config file
    APACHE_CONF_FILE="$APACHE_CONF_DIR/pdf-renamer.conf"

    echo -e "${YELLOW}This will require sudo access to:${NC}"
    echo "  1. Create Apache configuration at: $APACHE_CONF_FILE"
    echo "  2. Enable proxy modules (proxy, proxy_http)"
    echo "  3. Enable the site configuration"
    echo "  4. Restart Apache"
    echo ""
    read -p "$(echo -e "${YELLOW}Continue with Apache setup? (y/n): ${NC}")" -n 1 -r
    echo ""

    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Apache setup cancelled.${NC}"
        exit 0
    fi

    echo -e "${GREEN}Requesting sudo access...${NC}"
    sudo -k
    if ! sudo -v; then
        echo -e "${RED}Sudo authentication failed. Aborting Apache setup.${NC}"
        exit 1
    fi

    # Write Apache configuration
    echo -e "${GREEN}Creating Apache configuration...${NC}"
    echo "$APACHE_CONF_CONTENT" | sudo tee "$APACHE_CONF_FILE" > /dev/null

    if [ $? -ne 0 ]; then
        echo -e "${RED}Failed to create Apache configuration file${NC}"
        exit 1
    fi

    echo -e "${GREEN}Configuration file created: $APACHE_CONF_FILE${NC}"

    # Enable proxy modules
    echo ""
    echo -e "${GREEN}Enabling required Apache modules...${NC}"

    if [ -n "$APACHE_MODULE_CMD" ]; then
        sudo $APACHE_MODULE_CMD proxy
        sudo $APACHE_MODULE_CMD proxy_http
        sudo $APACHE_MODULE_CMD rewrite
    else
        echo -e "${YELLOW}Note: Please ensure proxy and proxy_http modules are enabled${NC}"
    fi

    # Enable the site
    echo ""
    echo -e "${GREEN}Enabling the site...${NC}"
    if [ -n "$APACHE_ENABLE_CMD" ]; then
        sudo $APACHE_ENABLE_CMD pdf-renamer.conf
    else
        echo -e "${YELLOW}Note: Site configuration is in $APACHE_CONF_FILE${NC}"
        echo -e "${YELLOW}Please ensure it is included in your Apache configuration${NC}"
    fi

    # Restart Apache
    echo ""
    echo -e "${GREEN}Restarting Apache...${NC}"
    if [ "$APACHE_CMD" = "apache2" ]; then
        sudo systemctl restart apache2
    else
        sudo systemctl restart httpd
    fi

    if [ $? -eq 0 ]; then
        echo ""
        echo -e "${GREEN}========================================${NC}"
        echo -e "${GREEN}Apache setup completed successfully!${NC}"
        echo -e "${GREEN}========================================${NC}"
        echo ""
        echo -e "Your application is now accessible at:"
        echo -e "  ${BLUE}http://localhost/pdf-renamer/${NC}"
        echo ""
        echo "The Flask app will still run on port 5000."
        echo "Make sure the Flask app is running before accessing via Apache."
        echo ""
        echo "To start the Flask app:"
        echo "  ./start.sh"
    else
        echo ""
        echo -e "${RED}Failed to restart Apache${NC}"
        echo "Please check the Apache error logs:"
        echo "  sudo journalctl -xe"
        echo "  or"
        echo "  sudo tail -f /var/log/$APACHE_CMD/error.log"
        exit 1
    fi
fi
