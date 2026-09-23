from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, F, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
    View,
)

from core.mixins import AdminRequiredMixin, EditorRequiredMixin
from inventory.forms import (
    InventoryItemForm,
    InventoryMovementForm,
    ItemCategoryForm,
    ItemTypeForm,
    StorageForm,
    StorageLocationForm,
)
from inventory.models import (
    Condition,
    InventoryItem,
    ItemCategory,
    ItemType,
    Storage,
    StorageLocation,
)


class InventoryBoardView(LoginRequiredMixin, ListView):
    """Доска складов."""

    model = Storage
    template_name = "inventory/board.html"
    context_object_name = "storages"

    def get_queryset(self):
        return (
            Storage.objects.annotate(
                items_total=Count("items", filter=Q(items__is_active=True))
            )
            .order_by("sort_order", "name")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["items_total"] = InventoryItem.objects.filter(is_active=True).count()
        ctx["no_storage_total"] = InventoryItem.objects.filter(
            is_active=True, storage__isnull=True
        ).count()
        return ctx


class InventoryStorageTypesView(LoginRequiredMixin, DetailView):
    """Типы позиций внутри склада."""

    model = Storage
    template_name = "inventory/storage_types.html"
    context_object_name = "storage"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["types"] = (
            ItemType.objects.annotate(
                items_total=Count(
                    "items",
                    filter=Q(items__is_active=True, items__storage=self.object),
                )
            ).order_by("sort_order", "name")
        )
        ctx["items_total"] = InventoryItem.objects.filter(
            is_active=True, storage=self.object
        ).count()
        return ctx


class InventoryItemListView(LoginRequiredMixin, ListView):
    model = InventoryItem
    template_name = "inventory/item_list.html"
    context_object_name = "items"
    paginate_by = 25

    def get(self, request, *args, **kwargs):
        # живой поиск: отдаём только результаты без перезагрузки страницы
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            self.object_list = self.get_queryset()
            context = self.get_context_data()
            return render(request, "inventory/partials/items_results.html", context)
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        qs = InventoryItem.objects.select_related(
            "category", "location", "location__workshop", "storage", "kind"
        )
        params = self.request.GET
        query = params.get("q")
        kind = params.get("kind")
        condition = params.get("condition")
        location = params.get("location")
        category = params.get("category")
        storage = params.get("storage")
        low = params.get("low")
        if query:
            qs = qs.filter(
                Q(name__icontains=query)
                | Q(inventory_number__icontains=query)
                | Q(serial_number__icontains=query)
            )
        if kind:
            qs = qs.filter(kind=kind)
        if condition:
            qs = qs.filter(condition=condition)
        if location:
            qs = qs.filter(location_id=location)
        if category:
            qs = qs.filter(category_id=category)
        if storage:
            qs = qs.filter(storage_id=storage)
        if low:
            qs = qs.filter(quantity__lte=F("min_quantity"))
        if params.get("no_kind"):
            qs = qs.filter(kind__isnull=True)
        if params.get("no_storage"):
            qs = qs.filter(storage__isnull=True)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["kinds"] = ItemType.objects.all()
        ctx["storages"] = Storage.objects.all()
        ctx["conditions"] = Condition.choices
        ctx["locations"] = StorageLocation.objects.select_related("workshop")
        ctx["categories"] = ItemCategory.objects.all()
        ctx["current"] = self.request.GET
        ctx["stats"] = {
            "total": InventoryItem.objects.count(),
            "low": InventoryItem.objects.filter(quantity__lte=F("min_quantity")).count(),
            "worn": InventoryItem.objects.filter(
                condition__in=[Condition.WORN, Condition.NEEDS_REPAIR, Condition.BROKEN]
            ).count(),
        }
        return ctx


class InventoryItemDetailView(LoginRequiredMixin, DetailView):
    model = InventoryItem
    template_name = "inventory/item_detail.html"
    context_object_name = "item"

    def get_queryset(self):
        return InventoryItem.objects.select_related("category", "location", "location__workshop")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["movements"] = self.object.movements.select_related("created_by", "shift")[:50]
        ctx["movement_form"] = InventoryMovementForm()
        return ctx


class InventoryItemCreateView(EditorRequiredMixin, CreateView):
    model = InventoryItem
    form_class = InventoryItemForm
    template_name = "inventory/item_form.html"
    extra_context = {"title": "Новая позиция склада", "back_url": "inventory:item_list"}

    def form_valid(self, form):
        messages.success(self.request, "Позиция добавлена.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("inventory:item_detail", args=[self.object.pk])


class InventoryItemUpdateView(AdminRequiredMixin, UpdateView):
    model = InventoryItem
    form_class = InventoryItemForm
    template_name = "inventory/item_form.html"
    extra_context = {"title": "Редактирование позиции", "back_url": "inventory:item_list"}

    def form_valid(self, form):
        messages.success(self.request, "Изменения сохранены.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("inventory:item_detail", args=[self.object.pk])


class InventoryItemTypeChangeView(AdminRequiredMixin, View):
    """Быстрая смена типа позиции прямо из списка (только администратор)."""

    def post(self, request, pk):
        item = get_object_or_404(InventoryItem, pk=pk)
        kind_id = request.POST.get("kind")
        item.kind = ItemType.objects.filter(pk=kind_id).first() if kind_id else None
        item.save(update_fields=["kind", "updated_at"])
        messages.success(request, "Тип обновлён.")
        return redirect(request.META.get("HTTP_REFERER") or reverse("inventory:item_list"))


class InventoryItemDeleteView(AdminRequiredMixin, DeleteView):
    model = InventoryItem
    template_name = "core/confirm_delete.html"
    success_url = reverse_lazy("inventory:item_list")


class InventoryMovementCreateView(EditorRequiredMixin, View):
    def post(self, request, pk):
        item = get_object_or_404(InventoryItem, pk=pk)
        form = InventoryMovementForm(request.POST)
        if form.is_valid():
            movement = form.save(commit=False)
            movement.item = item
            movement.created_by = request.user
            movement.save()
            movement.apply()
            messages.success(
                request, f"{movement.get_movement_type_display()}: {item.name} → {item.quantity} {item.unit}"
            )
        else:
            messages.error(request, "Не удалось применить движение. Проверьте данные.")
        return redirect("inventory:item_detail", pk=pk)


class StorageLocationListView(LoginRequiredMixin, ListView):
    model = StorageLocation
    template_name = "inventory/location_list.html"
    context_object_name = "locations"

    def get_queryset(self):
        return StorageLocation.objects.select_related("workshop").prefetch_related("items")


class StorageLocationCreateView(EditorRequiredMixin, CreateView):
    model = StorageLocation
    form_class = StorageLocationForm
    template_name = "inventory/location_form.html"
    success_url = reverse_lazy("inventory:location_list")
    extra_context = {"title": "Новое место хранения", "back_url": "inventory:location_list"}


class StorageLocationUpdateView(AdminRequiredMixin, UpdateView):
    model = StorageLocation
    form_class = StorageLocationForm
    template_name = "inventory/location_form.html"
    success_url = reverse_lazy("inventory:location_list")
    extra_context = {"title": "Редактирование места хранения", "back_url": "inventory:location_list"}


class ItemCategoryListView(LoginRequiredMixin, ListView):
    model = ItemCategory
    template_name = "inventory/category_list.html"
    context_object_name = "categories"


class ItemCategoryCreateView(EditorRequiredMixin, CreateView):
    model = ItemCategory
    form_class = ItemCategoryForm
    template_name = "inventory/category_form.html"
    success_url = reverse_lazy("inventory:category_list")
    extra_context = {"title": "Новая категория", "back_url": "inventory:category_list"}


class ItemCategoryUpdateView(AdminRequiredMixin, UpdateView):
    model = ItemCategory
    form_class = ItemCategoryForm
    template_name = "inventory/category_form.html"
    success_url = reverse_lazy("inventory:category_list")
    extra_context = {"title": "Редактирование категории", "back_url": "inventory:category_list"}


class StorageListView(LoginRequiredMixin, ListView):
    model = Storage
    template_name = "inventory/storage_list.html"
    context_object_name = "storages"


class StorageCreateView(AdminRequiredMixin, CreateView):
    model = Storage
    form_class = StorageForm
    template_name = "inventory/storage_form.html"
    success_url = reverse_lazy("inventory:board")
    extra_context = {"title": "Новый склад", "back_url": "inventory:board"}


class StorageUpdateView(AdminRequiredMixin, UpdateView):
    model = Storage
    form_class = StorageForm
    template_name = "inventory/storage_form.html"
    success_url = reverse_lazy("inventory:board")
    extra_context = {"title": "Редактирование склада", "back_url": "inventory:board"}


class StorageDeleteView(AdminRequiredMixin, DeleteView):
    model = Storage
    template_name = "core/confirm_delete.html"
    success_url = reverse_lazy("inventory:board")


class ItemTypeListView(LoginRequiredMixin, ListView):
    model = ItemType
    template_name = "inventory/kind_list.html"
    context_object_name = "types"


class ItemTypeCreateView(AdminRequiredMixin, CreateView):
    model = ItemType
    form_class = ItemTypeForm
    template_name = "inventory/kind_form.html"
    success_url = reverse_lazy("inventory:kind_list")
    extra_context = {"title": "Новый тип", "back_url": "inventory:kind_list"}


class ItemTypeUpdateView(AdminRequiredMixin, UpdateView):
    model = ItemType
    form_class = ItemTypeForm
    template_name = "inventory/kind_form.html"
    success_url = reverse_lazy("inventory:kind_list")
    extra_context = {"title": "Редактирование типа", "back_url": "inventory:kind_list"}


class ItemTypeDeleteView(AdminRequiredMixin, DeleteView):
    model = ItemType
    template_name = "core/confirm_delete.html"
    success_url = reverse_lazy("inventory:kind_list")
