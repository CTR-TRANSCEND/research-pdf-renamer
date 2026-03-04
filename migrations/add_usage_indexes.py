"""Migration script to add performance indexes to the Usage table."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone
from backend.database import db
from backend.models import Usage
from sqlalchemy import text

def upgrade():
    """Add performance indexes to the Usage table."""
    from backend.app import create_app
    app = create_app()
    with app.app_context():
        try:
            # Check if indexes already exist
            inspector = db.inspect(db.engine)
            indexes = inspector.get_indexes('usage')
            index_names = [idx['name'] for idx in indexes]

            # Add composite indexes for common query patterns
            if 'idx_user_timestamp' not in index_names:
                db.session.execute(text("""
                    CREATE INDEX idx_user_timestamp
                    ON usage (user_id, timestamp)
                """))
                print("Created idx_user_timestamp index")

            if 'idx_user_timestamp_files' not in index_names:
                db.session.execute(text("""
                    CREATE INDEX idx_user_timestamp_files
                    ON usage (user_id, timestamp, files_processed)
                """))
                print("Created idx_user_timestamp_files index")

            db.session.commit()
            print("✅ Database indexes added successfully")

        except Exception as e:
            print(f"❌ Error adding indexes: {e}")
            db.session.rollback()
            raise

def downgrade():
    """Remove the added indexes."""
    from backend.app import create_app
    app = create_app()
    with app.app_context():
        try:
            db.session.execute(text("DROP INDEX IF EXISTS idx_user_timestamp"))
            db.session.execute(text("DROP INDEX IF EXISTS idx_user_timestamp_files"))
            db.session.commit()
            print("✅ Indexes removed successfully")
        except Exception as e:
            print(f"❌ Error removing indexes: {e}")
            db.session.rollback()
            raise

if __name__ == "__main__":
    print(f"Running index migration at {datetime.now(timezone.utc)}")
    upgrade()