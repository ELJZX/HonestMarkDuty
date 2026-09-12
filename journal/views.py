from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DetailView, ListView, UpdateView, View

from core.mixins import EditorRequiredMixin
from journal.exports import export_entries_to_excel
from journal.forms import JournalEntryForm
from journal.models import JournalEntry, JournalExport
from shifts.models import Shift


def _filter_entries(request):
    qs = JournalEntry.objects.select_related(
        "workshop", "assigned_to", "created_by", "shift", "equipment"
    )
    params = request.GET
    query = params.get("q")
    status = params.get("status")
    priority = params.get("priority")
    shift = params.get("shift")
    date_from = params.get("date_from")
    date_to = params.get("date_to")
    if query:
        qs = qs.filter(
            Q(problem__icontains=query)
            | Q(solution__icontains=query)
            | Q(source_location__icontains=query)
            | Q(reported_by__icontains=query)
        )
    if status:
        qs = qs.filter(status=status)
    if priority:
        qs = qs.filter(priority=priority)
    if shift:
        qs = qs.filter(shift_id=shift)
    if date_from:
        qs = qs.filter(received_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(received_at__date__lte=date_to)
    return qs


class JournalEntryListView(LoginRequiredMixin, ListView):
    model = JournalEntry
    template_name = "journal/entry_list.html"
    context_object_name = "entries"
    paginate_by = 25

    def get_queryset(self):
        return _filter_entries(self.request)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["statuses"] = JournalEntry.Status.choices
        ctx["priorities"] = JournalEntry.Priority.choices
        ctx["current"] = self.request.GET
        ctx["open_shift"] = Shift.objects.open().first()
        ctx["stats"] = {
            "total": JournalEntry.objects.count(),
            "new": JournalEntry.objects.filter(status=JournalEntry.Status.NEW).count(),
            "progress": JournalEntry.objects.filter(status=JournalEntry.Status.IN_PROGRESS).count(),
            "done": JournalEntry.objects.filter(status=JournalEntry.Status.DONE).count(),
        }
        return ctx


class JournalEntryDetailView(LoginRequiredMixin, DetailView):
    model = JournalEntry
    template_name = "journal/entry_detail.html"
    context_object_name = "entry"


class JournalEntryCreateView(EditorRequiredMixin, CreateView):
    model = JournalEntry
    form_class = JournalEntryForm
    template_name = "journal/entry_form.html"
    extra_context = {"title": "Новое обращение", "back_url": "journal:entry_list"}

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        if form.instance.shift is None:
            form.instance.shift = (
                Shift.objects.open().filter(opened_by=self.request.user).first()
                or Shift.objects.open().first()
            )
        messages.success(self.request, "Обращение зарегистрировано.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("journal:entry_detail", args=[self.object.pk])


class JournalEntryUpdateView(EditorRequiredMixin, UpdateView):
    model = JournalEntry
    form_class = JournalEntryForm
    template_name = "journal/entry_form.html"
    extra_context = {"title": "Редактирование обращения", "back_url": "journal:entry_list"}

    def form_valid(self, form):
        messages.success(self.request, "Запись обновлена.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("journal:entry_detail", args=[self.object.pk])


class JournalExportListView(LoginRequiredMixin, ListView):
    model = JournalExport
    template_name = "journal/export_list.html"
    context_object_name = "exports"
    paginate_by = 30


class JournalExportCreateView(EditorRequiredMixin, View):
    """Ручная выгрузка отфильтрованного журнала."""

    def get(self, request):
        entries = _filter_entries(request).order_by("received_at")
        if not entries.exists():
            messages.warning(request, "Нет записей для выгрузки.")
            return redirect("journal:entry_list")
        export = export_entries_to_excel(entries, request.user)
        messages.success(request, f"Сформирован файл: {export.file.name.split('/')[-1]}")
        return redirect("journal:export_list")
