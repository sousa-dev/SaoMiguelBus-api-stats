# Generated by Django 3.0.14 on 2023-07-17 00:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0021_auto_20230715_2150'),
    ]

    operations = [
        migrations.AlterField(
            model_name='stat',
            name='timestamp',
            field=models.DateTimeField(),
        ),
    ]