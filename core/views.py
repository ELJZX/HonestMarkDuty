from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.shortcuts import render
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView, View

from core.forms import ProductionSiteForm, WorkshopForm
from core.mixins import AdminRequiredMixin
from core.models import AuditLog, ProductionSite, Workshop

User = get_user_model()


class HomeView(LoginRequiredMixin, View):
    def get(self, request):
        from django.shortcuts import redirect

        return redirect("analytics:dashboard")


class AuditLogListView(LoginRequiredMixin, ListView):
    model = AuditLog
    template_name = "core/audit_list.html"
    context_object_name = "logs"
    paginate_by = 50

    def get_queryset(self):
        qs = AuditLog.objects.select_related("user")
        model = self.request.GET.get("model")
        action = self.request.GET.get("action")
        user = self.request.GET.get("user")
        query = self.request.GET.get("q")
        if model:
            qs = qs.filter(model_name=model)
        if action:
            qs = qs.filter(action=action)
        if user:
            qs = qs.filter(user_id=user)
        if query:
            qs = qs.filter(Q(object_repr__icontains=query) | Q(object_id__icontains=query))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["models"] = (
            AuditLog.objects.values_list("model_name", flat=True).distinct().order_by("model_name")
        )
        ctx["actions"] = AuditLog.Action.choices
        ctx["users"] = (
            User.objects.filter(audit_logs__isnull=False).distinct().order_by("last_name", "username")
        )
        ctx["current"] = self.request.GET
        return ctx


class WorkshopListView(LoginRequiredMixin, ListView):
    model = Workshop
    template_name = "core/workshop_list.html"
    context_object_name = "workshops"


class WorkshopCreateView(AdminRequiredMixin, CreateView):
    model = Workshop
    form_class = WorkshopForm
    template_name = "core/workshop_form.html"
    success_url = reverse_lazy("core:workshop_list")
    extra_context = {"title": "Новый цех", "back_url": "core:workshop_list"}

    def form_valid(self, form):
        messages.success(self.request, "Цех добавлен.")
        return super().form_valid(form)


class WorkshopUpdateView(AdminRequiredMixin, UpdateView):
    model = Workshop
    form_class = WorkshopForm
    template_name = "core/workshop_form.html"
    success_url = reverse_lazy("core:workshop_list")
    extra_context = {"title": "Редактирование цеха", "back_url": "core:workshop_list"}

    def form_valid(self, form):
        messages.success(self.request, "Изменения сохранены.")
        return super().form_valid(form)


class WorkshopDeleteView(AdminRequiredMixin, DeleteView):
    model = Workshop
    template_name = "core/confirm_delete.html"
    success_url = reverse_lazy("core:workshop_list")

    def form_valid(self, form):
        messages.success(self.request, "Цех удалён.")
        return super().form_valid(form)


class ProductionSiteListView(LoginRequiredMixin, ListView):
    model = ProductionSite
    template_name = "core/site_list.html"
    context_object_name = "sites"


class ProductionSiteCreateView(AdminRequiredMixin, CreateView):
    model = ProductionSite
    form_class = ProductionSiteForm
    template_name = "core/site_form.html"
    success_url = reverse_lazy("core:site_list")
    extra_context = {"title": "Новая площадка", "back_url": "core:site_list"}


class ProductionSiteUpdateView(AdminRequiredMixin, UpdateView):
    model = ProductionSite
    form_class = ProductionSiteForm
    template_name = "core/site_form.html"
    success_url = reverse_lazy("core:site_list")
    extra_context = {"title": "Редактирование площадки", "back_url": "core:site_list"}


class ProductionSiteDeleteView(AdminRequiredMixin, DeleteView):
    model = ProductionSite
    template_name = "core/confirm_delete.html"
    success_url = reverse_lazy("core:site_list")


def forbidden(request, exception=None):
    return render(request, "errors/403.html", status=403)


def not_found(request, exception=None):
    return render(request, "errors/404.html", status=404)


def server_error(request):
    return render(request, "errors/500.html", status=500)
