from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('queueapp', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='token',
            name='started_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='token',
            name='completed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
