from rest_framework.routers import SimpleRouter

from ..views.admin import InvestmentAccountViewSet, InvestmentProductViewSet, InvestmentReturnViewSet

router = SimpleRouter()
router.register("investments/products", InvestmentProductViewSet, basename="investment-product")
router.register("investments/accounts", InvestmentAccountViewSet, basename="investment-account")
router.register("investments/returns", InvestmentReturnViewSet, basename="investment-return")

urlpatterns = router.urls
