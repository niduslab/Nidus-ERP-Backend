# backend/authentication/urls.py

from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views


app_name = 'authentication'

urlpatterns = [
    # ── Registration & email verification ──
    path('register/', views.RegisterView.as_view(), name='register'),
    path('verify-email/', views.VerifyEmailView.as_view(), name='verify-email'),
    path('resend-otp/', views.ResendOTPView.as_view(), name='resend-otp'),

    # ── Session management ──
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),

    # ── Profile ──
    path('profile/', views.ProfileView.as_view(), name='profile'),

    # ── Password reset (Phase 2) ──
    # Step 1: user requests an OTP to their email.
    path('forgot-password/', views.ForgotPasswordView.as_view(), name='forgot-password'),
    # Step 2: user submits OTP + new password.
    path('reset-password/', views.ResetPasswordView.as_view(), name='reset-password'),
]