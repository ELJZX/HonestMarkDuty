from __future__ import annotations

from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DetailView, DeleteView, ListView, UpdateView, View

from core.mixins import AdminRequiredMixin, EditorRequiredMixin
from core.models import ProductionLine, ProductionSite, Workshop
from equipment.forms import (
    EquipmentCategoryForm,
    EquipmentForm,
    EquipmentStatusLogForm,
    MaintenanceRecordForm,
    ProductionLineForm,
)
from equipment.models import (
    Equipment,
    EquipmentCategory,
    EquipmentStatus,
    MaintenanceRecord,
)


class EquipmentListView(LoginRequiredMixin, ListView):
    model = Equipment
    template_name = "equipment/equipment_list.html"
    context_object_name = "equipment_list"
    paginate_by = 25

    def get_queryset(self):
        qs = Equipment.objects.select_related("site", "workshop", "line", "category", "responsible")
        params = self.request.GET
        query = params.get("q")
        site = params.get("site")
        workshop = params.get("workshop")
        status = params.get("status")
        category = params.get("category")
        if query:
            qs = qs.filter(
                Q(name__icontains=query)
                | Q(inventory_number__icontains=query)
                | Q(serial_number__icontains=query)
            )
        if site:
            qs = qs.filter(site_id=site)
        if workshop:
            qs = qs.filter(workshop_id=workshop)
        if status:
            qs = qs.filter(status=status)
        if category:
            qs = qs.filter(category_id=category)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["sites"] = ProductionSite.objects.all()
        ctx["workshops"] = Workshop.objects.all()
        ctx["categories"] = EquipmentCategory.objects.all()
        ctx["statuses"] = EquipmentStatus.choices
        ctx["current"] = self.request.GET
        ctx["by_status"] = Equipment.objects.values("status").annotate(total=Count("id"))
        return ctx


