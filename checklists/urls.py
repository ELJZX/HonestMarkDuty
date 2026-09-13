from django.urls import path

from checklists import views

app_name = "checklists"

urlpatterns = [
    path("", views.ChecklistListView.as_view(), name="checklist_list"),
    path("new/", views.ChecklistCreateView.as_view(), name="checklist_create"),
    path("<int:pk>/", views.ChecklistDetailView.as_view(), name="checklist_detail"),
    path("<int:pk>/edit/", views.ChecklistUpdateView.as_view(), name="checklist_update"),
    path("<int:pk>/generate/", views.ChecklistGenerateView.as_view(), name="checklist_generate"),
    path("<int:pk>/delete/", views.ChecklistDeleteView.as_view(), name="checklist_delete"),
]
