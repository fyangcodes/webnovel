from django.core.validators import RegexValidator

# Custom validator for Unicode slugs
unicode_slug_validator = RegexValidator(
    regex=r'^[^\s/\\?%*:|"<>]+$',
    message='Slug can contain any characters except whitespace and /\\?%*:|"<>',
    code="invalid_slug",
)