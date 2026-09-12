from django.urls import path

from journal import views

app_name = "journal"

urlpatterns = [
    path("", views.JournalEntryListView.as_view(), name="entry_list"),
    path("new/", views.JournalEntryCreateView.as_view(), name="entry_create"),
    path("<int:pk>/", views.JournalEntryDetailView.as_view(), name="entry_detail"),
    path("<int:pk>/edit/", views.JournalEntryUpdateView.as_view(), name="entry_update"),
    path("exports/", views.JournalExportListView.as_view(), name="export_list"),
    path("exports/create/", views.JournalExportCreateView.as_view(), name="export_create"),
]
