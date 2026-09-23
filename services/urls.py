from django.urls import path

from services import views

app_name = "services"

urlpatterns = [
    path("", views.ServiceListView.as_view(), name="service_list"),
    path("new/", views.ServiceCreateView.as_view(), name="service_create"),
    path("<int:pk>/delete/", views.ServiceDeleteView.as_view(), name="service_delete"),
]
