from django.urls import path

from shifts import views

app_name = "shifts"

urlpatterns = [
    path("", views.ShiftListView.as_view(), name="shift_list"),
    path("open/", views.ShiftOpenView.as_view(), name="shift_open"),
    path("open/ajax/", views.shift_open_ajax, name="shift_open_ajax"),
    path("<int:pk>/", views.ShiftDetailView.as_view(), name="shift_detail"),
    path("<int:pk>/close/", views.ShiftCloseView.as_view(), name="shift_close"),
    path("<int:pk>/close/ajax/", views.shift_close_ajax, name="shift_close_ajax"),
    path("<int:pk>/checks/add/", views.ShiftCheckCreateView.as_view(), name="check_create"),
]
