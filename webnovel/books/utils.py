import os
import logging
import tempfile
from datetime import datetime
import uuid

import PyPDF2

# from docx import Document
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup

from django.core.exceptions import ValidationError
from django.templatetags.static import static
from .models import Book
from accounts.models import User
from django.core.files.storage import default_storage

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
    def extract_text_from_file(file_obj_or_path):
        """
        Extract text based on file extension.
        
        Args:
            file_obj_or_path: Either a file-like object or a file path string
            
        Returns:
            Extracted text as string
        """
        # Determine if we have a file object or path
        if hasattr(file_obj_or_path, 'name'):
            # It's a file-like object
            filename = file_obj_or_path.name
            file_obj = file_obj_or_path
        else:
            # It's a path string
            filename = file_obj_or_path
            file_obj = None
            
        _, ext = os.path.splitext(filename.lower())

        extractors = {
            ".pdf": TextExtractor._extract_from_pdf,
            ".txt": TextExtractor._extract_from_txt,
            # ".docx": TextExtractor._extract_from_docx,
            ".epub": TextExtractor._extract_from_epub,
        }

        extractor = extractors.get(ext)
        if not extractor:
            raise ValidationError(f"Unsupported file format: {ext}")

        return extractor(file_obj_or_path)

    @staticmethod
    def _extract_from_pdf(file_obj_or_path):
        """Extract text from PDF file"""
        text = ""
        try:
            if hasattr(file_obj_or_path, 'read'):
                # It's a file-like object
                pdf_reader = PyPDF2.PdfReader(file_obj_or_path)
            else:
                # It's a path string, open with storage
                with default_storage.open(file_obj_or_path, "rb") as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
        except Exception as e:
            raise ValidationError(f"Error reading PDF: {str(e)}")
        return text.strip()

    @staticmethod
    def _extract_from_txt(file_obj_or_path):
        """Extract text from TXT file with intelligent encoding detection"""
        try:
            if hasattr(file_obj_or_path, 'read'):
                # It's a file-like object
                content_bytes = file_obj_or_path.read()
                # Reset file pointer for potential future reads
                file_obj_or_path.seek(0)
            else:
                # It's a path string, open with storage
                with default_storage.open(file_obj_or_path, "rb") as file:
                    content_bytes = file.read()

            # Use intelligent decoding with charset detection
            return decode_text(content_bytes)
        except Exception as e:
            raise ValidationError(f"Error reading TXT file: {str(e)}")

    # @staticmethod
    # def _extract_from_docx(file_obj_or_path):
    #     try:
    #         if hasattr(file_obj_or_path, 'name'):
    #             # It's a file-like object
    #             doc = Document(file_obj_or_path)
    #         else:
    #             # It's a path string
    #             doc = Document(file_obj_or_path)
    #         text = []
    #         for paragraph in doc.paragraphs:
    #             text.append(paragraph.text)
    #         return "\n".join(text)
    #     except Exception as e:
    #         raise ValidationError(f"Error reading DOCX: {str(e)}")

    @staticmethod
    def _extract_from_epub(file_obj_or_path):
        """Extract text from EPUB file"""
        try:
            if hasattr(file_obj_or_path, 'name'):
                # It's a file-like object, we need to save it temporarily
                with tempfile.NamedTemporaryFile(delete=False, suffix='.epub') as temp_file:
                    # Copy content to temporary file
                    file_obj_or_path.seek(0)
                    temp_file.write(file_obj_or_path.read())
                    temp_file_path = temp_file.name
                
                try:
                    book = epub.read_epub(temp_file_path)
                finally:
                    # Clean up temporary file
                    os.unlink(temp_file_path)
            else:
                # It's a path string, we need to download it temporarily for S3
                if hasattr(default_storage, 'url'):
                    # For S3 storage, download to temp file
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.epub') as temp_file:
                        with default_storage.open(file_obj_or_path, 'rb') as source_file:
                            temp_file.write(source_file.read())
                        temp_file_path = temp_file.name
                    
                    try:
                        book = epub.read_epub(temp_file_path)
                    finally:
                        # Clean up temporary file
                        os.unlink(temp_file_path)
                else:
                    # For local storage, use path directly
                    book = epub.read_epub(file_obj_or_path)

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
    # For uploaded files, we can use the file object directly
    return TextExtractor.extract_text_from_file(uploaded_file)


def get_default_book_cover_url():
    """Get the URL for the default book cover image"""
    return static("images/default_book_cover.png")


def get_book_cover_url(book):
    """Get the cover image URL for a book with fallback to default"""
    if not isinstance(book, Book):
        return get_default_book_cover_url()
    return book.get_cover_image_url()


def get_book_cover_data(book):
    """Get comprehensive cover image data for a book"""
    if not isinstance(book, Book):
        return {
            'url': get_default_book_cover_url(),
            'is_default': True,
            'custom_image_url': None,
        }
    return book.get_cover_image_data()


def format_book_cover_for_display(book, width=300, height=400):
    """Format book cover for display with specific dimensions"""
    cover_data = get_book_cover_data(book)
    return {
        'url': cover_data['url'],
        'alt_text': f"Cover for {book.title}" if hasattr(book, 'title') else "Book cover",
        'width': width,
        'height': height,
        'is_default': cover_data['is_default'],
    }


# User Avatar Utility Functions
def get_default_user_avatar_url():
    """Get the URL for the default user avatar image"""
    return static("images/default_user_avatar.png")


def get_user_avatar_url(user):
    """Get the avatar URL for a user with fallback to default"""
    if not isinstance(user, User):
        return get_default_user_avatar_url()
    return user.get_avatar_url()


def get_user_avatar_thumbnail_url(user):
    """Get the avatar thumbnail URL for a user with fallback to default"""
    if not isinstance(user, User):
        return get_default_user_avatar_url()
    return user.get_avatar_thumbnail_url()


def get_user_avatar_data(user):
    """Get comprehensive avatar data for a user"""
    if not isinstance(user, User):
        return {
            'url': get_default_user_avatar_url(),
            'thumbnail_url': get_default_user_avatar_url(),
            'is_default': True,
            'custom_avatar_url': None,
            'custom_thumbnail_url': None,
        }
    return user.get_avatar_data()
