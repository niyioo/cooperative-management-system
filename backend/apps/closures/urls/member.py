from rest_framework.routers import SimpleRouter

from ..views.member import MyClosureRequestViewSet

router = SimpleRouter()
router.register("closure-requests", MyClosureRequestViewSet, basename="my-closure-request")

urlpatterns = router.urls
