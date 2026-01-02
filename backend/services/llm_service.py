import openai
import json
import os
import re
import httpx
from typing import Dict, Optional

class LLMService:
    def __init__(self, config=None):
        self.config = config or {}
        self.provider = self.config.get('LLM_PROVIDER', 'openai')
        self.model = self.config.get('LLM_MODEL', 'gpt-4o-mini')
        self.api_key = self._load_api_key()

        if self.provider == 'openai':
            # Create OpenAI client - simplified initialization for newer OpenAI library
            try:
                self.client = openai.OpenAI(api_key=self.api_key)
            except Exception as e:
                # Fallback for older OpenAI library versions that might support proxies
                http_client = httpx.Client(
                    limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
                    timeout=30.0
                )
                self.client = openai.OpenAI(
                    api_key=self.api_key,
                    http_client=http_client
                )

    def _load_api_key(self) -> str:
        """Load API key from database, environment, or file (in that order)."""
        # Try to load from database first (most preferred)
        try:
            from backend.models import SystemSettings
            db_api_key = SystemSettings.get_api_key('openai')
            if db_api_key:
                return db_api_key
        except Exception as e:
            # Database might not be initialized yet, continue to fallbacks
            print(f"Note: Could not load API key from database: {e}")

        # Check environment variable
        api_key = os.environ.get('OPENAI_API_KEY')
        if api_key:
            return api_key

        # Try to load from APISetting.txt (legacy support)
        api_key_file = self.config.get('API_KEY_FILE', 'APISetting.txt')
        try:
            with open(api_key_file, 'r') as f:
                file_key = f.read().strip()
                if file_key:
                    return file_key
        except FileNotFoundError:
            pass

        raise ValueError(f"API key not found. Please configure via Admin Panel, set OPENAI_API_KEY environment variable, or create {api_key_file}")

    def extract_paper_metadata(self, text: str, user_preferences: Optional[Dict] = None) -> Optional[Dict]:
        """
        Extract metadata from research paper text.
        Returns dict with author, year, title, and suggested filename.
        """
        if self.provider == 'openai':
            return self._extract_with_openai(text, user_preferences)
        elif self.provider == 'ollama':
            return self._extract_with_ollama(text, user_preferences)
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")

    def _extract_with_openai(self, text: str, user_preferences: Optional[Dict] = None) -> Optional[Dict]:
        """Extract metadata using OpenAI API."""
        prompt = self._create_prompt(text, user_preferences)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert at analyzing academic research papers. Extract metadata accurately and format as JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=500
            )

            content = response.choices[0].message.content
            return self._parse_response(content)

        except Exception as e:
            print(f"Error calling OpenAI API: {e}")
            return None

    def _extract_with_ollama(self, text: str, user_preferences: Optional[Dict] = None) -> Optional[Dict]:
        """Extract metadata using local Ollama model."""
        # TODO: Implement Ollama integration
        # This would require requests library and Ollama running locally
        raise NotImplementedError("Ollama integration not yet implemented")

    def _create_prompt(self, text: str, user_preferences: Optional[Dict] = None) -> str:
        """Create the prompt for LLM."""
        # Get user preferences for filename format
        filename_format = 'Author_Year_Journal_Keywords'  # Default format
        custom_format = None

        if user_preferences:
            filename_format = user_preferences.get('filename_format', 'Author_Year_Journal_Keywords')
            if filename_format == 'Custom':
                custom_format = user_preferences.get('custom_filename_format', '{author}_{year}_{title}')

        # Limit text length to avoid token limits
        max_text_length = 3000
        if len(text) > max_text_length:
            text = text[:max_text_length] + "..."

        # Format instructions based on user preference
        format_instructions = self._get_format_instructions(filename_format, custom_format)

        return f"""
Extract the following metadata from this research paper text and respond with ONLY a JSON object:

1. Author: Extract the primary author's last name (most important for filename)
2. Year: Publication year (look for 4-digit years, usually recent)
3. Journal: Extract journal name (e.g., Nature, Science, bioRxiv, Cell, NEJM, etc.)
4. Title: The main title of the paper
5. Keywords: Extract 3-5 key words that represent the core research
6. Suggested Filename: Create a filename following the specified format

{format_instructions}

Paper text:
{text}

Respond with JSON like:
{{
    "author": "Navaeiseddighi",
    "year": "2025",
    "journal": "bioRxiv",
    "title": "NF-κB-mediated epithelial tolerance enhances susceptibility to Streptococcus pneumoniae infection after influenza virus infection",
    "keywords": "NF-κB, epithelial tolerance, Streptococcus pneumoniae, influenza, infection",
    "suggested_filename": "Navaeiseddighi_2025_bioRxiv_NF-kB-epithelial-tolerance-Spn-IAV.pdf"
}}
"""

    def _get_format_instructions(self, filename_format: str, custom_format: Optional[str] = None) -> str:
        """Get format-specific instructions for filename creation."""

        if filename_format == 'Custom' and custom_format:
            # Map template variables to descriptions
            variable_help = []
            if '{author}' in custom_format:
                variable_help.append("- {author}: Primary author's last name")
            if '{year}' in custom_format:
                variable_help.append("- {year}: 4-digit publication year")
            if '{title}' in custom_format:
                variable_help.append("- {title}: Brief title (first 3-5 words)")
            if '{journal}' in custom_format:
                variable_help.append("- {journal}: Journal name (abbreviated)")
            if '{keywords}' in custom_format:
                variable_help.append("- {keywords}: 3-5 key research terms")

            return f"""
Rules for filename:
- Use this custom format: {custom_format}
- Available variables: {', '.join([f'{{{v}}}' for v in ['author', 'year', 'title', 'journal', 'keywords'] if f'{{{v}}}' in custom_format])}
{chr(10).join(variable_help)}
- Use hyphens to connect multi-word terms (e.g., "NF-κB-mediated")
- Remove special characters except hyphens, use only letters, numbers, underscores, and hyphens
- Keep content concise but descriptive
- End with .pdf
"""

        format_rules = {
            'Author_Year_Journal_Keywords': """
Rules for filename:
- Format: Author_Year_Journal_KeyWords
- Use only the primary author's last name
- Include the 4-digit year
- Include abbreviated journal name (standard abbreviation)
- Extract 3-5 key words from the title that represent the core research
- Use hyphens to connect multi-word keywords (e.g., "NF-κB-mediated")
- Remove special characters except hyphens, use only letters, numbers, underscores, and hyphens
- Keep keywords concise but descriptive
- End with .pdf
""",
            'Author_Year_Title': """
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
            'Author_Year_Journal': """
Rules for filename:
- Format: Author_Year_Journal
- Use only the primary author's last name
- Include the 4-digit year
- Include abbreviated journal name (standard abbreviation)
- Use hyphens to connect multi-word journal names (e.g., "Science-Advances")
- Remove special characters except hyphens, use only letters, numbers, underscores, and hyphens
- End with .pdf
""",
            'Year_Author_Title': """
Rules for filename:
- Format: Year_Author_Title
- Start with the 4-digit year
- Use only the primary author's last name
- Include first 5-8 words of the title (truncated if too long)
- Use hyphens to connect multi-word terms (e.g., "NF-κB-mediated")
- Remove special characters except hyphens, use only letters, numbers, underscores, and hyphens
- Keep title portion concise but descriptive
- End with .pdf
"""
        }

        return format_rules.get(filename_format, format_rules['Author_Year_Journal_Keywords'])

    def _parse_response(self, content: str) -> Optional[Dict]:
        """Parse LLM response to extract JSON."""
        try:
            # Try to find JSON in the response
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                return json.loads(json_str)
            else:
                # Fallback: try to parse entire response as JSON
                return json.loads(content)
        except json.JSONDecodeError as e:
            print(f"Error parsing LLM response: {e}")
            print(f"Response content: {content}")
            return None

    def validate_filename(self, filename: str) -> bool:
        """Validate that the suggested filename follows the required format."""
        # Check format: Author_Year_Journal_KeyWords.pdf
        # Allows letters, numbers, hyphens, and underscores
        pattern = r'^[A-Za-z]+_\d{4}_[A-Za-z0-9]+(?:_[A-Za-z0-9-]+)*\.pdf$'
        return bool(re.match(pattern, filename))

    def sanitize_filename(self, filename: str) -> str:
        """Sanitize filename to be safe for filesystem."""
        # Remove special characters except underscores and dots
        filename = re.sub(r'[^\w\s.-]', '', filename)
        # Replace spaces with underscores
        filename = re.sub(r'\s+', '_', filename)
        # Limit length
        if len(filename) > 255:
            name, ext = os.path.splitext(filename)
            filename = name[:250] + ext
        return filename