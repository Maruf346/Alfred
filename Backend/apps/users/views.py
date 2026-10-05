"""
Views for user authentication, profile management, and admin user access.
"""

from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
    inline_serializer,
)
from rest_framework import serializers as drf_serializers
from rest_framework import status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import User
from .permissions import IsAdminUser
from .serializers import *
from .services import *

def success_response(message: str, data=None, status_code=status.HTTP_200_OK):
    return Response(
        {
            "success": True,
            "message": message,
            "data": data or {},
        },
        status=status_code,
    )


def perform_service_call(callback, *args, **kwargs):
    try:
        return callback(*args, **kwargs)
    except ValueError as exc:
        raise ValidationError({"detail": str(exc)})


def build_success_response_serializer(name: str, data_serializer=None):
    if data_serializer is None:
        data_serializer = inline_serializer(
            name=f"{name}Data",
            fields={},
        )

    return inline_serializer(
        name=f"{name}Response",
        fields={
            "success": drf_serializers.BooleanField(default=True),
            "message": drf_serializers.CharField(),
            "data": data_serializer,
        },
    )


user_auth_payload_serializer = inline_serializer(
    name="UserAuthPayload",
    fields={
        "access_token": drf_serializers.CharField(),
        "refresh_token": drf_serializers.CharField(),
        "user": inline_serializer(
            name="AuthenticatedUserSummary",
            fields={
                "id": drf_serializers.UUIDField(),
                "full_name": drf_serializers.CharField(allow_blank=True),
                "email": drf_serializers.EmailField(),
                "gender": drf_serializers.CharField(allow_null=True, allow_blank=True, required=False),
                "age": drf_serializers.IntegerField(allow_null=True, required=False),
                "location": drf_serializers.CharField(allow_null=True, allow_blank=True, required=False),
                "address": drf_serializers.CharField(allow_null=True, allow_blank=True, required=False),
                "latitude": drf_serializers.DecimalField(max_digits=9, decimal_places=6, allow_null=True, required=False),
                "longitude": drf_serializers.DecimalField(max_digits=9, decimal_places=6, allow_null=True, required=False),
                "interests": drf_serializers.JSONField(allow_null=True, required=False),
                "budget": drf_serializers.CharField(allow_null=True, allow_blank=True, required=False),
                "subscription_plan": drf_serializers.CharField(),
                "provider": drf_serializers.CharField(),
                "profile_picture": drf_serializers.CharField(allow_null=True, required=False),
                "is_active": drf_serializers.BooleanField(),
                "is_admin": drf_serializers.BooleanField(),
            },
        ),
    },
)

otp_delivery_data_serializer = inline_serializer(
    name="OtpDeliveryData",
    fields={
        "message": drf_serializers.CharField(),
        "email": drf_serializers.EmailField(),
        "expires_in_seconds": drf_serializers.IntegerField(),
    },
)

password_reset_initiate_data_serializer = inline_serializer(
    name="PasswordResetInitiateData",
    fields={
        "message": drf_serializers.CharField(),
        "expires_in_seconds": drf_serializers.IntegerField(),
    },
)

password_reset_verify_data_serializer = inline_serializer(
    name="PasswordResetVerifyData",
    fields={
        "message": drf_serializers.CharField(),
        "reset_token": drf_serializers.CharField(),
        "expires_in_seconds": drf_serializers.IntegerField(),
    },
)

empty_data_serializer = inline_serializer(
    name="EmptyData",
    fields={},
)

validation_error_serializer = inline_serializer(
    name="ValidationErrorResponse",
    fields={
        "detail": drf_serializers.CharField(required=False),
    },
)


