# Generated by Django 3.0.14 on 2022-10-02 13:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0006_route_disabled'),
    ]

    operations = [
        migrations.CreateModel(
            name='Stat',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('request', models.CharField(max_length=100)),
                ('origin', models.CharField(max_length=100)),
                ('destination', models.CharField(max_length=100)),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
            ],
        ),
    ]
