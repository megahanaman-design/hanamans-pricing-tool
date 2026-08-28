from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("profit_web", "0001_monthly"),
    ]

    operations = [
        migrations.AddField(
            model_name="ebayorderline",
            name="shipping_override_yen",
            field=models.DecimalField(blank=True, decimal_places=0, max_digits=14, null=True),
        ),
    ]
