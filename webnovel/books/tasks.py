from celery import shared_task
from django.utils import timezone
from .models import Book, Chapter, BookFile
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
        book.save()

        # Step 1: Extract text
        logger.info(f"Extracting text from book {book.id}")
        # Note: This would need to be updated to work with BookFile model
        # For now, we'll skip this step as the Book model doesn't have uploaded_file
        book.estimated_words = 0  # Will be updated when chapters are created
        book.save()

        # Step 2: Divide into chapters
        logger.info(f"Dividing book {book.id} into chapters")
        book.status = "chunking"
        book.save()

        llm_service = LLMTranslationService()
        # This would need actual text content to work
        # For now, we'll create a placeholder chapter
        chapters_data = [{"title": "Chapter 1", "text": "Placeholder content"}]

        book.save()

        # Step 3: Create chapter objects
        chapters = []
        for i, chapter_data in enumerate(chapters_data):
            chapter = Chapter.objects.create(
                book=book,
                chapter_number=i + 1,
                title=chapter_data.get("title", f"Chapter {i + 1}"),
                content=chapter_data["text"],
                status="draft",
            )
            chapters.append(chapter)

        book.total_chapters = len(chapters)
        book.status = "translating"
        book.save()

        # Step 4: Process each chapter
        for i, chapter in enumerate(chapters):
            process_chapter_async.delay(chapter.id)
            # Update progress
            # progress = 60 + (30 * (i + 1) / len(chapters))
            # book.processing_progress = int(progress)
            # book.save()

        book.status = "translated"
        book.save()

        logger.info(f"Successfully processed book {book.id}")

    except Exception as e:
        logger.error(f"Error processing book {book_id}: {str(e)}")
        book = Book.objects.get(id=book_id)
        book.status = "error"
        book.save()


@shared_task
def process_chapter_async(chapter_id):
    """Process individual chapter - generate abstract and key terms only (no translation)"""
    try:
        chapter = Chapter.objects.get(id=chapter_id)
        # Remove processing_status as it's not in the new model
        # chapter.processing_status = "processing"
        chapter.save()

        llm_service = LLMTranslationService()

        # Generate abstract for context (in original language)
        original_lang = (
            chapter.book.language.code
            if chapter.book.language
            else None
        )
        abstract = llm_service.generate_chapter_abstract(
            chapter.content, target_language=original_lang
        )
        chapter.abstract = abstract
        # chapter.processing_status = "abstract_complete"
        chapter.save()

        # Generate key terms (in original language)
        key_terms = llm_service.extract_key_terms(
            chapter.content, target_language=original_lang
        )
        chapter.key_terms = key_terms
        # chapter.processing_status = "analyzed"
        chapter.save()

        logger.info(f"Successfully analyzed chapter {chapter.id}")

    except Exception as e:
        logger.error(f"Error processing chapter {chapter_id}: {str(e)}")
        chapter = Chapter.objects.get(id=chapter_id)
        # chapter.processing_status = "error"
        chapter.save()


@shared_task
def generate_chapter_abstract_async(chapter_id):
    """Regenerate abstract for a specific chapter"""
    try:
        chapter = Chapter.objects.get(id=chapter_id)
        llm_service = LLMTranslationService()

        abstract = llm_service.generate_chapter_abstract(
            chapter.content,
            target_language=(
                chapter.book.language.code
                if chapter.book.language
                else None
            ),
        )
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
        chapters = Chapter.objects.filter(book=book, id__in=chapter_ids).order_by(
            "chapter_number"
        )
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
                    chapter.content, target_language.code
                )
                # Translate key terms (returns a list)
                key_terms = translation_service.extract_key_terms(
                    chapter.content, target_language.code
                )
                # Translate each key term and store as key-value pairs
                key_term_pairs = {}
                for term in key_terms:
                    translated_term = translation_service.translate_text(
                        term, target_language.code
                    )
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


