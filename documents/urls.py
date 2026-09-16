from django.urls import path

from documents import views

app_name = "documents"

urlpatterns = [
    path("", views.DocumentListView.as_view(), name="document_list"),
    path("new/", views.DocumentCreateView.as_view(), name="document_create"),
    path(
        "download/<slug:code>/<str:kind>/",
        views.WorkshopDocumentDownloadView.as_view(),
        name="workshop_document_download",
    ),
    path("<int:pk>/", views.DocumentDetailView.as_view(), name="document_detail"),
    path("<int:pk>/edit/", views.DocumentUpdateView.as_view(), name="document_update"),
    path("<int:pk>/print/", views.DocumentPrintView.as_view(), name="document_print"),
    path("<int:pk>/download/", views.DocumentDownloadView.as_view(), name="document_download"),
    path("<int:pk>/regenerate/", views.DocumentRegenerateView.as_view(), name="document_regenerate"),
    path("<int:pk>/delete/", views.DocumentDeleteView.as_view(), name="document_delete"),
    path("templates/", views.DocumentTemplateListView.as_view(), name="template_list"),
    path("templates/new/", views.DocumentTemplateCreateView.as_view(), name="template_create"),
    path("templates/<int:pk>/edit/", views.DocumentTemplateUpdateView.as_view(), name="template_update"),
    path("templates/<int:pk>/delete/", views.DocumentTemplateDeleteView.as_view(), name="template_delete"),
]
