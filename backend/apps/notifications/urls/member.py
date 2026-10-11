from django.urls import path
from rest_framework.routers import SimpleRouter

from ..views.member import MyAnnouncementsView, MyNotificationViewSet

router = SimpleRouter()
router.register("notifications", MyNotificationViewSet, basename="my-notification")

urlpatterns = [
    path("announcements/", MyAnnouncementsView.as_view(), name="announcements"),
    *router.urls,
]
