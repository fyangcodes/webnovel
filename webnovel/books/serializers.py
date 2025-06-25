from rest_framework import serializers

from .models import Book, Chapter


class BookSerializer(serializers.ModelSerializer):
    processing_duration = serializers.ReadOnlyField()
    is_processing = serializers.ReadOnlyField()
    file_extension = serializers.ReadOnlyField()

    class Meta:
        model = Book
        fields = [
            "id",
            "title",
            "author",
            "original_language",
            "isbn",
            "description",
            "status",
            "processing_progress",
            "error_message",
            "total_chapters",
            "estimated_words",
            "upload_date",
            "processing_started_at",
            "processing_completed_at",
            "processing_duration",
            "is_processing",
            "file_size",
            "file_extension",
        ]
        read_only_fields = [
            "id",
            "status",
            "processing_progress",
            "error_message",
            "total_chapters",
            "estimated_words",
            "upload_date",
            "processing_started_at",
            "processing_completed_at",
            "file_size",
        ]


class BookCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Book
        fields = [
            "title",
            "author",
            "original_language",
            "isbn",
            "description",
            "uploaded_file",
        ]

    def create(self, validated_data):
        validated_data["owner"] = self.context["request"].user
        return super().create(validated_data)


class ChapterSerializer(serializers.ModelSerializer):
    has_translations = serializers.ReadOnlyField()

    class Meta:
        model = Chapter
        fields = [
            "id",
            "chapter_number",
            "title",
            "excerpt",
            "abstract",
            "key_terms",
            "word_count",
            "char_count",
            "processing_status",
            "has_translations",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "word_count",
            "char_count",
            "created_at",
            "updated_at",
        ]


class ChapterDetailSerializer(ChapterSerializer):
    """Serializer with full text content for detail view"""

    class Meta(ChapterSerializer.Meta):
        fields = ChapterSerializer.Meta.fields + ["original_text"]
