from django.db import models

class RatingChoices(models.TextChoices):
    EVERYONE = "Everyone", "Everyone"
    TEEN = "Teen", "Teen (13+)"
    MATURE = "Mature", "Mature (16+)"
    ADULT = "Adult", "Adult (18+)"

class BookStatus(models.TextChoices):
    DRAFT = "Draft", "Draft"
    ONGOING = "Ongoing", "Ongoing"
    COMPLETED = "Completed", "Completed"
    ARCHIVED = "Archived", "Archived"


class MediaType(models.TextChoices):
    IMAGE = "Image", "Image"
    AUDIO = "Audio", "Audio"
    VIDEO = "Video", "Video"
    DOCUMENT = "Document", "Document"
    OTHER = "Other", "Other"

class ParagraphStyle(models.TextChoices):
    SINGLE_NEWLINE = "Single Newline", "Single Newline"
    DOUBLE_NEWLINE = "Double Newline", "Double Newline"
    AUTO_DETECT = "Auto Detect", "Auto Detect"


class ChangeType(models.TextChoices):
    TRANSLATION = "Translation", "Translation"
    EDIT = "Edit", "Edit/Correction"
    OTHER = "Other", "Other"


class ProcessingStatus(models.TextChoices):
    PENDING = "Pending", "Pending"
    PROCESSING = "Processing", "Processing"
    COMPLETED = "Completed", "Completed"
    FAILED = "Failed", "Failed"


class ChapterStatus(models.TextChoices):
    DRAFT = "Draft", "Draft"
    TRANSLATING = "Translating", "Translating"
    SCHEDULED = "Scheduled", "Scheduled"
    PUBLISHED = "Published", "Published"
    ARCHIVED = "Archived", "Archived"