from django.urls import path

from journal import views

app_name = "journal"

urlpatterns = [
    path("", views.JournalEntryListView.as_view(), name="entry_list"),
    path("new/", views.JournalEntryCreateView.as_view(), name="entry_create"),
    path("<int:pk>/edit/", views.JournalEntryUpdateView.as_view(), name="entry_update"),
    path("<int:pk>/delete/", views.JournalEntryDeleteView.as_view(), name="entry_delete"),
    path("exports/", views.JournalExportListView.as_view(), name="export_list"),
    path("exports/create/", views.JournalExportCreateView.as_view(), name="export_create"),
    path("exports/period/", views.JournalPeriodExportView.as_view(), name="export_period"),
    path(
        "shifts/<int:pk>/export/",
        views.JournalShiftExportView.as_view(),
        name="shift_export",
    ),
]
