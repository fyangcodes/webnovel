# ChapterMedia Model Documentation

## Overview

The `ChapterMedia` model is a generalized media storage system that extends the original `ChapterImage` model to support multiple media types including images, audio, video, and documents. This provides a flexible foundation for rich multimedia content in chapters.

## Key Features

- **Multiple Media Types**: Support for images, audio, video, documents, and other file types
- **Automatic Type Detection**: Media type is automatically detected from file extension
- **Rich Metadata**: File size, MIME type, duration (for audio/video), thumbnails
- **Processing Status**: Track processing state and errors
- **Backward Compatibility**: Existing `ChapterImage` functionality is preserved
- **Organized Storage**: Files are stored in organized directory structures
- **Admin Interface**: Full Django admin integration with inline editing

## Media Types Supported

### Images
- **Extensions**: jpg, jpeg, png, gif, webp, svg, bmp
- **Features**: Caption, alt text, thumbnail support

### Audio
- **Extensions**: mp3, wav, ogg, m4a, flac, aac
- **Features**: Duration tracking, title, caption, optional thumbnail

### Video
- **Extensions**: mp4, avi, mov, wmv, flv, webm, mkv
- **Features**: Duration tracking, title, caption, thumbnail support

### Documents
- **Extensions**: pdf, doc, docx, txt, rtf, odt
- **Features**: Title, caption, file size tracking

## Model Structure

### Core Fields
```python
class ChapterMedia(TimeStampedModel):
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name="media")
    media_type = models.CharField(max_length=20, choices=MEDIA_TYPE_CHOICES, default='image')
    file = models.FileField(upload_to="chapter_media_upload_to")
    title = models.CharField(max_length=255, blank=True)
    caption = models.TextField(blank=True)
    alt_text = models.CharField(max_length=255, blank=True)
    position = models.PositiveIntegerField(help_text="Order in chapter")
```

### Media-Specific Fields
```python
    # Media-specific metadata
    duration = models.PositiveIntegerField(null=True, blank=True)  # For audio/video
    file_size = models.PositiveIntegerField(default=0)
    mime_type = models.CharField(max_length=100, blank=True)
    
    # Processing status
    is_processed = models.BooleanField(default=False)
    processing_error = models.TextField(blank=True)
    
    # Thumbnail for video/audio
    thumbnail = models.ImageField(upload_to="chapter_media_thumbnails/", blank=True, null=True)
```

## Usage Examples

### Adding Media to a Chapter

**Note**: When you add media using the methods below, it is automatically integrated into the structured content file with the appropriate position.

#### Adding an Image
```python
from django.core.files.uploadedfile import SimpleUploadedFile

# Create a simple uploaded file (in real usage, this would be from a form)
image_file = SimpleUploadedFile(
    "my_image.jpg",
    image_content,
    content_type="image/jpeg"
)

# Add to chapter
media = chapter.add_image(
    image_file=image_file,
    caption="A beautiful landscape",
    alt_text="Mountain landscape with sunset"
)
```

#### Adding Audio
```python
audio_file = SimpleUploadedFile(
    "narration.mp3",
    audio_content,
    content_type="audio/mpeg"
)

media = chapter.add_audio(
    audio_file=audio_file,
    title="Chapter Narration",
    caption="Audio narration of this chapter",
    duration=180  # 3 minutes
)
```

#### Adding Video
```python
video_file = SimpleUploadedFile(
    "scene.mp4",
    video_content,
    content_type="video/mp4"
)

media = chapter.add_video(
    video_file=video_file,
    title="Scene Visualization",
    caption="Visual representation of the scene",
    duration=240,  # 4 minutes
    thumbnail=thumbnail_file  # Optional
)
```

#### Adding a Document
```python
doc_file = SimpleUploadedFile(
    "appendix.pdf",
    doc_content,
    content_type="application/pdf"
)

media = chapter.add_document(
    document_file=doc_file,
    title="Chapter Appendix",
    caption="Additional materials for this chapter"
)
```

### Querying Media

#### Get All Media of a Specific Type
```python
# Get all images
images = chapter.get_images()

# Get all audio files
audio_files = chapter.get_audio()

# Get all videos
videos = chapter.get_videos()

# Get all documents
documents = chapter.get_documents()

# Get media by type (generic method)
image_media = chapter.get_media_by_type('image')
```

#### Get Media Statistics
```python
# Total media count
total_media = chapter.total_media_count

# Count by type
media_counts = chapter.get_media_count_by_type()
for count in media_counts:
    print(f"{count['media_type']}: {count['count']}")
```

### Working with Media Objects

#### Accessing Media Properties
```python
media = chapter.media.first()

# Basic properties
print(media.display_title)  # Title or filename
print(media.media_type)     # 'image', 'audio', 'video', 'document'
print(media.formatted_file_size)  # "1.5 MB"
print(media.formatted_duration)   # "03:45" (for audio/video)

# Type checking
if media.is_image:
    print("This is an image")
elif media.is_audio:
    print("This is audio")
elif media.is_video:
    print("This is video")
elif media.is_document:
    print("This is a document")
```

#### Reordering Media
```python
# Reorder media items by providing a list of media IDs
media_ids = [3, 1, 2, 4]  # New order
chapter.reorder_media(media_ids)
```

## File Storage Organization

Media files are stored in organized directory structures:

