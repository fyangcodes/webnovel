from celery import shared_task
from django.utils import timezone
from .models import Book, Chapter, BookFile, Language
from .utils import extract_text_from_file
from llm_integration.services import LLMTranslationService
import logging
from django.utils.text import slugify

logger = logging.getLogger(__name__)


@shared_task
def process_bookfile_async(bookfile_id, user_id=None):
    book_file = BookFile.objects.get(id=bookfile_id)
    book = book_file.book

    # Get user if provided
    user = None
    if user_id:
        from django.contrib.auth import get_user_model

        try:
            user = get_user_model().objects.get(id=user_id)
        except:
            pass

    # 1. Extract text
    text = extract_text_from_file(book_file.file)
    # 2. Chunk into chapters (using your LLM or logic)
    llm_service = LLMTranslationService()
    chapters_data = llm_service.divide_into_chapters(text, book=book, user=user)
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
def translate_chapter_async(chapter_id, target_language_code):
    """
    Hybrid approach: Single task that handles the entire translation process
    Reduces database queries and simplifies error handling
    """
    try:
        # Get objects once with optimized queries
        chapter = Chapter.objects.select_related(
            "original_chapter", "book", "language"
        ).get(id=chapter_id)
        target_language = Language.objects.get(code=target_language_code)

        # Validate original chapter exists
        original_chapter = chapter.original_chapter
        if not original_chapter:
            raise ValueError("No original chapter found for translation")

        # Update chapter status to indicate translation is in progress
        chapter.status = "translating"
        chapter.save()

        logger.info(
            f"Starting translation for chapter {chapter_id} to {target_language_code}"
        )

        # Initialize LLM service once
        llm_service = LLMTranslationService()

        # Step 1: Translate title
        logger.info(f"Translating title for chapter {chapter_id}")
        translated_title = llm_service.translate_text(
            original_chapter.title, target_language_code
        )
        chapter.title = translated_title

        # Step 2: Translate content
        logger.info(f"Translating content for chapter {chapter_id}")
        translated_content = llm_service.translate_chapter(
            original_chapter.content, target_language_code
        )
        chapter.content = translated_content

        # Step 3: Translate abstract (if it exists)
        logger.info(f"Translating metadata for chapter {chapter_id}")
        translated_abstract = ""
        if original_chapter.abstract:
            translated_abstract = llm_service.translate_text(
                original_chapter.abstract, target_language_code
            )
        chapter.abstract = translated_abstract

        # Step 4: Extract key terms from translated content
        translated_key_terms = llm_service.extract_key_terms(
            chapter.content, target_language_code
        )
        chapter.key_terms = translated_key_terms

        # Step 5: Set language and generate slug
        chapter.language = target_language

        # Generate proper slug from translated title
        base_slug = slugify(translated_title, allow_unicode=True)
        # Ensure uniqueness
        counter = 1
        final_slug = base_slug
        while Chapter.objects.filter(slug=final_slug).exclude(pk=chapter.pk).exists():
            final_slug = f"{base_slug}-{counter}"
            counter += 1
        chapter.slug = final_slug

        # Step 6: Set final status and save
        chapter.status = "draft"  # Set back to draft for review
        chapter.save()

        logger.info(
            f"Successfully completed translation for chapter {chapter_id} to {target_language_code}"
        )

        return {
            "success": True,
            "chapter_id": chapter_id,
            "target_language": target_language_code,
            "message": f"Chapter '{translated_title}' translated successfully to {target_language.name}",
            "translated_title": translated_title,
            "content_length": len(translated_content),
            "abstract_length": len(translated_abstract),
            "key_terms_count": len(translated_key_terms),
            "final_slug": final_slug,
        }

    except Exception as e:
        logger.error(f"Error in translation for chapter {chapter_id}: {str(e)}")

        # Update chapter status to indicate error
        try:
            chapter = Chapter.objects.get(id=chapter_id)
            chapter.status = "error"
            chapter.save()
        except:
            pass

        return {
            "success": False,
            "chapter_id": chapter_id,
            "error": str(e),
            "message": f"Translation failed: {str(e)}",
        }


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