class EquipmentBoardView(LoginRequiredMixin, ListView):
    """Доска цехов: карточки с названием, переход к линиям цеха."""

    model = Workshop
    template_name = "equipment/board.html"
    context_object_name = "workshops"

    def get_queryset(self):
        return (
            Workshop.objects.filter(is_active=True)
            .annotate(
                total_lines=Count("lines", distinct=True),
                active_lines=Count("lines", filter=Q(lines__is_active=True), distinct=True),
                total_equipment=Count("equipment", distinct=True),
                active_equipment=Count(
                    "equipment", filter=Q(equipment__is_active=True), distinct=True
                ),
                operational_equipment=Count(
                    "equipment",
                    filter=Q(equipment__is_active=True, equipment__status=EquipmentStatus.OPERATIONAL),
                    distinct=True,
                ),
            )
            .order_by("name")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        for workshop in ctx["workshops"]:
            total = workshop.total_equipment or 0
            operational = workshop.operational_equipment or 0
            workshop.ready_percent = (
                f"{operational / total * 100:.2f}".replace(".", ",") if total else "0,00"
            )
        return ctx


class WorkshopLinesView(LoginRequiredMixin, DetailView):
    """Список производственных линий выбранного цеха."""

    model = Workshop
    template_name = "equipment/workshop_lines.html"
    context_object_name = "workshop"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["lines"] = (
            self.object.lines.filter(is_active=True)
            .annotate(equipment_total=Count("equipment", filter=Q(equipment__is_active=True)))
            .order_by("sort_order", "name")
        )
        ctx["no_line_equipment"] = (
            self.object.equipment.filter(is_active=True, line__isnull=True)
            .select_related("category")
        )
        return ctx


class LineEquipmentView(LoginRequiredMixin, DetailView):
    """Список оборудования выбранной производственной линии."""

    model = ProductionLine
    template_name = "equipment/line_equipment.html"
    context_object_name = "line"

    def get_queryset(self):
        return ProductionLine.objects.select_related("workshop")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["equipment_list"] = (
            self.object.equipment.filter(is_active=True)
            .select_related("category", "responsible")
            .order_by("name")
        )
        return ctx


class EquipmentDetailView(LoginRequiredMixin, DetailView):
    model = Equipment
    template_name = "equipment/equipment_detail.html"
    context_object_name = "equipment"

    def get_queryset(self):
        return Equipment.objects.select_related("site", "workshop", "line", "category", "responsible")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["status_logs"] = self.object.status_logs.select_related("changed_by")
        ctx["maintenance_records"] = self.object.maintenance_records.select_related("created_by")
        ctx["status_form"] = EquipmentStatusLogForm(initial={"status": self.object.status})
        ctx["maintenance_form"] = MaintenanceRecordForm()
        return ctx


class EquipmentCreateView(EditorRequiredMixin, CreateView):
    model = Equipment
    form_class = EquipmentForm
    template_name = "equipment/equipment_form.html"
    extra_context = {"title": "Новое оборудование", "back_url": "equipment:equipment_list"}

    def get_initial(self):
        initial = super().get_initial()
        line_id = self.request.GET.get("line")
        if line_id:
            line = (
                ProductionLine.objects.filter(pk=line_id).select_related("workshop").first()
            )
            if line:
                initial["line"] = line.pk
                initial["workshop"] = line.workshop_id
        return initial

    def form_valid(self, form):
        messages.success(self.request, "Оборудование добавлено.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("equipment:equipment_detail", args=[self.object.pk])


class ProductionLineCreateView(EditorRequiredMixin, CreateView):
    model = ProductionLine
    form_class = ProductionLineForm
    template_name = "equipment/line_form.html"

    def get_initial(self):
        initial = super().get_initial()
        workshop_id = self.request.GET.get("workshop")
        if workshop_id:
            initial["workshop"] = workshop_id
        return initial

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        workshop_id = self.request.GET.get("workshop") or self.request.POST.get("workshop")
        if workshop_id:
            ctx["title"] = "Новая линия"
            ctx["cancel_url"] = reverse("equipment:workshop_lines", args=[workshop_id])
        else:
            ctx["title"] = "Новая линия"
            ctx["cancel_url"] = reverse("equipment:board")
        return ctx

    def form_valid(self, form):
        messages.success(self.request, "Линия добавлена.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("equipment:workshop_lines", args=[self.object.workshop_id])


class EquipmentUpdateView(EditorRequiredMixin, UpdateView):
    model = Equipment
    form_class = EquipmentForm
    template_name = "equipment/equipment_form.html"
    extra_context = {"title": "Редактирование оборудования", "back_url": "equipment:equipment_list"}

    def form_valid(self, form):
        messages.success(self.request, "Изменения сохранены.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("equipment:equipment_detail", args=[self.object.pk])


class EquipmentDeleteView(AdminRequiredMixin, DeleteView):
    model = Equipment
    template_name = "core/confirm_delete.html"
    success_url = reverse_lazy("equipment:equipment_list")

    def get_success_url(self):
        line_id = self.object.line_id
        if line_id:
            return reverse("equipment:line_equipment", args=[line_id])
        return reverse("equipment:equipment_list")


class ProductionLineDeleteView(AdminRequiredMixin, DeleteView):
    model = ProductionLine
    template_name = "core/confirm_delete.html"

    def get_success_url(self):
        return reverse("equipment:workshop_lines", args=[self.object.workshop_id])


class EquipmentStatusChangeView(EditorRequiredMixin, View):
    def post(self, request, pk):
        equipment = get_object_or_404(Equipment, pk=pk)
        form = EquipmentStatusLogForm(request.POST)
        if form.is_valid():
            new_status = form.cleaned_data["status"]
            comment = form.cleaned_data.get("comment", "")
            if equipment.status != new_status:
                equipment.status = new_status
                equipment.save()
                auto_log = equipment.status_logs.first()
                if auto_log:
                    auto_log.comment = comment or auto_log.comment
                    auto_log.changed_by = request.user
                    auto_log.save()
            else:
                log = form.save(commit=False)
                log.equipment = equipment
                log.changed_by = request.user
                log.save()
            messages.success(request, f"Состояние обновлено: {equipment.get_status_display()}.")
        else:
            messages.error(request, "Не удалось изменить состояние.")
        return redirect("equipment:equipment_detail", pk=pk)


class MaintenanceRecordCreateView(EditorRequiredMixin, View):
    def post(self, request, pk):
        equipment = get_object_or_404(Equipment, pk=pk)
        form = MaintenanceRecordForm(request.POST)
        if form.is_valid():
            record = form.save(commit=False)
            record.equipment = equipment
            record.created_by = request.user
            record.save()
            equipment.last_maintenance_at = record.performed_at
            if record.performed_at and record.kind in ("to", "repair"):
                equipment.next_maintenance_at = record.performed_at + timedelta(days=180)
            equipment.save()
            messages.success(request, "Работа по оборудованию зарегистрирована.")
        else:
            messages.error(request, "Проверьте данные о работах.")
        return redirect("equipment:equipment_detail", pk=pk)


class EquipmentCategoryListView(LoginRequiredMixin, ListView):
    model = EquipmentCategory
    template_name = "equipment/category_list.html"
    context_object_name = "categories"


class EquipmentCategoryCreateView(EditorRequiredMixin, CreateView):
    model = EquipmentCategory
    form_class = EquipmentCategoryForm
    template_name = "equipment/category_form.html"
    success_url = reverse_lazy("equipment:category_list")
    extra_context = {"title": "Новая категория", "back_url": "equipment:category_list"}


class EquipmentCategoryUpdateView(EditorRequiredMixin, UpdateView):
    model = EquipmentCategory
    form_class = EquipmentCategoryForm
    template_name = "equipment/category_form.html"
    success_url = reverse_lazy("equipment:category_list")
    extra_context = {"title": "Редактирование категории", "back_url": "equipment:category_list"}
