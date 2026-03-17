from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ContributionTypeViewSet, ContributionRecordViewSet, FineViewSet

router = DefaultRouter()
router.register(r'types', ContributionTypeViewSet, basename='contribution_type')
router.register(r'records', ContributionRecordViewSet, basename='contribution_record')
router.register(r'fines', FineViewSet, basename='fine')

urlpatterns = [
    path('', include(router.urls)),
]