from celery import shared_task
from django.utils import timezone
from .models import Book, Chapter
from .utils import extract_text_from_file
from llm_integration.services import LLMTranslationService
import logging

logger = logging.getLogger(__name__)


@shared_task
def process_book_async(book_id):
    """Main task to process a book through the entire pipeline"""
    try:
        book = Book.objects.get(id=book_id)
        book.status = "processing"
        book.processing_started_at = timezone.now()
        book.processing_progress = 10
        book.save()

        # Step 1: Extract text
        logger.info(f"Extracting text from book {book.id}")
        text = extract_text_from_file(book.uploaded_file)
        book.estimated_words = len(text.split())
        book.processing_progress = 20
        book.save()

        # Step 2: Divide into chapters
        logger.info(f"Dividing book {book.id} into chapters")
        book.status = "chunking"
        book.save()

        llm_service = LLMTranslationService()
        chapters_data = llm_service.divide_into_chapters(text)

        book.processing_progress = 40
        book.save()

        # Step 3: Create chapter objects
        chapters = []
        for i, chapter_data in enumerate(chapters_data):
            chapter = Chapter.objects.create(
                book=book,
                chapter_number=i + 1,
                title=chapter_data.get("title", f"Chapter {i + 1}"),
                original_text=chapter_data["text"],
                processing_status="created",
            )
            chapters.append(chapter)

        book.total_chapters = len(chapters)
        book.processing_progress = 60
        book.status = "translating"
        book.save()

        # Step 4: Process each chapter
        for i, chapter in enumerate(chapters):
            process_chapter_async.delay(chapter.id)
            # Update progress
            progress = 60 + (30 * (i + 1) / len(chapters))
            book.processing_progress = int(progress)
            book.save()

        book.status = "translated"
        book.processing_progress = 100
        book.processing_completed_at = timezone.now()
        book.save()

        logger.info(f"Successfully processed book {book.id}")

    except Exception as e:
        logger.error(f"Error processing book {book_id}: {str(e)}")
        book = Book.objects.get(id=book_id)
        book.status = "error"
        book.error_message = str(e)
        book.save()


@shared_task
def process_chapter_async(chapter_id):
    """Process individual chapter - generate abstract and translations"""
    try:
        chapter = Chapter.objects.get(id=chapter_id)
        chapter.processing_status = "processing"
        chapter.save()

        llm_service = LLMTranslationService()

        # Generate abstract for context
        abstract = llm_service.generate_chapter_abstract(chapter.original_text)
        chapter.abstract = abstract
        chapter.processing_status = "abstract_complete"
        chapter.save()

        # Generate key terms
        key_terms = llm_service.extract_key_terms(chapter.original_text)
        chapter.key_terms = key_terms
        chapter.processing_status = "analyzed"
        chapter.save()

        # This will be extended when we add the translations app
        # For now, just mark as complete
        chapter.processing_status = "complete"
        chapter.save()

        logger.info(f"Successfully processed chapter {chapter.id}")

    except Exception as e:
        logger.error(f"Error processing chapter {chapter_id}: {str(e)}")
        chapter = Chapter.objects.get(id=chapter_id)
        chapter.processing_status = "error"
        chapter.save()


@shared_task
def generate_chapter_abstract_async(chapter_id):
    """Regenerate abstract for a specific chapter"""
    try:
        chapter = Chapter.objects.get(id=chapter_id)
        llm_service = LLMTranslationService()

        abstract = llm_service.generate_chapter_abstract(chapter.original_text)
        chapter.abstract = abstract
        chapter.save()

        logger.info(f"Regenerated abstract for chapter {chapter.id}")

    except Exception as e:
        logger.error(f"Error regenerating abstract for chapter {chapter_id}: {str(e)}")
