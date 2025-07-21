import os
from datetime import datetime
import uuid
from django.core.files.storage import default_storage

def generate_unique_filename(base_path, filename):
    """
    Generate a unique filename to prevent overwrites on S3.

    Args:
        base_path: The base directory path
        filename: The original filename

    Returns:
        str: A unique filename with timestamp and/or counter
    """
    # Split filename into name and extension
    name, ext = os.path.splitext(filename)

    # Generate timestamp for uniqueness
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Create the full path
    full_path = f"{base_path}/{name}_{timestamp}{ext}"

    # Check if file exists, if so, add a counter
    counter = 1
    while default_storage.exists(full_path):
        full_path = f"{base_path}/{name}_{timestamp}_{counter}{ext}"
        counter += 1
        # Prevent infinite loops
        if counter > 1000:
            # If we hit 1000, use UUID as fallback
            unique_id = str(uuid.uuid4())[:8]
            full_path = f"{base_path}/{name}_{timestamp}_{unique_id}{ext}"
            break

    return full_path


def book_file_upload_to(instance, filename):
    """Generate upload path for book files with duplicate handling"""
    base_path = instance.book.files_directory
    return generate_unique_filename(base_path, filename)


def chapter_media_upload_to(instance, filename):
    """Generate organized upload path for chapter media with duplicate handling"""
    base_path = instance.chapter.media_directory
    return generate_unique_filename(base_path, filename)


def book_cover_upload_to(instance, filename):
    """Generate upload path for book cover images with duplicate handling"""
    base_path = instance.book.covers_directory
    return generate_unique_filename(base_path, filename)