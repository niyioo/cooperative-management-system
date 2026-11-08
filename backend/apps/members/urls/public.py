from django.urls import path

from ..views.public import MembershipApplicationView, PublicDepartmentsView

urlpatterns = [
    path("membership-applications/", MembershipApplicationView.as_view(), name="membership-application"),
    path("departments/", PublicDepartmentsView.as_view(), name="departments"),
]
