# backend/authentication/views.py

import secrets                                   # Cryptographically secure OTP (replaces random.randint)
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from .serializers import (
    RegisterSerializer,
    VerifyEmailSerializer,
    ResendOTPSerializer,
    LoginSerializer,
    UserProfileSerializer,
)


User = get_user_model()


def generate_otp():
    return str(secrets.randbelow(900000) + 100000)


class RegisterView(APIView):

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                {
                    'success': False,
                    'message': 'Registration failed. Please check your input.',
                    'errors': serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = serializer.save()

        otp_code = generate_otp()
        user.email_verification_code = otp_code
        user.email_verification_code_expires = (
            timezone.now() + timedelta(minutes=settings.OTP_EXPIRY_MINUTES)
        )
        user.save(update_fields=[
            'email_verification_code',
            'email_verification_code_expires',
        ])

        # CHANGE: Uses centralized email service instead of raw send_mail
        from nidus_erp.email_service import send_verification_email
        send_verification_email(user=user, otp_code=otp_code)

        return Response(
            {
                'success': True,
                'message': f'Registration successful! A verification code has been sent to {user.email}.',
                'data': {
                    'user_id': str(user.id),
                    'email': user.email,
                },
            },
            status=status.HTTP_201_CREATED,
        )


class VerifyEmailView(APIView):

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = VerifyEmailSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                {
                    'success': False,
                    'message': 'Invalid input.',
                    'errors': serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = serializer.validated_data['email'].lower().strip()
        otp_code = serializer.validated_data['otp_code']

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {
                    'success': False,
                    'message': 'No account found with this email address.',
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        if user.is_email_verified:
            return Response(
                {
                    'success': False,
                    'message': 'This email is already verified. You can log in.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if user.email_verification_code != otp_code:
            return Response(
                {
                    'success': False,
                    'message': 'Invalid verification code. Please try again.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if timezone.now() > user.email_verification_code_expires:
            return Response(
                {
                    'success': False,
                    'message': 'Verification code has expired. Please request a new one.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.is_email_verified = True
        user.email_verification_code = None
        user.email_verification_code_expires = None
        user.save(update_fields=[
            'is_email_verified',
            'email_verification_code',
            'email_verification_code_expires',
        ])

        # CHANGE: Lazy import instead of top-level import
        from companies.models import PendingInvitation, CompanyUser

        pending_invitations = PendingInvitation.objects.filter(
            email=email,
            is_accepted=False,
        ).select_related('company')

        companies_joined = []
        for invitation in pending_invitations:
            CompanyUser.objects.create(
                user=user,
                company=invitation.company,
                role=invitation.role,
                invited_by=invitation.invited_by,
            )
            invitation.is_accepted = True
            invitation.save(update_fields=['is_accepted'])
            companies_joined.append(invitation.company.name)

        # CHANGE: Send welcome email with companies list
        from nidus_erp.email_service import send_welcome_email
        send_welcome_email(user=user, companies_joined=companies_joined)

        joined_msg = ''
        if companies_joined:
            joined_msg = f' You have been added to: {", ".join(companies_joined)}.'

        return Response(
            {
                'success': True,
                'message': f'Email verified successfully! You can now log in.{joined_msg}',
            },
            status=status.HTTP_200_OK,
        )


class ResendOTPView(APIView):

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ResendOTPSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                {
                    'success': False,
                    'message': 'Invalid input.',
                    'errors': serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = serializer.validated_data['email'].lower().strip()

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {
                    'success': True,
                    'message': 'If an account with this email exists, a new code has been sent.',
                },
                status=status.HTTP_200_OK,
            )

        if user.is_email_verified:
            return Response(
                {
                    'success': False,
                    'message': 'This email is already verified.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        otp_code = generate_otp()
        user.email_verification_code = otp_code
        user.email_verification_code_expires = (
            timezone.now() + timedelta(minutes=settings.OTP_EXPIRY_MINUTES)
        )
        user.save(update_fields=[
            'email_verification_code',
            'email_verification_code_expires',
        ])

        # CHANGE: Uses centralized email service
        from nidus_erp.email_service import send_verification_email
        send_verification_email(user=user, otp_code=otp_code)

        return Response(
            {
                'success': True,
                'message': 'If an account with this email exists, a new code has been sent.',
            },
            status=status.HTTP_200_OK,
        )


class LoginView(APIView):

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                {
                    'success': False,
                    'message': 'Invalid input.',
                    'errors': serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = serializer.validated_data['email'].lower().strip()
        password = serializer.validated_data['password']

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {
                    'success': False,
                    'message': 'Invalid email or password.',
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.check_password(password):
            return Response(
                {
                    'success': False,
                    'message': 'Invalid email or password.',
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.is_active:
            return Response(
                {
                    'success': False,
                    'message': 'This account has been deactivated. Please contact support.',
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        if not user.is_email_verified:
            return Response(
                {
                    'success': False,
                    'message': 'Please verify your email before logging in.',
                    'requires_verification': True,
                    'email': user.email,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        refresh = RefreshToken.for_user(user)

        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])

        return Response(
            {
                'success': True,
                'message': 'Login successful!',
                'data': {
                    'tokens': {
                        'access': str(refresh.access_token),
                        'refresh': str(refresh),
                    },
                    'user': UserProfileSerializer(user).data,
                },
            },
            status=status.HTTP_200_OK,
        )


class ProfileView(APIView):

    def get(self, request):
        serializer = UserProfileSerializer(request.user)

        return Response(
            {
                'success': True,
                'data': serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):

    def post(self, request):
        refresh_token = request.data.get('refresh')

        if not refresh_token:
            return Response(
                {
                    'success': False,
                    'message': 'Refresh token is required.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()

            return Response(
                {
                    'success': True,
                    'message': 'Logged out successfully.',
                },
                status=status.HTTP_200_OK,
            )

        except TokenError:
            return Response(
                {
                    'success': False,
                    'message': 'Token is invalid or already expired.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )