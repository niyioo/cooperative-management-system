from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import MemberViewSet, NextOfKinViewSet, MemberDocumentViewSet

router = DefaultRouter()
router.register(r'profiles', MemberViewSet, basename='member')
router.register(r'next-of-kin', NextOfKinViewSet, basename='next_of_kin')
router.register(r'documents', MemberDocumentViewSet, basename='document')

urlpatterns = [
    path('', include(router.urls)),
]