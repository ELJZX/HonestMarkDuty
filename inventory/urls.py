from django.urls import path

from inventory import views

app_name = "inventory"

urlpatterns = [
    path("", views.InventoryItemListView.as_view(), name="item_list"),
    path("new/", views.InventoryItemCreateView.as_view(), name="item_create"),
    path("<int:pk>/", views.InventoryItemDetailView.as_view(), name="item_detail"),
    path("<int:pk>/edit/", views.InventoryItemUpdateView.as_view(), name="item_update"),
    path("<int:pk>/delete/", views.InventoryItemDeleteView.as_view(), name="item_delete"),
    path("<int:pk>/movement/", views.InventoryMovementCreateView.as_view(), name="movement_create"),
    path("locations/", views.StorageLocationListView.as_view(), name="location_list"),
    path("locations/new/", views.StorageLocationCreateView.as_view(), name="location_create"),
    path("locations/<int:pk>/edit/", views.StorageLocationUpdateView.as_view(), name="location_update"),
    path("categories/", views.ItemCategoryListView.as_view(), name="category_list"),
    path("categories/new/", views.ItemCategoryCreateView.as_view(), name="category_create"),
    path("categories/<int:pk>/edit/", views.ItemCategoryUpdateView.as_view(), name="category_update"),
]
