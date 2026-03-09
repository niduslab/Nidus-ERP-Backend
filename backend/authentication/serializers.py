# backend/authentication/serializers.py

from rest_framework import serializers           
from django.contrib.auth import get_user_model  
from django.contrib.auth.password_validation import validate_password  

User = get_user_model()      

class RegisterSerializer(serializers.ModelSerializer):

    password = serializers.CharField(
        write_only=True,                       
        min_length=8,                      
        validators=[validate_password],       
        style={'input_type': 'password'},      
    )

   
    password_confirm = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'},
    )

    class Meta:
        model = User                             
        fields = [
            'id',                               
            'email',                           
            'full_name',                        
            'password',                         
            'password_confirm',               
        ]
        read_only_fields = ['id']              

    def validate_email(self, value):
       
        value = value.lower().strip()

        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError(
                'A user with this email already exists.'
            )

        return value

    def validate_full_name(self, value):
      
        value = value.strip()               

        if len(value) < 2:
            raise serializers.ValidationError(
                'Full name must be at least 2 characters.'
            )

        return value

    def validate(self, attrs):
        
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({
                'password_confirm': 'Passwords do not match.'
            })

        return attrs

    def create(self, validated_data):
        
        validated_data.pop('password_confirm')

        user = User.objects.create_user(
            email=validated_data['email'],
            full_name=validated_data['full_name'],
            password=validated_data['password'],
        )

        return user


class VerifyEmailSerializer(serializers.Serializer):

    email = serializers.EmailField()         

    otp_code = serializers.CharField(
        max_length=6,                           
        min_length=6,
    )


class ResendOTPSerializer(serializers.Serializer):

    email = serializers.EmailField()


class LoginSerializer(serializers.Serializer):

    email = serializers.EmailField()

    password = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'},
    )


class UserProfileSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'full_name',
            'phone',
            'is_email_verified',
            'date_joined',
        ]
        read_only_fields = fields             