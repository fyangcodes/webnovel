from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from books.models import Book, Chapter, Language, ChangeLog
from books.views import ChapterVersionCompareView
from django.test import RequestFactory
from django.contrib.auth.models import User

User = get_user_model()


class Command(BaseCommand):
    help = 'Test the version comparison functionality'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Testing version comparison functionality...'))
        
        # Create test data
        user = User.objects.first()
        if not user:
            self.stdout.write(self.style.ERROR('No user found. Please create a user first.'))
            return
        
        # Get or create test language
        language, created = Language.objects.get_or_create(
            code='en',
            defaults={'name': 'English', 'local_name': 'English'}
        )
        
        # Get or create test book
        book, created = Book.objects.get_or_create(
            title='Test Book for Version Compare',
            defaults={
                'owner': user,
                'language': language,
                'status': 'draft'
            }
        )
        
        # Get or create test chapter
        chapter, created = Chapter.objects.get_or_create(
            book=book,
            chapter_number=1,
            defaults={
                'title': 'Test Chapter',
                'content': 'This is the original content of the test chapter.',
                'language': language,
                'status': 'draft'
            }
        )
        
        self.stdout.write(f'Created test chapter: {chapter.title}')
        
        # Create some changelog entries to simulate version history
        content_type = ContentType.objects.get_for_model(Chapter)
        
        # First edit
        changelog1 = ChangeLog.objects.create(
            content_type=content_type,
            original_object_id=chapter.id,
            changed_object_id=chapter.id,
            user=user,
            change_type="edit",
            status="completed",
            notes="First manual correction - fixed grammar",
            diff="Title Changes:\n\nContent Changes:\n- This is the original content of the test chapter.\n+ This is the corrected content of the test chapter.",
        )
        
        # Update chapter content to reflect the change
        chapter.content = "This is the corrected content of the test chapter."
        chapter.save()
        
        # Second edit
        changelog2 = ChangeLog.objects.create(
            content_type=content_type,
            original_object_id=chapter.id,
            changed_object_id=chapter.id,
            user=user,
            change_type="edit",
            status="completed",
            notes="Second correction - improved clarity",
            diff="Title Changes:\n\nContent Changes:\n- This is the corrected content of the test chapter.\n+ This is the improved and corrected content of the test chapter.",
        )
        
        # Update chapter content again
        chapter.content = "This is the improved and corrected content of the test chapter."
        chapter.save()
        
        self.stdout.write(f'Created {ChangeLog.objects.filter(changed_object_id=chapter.id).count()} changelog entries')
        
        # Test the version comparison view
        factory = RequestFactory()
        request = factory.get(f'/chapters/{chapter.pk}/compare/')
        request.user = user
        
        view = ChapterVersionCompareView()
        view.request = request
        
        # Test getting available versions
        available_versions = view._get_available_versions(chapter)
        self.stdout.write(f'Available versions: {len(available_versions)}')
        
        for version in available_versions:
            self.stdout.write(f'  - {version["title"]} ({version["version_type"]})')
        
        # Test getting version history
        version_history = view._get_version_history(chapter, content_type)
        self.stdout.write(f'Version history entries: {len(version_history)}')
        
        for history in version_history:
            self.stdout.write(f'  - {history["title"]} (v{history["version_number"]}) by {history["user"]}')
        
        self.stdout.write(self.style.SUCCESS('Version comparison test completed successfully!'))
        self.stdout.write(f'You can now test the comparison view at: /chapters/{chapter.pk}/compare/') 