@shared_task
def process_bookfile_async(bookfile_id):
    book_file = BookFile.objects.get(id=bookfile_id)
    book = book_file.book
    # 1. Extract text
    text = extract_text_from_file(book_file.file)
    # 2. Chunk into chapters (using your LLM or logic)
    llm_service = LLMTranslationService()
    chapters_data = llm_service.divide_into_chapters(text)
    # 3. Create Chapter objects
    for chapter_data in chapters_data:
        Chapter.objects.create(
            book=book,
            title=chapter_data.get("title", "Chapter"),
            content=chapter_data["text"],
        )
    # Optionally update book.total_chapters
    book.total_chapters = book.chapters.count()
    book.save()


@shared_task
def publish_scheduled_chapters_async():
    """Automatically publish chapters that are scheduled for publication"""
    try:
        from django.utils import timezone
        
        # Get scheduled chapters that are ready to be published
        scheduled_chapters = Chapter.objects.filter(
            status="scheduled", active_at__lte=timezone.now()
        )
        
        published_count = 0
        for chapter in scheduled_chapters:
            try:
                chapter.publish_now()
                published_count += 1
                logger.info(
                    f"Auto-published chapter: {chapter.book.title} - Chapter {chapter.chapter_number}: {chapter.title}"
                )
            except Exception as e:
                logger.error(f"Failed to auto-publish chapter {chapter.id}: {str(e)}")
        
        if published_count > 0:
            logger.info(f"Successfully auto-published {published_count} chapters")
        
        return published_count
        
    except Exception as e:
        logger.error(f"Error in publish_scheduled_chapters_async: {str(e)}")
        return 0


@shared_task
def schedule_chapter_publishing_async(chapter_id, publish_datetime):
    """Schedule a chapter for publishing at a specific datetime"""
    try:
        chapter = Chapter.objects.get(id=chapter_id)
        chapter.schedule_for_publishing(publish_datetime)
        logger.info(
            f"Scheduled chapter {chapter.id} for publishing at {publish_datetime}"
        )
        return True
    except Exception as e:
        logger.error(f"Error scheduling chapter {chapter_id}: {str(e)}")
        return False


@shared_task
def translate_chapter_async(chapter_id, target_language_code):
    """
    Translate a chapter to the target language using AI
    """
    try:
        chapter = Chapter.objects.get(id=chapter_id)
        target_language = Language.objects.get(code=target_language_code)
        
        # Update chapter status to indicate translation is in progress
        chapter.status = "translating"
        chapter.save()
        
        llm_service = LLMTranslationService()
        
        # Get context from original chapter if available
        context_abstract = ""
        if chapter.original_chapter and chapter.original_chapter.abstract:
            context_abstract = chapter.original_chapter.abstract
        
        # Translate the chapter content
        translated_content = llm_service.translate_chapter(
            chapter.content, 
            target_language_code, 
            context_abstract
        )
        
        # Translate the title
        translated_title = llm_service.translate_text(
            chapter.title, 
            target_language_code
        )
        
        # Generate abstract in target language
        translated_abstract = llm_service.generate_chapter_abstract(
            translated_content, 
            target_language_code
        )
        
        # Extract key terms in target language
        translated_key_terms = llm_service.extract_key_terms(
            translated_content, 
            target_language_code
        )
        
        # Update the chapter with translated content
        chapter.content = translated_content
        chapter.title = translated_title
        chapter.abstract = translated_abstract
        chapter.key_terms = translated_key_terms
        chapter.language = target_language
        chapter.status = "draft"  # Set back to draft for review
        chapter.save()
        
        logger.info(f"Successfully translated chapter {chapter.id} to {target_language_code}")
        
        return {
            'success': True,
            'chapter_id': chapter.id,
            'target_language': target_language_code,
            'message': f'Chapter "{translated_title}" translated successfully to {target_language.name}'
        }
        
    except Exception as e:
        logger.error(f"Error translating chapter {chapter_id}: {str(e)}")
        
        # Update chapter status to indicate error
        try:
            chapter = Chapter.objects.get(id=chapter_id)
            chapter.status = "error"
            chapter.save()
        except:
            pass
        
        return {
            'success': False,
            'chapter_id': chapter_id,
            'error': str(e),
            'message': f'Translation failed: {str(e)}'
        }
