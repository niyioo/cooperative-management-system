from rest_framework.routers import SimpleRouter

from django.urls import path

from ..views import CooperativeSettingsView, DepartmentViewSet

router = SimpleRouter()
router.register("departments", DepartmentViewSet, basename="department")

urlpatterns = [
    path("settings/", CooperativeSettingsView.as_view(), name="settings"),
    *router.urls,
]
