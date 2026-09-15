from django.urls import path

from checklists import views

app_name = "checklists"

urlpatterns = [
    path("", views.ChecklistHubView.as_view(), name="hub"),
    path("znak/", views.ChecklistListView.as_view(), name="checklist_list"),
    path("znak/new/", views.ChecklistCreateView.as_view(), name="checklist_create"),
    path("znak/<int:pk>/", views.ChecklistDetailView.as_view(), name="checklist_detail"),
    path("znak/<int:pk>/edit/", views.ChecklistUpdateView.as_view(), name="checklist_update"),
    path("znak/<int:pk>/close/", views.ChecklistCloseView.as_view(), name="checklist_close"),
    path("znak/<int:pk>/download/", views.ChecklistDownloadView.as_view(), name="checklist_download"),
    path("znak/<int:pk>/generate/", views.ChecklistGenerateView.as_view(), name="checklist_generate"),
    path("znak/<int:pk>/delete/", views.ChecklistDeleteView.as_view(), name="checklist_delete"),
    path("markem/", views.MarkemChecklistView.as_view(), name="markem"),
    path("markem/new/", views.MarkemCreateView.as_view(), name="markem_create"),
    path("markem/<int:pk>/edit/", views.MarkemUpdateView.as_view(), name="markem_update"),
    path("markem/<int:pk>/close/", views.MarkemCloseView.as_view(), name="markem_close"),
    path("markem/<int:pk>/download/", views.MarkemDownloadView.as_view(), name="markem_download"),
    path("markem/<int:pk>/delete/", views.MarkemDeleteView.as_view(), name="markem_delete"),
]
