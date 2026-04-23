import openai
import json
import os
import re
import httpx
import logging
from typing import Dict, Optional, Tuple
from enum import Enum
from pydantic import BaseModel, Field, field_validator, ConfigDict

# Configure logging
logger = logging.getLogger(__name__)


# PERF-004: Module-level shared HTTP client with connection pooling
# Created once at module import and reused for all LLM service requests
# This prevents creating new connections for each request
_shared_http_client = None


def get_shared_http_client():
    """Get or create the shared HTTP client with connection pooling."""
    global _shared_http_client
    if _shared_http_client is None:
        _shared_http_client = httpx.Client(
            limits=httpx.Limits(
                max_connections=10,  # Maximum concurrent connections
                max_keepalive_connections=5,  # Maximum connections to keep alive
            ),
            timeout=30.0,  # Default timeout for requests
        )
        logger.info("Created shared HTTP client with connection pooling")
    return _shared_http_client


# QUAL-002 FIX: Add Pydantic schema for strict metadata validation
class PaperMetadata(BaseModel):
    """Schema for validating LLM-extracted paper metadata."""

    author: str = Field(..., min_length=1, description="Primary author's last name")
    year: str = Field(
        ..., min_length=4, max_length=4, description="Publication year (YYYY)"
    )
    journal: str = Field(..., min_length=1, description="Journal name")
    title: str = Field(..., min_length=1, description="Paper title")
    keywords: str = Field(..., min_length=1, description="Comma-separated keywords")

    @field_validator("keywords", mode="before")
    @classmethod
    def coerce_keywords(cls, v):
        """Accept keywords as list or string — LLMs often return arrays."""
        if isinstance(v, list):
            return ", ".join(str(k) for k in v)
        return v
    suggested_filename: str = Field(..., min_length=1, description="Generated filename")

    @field_validator("year")
    @classmethod
    def validate_year(cls, v: str) -> str:
        """Ensure year is a valid 4-digit year."""
        if not v.isdigit():
            raise ValueError("Year must be numeric")
        year_int = int(v)
        if year_int < 1900 or year_int > 2100:
            raise ValueError("Year must be between 1900 and 2100")
        return v

    @field_validator("suggested_filename")
    @classmethod
    def validate_filename(cls, v: str) -> str:
        """Ensure filename is safe and ends with .pdf. Auto-sanitize common issues."""
        if not v.lower().endswith(".pdf"):
            v = v.rstrip(".") + ".pdf"
        # Auto-fix: replace spaces with hyphens, remove other invalid chars
        name = v[:-4]  # strip .pdf
        name = name.replace(" ", "-")
        name = re.sub(r"[^A-Za-z0-9._-]", "", name)
        name = re.sub(r"-+", "-", name)  # collapse multiple hyphens
        name = name.strip("-_.")
        v = name + ".pdf"
        if not re.match(r"^[A-Za-z0-9._-]+\.pdf$", v):
            raise ValueError("Filename contains invalid characters after sanitization")
        return v

    model_config = ConfigDict(
        strict=True,  # Strict validation - no extra fields allowed
        extra="forbid",  # Reject responses with extra fields
    )


class ExtractionError(Enum):
    """Types of extraction errors for better error handling."""

    INVALID_API_KEY = "invalid_api_key"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    TOKEN_LIMIT_EXCEEDED = "token_limit_exceeded"
    NETWORK_ERROR = "network_error"
    TIMEOUT = "timeout"
    API_ERROR = "api_error"
    INVALID_RESPONSE = "invalid_response"
    TEXT_TOO_SHORT = "text_too_short"
    SERVICE_UNAVAILABLE = "service_unavailable"
    UNKNOWN_ERROR = "unknown_error"


