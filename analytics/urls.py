from django.urls import path

from analytics import views

app_name = "analytics"

urlpatterns = [
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("statistics/", views.StatisticsView.as_view(), name="statistics"),
]
