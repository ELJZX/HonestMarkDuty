from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView, View

from core.mixins import EditorRequiredMixin
from journal.exports import export_full_journal, group_entries
from journal.forms import JournalEntryForm
from journal.models import JournalEntry, JournalExport
from shifts.models import Shift


def _filter_entries(request):
    qs = JournalEntry.objects.select_related("shift", "specialist", "created_by")
    params = request.GET
    query = params.get("q")
    specialist = params.get("specialist")
    date_from = params.get("date_from")
    date_to = params.get("date_to")
    if query:
        qs = qs.filter(
            Q(action_task__icontains=query)
            | Q(solution__icontains=query)
            | Q(equipment_line__icontains=query)
        )
    if specialist:
        qs = qs.filter(specialist_id=specialist)
    if date_from:
        qs = qs.filter(occurred_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(occurred_at__date__lte=date_to)
    return qs


def build_groups(entries) -> list[dict]:
    groups = []
    for chunk in group_entries(list(entries)):
        first = chunk[0]
        groups.append(
            {
                "date": first.entry_date,
                "specialist": first.specialist_name,
                "span": len(chunk),
                "rows": chunk,
            }
        )
    return groups


class JournalEntryListView(LoginRequiredMixin, ListView):
    model = JournalEntry
    template_name = "journal/entry_list.html"
    context_object_name = "entries"
    paginate_by = 50

    def get_queryset(self):
        return _filter_entries(self.request)

    def get_context_data(self, **kwargs):
        from accounts.models import User

        ctx = super().get_context_data(**kwargs)
        ctx["groups"] = build_groups(self.object_list)
        ctx["specialists"] = (
            User.objects.filter(journal_records__isnull=False).distinct().order_by("last_name")
        )
        ctx["current"] = self.request.GET
        ctx["open_shift"] = Shift.objects.open().select_related("opened_by").first()
        ctx["total"] = JournalEntry.objects.count()
        return ctx


class JournalEntryCreateView(EditorRequiredMixin, CreateView):
    model = JournalEntry
    form_class = JournalEntryForm
    template_name = "journal/entry_form.html"
    extra_context = {"title": "Новая запись журнала", "back_url": "journal:entry_list"}

    def get_initial(self):
        initial = super().get_initial()
        shift = (
            Shift.objects.open().filter(opened_by=self.request.user).first()
            or Shift.objects.open().first()
        )
        if shift and shift.opened_by_id:
            initial["specialist"] = shift.opened_by_id
        return initial

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.entry_type = JournalEntry.EntryType.WORK
        if form.instance.specialist is None:
            form.instance.specialist = self.request.user
        if form.instance.shift is None:
            form.instance.shift = (
                Shift.objects.open().filter(opened_by=self.request.user).first()
                or Shift.objects.open().first()
            )
        messages.success(self.request, "Запись добавлена в сменный журнал.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("journal:entry_list")


class JournalEntryUpdateView(EditorRequiredMixin, UpdateView):
    model = JournalEntry
    form_class = JournalEntryForm
    template_name = "journal/entry_form.html"
    extra_context = {"title": "Редактирование записи", "back_url": "journal:entry_list"}

    def form_valid(self, form):
        messages.success(self.request, "Запись обновлена.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("journal:entry_list")


class JournalEntryDeleteView(EditorRequiredMixin, DeleteView):
    model = JournalEntry
    template_name = "core/confirm_delete.html"
    success_url = reverse_lazy("journal:entry_list")

    def form_valid(self, form):
        messages.success(self.request, "Запись удалена.")
        return super().form_valid(form)


class JournalExportListView(LoginRequiredMixin, ListView):
    model = JournalExport
    template_name = "journal/export_list.html"
    context_object_name = "exports"
    paginate_by = 30

    def get_context_data(self, **kwargs):
        from checklists.models import EquipmentChecklist

        ctx = super().get_context_data(**kwargs)
        ctx["checklist_exports"] = (
            EquipmentChecklist.objects.exclude(file="")
            .select_related("workshop", "performed_by")
            .order_by("-date", "-created_at")[:30]
        )
        ctx["checklists_total"] = EquipmentChecklist.objects.count()
        return ctx


class JournalExportCreateView(EditorRequiredMixin, View):
    """Ручное формирование единого Excel-архива журнала."""

    def get(self, request):
        export = export_full_journal(user=request.user)
        if export is None:
            messages.warning(request, "Журнал пуст — нечего выгружать.")
        else:
            messages.success(
                request, f"Единый архив сформирован: {export.file.name.split('/')[-1]}"
            )
        return redirect("journal:export_list")
