from rest_framework.routers import DefaultRouter
from django.urls import path, include

from .views import ProgramViewSet, ProgramSectionViewSet

router = DefaultRouter()
router.register(r"programs", ProgramViewSet, basename="program")
router.register(r"program-sections", ProgramSectionViewSet, basename="programsection")

urlpatterns = [
    path("", include(router.urls)),
]
