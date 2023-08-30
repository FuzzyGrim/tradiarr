# Generated by Django 4.2 on 2023-08-25 20:58

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="last_search_type",
            field=models.CharField(
                choices=[
                    ("tv", "tv"),
                    ("movie", "movie"),
                    ("anime", "anime"),
                    ("manga", "manga"),
                ],
                default="tv",
                max_length=10,
            ),
        ),
    ]