```
media/
├── image/
│   └── book_1/
│       └── chapter_5/
│           ├── image_1.jpg
│           └── image_2.png
├── audio/
│   └── book_1/
│       └── chapter_5/
│           └── audio_1.mp3
├── video/
│   └── book_1/
│       └── chapter_5/
│           └── video_1.mp4
└── document/
    └── book_1/
        └── chapter_5/
            └── document_1.pdf
```

Thumbnails are stored separately:
```
chapter_media_thumbnails/
├── thumbnail_1.jpg
└── thumbnail_2.png
```

## Admin Interface

The ChapterMedia model includes a comprehensive Django admin interface:

### ChapterMediaAdmin Features
- **List Display**: ID, chapter, media type, title, position, file size, duration, processing status
- **Filters**: Media type, processing status, creation date, book
- **Search**: Title, caption, alt text, chapter title, book title
- **Read-only Fields**: File size, MIME type, formatted file size, duration, timestamps

### Inline Editing
ChapterMedia can be edited inline within the Chapter admin interface, making it easy to manage media alongside chapter content.

## Backward Compatibility

The new ChapterMedia model is designed to work alongside the existing ChapterImage model:

### Existing ChapterImage Functionality
- All existing ChapterImage instances continue to work
- The `chapter.images` relationship is preserved
- Existing structured content with `image_id` references still work

### Migration Path
To migrate from ChapterImage to ChapterMedia:

1. **Gradual Migration**: Use both models simultaneously
2. **Data Migration**: Create ChapterMedia instances from existing ChapterImage instances
3. **Content Updates**: Update structured content to reference new media IDs

### Structured Content Integration

The structured content system supports both old and new media references:

```json
[
    {
        "type": "text",
        "content": "This is a paragraph with media."
    },
    {
        "type": "image",
        "image_id": 1,  // Legacy ChapterImage reference
        "caption": "Old image"
    },
    {
        "type": "image",
        "media_id": 5,  // New ChapterMedia reference
        "caption": "New image"
    },
    {
        "type": "audio",
        "media_id": 6,  // New ChapterMedia reference
        "caption": "Audio narration"
    }
]
```

## Best Practices

### File Management
1. **File Size Limits**: Consider implementing file size limits for different media types
2. **Format Validation**: Use the built-in file extension validators
3. **Processing**: Implement background tasks for media processing (thumbnails, metadata extraction)

### Performance
1. **Indexing**: The model includes database indexes for common queries
2. **Lazy Loading**: Use `select_related()` when querying media with chapter information
3. **Caching**: Consider caching media metadata for frequently accessed content

### Security
1. **File Validation**: Always validate uploaded files
2. **Access Control**: Implement proper permissions for media access
3. **Storage**: Use secure storage backends for sensitive media

## Future Enhancements

### Potential Features
- **Media Processing**: Automatic thumbnail generation, video transcoding
- **CDN Integration**: Support for content delivery networks
- **Streaming**: Support for streaming audio/video
- **Analytics**: Media usage tracking and analytics
- **Accessibility**: Enhanced accessibility features for media content

### Extensibility
The model is designed to be easily extensible:
- Add new media types by extending `MEDIA_TYPE_CHOICES`
- Add new file extensions to the validation lists
- Extend metadata fields for specific media types
- Add custom processing logic for different media types

## Content Synchronization

The ChapterMedia model automatically integrates with the structured content system. When you add media to a chapter, it's automatically added to the structured content file with the correct position.

### Automatic Integration

When you use any of the `add_*` methods (e.g., `add_image`, `add_audio`, `add_video`, `add_document`), the media is automatically:

1. **Stored in the database** with metadata and position
2. **Added to structured content** with the correct type and ID
3. **Positioned correctly** in the content flow

### Manual Synchronization

If you need to manually sync media with structured content:

```python
# Sync any missing media items to structured content
added_count = chapter.sync_media_with_content()
print(f"Added {added_count} media items to structured content")

# Rebuild structured content to match current media order
elements_count = chapter.rebuild_structured_content_from_media()
print(f"Rebuilt content with {elements_count} elements")
```

### Admin Actions

The Django admin includes actions for content synchronization:

1. **Sync media with structured content**: Adds any missing media items to the structured content
2. **Rebuild content from media order**: Rebuilds the entire structured content to match the current media positions

### Structured Content Format

Media items are stored in structured content as:

```json
[
    {
        "type": "text",
        "content": "This is a paragraph of text."
    },
    {
        "type": "image",
        "image_id": 1,
        "caption": "An image caption"
    },
    {
        "type": "audio",
        "media_id": 2,
        "caption": "Audio narration"
    },
    {
        "type": "video",
        "media_id": 3,
        "caption": "Video content"
    }
]
```

**Note**: Images use `image_id` for backward compatibility, while other media types use `media_id`.

### Retrieving Content with Media

```python
# Get all content elements (text and media) in order
content_elements = chapter.get_paragraphs_and_media()

for element in content_elements:
    if element['type'] == 'text':
        print(f"Text: {element['content']}")
    elif element['type'] == 'image':
        if element.get('media'):
            print(f"Image: {element['media'].display_title}")
        else:
            print(f"Legacy Image: {element['image'].id}")
    else:
        print(f"{element['type'].title()}: {element['media'].display_title}")
```

## Testing

Run the test scripts to verify functionality:

```bash
# Test basic ChapterMedia functionality
python books/test_chapter_media.py

# Test content synchronization
python books/test_media_content_sync.py
```

These will create test data and demonstrate all the key features of the ChapterMedia model and content synchronization.

## Migration

To apply the database migration:

```bash
python manage.py migrate books
```

This will create the new ChapterMedia table while preserving existing ChapterImage data. 