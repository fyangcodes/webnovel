# Structured Content Implementation

## Overview

This implementation provides a flexible, file-based storage system for chapter content with paragraph-level commenting capabilities, similar to Wattpad's functionality.

## Key Features

### 1. Flexible Paragraph Parsing
- **Single Newline**: Each line becomes a paragraph (good for poetry, short content)
- **Double Newline**: Traditional paragraph separation (good for prose)
- **Auto Detect**: Automatically determines the best parsing method

### 2. File-Based Storage
- Content stored as JSON files outside the database
- Organized by book and chapter: `content/chapters/book_{id}/chapter_{id}.json`
- Images stored separately: `images/book_{id}/chapter_{id}/image_{position}.{ext}`

### 3. Clean JSON Structure
```json
[
  {
    "type": "paragraph",
    "content": "This is the first paragraph of the chapter."
  },
  {
    "type": "image",
    "image_id": 123,
    "caption": "A beautiful sunset over the mountains"
  },
  {
    "type": "paragraph",
    "content": "This is the second paragraph that comes after the image."
  }
]
```

### 4. Paragraph-Level Commenting
- Comments can be attached to specific paragraphs or images
- Uses array indices for precise element targeting
- Supports nested replies and moderation

## Database Models

### Chapter Model Enhancements
```python
class Chapter(TimeStampedModel):
    # New fields
    content_file_path = models.CharField(max_length=255, blank=True)
    paragraph_style = models.CharField(
        max_length=20, 
        choices=[
            ('single_newline', 'Single Newline'),
            ('double_newline', 'Double Newline'),
            ('auto_detect', 'Auto Detect')
        ],
        default='auto_detect'
    )
```

### ChapterImage Model
```python
class ChapterImage(models.Model):
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='chapter_image_upload_to')
    caption = models.TextField(blank=True)
    alt_text = models.CharField(max_length=255, blank=True)
    position = models.PositiveIntegerField(help_text="Order in chapter")
```

### ChapterComment Model
```python
class ChapterComment(models.Model):
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name='comments')
    element_index = models.PositiveIntegerField(null=True, blank=True)  # Array index
    image = models.ForeignKey(ChapterImage, on_delete=models.CASCADE, related_name='comments', null=True, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='chapter_comments')
    comment_type = models.CharField(max_length=20, choices=COMMENT_TYPE_CHOICES, default='paragraph')
    content = models.TextField()
    parent_comment = models.ForeignKey('self', on_delete=models.CASCADE, related_name='replies', null=True, blank=True)
    is_public = models.BooleanField(default=True)
    is_moderated = models.BooleanField(default=False)
```

## Key Methods

### Content Access
- `get_structured_content()`: Load content from JSON file or parse legacy content
- `get_paragraphs()`: Get paragraphs with calculated numbers
- `get_paragraphs_and_images()`: Get all content elements
- `get_element_by_index(index)`: Get specific element by array index

### Content Manipulation
- `add_paragraph(content, position=None)`: Add new paragraph
- `add_image(image_id, caption="", position=None)`: Add new image
- `update_paragraph(index, content)`: Update paragraph content
- `delete_element(index)`: Delete element at index
- `reorder_elements(new_order)`: Reorder elements

### File Management
- `get_content_file_path()`: Generate organized file path
- `save_structured_content(structured_content)`: Save to JSON file
- `get_book_content_directory()`: Get book's content directory
- `get_chapter_images_directory()`: Get chapter's images directory

## Usage Examples

### Basic Usage
```python
# Get structured content
chapter = Chapter.objects.get(id=1)
content = chapter.get_structured_content()

# Get paragraphs with numbers
paragraphs = chapter.get_paragraphs()
for p in paragraphs:
    print(f"Paragraph {p['paragraph_number']}: {p['content']}")

# Add new paragraph
chapter.add_paragraph("This is a new paragraph.")

# Add image
chapter.add_image(image_id=123, caption="Beautiful sunset")
```

### Commenting
```python
# Create comment on paragraph
comment = ChapterComment.objects.create(
    chapter=chapter,
    element_index=0,  # First element
    user=user,
    content="Great opening paragraph!"
)

# Get paragraph number for comment
paragraph_number = comment.paragraph_number

# Get element content
element_content = comment.element_content
```

## Migration

### Automatic Migration
```bash
# Migrate all chapters
python manage.py migrate_to_structured_content

# Migrate specific book
python manage.py migrate_to_structured_content --book-id 1

# Dry run to see what would be migrated
python manage.py migrate_to_structured_content --dry-run

# Force migration even if files exist
python manage.py migrate_to_structured_content --force
```

### Manual Migration
```python
# For individual chapters
chapter = Chapter.objects.get(id=1)
structured_content = chapter.get_structured_content()
chapter.save_structured_content(structured_content)
```

## File Structure

```
media/
├── content/
│   └── chapters/
│       ├── book_1/
│       │   ├── chapter_1.json
│       │   ├── chapter_2.json
│       │   └── chapter_3.json
│       └── book_2/
│           ├── chapter_1.json
│           └── chapter_2.json
├── images/
│   ├── book_1/
│   │   ├── chapter_1/
│   │   │   ├── image_1.jpg
│   │   │   └── image_2.png
│   │   └── chapter_2/
│   │       └── image_1.jpg
│   └── book_2/
│       └── chapter_1/
│           └── image_1.jpg
```

## Benefits

1. **Performance**: Database queries are faster, content doesn't bloat the database
2. **Scalability**: Easy to handle large amounts of content
3. **Flexibility**: Support for different content types and parsing styles
4. **Modularity**: Each book is self-contained
5. **Version Control**: JSON files can be versioned with Git
6. **Caching**: Files can be cached at CDN level
7. **Backup**: Easy to backup content separately from database

## Testing

Run the test script to verify functionality:
```bash
python test_structured_content.py
```

## Future Enhancements

1. **Real-time Collaboration**: WebSocket support for live commenting
2. **Advanced Moderation**: AI-powered comment filtering
3. **Content Analytics**: Track popular paragraphs and engagement
4. **Export Features**: Export chapters in various formats
5. **Version History**: Track changes to structured content
6. **Search Integration**: Full-text search across paragraphs

## Notes

- The original `content` field is preserved for backward compatibility
- Paragraph numbers are calculated from array indices, not stored in JSON
- Images are stored separately and referenced by ID in JSON
- The system automatically falls back to legacy content parsing if JSON files don't exist 