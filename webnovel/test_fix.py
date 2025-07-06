#!/usr/bin/env python
"""
Test script to verify the get_structured_content fix.
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

def test_structured_content():
    """Test that get_structured_content now works correctly."""
    
    print("=== TESTING STRUCTURED CONTENT FIX ===")
    
    chapter = Chapter.objects.filter(content_file_path__isnull=False).first()
    if not chapter:
        print("No chapters with structured content found.")
        return
    
    print(f"Chapter: {chapter.title} (ID: {chapter.id})")
    print(f"Database content_file_path: {chapter.content_file_path}")
    
    # Test get_structured_content
    structured_content = chapter.get_structured_content()
    print(f"get_structured_content returned {len(structured_content)} elements")
    
    # Check for images
    image_elements = [elem for elem in structured_content if elem.get('type') == 'image']
    print(f"Found {len(image_elements)} image elements")
    
    for i, element in enumerate(image_elements):
        print(f"\nImage {i+1}:")
        print(f"  Image ID: {element.get('image_id')}")
        print(f"  File path: {element.get('file_path')}")
        print(f"  Caption: {element.get('caption', 'No caption')}")
    
    # Check element types
    element_types = {}
    for elem in structured_content:
        elem_type = elem.get('type', 'unknown')
        element_types[elem_type] = element_types.get(elem_type, 0) + 1
    
    print(f"\nElement types: {element_types}")
    
    # Test template rendering
    print(f"\n=== TESTING TEMPLATE RENDERING ===")
    from django.template import Template, Context
    
    template_code = """
    {% for element in structured_content %}
        {% if element.type == 'image' %}
            <div class="media-element mb-4">
                {% if element.file_path %}
                    <img src="{{ element.file_path }}" alt="{{ element.caption|default:'Chapter image' }}" class="img-fluid rounded">
                {% else %}
                    <div class="alert alert-warning">Image file not found</div>
                {% endif %}
                {% if element.caption %}
                    <div class="text-center mt-2">
                        <small class="text-muted">{{ element.caption }}</small>
                    </div>
                {% endif %}
            </div>
        {% elif element.type == 'text' %}
            <div class="text-element mb-3">
                <p>{{ element.content|linebreaks }}</p>
            </div>
        {% endif %}
    {% endfor %}
    """
    
    template = Template(template_code)
    context = Context({'structured_content': structured_content})
    rendered = template.render(context)
    
    # Count images in rendered HTML
    img_count = rendered.count('<img')
    print(f"Rendered HTML contains {img_count} <img> tags")
    
    if img_count > 0:
        print("SUCCESS: Images are being rendered correctly!")
    else:
        print("WARNING: No images found in rendered HTML")

if __name__ == "__main__":
    test_structured_content() 