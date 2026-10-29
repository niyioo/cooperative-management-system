from rest_framework.routers import SimpleRouter

from ..views.admin import AnnouncementViewSet, BroadcastViewSet

router = SimpleRouter()
router.register("announcements", AnnouncementViewSet, basename="announcement")
router.register("messages", BroadcastViewSet, basename="message")

urlpatterns = router.urls
