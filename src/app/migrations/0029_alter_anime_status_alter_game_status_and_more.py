# Generated by Django 5.1.2 on 2024-11-25 18:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0028_alter_item_unique_together_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='anime',
            name='status',
            field=models.CharField(choices=[('In progress', 'In Progress'), ('Completed', 'Completed'), ('Repeating', 'Repeating'), ('Planning', 'Planning'), ('Paused', 'Paused'), ('Dropped', 'Dropped')], default='Completed', max_length=20),
        ),
        migrations.AlterField(
            model_name='game',
            name='status',
            field=models.CharField(choices=[('In progress', 'In Progress'), ('Completed', 'Completed'), ('Repeating', 'Repeating'), ('Planning', 'Planning'), ('Paused', 'Paused'), ('Dropped', 'Dropped')], default='Completed', max_length=20),
        ),
        migrations.AlterField(
            model_name='historicalanime',
            name='status',
            field=models.CharField(choices=[('In progress', 'In Progress'), ('Completed', 'Completed'), ('Repeating', 'Repeating'), ('Planning', 'Planning'), ('Paused', 'Paused'), ('Dropped', 'Dropped')], default='Completed', max_length=20),
        ),
        migrations.AlterField(
            model_name='historicalgame',
            name='status',
            field=models.CharField(choices=[('In progress', 'In Progress'), ('Completed', 'Completed'), ('Repeating', 'Repeating'), ('Planning', 'Planning'), ('Paused', 'Paused'), ('Dropped', 'Dropped')], default='Completed', max_length=20),
        ),
        migrations.AlterField(
            model_name='historicalmanga',
            name='status',
            field=models.CharField(choices=[('In progress', 'In Progress'), ('Completed', 'Completed'), ('Repeating', 'Repeating'), ('Planning', 'Planning'), ('Paused', 'Paused'), ('Dropped', 'Dropped')], default='Completed', max_length=20),
        ),
        migrations.AlterField(
            model_name='historicalmovie',
            name='status',
            field=models.CharField(choices=[('In progress', 'In Progress'), ('Completed', 'Completed'), ('Repeating', 'Repeating'), ('Planning', 'Planning'), ('Paused', 'Paused'), ('Dropped', 'Dropped')], default='Completed', max_length=20),
        ),
        migrations.AlterField(
            model_name='historicalseason',
            name='status',
            field=models.CharField(choices=[('In progress', 'In Progress'), ('Completed', 'Completed'), ('Repeating', 'Repeating'), ('Planning', 'Planning'), ('Paused', 'Paused'), ('Dropped', 'Dropped')], default='Completed', max_length=20),
        ),
        migrations.AlterField(
            model_name='historicaltv',
            name='status',
            field=models.CharField(choices=[('In progress', 'In Progress'), ('Completed', 'Completed'), ('Repeating', 'Repeating'), ('Planning', 'Planning'), ('Paused', 'Paused'), ('Dropped', 'Dropped')], default='Completed', max_length=20),
        ),
        migrations.AlterField(
            model_name='item',
            name='source',
            field=models.CharField(choices=[('tmdb', 'The Movie Database'), ('mal', 'MyAnimeList'), ('mangaupdates', 'MangaUpdates'), ('igdb', 'Internet Game Database'), ('manual', 'Manual')], max_length=20),
        ),
        migrations.AlterField(
            model_name='manga',
            name='status',
            field=models.CharField(choices=[('In progress', 'In Progress'), ('Completed', 'Completed'), ('Repeating', 'Repeating'), ('Planning', 'Planning'), ('Paused', 'Paused'), ('Dropped', 'Dropped')], default='Completed', max_length=20),
        ),
        migrations.AlterField(
            model_name='movie',
            name='status',
            field=models.CharField(choices=[('In progress', 'In Progress'), ('Completed', 'Completed'), ('Repeating', 'Repeating'), ('Planning', 'Planning'), ('Paused', 'Paused'), ('Dropped', 'Dropped')], default='Completed', max_length=20),
        ),
        migrations.AlterField(
            model_name='season',
            name='status',
            field=models.CharField(choices=[('In progress', 'In Progress'), ('Completed', 'Completed'), ('Repeating', 'Repeating'), ('Planning', 'Planning'), ('Paused', 'Paused'), ('Dropped', 'Dropped')], default='Completed', max_length=20),
        ),
        migrations.AlterField(
            model_name='tv',
            name='status',
            field=models.CharField(choices=[('In progress', 'In Progress'), ('Completed', 'Completed'), ('Repeating', 'Repeating'), ('Planning', 'Planning'), ('Paused', 'Paused'), ('Dropped', 'Dropped')], default='Completed', max_length=20),
        ),
    ]
