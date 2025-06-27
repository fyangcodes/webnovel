from django.core.management.base import BaseCommand
from django.utils.text import slugify
from books.models import Chapter


class Command(BaseCommand):
    help = 'Fix chapters with invalid or empty slugs'

    def handle(self, *args, **options):
        chapters = Chapter.objects.all()
        fixed_count = 0
        
        for chapter in chapters:
            original_slug = chapter.slug
            
            # Check if slug is empty or invalid
            if not chapter.slug or chapter.slug.strip() == "":
                # Generate slug from title, fallback to chapter number if title is empty
                if chapter.title and chapter.title.strip():
                    chapter.slug = slugify(chapter.title, allow_unicode=True)
                else:
                    # Fallback to chapter number if title is empty
                    chapter.slug = f"chapter-{chapter.chapter_number}"
                
                # Ensure uniqueness per book
                base_slug = chapter.slug
                counter = 1
                while (
                    Chapter.objects.filter(book=chapter.book, slug=chapter.slug)
                    .exclude(pk=chapter.pk)
                    .exists()
                ):
                    chapter.slug = f"{base_slug}-{counter}"
                    counter += 1
                
                chapter.save(update_fields=['slug'])
                fixed_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Fixed chapter "{chapter.title}" (ID: {chapter.pk}): "{original_slug}" -> "{chapter.slug}"'
                    )
                )
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully fixed {fixed_count} chapter slugs')
        ) 