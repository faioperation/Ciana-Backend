from django.contrib import admin
from .models import Application


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "full_name",
        "email",
        "application_type",
        "need_housing_when",
        "created_at",
    )
    list_filter = ("application_type", "need_housing_when", "created_at")
    search_fields = ("full_name", "email", "phone", "referral_full_name", "referral_email")
    readonly_fields = ("created_at", "updated_at")