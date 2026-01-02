from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import bcrypt
from backend.database import db

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    is_approved = db.Column(db.Boolean, default=False, nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False, server_default='1')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_login = db.Column(db.DateTime)
    deactivated_at = db.Column(db.DateTime)

    # User preferences
    filename_format = db.Column(db.String(100), default='Author_Year_Journal_Keywords')
    custom_filename_format = db.Column(db.String(200))
    auto_download = db.Column(db.Boolean, default=True)
    max_files_per_session = db.Column(db.Integer, default=5)  # Admin configurable limit

    # Relationships
    usage_logs = db.relationship('Usage', backref='user', lazy='dynamic', cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    def check_password(self, password):
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))

    def get_max_files(self):
        # Use user-specific limit if set, otherwise fall back to default based on approval status
        if self.max_files_per_session is not None:
            return self.max_files_per_session
        return 30 if self.is_approved else 5

    def is_user_active(self):
        """Check if user is active (both approved and not deactivated)."""
        return self.is_approved and self.is_active

    def __repr__(self):
        return f'<User {self.email}>'