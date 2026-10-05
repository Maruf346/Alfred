"""
URL configuration for the users app.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import *

router = DefaultRouter()
router.register(r"admin/users", AdminUserViewSet, basename="admin-users")

urlpatterns = [
    # User Authentication and Profile Management
    path("register/initiate/", UserInitiateRegistrationView.as_view(), name="user-register-initiate"),
    path("register/verify/", UserVerifyRegistrationView.as_view(), name="user-register-verify"),
    path("register/resend-otp/", ResendRegistrationOTPView.as_view(), name="register-resend-otp"),
    path("login/", UserLoginView.as_view(), name="user-login"),
    
    # Admin Authentication and Profile Management
    path("admin/login/", AdminLoginView.as_view(), name="admin-login"),
    path("admin/profile/", AdminProfileView.as_view(), name="admin-profile"),
    
    # Shared Authentication Endpoints
    path("logout/", LogoutView.as_view(), name="logout"),
    path("password/change/", ChangePasswordView.as_view(), name="password-change"),
    path("password-reset/initiate/", InitiatePasswordResetView.as_view(), name="password-reset-initiate"),
    path("password-reset/verify/", VerifyPasswordResetOTPView.as_view(), name="password-reset-verify"),
    path("password-reset/confirm/", ResetPasswordView.as_view(), name="password-reset-confirm"),
    
    # OAuth Authentication Endpoints
    path("auth/google/", GoogleOAuthView.as_view(), name="google-oauth"),
    path("auth/apple/", AppleOAuthView.as_view(), name="apple-oauth"),
    
    # User Profile Management
    path("profile/", UserProfileView.as_view(), name="user-profile"),
    path("address/", UserAddressUpdateView.as_view(), name="user-address-update"),
    
    # Admin User Management
    path("", include(router.urls)),
]
