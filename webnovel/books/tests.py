from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from .models import Book, Chapter, Language

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
            content='This is the original content in English.',
            language=self.english,
            chapter_number=1
        )
        
        # Create translated chapter
        self.translated_chapter = Chapter.objects.create(
            book=self.book,
            title='Translated Chapter',
            content='This is the translated content in Spanish.',
            language=self.spanish,
            chapter_number=1,
            original_chapter=self.original_chapter
        )
        
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
            content='This is the German content.',
            language=self.german,
            chapter_number=1,
            original_chapter=self.original_chapter
        )
        
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
            content='This is the French content.',
            language=self.french,
            chapter_number=1,
            original_chapter=self.original_chapter
        )
        
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