class UserInitiateRegistrationView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Users - Registration"],
        operation_id="user_register_initiate",
        summary="Initiate user registration",
        description="Starts email registration by validating the payload and sending an OTP to the user's email address.",
        request=InitiateRegistrationSerializer,
        responses={
            200: OpenApiResponse(
                response=build_success_response_serializer(
                    "RegistrationInitiate",
                    otp_delivery_data_serializer,
                ),
                description="OTP queued for delivery.",
                examples=[
                    OpenApiExample(
                        "Registration Initiated",
                        value={
                            "success": True,
                            "message": "OTP sent to your email. Please verify to complete registration.",
                            "data": {
                                "message": "OTP sent to your email. Please verify to complete registration.",
                                "email": "jane@example.com",
                                "expires_in_seconds": 300,
                            },
                        },
                        response_only=True,
                    )
                ],
            ),
            400: OpenApiResponse(response=validation_error_serializer, description="Invalid registration input."),
        },
        examples=[
            OpenApiExample(
                "Registration Request",
                value={
                    "full_name": "Jane Doe",
                    "email": "jane@example.com",
                    "password": "StrongPass123!",
                    "confirm_password": "StrongPass123!",
                },
                request_only=True,
            )
        ],
    )
    def post(self, request):
        serializer = InitiateRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data.copy()
        payload.pop("confirm_password", None)
        result = perform_service_call(
            RegistrationService.initiate_registration,
            **payload,
        )
        return success_response(result["message"], result)


class UserVerifyRegistrationView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Users - Registration"],
        operation_id="user_register_verify",
        summary="Verify registration OTP",
        description="Completes registration after OTP verification and returns the authenticated token payload.",
        request=VerifyRegistrationOTPSerializer,
        responses={
            201: OpenApiResponse(
                response=build_success_response_serializer(
                    "RegistrationVerify",
                    user_auth_payload_serializer,
                ),
                description="Registration completed successfully.",
                examples=[
                    OpenApiExample(
                        "Registration Verified",
                        value={
                            "success": True,
                            "message": "Registration completed successfully.",
                            "data": {
                                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.access",
                                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.refresh",
                                "user": {
                                    "id": "8ff2d741-3c58-4b2f-8b44-7ec7b8e018f6",
                                    "full_name": "Jane Doe",
                                    "email": "jane@example.com",
                                    "gender": None,
                                    "age": None,
                                    "location": None,
                                    "interests": None,
                                    "budget": None,
                                    "subscription_plan": "free",
                                    "provider": "self",
                                    "profile_picture": None,
                                    "is_active": True,
                                    "is_admin": False,
                                },
                            },
                        },
                        response_only=True,
                    )
                ],
            ),
            400: OpenApiResponse(response=validation_error_serializer, description="Invalid or expired OTP."),
        },
        examples=[
            OpenApiExample(
                "Verify Registration OTP",
                value={"email": "jane@example.com", "otp": "123456"},
                request_only=True,
            )
        ],
    )
    def post(self, request):
        serializer = VerifyRegistrationOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = perform_service_call(
            RegistrationService.verify_and_complete_registration,
            request=request,
            **serializer.validated_data,
        )
        return success_response(
            "Registration completed successfully.",
            result,
            status.HTTP_201_CREATED,
        )


class ResendRegistrationOTPView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Users - Registration"],
        operation_id="user_register_resend_otp",
        summary="Resend registration OTP",
        description="Resends a fresh registration OTP for an in-progress registration session.",
        request=ResendOTPSerializer,
        responses={
            200: OpenApiResponse(
                response=build_success_response_serializer(
                    "RegistrationResendOtp",
                    otp_delivery_data_serializer,
                ),
                description="OTP resent successfully.",
            ),
            400: OpenApiResponse(response=validation_error_serializer, description="Registration session expired or invalid."),
        },
    )
    def post(self, request):
        serializer = ResendOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = perform_service_call(
            RegistrationService.resend_otp,
            **serializer.validated_data,
        )
        return success_response(result["message"], result)


