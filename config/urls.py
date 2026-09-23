from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls")),
    path("accounts/", include("accounts.urls")),
    path("inventory/", include("inventory.urls")),
    path("shifts/", include("shifts.urls")),
    path("journal/", include("journal.urls")),
    path("checklists/", include("checklists.urls")),
    path("documents/", include("documents.urls")),
    path("equipment/", include("equipment.urls")),
    path("analytics/", include("analytics.urls")),
    path("services/", include("services.urls")),
]

handler403 = "core.views.forbidden"
handler404 = "core.views.not_found"
handler500 = "core.views.server_error"

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

admin.site.site_header = "HonestMarkDuty — администрирование"
admin.site.site_title = "HonestMarkDuty"
admin.site.index_title = "Управление системой"
