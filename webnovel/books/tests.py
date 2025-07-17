import os
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.storage import default_storage
from .models import (
    Book, Chapter, Language, Author, ChapterMedia, BookFile,
    generate_unique_filename
)

User = get_user_model()


class TranslationPanelLogicTest(TestCase):
    def setUp(self):
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create test languages
        self.english = Language.objects.create(
            code='en',
            name='English',
            local_name='English'
        )
        self.spanish = Language.objects.create(
            code='es',
            name='Spanish',
            local_name='Español'
        )
        self.french = Language.objects.create(
            code='fr',
            name='French',
            local_name='Français'
        )
        self.german = Language.objects.create(
            code='de',
            name='German',
            local_name='Deutsch'
        )
        
        # Create test book
        self.book = Book.objects.create(
            title='Test Book',
            language=self.english,
            owner=self.user
        )
        
        # Create original chapter
        self.original_chapter = Chapter.objects.create(
            book=self.book,
            title='Original Chapter',
            language=self.english,
            chapter_number=1
        )
        self.original_chapter.save_raw_content('This is the original content in English.')
        
        # Create translated chapter
        self.translated_chapter = Chapter.objects.create(
            book=self.book,
            title='Translated Chapter',
            language=self.spanish,
            chapter_number=1,
            original_chapter=self.original_chapter
        )
        self.translated_chapter.save_raw_content('This is the translated content in Spanish.')
        
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')

    def test_original_chapter_translation_options(self):
        """Test that original chapter excludes its own language and existing translations"""
        url = reverse('books:chapter_detail', kwargs={'pk': self.original_chapter.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        
        # Get available translation languages from context
        available_languages = response.context['available_translation_languages']
        available_language_ids = [lang.id for lang in available_languages]
        
        # Should exclude English (original language) and Spanish (existing translation)
        self.assertNotIn(self.english.id, available_language_ids)
        self.assertNotIn(self.spanish.id, available_language_ids)
        
        # Should include French and German
        self.assertIn(self.french.id, available_language_ids)
        self.assertIn(self.german.id, available_language_ids)

    def test_translated_chapter_translation_options(self):
        """Test that translated chapter excludes original language and ALL existing translations"""
        # Create another translation (German) of the original chapter
        german_chapter = Chapter.objects.create(
            book=self.book,
            title='German Chapter',
            language=self.german,
            chapter_number=1,
            original_chapter=self.original_chapter
        )
        german_chapter.save_raw_content('This is the German content.')
        
        # Now when viewing the Spanish translation, it should exclude:
        # - Spanish (own language)
        # - English (original language)
        # - German (existing translation)
        url = reverse('books:chapter_detail', kwargs={'pk': self.translated_chapter.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        
        # Get available translation languages from context
        available_languages = response.context['available_translation_languages']
        available_language_ids = [lang.id for lang in available_languages]
        
        # Should exclude Spanish (own language), English (original), and German (existing translation)
        self.assertNotIn(self.spanish.id, available_language_ids)
        self.assertNotIn(self.english.id, available_language_ids)
        self.assertNotIn(self.german.id, available_language_ids)
        
        # Should only include French
        self.assertIn(self.french.id, available_language_ids)
        
        # Test the same logic when viewing the German translation
        url = reverse('books:chapter_detail', kwargs={'pk': german_chapter.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        
        available_languages = response.context['available_translation_languages']
        available_language_ids = [lang.id for lang in available_languages]
        
        # Should exclude German (own language), English (original), and Spanish (existing translation)
        self.assertNotIn(self.german.id, available_language_ids)
        self.assertNotIn(self.english.id, available_language_ids)
        self.assertNotIn(self.spanish.id, available_language_ids)
        
        # Should only include French
        self.assertIn(self.french.id, available_language_ids)

    def test_chapter_with_multiple_translations(self):
        """Test that chapter with multiple translations excludes all relevant languages"""
        # Create another translation
        french_chapter = Chapter.objects.create(
            book=self.book,
            title='French Chapter',
            language=self.french,
            chapter_number=1,
            original_chapter=self.original_chapter
        )
        french_chapter.save_raw_content('This is the French content.')
        
        url = reverse('books:chapter_detail', kwargs={'pk': self.original_chapter.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        
        # Get available translation languages from context
        available_languages = response.context['available_translation_languages']
        available_language_ids = [lang.id for lang in available_languages]
        
        # Should exclude English (original), Spanish (translation), and French (translation)
        self.assertNotIn(self.english.id, available_language_ids)
        self.assertNotIn(self.spanish.id, available_language_ids)
        self.assertNotIn(self.french.id, available_language_ids)
        
        # Should only include German
        self.assertIn(self.german.id, available_language_ids)


class FileHandlingTestCase(TestCase):
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser2',
            email='test2@example.com',
            password='testpass123'
        )
        
        self.language = Language.objects.create(
            code='en',
            name='English',
            local_name='English'
        )
        
        self.author = Author.objects.create(
            canonical_name='Test Author',
            localized_name='Test Author',
            language=self.language
        )
        
        self.book = Book.objects.create(
            title='Test Book',
            language=self.language,
            author=self.author,
            owner=self.user
        )
        
        self.chapter = Chapter.objects.create(
            book=self.book,
            title='Test Chapter'
        )
        self.chapter.save_raw_content('Test content')

    def create_test_file(self, filename, content=b'test content'):
        """Create a test file"""
        return SimpleUploadedFile(filename, content)

    def test_generate_unique_filename(self):
        """Test unique filename generation"""
        base_path = "test/path"
        filename = "test.jpg"
        
        # First call should return timestamped filename
        unique_path1 = generate_unique_filename(base_path, filename)
        self.assertIn("test_", unique_path1)
        self.assertIn(".jpg", unique_path1)
        self.assertTrue(unique_path1.startswith(f"{base_path}/"))
        
        # Create a file with the first path to force counter increment
        default_storage.save(unique_path1, SimpleUploadedFile("test.jpg", b"content"))
        
        # Second call should return different path (with counter)
        unique_path2 = generate_unique_filename(base_path, filename)
        # They should be different due to counter
        self.assertNotEqual(unique_path1, unique_path2)
        
        # Both should follow the expected pattern
        self.assertIn("test_", unique_path2)
        self.assertIn(".jpg", unique_path2)

    def test_chapter_media_upload(self):
        """Test chapter media upload with unique filenames"""
        # Create first media file
        file1 = self.create_test_file("image1.jpg")
        media1 = ChapterMedia.objects.create(
            chapter=self.chapter,
            file=file1,
            media_type="image",
            title="Test Image 1",
            position=1
        )
        
        # Create second media file with same name
        file2 = self.create_test_file("image1.jpg")
        media2 = ChapterMedia.objects.create(
            chapter=self.chapter,
            file=file2,
            media_type="image",
            title="Test Image 2",
            position=2
        )
        
        # Verify files have different paths
        self.assertNotEqual(media1.file.name, media2.file.name)
        self.assertIn("image1_", media1.file.name)
        self.assertIn("image1_", media2.file.name)
        
        # Verify files exist on storage
        self.assertTrue(default_storage.exists(media1.file.name))
        self.assertTrue(default_storage.exists(media2.file.name))

    def test_book_file_upload(self):
        """Test book file upload with unique filenames"""
        # Create first book file
        file1 = self.create_test_file("manuscript.pdf")
        book_file1 = BookFile.objects.create(
            book=self.book,
            file=file1,
            description="Test manuscript 1"
        )
        
        # Create second book file with same name
        file2 = self.create_test_file("manuscript.pdf")
        book_file2 = BookFile.objects.create(
            book=self.book,
            file=file2,
            description="Test manuscript 2"
        )
        
        # Verify files have different paths
        self.assertNotEqual(book_file1.file.name, book_file2.file.name)
        self.assertIn("manuscript_", book_file1.file.name)
        self.assertIn("manuscript_", book_file2.file.name)

    def test_book_cover_upload(self):
        """Test book cover upload with unique filenames"""
        # Create first cover
        cover1 = self.create_test_file("cover.jpg")
        self.book.cover_image = cover1
        self.book.save()
        
        # Create second cover with same name
        cover2 = self.create_test_file("cover.jpg")
        self.book.cover_image = cover2
        self.book.save()
        
        # Verify cover has unique path
        self.assertIn("cover_", self.book.cover_image.name)

    def test_media_file_operations(self):
        """Test media file operations"""
        # Create media file
        file1 = self.create_test_file("test.jpg")
        media = ChapterMedia.objects.create(
            chapter=self.chapter,
            file=file1,
            media_type="image",
            title="Test Image",
            position=1
        )
        
        # Test get_original_filename
        original_name = media.get_original_filename()
        self.assertEqual(original_name, "test.jpg")
        
        # Test update_file
        file2 = self.create_test_file("new_test.jpg")
        old_path = media.file.name
        media.update_file(file2, delete_old=True)
        
        # Verify old file is deleted and new file exists
        self.assertFalse(default_storage.exists(old_path))
        self.assertTrue(default_storage.exists(media.file.name))
        
        # Test delete_file_from_storage
        current_path = media.file.name
        media.delete_file_from_storage()
        self.assertFalse(default_storage.exists(current_path))

    def test_book_file_operations(self):
        """Test book file operations"""
        # Create book file
        file1 = self.create_test_file("test.pdf")
        book_file = BookFile.objects.create(
            book=self.book,
            file=file1,
            description="Test file"
        )
        
        # Test get_original_filename
        original_name = book_file.get_original_filename()
        self.assertEqual(original_name, "test.pdf")
        
        # Test update_file
        file2 = self.create_test_file("new_test.pdf")
        old_path = book_file.file.name
        book_file.update_file(file2, delete_old=True)
        
        # Verify old file is deleted and new file exists
        self.assertFalse(default_storage.exists(old_path))
        self.assertTrue(default_storage.exists(book_file.file.name))

    def test_book_cover_operations(self):
        """Test book cover operations"""
        # Create cover
        cover1 = self.create_test_file("cover.jpg")
        self.book.cover_image = cover1
        self.book.save()
        
        # Test update_cover_image
        cover2 = self.create_test_file("new_cover.jpg")
        old_path = self.book.cover_image.name
        self.book.update_cover_image(cover2, delete_old=True)
        
        # Verify old file is deleted and new file exists
        self.assertFalse(default_storage.exists(old_path))
        self.assertTrue(default_storage.exists(self.book.cover_image.name))
        
        # Test delete_cover_image
        current_path = self.book.cover_image.name
        self.book.delete_cover_image()
        self.assertFalse(default_storage.exists(current_path))
        # Refresh from database to check the field is actually None
        self.book.refresh_from_db()
        # Check if the field is actually None (not just empty)
        self.assertIsNone(self.book.cover_image.name if self.book.cover_image else None)

    def test_cleanup_old_versions(self):
        """Test cleanup of old file versions - placeholder for future implementation"""
        # This test is a placeholder for when cleanup_old_file_versions is implemented
        pass

    def tearDown(self):
        """Clean up test files"""
        # Clean up any test files that might have been created
        test_paths = [
            "test/",
            self.book.get_book_directory(),
        ]
        
        for path in test_paths:
            try:
                if hasattr(default_storage, 'listdir'):
                    directories, files = default_storage.listdir(path)
                    for filename in files:
                        file_path = os.path.join(path, filename)
                        if default_storage.exists(file_path):
                            default_storage.delete(file_path)
            except Exception:
                pass
