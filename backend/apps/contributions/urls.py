from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ContributionViewSet

router = DefaultRouter()
# Maps to /contributions/
router.register(r'', ContributionViewSet, basename='contribution')

urlpatterns = [
    path('', include(router.urls)),
]