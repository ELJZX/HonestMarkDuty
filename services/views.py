from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView

from core.mixins import AdminRequiredMixin
from services.forms import ServiceForm
from services.models import Service, ServiceKind


class ServiceListView(LoginRequiredMixin, ListView):
    """Кликабельные кнопки сервисов и сайтов Молвест.Маркировка."""

    model = Service
    template_name = "services/service_list.html"
    context_object_name = "services"

    def get_queryset(self):
        return Service.objects.filter(is_active=True).order_by("sort_order", "name")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        active = list(self.get_queryset())
        ctx["services"] = [item for item in active if item.kind == ServiceKind.SERVICE]
        ctx["sites"] = [item for item in active if item.kind == ServiceKind.SITE]
        return ctx


class ServiceCreateView(AdminRequiredMixin, CreateView):
    model = Service
    form_class = ServiceForm
    template_name = "core/generic_form.html"
    success_url = reverse_lazy("services:service_list")
    kind = ServiceKind.SERVICE
    title = "Добавить сервис"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = self.title
        ctx["back_url"] = "services:service_list"
        return ctx

    def form_valid(self, form):
        form.instance.kind = self.kind
        messages.success(self.request, "Добавлено.")
        return super().form_valid(form)


class SiteCreateView(ServiceCreateView):
    kind = ServiceKind.SITE
    title = "Добавить сайт"
