#!/usr/bin/env python3
"""
Database migration script to add max_files_per_session column to users table.
Run this script to update the database schema.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import db
from backend.models.user import User

def migrate():
    """Add max_files_per_session column to users table if it doesn't exist."""
    try:
        # Check if column already exists
        result = db.engine.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in result]

        if 'max_files_per_session' not in columns:
            # Add the column
            db.engine.execute("ALTER TABLE users ADD COLUMN max_files_per_session INTEGER DEFAULT 5")
            print("Successfully added max_files_per_session column to users table")

            # Update existing users to have appropriate defaults
            # Approved users get 30, others get 5
            db.engine.execute("""
                UPDATE users
                SET max_files_per_session = CASE
                    WHEN is_approved = 1 THEN 30
                    ELSE 5
                END
            """)
            print("Updated existing users with appropriate file limits")
        else:
            print("max_files_per_session column already exists")

    except Exception as e:
        print(f"Migration failed: {e}")
        return False

    return True

if __name__ == "__main__":
    from backend.app import create_app
    app = create_app()

    with app.app_context():
        if migrate():
            print("Migration completed successfully")
        else:
            print("Migration failed")
            sys.exit(1)