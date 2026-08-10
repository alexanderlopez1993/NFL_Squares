from django.db import migrations, models


class Migration(migrations.Migration):
    """Store ESPN's exact status for completed-period payout gates."""

    dependencies = [
        ('games', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='nflgame',
            name='espn_status',
            field=models.CharField(blank=True, max_length=40),
        ),
    ]
