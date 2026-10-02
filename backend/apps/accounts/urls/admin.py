from django.urls import path
from rest_framework.routers import SimpleRouter

from ..views import admin as views

router = SimpleRouter()
router.register("officers", views.OfficerViewSet, basename="officer")
router.register("roles", views.RoleViewSet, basename="role")

urlpatterns = [
    path("permissions/", views.PermissionCatalogueView.as_view(), name="permission-catalogue"),
    *router.urls,
]
