from datetime import datetime, timezone
from backend.database import db

class Usage(db.Model):
    __tablename__ = 'usage'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # Null for anonymous users
    ip_address = db.Column(db.String(45), nullable=False, index=True)  # IPv6 compatible
    user_agent = db.Column(db.Text)
    files_processed = db.Column(db.Integer, default=0, nullable=False)
    success = db.Column(db.Boolean, default=True, nullable=False)  # Whether processing was successful
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    # Composite indexes for common query patterns
    __table_args__ = (
        db.Index('idx_user_timestamp', 'user_id', 'timestamp'),
        db.Index('idx_user_timestamp_files', 'user_id', 'timestamp', 'files_processed'),
    )

    def __repr__(self):
        user_info = f"User {self.user_id}" if self.user_id else f"Anonymous ({self.ip_address})"
        return f'<Usage {user_info}: {self.files_processed} files at {self.timestamp}>'