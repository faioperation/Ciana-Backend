from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView
from .views import (
    LoginView,
    LogoutView,
    AdminCreateView,
    AdminListView,
    AdminDetailView,
    AdminUpdateView,
    AdminDeleteView,
    CurrentUserView,
    ChangePasswordView,
    UpdateProfileView,
    ForgotPasswordView,
    ResetPasswordView,
    VerifyOTPView,
    RefreshTokenView
)

app_name = 'user'

urlpatterns = [
    # Authentication endpoints
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('token/refresh/', RefreshTokenView.as_view(), name='token_refresh'),
    path('token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    
    # Current user endpoints
    path('me/', CurrentUserView.as_view(), name='current-user'),
    path('me/update/', UpdateProfileView.as_view(), name='update-profile'),
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),
    
    # Admin management endpoints (Superuser only for CUD operations)
    path('admins/', AdminListView.as_view(), name='admin-list'),
    path('admins/create/', AdminCreateView.as_view(), name='admin-create'),
    path('admins/<int:pk>/', AdminDetailView.as_view(), name='admin-detail'),
    path('admins/<int:pk>/update/', AdminUpdateView.as_view(), name='admin-update'),
    path('admins/<int:pk>/delete/', AdminDeleteView.as_view(), name='admin-delete'),

    # Forgot/Reset Password
    path('password/forgot/', ForgotPasswordView.as_view(), name='password-forgot'),
    path('password/verify/', VerifyOTPView.as_view(), name='password-verify'),
    path('password/reset/', ResetPasswordView.as_view(), name='password-reset'),

    # JWT auth paths
    # path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    # path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]
