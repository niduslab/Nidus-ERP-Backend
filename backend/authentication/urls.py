# backend/authentication/urls.py


from django.urls import path                
from rest_framework_simplejwt.views import TokenRefreshView
from . import views                            


app_name = 'authentication'

urlpatterns = [
    
    path('register/', views.RegisterView.as_view(),name='register'),

    path('verify-email/', views.VerifyEmailView.as_view(),name='verify-email'),

    path('resend-otp/', views.ResendOTPView.as_view(),name='resend-otp'),

    path('login/', views.LoginView.as_view(), name='login'),

    path('logout/', views.LogoutView.as_view(), name='logout'),

    path('token/refresh/', TokenRefreshView.as_view(),name='token-refresh'),
   
    path('profile/', views.ProfileView.as_view(), name='profile'),
]