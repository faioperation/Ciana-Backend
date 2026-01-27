from django.urls import reverse
from django.conf import settings
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
import logging

from rest_framework import generics
from rest_framework.permissions import AllowAny, IsAuthenticated

from .models import Application
from .serializers import ApplicationSerializer

from .paginations import ApplicationPagination

from user.permissions import IsSuperUser, IsAdminOrSuperUser

logger = logging.getLogger(__name__)
User = get_user_model()

class ApplicationCreateView(generics.CreateAPIView):
    """
    Public endpoint to submit an application (Apply Now or Refer Someone).
    No authentication required. Notifies superusers by email when a new
    application is created.
    """
    queryset = Application.objects.all()
    serializer_class = ApplicationSerializer
    permission_classes = [AllowAny]

    def perform_create(self, serializer):
        # Save the application object
        app = serializer.save()

        # Build a short summary for the email
        def safe_display(value):
            return str(value) if value is not None else ""

        summary_lines = [
            f"Applicant: {safe_display(app.full_name)}",
            f"Application type: {safe_display(app.application_type)}",
            f"Email: {safe_display(app.email)}",
            f"Phone: {safe_display(app.phone)}",
            f"Need housing when: {safe_display(app.need_housing_when)}",
            f"Living situation: {safe_display(app.living_situation)}",
            f"Income sources: {', '.join(app.income_sources) if app.income_sources else ''}",
            f"Has case manager: {safe_display(app.has_case_manager)}",
            f"Additional info: {safe_display(app.additional_info)}",
            f"Submitted at: {safe_display(app.created_at)}",
        ]
        summary_text = "\n".join(summary_lines)

        subject = f"[New Application] {app.full_name}"

        text_body = (
            "New Application Submitted\n\n"
            "A new application has been submitted.\n\n"
            "Details:\n"
            "-------------------------\n"
            f"{summary_text}\n"
            "-------------------------\n\n"
            "Please log in to the admin panel to review and take action.\n\n"
            "— Star Light Path System"
        )

        html_body = f"""
        <div style="font-family: Arial, Helvetica, sans-serif; color: #111; line-height: 1.6;">
            <h2 style="margin-bottom: 8px;">New Application Submitted</h2>

            <p style="margin-top: 0;">
                A new application has been submitted. Details are below:
            </p>

            <div style="background: #f7f7f7; padding: 12px 16px; border-radius: 6px;">
                <pre style="margin: 0; white-space: pre-wrap; font-family: inherit;">{summary_text}</pre>
            </div>

            <p style="margin-top: 16px; font-size: 14px; color: #555;">
                Please log in to the admin panel to review and take action.
            </p>

            <p style="font-size: 13px; color: #888;">
                — Star Light Path System
            </p>
        </div>
        """


        # Collect superuser emails
        superuser_qs = User.objects.filter(is_active=True, is_superuser=True).exclude(email__isnull=True).exclude(email__exact="")
        recipient_list = list(superuser_qs.values_list("email", flat=True))

        # If there are no superusers with email, just log and return
        if not recipient_list:
            logger.warning("New application created but no superuser emails found to notify.")
            return

        # Use DEFAULT_FROM_EMAIL if set, otherwise fallback to settings.SERVER_EMAIL or empty
        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None) or getattr(settings, "SERVER_EMAIL", None) or None

        # Send email (do not raise on failure)
        try:
            send_mail(
                subject=subject,
                message=text_body,
                from_email=from_email,
                recipient_list=recipient_list,
                fail_silently=False,
                html_message=html_body,
            )
            logger.info("Notified superusers (%d) about new application id=%s", len(recipient_list), app.pk)
        except Exception as e:
            # Log exception but do not block the request/creation
            logger.exception("Failed to send new-application notification for application id=%s: %s", app.pk, e)


class ApplicationListView(generics.ListAPIView):
    """
    Admin-only listing of applications.
    """
    queryset = Application.objects.all().order_by("-created_at")
    serializer_class = ApplicationSerializer
    pagination_class = ApplicationPagination
    permission_classes = [IsAuthenticated, IsAdminOrSuperUser]


class ApplicationDetailView(generics.RetrieveAPIView):
    """
    Admin-only retrieve single application.
    """
    queryset = Application.objects.all()
    serializer_class = ApplicationSerializer
    permission_classes = [IsAuthenticated, IsAdminOrSuperUser]