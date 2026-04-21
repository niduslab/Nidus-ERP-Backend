# backend/authentication/admin.py

from django.contrib import admin                         # Django's admin module
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin  # Default user admin class
from .models import User   


@admin.register(User)                                   
class UserAdmin(BaseUserAdmin):
  

    list_display = (
        'email',             
        'full_name',        
        'is_email_verified',
        'is_active',          
        'is_staff',           
        'date_joined',       
    )

  
    list_filter = (
        'is_email_verified',
        'is_active',
        'is_staff',
        'is_superuser',
        'date_joined',
    )

    
    search_fields = ('email', 'full_name', 'phone')

   
    ordering = ('-date_joined',)    
    

    # ──────────────────────────────────────────────
    # FIELDSETS — how fields are grouped on the user detail page
    # ──────────────────────────────────────────────
    # Each tuple is (section_heading, {options_dict}). The `classes: ('collapse',)`
    # option renders a section collapsed by default — we use it for Password
    # Reset because those fields are transient and rarely need attention. The
    # Email Verification section stays open because it is checked frequently
    # during onboarding debugging.
    fieldsets = (
        (None, {
            'fields': ('email', 'password'),
        }),
        ('Personal Info', {
            'fields': ('full_name', 'phone'),
        }),
        ('Email Verification', {
            'fields': (
                'is_email_verified',
                'email_verification_code',
                'email_verification_code_expires',
            ),
        }),
        # ── Password Reset OTP (Phase 2) ──
        # Collapsed by default — these fields are short-lived (10 minutes) and
        # empty most of the time. When a user reports "I didn't get my reset
        # code", admins can expand this section to see whether an OTP was
        # actually generated and when it expires. The fields are intentionally
        # editable: a staff member can clear them manually to invalidate a
        # pending reset if the account is suspected compromised.
        ('Password Reset', {
            'classes': ('collapse',),
            'fields': (
                'password_reset_code',
                'password_reset_code_expires',
            ),
        }),
        ('Permissions', {
            'fields': (
                'is_active', 'is_staff', 'is_superuser',
                'groups', 'user_permissions',
            ),
        }),
        ('Timestamps', {
            'fields': ('date_joined', 'updated_at'),
            'classes': ('collapse',),
        }),
    )


    add_fieldsets = (
        (None, {
            'classes': ('wide',),                         
            'fields': ('email', 'full_name', 'password1', 'password2'),
        }),
    )

    readonly_fields = ('date_joined', 'updated_at')