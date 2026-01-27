from django.db import models
from django.utils import timezone


class Program(models.Model):
    """
    Program master. Created/edited/deleted only by superuser.
    """
    name = models.CharField(max_length=255)
    short_description = models.TextField(blank=True, null=True)
    feature_image = models.ImageField(upload_to='programs/feature_images/', blank=True, null=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Program"
        verbose_name_plural = "Programs"

    def __str__(self):
        return self.name


class ProgramSection(models.Model):
    """
    Section / content block that belongs to a Program.
    """
    program = models.ForeignKey(Program, related_name='sections', on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='programs/sections/', blank=True, null=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = "Program Section"
        verbose_name_plural = "Program Sections"

    def __str__(self):
        return f"{self.program.name} — {self.title}"
    