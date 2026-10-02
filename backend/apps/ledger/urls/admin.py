from rest_framework.routers import SimpleRouter

from ..views.admin import BatchViewSet, TransactionViewSet

router = SimpleRouter()
router.register("transactions", TransactionViewSet, basename="transaction")
router.register("batches", BatchViewSet, basename="batch")

urlpatterns = router.urls
