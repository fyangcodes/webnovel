#!/usr/bin/env python
"""
Example usage of book cover functionality

This script demonstrates how to use the book cover methods and utilities.
Run this in a Django shell or as a management command.
"""

from django.templatetags.static import static
from .models import Book
from .utils import get_default_book_cover_url, get_book_cover_url, get_book_cover_data


def example_book_cover_usage():
    """Example of how to use book cover functionality in Python code"""
    
    print("=== Book Cover Usage Examples ===\n")
    
    # 1. Get default cover URL
    default_url = get_default_book_cover_url()
    print(f"1. Default cover URL: {default_url}")
    
    # 2. Get cover URL for a specific book
    try:
        # Get the first book from the database
        book = Book.objects.first()
        if book:
            cover_url = book.get_cover_image_url()
            print(f"2. Book '{book.title}' cover URL: {cover_url}")
            
            # Check if it has a custom cover
            has_custom = book.has_custom_cover
            print(f"   Has custom cover: {has_custom}")
            
            # Get comprehensive cover data
            cover_data = book.get_cover_image_data()
            print(f"3. Cover data: {cover_data}")
            
        else:
            print("2. No books found in database")
            
    except Exception as e:
        print(f"2. Error accessing book: {e}")
    
    # 3. Using utility functions
    print(f"\n4. Using utility functions:")
    print(f"   Default URL: {get_default_book_cover_url()}")
    
    if book:
        print(f"   Book cover URL: {get_book_cover_url(book)}")
        print(f"   Book cover data: {get_book_cover_data(book)}")
    
    # 4. Example for API response
    print(f"\n5. Example API response format:")
    if book:
        api_data = {
            'id': book.id,
            'title': book.title,
            'cover_image': book.get_cover_image_data(),
            'status': book.status,
        }
        print(f"   {api_data}")


def example_template_usage():
    """Example of how to use in templates"""
    
    print("\n=== Template Usage Examples ===\n")
    
    print("1. Basic usage in template:")
    print("   <img src=\"{{ book.get_cover_image_url }}\" alt=\"{{ book.title }}\">")
    
    print("\n2. With conditional styling:")
    print("   <img src=\"{{ book.get_cover_image_url }}\" ")
    print("        class=\"cover-image {% if book.has_custom_cover %}custom{% else %}default{% endif %}\"")
    print("        alt=\"{{ book.title }}\">")
    
    print("\n3. With fallback handling:")
    print("   {% if book.has_custom_cover %}")
    print("       <img src=\"{{ book.cover_image.url }}\" alt=\"{{ book.title }}\">")
    print("   {% else %}")
    print("       <img src=\"{% static 'images/default_book_cover.png' %}\" alt=\"Default cover\">")
    print("   {% endif %}")


if __name__ == "__main__":
    # This would be run in a Django shell
    example_book_cover_usage()
    example_template_usage() 