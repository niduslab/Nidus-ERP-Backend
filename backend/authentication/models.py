# backend/authentication/models.py

import uuid                                      
from django.contrib.auth.models import (        
    AbstractBaseUser,                             
    BaseUserManager,                              
    PermissionsMixin,                           
)
from django.db import models               
from django.utils import timezone          


class UserManager(BaseUserManager):

    def create_user(self, email, full_name, password=None, **extra_fields):
        
        if not email:                                         
            raise ValueError('Users must have an email address')
        if not full_name:                                     
            raise ValueError('Users must have a full name')

        email = self.normalize_email(email)                    
        user = self.model(                                    
            email=email,
            full_name=full_name,
            **extra_fields                                     
        )
        user.set_password(password)                           
        user.save(using=self._db)                             
        return user

    def create_superuser(self, email, full_name, password=None, **extra_fields):
        
        extra_fields.setdefault('is_staff', True)             
        extra_fields.setdefault('is_superuser', True)         
        extra_fields.setdefault('is_active', True)            
        extra_fields.setdefault('is_email_verified', True)     

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, full_name, password, **extra_fields)

class User(AbstractBaseUser, PermissionsMixin):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(max_length=255, unique=True, db_index=True, verbose_name='email address')
    full_name = models.CharField(max_length=100, verbose_name='full name')
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name='phone number')
    is_email_verified = models.BooleanField(default=False, verbose_name='email verified')
    email_verification_code = models.CharField(max_length=6, blank=True, null=True, verbose_name='verification code')
    email_verification_code_expires = models.DateTimeField(blank=True, null=True, verbose_name='verification code expiry')
    is_active = models.BooleanField(default=True, verbose_name='active')
    is_staff = models.BooleanField(default=False, verbose_name='staff status')
    date_joined = models.DateTimeField(default=timezone.now, verbose_name='date joined')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='last updated')

    objects = UserManager()
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['full_name']

    class Meta:
        verbose_name = 'user'
        verbose_name_plural = 'users'
        ordering = ['-date_joined']

    def __str__(self):
        return f"{self.full_name} ({self.email})"

    def get_full_name(self):
        return self.full_name

    def get_short_name(self):
        return self.full_name.split(' ')[0]
