from django.urls import path
from .views import (
    ApplicationCreateView,
    ApplicationListView,
    ApplicationDetailView,
    ApplicationUpdateView,
)

app_name = "appliction"

urlpatterns = [
    # Public: create application
    path("new/", ApplicationCreateView.as_view(), name="application-create"),

    # Admin: list & detail
    path("list/", ApplicationListView.as_view(), name="application-list"),
    path("<int:pk>/", ApplicationDetailView.as_view(), name="application-detail"),
    path("<int:pk>/update", ApplicationUpdateView.as_view(), name="application-status-update"),
]