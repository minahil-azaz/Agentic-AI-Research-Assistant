from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("research", "0001_initial"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="researchsource",
            options={"ordering": ["created_at", "id"]},
        ),
    ]
