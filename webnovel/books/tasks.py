from celery import shared_task
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from .models import Chapter, BookFile, Language, ChangeLog
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

    try:
        # Update status to processing
        book_file.status = "processing"
        book_file.processing_started_at = timezone.now()
        book_file.save()

        # 1. Extract text
        logger.info(f"Extracting text from book file {bookfile_id}")
        text = extract_text_from_file(book_file.file)
        
        # 2. Chunk into chapters (using your LLM or logic)
        logger.info(f"Dividing text into chapters for book {book.id}")
        llm_service = LLMTranslationService()
        chapters_data = llm_service.divide_into_chapters(text, book=book, user=user)
        
        # 3. Create Chapter objects with proper content handling
        logger.info(f"Creating {len(chapters_data)} chapters for book {book.id}")
        for chapter_data in chapters_data:
            title = chapter_data.get("title", "Chapter")
            content_text = chapter_data["text"]
            
            # Create chapter without content first
            chapter = Chapter.objects.create(
                book=book,
                title=title,
                status="draft",
                language=book.language,
            )
            
            # Save raw content to S3
            logger.info(f"Saving raw content to S3 for chapter {chapter.id}")
            chapter.save_raw_content(
                content_text, 
                user=user,
                summary="Initial content from book file upload"
            )
            
            # Generate structured content from raw content
            logger.info(f"Generating structured content for chapter {chapter.id}")
            # Parse the raw content into structured format
            structured_content = []
            if chapter.paragraph_style == "single_newline":
                paragraphs = content_text.split("\n")
                for paragraph in paragraphs:
                    if paragraph.strip():
                        structured_content.append({"type": "text", "content": paragraph.strip()})
            elif chapter.paragraph_style == "double_newline":
                paragraphs = content_text.split("\n\n")
                for paragraph in paragraphs:
                    if paragraph.strip():
                        structured_content.append({"type": "text", "content": paragraph.strip()})
            else:  # auto_detect
                # Count single vs double newlines
                single_count = content_text.count("\n")
                double_count = content_text.count("\n\n")
                if double_count > single_count / 4:  # Threshold for detection
                    paragraphs = content_text.split("\n\n")
                    for paragraph in paragraphs:
                        if paragraph.strip():
                            structured_content.append({"type": "text", "content": paragraph.strip()})
                else:
                    paragraphs = content_text.split("\n")
                    for paragraph in paragraphs:
                        if paragraph.strip():
                            structured_content.append({"type": "text", "content": paragraph.strip()})
            
            chapter.save_structured_content(
                structured_content,
                user=user,
                summary="Initial structured content from book file upload"
            )
            
            # Generate excerpt from raw content (first 200 characters or so)
            logger.info(f"Generating excerpt for chapter {chapter.id}")
            try:
                chapter.excerpt = chapter.generate_excerpt(200)
            except Exception as e:
                logger.warning(f"Failed to generate excerpt for chapter {chapter.id}: {str(e)}")
                # Fallback: simple truncation
                chapter.excerpt = content_text[:200] + "..." if len(content_text) > 200 else content_text
            
            # Generate abstract and key terms
            logger.info(f"Generating abstract and key terms for chapter {chapter.id}")
            try:
                abstract = llm_service.generate_chapter_abstract(
                    content_text,
                    source_chapter=chapter,
                    user=user
                )
                key_terms = llm_service.extract_key_terms(
                    content_text,
                    source_chapter=chapter,
                    user=user
                )
                chapter.abstract = abstract
                chapter.key_terms = key_terms
            except Exception as e:
                logger.warning(f"Failed to generate abstract/key terms for chapter {chapter.id}: {str(e)}")
            
            # Update word and character counts
            chapter.update_content_statistics()
            
            # Save all updates
            chapter.save()
            
            logger.info(f"Successfully created chapter {chapter.id}: {title}")
        
        # Update book metadata
        logger.info(f"Updating book metadata for book {book.id}")
        book.update_metadata()
        
        # Mark book file as completed
        book_file.status = "completed"
        book_file.processing_completed_at = timezone.now()
        book_file.processing_progress = 100
        book_file.save()
        
        logger.info(f"Successfully processed book file {bookfile_id} - created {len(chapters_data)} chapters")
        
    except Exception as e:
        logger.error(f"Error processing book file {bookfile_id}: {str(e)}")
        
        # Mark book file as failed
        book_file.status = "failed"
        book_file.error_message = str(e)
        book_file.processing_completed_at = timezone.now()
        book_file.save()
        
        raise


