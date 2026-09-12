from django.urls import path

from core import views

app_name = "core"

urlpatterns = [
    path("", views.HomeView.as_view(), name="home"),
    path("audit/", views.AuditLogListView.as_view(), name="audit_list"),
    path("workshops/", views.WorkshopListView.as_view(), name="workshop_list"),
    path("workshops/new/", views.WorkshopCreateView.as_view(), name="workshop_create"),
    path("workshops/<int:pk>/edit/", views.WorkshopUpdateView.as_view(), name="workshop_update"),
    path("workshops/<int:pk>/delete/", views.WorkshopDeleteView.as_view(), name="workshop_delete"),
    path("sites/", views.ProductionSiteListView.as_view(), name="site_list"),
    path("sites/new/", views.ProductionSiteCreateView.as_view(), name="site_create"),
    path("sites/<int:pk>/edit/", views.ProductionSiteUpdateView.as_view(), name="site_update"),
    path("sites/<int:pk>/delete/", views.ProductionSiteDeleteView.as_view(), name="site_delete"),
]
