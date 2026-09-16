from django.urls import path

from equipment import views

app_name = "equipment"

urlpatterns = [
    path("", views.EquipmentBoardView.as_view(), name="board"),
    path("registry/", views.EquipmentListView.as_view(), name="equipment_list"),
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
    path("categories/", views.EquipmentCategoryListView.as_view(), name="category_list"),
    path("categories/new/", views.EquipmentCategoryCreateView.as_view(), name="category_create"),
    path("categories/<int:pk>/edit/", views.EquipmentCategoryUpdateView.as_view(), name="category_update"),
]
