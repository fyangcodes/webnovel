#!/usr/bin/env python
"""
Example usage of user avatar functionality

This script demonstrates how to use the user avatar methods and utilities.
Run this in a Django shell or as a management command.
"""

from django.templatetags.static import static
from .models import User
from .utils import get_default_user_avatar_url, get_user_avatar_url, get_user_avatar_data


def example_user_avatar_usage():
    """Example of how to use user avatar functionality in Python code"""
    
    print("=== User Avatar Usage Examples ===\n")
    
    # 1. Get default avatar URL
    default_url = get_default_user_avatar_url()
    print(f"1. Default avatar URL: {default_url}")
    
    # 2. Get avatar URL for a specific user
    try:
        # Get the first user from the database
        user = User.objects.first()
        if user:
            avatar_url = user.get_avatar_url()
            print(f"2. User '{user.display_name}' avatar URL: {avatar_url}")
            
            # Check if it has a custom avatar
            has_custom = user.has_custom_avatar
            print(f"   Has custom avatar: {has_custom}")
            
            # Get comprehensive avatar data
            avatar_data = user.get_avatar_data()
            print(f"3. Avatar data: {avatar_data}")
            
            # Get thumbnail URL
            thumbnail_url = user.get_avatar_thumbnail_url()
            print(f"4. Thumbnail URL: {thumbnail_url}")
            
        else:
            print("2. No users found in database")
            
    except Exception as e:
        print(f"2. Error accessing user: {e}")
    
    # 3. Using utility functions
    print(f"\n5. Using utility functions:")
    print(f"   Default URL: {get_default_user_avatar_url()}")
    
    if user:
        print(f"   User avatar URL: {get_user_avatar_url(user)}")
        print(f"   User avatar data: {get_user_avatar_data(user)}")
    
    # 4. Example for API response
    print(f"\n6. Example API response format:")
    if user:
        api_data = {
            'id': user.id,
            'username': user.username,
            'display_name': user.display_name,
            'avatar': user.get_avatar_data(),
            'role': user.role,
        }
        print(f"   {api_data}")


def example_template_usage():
    """Example of how to use in templates"""
    
    print("\n=== Template Usage Examples ===\n")
    
    print("1. Basic usage in template:")
    print("   <img src=\"{{ user.get_avatar_url }}\" alt=\"{{ user.display_name }}\">")
    
    print("\n2. With thumbnail for smaller displays:")
    print("   <img src=\"{{ user.get_avatar_thumbnail_url }}\" alt=\"{{ user.display_name }}\">")
    
    print("\n3. With conditional styling:")
    print("   <img src=\"{{ user.get_avatar_url }}\" ")
    print("        class=\"avatar-image {% if user.has_custom_avatar %}custom{% else %}default{% endif %}\"")
    print("        alt=\"{{ user.display_name }}\">")
    
    print("\n4. With fallback handling:")
    print("   {% if user.has_custom_avatar %}")
    print("       <img src=\"{{ user.avatar.url }}\" alt=\"{{ user.display_name }}\">")
    print("   {% else %}")
    print("       <img src=\"{% static 'images/default_user_avatar.png' %}\" alt=\"Default avatar\">")
    print("   {% endif %}")


def example_different_sizes():
    """Example of using different avatar sizes"""
    
    print("\n=== Different Avatar Sizes ===\n")
    
    try:
        user = User.objects.first()
        if user:
            print("Avatar URLs for different use cases:")
            print(f"1. Profile page (large): {user.get_avatar_url()}")
            print(f"2. User list (thumbnail): {user.get_avatar_thumbnail_url()}")
            print(f"3. Navigation (small): {user.get_avatar_thumbnail_url()}")
            
            # Example of conditional sizing
            print("\n4. Conditional sizing example:")
            context = "profile"  # Could be 'list', 'nav', etc.
            
            if context == "profile":
                avatar_url = user.get_avatar_url()
                size = 150
            elif context == "list":
                avatar_url = user.get_avatar_thumbnail_url()
                size = 40
            else:
                avatar_url = user.get_avatar_thumbnail_url()
                size = 30
                
            print(f"   Context: {context}")
            print(f"   URL: {avatar_url}")
            print(f"   Size: {size}px")
            
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    # This would be run in a Django shell
    example_user_avatar_usage()
    example_template_usage()
    example_different_sizes() 