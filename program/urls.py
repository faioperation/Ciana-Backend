from rest_framework.routers import DefaultRouter
from django.urls import path, include

from .views import ProgramViewSet, ProgramSectionViewSet
from .views import PublicProgramListView, PublicProgramDetailView

router = DefaultRouter()
router.register(r"programs", ProgramViewSet, basename="program")
router.register(r"program-sections", ProgramSectionViewSet, basename="programsection")

urlpatterns = [
    path("", include(router.urls)),

    path("public/programs/", PublicProgramListView.as_view(), name="public-program-list"),
    path("public/programs/<int:pk>/", PublicProgramDetailView.as_view(), name="public-program-detail"),
]
