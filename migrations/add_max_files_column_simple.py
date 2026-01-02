#!/usr/bin/env python3
"""
Database migration script to add max_files_per_session column to users table.
This version works with SQLite directly without loading the Flask app.
"""

import sqlite3
import os

def migrate():
    """Add max_files_per_session column to users table if it doesn't exist."""
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'instance', 'app.db')

    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return False

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if column already exists
        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]

        if 'max_files_per_session' not in columns:
            # Add the column
            cursor.execute("ALTER TABLE users ADD COLUMN max_files_per_session INTEGER DEFAULT 5")
            print("Successfully added max_files_per_session column to users table")

            # Update existing users to have appropriate defaults
            # Approved users get 30, others get 5
            cursor.execute("""
                UPDATE users
                SET max_files_per_session = CASE
                    WHEN is_approved = 1 THEN 30
                    ELSE 5
                END
            """)
            print("Updated existing users with appropriate file limits")

            conn.commit()
        else:
            print("max_files_per_session column already exists")

    except Exception as e:
        print(f"Migration failed: {e}")
        return False
    finally:
        conn.close()

    return True

if __name__ == "__main__":
    if migrate():
        print("Migration completed successfully")
    else:
        print("Migration failed")
        exit(1)