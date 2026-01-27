from rest_framework import viewsets, permissions, parsers
from rest_framework.response import Response
from rest_framework import status

from .models import Program, ProgramSection
from .permissions import IsSuperUserOrAdminReadOnly
from . import serializers


class ProgramViewSet(viewsets.ModelViewSet):
    queryset = Program.objects.all()
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]
    permission_classes = [IsSuperUserOrAdminReadOnly]

    def get_serializer_class(self):
        if self.request.method in permissions.SAFE_METHODS:
            return serializers.ProgramReadSerializer
        return serializers.ProgramWriteNestedSerializer

    def create(self, request, *args, **kwargs):
        # validate & save using the write serializer (this is the default behavior)
        write_serializer = self.get_serializer(data=request.data)
        write_serializer.is_valid(raise_exception=True)
        program = write_serializer.save()

        # return representation using the read serializer (includes nested sections)
        read_serializer = serializers.ProgramReadSerializer(program, context={"request": request})
        headers = self.get_success_headers(read_serializer.data)
        return Response(read_serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()

        write_serializer = self.get_serializer(instance, data=request.data, partial=partial)
        write_serializer.is_valid(raise_exception=True)
        program = write_serializer.save()

        read_serializer = serializers.ProgramReadSerializer(program, context={"request": request})
        return Response(read_serializer.data, status=status.HTTP_200_OK)


class ProgramSectionViewSet(viewsets.ModelViewSet):
    queryset = ProgramSection.objects.all()
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]
    permission_classes = [IsSuperUserOrAdminReadOnly]

    def get_serializer_class(self):
        if self.request.method in permissions.SAFE_METHODS:
            return serializers.ProgramSectionReadSerializer
        return serializers.ProgramSectionWriteSerializer