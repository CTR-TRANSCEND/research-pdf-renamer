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

# Check if we're in a conda environment
if [ -z "$CONDA_DEFAULT_ENV" ]; then
    echo -e "${YELLOW}Warning: Not in a conda environment${NC}"
    echo "It's recommended to use a conda environment"
    echo ""
    echo "To create a conda environment:"
    echo "  conda create -n pdf-renamer python=3.10"
    echo "  conda activate pdf-renamer"
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo -e "${GREEN}Creating virtual environment...${NC}"
    python3 -m venv venv
fi

# Activate virtual environment
echo -e "${GREEN}Activating virtual environment...${NC}"
source venv/bin/activate

# Upgrade pip
echo -e "${GREEN}Upgrading pip...${NC}"
pip install --upgrade pip

# Install dependencies
echo -e "${GREEN}Installing dependencies...${NC}"

# ERROR-PROOFING: Validate requirements.txt before installation
echo -e "${BLUE}Validating package versions...${NC}"
if python3 scripts/validate_requirements.py requirements.txt; then
    echo -e "${GREEN}All packages validated successfully${NC}"
else
    echo -e "${RED}Package validation failed. Please fix requirements.txt and try again.${NC}"
    echo ""
    echo -e "${YELLOW}Tip: Run 'python3 scripts/validate_requirements.py' to see detailed errors${NC}"
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
