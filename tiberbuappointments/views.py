from django.middleware.csrf import get_token
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from .models import Doctor, Patient, Appointment
from django.utils.dateparse import parse_datetime
from datetime import datetime
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.http import JsonResponse
import json


@csrf_protect
@api_view(['GET'])
def csrf_token_view(request):
    token = get_token(request) 
    return JsonResponse({'csrfToken': token})


@csrf_exempt
@api_view(['POST'])
def simple_login(request):
    username = request.data.get('username')
    password = request.data.get('password')
    user = authenticate(request, username=username, password=password)
    if user is not None:
        login(request, user)
        return Response({'message': 'Login successful'})
    else:
        return Response({'error': 'Invalid credentials'}, status=400)


@api_view(['POST'])
def simple_logout(request):
    logout(request)
    return Response({'message': 'Logged out successfully'})


# Register Patient View
@csrf_exempt
@api_view(['POST'])
def register_patient(request):
    username = request.data.get("username")
    password = request.data.get("password")
    phone = request.data.get("phone")
    insurance_id = request.data.get("insurance_id")

    if not all([username, password, phone, insurance_id]):
        return Response({"error": "Missing required fields"}, status=400)

    if User.objects.filter(username=username).exists():
        return Response({"error": "Username already exists"}, status=400)

    user = User.objects.create_user(username=username, password=password)
    patient = Patient.objects.create(user=user, phone=phone, insurance_id=insurance_id)

    return Response({"message": "Patient registered successfully", "id": patient.id}, status=201)


# List Doctors View
@api_view(['GET'])
def list_doctors(request):
    doctors = Doctor.objects.all().values("id", "user__username", "specialization")
    return Response(list(doctors), status=200)


# Book Appointment View
@csrf_exempt
@api_view(['POST'])
def book_appointment(request):
    patient_id = request.data.get("patient_id")
    doctor_id = request.data.get("doctor_id")
    appointment_date_str = request.data.get("appointment_date")

    if not patient_id or not doctor_id or not appointment_date_str:
        return Response({"error": "Missing required fields"}, status=400)

    try:
        appointment_date = parse_datetime(appointment_date_str)
        if not appointment_date:
            raise ValueError("Invalid format")
    except ValueError:
        return Response({"error": "Invalid date format"}, status=400)

    if Appointment.objects.filter(doctor_id=doctor_id, appointment_date=appointment_date).exists():
        return Response({"error": "Doctor is not available at this time"}, status=400)

    appointment = Appointment.objects.create(
        patient_id=patient_id,
        doctor_id=doctor_id,
        appointment_date=appointment_date,
        status="Scheduled"
    )

    return Response({"message": "Appointment booked successfully", "id": appointment.id}, status=201)


# Register Doctor View
@csrf_exempt
@api_view(['POST'])
def register_doctor(request):
    try:
        data = json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError as e:
        return Response({"error": f"Invalid JSON: {str(e)}"}, status=400)

    username = data.get("username")
    password = data.get("password")
    specialization = data.get("specialization")

    if not username or not password or not specialization:
        return Response({"error": "Missing required fields"}, status=400)

    user = User.objects.create_user(username=username, password=password)
    doctor = Doctor.objects.create(user=user, specialization=specialization)

    return Response({"message": "Doctor registered successfully", "id": doctor.id}, status=201)


@api_view(['GET'])
def user_profile(request):
    if not request.user.is_authenticated:
        return Response({"error": "Not authenticated"}, status=401)

    return Response({
        "username": request.user.username,
        "email": request.user.email,
    })
