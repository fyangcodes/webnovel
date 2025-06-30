#!/usr/bin/env python
"""
Test script to debug LLM tracking functionality.
Run this script to check if LLMServiceCall entries are being created.
"""

import os
import sys
import django
from django.conf import settings

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webnovel.settings')
django.setup()

from django.contrib.auth import get_user_model
from llm_integration.models import LLMProvider, LLMServiceCall, LLMQualityMetrics
from llm_integration.services import LLMTranslationService
from books.models import Book, Chapter

User = get_user_model()

def test_llm_tracking():
    """Test LLM tracking functionality"""
    print("=== LLM Tracking Debug Test ===\n")
    
    # 1. Check database state before test
    print("1. Checking initial database state...")
    initial_calls = LLMServiceCall.objects.count()
    initial_metrics = LLMQualityMetrics.objects.count()
    providers = LLMProvider.objects.all()
    
    print(f"   - LLMServiceCall entries: {initial_calls}")
    print(f"   - LLMQualityMetrics entries: {initial_metrics}")
    print(f"   - LLMProvider entries: {providers.count()}")
    
    if providers.exists():
        print("   - Available providers:")
        for provider in providers:
            print(f"     * {provider.name} (active: {provider.is_active})")
    else:
        print("   - No providers found!")
        return
    
    # 2. Check if we have any books/chapters to test with
    print("\n2. Checking for test data...")
    books = Book.objects.all()
    chapters = Chapter.objects.all()
    
    print(f"   - Books: {books.count()}")
    print(f"   - Chapters: {chapters.count()}")
    
    if not chapters.exists():
        print("   - No chapters found for testing!")
        return
    
    # 3. Get a test chapter and user
    test_chapter = chapters.first()
    test_user = User.objects.first()
    
    if not test_user:
        print("   - No users found!")
        return
    
    print(f"   - Using chapter: {test_chapter.title}")
    print(f"   - Chapter language: {test_chapter.language}")
    print(f"   - Chapter book: {test_chapter.book.title}")
    print(f"   - Using user: {test_user.username}")
    
    # 4. Test manual creation of LLMServiceCall
    print("\n3. Testing manual LLMServiceCall creation...")
    try:
        test_provider = providers.first()
        manual_call = LLMServiceCall.objects.create(
            provider=test_provider,
            operation='translation',
            model_name='test-model',
            input_tokens=100,
            output_tokens=50,
            status='success',
            response_time_ms=1500,
            error_message='',
            created_by=test_user
        )
        print(f"   - Successfully created manual LLMServiceCall: {manual_call.id}")
        
        # Clean up manual test
        manual_call.delete()
        print("   - Cleaned up manual test entry")
        
    except Exception as e:
        print(f"   - ERROR creating manual LLMServiceCall: {e}")
        return
    
    # 5. Test actual translation service call with both source and target chapters
    print("\n4. Testing actual translation service call...")
    try:
        service = LLMTranslationService()
        
        # Create a target book and target chapter for translation
        target_book, _ = Book.objects.get_or_create(
            title=f"{test_chapter.book.title} (English Translation)",
            defaults={
                'language': test_chapter.book.language,  # You may want to set to English Language object
                'author': test_chapter.book.author,
                'owner': test_chapter.book.owner,
            }
        )
        target_chapter = Chapter.objects.create(
            book=target_book,
            title=f"{test_chapter.title} (EN)",
            content="Pending translation...",  # Use dummy content to avoid validation error
            language=target_book.language,
            chapter_number=9999  # Dummy number for test
        )
        
        print(f"   - Testing translation of chapter: '{test_chapter.title}'")
        print(f"   - Source language: {test_chapter.language}")
        print(f"   - Target language: English")
        
        result = service.translate_chapter(
            chapter_text=test_chapter.content[:500],  # First 500 chars for testing
            target_language='en',
            source_chapter=test_chapter,
            target_chapter=target_chapter,
            user=test_user
        )
        
        # Optionally update the target chapter content
        target_chapter.content = result
        target_chapter.save()
        
        print(f"   - Translation result: {result[:200]}...")
        
    except Exception as e:
        print(f"   - ERROR during translation: {e}")
        import traceback
        traceback.print_exc()
    
    # 6. Check database state after test
    print("\n5. Checking final database state...")
    final_calls = LLMServiceCall.objects.count()
    final_metrics = LLMQualityMetrics.objects.count()
    
    print(f"   - LLMServiceCall entries: {final_calls}")
    print(f"   - LLMQualityMetrics entries: {final_metrics}")
    
    if final_calls > initial_calls:
        print(f"   - SUCCESS: {final_calls - initial_calls} new LLMServiceCall entries created!")
        
        # Show the new entries with detailed information
        new_calls = LLMServiceCall.objects.order_by('-created_at')[:final_calls - initial_calls]
        for call in new_calls:
            print(f"     * {call.operation} - {call.provider.name} - {call.model_name}")
            print(f"       Source: {call.source_language} -> Target: {call.target_language}")
            print(f"       Source Book: {call.source_book.title if call.source_book else 'None'}")
            print(f"       Source Chapter: {call.source_chapter.title if call.source_chapter else 'None'}")
            print(f"       Target Book: {call.target_book.title if call.target_book else 'None'}")
            print(f"       Target Chapter: {call.target_chapter.title if call.target_chapter else 'None'}")
            print(f"       Status: {call.status}")
    else:
        print("   - FAILURE: No new LLMServiceCall entries created!")
        
        # Check if there are any recent entries
        recent_calls = LLMServiceCall.objects.order_by('-created_at')[:5]
        if recent_calls.exists():
            print("   - Recent LLMServiceCall entries:")
            for call in recent_calls:
                print(f"     * {call.created_at} - {call.operation} - {call.provider.name}")
                print(f"       Source: {call.source_language} -> Target: {call.target_language}")
                print(f"       Source Book: {call.source_book.title if call.source_book else 'None'}")
                print(f"       Source Chapter: {call.source_chapter.title if call.source_chapter else 'None'}")
                print(f"       Target Book: {call.target_book.title if call.target_book else 'None'}")
                print(f"       Target Chapter: {call.target_chapter.title if call.target_chapter else 'None'}")
        else:
            print("   - No LLMServiceCall entries found in database")
    
    # 7. Check for any errors in recent calls
    print("\n6. Checking for failed calls...")
    failed_calls = LLMServiceCall.objects.filter(status='error').order_by('-created_at')[:5]
    if failed_calls.exists():
        print("   - Recent failed calls:")
        for call in failed_calls:
            print(f"     * {call.created_at} - {call.operation} - {call.error_message}")
    else:
        print("   - No failed calls found")
    
    print("\n=== Test Complete ===")

if __name__ == '__main__':
    test_llm_tracking() 