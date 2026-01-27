from rest_framework import status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from django.contrib.auth import authenticate, get_user_model
from django.conf import settings
from django.core.cache import cache
from rest_framework.permissions import AllowAny

from .serializers import (
    UserSerializer,
    AdminCreateSerializer,
    AdminUpdateSerializer,
    AdminListSerializer,
    LoginSerializer,
    ChangePasswordSerializer,
    UserProfileSerializer,
    ForgotPasswordSerializer,
    PasswordResetConfirmSerializer,
    VerifyOTPSerializer
)
from .utils import (
    generate_numeric_otp, can_request_otp, store_otp_for_email,
    send_otp_email, verify_otp, increment_verify_attempts,
    clear_otp_for_email, _otp_reqcount_key, _otp_attempts_key,
    set_verified_for_email, is_verified_for_email, clear_verified_for_email
)
from .permissions import IsSuperUser, IsAdminOrSuperUser

User = get_user_model()


class LoginView(APIView):
    """
    API endpoint for user login.
    Returns JWT tokens on successful authentication.
    Only active users with ADMIN or SUPERUSER role can login.
    """
    permission_classes = [AllowAny]
    serializer_class = LoginSerializer
    
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email']
        password = serializer.validated_data['password']
        
        # Authenticate user
        user = authenticate(email=email, password=password)
        
        if user is None:
            return Response(
                {'error': 'Invalid email or password'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Check if user is active
        if not user.is_active:
            return Response(
                {'error': 'User account is disabled'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if user has admin privileges
        if user.role not in [User.Role.ADMIN, User.Role.SUPERUSER]:
            return Response(
                {'error': 'You do not have permission to access this system'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'message': 'Login successful',
            'user': UserSerializer(user, context={'request': request}).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }, status=status.HTTP_200_OK)


class LogoutView(APIView):
    """
    API endpoint for user logout.
    Blacklists the refresh token.
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        try:
            refresh_token = request.data.get('refresh_token')
            if not refresh_token:
                return Response(
                    {'error': 'Refresh token is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            token = RefreshToken(refresh_token)
            token.blacklist()
            
            return Response(
                {'message': 'Logout successful'},
                status=status.HTTP_200_OK
            )

        except TokenError as e:
            return Response(
                {'error': f'Token error: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': f'Invalid token: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )


class AdminCreateView(generics.CreateAPIView):
    """
    API endpoint for creating new admin users.
    Only accessible by superuser.
    """
    queryset = User.objects.filter(role=User.Role.ADMIN)
    serializer_class = AdminCreateSerializer
    permission_classes = [IsAuthenticated, IsSuperUser]
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        return Response(
            {
                'message': 'Admin user created successfully',
                'user': UserSerializer(user, context={'request': request}).data
            },
            status=status.HTTP_201_CREATED
        )


class AdminListView(generics.ListAPIView):
    """
    API endpoint to list all admin users.
    Only accessible by admin and superuser.
    """
    serializer_class = AdminListSerializer
    permission_classes = [IsAuthenticated, IsAdminOrSuperUser]
    
    def get_queryset(self):
        """
        Return all active admin users (both ADMIN and SUPERUSER roles).
        """
        return User.objects.filter(
            role__in=[User.Role.ADMIN, User.Role.SUPERUSER],
            is_active=True
        ).order_by('-date_joined')


class AdminDetailView(generics.RetrieveAPIView):
    """
    API endpoint to retrieve a specific admin user.
    Only accessible by admin and superuser.
    """
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsAdminOrSuperUser]
    
    def get_queryset(self):
        return User.objects.filter(role__in=[User.Role.ADMIN, User.Role.SUPERUSER])


class AdminUpdateView(generics.UpdateAPIView):
    """
    API endpoint to update a specific admin user.
    Only accessible by superuser.
    """
    serializer_class = AdminUpdateSerializer
    permission_classes = [IsAuthenticated, IsSuperUser]
    
    def get_queryset(self):
        return User.objects.filter(role=User.Role.ADMIN)
    
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        return Response(
            {
                'message': 'Admin user updated successfully',
                'user': UserSerializer(instance, context={'request': request}).data
            },
            status=status.HTTP_200_OK
        )


class AdminDeleteView(generics.DestroyAPIView):
    """
    API endpoint to deactivate/delete a specific admin user.
    Only accessible by superuser.
    Performs soft delete by setting is_active to False.
    """
    queryset = User.objects.filter(role=User.Role.ADMIN)
    permission_classes = [IsAuthenticated, IsSuperUser]
    
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        
        # Prevent deactivating yourself
        if instance.id == request.user.id:
            return Response(
                {'error': 'You cannot deactivate your own account'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Soft delete - deactivate user instead of deleting
        instance.is_active = False
        instance.save()
        
        return Response(
            {'message': 'Admin user deactivated successfully'},
            status=status.HTTP_200_OK
        )


class CurrentUserView(APIView):
    """
    API endpoint to get current logged-in user information.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ChangePasswordView(APIView):
    """
    API endpoint for changing user password.
    User must provide old password to change to new password.
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        
        # Change password
        user = request.user
        user.set_password(serializer.validated_data['new_password'])
        user.save()

        # 🔒 Invalidate all refresh tokens for this user
        try:
            tokens = RefreshToken.for_user(user)
            tokens.blacklist()
        except Exception:
            pass  # Token may already be invalid
        
        return Response(
            {'message': "Password changed successfully. Please log in again."},
            status=status.HTTP_200_OK
        )


class UpdateProfileView(generics.UpdateAPIView):
    """
    API endpoint for users to update their own profile.
    Cannot change role or admin privileges.
    """
    serializer_class = AdminUpdateSerializer
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        return self.request.user
    
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        
        # Remove is_active from data to prevent users from changing their own status
        data = request.data.copy()
        
        serializer = self.get_serializer(instance, data=data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        return Response(
            {
                'message': 'Profile updated successfully',
                'user': UserProfileSerializer(instance).data
            },
            status=status.HTTP_200_OK
        )
    

class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email'].lower()

        # can_request_otp returns (allowed, reason, remaining_cd, remaining_reqs)
        allowed, reason, retry_after, remaining_reqs = can_request_otp(email)
        if not allowed:
            return Response(
                {"detail": reason, "retry_after": retry_after, "remaining_requests": remaining_reqs},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

        otp = generate_numeric_otp()
        store_otp_for_email(email, otp)

        try:
            if User.objects.filter(email__iexact=email).exists():
                send_otp_email(email, otp)
        except Exception:
            # Do not reveal email/send errors to caller
            pass

        # Use the values returned by can_request_otp for frontend-friendly info
        # If retry_after is None/0, fall back to the configured cooldown
        cooldown = retry_after or getattr(settings, "PASSWORD_RESET_RESEND_COOLDOWN", 60)
        remaining = remaining_reqs if remaining_reqs is not None else max(0, getattr(settings, "PASSWORD_RESET_MAX_REQUESTS_PER_HOUR", 5) - (cache.get(_otp_reqcount_key(email)) or 0))

        return Response({
            "detail": "If an account exists for that email, you will receive an OTP shortly.",
            "retry_after": cooldown,
            "remaining_requests": remaining
        }, status=status.HTTP_200_OK)
    

class VerifyOTPView(APIView):
    """
    Verify OTP only. If correct, set a short 'verified' flag in Redis.
    Frontend should call this after user enters the OTP.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email'].lower()
        otp = serializer.validated_data['otp']

        # increment and check attempts
        attempts = increment_verify_attempts(email)
        max_attempts = getattr(settings, "PASSWORD_RESET_MAX_VERIFY_ATTEMPTS", 5)
        if attempts > max_attempts:
            clear_otp_for_email(email)
            clear_verified_for_email(email)
            return Response({"detail": "Too many wrong OTP attempts. Request a new OTP."},
                            status=status.HTTP_403_FORBIDDEN)

        if not verify_otp(email, otp):
            return Response({"detail": "Invalid OTP or expired."}, status=status.HTTP_400_BAD_REQUEST)

        # OTP is valid: mark verified and clear stored otp (prevent reuse)
        set_verified_for_email(email)
        clear_otp_for_email(email)  # optional: remove original OTP
        return Response({"detail": "OTP verified. You may set a new password now."},
                        status=status.HTTP_200_OK)


class ResetPasswordView(APIView):
    """
    Reset password after OTP verification.
    Frontend must first call VerifyOTPView which sets a short-lived verified flag.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email'].lower()
        new_password = serializer.validated_data['new_password']

        # require the prior verification step
        if not is_verified_for_email(email):
            return Response(
                {"detail": "OTP not verified or verification expired. Please verify OTP first."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            # clear verified marker to avoid reuse; keep response generic
            clear_verified_for_email(email)
            return Response({"detail": "Password has been reset if the account exists."}, status=status.HTTP_200_OK)

        user.set_password(new_password)
        user.save()

        # clear verification and attempt keys
        clear_verified_for_email(email)
        clear_otp_for_email(email)

        # optional: blacklist outstanding tokens / force logout (advanced)
        return Response({"detail": "Password reset successful. Please log in with your new password."},
                        status=status.HTTP_200_OK)
    