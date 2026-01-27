from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.admin import AdminSite
from django.utils.translation import gettext_lazy as _
from .models import Users


# Custom Admin Site for Normal Admins (Read-Only)
class ReadOnlyAdminSite(AdminSite):
    site_header = "Admin Dashboard (Read-Only)"
    site_title = "Admin Portal"
    index_title = "Welcome to Admin Dashboard"

    def has_permission(self, request):
        """
        Only allow users with ADMIN role
        """
        return (
            request.user.is_active 
            and request.user.is_staff
            and request.user.role == Users.Role.ADMIN
        )


# Create instance of custom admin site
readonly_admin_site = ReadOnlyAdminSite(name='readonly_admin')


# Custom User Admin for Superuser (Full Access)
class CustomUserAdmin(BaseUserAdmin):
    model = Users
    list_display = ['email', 'full_name', 'role', 'is_active', 'is_staff', 'date_joined']
    list_filter = ['role', 'is_active', 'is_staff', 'date_joined']
    search_fields = ['email', 'full_name', 'contact_number']
    ordering = ['-date_joined']

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Personal Info'), {'fields': ('full_name', 'contact_number', 'image')}),
        (_('Permissions'), {
            'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        (_('Important dates'), {'fields': ('last_login', 'date_joined', 'updated_at')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'full_name', 'password1', 'password2', 'role', 'is_active'),
        }),
    )

    readonly_fields = ['date_joined', 'updated_at', 'last_login']

    def get_readonly_fields(self, request, obj=None):
        """
        Superusers can edit everything, normal admins cannot edit anything
        """
        if request.user.role == Users.Role.SUPERUSER:
            return self.readonly_fields
        return [f.name for f in self.model._meta.fields]

    def has_add_permission(self, request):
        """Only superusers can add users"""
        return request.user.role == Users.Role.SUPERUSER

    def has_delete_permission(self, request, obj=None):
        """Only superusers can delete users"""
        return request.user.role == Users.Role.SUPERUSER

    def has_change_permission(self, request, obj=None):
        """Superusers can change, admins can only view"""
        return request.user.is_staff
    
    def save_model(self, request, obj, form, change):
        """
        Auto-set is_staff and is_superuser based on role
        """
        if obj.role == Users.Role.ADMIN:
            obj.is_staff = True
            obj.is_superuser = False
        elif obj.role == Users.Role.SUPERUSER:
            obj.is_staff = True
            obj.is_superuser = True
        else:  # USER
            obj.is_staff = False
            obj.is_superuser = False
        
        super().save_model(request, obj, form, change)


# Read-Only User Admin for Normal Admins
class ReadOnlyUserAdmin(CustomUserAdmin):
    """
    Read-only version for normal admins
    """
    def get_readonly_fields(self, request, obj=None):
        """Make all fields read-only"""
        return [f.name for f in self.model._meta.fields] + ['last_login']

    def has_add_permission(self, request):
        """Normal admins cannot add users"""
        return False

    def has_delete_permission(self, request, obj=None):
        """Normal admins cannot delete users"""
        return False

    def has_change_permission(self, request, obj=None):
        """Normal admins can view but not change"""
        if obj is None:
            return True  # Can view list
        return False  # Cannot edit


# Register models
admin.site.register(Users, CustomUserAdmin)
readonly_admin_site.register(Users, ReadOnlyUserAdmin)