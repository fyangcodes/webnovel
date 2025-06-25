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
    """Process individual chapter - generate abstract and key terms only (no translation)"""
    try:
        chapter = Chapter.objects.get(id=chapter_id)
        chapter.processing_status = "processing"
        chapter.save()

        llm_service = LLMTranslationService()

        # Generate abstract for context (in original language)
        original_lang = chapter.book.original_language.code if chapter.book.original_language else None
        abstract = llm_service.generate_chapter_abstract(chapter.original_text, target_language=original_lang)
        chapter.abstract = abstract
        chapter.processing_status = "abstract_complete"
        chapter.save()

        # Generate key terms (in original language)
        key_terms = llm_service.extract_key_terms(chapter.original_text, target_language=original_lang)
        chapter.key_terms = key_terms
        chapter.processing_status = "analyzed"
        chapter.save()

        logger.info(f"Successfully analyzed chapter {chapter.id}")

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

        abstract = llm_service.generate_chapter_abstract(chapter.original_text, target_language=chapter.book.original_language.code if chapter.book.original_language else None)
        chapter.abstract = abstract
        chapter.save()

        logger.info(f"Regenerated abstract for chapter {chapter.id}")

    except Exception as e:
        logger.error(f"Error regenerating abstract for chapter {chapter_id}: {str(e)}")


@shared_task
def bulk_translate_chapters_async(book_id, target_language_code, chapter_ids, user_id):
    """Bulk translate selected chapters to the target language asynchronously."""
    from books.models import Book, Chapter
    from languages.models import Language
    from translations.models import Translation
    from django.contrib.auth import get_user_model
    import json
    try:
        book = Book.objects.get(id=book_id)
        chapters = Chapter.objects.filter(book=book, id__in=chapter_ids).order_by("chapter_number")
        target_language = Language.objects.get(code=target_language_code)
        user = get_user_model().objects.get(id=user_id)
        translation_service = LLMTranslationService()
        translated_count = 0
        for chapter in chapters:
            exists = Translation.objects.filter(
                chapter=chapter, target_language=target_language
            ).exists()
            if not exists:
                # Translate title
                translated_title = translation_service.translate_text(
                    chapter.title, target_language.code
                )
                # Translate main text
                translated_text = translation_service.translate_chapter(
                    chapter.original_text, target_language.code
                )
                # Translate key terms (returns a list)
                key_terms = translation_service.extract_key_terms(
                    chapter.original_text, target_language.code
                )
                # Translate each key term and store as key-value pairs
                key_term_pairs = {}
                for term in key_terms:
                    translated_term = translation_service.translate_text(term, target_language.code)
                    key_term_pairs[term] = translated_term
                # Store key_term_pairs as JSON string if Translation model has a field for it
                # If not, add a comment for where to store
                Translation.objects.create(
                    chapter=chapter,
                    target_language=target_language,
                    title=translated_title,
                    translated_text=translated_text,
                    created_by=user,
                    # key_terms=json.dumps(key_term_pairs),  # Uncomment if you add this field
                )
                translated_count += 1
        return translated_count
    except Exception as e:
        logger.error(f"Error in bulk_translate_chapters_async: {str(e)}")
        return 0
