from rest_framework.routers import SimpleRouter

from ..views.admin import MemberImportViewSet, MemberViewSet

router = SimpleRouter()
# Registered before "members" so /members/imports/ is never read as a member id.
router.register("members/imports", MemberImportViewSet, basename="member-import")
router.register("members", MemberViewSet, basename="member")

urlpatterns = router.urls
