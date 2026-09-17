from django.urls import path

from equipment import views

app_name = "equipment"

urlpatterns = [
    path("", views.EquipmentBoardView.as_view(), name="board"),
    path("reorder/", views.WorkshopReorderView.as_view(), name="workshop_reorder"),
    path("registry/", views.EquipmentListView.as_view(), name="equipment_list"),
    path("cameras/", views.CameraWallView.as_view(), name="cameras"),
    path("cameras/new/", views.CameraCreateView.as_view(), name="camera_create"),
    path("cameras/<int:pk>/delete/", views.CameraDeleteView.as_view(), name="camera_delete"),
    path("cameras/workshops/<int:pk>/", views.CameraWorkshopView.as_view(), name="camera_workshop"),
    path("workshops/<int:pk>/", views.WorkshopLinesView.as_view(), name="workshop_lines"),
    path("workshops/<int:pk>/reorder/", views.ProductionLineReorderView.as_view(), name="line_reorder"),
    path("lines/new/", views.ProductionLineCreateView.as_view(), name="line_create"),
    path("lines/<int:pk>/", views.LineEquipmentView.as_view(), name="line_equipment"),
    path("lines/<int:pk>/edit/", views.ProductionLineUpdateView.as_view(), name="line_update"),
    path("lines/<int:pk>/delete/", views.ProductionLineDeleteView.as_view(), name="line_delete"),
    path("new/", views.EquipmentCreateView.as_view(), name="equipment_create"),
    path("<int:pk>/", views.EquipmentDetailView.as_view(), name="equipment_detail"),
    path("<int:pk>/edit/", views.EquipmentUpdateView.as_view(), name="equipment_update"),
    path("<int:pk>/delete/", views.EquipmentDeleteView.as_view(), name="equipment_delete"),
    path("<int:pk>/status/", views.EquipmentStatusChangeView.as_view(), name="status_change"),
    path("<int:pk>/maintenance/", views.MaintenanceRecordCreateView.as_view(), name="maintenance_create"),
]