class LLMService:
    def __init__(self, config=None):
        self.config = config or {}
        self.provider = self.config.get("LLM_PROVIDER") or "openai"
        self.model = self.config.get("LLM_MODEL") or "gpt-4o-mini"
        self.api_key = self._load_api_key()

        # Configure retry and timeout settings
        self.max_retries = self.config.get("LLM_MAX_RETRIES") or 3
        self.request_timeout = self.config.get("LLM_REQUEST_TIMEOUT") or 180
        self.retry_delay = self.config.get("LLM_RETRY_DELAY") or 1

        # Text processing limits
        self.min_text_length = self.config.get("MIN_TEXT_LENGTH") or 50
        self.max_text_length = self.config.get("MAX_TEXT_LENGTH") or 3000

        # Context window configuration (for LM Studio)
        self.context_window = self._load_context_window()

        # Load provider-specific URL
        self.provider_url = self._load_provider_url()

        if self.provider == "openai":
            # PERF-004: Use shared HTTP client with connection pooling
            # This prevents creating new connections for each request
            try:
                self.client = openai.OpenAI(api_key=self.api_key)
            except Exception:
                # Fallback for older OpenAI library versions that might support proxies
                # Use shared HTTP client instead of creating a new one
                http_client = get_shared_http_client()
                self.client = openai.OpenAI(
                    api_key=self.api_key, http_client=http_client
                )

    def _load_api_key(self) -> Optional[str]:
        """Load API key from environment variables (recommended method)."""
        provider_upper = self.provider.upper()

        # Check environment variable (highest priority - recommended method)
        env_var_names = {
            "OPENAI": ["OPENAI_API_KEY", "OPENAI_KEY"],
            "ANTHROPIC": ["ANTHROPIC_API_KEY", "ANTHROPIC_KEY"],
            "COHERE": ["COHERE_API_KEY", "COHERE_KEY"],
            "GOOGLE": ["GOOGLE_API_KEY", "GEMINI_API_KEY", "GOOGLE_KEY"],
            "OLLAMA": ["OLLAMA_API_KEY"],  # Ollama API key is optional
            "OPENAI-COMPATIBLE": [
                "OPENAI_COMPATIBLE_API_KEY"
            ],  # OpenAI-compatible API key is optional
            "LM-STUDIO": [
                "OPENAI_COMPATIBLE_API_KEY"
            ],  # LM Studio uses OpenAI-compatible API key
        }

        if provider_upper in env_var_names:
            for env_var in env_var_names[provider_upper]:
                api_key = os.environ.get(env_var)
                if api_key:
                    logger.info(f"Loaded API key from environment variable: {env_var}")
                    return api_key

        # For Ollama and OpenAI-Compatible, API key is optional - return None if not found
        if self.provider in ["ollama", "openai-compatible", "lm-studio"]:
            logger.info(f"No {self.provider} API key found (optional)")
            return None

        raise ValueError(
            f"API key not found. Please set {env_var_names[provider_upper][0]} environment variable."
        )

    def _load_context_window(self) -> int:
        """Load context window for the current model.

        For LM Studio, queries the server's native API (/api/v0/models) to get
        the actual max_context_length for the selected model. Falls back to the
        DB setting, then to a safe default.
        """
        if self.provider == "lm-studio":
            # Try to get context window from LM Studio API (per-model, authoritative)
            try:
                context = self._query_lm_studio_context_window()
                if context:
                    return context
            except Exception as e:
                logger.debug(f"Could not query LM Studio for context window: {e}")

            # Fallback to DB setting
            try:
                from backend.models import SystemSettings

                context_window = SystemSettings.get_setting("lm_studio_context_window")
                if context_window:
                    return int(context_window)
            except Exception as e:
                logger.debug(f"Could not load context window setting: {e}")
        return 4096  # Default context window

    def _query_lm_studio_context_window(self) -> int | None:
        """Query LM Studio native API for the selected model's max context length."""
        import httpx

        base_url = self.provider_url.rstrip("/")
        if base_url.endswith("/v1"):
            base_url = base_url[:-3]

        try:
            resp = httpx.get(f"{base_url}/api/v0/models", timeout=5)
            if resp.status_code == 200:
                for model_info in resp.json().get("data", []):
                    if model_info.get("id") == self.model:
                        ctx = model_info.get("max_context_length")
                        if ctx:
                            logger.info(
                                f"LM Studio reports max_context_length={ctx} for {self.model}"
                            )
                            return int(ctx)
        except Exception as e:
            logger.debug(f"LM Studio /api/v0/models query failed: {e}")
        return None

    def _load_provider_url(self) -> str:
        """Load provider-specific server URL from database with fallback to config/env."""
        try:
            from backend.models import SystemSettings
            from backend.utils.validators import validate_llm_server_url

            # Try to get provider-specific URL from database
            provider_url = SystemSettings.get_provider_url(self.provider)
            if provider_url:
                is_valid, error_msg = validate_llm_server_url(provider_url)
                if is_valid:
                    logger.info(f"Loaded {self.provider} URL from database: {provider_url}")
                    return provider_url
                else:
                    logger.warning(f"Invalid {self.provider} URL in database: {error_msg}. Using fallback.")
        except Exception as e:
            logger.debug(f"Could not load provider URL from database: {e}")

        # Fallback to config or environment based on provider type
        if self.provider in ["openai-compatible", "lm-studio"]:
            provider_url = self.config.get("OPENAI_COMPATIBLE_API_URL") or self.config.get("OLLAMA_URL", "http://localhost:11434")
        else:
            provider_url = self.config.get("OLLAMA_URL", "http://localhost:11434")
        logger.info(f"Using {self.provider} URL from config: {provider_url}")
        return provider_url

    def extract_paper_metadata(
        self, text: str, user_preferences: Optional[Dict] = None
    ) -> Tuple[Optional[Dict], Optional[ExtractionError]]:
        """
        Extract metadata from research paper text.
        Returns tuple of (metadata_dict, error_type).
        """
        import time as _time

        # Validate input text
        if not text or not text.strip():
            return None, ExtractionError.TEXT_TOO_SHORT

        text = text.strip()
        if len(text) < self.min_text_length:
            logger.warning(f"Text too short for extraction: {len(text)} characters")
            return None, ExtractionError.TEXT_TOO_SHORT

        # Truncate text if too long
        if len(text) > self.max_text_length:
            text = text[: self.max_text_length] + "..."
            logger.info(
                f"Text truncated to {self.max_text_length} characters for extraction"
            )

        _start = _time.monotonic()
        try:
            if self.provider == "openai":
                result, error = self._extract_with_openai(text, user_preferences)
            elif self.provider == "ollama":
                result, error = self._extract_with_ollama(text, user_preferences)
            elif self.provider == "openai-compatible":
                # OpenAI-compatible servers use the same extraction logic as Ollama with server type detection
                result, error = self._extract_with_ollama(text, user_preferences)
            elif self.provider == "lm-studio":
                # LM Studio uses OpenAI-compatible endpoints
                result, error = self._extract_with_ollama(text, user_preferences)
            else:
                logger.error(f"Unsupported LLM provider: {self.provider}")
                result, error = None, ExtractionError.SERVICE_UNAVAILABLE

        except Exception as e:
            logger.error(
                f"Unexpected error during metadata extraction: {type(e).__name__}: {str(e)}"
            )
            result, error = None, ExtractionError.UNKNOWN_ERROR

        # Record LLM call metrics (REQ-OPS-004)
        _duration_ms = (_time.monotonic() - _start) * 1000
        try:
            from backend.utils.metrics_collector import MetricsCollector

            MetricsCollector.get_instance().record_llm_call(
                duration_ms=_duration_ms, success=(error is None)
            )
        except Exception:
            pass  # Never let metrics recording break the main flow

        return result, error

    def _extract_with_openai(
        self, text: str, user_preferences: Optional[Dict] = None
    ) -> Tuple[Optional[Dict], Optional[ExtractionError]]:
        """Extract metadata using OpenAI API with retry logic and comprehensive error handling."""
        prompt = self._create_prompt(text, user_preferences)

        for attempt in range(self.max_retries):
            try:
                logger.debug(
                    f"OpenAI extraction attempt {attempt + 1}/{self.max_retries}"
                )

                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are an expert at analyzing academic research papers. Extract metadata accurately and format as JSON.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.1,
                    max_tokens=500,
                    timeout=self.request_timeout,
                )

                if not response.choices or not response.choices[0].message:
                    logger.error(
                        "Invalid response from OpenAI API: no choices or message"
                    )
                    return None, ExtractionError.INVALID_RESPONSE

                content = response.choices[0].message.content
                if not content:
                    logger.error("Empty response content from OpenAI API")
                    return None, ExtractionError.INVALID_RESPONSE

                metadata = self._parse_response(content)
                if metadata:
                    logger.info(
                        f"Successfully extracted metadata on attempt {attempt + 1}"
                    )
                    return metadata, None
                else:
                    logger.warning(f"Failed to parse response on attempt {attempt + 1}")
                    if attempt == self.max_retries - 1:
                        return None, ExtractionError.INVALID_RESPONSE

            except openai.AuthenticationError as e:
                logger.error(f"OpenAI authentication error: {e}")
                return None, ExtractionError.INVALID_API_KEY

            except openai.RateLimitError as e:
                logger.warning(
                    f"OpenAI rate limit exceeded on attempt {attempt + 1}: {e}"
                )
                if attempt < self.max_retries - 1:
                    import time

                    time.sleep(self.retry_delay * (2**attempt))  # Exponential backoff
                else:
                    return None, ExtractionError.RATE_LIMIT_EXCEEDED

            except openai.APITimeoutError as e:
                logger.warning(f"OpenAI API timeout on attempt {attempt + 1}: {e}")
                if attempt == self.max_retries - 1:
                    return None, ExtractionError.NETWORK_ERROR

            except openai.APIConnectionError as e:
                logger.warning(
                    f"OpenAI API connection error on attempt {attempt + 1}: {e}"
                )
                if attempt < self.max_retries - 1:
                    import time

                    time.sleep(self.retry_delay)
                else:
                    return None, ExtractionError.NETWORK_ERROR

            except openai.BadRequestError as e:
                # This could be due to token limits or invalid request
                if "token" in str(e).lower():
                    logger.error(f"Token limit exceeded: {e}")
                    # Try with shorter text
                    if attempt == 0 and len(text) > 2000:
                        # Retry with shorter text
                        text = text[:2000] + "..."
                        logger.info("Retrying with shorter text due to token limit")
                        continue
                    return None, ExtractionError.TOKEN_LIMIT_EXCEEDED
                else:
                    logger.error(f"OpenAI API bad request: {e}")
                    return None, ExtractionError.API_ERROR

            except openai.APIError as e:
                logger.error(f"OpenAI API error on attempt {attempt + 1}: {e}")
                if attempt < self.max_retries - 1:
                    import time

                    time.sleep(self.retry_delay)
                else:
                    return None, ExtractionError.API_ERROR

            except Exception as e:
                logger.error(
                    f"Unexpected error calling OpenAI API on attempt {attempt + 1}: {type(e).__name__}: {str(e)}"
                )
                if attempt == self.max_retries - 1:
                    return None, ExtractionError.UNKNOWN_ERROR

        logger.error(f"All {self.max_retries} attempts failed")
        return None, ExtractionError.UNKNOWN_ERROR

    def _extract_with_ollama(
        self, text: str, user_preferences: Optional[Dict] = None
    ) -> Tuple[Optional[Dict], Optional[ExtractionError]]:
        """Extract metadata using Ollama API or OpenAI-compatible API."""

        # Use provider-specific URL
        ollama_url = self.provider_url

        # Determine server type based on provider
        # - If provider is 'openai-compatible' or 'lm-studio', always use OpenAI-compatible endpoint
        # - If provider is 'ollama', check database for detected server type, default to native
        if self.provider in ["openai-compatible", "lm-studio"]:
            server_type = "openai-compatible"
            logger.info(
                f"Provider is {self.provider}, using OpenAI-compatible endpoint"
            )
        else:
            # Provider is 'ollama' - get the server type from database
            server_type = "ollama-native"
            try:
                from backend.models import SystemSettings

                stored_server_type = SystemSettings.get_setting("ollama_server_type")
                if stored_server_type:
                    server_type = stored_server_type
                    logger.info(f"Using detected server type: {server_type}")
            except Exception as e:
                logger.warning(
                    f"Could not retrieve server type from database: {e}. Using default: ollama-native"
                )

        # Prepare headers (optional API key if provided)
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            if server_type == "openai-compatible":
                # Use OpenAI-compatible /v1/completions endpoint
                logger.info(f"Using OpenAI-compatible endpoint for {self.model}")
                return self._extract_openai_compatible(
                    ollama_url, text, user_preferences, headers
                )
            else:
                # Use native Ollama /api/generate endpoint
                logger.info(f"Using native Ollama endpoint for {self.model}")
                return self._extract_ollama_native(
                    ollama_url, text, user_preferences, headers
                )

        except Exception as e:
            logger.error(
                f"Unexpected error during Ollama extraction: {type(e).__name__}: {str(e)}"
            )
            return None, ExtractionError.UNKNOWN_ERROR

    def _extract_openai_compatible(
        self,
        ollama_url: str,
        text: str,
        user_preferences: Optional[Dict],
        headers: dict,
    ) -> Tuple[Optional[Dict], Optional[ExtractionError]]:
        """Extract metadata using OpenAI-compatible /v1/completions endpoint."""
        # PERF-004: Use shared httpx client instead of requests
        http_client = get_shared_http_client()

        base_url = ollama_url.rstrip("/")
        if base_url.endswith("/v1"):
            base_url = base_url[:-3]

        # Create prompt
        prompt = self._create_prompt(text, user_preferences)

        # Calculate max_tokens — reasoning/thinking models need more headroom
        # (they use tokens for internal chain-of-thought before producing output)
        if self.provider == "lm-studio":
            max_tokens = max(2000, self.context_window // 3)
        elif self.provider == "openai-compatible":
            max_tokens = 2000
        else:
            max_tokens = 500

        try:
            # Use chat/completions for LM Studio (chat models), completions for others
            if self.provider == "lm-studio":
                response = http_client.post(
                    f"{base_url}/v1/chat/completions",
                    headers=headers,
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": "You are a research paper metadata extractor. Respond with ONLY valid JSON, no explanation."},
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": 0.0,
                        "max_tokens": max_tokens,
                    },
                    timeout=self.request_timeout,
                )
            else:
                response = http_client.post(
                    f"{base_url}/v1/completions",
                    headers=headers,
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "temperature": 0.0,
                        "max_tokens": max_tokens,
                    },
                    timeout=self.request_timeout,
                )

            response.raise_for_status()
            result = response.json()

            # Extract response text from the appropriate format
            if "choices" in result and len(result["choices"]) > 0:
                choice = result["choices"][0]
                # chat/completions returns message.content, completions returns text
                if "message" in choice:
                    response_text = choice["message"].get("content", "")
                    # Some reasoning models (gemma-4, etc.) put content in reasoning_content
                    # when they run out of tokens before producing final content
                    if not response_text:
                        reasoning = choice["message"].get("reasoning_content", "")
                        if reasoning:
                            response_text = reasoning
                            logger.info("Using reasoning_content as response (model used thinking mode)")
                else:
                    response_text = choice.get("text", "")
            else:
                logger.error("OpenAI-compatible response missing choices array")
                return None, ExtractionError.INVALID_RESPONSE

            if not response_text:
                logger.error("Empty response from OpenAI-compatible server")
                return None, ExtractionError.INVALID_RESPONSE

            # Parse JSON response
            metadata = self._parse_response(response_text)
            if not metadata:
                logger.error(
                    f"Failed to parse OpenAI-compatible response. Response text: {response_text[:500]}"
                )
                return None, ExtractionError.INVALID_RESPONSE

            # Debug: Log parsed metadata
            logger.debug(f"Parsed metadata: {metadata}")

            # Validate required fields
            if not metadata.get("author"):
                logger.warning(
                    f"OpenAI-compatible response missing author field. Metadata keys: {list(metadata.keys())}"
                )
                return None, ExtractionError.INVALID_RESPONSE

            return metadata, None

        except httpx.TimeoutException:
            logger.error(
                f"OpenAI-compatible request timeout after {self.request_timeout}s"
            )
            return None, ExtractionError.NETWORK_ERROR
        except httpx.NetworkError as e:
            logger.error(f"OpenAI-compatible connection error: {e}")
            return None, ExtractionError.SERVICE_UNAVAILABLE
        except httpx.HTTPStatusError as e:
            error_body = e.response.text[:500] if e.response else "no body"
            logger.error(f"OpenAI-compatible HTTP error: {e.response.status_code} - {error_body}")
            if e.response.status_code == 404:
                logger.error(
                    f"Model '{self.model}' not found or endpoint not supported. Server may be native Ollama."
                )
                return None, ExtractionError.SERVICE_UNAVAILABLE
            return None, ExtractionError.API_ERROR
        except httpx.HTTPError as e:
            logger.error(f"OpenAI-compatible HTTP error: {e}")
            return None, ExtractionError.API_ERROR

    def _extract_ollama_native(
        self,
        ollama_url: str,
        text: str,
        user_preferences: Optional[Dict],
        headers: dict,
    ) -> Tuple[Optional[Dict], Optional[ExtractionError]]:
        """Extract metadata using native Ollama /api/generate endpoint."""
        # PERF-004: Use shared httpx client instead of requests
        http_client = get_shared_http_client()
        import json

        # Create prompt
        prompt = self._create_prompt(text, user_preferences)

        try:
            # Call Ollama generate API using shared client
            response = http_client.post(
                f"{ollama_url}/api/generate",
                headers=headers,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.0},
                },
                timeout=self.request_timeout,
            )

            response.raise_for_status()
            result = response.json()

            # Extract the response text
            response_text = result.get("response", "")

            if not response_text:
                logger.error("Empty response from Ollama")
                return None, ExtractionError.INVALID_RESPONSE

            # Parse JSON response
            try:
                # Try to extract JSON from the response
                # Ollama might include extra text, so we need to find the JSON part
                json_start = response_text.find("{")
                json_end = response_text.rfind("}") + 1

                if json_start >= 0 and json_end > json_start:
                    json_str = response_text[json_start:json_end]
                    metadata = json.loads(json_str)
                else:
                    # Fallback: try parsing the entire response
                    metadata = json.loads(response_text)

                # Validate required fields
                if not metadata.get("author"):
                    logger.warning("Ollama response missing author field")
                    return None, ExtractionError.INVALID_RESPONSE

                return metadata, None

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse Ollama JSON response: {e}")
                logger.debug(f"Response text: {response_text[:500]}")
                return None, ExtractionError.INVALID_RESPONSE

        except httpx.TimeoutException:
            logger.error(f"Ollama request timeout after {self.request_timeout}s")
            return None, ExtractionError.TIMEOUT
        except httpx.NetworkError as e:
            logger.error(f"Ollama connection error: {e}")
            return None, ExtractionError.SERVICE_UNAVAILABLE
        except httpx.HTTPStatusError as e:
            logger.error(f"Ollama HTTP error: {e.response.status_code}")
            if e.response.status_code == 404:
                logger.error(f"Model '{self.model}' not found on Ollama server")
                return None, ExtractionError.SERVICE_UNAVAILABLE
            return None, ExtractionError.API_ERROR
        except httpx.HTTPError as e:
            logger.error(f"Ollama HTTP error: {e}")
            return None, ExtractionError.API_ERROR

    def _create_prompt(self, text: str, user_preferences: Optional[Dict] = None) -> str:
        """Create the prompt for LLM."""
        # Get user preferences for filename format
        filename_format = "Author_Year_Journal_Keywords"  # Default format
        custom_format = None

        if user_preferences:
            filename_format = user_preferences.get(
                "filename_format", "Author_Year_Journal_Keywords"
            )
            if filename_format == "Custom":
                custom_format = user_preferences.get(
                    "custom_filename_format", "{author}_{year}_{title}"
                )

        # Text is already truncated in extract_paper_metadata method
        # No need to truncate again here

        # Format instructions based on user preference
        format_instructions = self._get_format_instructions(
            filename_format, custom_format
        )

        return f"""
Extract the following metadata from this research paper text and respond with ONLY a JSON object:

1. Author: Extract the primary author's last name (most important for filename)
2. Year: The ORIGINAL publication year of the paper in the journal (NOT the PMC availability year).
   - For PMC author manuscripts, look for "Published in final edited form as: [Journal]. [YEAR]" — use that YEAR.
   - IGNORE "available in PMC [YEAR]" — that is only when the PMC copy was posted.
   - Example: Text says "available in PMC 2024" and "Published in final edited form as: Cell. 2023" → year is 2023.
3. Journal: Extract journal name (e.g., Nature, Science, bioRxiv, Cell, NEJM, etc.)
4. Title: The main title of the paper
5. Keywords: Extract 3-5 key words that represent the core research
6. Suggested Filename: Create a filename following the specified format

{format_instructions}

Paper text:
{text}

Respond with JSON only (no other text). Example format:
{{
    "author": "<first author last name>",
    "year": "<4-digit publication year>",
    "journal": "<journal or preprint server name>",
    "title": "<full paper title>",
    "keywords": "<3-5 comma-separated key terms>",
    "suggested_filename": "<Author_Year_Journal_keywords.pdf>"
}}
"""

    def _get_format_instructions(
        self, filename_format: str, custom_format: Optional[str] = None
    ) -> str:
        """Get format-specific instructions for filename creation."""

        if filename_format == "Custom" and custom_format:
            # Map template variables to descriptions
            variable_help = []
            if "{author}" in custom_format:
                variable_help.append("- {author}: Primary author's last name")
            if "{year}" in custom_format:
                variable_help.append("- {year}: 4-digit publication year")
            if "{title}" in custom_format:
                variable_help.append("- {title}: Brief title (first 3-5 words)")
            if "{journal}" in custom_format:
                variable_help.append("- {journal}: Journal name (abbreviated)")
            if "{keywords}" in custom_format:
                variable_help.append("- {keywords}: 3-5 key research terms")

            return f"""
Rules for filename:
- Use this custom format: {custom_format}
- Available variables: {", ".join([f"{{{v}}}" for v in ["author", "year", "title", "journal", "keywords"] if f"{{{v}}}" in custom_format])}
{chr(10).join(variable_help)}
- Use hyphens to connect multi-word terms (e.g., "NF-κB-mediated")
- Remove special characters except hyphens, use only letters, numbers, underscores, and hyphens
- Keep content concise but descriptive
- End with .pdf
"""

        format_rules = {
            "Author_Year_Journal_Keywords": """
Rules for filename:
- Format: Author_Year_Journal_keyword1-keyword2-keyword3.pdf
- Use only the primary author's last name
- Include the 4-digit year
- Include abbreviated journal name (standard abbreviation)
- Keywords section: pick 3-5 of the most important single words, separated by hyphens
- CRITICAL: Each keyword must be ONE word only. Never concatenate words together.
  WRONG: "insulinresistance" or "deeplearning" or "weightloss"
  RIGHT: "insulin-resistance" or "deep-learning" or "weight-loss"
- Maximum 5 keywords (hyphen-separated words). Count each word individually.
- Use underscores (_) ONLY to separate Author, Year, Journal, and Keywords sections
- Use hyphens (-) ONLY between keywords within the keywords section
- Remove special characters, use only letters, numbers, underscores, and hyphens
- End with .pdf
- Examples:
  Smith_2024_Nature_obesity-insulin-resistance.pdf
  Lee_2023_Cell_CRISPR-gene-editing-cancer.pdf
  Wang_2025_Science_single-cell-RNA-seq.pdf
""",
            "Author_Year_Title": """
Rules for filename:
- Format: Author_Year_Title
- Use only the primary author's last name
- Include the 4-digit year
- Include first 5-8 words of the title (truncated if too long)
- Use hyphens to connect multi-word terms (e.g., "NF-κB-mediated")
- Remove special characters except hyphens, use only letters, numbers, underscores, and hyphens
- Keep title portion concise but descriptive
- End with .pdf
""",
            "Author_Year_Journal": """
Rules for filename:
- Format: Author_Year_Journal
- Use only the primary author's last name
- Include the 4-digit year
- Include abbreviated journal name (standard abbreviation)
- Use hyphens to connect multi-word journal names (e.g., "Science-Advances")
- Remove special characters except hyphens, use only letters, numbers, underscores, and hyphens
- End with .pdf
""",
            "Year_Author_Title": """
Rules for filename:
- Format: Year_Author_Title
- Start with the 4-digit year
- Use only the primary author's last name
- Include first 5-8 words of the title (truncated if too long)
- Use hyphens to connect multi-word terms (e.g., "NF-κB-mediated")
- Remove special characters except hyphens, use only letters, numbers, underscores, and hyphens
- Keep title portion concise but descriptive
- End with .pdf
""",
        }

        return format_rules.get(
            filename_format, format_rules["Author_Year_Journal_Keywords"]
        )

    def _parse_response(self, content: str) -> Optional[Dict]:
        """
        Parse LLM response to extract JSON with strict schema validation.

        QUAL-002 FIX: Uses Pydantic schema validation to ensure all required fields
        are present and valid. Rejects malformed or incomplete responses.
        """
        if not content:
            logger.error("Empty content provided to _parse_response")
            return None

        parsed_data = None

        # Try to extract JSON from the response using multiple strategies
        try:
            # First try to find JSON block with markdown code fences
            code_fence_match = re.search(
                r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL | re.IGNORECASE
            )
            if code_fence_match:
                json_str = code_fence_match.group(1)
                logger.debug("Found JSON in code fences")
                parsed_data = json.loads(json_str)

            # Try to find JSON in the response (looking for outer braces)
            if not parsed_data:
                json_match = re.search(
                    r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", content, re.DOTALL
                )
                if json_match:
                    json_str = json_match.group()
                    logger.debug("Found JSON with basic regex")
                    parsed_data = json.loads(json_str)

            # Fallback: try to parse entire response as JSON
            if not parsed_data:
                try:
                    logger.debug("Attempting to parse entire response as JSON")
                    parsed_data = json.loads(content)
                except json.JSONDecodeError:
                    # QUAL-002 FIX: Remove manual parsing fallback - it was too permissive
                    # If we can't extract valid JSON, fail fast rather than guessing
                    logger.warning("Could not extract valid JSON from response")
                    return None

        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            logger.debug(f"Response content (first 500 chars): {content[:500]}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error parsing response: {type(e).__name__}: {e}")
            return None

        # QUAL-002 FIX: Validate parsed data against strict schema
        if not parsed_data:
            return None

        try:
            # Validate using Pydantic schema - this ensures all required fields exist
            # and validates data types, formats, and constraints
            validated_metadata = PaperMetadata(**parsed_data)

            # Return validated data as dictionary
            return validated_metadata.model_dump()

        except Exception as validation_error:
            logger.warning(
                f"Schema validation failed: {type(validation_error).__name__}: {validation_error}"
            )
            logger.debug(f"Invalid parsed data: {parsed_data}")
            return None

    def validate_filename(self, filename: str) -> bool:
        """Validate that the suggested filename follows safe filename practices."""
        if not filename:
            return False

        # Check for .pdf extension
        if not filename.lower().endswith(".pdf"):
            return False

        # Check for valid characters: letters, numbers, hyphens, underscores, and dots
        # Disallow dangerous characters like / \ : * ? " < > |
        pattern = r"^[A-Za-z0-9._-]+\.pdf$"
        return bool(re.match(pattern, filename))

    def sanitize_filename(self, filename: str) -> str:
        """Sanitize filename to be safe for filesystem."""
        # Remove special characters except underscores and dots
        filename = re.sub(r"[^\w\s.-]", "", filename)
        # Replace spaces with underscores
        filename = re.sub(r"\s+", "_", filename)
        # Limit length
        if len(filename) > 255:
            name, ext = os.path.splitext(filename)
            filename = name[:250] + ext
        return filename

    def get_error_message(self, error: ExtractionError) -> str:
        """Get user-friendly error message for extraction error."""
        messages = {
            ExtractionError.INVALID_API_KEY: "Invalid API key. Please configure a valid OpenAI API key.",
            ExtractionError.RATE_LIMIT_EXCEEDED: "API rate limit exceeded. Please try again in a few minutes.",
            ExtractionError.TOKEN_LIMIT_EXCEEDED: "Text too long for processing. Please try with a shorter document.",
            ExtractionError.NETWORK_ERROR: "Network connection error. Please check your internet connection and try again.",
            ExtractionError.TIMEOUT: "AI processing timed out on this file. The PDF may be too large or complex. Try again or upload fewer files.",
            ExtractionError.API_ERROR: "API service error. Please try again later.",
            ExtractionError.INVALID_RESPONSE: "Unable to process the response from the AI service. Please try again.",
            ExtractionError.TEXT_TOO_SHORT: "Document text is too short for metadata extraction. Please ensure the PDF contains readable text.",
            ExtractionError.SERVICE_UNAVAILABLE: "AI service is currently unavailable. Please try again later.",
            ExtractionError.UNKNOWN_ERROR: "An unexpected error occurred. Please try again or contact support if the issue persists.",
        }
        return messages.get(error, str(error.value))
