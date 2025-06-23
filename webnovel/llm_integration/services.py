# llm_integration/services.py
import openai
import json
import re
from typing import List, Dict, Any
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


def decode_gb_text(input_data, encoding="gbk"):
    """
    Decodes bytes or str in GB encoding to Unicode string.
    If input is already str, returns as is.
    """
    if isinstance(input_data, bytes):
        return input_data.decode(encoding)
    elif isinstance(input_data, str):
        return input_data
    else:
        raise TypeError("Input must be bytes or str")


class LLMTranslationService:
    """Service for handling LLM API calls for translation and text processing"""

    LANGUAGE_CODE_TO_NAME = {
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
        # Add more as needed
    }

    def __init__(self, api_key=None, model="gpt-3.5-turbo"):
        self.api_key = api_key or getattr(settings, "LLM_API_KEY", None)
        self.model = model
        if self.api_key:
            self.client = openai.OpenAI(api_key=self.api_key)
        else:
            self.client = None

    def divide_into_chapters(self, text: str) -> List[Dict[str, Any]]:
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

        # try:
        #     if not self.client:
        #         raise Exception("OpenAI client not initialized. No API key provided.")
        #     response = self.client.chat.completions.create(
        #         model=self.model,
        #         messages=[
        #             {
        #                 "role": "system",
        #                 "content": "You are a helpful assistant that specializes in analyzing and structuring text content.",
        #             },
        #             {"role": "user", "content": prompt},
        #         ],
        #         temperature=0.3,
        #         max_tokens=4000,
        #     )
        #     result = response.choices[0].message.content.strip()

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
        #     logger.error(f"Error calling OpenAI API: {str(e)}")

        # Fallback: Simple chapter division
        return self._simple_chapter_division(text)

    def _simple_chapter_division(
        self, text: str, max_chars_per_chapter: int = 5000
    ) -> List[Dict[str, Any]]:
        """
        Improved method to divide text into chapters for Chinese novels:
        1. Try to split by chapter headings (e.g., 第X章, 第X回, Chapter X)
        2. If no headings found, split by sentence-ending punctuation and character count
        """
        chapters = []
        # Regex for common chapter headings in Chinese and English
        chapter_heading_pattern = re.compile(
            r'(第[\d一二三四五六七八九十百千零〇两]+[章回节卷]|Chapter\\s*\\d+|CHAPTER\\s*\\d+)', re.UNICODE
        )

        # Find all chapter headings and their positions
        matches = list(chapter_heading_pattern.finditer(text))
        if matches and len(matches) > 1:
            # Split by chapter headings
            for idx, match in enumerate(matches):
                start = match.start()
                end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
                chapter_title = match.group()
                chapter_text = text[start:end].strip()
                chapters.append({
                    "title": chapter_title,
                    "text": chapter_text
                })
            return chapters

        # Fallback: split by sentence-ending punctuation and character count
        # Chinese sentence-ending punctuation: 。！？!? (fullwidth and halfwidth)
        sentence_endings = re.compile(r'[。！？!?]')
        sentences = sentence_endings.split(text)
        current_chunk = ''
        chapter_num = 1
        for sentence in sentences:
            if not sentence.strip():
                continue
            if current_chunk:
                current_chunk += sentence + '。'  # Add back a period for readability
            else:
                current_chunk = sentence + '。'
            if len(current_chunk) >= max_chars_per_chapter:
                chapters.append({
                    "title": f"Chapter {chapter_num}",
                    "text": current_chunk.strip()
                })
                chapter_num += 1
                current_chunk = ''
        if current_chunk:
            chapters.append({
                "title": f"Chapter {chapter_num}",
                "text": current_chunk.strip()
            })
        return chapters

    def generate_chapter_abstract(self, chapter_text: str, target_language: str = None) -> str:
        """
        Generate a summary/abstract of the chapter in the specified target language (default: original language)
        """
        language_name = self.LANGUAGE_CODE_TO_NAME.get(target_language, target_language) if target_language else "the original language"
        language_instruction = f" in {language_name}" if target_language else " in the original language of chapter text"
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
            if not self.client:
                raise Exception("OpenAI client not initialized. No API key provided.")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=200,
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.error(f"Error generating abstract: {str(e)}")
            return f"Chapter abstract (auto-generated excerpt): {chapter_text[:200]}..."

    def extract_key_terms(self, chapter_text: str, target_language: str = None) -> List[str]:
        """
        Extract key terms that should be consistently translated, in the specified target language (default: original language)
        """
        language_name = self.LANGUAGE_CODE_TO_NAME.get(target_language, target_language) if target_language else "the original language"
        language_instruction = f" in {language_name}" if target_language else " in the original language"
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
            if not self.client:
                raise Exception("OpenAI client not initialized. No API key provided.")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=300,
            )

            result = response.choices[0].message.content.strip()

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

    def translate_chapter(
        self, chapter_text: str, target_language: str, context_abstract: str = ""
    ) -> str:
        """
        Translate chapter text to target language with context
        """
        target_lang_name = self.LANGUAGE_CODE_TO_NAME.get(target_language, target_language)

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
            if not self.client:
                raise Exception("OpenAI client not initialized. No API key provided.")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": f"You are a professional translator specializing in literary translation to {target_lang_name}.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=4000,
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.error(f"Error translating chapter: {str(e)}")
            return f"[Translation Error: {str(e)}]\n\nOriginal text:\n{chapter_text}"
