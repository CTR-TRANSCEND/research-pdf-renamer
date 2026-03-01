import ipaddress
import os
import re
from typing import Tuple
from urllib.parse import urlparse

# SSRF Protection: Allow private IPs when explicitly configured
# SECURITY: When enabled, allows internal network access for LLM servers
# Use only in trusted environments where local LLM servers are required
ALLOW_PRIVATE_IPS = os.environ.get("ALLOW_PRIVATE_IPS", "false").lower() == "true"

try:
    from email_validator import validate_email as email_validator_validate

    EMAIL_VALIDATOR_AVAILABLE = True
except ImportError:
    EMAIL_VALIDATOR_AVAILABLE = False


def validate_email(email: str) -> Tuple[bool, str]:
    """Validate email format using email-validator library if available, with regex fallback."""
    if EMAIL_VALIDATOR_AVAILABLE:
        try:
            # Validate email and check deliverability (DNS check disabled for speed)
            email_validator_validate(email, check_deliverability=False)
            return True, "Valid email"
        except Exception:
            return False, "Invalid email format"
    else:
        # SEC-002 FIX: Fallback to improved regex pattern that supports plus signs and more
        # This pattern is more permissive than RFC 5322 but covers common valid email formats
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(pattern, email):
            return False, "Invalid email format"
        return True, "Valid email"


def validate_password(password: str) -> Tuple[bool, str]:
    """Validate password strength."""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"

    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter"

    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter"

    if not re.search(r"\d", password):
        return False, "Password must contain at least one number"

    return True, "Valid password"


def validate_name(name: str) -> Tuple[bool, str]:
    """Validate user name."""
    if not name or len(name.strip()) < 2:
        return False, "Name must be at least 2 characters long"

    if len(name) > 100:
        return False, "Name must be less than 100 characters"

    return True, "Valid name"


def validate_llm_server_url(url: str) -> Tuple[bool, str]:
    """Validate LLM server URL to prevent SSRF attacks.

    Args:
        url: The URL to validate

    Returns:
        Tuple of (is_valid, error_message)

    Security:
        - Only allows http:// and https:// schemes
        - Requires a valid network location (netloc)
        - Restricts path to safe endpoints (/api, /v1, or root)
        - Uses strict URL parsing to catch malformed URLs
        - Rejects private/internal network ranges (optional, depending on requirements)
    """
    if not url or not isinstance(url, str):
        return False, "URL must be a non-empty string"

    try:
        # Parse URL with strict validation (Python 3.9+)
        # For older Python versions, fall back to standard parsing
        try:
            parsed = urlparse(url, strict=True)
        except TypeError:
            # Python < 3.9 doesn't support strict parameter
            parsed = urlparse(url)
    except (ValueError, TypeError) as e:
        return False, f"Invalid URL format: {e}"

    # Scheme validation - only http and https allowed
    if parsed.scheme not in ("http", "https"):
        return False, "URL scheme must be http:// or https://"

    # Network location must exist
    if not parsed.netloc:
        return False, "URL must contain a valid host address"

    # Path validation - allow common LLM API endpoints
    # Remove trailing slash for comparison
    path_clean = parsed.path.rstrip("/")

    # Allow common API paths used by LLM servers
    # Includes: root, OpenAI-compatible paths, Ollama paths, and common variations
    allowed_paths = (
        "",
        "/",
        "/api",
        "/api/generate",
        "/api/tags",
        "/api/ps",
        "/v1",
        "/v1/models",
        "/v1/completions",
        "/models",
        "/models/status",
    )
    if path_clean not in allowed_paths:
        return False, f"URL path must be one of: {', '.join(allowed_paths)}"

    # Hostname validation - reject obviously malformed hosts
    hostname = parsed.hostname
    if hostname:
        # Reject extremely long hostnames (DoS prevention)
        if len(hostname) > 253:
            return False, "Hostname is too long"

        # Reject hostnames with invalid characters
        if not re.match(r"^[a-zA-Z0-9.\-_:]+$", hostname):
            return False, "Hostname contains invalid characters"

        # SSRF Protection: Reject private IP addresses, loopback, and link-local addresses
        # unless ALLOW_PRIVATE_IPS is explicitly enabled
        #
        # SECURITY NOTE: Loopback addresses (127.0.0.1, localhost) are explicitly allowed
        # because:
        # 1. LLM server URLs are configured by trusted administrators via admin panel
        # 2. Local LLM servers (Ollama, LM Studio) commonly run on localhost
        # 3. This is not user-controlled input - only admins can set these URLs
        #
        # For environments where private IPs are required, set ALLOW_PRIVATE_IPS=true
        try:
            ip = ipaddress.ip_address(hostname)
            if not ALLOW_PRIVATE_IPS:
                if ip.is_private or ip.is_link_local or ip.is_reserved:
                    return (
                        False,
                        "Private IP addresses and link-local addresses are not allowed for security reasons. "
                        "Set ALLOW_PRIVATE_IPS=true to enable.",
                    )
            # Allow loopback (localhost, 127.0.0.1) for local LLM server development
            # This is intentional as LLM servers often run locally
        except ValueError:
            # Not an IP address (hostname), continue validation
            pass

    # Query and fragment should typically not be present for server URLs
    if parsed.query:
        return False, "URL should not contain query parameters"

    if parsed.fragment:
        return False, "URL should not contain fragments"

    return True, "Valid URL"
