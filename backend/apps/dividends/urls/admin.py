from rest_framework.routers import SimpleRouter

from ..views.admin import DividendCycleViewSet

router = SimpleRouter()
router.register("dividends/cycles", DividendCycleViewSet, basename="dividend-cycle")

urlpatterns = router.urls
