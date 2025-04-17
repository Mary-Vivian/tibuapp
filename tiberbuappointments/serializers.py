from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Patient, Doctor, Appointment


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email']


class PatientSerializer(serializers.ModelSerializer):
    user = UserSerializer()  

    class Meta:
        model = Patient
        fields = ['id', 'user', 'phone', 'insurance_id']

class DoctorSerializer(serializers.ModelSerializer):
    user = UserSerializer()

    class Meta:
        model = Doctor
        fields = ['id', 'user', 'specialization', 'available_times']


class AppointmentSerializer(serializers.ModelSerializer):
    patient = PatientSerializer()
    doctor = DoctorSerializer()

    class Meta:
        model = Appointment
        fields = ['id', 'patient', 'doctor', 'appointment_date', 'status']
