from rest_framework.routers import SimpleRouter

from ..views.admin import ClosureRequestViewSet

router = SimpleRouter()
router.register("closure-requests", ClosureRequestViewSet, basename="closure-request")

urlpatterns = router.urls
