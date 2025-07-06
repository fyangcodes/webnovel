#!/usr/bin/env python
"""
Debug script to understand version logic in get_content_file_path method.
"""
import os
import sys
import django
import re

# Add the webnovel directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webnovel.settings')
django.setup()

from books.models import Chapter
from django.conf import settings
from django.core.files.storage import default_storage

def debug_version_logic():
    """Debug version logic in get_content_file_path method."""
    
    print("=== VERSION LOGIC DEBUG ===")
    
    chapter = Chapter.objects.filter(content_file_path__isnull=False).first()
    if not chapter:
        print("No chapters with structured content found.")
        return
    
    print(f"Chapter: {chapter.title} (ID: {chapter.id})")
    print(f"Database content_file_path: {chapter.content_file_path}")
    
    # Simulate the get_content_file_path logic
    book_id = chapter.book.id
    chapter_id = chapter.id
    base_dir = f"content/chapters/book_{book_id}"
    
    print(f"\nSimulating get_content_file_path logic:")
    print(f"  book_id: {book_id}")
    print(f"  chapter_id: {chapter_id}")
    print(f"  base_dir: {base_dir}")
    
    # Use Django's storage system to list files
    pattern = re.compile(rf"chapter_{chapter_id}_v(\\d+)\\.json")
    existing_versions = []
    
    print(f"  Pattern: {pattern.pattern}")
    
    try:
        # List all files in the directory using Django storage
        if default_storage.exists(base_dir):
            directories, files = default_storage.listdir(base_dir)
            print(f"  Files in directory: {files}")
            
            for f in files:
                match = pattern.match(f)
                if match:
                    version = int(match.group(1))
                    existing_versions.append(version)
                    print(f"    Matched: {f} -> version {version}")
                else:
                    print(f"    No match: {f}")
        else:
            print(f"  Directory does not exist: {base_dir}")
    except Exception as e:
        print(f"  Error listing files: {e}")
        existing_versions = []
    
    print(f"  Existing versions found: {existing_versions}")
    
    latest_version = max(existing_versions) if existing_versions else 0
    print(f"  Latest version: {latest_version}")
    
    # Test both next_version=False and next_version=True
    current_path = f"{base_dir}/chapter_{chapter_id}_v{latest_version}.json"
    next_path = f"{base_dir}/chapter_{chapter_id}_v{latest_version + 1}.json"
    
    print(f"  Current path (next_version=False): {current_path}")
    print(f"  Next path (next_version=True): {next_path}")
    
    print(f"  Current path exists: {default_storage.exists(current_path)}")
    print(f"  Next path exists: {default_storage.exists(next_path)}")
    
    # Test the actual method
    print(f"\nTesting actual get_content_file_path method:")
    actual_path = chapter.get_content_file_path()
    print(f"  get_content_file_path() returns: {actual_path}")
    print(f"  This path exists: {default_storage.exists(actual_path)}")
    
    # Compare with database path
    print(f"\nComparison:")
    print(f"  Database path: {chapter.content_file_path}")
    print(f"  Generated path: {actual_path}")
    print(f"  Database path exists: {default_storage.exists(chapter.content_file_path)}")
    print(f"  Generated path exists: {default_storage.exists(actual_path)}")
    
    # Check if we should use the database path instead
    if default_storage.exists(chapter.content_file_path) and not default_storage.exists(actual_path):
        print(f"\nRECOMMENDATION: Use database path instead of generated path!")
        print(f"  The database path exists and contains the correct data.")
        print(f"  The generated path does not exist.")

if __name__ == "__main__":
    debug_version_logic() 