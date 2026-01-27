from django.db import transaction
import json

from rest_framework import serializers

from .models import Program, ProgramSection


class ProgramSectionReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProgramSection
        fields = ("id", "program", "title", "description", "image", "created_at", "updated_at")


class ProgramReadSerializer(serializers.ModelSerializer):
    sections = ProgramSectionReadSerializer(many=True, read_only=True)

    class Meta:
        model = Program
        fields = (
            "id",
            "name",
            "short_description",
            "feature_image",
            "sections",
            "created_at",
            "updated_at",
        )


class ProgramWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Program
        fields = ("id", "name", "short_description", "feature_image")
        read_only_fields = ("id",)


class ProgramSectionWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProgramSection
        fields = ("id", "program", "title", "description", "image")
        read_only_fields = ("id",)


# Nested write serializer for Program that accepts program_sections as JSON in multipart/form-data.
# program_sections JSON structure (example):
# [
#   {"title": "Section 1", "description": "Desc", "image_key": "section1_image"},
#   {"title": "Section 2", "description": "Desc", "image_key": "section2_image"}
# ]
class ProgramWriteNestedSerializer(serializers.ModelSerializer):
    # Accept a JSON string for sections (useful for multipart form-data)
    program_sections = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = Program
        fields = ("id", "name", "short_description", "feature_image", "program_sections",)
        read_only_fields = ("id",)

    @transaction.atomic
    def create(self, validated_data):
        request = self.context.get("request")
        # print("DATA:", request.data)
        # print("FILES:", request.FILES)
        files = getattr(request, "FILES", {})

        program_sections_raw = validated_data.pop("program_sections", "[]")
        # print("PROGRAM SECTIONS RAW:", program_sections_raw)

        try:
            program_sections_data = json.loads(program_sections_raw) if program_sections_raw else []
        except json.JSONDecodeError:
            raise serializers.ValidationError({"program_sections": "Invalid JSON."})

        # Create Program
        program = Program.objects.create(**validated_data)

        # Create sections and attach image(s) if provided via file keys
        for idx, section_data in enumerate(program_sections_data):
            image_key = section_data.get("image_key")

            section = ProgramSection.objects.create(
                program=program,
                title=section_data.get("title", ""),
                description=section_data.get("description", ""),
            )

            chosen_key = None
            if image_key:
                chosen_key = image_key

            if chosen_key:
                if chosen_key not in files:
                    raise serializers.ValidationError(
                        {"program_sections": f"Missing file for key '{chosen_key}' for section index {idx}."}
                    )
                section.image = files[chosen_key]
                section.save()

        return program

    @transaction.atomic
    def update(self, instance, validated_data):
        # Basic update for program fields; nested section updates can be implemented as needed.
        # For now, this mirrors the flat ProgramWriteSerializer behavior.
        program_sections_raw = validated_data.pop("program_sections", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if program_sections_raw:
            # If user provided program_sections on update, treat it as "add new sections".
            try:
                program_sections_data = json.loads(program_sections_raw) if program_sections_raw else []
            except json.JSONDecodeError:
                raise serializers.ValidationError({"program_sections": "Invalid JSON."})

            request = self.context.get("request")
            files = getattr(request, "FILES", {})

            for idx, section_data in enumerate(program_sections_data):
                image_key = section_data.get("image_key")
                image_keys = section_data.get("image_keys", [])

                section = ProgramSection.objects.create(
                    program=instance,
                    title=section_data.get("title", ""),
                    description=section_data.get("description", ""),
                )

                chosen_key = image_key or (image_keys[0] if image_keys else None)
                if chosen_key:
                    if chosen_key not in files:
                        raise serializers.ValidationError(
                            {"program_sections": f"Missing file for key '{chosen_key}' for section index {idx}."}
                        )
                    section.image = files[chosen_key]
                    section.save()

        return instance
    