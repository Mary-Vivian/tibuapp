from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth.models import User
from .models import Doctor, Patient, Appointment
from datetime import datetime

class APITestCase(TestCase):
    def setUp(self):
        """Set up test data before each test"""
        self.client = APIClient()

        # Create doctor user and doctor profile
        self.doctor_user = User.objects.create_user(username="dr_smith", password="password123")
        self.doctor = Doctor.objects.create(
            user=self.doctor_user,
            specialization="Cardiology",
            available_times=[]
        )

        # Create patient user and patient profile
        self.patient_user = User.objects.create_user(username="john_doe", password="password123")
        self.patient = Patient.objects.create(
            user=self.patient_user,
            phone="1234567890",
            insurance_id="INS123456"
        )

        # Authenticate as doctor
        self.client.force_authenticate(user=self.doctor_user)


    def test_register_patient(self):
        """Test patient registration"""
        data = {"name": "Jane Doe", "contact": "0987654321"}
        response = self.client.post("/patients/register/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_list_doctors(self):
        """Test retrieving the doctor list"""
        response = self.client.get("/doctors/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_book_appointment(self):
        """Test appointment booking"""
        data = {
            "patient_id": self.patient.id,
            "doctor_id": self.doctor.id,
            "appointment_date": datetime.now().strftime("%Y-%m-%dT%H:%M"),
        }
        response = self.client.post("/appointments/book/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_double_booking_prevention(self):
        """Test preventing double booking"""
        data = {
            "patient_id": self.patient.id,
            "doctor_id": self.doctor.id,
            "appointment_date": datetime.now().strftime("%Y-%m-%dT%H:%M"),
        }
     
        self.client.post("/appointments/book/", data, format="json")
        
        response = self.client.post("/appointments/book/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Doctor is not available", response.data["error"])
