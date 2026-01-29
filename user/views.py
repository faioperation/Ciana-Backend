from datetime import timedelta, date
from django.db.models import Count
from django.utils import timezone
from django.db.models.functions import TruncMonth
from calendar import month_name
from rest_framework import status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from django.contrib.auth import authenticate, get_user_model
from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse
from rest_framework.permissions import AllowAny

import logging

from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

from application.models import Application
from .permissions import IsAdminOrSuperUser

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

logger = logging.getLogger(__name__)
User = get_user_model()


# helper to set refresh cookie consistently
def _set_refresh_cookie(response: HttpResponse, refresh_token: str):
    cookie_name = settings.SIMPLE_JWT.get('REFRESH_COOKIE_NAME', 'refresh_token')
    cookie_path = settings.SIMPLE_JWT.get('REFRESH_COOKIE_PATH', '/')
    lifetime = settings.SIMPLE_JWT.get('REFRESH_TOKEN_LIFETIME', timedelta(days=7))
    # lifetime may be timedelta or int/seconds
    max_age = int(lifetime.total_seconds()) if isinstance(lifetime, timedelta) else int(lifetime)
    secure = not settings.DEBUG  # True in production
    samesite = getattr(settings, 'CSRF_COOKIE_SAMESITE', 'Lax') or 'Lax'

    # DRF Response inherits from Django's HttpResponse so set_cookie available
    response.set_cookie(
        cookie_name,
        str(refresh_token),
        max_age=max_age,
        httponly=True,
        secure=secure,
        samesite=samesite,
        path=cookie_path,
    )

def _delete_refresh_cookie(response: HttpResponse):
    cookie_name = settings.SIMPLE_JWT.get('REFRESH_COOKIE_NAME', 'refresh_token')
    cookie_path = settings.SIMPLE_JWT.get('REFRESH_COOKIE_PATH', '/')
    response.delete_cookie(cookie_name, path=cookie_path)


def _set_access_cookie(response: HttpResponse, access_token: str):
    cookie_name = getattr(settings, "ACCESS_COOKIE_NAME", "access_token")
    cookie_path = getattr(settings, "ACCESS_COOKIE_PATH", "/")
    # read lifetime from SIMPLE_JWT or fallback to 15 minutes
    access_life = settings.SIMPLE_JWT.get("ACCESS_TOKEN_LIFETIME", timedelta(minutes=15))
    max_age = int(access_life.total_seconds()) if isinstance(access_life, timedelta) else int(access_life)
    # HttpOnly True by default for safety (client JS cannot read it)
    httponly = getattr(settings, "ACCESS_COOKIE_HTTPONLY", True)
    secure = False if settings.DEBUG else True
    samesite = getattr(settings, 'CSRF_COOKIE_SAMESITE', 'Lax') or 'Lax'

    response.set_cookie(
        cookie_name,
        str(access_token),
        max_age=max_age,
        httponly=httponly,
        secure=secure,
        samesite=samesite,
        path=cookie_path,
    )

def _delete_access_cookie(response: HttpResponse):
    cookie_name = getattr(settings, "ACCESS_COOKIE_NAME", "access_token")
    cookie_path = getattr(settings, "ACCESS_COOKIE_PATH", "/")
    response.delete_cookie(cookie_name, path=cookie_path)


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
        access = refresh.access_token

        resp = Response({
            'message': 'Login successful',
            'user': UserSerializer(user, context={'request': request}).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(access),
            }
        }, status=status.HTTP_200_OK)
        print("SETTING REFRESH COOKIE FOR USER", user.id)

        _set_refresh_cookie(resp, refresh)
        _set_access_cookie(resp, access)

        return resp
    

