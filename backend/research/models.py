from django.contrib.auth.models import User
from django.db import models
from pgvector.django import VectorField


class ResearchQuery(models.Model):
    STATUS_CHOICES = [
        ("pending",   "Pending"),
        ("planning",  "Planning"),
        ("searching", "Searching"),
        ("scraping",  "Scraping"),
        ("embedding", "Embedding"),
        ("writing",   "Writing"),
        ("done",      "Done"),
        ("error",     "Error"),
    ]

    user           = models.ForeignKey(User, on_delete=models.CASCADE, related_name="queries", null=True, blank=True)
    query          = models.TextField()
    report         = models.TextField(blank=True, default="")
    status         = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    status_message = models.CharField(max_length=500, blank=True, default="")
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.status}] {self.query[:80]}"


class ResearchSource(models.Model):
    query      = models.ForeignKey(ResearchQuery, on_delete=models.CASCADE, related_name="sources")
    url        = models.URLField(max_length=2000)
    title      = models.CharField(max_length=500, blank=True)
    content    = models.TextField(blank=True)
    snippet    = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("query", "url")

    def __str__(self):
        return self.title or self.url[:60]


class ResearchEmbedding(models.Model):
    source      = models.ForeignKey(ResearchSource, on_delete=models.CASCADE, related_name="embeddings")
    chunk_text  = models.TextField()
    chunk_index = models.PositiveIntegerField(default=0)
    embedding   = VectorField(dimensions=384)

    def __str__(self):
        return f"Chunk {self.chunk_index} — {self.source}"
