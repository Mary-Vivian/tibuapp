import uuid
from django.db import models
from django.contrib.auth.models import User

class Patient(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone = models.CharField(max_length=15, blank=True, default="")
    insurance_id = models.CharField(max_length=50, unique=True, null=True, blank=True)

class Doctor(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    specialization = models.CharField(max_length=100)
    available_times = models.JSONField(default=list)
 

class Appointment(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE)
    appointment_date = models.DateTimeField()
    room_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    status = models.CharField(
        max_length=20,
        choices=[("Scheduled", "Scheduled"), ("Completed", "Completed"), ("Cancelled", "Cancelled")],  
        
    )


    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["doctor", "appointment_date"],
                condition=~models.Q(status="Cancelled"),
                name="unique_active_slot",
            )
        ]