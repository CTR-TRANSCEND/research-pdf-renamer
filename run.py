#!/usr/bin/env python3
import os
import sys
from backend.app import create_app

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    # Set environment
    env = os.environ.get('FLASK_ENV', 'development')
    app = create_app(env)

    # Get host and port from environment or use defaults
    host = os.environ.get('HOST', '127.0.0.1')
    port = int(os.environ.get('PORT', 5000))

    print(f"""
    ========================================
    Research PDF File Renamer
    ========================================
    Environment: {env}
    URL: http://{host}:{port}
    ========================================
    """)

    # Run the app
    if env == 'production':
        app.run(host=host, port=port)
    else:
        app.run(host=host, port=port, debug=True)

if __name__ == '__main__':
    main()