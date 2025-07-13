# Markdown Support in WebNovel

This document explains how to use Markdown formatting in your WebNovel project.

## Overview

The WebNovel project now supports Markdown formatting for various text fields, allowing you to create rich, formatted content using simple Markdown syntax.

## Supported Fields

The following fields now support Markdown formatting:

### Chapter Content
- **Legacy Content**: The main chapter content field
- **Structured Content**: Text elements within structured content
- **Abstract**: AI-generated chapter summaries
- **Media Captions**: Captions for images, audio, video, and documents

### Book Information
- **Book Description**: Book descriptions and summaries
- **Author Description**: Author biographies and information

### User Profiles
- **User Bio**: User profile descriptions
- **Author Bio**: Author-specific biographies

### Collaboration
- **Collaboration Notes**: Notes on book collaborations
- **Change Log Notes**: Notes in change tracking

## How to Use

### In Templates

The markdown filter is available in templates using the `books_extras` template tag library:

```django
{% load books_extras %}

<!-- Basic usage -->
{{ chapter.content|markdown }}

<!-- For abstracts -->
{{ chapter.abstract|markdown }}

<!-- For media captions -->
{{ element.caption|markdown }}
```

### In Python Code

You can also use the markdown filter programmatically:

```python
from books.templatetags.books_extras import markdown_format

# Convert markdown to HTML
html_content = markdown_format("**Bold text** and *italic text*")
```

## Markdown Features Supported

The markdown implementation supports the following features:

### Text Formatting
- **Bold**: `**bold text**` or `__bold text__`
- **Italic**: `*italic text*` or `_italic text_`
- **Strikethrough**: `~~strikethrough text~~`

### Headers
- `# Header 1`
- `## Header 2`
- `### Header 3`
- `#### Header 4`
- `##### Header 5`
- `###### Header 6`

### Lists
- **Unordered lists**:
  ```markdown
  - Item 1
  - Item 2
    - Subitem 2.1
    - Subitem 2.2
  ```

- **Ordered lists**:
  ```markdown
  1. First item
  2. Second item
  3. Third item
  ```

### Links and Images
- **Links**: `[Link text](https://example.com)`
- **Images**: `![Alt text](image.jpg)`

### Code
- **Inline code**: `` `code` ``
- **Code blocks**:
  ```markdown
  ```python
  def hello_world():
      print("Hello, World!")
  ```
  ```

### Blockquotes
```markdown
> This is a blockquote
> It can span multiple lines
```

### Tables
```markdown
| Header 1 | Header 2 | Header 3 |
|----------|----------|----------|
| Cell 1   | Cell 2   | Cell 3   |
| Cell 4   | Cell 5   | Cell 6   |
```

### Horizontal Rules
```markdown
---
```

## Security

The markdown implementation includes security features:

- **HTML Sanitization**: All HTML is sanitized using the `bleach` library
- **Allowed Tags**: Only safe HTML tags are allowed
- **XSS Protection**: Prevents cross-site scripting attacks

## Examples

### Chapter Content Example
```markdown
# Chapter 1: The Beginning

This is the **first chapter** of our story. It introduces the main character and sets up the plot.

## Main Character

The protagonist, *John Doe*, is a young adventurer who dreams of exploring the world.

### His Journey

John's journey begins with:
1. Leaving his hometown
2. Meeting new friends
3. Facing his first challenge

> "Every journey begins with a single step." - Ancient Proverb

![John's hometown](town.jpg)

For more information, visit [our website](https://example.com).
```

### Author Bio Example
```markdown
## About the Author

**Jane Smith** is an award-winning author who specializes in fantasy and science fiction.

### Published Works
- *The Dragon's Call* (2020)
- *Stars Beyond* (2021)
- *The Last Kingdom* (2022)

### Awards
- Best Fantasy Novel 2021
- Reader's Choice Award 2022

> "I believe every story has the power to change lives." - Jane Smith
```

## Migration

If you have existing content that you want to convert to Markdown format, you can use the provided management command:

```bash
# Preview what would be migrated (dry run)
python manage.py migrate_to_markdown --dry-run

# Actually migrate the content
python manage.py migrate_to_markdown
```

This command will:
1. Detect existing plain text content
2. Convert it to basic Markdown format
3. Preserve existing Markdown content
4. Update all relevant fields

## Best Practices

1. **Use Markdown Consistently**: Choose a style guide and stick to it
2. **Keep It Simple**: Don't over-format your content
3. **Test Your Content**: Preview your Markdown before publishing
4. **Use Descriptive Links**: Make link text meaningful
5. **Optimize Images**: Use appropriate alt text for accessibility

## Troubleshooting

### Common Issues

1. **Markdown not rendering**: Make sure you're using the `|markdown` filter in templates
2. **HTML not showing**: Check that the HTML tags are in the allowed list
3. **Links not working**: Verify the URL format is correct

### Getting Help

If you encounter issues with Markdown formatting:
1. Check the template syntax
2. Verify the markdown syntax is correct
3. Test with simple examples first
4. Check the browser console for errors

## Future Enhancements

Planned improvements to the Markdown system:
- Syntax highlighting for code blocks
- Custom CSS styling options
- Advanced table formatting
- Math equation support
- Diagram and chart support 