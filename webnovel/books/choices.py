from django.db import models

class RatingChoices(models.TextChoices):
    EVERYONE = "E", "Everyone"
    TEEN = "T", "Teen (13+)"
    MATURE = "M", "Mature (16+)"
    ADULT = "A", "Adult (18+)"

class BookStatus(models.TextChoices):
    DRAFT = "D", "Draft"
    ONGOING = "O", "Ongoing"
    COMPLETED = "C", "Completed"
    ARCHIVED = "A", "Archived"


class MediaType(models.TextChoices):
    IMAGE = "I", "Image"
    AUDIO = "A", "Audio"
    VIDEO = "V", "Video"
    DOCUMENT = "D", "Document"
    OTHER = "O", "Other"

class ParagraphStyle(models.TextChoices):
    SINGLE_NEWLINE = "S", "Single Newline"
    DOUBLE_NEWLINE = "D", "Double Newline"
    AUTO_DETECT = "A", "Auto Detect"


class ChangeType(models.TextChoices):
    TRANSLATION = "T", "Translation"
    EDIT = "E", "Edit/Correction"
    OTHER = "O", "Other"


class ProcessingStatus(models.TextChoices):
    WAITING = "W", "Waiting"
    PROCESSING = "P", "Processing"
    COMPLETED = "C", "Completed"
    FAILED = "F", "Failed"


class ChapterStatus(models.TextChoices):
    DRAFT = "D", "Draft"
    TRANSLATING = "T", "Translating"
    SCHEDULED = "S", "Scheduled"
    PUBLISHED = "P", "Published"
    ARCHIVED = "A", "Archived"