class UserLoginView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Users - Authentication"],
        operation_id="user_login",
        summary="User login",
        description="Authenticates a regular user with email and password and returns JWT tokens.",
        request=LoginSerializer,
        responses={
            200: OpenApiResponse(
                response=build_success_response_serializer("UserLogin", user_auth_payload_serializer),
                description="Login successful.",
                examples=[
                    OpenApiExample(
                        "User Login Success",
                        value={
                            "success": True,
                            "message": "Login successful.",
                            "data": {
                                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.access",
                                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.refresh",
                                "user": {
                                    "id": "8ff2d741-3c58-4b2f-8b44-7ec7b8e018f6",
                                    "full_name": "Jane Doe",
                                    "email": "jane@example.com",
                                    "gender": "female",
                                    "age": 27,
                                    "location": "Dhaka",
                                    "interests": ["Coffee", "Books"],
                                    "budget": "$50 - $100",
                                    "subscription_plan": "free",
                                    "provider": "self",
                                    "profile_picture": None,
                                    "is_active": True,
                                    "is_admin": False,
                                },
                            },
                        },
                        response_only=True,
                    )
                ],
            ),
            400: OpenApiResponse(response=validation_error_serializer, description="Invalid credentials or blocked account."),
        },
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = perform_service_call(
            AuthService.authenticate_user,
            **serializer.validated_data,
        )
        payload = AuthService.create_auth_payload(user, request=request)
        return success_response("Login successful.", payload)


class AdminLoginView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Admin - Authentication"],
        operation_id="admin_login",
        summary="Admin login",
        description="Authenticates an administrator with email and password and returns JWT tokens.",
        request=LoginSerializer,
        responses={
            200: OpenApiResponse(
                response=build_success_response_serializer("AdminLogin", user_auth_payload_serializer),
                description="Admin login successful.",
            ),
            400: OpenApiResponse(response=validation_error_serializer, description="Invalid credentials or non-admin account."),
        },
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = perform_service_call(
            AuthService.authenticate_user,
            require_admin=True,
            **serializer.validated_data,
        )
        payload = AuthService.create_auth_payload(user, request=request)
        return success_response("Admin login successful.", payload)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Users - Authentication"],
        operation_id="user_logout",
        summary="Logout",
        description="Invalidates the provided refresh token. Requires a valid access token for the current session.",
        request=RefreshTokenSerializer,
        responses={
            200: OpenApiResponse(
                response=build_success_response_serializer("Logout", empty_data_serializer),
                description="Logout successful.",
                examples=[
                    OpenApiExample(
                        "Logout Success",
                        value={
                            "success": True,
                            "message": "Logout successful.",
                            "data": {},
                        },
                        response_only=True,
                    )
                ],
            ),
            400: OpenApiResponse(response=validation_error_serializer, description="Invalid or expired refresh token."),
        },
    )
    def post(self, request):
        serializer = RefreshTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        perform_service_call(
            AuthService.logout,
            serializer.validated_data["refresh_token"],
        )
        return success_response("Logout successful.")


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Users - Authentication"],
        operation_id="user_change_password",
        summary="Change password",
        description="Changes the authenticated user's password after validating the current password and the new password rules.",
        request=ChangePasswordSerializer,
        responses={
            200: OpenApiResponse(
                response=build_success_response_serializer("ChangePassword", empty_data_serializer),
                description="Password changed successfully.",
            ),
            400: OpenApiResponse(response=validation_error_serializer, description="Validation failed for current or new password."),
        },
    )
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        perform_service_call(
            AuthService.change_password,
            request.user,
            serializer.validated_data["new_password"],
        )
        return success_response("Password changed successfully.")


class InitiatePasswordResetView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Users - Authentication"],
        operation_id="password_reset_initiate",
        summary="Initiate password reset",
        description="Starts the password reset flow and sends an OTP if the email exists. The response stays generic for security.",
        request=InitiatePasswordResetSerializer,
        responses={
            200: OpenApiResponse(
                response=build_success_response_serializer(
                    "PasswordResetInitiate",
                    password_reset_initiate_data_serializer,
                ),
                description="Password reset initiation response.",
            ),
            400: OpenApiResponse(response=validation_error_serializer, description="Invalid email payload."),
        },
    )
    def post(self, request):
        serializer = InitiatePasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = perform_service_call(
            PasswordResetService.initiate_password_reset,
            serializer.validated_data["email"],
        )
        return success_response(result["message"], result)


