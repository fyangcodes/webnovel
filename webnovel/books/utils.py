import os

import PyPDF2
from typing import Optional
from docx import Document
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile


class TextExtractor:
    """Utility class for extracting text from various file formats"""

    @staticmethod
    def extract_text_from_file(file_path):
        """Extract text based on file extension"""
        _, ext = os.path.splitext(file_path.lower())

        extractors = {
            ".pdf": TextExtractor._extract_from_pdf,
            ".txt": TextExtractor._extract_from_txt,
            ".docx": TextExtractor._extract_from_docx,
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
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                return file.read()
        except UnicodeDecodeError:
            # Try with different encoding
            with open(file_path, "r", encoding="latin-1") as file:
                return file.read()

    @staticmethod
    def _extract_from_docx(file_path):
        try:
            doc = Document(file_path)
            text = []
            for paragraph in doc.paragraphs:
                text.append(paragraph.text)
            return "\n".join(text)
        except Exception as e:
            raise ValidationError(f"Error reading DOCX: {str(e)}")

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
