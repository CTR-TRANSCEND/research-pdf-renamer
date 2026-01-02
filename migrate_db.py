#!/usr/bin/env python3
"""
Database migration script to add missing columns to the users table.
"""

import sqlite3
import sys
from pathlib import Path

# Get the database path
db_path = Path(__file__).parent / 'instance' / 'app.db'

if not db_path.exists():
    print(f"Database not found at {db_path}")
    sys.exit(1)

print(f"Connecting to database: {db_path}")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    # Check if deactivated_at column exists
    cursor.execute("PRAGMA table_info(users)")
    columns = [row[1] for row in cursor.fetchall()]

    print(f"Current columns: {columns}")

    # Add deactivated_at column if it doesn't exist
    if 'deactivated_at' not in columns:
        print("Adding deactivated_at column...")
        cursor.execute("ALTER TABLE users ADD COLUMN deactivated_at DATETIME")
        print("✓ deactivated_at column added")
    else:
        print("✓ deactivated_at column already exists")

    # Check if max_files_per_session column exists
    if 'max_files_per_session' not in columns:
        print("Adding max_files_per_session column...")
        cursor.execute("ALTER TABLE users ADD COLUMN max_files_per_session INTEGER DEFAULT 5")
        print("✓ max_files_per_session column added")
    else:
        print("✓ max_files_per_session column already exists")

    # Check if auto_download column exists
    if 'auto_download' not in columns:
        print("Adding auto_download column...")
        cursor.execute("ALTER TABLE users ADD COLUMN auto_download BOOLEAN DEFAULT 1")
        print("✓ auto_download column added")
    else:
        print("✓ auto_download column already exists")

    # Check if filename_format column exists
    if 'filename_format' not in columns:
        print("Adding filename_format column...")
        cursor.execute("ALTER TABLE users ADD COLUMN filename_format VARCHAR(100) DEFAULT 'Author_Year_Journal_Keywords'")
        print("✓ filename_format column added")
    else:
        print("✓ filename_format column already exists")

    # Check if custom_filename_format column exists
    if 'custom_filename_format' not in columns:
        print("Adding custom_filename_format column...")
        cursor.execute("ALTER TABLE users ADD COLUMN custom_filename_format VARCHAR(200)")
        print("✓ custom_filename_format column added")
    else:
        print("✓ custom_filename_format column already exists")

    # Commit the changes
    conn.commit()
    print("\n✓ Migration completed successfully!")

    # Show updated table structure
    cursor.execute("PRAGMA table_info(users)")
    columns = cursor.fetchall()
    print("\nUpdated table structure:")
    for col in columns:
        print(f"  - {col[1]} ({col[2]})")

except Exception as e:
    print(f"Error during migration: {e}")
    conn.rollback()
    sys.exit(1)

finally:
    conn.close()
    print("\nDatabase connection closed.")