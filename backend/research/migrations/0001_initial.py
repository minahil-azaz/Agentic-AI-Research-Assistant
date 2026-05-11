from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import pgvector.django


class Migration(migrations.Migration):

    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunSQL("CREATE EXTENSION IF NOT EXISTS vector;"),

        migrations.CreateModel(
            name="ResearchQuery",
            fields=[
                ("id",             models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("query",          models.TextField()),
                ("report",         models.TextField(blank=True, default="")),
                ("status",         models.CharField(
                    choices=[
                        ("pending","Pending"),("planning","Planning"),("searching","Searching"),
                        ("scraping","Scraping"),("embedding","Embedding"),("writing","Writing"),
                        ("done","Done"),("error","Error"),
                    ],
                    default="pending", max_length=20,
                )),
                ("status_message", models.CharField(blank=True, default="", max_length=500)),
                ("created_at",     models.DateTimeField(auto_now_add=True)),
                ("updated_at",     models.DateTimeField(auto_now=True)),
                ("user",           models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="queries",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={"ordering": ["-created_at"]},
        ),

        migrations.CreateModel(
            name="ResearchSource",
            fields=[
                ("id",         models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("url",        models.URLField(max_length=2000)),
                ("title",      models.CharField(blank=True, max_length=500)),
                ("content",    models.TextField(blank=True)),
                ("snippet",    models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("query",      models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="sources",
                    to="research.researchquery",
                )),
            ],
        ),
        migrations.AlterUniqueTogether(
            name="researchsource",
            unique_together={("query", "url")},
        ),

        migrations.CreateModel(
            name="ResearchEmbedding",
            fields=[
                ("id",          models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("chunk_text",  models.TextField()),
                ("chunk_index", models.PositiveIntegerField(default=0)),
                ("embedding",   pgvector.django.VectorField(dimensions=384)),
                ("source",      models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="embeddings",
                    to="research.researchsource",
                )),
            ],
        ),
    ]
