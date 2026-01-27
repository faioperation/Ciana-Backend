from rest_framework import permissions


class IsSuperUser(permissions.BasePermission):
    """
    Custom permission to only allow superusers to access.
    """
    
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.role == request.user.Role.SUPERUSER and
            request.user.is_superuser
        )


class IsAdminOrSuperUser(permissions.BasePermission):
    """
    Custom permission to allow both admin and superuser to access.
    """
    
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.role in [request.user.Role.ADMIN, request.user.Role.SUPERUSER]
        )


class IsAdminUser(permissions.BasePermission):
    """
    Custom permission to only allow normal admin users (not superuser).
    """
    
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.role == request.user.Role.ADMIN and
            not request.user.is_superuser
        )