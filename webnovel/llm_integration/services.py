# llm_integration/services.py
import json
import re
import time
from typing import List, Dict, Any
from django.conf import settings
import logging
from langchain_core.messages import HumanMessage, SystemMessage
import os

logger = logging.getLogger(__name__)

# Try to import provider-specific packages, with fallbacks
try:
    from langchain_openai import ChatOpenAI

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("langchain_openai not available, OpenAI provider disabled")

try:
    from langchain_anthropic import ChatAnthropic

    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    logger.warning("langchain_anthropic not available, Anthropic provider disabled")

try:
    from langchain_google_genai import ChatGoogleGenerativeAI

    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False
    logger.warning("langchain_google_genai not available, Google provider disabled")

try:
    from langchain_community.chat_models import ChatCohere

    COHERE_AVAILABLE = True
except ImportError:
    COHERE_AVAILABLE = False
    logger.warning("langchain_community not available, Cohere provider disabled")

try:
    from langchain_community.llms import Ollama

    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    logger.warning("langchain_community not available, Ollama provider disabled")




class LLMTranslationService:
    """Service for handling LLM API calls for translation and text processing"""

    def __init__(self, api_key=None, model=None, provider="openai"):
        """
        Initialize LLM service with provider-agnostic interface using LangChain

        Args:
            api_key: API key for the LLM provider
            model: Model name (e.g., 'gpt-3.5-turbo', 'claude-3-sonnet-20240229')
            provider: Provider name ('openai', 'anthropic', 'google', etc.)
        """
        self.api_key = api_key or getattr(settings, "LLM_API_KEY", None)
        self.provider = provider or getattr(settings, "LLM_PROVIDER", "openai")

        # Set default model based on provider
        if model:
            self.model = model
        else:
            self.model = getattr(settings, "LLM_MODEL_NAME", self._get_default_model())

        # Initialize the LLM client
        self.llm = self._initialize_llm()

    def _get_language_name(self, language_code: str) -> str:
        """
        Get language name from database by language code, with lazy caching.
        """
        if not hasattr(self, '_language_code_to_name_cache') or self._language_code_to_name_cache is None:
            try:
                from books.models import Language
                self._language_code_to_name_cache = {l.code: l.name for l in Language.objects.all()}  # type: ignore[attr-defined]
            except Exception as e:
                logger.warning(f"Error retrieving language from database: {e}")
                self._language_code_to_name_cache = {}
        # Try cache first
        name = self._language_code_to_name_cache.get(language_code)
        if name:
            return name
        # Fallback to common mappings if not found
        fallback_mappings = {
            "en": "English",
            "cn": "Chinese",
            "zh": "Chinese",
            "zh-CN": "Chinese",
            "zh-Hans": "Chinese",
            "zh-Hant": "Chinese (Traditional)",
            "fr": "French",
            "de": "German",
            "es": "Spanish",
            "it": "Italian",
        }
        return fallback_mappings.get(language_code, language_code)

    def _get_default_model(self):
        """Get default model based on provider"""
        defaults = {
            "openai": "gpt-3.5-turbo",
            "anthropic": "claude-3-sonnet-20240229",
            "google": "gemini-pro",
            "cohere": "command",
            "mistral": "mistral-large-latest",
            "ollama": "llama2",
        }
        return defaults.get(self.provider, "gpt-3.5-turbo")

    def _initialize_llm(self):
        """Initialize the appropriate LLM client based on provider"""
        try:
            if self.provider == "openai":
                if not OPENAI_AVAILABLE:
                    raise ImportError("langchain_openai not available")
                api_key = self.api_key or os.getenv("OPENAI_API_KEY")
                return ChatOpenAI(
                    model=self.model,
                    openai_api_key=api_key,
                    temperature=0.3,
                    max_tokens=2000,
                )
            elif self.provider == "anthropic":
                if not ANTHROPIC_AVAILABLE:
                    raise ImportError("langchain_anthropic not available")
                api_key = self.api_key or os.getenv("ANTHROPIC_API_KEY")
                return ChatAnthropic(
                    model=self.model,
                    anthropic_api_key=api_key,
                    temperature=0.3,
                    max_tokens=2000,
                )
            elif self.provider == "google":
                if not GOOGLE_AVAILABLE:
                    raise ImportError("langchain_google_genai not available")
                api_key = self.api_key or os.getenv("GOOGLE_API_KEY")
                return ChatGoogleGenerativeAI(
                    model=self.model,
                    google_api_key=api_key,
                    temperature=0.3,
                    max_tokens=2000,
                )
            elif self.provider == "cohere":
                if not COHERE_AVAILABLE:
                    raise ImportError("langchain_community not available")
                api_key = self.api_key or os.getenv("COHERE_API_KEY")
                return ChatCohere(
                    model=self.model,
                    cohere_api_key=api_key,
                    temperature=0.3,
                    max_tokens=2000,
                )
            elif self.provider == "ollama":
                if not OLLAMA_AVAILABLE:
                    raise ImportError("langchain_community not available")
                return Ollama(model=self.model, temperature=0.3)
            else:
                raise ValueError(f"Unsupported provider: {self.provider}")
        except Exception as e:
            logger.error(
                f"Error initializing LLM for provider {self.provider}: {str(e)}"
            )
            raise

    def switch_provider(self, provider: str, api_key: str = None, model: str = None):
        """
        Switch to a different LLM provider

        Args:
            provider: Provider name ('openai', 'anthropic', 'google', etc.)
            api_key: API key for the new provider
            model: Model name for the new provider
        """
        self.provider = provider
        if api_key:
            self.api_key = api_key
        if model:
            self.model = model
        else:
            self.model = self._get_default_model()

        # Reinitialize the LLM client
        self.llm = self._initialize_llm()
        logger.info(f"Switched to {provider} provider with model {self.model}")

    def get_available_providers(self) -> List[str]:
        """Get list of available LLM providers"""
        available = []
        if OPENAI_AVAILABLE:
            available.append("openai")
        if ANTHROPIC_AVAILABLE:
            available.append("anthropic")
        if GOOGLE_AVAILABLE:
            available.append("google")
        if COHERE_AVAILABLE:
            available.append("cohere")
        if OLLAMA_AVAILABLE:
            available.append("ollama")

        # Add providers that don't require specific packages
        available.extend(["mistral", "huggingface", "local"])
        return available

    def get_provider_models(self, provider: str = None) -> List[str]:
        """Get available models for a provider"""
        provider = provider or self.provider

        models = {
            "openai": [
                "gpt-4o",
                "gpt-4o-mini",
                "gpt-4-turbo",
                "gpt-3.5-turbo",
                "gpt-4",
            ],
            "anthropic": [
                "claude-3-5-sonnet-20241022",
                "claude-3-5-haiku-20241022",
                "claude-3-opus-20240229",
                "claude-3-sonnet-20240229",
                "claude-3-haiku-20240307",
            ],
            "google": [
                "gemini-1.5-pro",
                "gemini-1.5-flash",
                "gemini-pro",
                "gemini-pro-vision",
            ],
            "cohere": ["command", "command-light", "command-nightly"],
            "mistral": [
                "mistral-large-latest",
                "mistral-medium-latest",
                "mistral-small-latest",
            ],
            "ollama": [
                "llama2",
                "llama2:13b",
                "llama2:70b",
                "mistral",
                "codellama",
                "neural-chat",
            ],
        }

        return models.get(provider, [])

    def get_chain(self, prompt_template=None):
        """
        Get a LangChain chain for more advanced workflows

        Args:
            prompt_template: Optional prompt template for the chain

        Returns:
            LangChain chain instance
        """
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.output_parsers import StrOutputParser

        if prompt_template is None:
            prompt_template = ChatPromptTemplate.from_messages(
                [("system", "You are a helpful assistant."), ("user", "{input}")]
            )

        chain = prompt_template | self.llm | StrOutputParser()
        return chain

    def get_memory_chain(self):
        """
        Get a LangChain chain with conversation memory

        Returns:
            LangChain chain with memory
        """
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.output_parsers import StrOutputParser
        from langchain_core.memory import ConversationBufferMemory

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "You are a helpful assistant."),
                ("human", "{input}"),
            ]
        )

        memory = ConversationBufferMemory(
            return_messages=True, memory_key="chat_history"
        )

        chain = prompt | self.llm | StrOutputParser()
        return chain, memory

    def _call_llm(
        self,
        messages,
        temperature=0.3,
        max_tokens=2000,
        operation="other",
        source_book=None,
        source_chapter=None,
        target_book=None,
        target_chapter=None,
        source_lang=None,
        target_lang=None,
        user=None,
    ):
        """
        Make LLM API call using LangChain with comprehensive tracking

        Args:
            messages: List of message dictionaries or LangChain messages
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            operation: Type of operation being performed
            source_book: Source book object (what we're translating FROM)
            source_chapter: Source chapter object (what we're translating FROM)
            target_book: Target book object (what we're translating TO)
            target_chapter: Target chapter object (what we're translating TO)
            source_lang: Source language code
            target_lang: Target language code
            user: User making the request

        Returns:
            LLM response content
        """
        start_time = time.time()

        try:
            # Import tracking models here to avoid circular imports
            from .models import LLMServiceCall, LLMProvider

            # Convert dict messages to LangChain messages if needed
            if messages and isinstance(messages[0], dict):
                langchain_messages = []
                for msg in messages:
                    if msg["role"] == "system":
                        langchain_messages.append(SystemMessage(content=msg["content"]))
                    elif msg["role"] == "user":
                        langchain_messages.append(HumanMessage(content=msg["content"]))
                    # Add other message types as needed
                messages = langchain_messages

            # Calculate approximate input tokens
            input_text = ""
            for msg in messages:
                if hasattr(msg, "content"):
                    input_text += str(msg.content)
            input_tokens = len(input_text.split())  # Rough approximation

            # Update temperature and max_tokens if different from default
            if temperature != 0.3 or max_tokens != 2000:
                # Create a new instance with updated parameters
                temp_llm = self._initialize_llm()
                temp_llm.temperature = temperature
                temp_llm.max_tokens = max_tokens
                response = temp_llm.invoke(messages)
            else:
                response = self.llm.invoke(messages)

            response_time = int((time.time() - start_time) * 1000)
            output_tokens = len(response.content.split())

            # Track successful call
            try:
                provider_obj, created = LLMProvider.objects.get_or_create(
                    name=self.provider,
                    defaults={
                        "display_name": self.provider.title(),
                        "default_model": self.model,
                        "available_models": self.get_provider_models(self.provider),
                    },
                )

                LLMServiceCall.objects.create(
                    provider=provider_obj,
                    model_name=self.model,
                    operation=operation,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    status="success",
                    response_time_ms=response_time,
                    source_book=source_book,
                    source_chapter=source_chapter,
                    target_book=target_book,
                    target_chapter=target_chapter,
                    source_language=source_lang,
                    target_language=target_lang,
                    created_by=user,
                )
            except Exception as tracking_error:
                logger.warning(f"Failed to track LLM call: {tracking_error}")

            return response.content.strip()

        except Exception as e:
            response_time = int((time.time() - start_time) * 1000)

            # Track failed call
            try:
                from .models import LLMServiceCall, LLMProvider

                provider_obj, created = LLMProvider.objects.get_or_create(
                    name=self.provider,
                    defaults={
                        "display_name": self.provider.title(),
                        "default_model": self.model,
                        "available_models": self.get_provider_models(self.provider),
                    },
                )

                # Determine error status
                error_status = "error"
                if "timeout" in str(e).lower():
                    error_status = "timeout"
                elif "rate" in str(e).lower() or "quota" in str(e).lower():
                    error_status = "rate_limited"

                LLMServiceCall.objects.create(
                    provider=provider_obj,
                    model_name=self.model,
                    operation=operation,
                    input_tokens=input_tokens if "input_tokens" in locals() else None,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    status=error_status,
                    response_time_ms=response_time,
                    error_message=str(e),
                    source_book=source_book,
                    source_chapter=source_chapter,
                    target_book=target_book,
                    target_chapter=target_chapter,
                    source_language=source_lang,
                    target_language=target_lang,
                    created_by=user,
                )
            except Exception as tracking_error:
                logger.warning(f"Failed to track LLM error: {tracking_error}")

            logger.error(
                f"Error calling LLM API ({self.provider}/{self.model}): {str(e)}"
            )
            raise

    def divide_into_chapters(
        self, text: str, book=None, user=None
    ) -> List[Dict[str, Any]]:
        """
        Use LLM to intelligently divide book into chapters
        Returns list of dicts with 'title' and 'text' keys
        """

        prompt = f"""
        Please analyze the following text and divide it into logical chapters. 
        For each chapter, provide:
        1. A descriptive title
        2. The full text content
        
        Return the result as a JSON array where each object has 'title' and 'text' fields.
        
        Text to analyze:
        {text[:8000]}...  # Truncate to avoid token limits
        
        If the text is very long, focus on finding natural chapter breaks based on:
        - Chapter headings or numbers
        - Scene transitions
        - Topic changes
        - Paragraph breaks that indicate new sections
        """
        # Currently not working, so we're using the simple division method below
        # try:
        #     messages = [
        #         SystemMessage(
        #             content="You are a helpful assistant that specializes in analyzing and structuring text content."
        #         ),
        #         HumanMessage(content=prompt),
        #     ]

        #     result = self._call_llm(
        #         messages,
        #         temperature=0.3,
        #         max_tokens=4000,
        #         operation="chapter_division",
        #         book=book,
        #         user=user,
        #     )

        #     # Try to parse JSON response
        #     try:
        #         chapters = json.loads(result)
        #         if isinstance(chapters, list):
        #             return chapters
        #     except json.JSONDecodeError:
        #         logger.warning(
        #             "LLM response was not valid JSON, falling back to simple division"
        #         )

        # except Exception as e:
        #     logger.error(f"Error calling LLM API: {str(e)}")

        # Fallback: Simple chapter division
        return self._simple_chapter_division(text)

    def _simple_chapter_division(self, text: str) -> List[Dict[str, Any]]:
        """Simple fallback chapter division by sentence count"""
        chapters = []
        
        # Enhanced regex for chapter headings - captures full titles including descriptions
        # Chinese patterns: 第一章, 第一章 xxx, 第1章, 第1章 xxx, etc.
        # English patterns: Chapter 1, Chapter 1: Title, CHAPTER 1, etc.
        chapter_heading_pattern = re.compile(
            r"(第[\d一二三四五六七八九十百千零〇两]+[章回节卷][^\n]*?)(?=\n|第[\d一二三四五六七八九十百千零〇两]+[章回节卷]|Chapter\s*\d+|CHAPTER\s*\d+|$)|"
            r"(Chapter\s*\d+[^\n]*?)(?=\n|第[\d一二三四五六七八九十百千零〇两]+[章回节卷]|Chapter\s*\d+|CHAPTER\s*\d+|$)|"
            r"(CHAPTER\s*\d+[^\n]*?)(?=\n|第[\d一二三四五六七八九十百千零〇两]+[章回节卷]|Chapter\s*\d+|CHAPTER\s*\d+|$)",
            re.UNICODE | re.MULTILINE
        )

        # Find all chapter headings and their positions
        matches = list(chapter_heading_pattern.finditer(text))
        
        if matches and len(matches) > 1:
            # Split by chapter headings
            for idx, match in enumerate(matches):
                start = match.start()
                end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
                
                # Extract the full title (including any description after the chapter number)
                full_title = match.group().strip()
                
                # Get the chapter content (excluding the title)
                chapter_content = text[start:end].strip()
                
                # Remove the title from the beginning of the content
                if chapter_content.startswith(full_title):
                    chapter_content = chapter_content[len(full_title):].strip()
                
                # Clean up any leading/trailing whitespace and newlines
                chapter_content = re.sub(r'^\s*[\n\r]+', '', chapter_content)
                chapter_content = re.sub(r'[\n\r]+\s*$', '', chapter_content)
                
                chapters.append({
                    "title": full_title, 
                    "text": chapter_content
                })
            return chapters

        # Fallback: split by sentence-ending punctuation and character count
        # Chinese sentence-ending punctuation: 。！？!? (fullwidth and halfwidth)
        sentence_endings = re.compile(r"[。！？!?]")
        sentences = sentence_endings.split(text)
        current_chunk = ""
        chapter_num = 1
        max_chars_per_chapter = 5000  # Define this variable

        for sentence in sentences:
            if not sentence.strip():
                continue
            if current_chunk:
                current_chunk += sentence + "。"  # Add back a period for readability
            else:
                current_chunk = sentence + "。"
            if len(current_chunk) >= max_chars_per_chapter:
                chapters.append(
                    {"title": f"Chapter {chapter_num}", "text": current_chunk.strip()}
                )
                chapter_num += 1
                current_chunk = ""
        if current_chunk:
            chapters.append(
                {"title": f"Chapter {chapter_num}", "text": current_chunk.strip()}
            )
        return chapters

    def translate_chapter(
        self,
        chapter_text: str,
        target_language: str,
        context_abstract: str = "",
        source_chapter=None,
        target_chapter=None,
        user=None,
    ) -> str:
        """
        Translate chapter text to target language with context
        """
        target_lang_name = self._get_language_name(target_language)

        # Detect source language from chapter
        source_language = ""
        source_book = None
        if source_chapter:
            if source_chapter.language:
                source_language = source_chapter.language.code
            elif source_chapter.book and source_chapter.book.language:
                source_language = source_chapter.book.language.code
            source_book = source_chapter.book

        # Get target book from target chapter
        target_book = None
        if target_chapter:
            target_book = target_chapter.book

        context_prompt = (
            f"\n\nContext from previous chapters:\n{context_abstract}"
            if context_abstract
            else ""
        )

        prompt = f"""
        Please translate the following text to {target_lang_name}. 
        Maintain the original tone, style, and formatting.
        Pay attention to consistency with the provided context.{context_prompt}
        
        Text to translate:
        {chapter_text}
        """

        try:
            messages = [
                SystemMessage(
                    content=f"You are a professional translator specializing in literary translation to {target_lang_name}."
                ),
                HumanMessage(content=prompt),
            ]

            return self._call_llm(
                messages,
                temperature=0.3,
                max_tokens=4000,
                operation="translation",
                source_book=source_book,
                source_chapter=source_chapter,
                target_book=target_book,
                target_chapter=target_chapter,
                source_lang=source_language,
                target_lang=target_language,
                user=user,
            )

        except Exception as e:
            logger.error(f"Error translating chapter: {str(e)}")
            return f"[Translation Error: {str(e)}]\n\nOriginal text:\n{chapter_text}"

    def translate_text(
        self, text: str, target_language: str, user=None, source_language=None
    ) -> str:
        """
        Translate a short text (e.g., title or key term) to the target language.
        """
        target_lang_name = self._get_language_name(target_language)
        prompt = f"""
        Please translate the following text to {target_lang_name}. Maintain the original meaning and style.
        Text to translate:
        {text}
        """
        try:
            messages = [
                SystemMessage(
                    content=f"You are a professional translator specializing in literary translation to {target_lang_name}."
                ),
                HumanMessage(content=prompt),
            ]

            return self._call_llm(
                messages,
                temperature=0.3,
                max_tokens=256,
                operation="translation",
                source_lang=source_language or "",
                target_lang=target_language,
                user=user,
            )

        except Exception as e:
            logger.error(f"Error translating text: {str(e)}")
            return f"[Translation Error: {str(e)}] {text}"

    def generate_chapter_abstract(
        self,
        chapter_text: str,
        target_language: str = None,
        source_chapter=None,
        target_chapter=None,
        user=None,
    ) -> str:
        """
        Generate a summary/abstract of the chapter in the specified target language (default: original language)
        """
        language_name = (
            self._get_language_name(target_language)
            if target_language
            else "the original language"
        )
        language_instruction = (
            f" in {language_name}"
            if target_language
            else " in the original language of chapter text"
        )

        # Detect source language from chapter
        source_language = ""
        source_book = None
        if source_chapter:
            if source_chapter.language:
                source_language = source_chapter.language.code
            elif source_chapter.book and source_chapter.book.language:
                source_language = source_chapter.book.language.code
            source_book = source_chapter.book

        # Get target book from target chapter
        target_book = None
        if target_chapter:
            target_book = target_chapter.book

        prompt = f"""
        Please create a concise abstract (2-3 sentences){language_instruction} of the following chapter that will help maintain consistency in translation. 
        Focus on:
        - Main themes and topics
        - Key characters or concepts
        - Tone and style
        - Important context for translation
        
        Chapter text:
        {chapter_text[:2000]}...
        """
        system_prompt = f"You are a helpful assistant that creates concise summaries for translation context. Always respond in {language_name}."

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=prompt),
            ]

            return self._call_llm(
                messages,
                temperature=0.3,
                max_tokens=200,
                operation="abstract_generation",
                source_book=source_book,
                source_chapter=source_chapter,
                target_book=target_book,
                target_chapter=target_chapter,
                source_lang=source_language,
                target_lang=target_language or "",
                user=user,
            )

        except Exception as e:
            logger.error(f"Error generating abstract: {str(e)}")
            return f"Chapter abstract (auto-generated excerpt): {chapter_text[:200]}..."

    def extract_key_terms(
        self,
        chapter_text: str,
        target_language: str = None,
        source_chapter=None,
        target_chapter=None,
        user=None,
    ) -> List[str]:
        """
        Extract key terms that should be consistently translated, in the specified target language (default: original language)
        """
        language_name = (
            self._get_language_name(target_language)
            if target_language
            else "the original language"
        )
        language_instruction = (
            f" in {language_name}" if target_language else " in the original language"
        )

        # Detect source language from chapter
        source_language = ""
        source_book = None
        if source_chapter:
            if source_chapter.language:
                source_language = source_chapter.language.code
            elif source_chapter.book and source_chapter.book.language:
                source_language = source_chapter.book.language.code
            source_book = source_chapter.book

        # Get target book from target chapter
        target_book = None
        if target_chapter:
            target_book = target_chapter.book

        prompt = f"""
        Please identify 5-10 key terms{language_instruction} from the following text that are important for consistent translation. 
        Focus on:
        - Proper nouns (names, places)
        - Technical terms
        - Repeated important concepts
        - Cultural references
        
        Return as a JSON array of strings.
        
        Text:
        {chapter_text[:1500]}...
        """
        system_prompt = f"You are a helpful assistant that identifies key terms for translation consistency. Always respond in {language_name}."

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=prompt),
            ]

            result = self._call_llm(
                messages,
                temperature=0.2,
                max_tokens=300,
                operation="key_terms_extraction",
                source_book=source_book,
                source_chapter=source_chapter,
                target_book=target_book,
                target_chapter=target_chapter,
                source_lang=source_language,
                target_lang=target_language or "",
                user=user,
            )

            try:
                terms = json.loads(result)
                if isinstance(terms, list):
                    return terms
            except json.JSONDecodeError:
                # Try to extract terms from a text response
                terms = re.findall(r'"([^"]+)"', result)
                return terms[:10]  # Limit to 10 terms

        except Exception as e:
            logger.error(f"Error extracting key terms: {str(e)}")

        return []

    def analyze_chapter(
        self,
        chapter_text: str,
        target_language: str = None,
        source_chapter=None,
        target_chapter=None,
        user=None,
    ) -> Dict[str, Any]:
        """
        Analyze a chapter to generate both a summary, extract key terms, and rate the content in a single LLM call.
        Returns a dict with 'summary', 'key_terms', and 'rating' keys.
        """
        language_name = (
            self._get_language_name(target_language)
            if target_language
            else "the original language"
        )
        language_instruction = (
            f" in {language_name}" if target_language else " in the original language of chapter text"
        )

        # Detect source language from chapter
        source_language = ""
        source_book = None
        if source_chapter:
            if source_chapter.language:
                source_language = source_chapter.language.code
            elif source_chapter.book and source_chapter.book.language:
                source_language = source_chapter.book.language.code
            source_book = source_chapter.book

        # Get target book from target chapter
        target_book = None
        if target_chapter:
            target_book = target_chapter.book

        prompt = f"""
        Given the following chapter text, please:
        1. Write a concise summary (2-3 sentences){language_instruction} that summarizes the main themes, key characters, tone, and important context for translation.
        2. Identify 5-10 key terms (proper nouns, technical terms, repeated concepts, or cultural references) that are important for consistent translation.
        3. Rate the content of the chapter for appropriate audience. Choose one rating from ONLY the following list: [\"everybody\", \"teen\", \"mature\", \"adult\"].

        Return your answer as a JSON object with three fields:
        - \"summary\": the summary as a string
        - \"key_terms\": a list of strings
        - \"rating\": one of [\"everybody\", \"teen\", \"mature\", \"adult\"]

        Chapter text:
        {chapter_text}
        """
        system_prompt = f"You are a helpful assistant that creates concise summaries, identifies key terms, and rates content for audience appropriateness for translation context. Always respond in {language_name}."

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=prompt),
            ]

            result = self._call_llm(
                messages,
                temperature=0.3,
                max_tokens=500,
                operation="analyze_chapter",
                source_book=source_book,
                source_chapter=source_chapter,
                target_book=target_book,
                target_chapter=target_chapter,
                source_lang=source_language,
                target_lang=target_language or "",
                user=user,
            )

            # Try to parse JSON response
            try:
                data = json.loads(result)
                summary = data.get("summary", "")
                key_terms = data.get("key_terms", [])
                rating = data.get("rating", "")
                if not isinstance(key_terms, list):
                    key_terms = []
                if rating not in ["everybody", "teen", "mature", "adult"]:
                    rating = "everybody"
                return {"summary": summary, "key_terms": key_terms, "rating": rating}
            except json.JSONDecodeError:
                # Fallback: try to extract summary, key terms, and rating from text
                summary = ""
                key_terms = []
                rating = "everybody"
                summary_match = re.search(r"summary\s*[:：]\s*(.+?)(?:key terms|rating|$)", result, re.IGNORECASE | re.DOTALL)
                if summary_match:
                    summary = summary_match.group(1).strip()
                key_terms_match = re.findall(r'"([^"]+)"', result)
                if not key_terms_match:
                    # Try comma-separated terms
                    key_terms_match = re.findall(r"key terms\s*[:：]\s*(.+?)(?:rating|$)", result, re.IGNORECASE)
                    if key_terms_match:
                        key_terms = [t.strip() for t in key_terms_match[0].split(",") if t.strip()]
                else:
                    key_terms = key_terms_match[:10]
                rating_match = re.search(r"rating\s*[:：]\s*(everybody|teen|mature|adult)", result, re.IGNORECASE)
                if rating_match:
                    rating = rating_match.group(1).lower()
                return {"summary": summary or result[:200], "key_terms": key_terms, "rating": rating}
        except Exception as e:
            logger.error(f"Error analyzing chapter: {str(e)}")
            return {"summary": f"Chapter summary (auto-generated excerpt): {chapter_text[:200]}...", "key_terms": [], "rating": "everybody"}

    def clear_language_cache(self):
        """Clear the cached language code-to-name mapping."""
        self._language_code_to_name_cache = None
