from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/auth/', include('apps.accounts.urls')),
    path('api/v1/members/', include('apps.members.urls')),
    path('api/v1/savings/', include('apps.savings.urls')),
    path('api/v1/loans/', include('apps.loans.urls')),
    path('api/v1/shares/', include('apps.shares.urls')),
    path('api/v1/contributions/', include('apps.contributions.urls')),
    path('api/v1/finance/', include('apps.finance.urls')),
    path('api/v1/reports/', include('apps.reports.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)