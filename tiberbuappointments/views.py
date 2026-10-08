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
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.throttling import AnonRateThrottle
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests

from .emailing import send_email

from .models import Appointment, Doctor, Patient

class ResetThrottle(AnonRateThrottle):
    scope = "password_reset"


class AuthThrottle(AnonRateThrottle):
    scope = "auth"


# ---------- Auth ----------

@api_view(['GET'])
def csrf_token_view(request):
    return JsonResponse({'csrfToken': get_token(request)})


@api_view(['POST'])
@throttle_classes([AuthThrottle])
def simple_login(request):
    username = (request.data.get('username') or '').strip()
    if "@" in username:
        match = User.objects.filter(email__iexact=username).first()
        if match:
            username = match.username
    user = authenticate(request, username=username, password=request.data.get('password'))
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
    username = (request.data.get("username") or "").strip()
    email = (request.data.get("email") or "").strip().lower()
    password = request.data.get("password")
    phone = request.data.get("phone")
    insurance_id = request.data.get("insurance_id")

    if not all([username, email, password, phone, insurance_id]):
        return Response({"error": "Missing required fields"}, status=400)
    try:
        validate_email(email)
    except ValidationError:
        return Response({"error": "Enter a valid email address"}, status=400)
    if User.objects.filter(username__iexact=username).exists():
        return Response({"error": "Username already exists"}, status=400)
    if User.objects.filter(email__iexact=email).exists():
        return Response({"error": "An account with this email already exists"}, status=400)
    if Patient.objects.filter(insurance_id=insurance_id).exists():
        return Response({"error": "This insurance ID is already registered"}, status=400)
    try:
        validate_password(password)
    except ValidationError as e:
        return Response({"error": " ".join(e.messages)}, status=400)

    with transaction.atomic():
        user = User.objects.create_user(username=username, email=email, password=password)
        patient = Patient.objects.create(user=user, phone=phone, insurance_id=insurance_id)

    return Response({"message": "Patient registered successfully", "id": patient.id}, status=201)


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
    ).exclude(status="Cancelled").exists():
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

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_appointment_status(request, appointment_id):
    new_status = request.data.get("status")
    if new_status not in ("Cancelled", "Completed"):
        return Response({"error": "Invalid status"}, status=400)

    appt = Appointment.objects.select_related("patient", "doctor").filter(id=appointment_id).first()
    if not appt:
        return Response({"error": "Appointment not found"}, status=404)

    user = request.user
    is_patient = appt.patient.user_id == user.id
    is_doctor = appt.doctor.user_id == user.id
    allowed = (is_patient or is_doctor or user.is_staff) if new_status == "Cancelled" \
        else (is_doctor or user.is_staff)
    if not allowed:
        return Response({"error": "Not allowed"}, status=403)
    if appt.status != "Scheduled":
        return Response({"error": f"Appointment is already {appt.status.lower()}"}, status=400)

    appt.status = new_status
    appt.save()
    return Response({"message": f"Appointment {new_status.lower()}"})

@api_view(['POST'])
@throttle_classes([ResetThrottle])
def forgot_password(request):
    email = (request.data.get("email") or "").strip().lower()
    user = User.objects.filter(email__iexact=email, is_active=True).first() if email else None

    if user:
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        base = getattr(settings, "FRONTEND_URL", None) or "http://localhost:3000"
        link = f"{base}/reset-password?uid={uid}&token={token}"
        send_email(
            user.email,
            "Reset your Tibu Health password",
            f"Hello {user.username},\n\n"
            f"Use this link to choose a new password (valid for 1 hour):\n{link}\n\n"
            "If you didn't ask for this, you can ignore this email.",
        )

    # Same answer whether or not the account exists, so nobody can probe for emails
    return Response({"message": "If an account exists for that email, a reset link has been sent."})


@api_view(['POST'])
@throttle_classes([ResetThrottle])
def reset_password(request):
    uid = request.data.get("uid") or ""
    token = request.data.get("token") or ""
    password = request.data.get("password") or ""

    try:
        user = User.objects.get(pk=force_str(urlsafe_base64_decode(uid)))
    except (ValueError, TypeError, OverflowError, User.DoesNotExist):
        user = None

    if user is None or not default_token_generator.check_token(user, token):
        return Response({"error": "This reset link is invalid or has expired."}, status=400)
    try:
        validate_password(password, user)
    except ValidationError as e:
        return Response({"error": " ".join(e.messages)}, status=400)

    user.set_password(password)
    user.save()  # this also invalidates the link, so it only works once
    return Response({"message": "Password updated"})


@api_view(['POST'])
@throttle_classes([AuthThrottle])
def google_login(request):
    credential = request.data.get("credential")
    if not credential or not settings.GOOGLE_CLIENT_ID:
        return Response({"error": "Google sign-in is not available"}, status=400)

    try:
        # Checks Google's signature, the expiry, and that the token was issued for YOUR client ID
        info = google_id_token.verify_oauth2_token(
            credential, google_requests.Request(), settings.GOOGLE_CLIENT_ID
        )
    except ValueError:
        return Response({"error": "Google sign-in failed. Please try again."}, status=400)

    email = (info.get("email") or "").lower()
    if not email or not info.get("email_verified"):
        return Response({"error": "Your Google email is not verified"}, status=400)

    user = User.objects.filter(email__iexact=email).first()
    if user is None:
        base = (email.split("@")[0] or "user")[:30]
        username, n = base, 1
        while User.objects.filter(username__iexact=username).exists():
            n += 1
            username = f"{base}{n}"
        with transaction.atomic():
            user = User(
                username=username,
                email=email,
                first_name=(info.get("given_name") or "")[:150],
                last_name=(info.get("family_name") or "")[:150],
            )
            user.set_unusable_password()
            user.save()
            Patient.objects.create(user=user)  # Google sign-ups are always patients
    elif user.is_staff or user.is_superuser:
        return Response({"error": "Admin accounts must sign in with a password"}, status=403)
    elif not user.is_active:
        return Response({"error": "This account is disabled"}, status=403)

    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    return Response({"message": "Login successful"})