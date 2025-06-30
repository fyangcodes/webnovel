from django.core.management.base import BaseCommand
from django.contrib.contenttypes.models import ContentType
from books.models import Chapter, ChangeLog


class Command(BaseCommand):
    help = 'Test the version field functionality for changelog entries'

    def add_arguments(self, parser):
        parser.add_argument('chapter_id', type=int, help='Chapter ID to test')

    def handle(self, *args, **options):
        chapter_id = options['chapter_id']
        
        try:
            chapter = Chapter.objects.get(id=chapter_id)
            content_type = ContentType.objects.get_for_model(Chapter)
            
            self.stdout.write(f"Testing version field for Chapter {chapter_id}: {chapter.title}")
            
            # Get all changelog entries for this chapter
            entries = ChangeLog.objects.filter(
                content_type=content_type,
                changed_object_id=chapter_id
            ).order_by('version')
            
            if entries.exists():
                self.stdout.write(f"Found {entries.count()} changelog entries:")
                for entry in entries:
                    self.stdout.write(f"  - Version {entry.version}: {entry.change_type} ({entry.status}) - {entry.created_at}")
                
                # Test creating a new entry
                self.stdout.write("\nTesting creation of new changelog entry...")
                new_entry = ChangeLog.objects.create(
                    content_type=content_type,
                    original_object_id=chapter_id,
                    changed_object_id=chapter_id,
                    change_type="edit",
                    status="completed",
                    notes="Test entry for version field"
                )
                self.stdout.write(f"Created new entry with version: {new_entry.version}")
                
                # Show updated list
                updated_entries = ChangeLog.objects.filter(
                    content_type=content_type,
                    changed_object_id=chapter_id
                ).order_by('version')
                
                self.stdout.write(f"\nUpdated list ({updated_entries.count()} entries):")
                for entry in updated_entries:
                    self.stdout.write(f"  - Version {entry.version}: {entry.change_type} ({entry.status}) - {entry.created_at}")
                
            else:
                self.stdout.write("No changelog entries found for this chapter.")
                
                # Create a test entry
                self.stdout.write("Creating test entry...")
                test_entry = ChangeLog.objects.create(
                    content_type=content_type,
                    original_object_id=chapter_id,
                    changed_object_id=chapter_id,
                    change_type="edit",
                    status="completed",
                    notes="Initial test entry"
                )
                self.stdout.write(f"Created test entry with version: {test_entry.version}")
            
        except Chapter.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Chapter {chapter_id} does not exist"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {str(e)}")) 