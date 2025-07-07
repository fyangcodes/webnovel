from django.templatetags.static import static
from .models import User


def get_default_user_avatar_url():
    """Get the URL for the default user avatar image"""
    return static("images/default_user_avatar.png")


def get_user_avatar_url(user):
    """Get the avatar URL for a user with fallback to default"""
    if not isinstance(user, User):
        return get_default_user_avatar_url()
    return user.get_avatar_url()


def get_user_avatar_thumbnail_url(user):
    """Get the avatar thumbnail URL for a user with fallback to default"""
    if not isinstance(user, User):
        return get_default_user_avatar_url()
    return user.get_avatar_thumbnail_url()


def get_user_avatar_data(user):
    """Get comprehensive avatar data for a user"""
    if not isinstance(user, User):
        return {
            'url': get_default_user_avatar_url(),
            'thumbnail_url': get_default_user_avatar_url(),
            'is_default': True,
            'custom_avatar_url': None,
            'custom_thumbnail_url': None,
        }
    return user.get_avatar_data()


def format_user_avatar_for_display(user, size=150, use_thumbnail=False):
    """Format user avatar for display with specific size"""
    avatar_data = get_user_avatar_data(user)
    
    if use_thumbnail and avatar_data['thumbnail_url']:
        url = avatar_data['thumbnail_url']
    else:
        url = avatar_data['url']
    
    return {
        'url': url,
        'alt_text': f"Avatar for {user.display_name}" if hasattr(user, 'display_name') else "User avatar",
        'size': size,
        'is_default': avatar_data['is_default'],
        'has_custom': avatar_data['custom_avatar_url'] is not None,
    } 