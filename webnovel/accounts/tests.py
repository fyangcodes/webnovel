from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from .models import User, BookCollaborator, TranslationAssignment
from books.models import Book, Chapter, Language

User = get_user_model()


class UserModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            role='writer'
        )
    
    def test_user_creation(self):
        self.assertEqual(self.user.username, 'testuser')
        self.assertEqual(self.user.role, 'writer')
        self.assertEqual(self.user.display_name, 'testuser')
    
    def test_user_with_pen_name(self):
        self.user.pen_name = 'Test Author'
        self.user.save()
        self.assertEqual(self.user.display_name, 'Test Author')
    
    def test_role_properties(self):
        # Test writer role
        self.assertTrue(self.user.is_writer)
        self.assertFalse(self.user.is_translator)
        self.assertFalse(self.user.is_editor)
        self.assertFalse(self.user.is_administrator)
        
        # Test translator role
        self.user.role = 'translator'
        self.user.save()
        self.assertFalse(self.user.is_writer)
        self.assertTrue(self.user.is_translator)
        self.assertFalse(self.user.is_editor)
        self.assertFalse(self.user.is_administrator)
        
        # Test editor role
        self.user.role = 'editor'
        self.user.save()
        self.assertTrue(self.user.is_writer)
        self.assertTrue(self.user.is_translator)
        self.assertTrue(self.user.is_editor)
        self.assertFalse(self.user.is_administrator)
        
        # Test admin role
        self.user.role = 'admin'
        self.user.save()
        self.assertTrue(self.user.is_writer)
        self.assertTrue(self.user.is_translator)
        self.assertTrue(self.user.is_editor)
        self.assertTrue(self.user.is_administrator)


class BookCollaboratorTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.book = Book.objects.create(
            title='Test Book',
            owner=self.user
        )
        self.collaborator = BookCollaborator.objects.create(
            book=self.book,
            user=self.user,
            role='co_author'
        )
    
    def test_collaborator_creation(self):
        self.assertEqual(self.collaborator.book, self.book)
        self.assertEqual(self.collaborator.user, self.user)
        self.assertEqual(self.collaborator.role, 'co_author')
    
    def test_collaborator_permissions(self):
        permissions = self.collaborator.get_permissions()
        self.assertTrue(permissions['can_read'])
        self.assertTrue(permissions['can_write'])
        self.assertTrue(permissions['can_translate'])
        self.assertFalse(permissions['can_edit'])
        self.assertFalse(permissions['can_approve'])
        self.assertFalse(permissions['can_delete'])


class TranslationAssignmentTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            role='translator'
        )
        self.book = Book.objects.create(
            title='Test Book',
            owner=self.user
        )
        self.chapter = Chapter.objects.create(
            book=self.book,
            title='Test Chapter',
            content='Test content'
        )
        self.language = Language.objects.create(
            code='es',
            name='Spanish',
            local_name='Español'
        )
        self.assignment = TranslationAssignment.objects.create(
            chapter=self.chapter,
            translator=self.user,
            target_language=self.language
        )
    
    def test_assignment_creation(self):
        self.assertEqual(self.assignment.chapter, self.chapter)
        self.assertEqual(self.assignment.translator, self.user)
        self.assertEqual(self.assignment.target_language, self.language)
        self.assertEqual(self.assignment.status, 'pending')
    
    def test_assignment_string_representation(self):
        expected = f"Translation of {self.chapter.title} to {self.language.name} by {self.user.display_name}"
        self.assertEqual(str(self.assignment), expected)


class ViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            role='writer'
        )
    
    def test_profile_view_authenticated(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('accounts:profile'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'testuser')
    
    def test_profile_view_unauthenticated(self):
        response = self.client.get(reverse('accounts:profile'))
        self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_profile_edit_view(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('accounts:profile_edit'))
        self.assertEqual(response.status_code, 200)
    
    def test_user_list_view_admin_only(self):
        # Test as regular user (should be denied)
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('accounts:user_list'))
        self.assertEqual(response.status_code, 302)  # Redirect due to permission denied
        
        # Test as admin user
        admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            role='admin'
        )
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('accounts:user_list'))
        self.assertEqual(response.status_code, 200)
    
    def test_translation_assignments_view_translator_only(self):
        # Test as regular user (should be denied)
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('accounts:translation_assignments'))
        self.assertEqual(response.status_code, 302)  # Redirect due to permission denied
        
        # Test as translator user
        translator_user = User.objects.create_user(
            username='translator',
            email='translator@example.com',
            password='translatorpass123',
            role='translator'
        )
        self.client.login(username='translator', password='translatorpass123')
        response = self.client.get(reverse('accounts:translation_assignments'))
        self.assertEqual(response.status_code, 200)
