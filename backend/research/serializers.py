from rest_framework import serializers
from .models import ResearchQuery, ResearchSource


class ResearchSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ResearchSource
        fields = ["id", "url", "title", "snippet", "created_at"]


class ResearchQuerySerializer(serializers.ModelSerializer):
    sources = ResearchSourceSerializer(many=True, read_only=True)

    class Meta:
        model  = ResearchQuery
        fields = ["id", "query", "report", "status", "status_message", "sources", "created_at", "updated_at"]
        read_only_fields = ["report", "status", "status_message", "sources", "created_at", "updated_at"]


class ResearchQueryCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ResearchQuery
        fields = ["query"]


class ResearchQueryListSerializer(serializers.ModelSerializer):
    """Lightweight shape for the history sidebar (no report body or sources)."""
    class Meta:
        model  = ResearchQuery
        fields = ["id", "query", "status", "status_message", "created_at", "updated_at"]
