from rest_framework import serializers
from .models import Application


class ApplicationSerializer(serializers.ModelSerializer):
    """
    Serializer for public application creation and admin read.
    - income_sources: list of predefined choice keys (e.g. "EMPLOYMENT", "PENSION", ...).
    - If application_type == REFER, referral fields are required.
    - consent must be True to submit.
    """
    income_sources = serializers.ListField(
        child=serializers.ChoiceField(choices=Application.IncomeSource.choices),
        required=False,
        allow_empty=True
    )

    date_of_birth = serializers.DateField(required=False, allow_null=True)
    signature_date = serializers.DateField(required=False, allow_null=True)

    class Meta:
        model = Application
        fields = [
            "id",
            "application_type",
            "full_name",
            "email",
            "phone",
            "date_of_birth",
            "living_situation",
            "need_housing_when",
            "lived_in_shared_before",
            "us_veteran",
            "transitioning",
            "income_sources",
            "income_consistent",
            "can_provide_income_docs",
            "comfortable_shared",
            "asked_to_leave_before",
            "has_case_manager",
            "case_manager_name",
            "case_manager_contact",
            "willing_to_undergo_background_check",
            "upcoming_court_dates",
            "additional_info",
            "consent",
            "signature_name",
            "signature_date",
            "referral_full_name",
            "referral_email",
            "referral_phone",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        # consent required
        consent = attrs.get("consent", None)
        if consent is False or consent is None:
            raise serializers.ValidationError({"consent": "Applicant must agree to consent to submit."})

        # If refer type, require referral fields
        app_type = attrs.get("application_type", getattr(self.instance, "application_type", None))
        if app_type == Application.ApplicationType.REFER:
            missing = []
            if not attrs.get("referral_full_name") and not getattr(self.instance, "referral_full_name", None):
                missing.append("referral_full_name")
            if not attrs.get("referral_email") and not getattr(self.instance, "referral_email", None):
                missing.append("referral_email")
            if not attrs.get("referral_phone") and not getattr(self.instance, "referral_phone", None):
                missing.append("referral_phone")
            if missing:
                raise serializers.ValidationError({f: "This field is required for Refer Someone." for f in missing})

        # Validate income_sources list elements are allowed choices (handled by ChoiceField child)
        return attrs

    def create(self, validated_data):
        # income_sources will be a list (JSONField accepts list)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        return super().update(instance, validated_data)