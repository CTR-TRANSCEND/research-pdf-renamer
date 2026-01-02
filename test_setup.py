#!/usr/bin/env python3
"""Test script to verify the application setup"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test if all modules can be imported"""
    print("Testing imports...")

    try:
        from backend.app import create_app
        print("✓ Flask app import successful")
    except ImportError as e:
        print(f"✗ Flask app import failed: {e}")
        return False

    try:
        from backend.models import User, Usage
        print("✓ Models import successful")
    except ImportError as e:
        print(f"✗ Models import failed: {e}")
        return False

    try:
        from backend.services import PDFProcessor, LLMService, FileService
        print("✓ Services import successful")
    except ImportError as e:
        print(f"✗ Services import failed: {e}")
        return False

    return True

def test_app_creation():
    """Test if Flask app can be created"""
    print("\nTesting app creation...")

    try:
        from backend.app import create_app
        app = create_app('development')
        print("✓ Flask app created successfully")

        # Test app context
        with app.app_context():
            from backend.models import db
            print("✓ App context works")

            # Test database
            db.create_all()
            print("✓ Database tables created")

        return True
    except Exception as e:
        print(f"✗ App creation failed: {e}")
        return False

def test_config():
    """Test configuration"""
    print("\nTesting configuration...")

    try:
        from backend.config import DevelopmentConfig, ProductionConfig

        # Check development config
        dev_config = DevelopmentConfig()
        assert dev_config.DEBUG == True
        print("✓ Development config loaded")

        # Check production config
        prod_config = ProductionConfig()
        assert prod_config.DEBUG == False
        print("✓ Production config loaded")

        return True
    except Exception as e:
        print(f"✗ Configuration test failed: {e}")
        return False

def test_services():
    """Test services initialization"""
    print("\nTesting services...")

    try:
        from backend.services import PDFProcessor, FileService
        from backend.config import DevelopmentConfig

        config = DevelopmentConfig()

        # Test PDF processor
        pdf_processor = PDFProcessor()
        print("✓ PDF Processor initialized")

        # Test file service
        file_service = FileService(config)
        print("✓ File Service initialized")

        # Test directories
        os.makedirs(file_service.upload_folder, exist_ok=True)
        os.makedirs(file_service.temp_folder, exist_ok=True)
        print("✓ Service directories created")

        return True
    except Exception as e:
        print(f"✗ Services test failed: {e}")
        return False

def check_requirements():
    """Check if required files exist"""
    print("\nChecking required files...")

    required_files = [
        'requirements.txt',
        'run.py',
        'backend/app.py',
        'backend/config.py',
        'backend/services/pdf_processor.py',
        'backend/services/llm_service.py',
        'backend/services/file_service.py',
        'frontend/templates/index.html',
        'frontend/static/js/main.js'
    ]

    missing = []
    for file in required_files:
        if os.path.exists(file):
            print(f"✓ {file}")
        else:
            print(f"✗ {file} - Missing!")
            missing.append(file)

    return len(missing) == 0

def check_api_key():
    """Check if API key is configured"""
    print("\nChecking API key configuration...")

    # Check environment variable
    if os.environ.get('OPENAI_API_KEY'):
        print("✓ OPENAI_API_KEY environment variable set")
        return True

    # Check APISetting.txt
    if os.path.exists('APISetting.txt'):
        with open('APISetting.txt', 'r') as f:
            key = f.read().strip()
            if key and key.startswith('sk-'):
                print("✓ APISetting.txt contains valid API key")
                return True
            else:
                print("✗ APISetting.txt exists but key is invalid")
    else:
        print("⚠ APISetting.txt not found (template available as APISetting.txt.example)")
        print("  Set OPENAI_API_KEY environment variable or create APISetting.txt")

    return False

def main():
    print("=" * 50)
    print("Research PDF File Renamer - Setup Test")
    print("=" * 50)

    tests = [
        ("Import Test", test_imports),
        ("App Creation Test", test_app_creation),
        ("Configuration Test", test_config),
        ("Services Test", test_services),
        ("File Check", check_requirements),
        ("API Key Check", check_api_key)
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"✗ {test_name} crashed: {e}")

    print("\n" + "=" * 50)
    print(f"Test Results: {passed}/{total} passed")
    print("=" * 50)

    if passed == total:
        print("\n✓ All tests passed! The application is ready to run.")
        print("\nTo start the application:")
        print("  ./start.sh")
        print("  or")
        print("  source venv/bin/activate && python run.py")
    else:
        print("\n⚠ Some tests failed. Please fix the issues above.")
        print("\nRun ./setup.sh to properly configure the application.")

    return passed == total

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)