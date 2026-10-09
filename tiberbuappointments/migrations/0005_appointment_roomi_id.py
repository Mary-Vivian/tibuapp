import uuid
from django.db import migrations, models


def fill_rooms(apps, schema_editor):
    Appointment = apps.get_model("tiberbuappointments", "Appointment")
    for a in Appointment.objects.all():
        a.room_id = uuid.uuid4()
        a.save(update_fields=["room_id"])


class Migration(migrations.Migration):
    dependencies = [
        ("tiberbuappointments", "0004_alter_patient_insurance_id_alter_patient_phone"),
    ]

    operations = [
        migrations.AddField(
            "appointment", "room_id",
            models.UUIDField(null=True, editable=False),
        ),
        migrations.RunPython(fill_rooms, migrations.RunPython.noop),
        migrations.AlterField(
            "appointment", "room_id",
            models.UUIDField(default=uuid.uuid4, unique=True, editable=False),
        ),
    ]