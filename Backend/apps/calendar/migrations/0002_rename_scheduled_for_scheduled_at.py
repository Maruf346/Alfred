from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("calendar", "0001_initial"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="scheduledplan",
            name="calendar_sc_user_id_15286d_idx",
        ),
        migrations.RemoveIndex(
            model_name="scheduledplan",
            name="calendar_sc_reminde_ebdbbf_idx",
        ),
        migrations.RenameField(
            model_name="scheduledplan",
            old_name="scheduled_for",
            new_name="scheduled_at",
        ),
        migrations.AlterModelOptions(
            name="scheduledplan",
            options={"ordering": ["scheduled_at"]},
        ),
        migrations.AddIndex(
            model_name="scheduledplan",
            index=models.Index(
                fields=["user", "scheduled_at"],
                name="calendar_sc_user_id_e1967a_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="scheduledplan",
            index=models.Index(
                fields=["reminder_sent_at", "scheduled_at"],
                name="calendar_sc_reminde_b1c7b1_idx",
            ),
        ),
    ]
