# Generated by Django 5.1.3 on 2024-12-02 22:20

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0031_alter_item_image'),
        ('events', '0001_initial'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='event',
            unique_together={('item', 'episode_number')},
        ),
    ]
