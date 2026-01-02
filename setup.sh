#!/bin/bash

echo "========================================"
echo "Research PDF File Renamer Setup"
echo "========================================"

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed"
    exit 1
fi

# Check if we're in a conda environment
if [ -z "$CONDA_DEFAULT_ENV" ]; then
    echo "Warning: Not in a conda environment"
    echo "It's recommended to use a conda environment"
    echo ""
    echo "To create a conda environment:"
    echo "conda create -n pdf-renamer python=3.10"
    echo "conda activate pdf-renamer"
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Create necessary directories
echo "Creating directories..."
mkdir -p uploads/downloads
mkdir -p temp
mkdir -p instance

# Check API key file
if [ ! -f "APISetting.txt" ]; then
    echo ""
    echo "========================================"
    echo "API Key Setup"
    echo "========================================"
    echo "You need to set up your OpenAI API key"
    echo ""
    echo "Option 1: Set environment variable"
    echo "export OPENAI_API_KEY='sk-your-key-here'"
    echo ""
    echo "Option 2: Create APISetting.txt file"
    read -p "Would you like to create APISetting.txt now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        read -p "Enter your OpenAI API key: " api_key
        echo "$api_key" > APISetting.txt
        chmod 600 APISetting.txt
        echo "API key saved to APISetting.txt"
    fi
fi

# Initialize database
echo ""
echo "Initializing database..."
export FLASK_APP=run.py
flask db init 2>/dev/null || true
flask db migrate -m "Initial migration" 2>/dev/null || true
flask db upgrade

echo ""
echo "========================================"
echo "Setup Complete!"
echo "========================================"
echo ""
echo "To run the application:"
echo "1. Activate the virtual environment:"
echo "   source venv/bin/activate"
echo ""
echo "2. Run the application:"
echo "   python run.py"
echo ""
echo "Or simply run: ./start.sh"
echo ""

# Create start script
cat > start.sh << 'EOF'
#!/bin/bash
source venv/bin/activate
python run.py
EOF

chmod +x start.sh
echo "Created start.sh script for easy launching"