@shared_task
def translate_chapter_async(chapter_id, target_language_code):
    """
    Asynchronously translate a chapter to a target language using LLM service.
    """
    try:
        from django.contrib.auth import get_user_model
        from llm_integration.services import LLMTranslationService

        # Get the chapter and target language
        chapter = Chapter.objects.get(id=chapter_id)
        target_language = Language.objects.get(code=target_language_code)
        original_chapter = chapter.original_chapter or chapter

        # Initialize LLM service
        llm_service = LLMTranslationService()

        # Update status to translating
        chapter.status = "translating"
        chapter.save()

        # Create changelog entry to track translation progress
        try:
            content_type = ContentType.objects.get_for_model(Chapter)
            ChangeLog.objects.create(
                content_type=content_type,
                original_object_id=original_chapter.id,
                changed_object_id=chapter.id,
                user=None,  # System-initiated translation
                change_type="translation",
                status="in_progress",
                notes=f"AI translation started from {original_chapter.get_effective_language().name if original_chapter.get_effective_language() else 'Unknown'} to {target_language.name}",
            )
        except Exception as e:
            logger.warning(f"Failed to create changelog entry for chapter {chapter_id}: {str(e)}")

        # Step 1: Translate title
        logger.info(f"Translating title for chapter {chapter_id}")
        original_title = original_chapter.title
        translated_title = llm_service.translate_text(
            original_title, target_language_code
        )
        chapter.title = translated_title

        # Step 2: Translate content
        logger.info(f"Translating content for chapter {chapter_id}")
        original_raw_content = original_chapter.get_raw_content()  # Use raw content from S3
        translated_content = llm_service.translate_chapter(
            original_raw_content, target_language_code
        )
        
        # Save translated content to S3
        chapter.save_raw_content(
            translated_content, 
            summary=f"AI translation from {original_chapter.get_effective_language().name if original_chapter.get_effective_language() else 'Unknown'} to {target_language.name}"
        )

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
            translated_content, target_language_code
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

        # Update changelog to mark translation as completed
        try:
            content_type = ContentType.objects.get_for_model(Chapter)
            changelog_entry = ChangeLog.objects.filter(
                content_type=content_type,
                original_object_id=original_chapter.id,
                changed_object_id=chapter.id,
                change_type="translation",
                status="in_progress"
            ).first()
            
            if changelog_entry:
                changelog_entry.status = "completed"
                changelog_entry.notes = f"AI translation completed successfully from {original_chapter.get_effective_language().name if original_chapter.get_effective_language() else 'Unknown'} to {target_language.name}. Translated title: '{translated_title}'"
                changelog_entry.save()
        except Exception as e:
            logger.warning(f"Failed to update changelog for chapter {chapter_id}: {str(e)}")

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
            
            # Update changelog to mark translation as failed
            try:
                content_type = ContentType.objects.get_for_model(Chapter)
                changelog_entry = ChangeLog.objects.filter(
                    content_type=content_type,
                    changed_object_id=chapter_id,
                    change_type="translation",
                    status="in_progress"
                ).first()
                
                if changelog_entry:
                    changelog_entry.status = "failed"
                    changelog_entry.notes = f"AI translation failed: {str(e)}"
                    changelog_entry.save()
            except Exception as changelog_error:
                logger.warning(f"Failed to update changelog for failed translation {chapter_id}: {str(changelog_error)}")
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
def sync_media_with_content_async(chapter_id, user_id=None):
    """
    Asynchronously sync media with structured content for a chapter.
    This task adds any missing media items to the structured content JSON.
    """
    try:
        from django.contrib.auth import get_user_model
        
        # Get the chapter
        chapter = Chapter.objects.get(id=chapter_id)
        
        # Get user if provided
        user = None
        if user_id:
            try:
                user = get_user_model().objects.get(id=user_id)
            except:
                pass
        
        logger.info(f"Starting media sync for chapter {chapter_id}")
        
        # Perform the sync operation
        added_count = chapter.sync_media_with_content()
        
        logger.info(f"Completed media sync for chapter {chapter_id}. Added {added_count} media items.")
        
        return {
            "success": True,
            "chapter_id": chapter_id,
            "added_count": added_count,
            "message": f"Successfully synced {added_count} media items with structured content"
        }
        
    except Exception as e:
        logger.error(f"Error syncing media for chapter {chapter_id}: {str(e)}")
        return {
            "success": False,
            "chapter_id": chapter_id,
            "error": str(e),
            "message": f"Media sync failed: {str(e)}"
        }


@shared_task
def rebuild_structured_content_from_media_async(chapter_id, user_id=None):
    """
    Asynchronously rebuild structured content from media for a chapter.
    This task completely rebuilds the structured content JSON from the database media.
    """
    try:
        from django.contrib.auth import get_user_model
        
        # Get the chapter
        chapter = Chapter.objects.get(id=chapter_id)
        
        # Get user if provided
        user = None
        if user_id:
            try:
                user = get_user_model().objects.get(id=user_id)
            except:
                pass
        
        logger.info(f"Starting structured content rebuild for chapter {chapter_id}")
        
        # Get media count for logging
        media_count = chapter.media.count()
        
        # Perform the rebuild operation
        result_count = chapter.rebuild_structured_content_from_media()
        
        logger.info(f"Completed structured content rebuild for chapter {chapter_id}. Result has {result_count} elements.")
        
        return {
            "success": True,
            "chapter_id": chapter_id,
            "media_count": media_count,
            "result_count": result_count,
            "message": f"Successfully rebuilt structured content with {result_count} elements from {media_count} media items"
        }
        
    except Exception as e:
        logger.error(f"Error rebuilding structured content for chapter {chapter_id}: {str(e)}")
        return {
            "success": False,
            "chapter_id": chapter_id,
            "error": str(e),
            "message": f"Structured content rebuild failed: {str(e)}"
        }


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
