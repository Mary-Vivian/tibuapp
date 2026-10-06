from django.urls import path
from .views import (
    register_patient, list_doctors, book_appointment, register_doctor,
    simple_login, simple_logout, user_profile, csrf_token_view, my_appointments, update_appointment_status
)

urlpatterns = [
    path('login/', simple_login),
    path('logout/', simple_logout),
    path('patients/register/', register_patient),
    path('doctors/', list_doctors),
    path('appointments/book/', book_appointment),
    path('appointments/mine/', my_appointments),
    path('doctors/register/', register_doctor),
    path('profile/', user_profile),
    path('csrf/', csrf_token_view, name='csrf_token'),
    path('appointments/<int:appointment_id>/status/', update_appointment_status),
]
