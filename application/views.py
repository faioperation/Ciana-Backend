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
        app = serializer.save()

        def safe_display(value):
            return str(value) if value not in [None, ""] else "N/A"

        income_sources = (
            ", ".join(app.income_sources)
            if isinstance(app.income_sources, list)
            else safe_display(app.income_sources)
        )

        case_manager_status = (
            "Yes"
            if app.has_case_manager is True
            else "No"
            if app.has_case_manager is False
            else "N/A"
        )

        summary_lines = [
            f"Applicant: {safe_display(app.full_name)}",
            f"Application type: {safe_display(app.application_type)}",
            f"Email: {safe_display(app.email)}",
            f"Phone: {safe_display(app.phone)}",
            f"Need housing when: {safe_display(app.need_housing_when)}",
            f"Living situation: {safe_display(app.living_situation)}",
            f"Income sources: {income_sources}",
            f"Has case manager, social worker, or VA coordinator?: {case_manager_status}",
            f"Additional info: {safe_display(app.additional_info)}",
            f"Submitted at: {safe_display(app.created_at)}",
        ]

        summary_text = "\n".join(summary_lines)

        subject = f"[New Application] {app.full_name}"

        text_body = f"""
    New Application Submitted

    A new application has been submitted.

    Details:
    -------------------------
    {summary_text}
    -------------------------

    Please log in to the admin panel to review and take action.

    — Star Light Path System
    """

        html_body = f"""
        <div style="font-family: Arial, Helvetica, sans-serif; color: #111; line-height: 1.6; max-width: 700px;">
            <h2 style="margin-bottom: 8px;">
                New Application Submitted
            </h2>

            <p>
                A new application has been submitted. Details are below:
            </p>

            <div style="
                background: #f7f7f7;
                padding: 16px;
                border-radius: 8px;
                border: 1px solid #e5e5e5;
            ">
                <pre style="
                    margin: 0;
                    white-space: pre-wrap;
                    font-family: Arial, Helvetica, sans-serif;
                ">{summary_text}</pre>
            </div>

            <div style="margin-top: 24px;">
                <p style="font-size: 14px; color: #555;">
                    Please log in to the admin panel to review and take action.
                </p>

                <a
                    href="https://starlightpath.org/admin/login"
                    style="
                        display: inline-block;
                        padding: 12px 24px;
                        background-color: #2563eb;
                        color: #ffffff;
                        text-decoration: none;
                        border-radius: 6px;
                        font-weight: 600;
                    "
                >
                    Login to Admin Panel
                </a>
            </div>

            <p style="margin-top: 24px; font-size: 13px; color: #888;">
                — Star Light Path System
            </p>
        </div>
        """

        superuser_qs = (
            User.objects.filter(
                is_active=True,
                is_superuser=True
            )
            .exclude(email__isnull=True)
            .exclude(email__exact="")
        )

        recipient_list = list(
            superuser_qs.values_list("email", flat=True)
        )

        if not recipient_list:
            logger.warning(
                "New application created but no superuser emails found."
            )
            return

        from_email = (
            getattr(settings, "DEFAULT_FROM_EMAIL", None)
            or getattr(settings, "SERVER_EMAIL", None)
            or settings.EMAIL_HOST_USER
        )

        logger.info(
            "Sending application notification email to: %s",
            recipient_list
        )

        try:
            send_mail(
                subject=subject,
                message=text_body,
                from_email=from_email,
                recipient_list=recipient_list,
                fail_silently=False,
                html_message=html_body,
            )

            logger.info(
                "Application notification sent successfully. Application ID=%s",
                app.pk,
            )

        except Exception:
            logger.exception(
                "Failed to send application notification. Application ID=%s",
                app.pk,
            )

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


class ApplicationUpdateView(generics.UpdateAPIView):
    """
    Update application status (archive/unarchive) by ID
    """

    queryset = Application.objects.all()
    serializer_class = ApplicationSerializer
    permission_classes = [IsAuthenticated, IsAdminOrSuperUser]  