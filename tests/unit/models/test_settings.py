"""
Unit tests for the SystemSettings model.
"""

import pytest
from backend.models import SystemSettings
from cryptography.fernet import Fernet
import base64


class TestSystemSettingsModel:
    """Test SystemSettings model functionality."""

    def test_set_and_get_setting(self, db):
        """Test setting and getting a value."""
        SystemSettings.set_setting("test_key", "test_value", user_id=1)
        value = SystemSettings.get_setting("test_key")

        assert value == "test_value"

    def test_get_setting_default(self, db):
        """Test getting a non-existent setting returns default."""
        value = SystemSettings.get_setting("nonexistent_key", default="default_value")

        assert value == "default_value"

    def test_set_encrypted_setting(self, db):
        """Test setting an encrypted value."""
        SystemSettings.set_setting(
            "secret_key", "secret_value", encrypt=True, user_id=1
        )
        setting = SystemSettings.query.filter_by(key="secret_key").first()

        assert setting is not None
        assert setting.is_encrypted is True
        assert setting.value != "secret_value"  # Should be encrypted

    def test_get_encrypted_setting(self, db):
        """Test getting an encrypted value."""
        SystemSettings.set_setting(
            "secret_key", "secret_value", encrypt=True, user_id=1
        )
        value = SystemSettings.get_setting("secret_key")

        assert value == "secret_value"

    def test_update_existing_setting(self, db):
        """Test updating an existing setting."""
        SystemSettings.set_setting("test_key", "value1", user_id=1)
        SystemSettings.set_setting("test_key", "value2", user_id=2)
        value = SystemSettings.get_setting("test_key")

        assert value == "value2"

    def test_has_api_key(self, db):
        """Test checking if API key exists."""
        # Initially doesn't exist
        assert SystemSettings.has_api_key("openai") is False

        # Add API key
        SystemSettings.set_setting("openai_api_key", "sk-test-key", encrypt=True)
        assert SystemSettings.has_api_key("openai") is True

    def test_get_masked_api_key(self, db):
        """Test getting masked API key."""
        SystemSettings.set_setting(
            "openai_api_key", "sk-verysecretkey123", encrypt=True
        )
        masked = SystemSettings.get_masked_api_key("openai")

        # Should show first 4 and last 4 characters
        assert masked is not None
        assert masked.startswith("sk-")
        assert "123" in masked
        assert "verysecretkey" not in masked  # Middle should be masked
        assert "*" in masked  # Should have asterisks

    def test_get_masked_api_key_short(self, db):
        """Test getting masked API key for short key."""
        SystemSettings.set_setting("openai_api_key", "short", encrypt=True)
        masked = SystemSettings.get_masked_api_key("openai")

        # Short keys should be fully masked
        assert "*" * 10 in masked or len(masked) >= 10

    def test_get_api_key(self, db):
        """Test getting API key (decrypted)."""
        test_key = "sk-test-secret-key-12345"
        SystemSettings.set_setting("openai_api_key", test_key, encrypt=True)
        retrieved_key = SystemSettings.get_api_key("openai")

        assert retrieved_key == test_key

    def test_set_llm_provider(self, db):
        """Test setting LLM provider."""
        SystemSettings.set_llm_provider("openai", user_id=1)
        provider = SystemSettings.get_setting("llm_provider")

        assert provider == "openai"

    def test_set_llm_model(self, db):
        """Test setting LLM model."""
        SystemSettings.set_llm_model("gpt-4o-mini", user_id=1)
        model = SystemSettings.get_setting("llm_model")

        assert model == "gpt-4o-mini"

    def test_get_llm_settings(self, db):
        """Test getting all LLM settings."""
        SystemSettings.set_llm_provider("ollama", user_id=1)
        SystemSettings.set_llm_model("llama2", user_id=1)
        SystemSettings.set_setting("ollama_url", "http://localhost:11434", user_id=1)

        settings = SystemSettings.get_llm_settings()

        assert settings["provider"] == "ollama"
        assert settings["model"] == "llama2"
        assert settings["ollama_url"] == "http://localhost:11434"

    def test_encryption_decryption_roundtrip(self, db):
        """Test that encryption and decryption work correctly."""
        test_values = [
            "simple-string",
            "string with spaces",
            "special!@#$%^&*()characters",
            "unicode-characters-αβγ",
            "very" * 100,  # Long string
        ]

        for test_value in test_values:
            SystemSettings.set_setting("test_roundtrip", test_value, encrypt=True)
            retrieved = SystemSettings.get_setting("test_roundtrip")
            assert retrieved == test_value, f"Failed for: {test_value[:20]}"

    def test_encryption_with_different_secret_keys(self, db):
        """Test that decryption fails with different SECRET_KEY."""
        # Set with one SECRET_KEY
        SystemSettings.set_setting("sensitive", "secret_data", encrypt=True)

        # Simulate SECRET_KEY change by creating new cipher
        # (In real scenario, this would happen across app restarts)
        original_cipher = SystemSettings._get_cipher()
        SystemSettings._cipher = None

        # Change SECRET_KEY
        from flask import current_app

        current_app.config["SECRET_KEY"] = "different-secret-key"

        # Try to get the value
        value = SystemSettings.get_setting("sensitive")

        # Should fail to decrypt and return None
        assert value is None

        # Restore original cipher for other tests
        SystemSettings._cipher = original_cipher
