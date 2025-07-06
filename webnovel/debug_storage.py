#!/usr/bin/env python
"""
Debug script to investigate storage system issues.
"""
import os
import sys
import django

# Add the webnovel directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webnovel.settings')
django.setup()

from books.models import Chapter
from django.conf import settings
from django.core.files.storage import default_storage

def debug_storage():
    """Debug storage system issues."""
    
    print("=== STORAGE DEBUG ===")
    print(f"MEDIA_ROOT: {settings.MEDIA_ROOT}")
    print(f"MEDIA_URL: {settings.MEDIA_URL}")
    print(f"BASE_DIR: {settings.BASE_DIR}")
    
    # Check if MEDIA_ROOT exists
    print(f"\nMEDIA_ROOT exists: {os.path.exists(settings.MEDIA_ROOT)}")
    if os.path.exists(settings.MEDIA_ROOT):
        print(f"MEDIA_ROOT contents: {os.listdir(settings.MEDIA_ROOT)}")
    
    # Get the first chapter with structured content
    chapter = Chapter.objects.filter(content_file_path__isnull=False).first()
    if not chapter:
        print("No chapters with structured content found.")
        return
    
    print(f"\n=== CHAPTER DEBUG ===")
    print(f"Chapter: {chapter.title} (ID: {chapter.id})")
    print(f"Database content_file_path: {chapter.content_file_path}")
    
    # Test different storage methods
    print(f"\n=== STORAGE TESTS ===")
    
    # Test 1: Direct file path
    print(f"1. Testing direct file path: {chapter.content_file_path}")
    print(f"   default_storage.exists(): {default_storage.exists(chapter.content_file_path)}")
    
    # Test 2: Full path
    full_path = os.path.join(settings.MEDIA_ROOT, chapter.content_file_path)
    print(f"2. Testing full path: {full_path}")
    print(f"   os.path.exists(): {os.path.exists(full_path)}")
    
    # Test 3: Check what files actually exist
    print(f"\n3. Checking actual files in media directory:")
    media_dir = settings.MEDIA_ROOT
    if os.path.exists(media_dir):
        for root, dirs, files in os.walk(media_dir):
            rel_path = os.path.relpath(root, media_dir)
            if rel_path == '.':
                rel_path = ''
            for file in files:
                if file.endswith('.json'):
                    storage_path = os.path.join(rel_path, file).replace('\\', '/')
                    print(f"   Found: {storage_path}")
    
    # Test 4: Test get_content_file_path method
    print(f"\n4. Testing get_content_file_path method:")
    expected_path = chapter.get_content_file_path()
    print(f"   Expected path: {expected_path}")
    print(f"   default_storage.exists(): {default_storage.exists(expected_path)}")
    
    # Test 5: Check if the file exists with different path formats
    print(f"\n5. Testing different path formats:")
    test_paths = [
        chapter.content_file_path,
        f"media/{chapter.content_file_path}",
        chapter.content_file_path.replace('content/', 'media/content/'),
        expected_path,
        f"media/{expected_path}",
    ]
    
    for path in test_paths:
        exists = default_storage.exists(path)
        print(f"   {path}: {exists}")
        if exists:
            try:
                with default_storage.open(path, 'r') as f:
                    content = f.read(100)
                    print(f"     Content preview: {content[:50]}...")
            except Exception as e:
                print(f"     Error reading: {e}")
    
    # Test 6: Check storage backend
    print(f"\n6. Storage backend info:")
    print(f"   Storage class: {type(default_storage).__name__}")
    print(f"   Storage location: {getattr(default_storage, 'location', 'N/A')}")
    
    # Test 7: Try to list directory contents
    print(f"\n7. Testing directory listing:")
    content_dir = os.path.dirname(chapter.content_file_path)
    print(f"   Content directory: {content_dir}")
    try:
        if default_storage.exists(content_dir):
            directories, files = default_storage.listdir(content_dir)
            print(f"   Files in directory: {files}")
        else:
            print(f"   Directory does not exist")
    except Exception as e:
        print(f"   Error listing directory: {e}")

if __name__ == "__main__":
    debug_storage() 