class VerifyPasswordResetOTPView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Users - Authentication"],
        operation_id="password_reset_verify_otp",
        summary="Verify password reset OTP",
        description="Validates the password-reset OTP and returns a one-time reset token.",
        request=VerifyPasswordResetOTPSerializer,
        responses={
            200: OpenApiResponse(
                response=build_success_response_serializer(
                    "PasswordResetVerifyOtp",
                    password_reset_verify_data_serializer,
                ),
                description="OTP verified successfully.",
            ),
            400: OpenApiResponse(response=validation_error_serializer, description="Invalid or expired OTP."),
        },
    )
    def post(self, request):
        serializer = VerifyPasswordResetOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = perform_service_call(
            PasswordResetService.verify_reset_otp,
            **serializer.validated_data,
        )
        return success_response(result["message"], result)


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Users - Authentication"],
        operation_id="password_reset_confirm",
        summary="Confirm password reset",
        description="Completes the password reset using the one-time reset token and the new password.",
        request=ResetPasswordSerializer,
        responses={
            200: OpenApiResponse(
                response=build_success_response_serializer("PasswordResetConfirm", empty_data_serializer),
                description="Password reset completed successfully.",
            ),
            400: OpenApiResponse(response=validation_error_serializer, description="Invalid token or password validation failed."),
        },
    )
    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = perform_service_call(
            PasswordResetService.reset_password,
            serializer.validated_data["reset_token"],
            serializer.validated_data["new_password"],
        )
        return success_response(result["message"])


class GoogleOAuthView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Users - Authentication"],
        operation_id="user_google_oauth",
        summary="Google sign-in",
        description="Authenticates or creates a user from a Google ID token and returns JWT tokens.",
        request=GoogleOAuthSerializer,
        responses={
            200: OpenApiResponse(
                response=build_success_response_serializer("GoogleOAuth", user_auth_payload_serializer),
                description="Google login successful.",
            ),
            400: OpenApiResponse(response=validation_error_serializer, description="Invalid Google token or account conflict."),
        },
    )
    def post(self, request):
        serializer = GoogleOAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = perform_service_call(
            AuthService.login_with_google,
            serializer.validated_data["id_token"],
            request=request,
        )
        return success_response("Google login successful.", result)


class AppleOAuthView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Users - Authentication"],
        operation_id="user_apple_oauth",
        summary="Apple sign-in",
        description="Authenticates or creates a user from an Apple ID token and returns JWT tokens.",
        request=AppleOAuthSerializer,
        responses={
            200: OpenApiResponse(
                response=build_success_response_serializer("AppleOAuth", user_auth_payload_serializer),
                description="Apple login successful.",
            ),
            400: OpenApiResponse(response=validation_error_serializer, description="Invalid Apple token or account conflict."),
        },
    )
    def post(self, request):
        serializer = AppleOAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = perform_service_call(
            AuthService.login_with_apple,
            serializer.validated_data["id_token"],
            user_data=serializer.validated_data.get("user"),
            request=request,
        )
        return success_response("Apple login successful.", result)


