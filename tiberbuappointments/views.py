from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.db import transaction
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from .models import Appointment, Doctor, Patient


# ---------- Auth ----------

@api_view(['GET'])
def csrf_token_view(request):
    return JsonResponse({'csrfToken': get_token(request)})


@api_view(['POST'])
def simple_login(request):
    user = authenticate(
        request,
        username=request.data.get('username'),
        password=request.data.get('password'),
    )
    if user is None:
        return Response({'error': 'Invalid credentials'}, status=400)
    login(request, user)
    return Response({'message': 'Login successful'})


@api_view(['POST'])
def simple_logout(request):
    logout(request)
    return Response({'message': 'Logged out successfully'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_profile(request):
    user = request.user
    patient = Patient.objects.filter(user=user).first()
    doctor = Doctor.objects.filter(user=user).first()
    role = (
        "admin" if user.is_staff
        else "doctor" if doctor
        else "patient" if patient
        else "user"
    )
    return Response({
        "username": user.username,
        "role": role,
        "patient_id": patient.id if patient else None,
        "doctor_id": doctor.id if doctor else None,
    })


# ---------- Registration ----------

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

    with transaction.atomic():
        user = User.objects.create_user(username=username, password=password)
        patient = Patient.objects.create(
            user=user, phone=phone, insurance_id=insurance_id
        )

    return Response(
        {"message": "Patient registered successfully", "id": patient.id},
        status=201,
    )


@api_view(['POST'])
@permission_classes([IsAdminUser])
def register_doctor(request):
    username = request.data.get("username")
    password = request.data.get("password")
    specialization = request.data.get("specialization")

    if not all([username, password, specialization]):
        return Response({"error": "Missing required fields"}, status=400)
    if User.objects.filter(username=username).exists():
        return Response({"error": "Username already exists"}, status=400)

    with transaction.atomic():  # no orphan user if the Doctor insert fails
        user = User.objects.create_user(username=username, password=password)
        doctor = Doctor.objects.create(user=user, specialization=specialization)

    return Response(
        {"message": "Doctor registered successfully", "id": doctor.id},
        status=201,
    )


# ---------- Doctors ----------

@api_view(['GET'])
def list_doctors(request):
    doctors = Doctor.objects.all().values("id", "user__username", "specialization")
    return Response(list(doctors), status=200)


# ---------- Appointments ----------

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def book_appointment(request):
    # The patient comes from the logged-in user, never from the request
    patient = Patient.objects.filter(user=request.user).first()
    if not patient:
        return Response({"error": "Only patients can book appointments"}, status=403)

    doctor_id = request.data.get("doctor_id")
    date_str = request.data.get("appointment_date")
    if not doctor_id or not date_str:
        return Response({"error": "Missing required fields"}, status=400)

    try:
        doctor_id = int(doctor_id)
    except (TypeError, ValueError):
        return Response({"error": "Invalid doctor"}, status=400)

    try:
        appointment_date = parse_datetime(str(date_str))
    except ValueError:
        appointment_date = None
    if not appointment_date:
        return Response({"error": "Invalid date format"}, status=400)
    if timezone.is_naive(appointment_date):
        appointment_date = timezone.make_aware(appointment_date)
    if appointment_date < timezone.now():
        return Response({"error": "Appointment must be in the future"}, status=400)

    if not Doctor.objects.filter(id=doctor_id).exists():
        return Response({"error": "Doctor not found"}, status=404)
    if Appointment.objects.filter(
        doctor_id=doctor_id, appointment_date=appointment_date
    ).exists():
        return Response({"error": "Doctor is not available at this time"}, status=400)

    appointment = Appointment.objects.create(
        patient=patient,
        doctor_id=doctor_id,
        appointment_date=appointment_date,
        status="Scheduled",
    )
    return Response(
        {"message": "Appointment booked successfully", "id": appointment.id},
        status=201,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_appointments(request):
    qs = Appointment.objects.all()
    patient = Patient.objects.filter(user=request.user).first()
    doctor = Doctor.objects.filter(user=request.user).first()

    if doctor:
        qs = qs.filter(doctor=doctor)
    elif patient:
        qs = qs.filter(patient=patient)
    elif not request.user.is_staff:
        qs = qs.none()

    data = qs.order_by("appointment_date").values(
        "id", "appointment_date", "status",
        "doctor__user__username", "patient__user__username",
    )
    return Response(list(data))