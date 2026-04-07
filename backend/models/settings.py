from datetime import datetime, timezone
from backend.database import db
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
import logging
import base64

logger = logging.getLogger(__name__)

class SystemSettings(db.Model):
    """Store system-wide settings including LLM configuration and API keys."""

    __tablename__ = "system_settings"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False, index=True)
    value = db.Column(db.Text, nullable=True)
    is_encrypted = db.Column(db.Boolean, default=False, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )
    updated_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    # Encryption key derivation from SECRET_KEY
    _cipher = None
    _legacy_cipher = None

    @classmethod
    def _derive_key_hkdf(cls, secret_key: str) -> bytes:
        """
        Derive a 32-byte encryption key using HKDF (HMAC-based Key Derivation).

        This provides proper cryptographic key derivation with:
        - Input key material (IKM): SECRET_KEY encoded
        - Salt: None (HKDF will use default salt handling)
        - Info: Application-specific context binding
        - Length: 32 bytes (required by Fernet)

        SECURITY: This replaces the weak key derivation that used simple
        truncation and zero-padding, which provided no cryptographic security.
        """
        kdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=None,
            info=b"research-pdf-renamer-encryption",
        )
        return kdf.derive(secret_key.encode("utf-8"))

    @classmethod
    def _derive_key_legacy(cls, secret_key: str) -> bytes:
        """
        Legacy weak key derivation for backward compatibility.

        WARNING: This method is INSECURE and should only be used to decrypt
        existing values that were encrypted before the security fix.
        New values should always use _derive_key_hkdf().
        """
        return secret_key.encode("utf-8")[:32].ljust(32, b"0")

    @classmethod
    def _get_cipher(cls, legacy: bool = False):
        """
        Get or create the Fernet cipher for encryption.

        Args:
            legacy: If True, returns the legacy cipher for decrypting old values.
                    If False, returns the secure HKDF-derived cipher (default).

        Returns:
            Fernet cipher instance
        """
        from flask import current_app

        secret_key = current_app.config.get("SECRET_KEY")
        if not secret_key:
            raise RuntimeError("SECRET_KEY must be configured for API key encryption")

        if legacy:
            if cls._legacy_cipher is None:
                key_bytes = cls._derive_key_legacy(secret_key)
                fernet_key = base64.urlsafe_b64encode(key_bytes)
                cls._legacy_cipher = Fernet(fernet_key)
            return cls._legacy_cipher
        else:
            if cls._cipher is None:
                key_bytes = cls._derive_key_hkdf(secret_key)
                fernet_key = base64.urlsafe_b64encode(key_bytes)
                cls._cipher = Fernet(fernet_key)
            return cls._cipher

    @classmethod
    def get_setting(cls, key, default=None):
        """Get a setting value by key."""
        setting = cls.query.filter_by(key=key).first()
        if setting is None:
            return default

        if setting.is_encrypted:
            # Handle encrypted values with backward compatibility
            if not setting.value:
                # Empty value - record exists but no data
                logger.warning(f"Encrypted setting {key} has empty value")
                return default

            # Try secure HKDF-derived cipher first
            try:
                cipher = cls._get_cipher(legacy=False)
                decrypted = cipher.decrypt(setting.value.encode("utf-8"))
                return decrypted.decode("utf-8")
            except Exception as e:
                # If HKDF decryption fails, try legacy cipher for backward compatibility
                try:
                    cipher = cls._get_cipher(legacy=True)
                    decrypted = cipher.decrypt(setting.value.encode("utf-8"))
                    decrypted_value = decrypted.decode("utf-8")

                    # Auto-migrate: Re-encrypt with secure cipher on successful legacy decrypt
                    logger.info(f"Migrating {key} from legacy to secure encryption")
                    cls.set_setting(key, decrypted_value, encrypt=True, user_id=setting.updated_by)

                    return decrypted_value
                except Exception as legacy_error:
                    logger.error(
                        f"Error decrypting setting {key}: "
                        f"HKDF attempt: {type(e).__name__}: {e}, "
                        f"Legacy attempt: {type(legacy_error).__name__}: {legacy_error}. "
                        f"This may indicate a SECRET_KEY mismatch. The value was encrypted with a different key."
                    )
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
            # Always use secure HKDF-derived cipher for new encryptions
            cipher = cls._get_cipher(legacy=False)
            encrypted = cipher.encrypt(value.encode("utf-8"))
            setting.value = encrypted.decode("utf-8")
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
        key_name = f"{provider}_api_key"
        setting = cls.query.filter_by(key=key_name).first()
        return (
            setting is not None and setting.value is not None and len(setting.value) > 0
        )

    @classmethod
    def get_masked_api_key(cls, provider):
        """Get a masked version of the API key for display."""
        key_name = f"{provider}_api_key"
        actual_key = cls.get_setting(key_name)

        if not actual_key:
            return None

        # Show first 4 and last 4 characters, use fixed 10 asterisks in the middle
        if len(actual_key) <= 8:
            return "*" * 10
        else:
            return actual_key[:4] + "*" * 10 + actual_key[-4:]

    @classmethod
    def get_llm_settings(cls):
        """Get all LLM-related settings."""
        return {
            "provider": cls.get_setting("llm_provider", "openai"),
            "model": cls.get_setting("llm_model", "gpt-4o-mini"),
            "openai_api_key_set": cls.has_api_key("openai"),
            "openai_api_key_masked": cls.get_masked_api_key("openai"),
            "ollama_url": cls.get_setting("ollama_url", "http://localhost:11434"),
        }

    @classmethod
    def set_llm_provider(cls, provider, user_id=None):
        """Set the LLM provider."""
        cls.set_setting("llm_provider", provider, user_id=user_id)

    @classmethod
    def set_llm_model(cls, model, user_id=None):
        """Set the LLM model."""
        cls.set_setting("llm_model", model, user_id=user_id)

    @classmethod
    def set_api_key(cls, provider, api_key, user_id=None):
        """Set an API key for a provider (encrypted)."""
        key_name = f"{provider}_api_key"
        cls.set_setting(key_name, api_key, encrypt=True, user_id=user_id)

    @classmethod
    def get_api_key(cls, provider):
        """Get the API key for a provider (decrypted)."""
        key_name = f"{provider}_api_key"
        return cls.get_setting(key_name)

    @classmethod
    def get_provider_url(cls, provider):
        """Get the server URL for a provider."""
        url_map = {
            "ollama": ("ollama_url", "http://localhost:11434"),
            "openai-compatible": ("openai_compatible_url", "http://localhost:8000"),
            "lm-studio": ("lm_studio_url", "http://localhost:1234"),
        }
        setting_key, default_url = url_map.get(
            provider, ("ollama_url", "http://localhost:11434")
        )
        return cls.get_setting(setting_key, default_url)

    @classmethod
    def set_provider_url(cls, provider, url, user_id=None):
        """Set the server URL for a provider."""
        url_map = {
            "ollama": "ollama_url",
            "openai-compatible": "openai_compatible_url",
            "lm-studio": "lm_studio_url",
        }
        setting_key = url_map.get(provider, "ollama_url")
        cls.set_setting(setting_key, url, user_id=user_id)

    def __repr__(self):
        return f"<SystemSettings {self.key}>"
