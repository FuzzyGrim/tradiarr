# Generated by Django 5.1 on 2024-09-19 19:51

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0023_alter_item_source'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='item',
            unique_together={('media_id', 'source', 'media_type', 'season_number', 'episode_number')},
        ),
    ]
