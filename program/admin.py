from django.contrib import admin
from .models import Program, ProgramSection


class ProgramSectionInline(admin.TabularInline):
    model = ProgramSection
    extra = 0
    fields = ("title", "description", "image")
    readonly_fields = ()
    ordering = ("created_at",)


@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "created_at")
    search_fields = ("name",)
    inlines = [ProgramSectionInline]
    readonly_fields = ("created_at", "updated_at")


@admin.register(ProgramSection)
class ProgramSectionAdmin(admin.ModelAdmin):
    list_display = ("id", "program", "title", "description", "created_at")
    list_filter = ("program",)
    search_fields = ("title", "description")
    readonly_fields = ("created_at", "updated_at")
    