# backend/nidus_erp/email_service.py
"""
Centralized email service for Nidus ERP.

All email sending goes through this module. This gives us:
- One place to change email behavior (switch providers, add queuing, etc.)
- Consistent HTML + plain text fallback for all emails
- Centralized error handling and logging

Usage:
    from nidus_erp.email_service import send_verification_email
    send_verification_email(user=user, otp_code='123456')
"""

import logging
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags


logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# CORE EMAIL SENDER
# ──────────────────────────────────────────────

def _send_html_email(subject, template_name, context, recipient_email):
    """
    Internal helper: Renders an HTML template and sends it with a
    plain-text fallback. All public email functions call this.

    EmailMultiAlternatives sends BOTH plain text AND HTML in one email.
    Email clients that support HTML show the pretty version.
    Older clients (or privacy-focused ones) show the plain text version.

    Args:
        subject: Email subject line
        template_name: Path to HTML template (e.g., 'emails/verification.html')
        context: Dict of variables to pass into the template
        recipient_email: The recipient's email address
    """
    # Add common context available to ALL email templates
    context.update({
        'app_name': 'Nidus ERP',
        'support_email': settings.DEFAULT_FROM_EMAIL,
        'current_year': '2026',
    })

    try:
        # Render HTML from Django template
        html_content = render_to_string(template_name, context)

        # Strip HTML tags to create plain-text version automatically
        # This means we don't need to maintain separate .txt templates
        plain_text = strip_tags(html_content)

        # Create email with plain text as the base
        email = EmailMultiAlternatives(
            subject=subject,
            body=plain_text,                         # Plain text fallback
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient_email],
        )

        # Attach HTML as an alternative — email clients prefer this if supported
        email.attach_alternative(html_content, 'text/html')

        # fail_silently=False in DEBUG so we catch errors during development
        # fail_silently=True in production so email failures don't crash the API
        email.send(fail_silently=not settings.DEBUG)

        logger.info(f'Email sent: "{subject}" → {recipient_email}')
        return True

    except Exception as e:
        logger.error(f'Email failed: "{subject}" → {recipient_email} | Error: {e}')
        if settings.DEBUG:
            raise
        return False


# ──────────────────────────────────────────────
# PUBLIC EMAIL FUNCTIONS
# ──────────────────────────────────────────────

def send_verification_email(user, otp_code):
    """
    Send OTP verification code to a newly registered user.
    Called from: authentication/views.py → RegisterView, ResendOTPView
    """
    return _send_html_email(
        subject='Nidus ERP — Verify Your Email Address',
        template_name='emails/verification.html',
        context={
            'full_name': user.full_name,
            'otp_code': otp_code,
            'expiry_minutes': settings.OTP_EXPIRY_MINUTES,
        },
        recipient_email=user.email,
    )


def send_welcome_email(user, companies_joined=None):
    """
    Send welcome email after successful email verification.
    Optionally lists companies the user was auto-added to via pending invitations.
    Called from: authentication/views.py → VerifyEmailView
    """
    return _send_html_email(
        subject='Welcome to Nidus ERP!',
        template_name='emails/welcome.html',
        context={
            'full_name': user.full_name,
            'companies_joined': companies_joined or [],
        },
        recipient_email=user.email,
    )


def send_member_added_email(user, company_name, role, invited_by_name):
    """
    Notify an existing user that they've been added to a company.
    Called from: companies/views.py → CompanyMemberListView.post()
    """
    return _send_html_email(
        subject=f'Nidus ERP — You\'ve been added to {company_name}',
        template_name='emails/member_added.html',
        context={
            'full_name': user.full_name,
            'company_name': company_name,
            'role': role,
            'invited_by_name': invited_by_name,
        },
        recipient_email=user.email,
    )


def send_pending_invitation_email(email, company_name, role, invited_by_name):
    """
    Invite a non-registered person to join Nidus ERP and a company.
    Called from: companies/views.py → CompanyMemberListView.post()
    """
    return _send_html_email(
        subject=f'Nidus ERP — You\'re invited to join {company_name}',
        template_name='emails/pending_invitation.html',
        context={
            'email': email,
            'company_name': company_name,
            'role': role,
            'invited_by_name': invited_by_name,
            'signup_url': settings.FRONTEND_URL + '/register',
        },
        recipient_email=email,
    )


def send_member_removed_email(user, company_name):
    """
    Notify a user they've been removed from a company.
    Called from: companies/views.py → CompanyMemberDetailView.delete()
    """
    return _send_html_email(
        subject=f'Nidus ERP — You\'ve been removed from {company_name}',
        template_name='emails/member_removed.html',
        context={
            'full_name': user.full_name,
            'company_name': company_name,
        },
        recipient_email=user.email,
    )


def send_role_changed_email(user, company_name, old_role, new_role):
    """
    Notify a user their role in a company has changed.
    Called from: companies/views.py → CompanyMemberDetailView.patch()
    """
    return _send_html_email(
        subject=f'Nidus ERP — Your role in {company_name} has been updated',
        template_name='emails/role_changed.html',
        context={
            'full_name': user.full_name,
            'company_name': company_name,
            'old_role': old_role,
            'new_role': new_role,
        },
        recipient_email=user.email,
    )


def send_ownership_received_email(user, company_name, previous_owner_name):
    """
    Notify the new owner that ownership has been transferred to them.
    Called from: companies/views.py → TransferOwnershipView.post()
    """
    return _send_html_email(
        subject=f'Nidus ERP — You are now the Owner of {company_name}',
        template_name='emails/ownership_received.html',
        context={
            'full_name': user.full_name,
            'company_name': company_name,
            'previous_owner_name': previous_owner_name,
        },
        recipient_email=user.email,
    )


def send_ownership_transferred_email(user, company_name, new_owner_name, new_role_for_self):
    """
    Confirm to the previous owner that they have transferred ownership.
    Called from: companies/views.py → TransferOwnershipView.post()
    """
    left_company = (new_role_for_self == 'LEAVE')

    if left_company:
        your_status = 'Left the company'
    else:
        your_status = f'Role changed to {new_role_for_self}'

    return _send_html_email(
        subject=f'Nidus ERP — You have transferred ownership of {company_name}',
        template_name='emails/ownership_transferred.html',
        context={
            'full_name': user.full_name,
            'company_name': company_name,
            'new_owner_name': new_owner_name,
            'your_status': your_status,
            'left_company': left_company,
        },
        recipient_email=user.email,
    )