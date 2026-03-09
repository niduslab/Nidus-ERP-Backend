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
    

    fieldsets = (
        (None, {                                          
            'fields': ('email', 'password')               
        }),
        ('Personal Info', {                                
            'fields': ('full_name', 'phone')
        }),
        ('Email Verification', {                           
            'fields': ('is_email_verified', 'email_verification_code', 'email_verification_code_expires')
        }),
        ('Permissions', {                                 
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')
        }),
        ('Timestamps', {                                  
            'fields': ('date_joined', 'updated_at'),
            'classes': ('collapse',)                       
        }),
    )


    add_fieldsets = (
        (None, {
            'classes': ('wide',),                         
            'fields': ('email', 'full_name', 'password1', 'password2'),
        }),
    )

    readonly_fields = ('date_joined', 'updated_at')