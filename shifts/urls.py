from django.urls import path

from shifts import views

app_name = "shifts"

urlpatterns = [
    path("", views.ShiftListView.as_view(), name="shift_list"),
    path("open/", views.ShiftOpenView.as_view(), name="shift_open"),
    path("<int:pk>/", views.ShiftDetailView.as_view(), name="shift_detail"),
    path("<int:pk>/close/", views.ShiftCloseView.as_view(), name="shift_close"),
    path("<int:pk>/checks/add/", views.ShiftCheckCreateView.as_view(), name="check_create"),
]
