from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView

from core.mixins import AdminRequiredMixin
from services.forms import ServiceForm
from services.models import Service


class ServiceListView(LoginRequiredMixin, ListView):
    """Кликабельные кнопки внешних сервисов Молвест.Маркировка."""

    model = Service
    template_name = "services/service_list.html"
    context_object_name = "services"

    def get_queryset(self):
        return Service.objects.filter(is_active=True).order_by("sort_order", "name")


class ServiceCreateView(AdminRequiredMixin, CreateView):
    model = Service
    form_class = ServiceForm
    template_name = "core/generic_form.html"
    success_url = reverse_lazy("services:service_list")
    extra_context = {"title": "Добавить сервис", "back_url": "services:service_list"}

    def form_valid(self, form):
        messages.success(self.request, "Сервис добавлен.")
        return super().form_valid(form)