class UserProfileView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Users - Profile"],
        operation_id="user_profile_retrieve",
        summary="Get my profile",
        description="Returns the authenticated user's profile.",
        responses={
            200: OpenApiResponse(
                response=build_success_response_serializer("UserProfileRetrieve", UserProfileSerializer()),
                description="Profile retrieved successfully.",
            )
        },
    )
    def get(self, request):
        serializer = UserProfileSerializer(request.user, context={"request": request})
        return success_response("Profile retrieved successfully.", serializer.data)

    @extend_schema(
        tags=["Users - Profile"],
        operation_id="user_profile_update",
        summary="Update my profile",
        description="Updates editable profile fields for the authenticated user.",
        request=UpdateProfileSerializer,
        responses={
            200: OpenApiResponse(
                response=build_success_response_serializer("UserProfileUpdate", UserProfileSerializer()),
                description="Profile updated successfully.",
            ),
            400: OpenApiResponse(response=validation_error_serializer, description="Profile validation failed."),
        },
    )
    def patch(self, request):
        serializer = UpdateProfileSerializer(
            request.user,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        profile_serializer = UserProfileSerializer(
            request.user,
            context={"request": request},
        )
        return success_response("Profile updated successfully.", profile_serializer.data)


class UserAddressUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Users - Profile"],
        operation_id="user_address_update",
        summary="Update my address",
        description="Updates the authenticated user's saved address, latitude, and longitude.",
        request=UserAddressSerializer,
        responses={
            200: OpenApiResponse(
                response=build_success_response_serializer("UserAddressUpdate", UserAddressSerializer()),
                description="Address updated successfully.",
                examples=[
                    OpenApiExample(
                        "Address Updated",
                        value={
                            "success": True,
                            "message": "Address updated successfully.",
                            "data": {
                                "address": "Gulshan 1, Dhaka, Bangladesh",
                                "latitude": "23.780573",
                                "longitude": "90.416984",
                            },
                        },
                        response_only=True,
                    )
                ],
            ),
            400: OpenApiResponse(response=validation_error_serializer, description="Address validation failed."),
        },
        examples=[
            OpenApiExample(
                "Update Address",
                value={
                    "address": "Gulshan 1, Dhaka, Bangladesh",
                    "latitude": "23.780573",
                    "longitude": "90.416984",
                },
                request_only=True,
            )
        ],
    )
    def patch(self, request):
        serializer = UserAddressSerializer(
            request.user,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_response("Address updated successfully.", serializer.data)


class AdminProfileView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    @extend_schema(
        tags=["Admin -  Profile"],
        operation_id="admin_profile_retrieve",
        summary="Get admin profile",
        description="Returns the authenticated administrator's profile.",
        responses={
            200: OpenApiResponse(
                response=build_success_response_serializer("AdminProfileRetrieve", AdminProfileSerializer()),
                description="Admin profile retrieved successfully.",
            )
        },
    )
    def get(self, request):
        serializer = AdminProfileSerializer(request.user, context={"request": request})
        return success_response("Admin profile retrieved successfully.", serializer.data)

    @extend_schema(
        tags=["Admin -  Profile"],
        operation_id="admin_profile_update",
        summary="Update admin profile",
        description="Updates editable administrator profile fields such as full name, profile picture, and bio.",
        request=AdminProfileUpdateSerializer,
        responses={
            200: OpenApiResponse(
                response=build_success_response_serializer("AdminProfileUpdate", AdminProfileSerializer()),
                description="Admin profile updated successfully.",
            ),
            400: OpenApiResponse(response=validation_error_serializer, description="Profile validation failed."),
        },
    )
    def patch(self, request):
        serializer = AdminProfileUpdateSerializer(
            request.user,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        profile_serializer = AdminProfileSerializer(
            request.user,
            context={"request": request},
        )
        return success_response("Admin profile updated successfully.", profile_serializer.data)


@extend_schema(tags=["Admin - User Management"])
@extend_schema_view(
    list=extend_schema(
        operation_id="admin_user_list",
        summary="List users",
        description="Returns a paginated list of users for administrators. Supports search and ordering.",
        parameters=[
            OpenApiParameter("search", str, description="Search by email or full name."),
            OpenApiParameter("ordering", str, description="Order by `created_at`, `updated_at`, `email`, or `full_name`."),
            OpenApiParameter("page", int, description="Page number."),
            OpenApiParameter("page_size", int, description="Results per page."),
        ],
        responses={
            200: OpenApiResponse(
                response=AdminUserSerializer(many=True),
                description="Paginated user list.",
            )
        },
    ),
    retrieve=extend_schema(
        operation_id="admin_user_retrieve",
        summary="Retrieve user",
        description="Returns details for a single user by UUID for administrator review.",
        responses={
            200: OpenApiResponse(
                response=AdminUserSerializer,
                description="User details retrieved successfully.",
            )
        },
    ),
)
class AdminUserViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class = AdminUserSerializer
    queryset = User.objects.filter(is_superuser=False).order_by("-created_at")
    search_fields = ("email", "full_name")
    ordering_fields = ("created_at", "updated_at", "email", "full_name")
