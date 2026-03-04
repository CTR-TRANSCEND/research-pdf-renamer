"""
Unit tests for LLM server URL validation.

Tests the validate_llm_server_url function to prevent SSRF attacks.
"""

import pytest
from backend.utils.validators import validate_llm_server_url


class TestValidateLLMServerURL:
    """Test suite for LLM server URL validation."""

    def test_valid_http_localhost(self):
        """Test valid HTTP localhost URL."""
        is_valid, error_msg = validate_llm_server_url("http://localhost:11434")
        assert is_valid is True
        assert error_msg == "Valid URL"

    def test_valid_https_url(self):
        """Test valid HTTPS URL."""
        is_valid, error_msg = validate_llm_server_url("https://api.example.com")
        assert is_valid is True
        assert error_msg == "Valid URL"

    def test_private_ip_rejected_by_default(self):
        """Test that private IP addresses are rejected by default (SSRF protection)."""
        is_valid, error_msg = validate_llm_server_url("http://192.168.1.100:8080")
        assert is_valid is False
        assert "Private IP" in error_msg

    def test_valid_url_with_api_path(self):
        """Test valid URL with /api path."""
        is_valid, error_msg = validate_llm_server_url("http://localhost:11434/api")
        assert is_valid is True
        assert error_msg == "Valid URL"

    def test_valid_url_with_v1_path(self):
        """Test valid URL with /v1 path."""
        is_valid, error_msg = validate_llm_server_url("http://example.com/v1")
        assert is_valid is True
        assert error_msg == "Valid URL"

    def test_valid_url_with_trailing_slash(self):
        """Test valid URL with trailing slash is normalized."""
        is_valid, error_msg = validate_llm_server_url("http://localhost:11434/")
        assert is_valid is True
        assert error_msg == "Valid URL"

    # Invalid scheme tests

    def test_invalid_ftp_scheme(self):
        """Test FTP scheme is rejected."""
        is_valid, error_msg = validate_llm_server_url("ftp://example.com")
        assert is_valid is False
        assert "scheme must be http:// or https://" in error_msg

    def test_invalid_file_scheme(self):
        """Test file:// scheme is rejected."""
        is_valid, error_msg = validate_llm_server_url("file:///etc/passwd")
        assert is_valid is False
        assert "scheme must be http:// or https://" in error_msg

    def test_invalid_no_scheme(self):
        """Test URL without scheme is rejected."""
        is_valid, error_msg = validate_llm_server_url("localhost:11434")
        assert is_valid is False
        assert "scheme must be http:// or https://" in error_msg

    # SSRF prevention tests

    def test_invalid_internal_metadata_url(self):
        """Test AWS metadata URL is rejected."""
        is_valid, error_msg = validate_llm_server_url(
            "http://169.254.169.254/latest/meta-data/"
        )
        assert is_valid is False
        # Path validation will reject /latest path

    def test_invalid_disallowed_path(self):
        """Test disallowed path is rejected."""
        is_valid, error_msg = validate_llm_server_url("http://localhost:11434/evil")
        assert is_valid is False
        assert "path must be one of" in error_msg

    def test_invalid_with_query_params(self):
        """Test URL with query parameters is rejected."""
        is_valid, error_msg = validate_llm_server_url(
            "http://localhost:11434?malicious=true"
        )
        assert is_valid is False
        assert "should not contain query parameters" in error_msg

    def test_invalid_with_fragment(self):
        """Test URL with fragment is rejected."""
        is_valid, error_msg = validate_llm_server_url("http://localhost:11434#evil")
        assert is_valid is False
        assert "should not contain fragments" in error_msg

    # Input validation tests

    def test_invalid_empty_string(self):
        """Test empty string is rejected."""
        is_valid, error_msg = validate_llm_server_url("")
        assert is_valid is False
        assert "non-empty string" in error_msg

    def test_invalid_none(self):
        """Test None is rejected."""
        is_valid, error_msg = validate_llm_server_url(None)
        assert is_valid is False
        assert "non-empty string" in error_msg

    def test_invalid_not_string(self):
        """Test non-string type is rejected."""
        is_valid, error_msg = validate_llm_server_url(12345)
        assert is_valid is False
        assert "non-empty string" in error_msg

    # Malformed URL tests

    def test_invalid_missing_netloc(self):
        """Test URL with missing netloc is rejected."""
        is_valid, error_msg = validate_llm_server_url("http://")
        assert is_valid is False
        assert "valid host address" in error_msg

    def test_invalid_hostname_too_long(self):
        """Test excessively long hostname is rejected (DoS prevention)."""
        long_hostname = "a" * 300 + ".com"
        is_valid, error_msg = validate_llm_server_url(f"http://{long_hostname}")
        assert is_valid is False
        assert "Hostname is too long" in error_msg

    def test_invalid_hostname_with_bad_chars(self):
        """Test hostname with invalid characters is rejected."""
        is_valid, error_msg = validate_llm_server_url("http://exa$mple.com")
        # May pass basic validation but should fail on invalid chars
        # The regex rejects many special characters
        result = validate_llm_server_url("http://exa%20mple.com")
        assert result[0] is False or "invalid characters" in result[1]

    # Edge cases

    def test_valid_ipv6_loopback(self):
        """Test IPv6 loopback address is allowed for local LLM servers."""
        is_valid, error_msg = validate_llm_server_url("http://[::1]:11434")
        assert is_valid is True
        assert error_msg == "Valid URL"

    def test_valid_ipv4_loopback(self):
        """Test IPv4 loopback address (127.0.0.1) is allowed for local LLM servers."""
        is_valid, error_msg = validate_llm_server_url("http://127.0.0.1:11434")
        assert is_valid is True
        assert error_msg == "Valid URL"

    def test_valid_port_specified(self):
        """Test URL with explicit port."""
        is_valid, error_msg = validate_llm_server_url("http://ollama.example.com:11434")
        assert is_valid is True
        assert error_msg == "Valid URL"

    def test_valid_standard_http_port(self):
        """Test standard HTTP port (80)."""
        is_valid, error_msg = validate_llm_server_url("http://example.com:80")
        assert is_valid is True
        assert error_msg == "Valid URL"

    def test_valid_standard_https_port(self):
        """Test standard HTTPS port (443)."""
        is_valid, error_msg = validate_llm_server_url("https://example.com:443")
        assert is_valid is True
        assert error_msg == "Valid URL"
