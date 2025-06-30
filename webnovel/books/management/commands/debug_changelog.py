from django.core.management.base import BaseCommand
from django.contrib.contenttypes.models import ContentType
from books.models import Chapter, ChangeLog


class Command(BaseCommand):
    help = 'Debug changelog entries for a specific chapter'

    def add_arguments(self, parser):
        parser.add_argument('chapter_id', type=int, help='Chapter ID to debug')

    def handle(self, *args, **options):
        chapter_id = options['chapter_id']
        
        try:
            chapter = Chapter.objects.get(id=chapter_id)
            content_type = ContentType.objects.get_for_model(Chapter)
            
            self.stdout.write(f"Debugging changelog for Chapter {chapter_id}: {chapter.title}")
            self.stdout.write(f"Content Type ID: {content_type.id}")
            self.stdout.write(f"Is Translation: {chapter.original_chapter is not None}")
            if chapter.original_chapter:
                self.stdout.write(f"Original Chapter ID: {chapter.original_chapter.id}")
            
            # Check all changelog entries
            all_entries = ChangeLog.objects.filter(content_type=content_type)
            self.stdout.write(f"\nTotal changelog entries for Chapter model: {all_entries.count()}")
            
            # Check entries where this chapter is the original
            original_entries = ChangeLog.objects.filter(
                content_type=content_type,
                original_object_id=chapter_id
            )
            self.stdout.write(f"Entries where chapter {chapter_id} is original: {original_entries.count()}")
            for entry in original_entries:
                self.stdout.write(f"  - ID: {entry.id}, Type: {entry.change_type}, Status: {entry.status}, Notes: {entry.notes[:50]}...")
            
            # Check entries where this chapter is the changed object
            changed_entries = ChangeLog.objects.filter(
                content_type=content_type,
                changed_object_id=chapter_id
            )
            self.stdout.write(f"Entries where chapter {chapter_id} is changed: {changed_entries.count()}")
            for entry in changed_entries:
                self.stdout.write(f"  - ID: {entry.id}, Type: {entry.change_type}, Status: {entry.status}, Notes: {entry.notes[:50]}...")
            
            # If it's a translation, check entries for the original chapter
            if chapter.original_chapter:
                orig_entries = ChangeLog.objects.filter(
                    content_type=content_type,
                    original_object_id=chapter.original_chapter.id,
                    changed_object_id=chapter_id
                )
                self.stdout.write(f"Entries for translation {chapter_id} of original {chapter.original_chapter.id}: {orig_entries.count()}")
                for entry in orig_entries:
                    self.stdout.write(f"  - ID: {entry.id}, Type: {entry.change_type}, Status: {entry.status}, Notes: {entry.notes[:50]}...")
            
        except Chapter.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Chapter {chapter_id} does not exist"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {str(e)}")) 