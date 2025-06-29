import os
import logging

import PyPDF2

# from docx import Document
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup

from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

try:
    from charset_normalizer import detect

    CHARSET_NORMALIZER_AVAILABLE = True
except ImportError:
    CHARSET_NORMALIZER_AVAILABLE = False
    logger.warning(
        "charset_normalizer not available, falling back to basic encoding detection"
    )


def decode_text(input_data, encoding=None, fallback_encodings=None):
    """
    Intelligently decodes bytes or str to Unicode string using charset-normalizer.

    Args:
        input_data: Bytes or string to decode
        encoding: Preferred encoding (if None, will auto-detect)
        fallback_encodings: List of encodings to try if auto-detection fails

    Returns:
        Decoded Unicode string

    Raises:
        TypeError: If input is not bytes or str
        UnicodeDecodeError: If decoding fails with all attempted encodings
    """
    if isinstance(input_data, str):
        return input_data

    if not isinstance(input_data, bytes):
        raise TypeError("Input must be bytes or str")

    # If no encoding specified, try auto-detection
    if encoding is None:
        if CHARSET_NORMALIZER_AVAILABLE:
            try:
                # Use charset-normalizer for intelligent detection
                result = detect(input_data)
                detected_encoding = result["encoding"]
                confidence = result["confidence"]

                if detected_encoding and confidence > 0.7:  # High confidence threshold
                    logger.info(
                        f"Auto-detected encoding: {detected_encoding} (confidence: {confidence:.2f})"
                    )
                    return input_data.decode(detected_encoding)
                else:
                    logger.warning(
                        f"Low confidence encoding detection: {detected_encoding} (confidence: {confidence:.2f})"
                    )
            except Exception as e:
                logger.warning(f"Charset detection failed: {str(e)}")

        # Fallback to common encodings if auto-detection fails or unavailable
        fallback_encodings = fallback_encodings or [
            "utf-8",
            "gbk",
            "gb2312",
            "gb18030",
            "big5",
            "utf-16",
            "utf-16le",
            "utf-16be",
            "latin-1",
        ]

        for enc in fallback_encodings:
            try:
                decoded = input_data.decode(enc)
                logger.info(f"Successfully decoded with {enc}")
                return decoded
            except UnicodeDecodeError:
                continue

        # If all fallbacks fail, try with error handling
        try:
            return input_data.decode("utf-8", errors="replace")
        except Exception:
            return input_data.decode("latin-1", errors="replace")

    else:
        # Use specified encoding
        try:
            return input_data.decode(encoding)
        except UnicodeDecodeError as e:
            logger.warning(f"Failed to decode with {encoding}: {str(e)}")

            # Try fallback encodings
            fallback_encodings = fallback_encodings or ["utf-8", "gbk", "latin-1"]
            for enc in fallback_encodings:
                if enc != encoding:
                    try:
                        decoded = input_data.decode(enc)
                        logger.info(
                            f"Successfully decoded with fallback encoding {enc}"
                        )
                        return decoded
                    except UnicodeDecodeError:
                        continue

            # Last resort: decode with error handling
            return input_data.decode(encoding, errors="replace")


class TextExtractor:
    """Utility class for extracting text from various file formats"""

    @staticmethod
    def extract_text_from_file(file_path):
        """Extract text based on file extension"""
        _, ext = os.path.splitext(file_path.lower())

        extractors = {
            ".pdf": TextExtractor._extract_from_pdf,
            ".txt": TextExtractor._extract_from_txt,
            # ".docx": TextExtractor._extract_from_docx,
            ".epub": TextExtractor._extract_from_epub,
        }

        extractor = extractors.get(ext)
        if not extractor:
            raise ValidationError(f"Unsupported file format: {ext}")

        return extractor(file_path)

    @staticmethod
    def _extract_from_pdf(file_path):
        text = ""
        try:
            with open(file_path, "rb") as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
        except Exception as e:
            raise ValidationError(f"Error reading PDF: {str(e)}")
        return text.strip()

    @staticmethod
    def _extract_from_txt(file_path):
        """Extract text from TXT file with intelligent encoding detection"""
        try:
            # Read file as bytes first
            with open(file_path, "rb") as file:
                content_bytes = file.read()

            # Use intelligent decoding with charset detection
            return decode_text(content_bytes)
        except Exception as e:
            raise ValidationError(f"Error reading TXT file: {str(e)}")

    # @staticmethod
    # def _extract_from_docx(file_path):
    #     try:
    #         doc = Document(file_path)
    #         text = []
    #         for paragraph in doc.paragraphs:
    #         text.append(paragraph.text)
    #         return "\n".join(text)
    #     except Exception as e:
    #         raise ValidationError(f"Error reading DOCX: {str(e)}")

    @staticmethod
    def _extract_from_epub(file_path):
        try:
            book = epub.read_epub(file_path)
            text = []

            for item in book.get_items():
                if item.get_type() == ebooklib.ITEM_DOCUMENT:
                    soup = BeautifulSoup(item.get_content(), "html.parser")
                    text.append(soup.get_text())

            return "\n".join(text)
        except Exception as e:
            raise ValidationError(f"Error reading EPUB: {str(e)}")


def extract_text_from_file(uploaded_file):
    """Main function to extract text from uploaded file"""
    return TextExtractor.extract_text_from_file(uploaded_file.path)
