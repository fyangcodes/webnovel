# llm_integration/services.py
import openai
import json
import re
from typing import List, Dict, Any
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class LLMTranslationService:
    """Service for handling LLM API calls for translation and text processing"""

    def __init__(self, api_key=None, model="gpt-4"):
        self.api_key = api_key or getattr(settings, "OPENAI_API_KEY", None)
        self.model = model
        if self.api_key:
            openai.api_key = self.api_key

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

        try:
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that specializes in analyzing and structuring text content.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=4000,
            )

            result = response.choices[0].message.content.strip()

            # Try to parse JSON response
            try:
                chapters = json.loads(result)
                if isinstance(chapters, list):
                    return chapters
            except json.JSONDecodeError:
                logger.warning(
                    "LLM response was not valid JSON, falling back to simple division"
                )

        except Exception as e:
            logger.error(f"Error calling OpenAI API: {str(e)}")

        # Fallback: Simple chapter division
        return self._simple_chapter_division(text)

    def _simple_chapter_division(
        self, text: str, max_chars_per_chapter: int = 5000
    ) -> List[Dict[str, Any]]:
        """
        Fallback method to divide text into chapters based on length
        """
        chapters = []
        words = text.split()
        current_chapter = []
        current_length = 0
        chapter_num = 1

        for word in words:
            current_chapter.append(word)
            current_length += len(word) + 1  # +1 for space

            if current_length >= max_chars_per_chapter:
                # Try to break at a sentence end
                chapter_text = " ".join(current_chapter)

                # Find last sentence end
                last_sentence_end = max(
                    chapter_text.rfind(". "),
                    chapter_text.rfind("! "),
                    chapter_text.rfind("? "),
                )

                if (
                    last_sentence_end > len(chapter_text) * 0.7
                ):  # If we found a good break point
                    final_text = chapter_text[: last_sentence_end + 1]
                    remaining = chapter_text[last_sentence_end + 2 :]

                    chapters.append(
                        {"title": f"Chapter {chapter_num}", "text": final_text.strip()}
                    )

                    current_chapter = remaining.split() if remaining else []
                    current_length = len(remaining) if remaining else 0
                else:
                    chapters.append(
                        {
                            "title": f"Chapter {chapter_num}",
                            "text": chapter_text.strip(),
                        }
                    )
                    current_chapter = []
                    current_length = 0

                chapter_num += 1

        # Add remaining text as final chapter
        if current_chapter:
            chapters.append(
                {
                    "title": f"Chapter {chapter_num}",
                    "text": " ".join(current_chapter).strip(),
                }
            )

        return chapters

    def generate_chapter_abstract(self, chapter_text: str) -> str:
        """
        Generate a summary/abstract of the chapter for translation context
        """
        prompt = f"""
        Please create a concise abstract (2-3 sentences) of the following chapter that will help maintain consistency in translation. 
        Focus on:
        - Main themes and topics
        - Key characters or concepts
        - Tone and style
        - Important context for translation
        
        Chapter text:
        {chapter_text[:2000]}...
        """

        try:
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that creates concise summaries for translation context.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=200,
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.error(f"Error generating abstract: {str(e)}")
            return f"Chapter abstract (auto-generated): {chapter_text[:200]}..."

    def extract_key_terms(self, chapter_text: str) -> List[str]:
        """
        Extract key terms that should be consistently translated
        """
        prompt = f"""
        Please identify 5-10 key terms from the following text that are important for consistent translation. 
        Focus on:
        - Proper nouns (names, places)
        - Technical terms
        - Repeated important concepts
        - Cultural references
        
        Return as a JSON array of strings.
        
        Text:
        {chapter_text[:1500]}...
        """

        try:
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that identifies key terms for translation consistency.",
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
        language_names = {
            "en": "English",
            "de": "German",
            "fr": "French",
            "es": "Spanish",
            "it": "Italian",
        }

        target_lang_name = language_names.get(target_language, target_language)

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
            response = openai.ChatCompletion.create(
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


