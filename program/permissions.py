from rest_framework import permissions


class IsSuperUserOrAdminReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False

        # Superuser: allow everything (keep same check pattern you used)
        try:
            is_role_super = user.role == user.Role.SUPERUSER
        except Exception:
            is_role_super = False

        try:
            is_role_admin = user.role == user.Role.ADMIN
        except Exception:
            is_role_admin = False

        if is_role_super and getattr(user, "is_superuser", False):
            return True

        # Admins: only read-only access
        if request.method in permissions.SAFE_METHODS and is_role_admin:
            return True

        return False
    