class RefreshTokenView(APIView):
    permission_classes = [AllowAny]  # ensure CSRF checks on POST (Django's middleware) when cookies are used

    def post(self, request):
        cookie_name = settings.SIMPLE_JWT.get('REFRESH_COOKIE_NAME', 'refresh_token')
        refresh_token = request.COOKIES.get(cookie_name)
        if not refresh_token:
            return Response({'detail': 'Refresh token not provided'}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            token = RefreshToken(refresh_token)
        except TokenError:
            return Response({'detail': 'Invalid refresh token'}, status=status.HTTP_401_UNAUTHORIZED)

        # verify user exists
        user_id = token.get('user_id')
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({'detail': 'User not found'}, status=status.HTTP_401_UNAUTHORIZED)

        # create new access token
        new_access = token.access_token

        resp = Response({'access': str(new_access)}, status=status.HTTP_200_OK)

        # set access cookie
        _set_access_cookie(resp, new_access)

        # handle rotation if enabled
        rotate = settings.SIMPLE_JWT.get('ROTATE_REFRESH_TOKENS', False)
        blacklist_after_rotation = settings.SIMPLE_JWT.get('BLACKLIST_AFTER_ROTATION', False)

        if rotate:
            # issue a new refresh and set cookie
            new_refresh = RefreshToken.for_user(user)
            _set_refresh_cookie(resp, new_refresh)
            if blacklist_after_rotation:
                try:
                    token.blacklist()
                except Exception:
                    pass

        return resp


class LogoutView(APIView):
    """
    API endpoint for user logout.
    Blacklists the refresh token.
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        try:
            # prefer token from request body, fallback to cookie
            cookie_name = settings.SIMPLE_JWT.get('REFRESH_COOKIE_NAME', 'refresh_token')
            refresh_token = request.data.get('refresh_token') or request.COOKIES.get(cookie_name)

            resp = Response({'message': 'Logout successful'}, status=status.HTTP_200_OK)

            # clear cookies regardless
            _delete_refresh_cookie(resp)
            _delete_access_cookie(resp)

            if not refresh_token:
                return Response(
                    {'error': 'Refresh token is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            try:
                token = RefreshToken(refresh_token)
                token.blacklist()
            except TokenError:
                # token invalid; still clear cookies and return success
                pass
            
            return resp
        
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

        # capture plaintext password from validated data so we can email it.
        # NOTE: Do not log this value.
        raw_password = serializer.validated_data.get("password")

        # Save the user (serializer should call create_admin and set password)
        user = serializer.save()

        # Prepare email content
        subject = "Your admin account for Star Light Path"
        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None) or getattr(settings, "SERVER_EMAIL", None) or None
        to_email = [user.email]

        text_body = (
            f"Hello {user.get_full_name() or user.email},\n\n"
            "An admin account has been created for you at Star Light Path.\n\n"
            f"Login email: {user.email}\n"
            f"Password: {raw_password}\n\n"
            "Please sign in and change your password if you wish.\n\n"
            "— Star Light Path System"
        )

        # Optional: render an HTML template if you have templates/emails/new_admin.html
        try:
            html_body = render_to_string("emails/new_admin.html", {
                "full_name": user.get_full_name() or user.email,
                "email": user.email,
                "password": raw_password,
            })
        except Exception:
            html_body = None

        # Send email (don't fail the API if mail fails; just log)
        try:
            msg = EmailMultiAlternatives(subject, text_body, from_email, to_email)
            if html_body:
                msg.attach_alternative(html_body, "text/html")
            msg.send(fail_silently=False)
            logger.info("Sent new-admin credentials email to %s", user.email)
        except Exception as e:
            # Log exception but proceed — creation already completed
            logger.exception("Failed to send admin-credentials email to %s: %s", user.email, e)

        return Response(
            {
                "message": "Admin user created successfully",
                "user": UserSerializer(user, context={"request": request}).data
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



# Dashboard summary view
class DashboardSummaryView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrSuperUser]

    def get(self, request):
        users_count = User.objects.count()
        total_applications_count = Application.objects.count()
        total_refer_count = Application.objects.filter(application_type=Application.ApplicationType.REFER).count()
        total_without_refer_count = Application.objects.exclude(application_type=Application.ApplicationType.REFER).count()

        today = timezone.localdate()
        today_application_count = Application.objects.filter(created_at__date=today).count()

        return Response({
            "users_count": users_count,
            "total_applications_count": total_applications_count,
            "total_refer_count": total_refer_count,
            "total_without_refer_count": total_without_refer_count,
            "today_application_count": today_application_count,
        })


# Helper: build list of (year, month) tuples for the last N months (oldest -> newest)
def _get_last_n_months(n, end_date=None):
    end = end_date or timezone.now().date()
    year = end.year
    month = end.month
    months = []
    # produce months oldest -> newest
    for i in range(n - 1, -1, -1):
        m = month - i
        y = year
        while m <= 0:
            m += 12
            y -= 1
        months.append((y, m))
    return months


# Monthly applications series for bar chart
class DashboardMonthlyApplicationsView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrSuperUser]

    def get(self, request):
        # number of months to return (default 6)
        try:
            months = int(request.query_params.get("months", 6))
        except ValueError:
            months = 6
        months = max(1, min(24, months))  # constrain for safety

        # compute month buckets and start_date
        last_months = _get_last_n_months(months)
        first_year, first_month = last_months[0]
        start_date = date(first_year, first_month, 1)

        # aggregate counts grouped by month
        qs = (
            Application.objects
            .filter(created_at__date__gte=start_date)
            .annotate(month=TruncMonth('created_at'))
            .values('month')
            .annotate(count=Count('id'))
            .order_by('month')
        )

        # map TruncMonth results to 'YYYY-MM' keys
        counts_map = {}
        for r in qs:
            # r['month'] is datetime like 2026-01-01 00:00:00+00:00
            key = r['month'].date().strftime("%Y-%m")
            counts_map[key] = r['count']

        labels = []
        data = []
        for y, m in last_months:
            key = f"{y}-{m:02d}"
            labels.append(f"{month_name[m]} {y}")  # "Jan 2026"
            data.append(counts_map.get(key, 0))

        # optional: also send raw mapping if frontend wants iso keys
        iso_keys = [f"{y}-{m:02d}" for y, m in last_months]

        return Response({
            "labels": labels,
            "data": data,
            "iso_keys": iso_keys,
        })
