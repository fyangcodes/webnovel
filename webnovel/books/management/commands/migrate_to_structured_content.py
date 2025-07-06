from django.core.management.base import BaseCommand
from books.models import Chapter


class Command(BaseCommand):
    help = 'Migrate existing chapter content to file-based structured format'

    def add_arguments(self, parser):
        parser.add_argument(
            '--book-id',
            type=int,
            help='Migrate only chapters from a specific book'
        )
        parser.add_argument(
            '--chapter-id',
            type=int,
            help='Migrate only a specific chapter'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be migrated without actually doing it'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force migration even if content file already exists'
        )

    def handle(self, *args, **options):
        book_id = options.get('book_id')
        chapter_id = options.get('chapter_id')
        dry_run = options.get('dry_run')
        force = options.get('force')

        # Get chapters to migrate
        if chapter_id:
            chapters = Chapter.objects.filter(id=chapter_id)
        elif book_id:
            chapters = Chapter.objects.filter(book_id=book_id)
        else:
            chapters = Chapter.objects.all()

        total_chapters = chapters.count()
        migrated_count = 0
        skipped_count = 0
        error_count = 0

        self.stdout.write(f"Found {total_chapters} chapters to process...")

        for chapter in chapters:
            try:
                # Check if content file already exists
                if chapter.content_file_path and not force:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Skipping Chapter {chapter.id} ({chapter.title}): "
                            f"Content file already exists at {chapter.content_file_path}"
                        )
                    )
                    skipped_count += 1
                    continue

                # Get structured content
                structured_content = chapter.get_structured_content()
                
                if dry_run:
                    self.stdout.write(
                        f"Would migrate Chapter {chapter.id} ({chapter.title}): "
                        f"{len(structured_content)} elements"
                    )
                    for i, element in enumerate(structured_content):
                        if element['type'] == 'paragraph':
                            preview = element['content'][:50] + "..." if len(element['content']) > 50 else element['content']
                            self.stdout.write(f"  [{i}] Paragraph: {preview}")
                        else:
                            self.stdout.write(f"  [{i}] {element['type']}: {element}")
                else:
                    # Save structured content to file
                    chapter.save_structured_content(structured_content)
                    
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Migrated Chapter {chapter.id} ({chapter.title}): "
                            f"{len(structured_content)} elements -> {chapter.content_file_path}"
                        )
                    )
                    migrated_count += 1

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"Error migrating Chapter {chapter.id} ({chapter.title}): {str(e)}"
                    )
                )
                error_count += 1

        # Summary
        self.stdout.write("\n" + "="*50)
        self.stdout.write("MIGRATION SUMMARY")
        self.stdout.write("="*50)
        self.stdout.write(f"Total chapters: {total_chapters}")
        self.stdout.write(f"Migrated: {migrated_count}")
        self.stdout.write(f"Skipped: {skipped_count}")
        self.stdout.write(f"Errors: {error_count}")
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "\nThis was a dry run. No files were actually created. "
                    "Run without --dry-run to perform the actual migration."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nSuccessfully migrated {migrated_count} chapters to file-based storage!"
                )
            ) 