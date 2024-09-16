# Generated by Django 5.0.2 on 2024-03-02 19:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0007_alter_season_unique_together_remove_tv_end_date_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='anime',
            name='notes',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AlterField(
            model_name='manga',
            name='notes',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AlterField(
            model_name='movie',
            name='notes',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AlterField(
            model_name='season',
            name='notes',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AlterField(
            model_name='tv',
            name='notes',
            field=models.TextField(blank=True, default=''),
        ),
    ]