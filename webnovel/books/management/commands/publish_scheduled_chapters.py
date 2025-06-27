from django.core.management.base import BaseCommand
from django.utils import timezone
from books.models import Chapter


class Command(BaseCommand):
    help = "Publish chapters that are scheduled for publication"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be published without actually publishing",
        )
        parser.add_argument(
            "--book-id",
            type=int,
            help="Only process chapters for a specific book",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        book_id = options["book_id"]

        # Get scheduled chapters that are ready to be published
        queryset = Chapter.objects.filter(
            status="scheduled", active_at__lte=timezone.now()
        )

        if book_id:
            queryset = queryset.filter(book_id=book_id)

        scheduled_chapters = list(queryset)

        if not scheduled_chapters:
            self.stdout.write(
                self.style.SUCCESS(
                    "No chapters scheduled for publication at this time."
                )
            )
            return

        self.stdout.write(
            f"Found {len(scheduled_chapters)} chapter(s) ready for publication:"
        )

        for chapter in scheduled_chapters:
            self.stdout.write(
                f"  - {chapter.book.title} - Chapter {chapter.chapter_number}: {chapter.title}"
            )

        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN: No chapters were actually published.")
            )
            return

        # Publish the chapters
        published_count = 0
        for chapter in scheduled_chapters:
            try:
                chapter.publish_now()
                published_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ Published: {chapter.book.title} - Chapter {chapter.chapter_number}: {chapter.title}"
                    )
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"✗ Failed to publish {chapter.title}: {str(e)}")
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully published {published_count} out of {len(scheduled_chapters)} chapters."
            )
        )
