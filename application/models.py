from django.db import models
from django.utils import timezone


class Application(models.Model):
    """
    Pre-screen application used for both "Apply Now" and "Refer Someone".
    - income_sources is a JSONField storing a list of values from IncomeSource choices.
    - Boolean fields use BooleanField(null=True) so we can represent unknown / not answered.
    """

    class ApplicationType(models.TextChoices):
        APPLY = "APPLY", "Apply Now"
        REFER = "REFER", "Refer Someone"

    class LivingSituation(models.TextChoices):
        HOMELESS = "HOMELESS", "Homeless / Shelter / Transitional Housing"
        HOTEL = "HOTEL", "Hotel / Extended Stay"
        WITH_FAMILY =  "Staying with Family or Friends"
        RENTING = "RENTING", "Renting / Own Home"
        OTHER = "OTHER", "Other"

    class NeedWhen(models.TextChoices):
        IMMEDIATELY = "IMMEDIATELY", "Immediately"
        WITHIN_30_DAYS = "WITHIN_30_DAYS", "Within 30 days"
        ONE_TO_THREE_MONTHS = "ONE_TO_THREE_MONTHS", "1-3 months"
        THREE_TO_SIX_MONTHS = "THREE_TO_SIX_MONTHS", "3-6 months"
        MORE_THAN_SIX_MONTHS = "MORE_THAN_6_MONTHS", "More than 6 months"
        NOT_SURE = "NOT_SURE", "Not sure yet"

    class IncomeSource(models.TextChoices):
        EMPLOYMENT = "EMPLOYMENT", "Employment"
        SOCIAL_SECURITY = "SOCIAL_SECURITY", "Social Security / SSI / SSDI"
        VA_BENEFITS = "VA_BENEFITS", "VA Benefits"
        PENSION = "PENSION", "Pension"
        HOUSING_VOUCHER = "HOUSING_VOUCHER", "Housing Voucher"
        OTHER = "OTHER", "Other"

    # Basic meta
    application_type = models.CharField(
        max_length=10,
        choices=ApplicationType.choices,
        default=ApplicationType.APPLY,
        help_text="Apply now or refer someone"
    )

    # Applicant personal info
    full_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)

    # Current housing
    living_situation = models.CharField(
        max_length=50,
        choices=LivingSituation.choices,
        blank=True,
        null=True
    )
    need_housing_when = models.CharField(
        max_length=30,
        choices=NeedWhen.choices,
        blank=True,
        null=True
    )
    lived_in_shared_before = models.BooleanField(null=True)

    # Program eligibility
    us_veteran = models.BooleanField(null=True)
    transitioning = models.BooleanField(null=True)  # from incarceration/rehab/program

    # Income & financials
    # stored as JSON list of IncomeSource values [Multiple income source]
    income_sources = models.JSONField(default=list, blank=True)
    income_consistent = models.BooleanField(null=True)
    can_provide_income_docs = models.BooleanField(null=True)

    # Shared housing & household guidelines in step - 2
    comfortable_shared = models.BooleanField(null=True)
    asked_to_leave_before = models.BooleanField(null=True)

    # Support & services
    has_case_manager = models.BooleanField(null=True)
    case_manager_name = models.CharField(max_length=255, blank=True, null=True)
    case_manager_contact = models.CharField(max_length=255, blank=True, null=True)

    # Shared housing & household guidelines in     step - 3
    willing_to_undergo_background_check = models.BooleanField(null=True)
    upcoming_court_dates = models.BooleanField(null=True)

    # Additional fields
    additional_info = models.TextField(blank=True, null=True)
    consent = models.BooleanField(default=False)
    signature_name = models.CharField(max_length=255, blank=True, null=True)
    signature_date = models.DateField(blank=True, null=True)

    # Referral fields (only required for ApplicationType.REFER)
    referral_full_name = models.CharField(max_length=255, blank=True, null=True)
    referral_email = models.EmailField(blank=True, null=True)
    referral_phone = models.CharField(max_length=30, blank=True, null=True)

    # Administrative
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Application"
        verbose_name_plural = "Applications"

    def __str__(self):
        return f"{self.full_name} ({self.application_type})"
