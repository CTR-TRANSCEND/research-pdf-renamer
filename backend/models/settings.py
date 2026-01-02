from datetime import datetime
from backend.database import db
from cryptography.fernet import Fernet
import os
import base64

class SystemSettings(db.Model):
    """Store system-wide settings including LLM configuration and API keys."""
    __tablename__ = 'system_settings'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False, index=True)
    value = db.Column(db.Text, nullable=True)
    is_encrypted = db.Column(db.Boolean, default=False, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    # Encryption key derivation from SECRET_KEY
    _cipher = None

    @classmethod
    def _get_cipher(cls):
        """Get or create the Fernet cipher for encryption."""
        if cls._cipher is None:
            from flask import current_app
            secret_key = current_app.config.get('SECRET_KEY', 'default-secret-key')
            # Derive a 32-byte key from the secret key
            key_bytes = secret_key.encode('utf-8')[:32].ljust(32, b'0')
            fernet_key = base64.urlsafe_b64encode(key_bytes)
            cls._cipher = Fernet(fernet_key)
        return cls._cipher

    @classmethod
    def get_setting(cls, key, default=None):
        """Get a setting value by key."""
        setting = cls.query.filter_by(key=key).first()
        if setting is None:
            return default

        if setting.is_encrypted and setting.value:
            try:
                cipher = cls._get_cipher()
                decrypted = cipher.decrypt(setting.value.encode('utf-8'))
                return decrypted.decode('utf-8')
            except Exception as e:
                print(f"Error decrypting setting {key}: {e}")
                return default

        return setting.value

    @classmethod
    def set_setting(cls, key, value, encrypt=False, user_id=None):
        """Set a setting value."""
        setting = cls.query.filter_by(key=key).first()

        if setting is None:
            setting = cls(key=key)
            db.session.add(setting)

        if encrypt and value:
            cipher = cls._get_cipher()
            encrypted = cipher.encrypt(value.encode('utf-8'))
            setting.value = encrypted.decode('utf-8')
            setting.is_encrypted = True
        else:
            setting.value = value
            setting.is_encrypted = False

        setting.updated_by = user_id
        db.session.commit()
        return setting

    @classmethod
    def has_api_key(cls, provider):
        """Check if an API key exists for a provider (without revealing the key)."""
        key_name = f'{provider}_api_key'
        setting = cls.query.filter_by(key=key_name).first()
        return setting is not None and setting.value is not None and len(setting.value) > 0

    @classmethod
    def get_masked_api_key(cls, provider):
        """Get a masked version of the API key for display."""
        key_name = f'{provider}_api_key'
        actual_key = cls.get_setting(key_name)

        if not actual_key:
            return None

        # Show first 4 and last 4 characters, use fixed 10 asterisks in the middle
        if len(actual_key) <= 8:
            return '*' * 10
        else:
            return actual_key[:4] + '*' * 10 + actual_key[-4:]

    @classmethod
    def get_llm_settings(cls):
        """Get all LLM-related settings."""
        return {
            'provider': cls.get_setting('llm_provider', 'openai'),
            'model': cls.get_setting('llm_model', 'gpt-4o-mini'),
            'openai_api_key_set': cls.has_api_key('openai'),
            'openai_api_key_masked': cls.get_masked_api_key('openai'),
            'ollama_url': cls.get_setting('ollama_url', 'http://localhost:11434'),
        }

    @classmethod
    def set_llm_provider(cls, provider, user_id=None):
        """Set the LLM provider."""
        cls.set_setting('llm_provider', provider, user_id=user_id)

    @classmethod
    def set_llm_model(cls, model, user_id=None):
        """Set the LLM model."""
        cls.set_setting('llm_model', model, user_id=user_id)

    @classmethod
    def set_api_key(cls, provider, api_key, user_id=None):
        """Set an API key for a provider (encrypted)."""
        key_name = f'{provider}_api_key'
        cls.set_setting(key_name, api_key, encrypt=True, user_id=user_id)

    @classmethod
    def get_api_key(cls, provider):
        """Get the API key for a provider (decrypted)."""
        key_name = f'{provider}_api_key'
        return cls.get_setting(key_name)

    def __repr__(self):
        return f'<SystemSettings {self.key}>'
