from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.generic import CreateView, DetailView, ListView, UpdateView, View

from core.mixins import EditorRequiredMixin
from journal.exports import export_full_journal
from journal.models import JournalEntry
from shifts.forms import ShiftCheckForm, ShiftCloseForm, ShiftOpenForm
from shifts.models import Shift


class ShiftListView(LoginRequiredMixin, ListView):
    model = Shift
    template_name = "shifts/shift_list.html"
    context_object_name = "shifts"
    paginate_by = 25

    def get_queryset(self):
        qs = Shift.objects.select_related("opened_by", "closed_by", "workshop")
        status = self.request.GET.get("status")
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["open_shift"] = Shift.objects.open().select_related("opened_by").first()
        ctx["current"] = self.request.GET
        return ctx


class ShiftDetailView(LoginRequiredMixin, DetailView):
    model = Shift
    template_name = "shifts/shift_detail.html"
    context_object_name = "shift"

    def get_queryset(self):
        return Shift.objects.select_related(
            "opened_by", "closed_by", "handover_to", "workshop"
        ).prefetch_related("checks__item", "journal_entries", "inventory_movements", "exports")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["check_form"] = ShiftCheckForm()
        return ctx


class ShiftOpenView(EditorRequiredMixin, CreateView):
    model = Shift
    form_class = ShiftOpenForm
    template_name = "shifts/shift_open.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            existing = Shift.objects.open().filter(opened_by=request.user).first()
            if existing:
                messages.warning(request, "У вас уже есть открытая смена.")
                return redirect("shifts:shift_detail", pk=existing.pk)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.opened_by = self.request.user
        form.instance.opened_at = timezone.now()
        form.instance.status = Shift.Status.OPEN
        messages.success(self.request, "Смена открыта. Удачной работы!")
        response = super().form_valid(form)
        JournalEntry.objects.create(
            shift=self.object,
            entry_type=JournalEntry.EntryType.SHIFT_START,
            occurred_at=self.object.opened_at,
            specialist=self.request.user,
            action_task="Смену принял +",
            created_by=self.request.user,
        )
        return response

    def get_success_url(self):
        return reverse("shifts:shift_detail", args=[self.object.pk])


class ShiftCloseView(EditorRequiredMixin, UpdateView):
    model = Shift
    form_class = ShiftCloseForm
    template_name = "shifts/shift_close.html"

    def get_queryset(self):
        return Shift.objects.open()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["journal_count"] = self.object.journal_entries.count()
        return ctx

    def form_valid(self, form):
        shift = form.save(commit=False)
        shift.closed_by = self.request.user
        shift.closed_at = timezone.now()
        shift.status = Shift.Status.CLOSED
        shift.save()

        JournalEntry.objects.create(
            shift=shift,
            entry_type=JournalEntry.EntryType.SHIFT_END,
            occurred_at=shift.closed_at,
            specialist=self.request.user,
            action_task="Смену сдал",
            created_by=self.request.user,
        )

        messages.success(self.request, "Смена сдана.")

        try:
            export = export_full_journal(user=self.request.user, shift=shift)
            if export:
                messages.success(
                    self.request,
                    f"Сменный журнал выгружен в единый Excel-архив ({export.entries_count} записей).",
                )
        except Exception as exc:  # noqa: BLE001
            messages.warning(self.request, f"Журнал сдан, но выгрузка Excel не удалась: {exc}")

        try:
            from checklists.services import finalize_shift_checklists

            generated = finalize_shift_checklists(shift, self.request.user)
            if generated:
                messages.success(
                    self.request, f"Чеклист оборудования сформирован ({generated} файл(ов))."
                )
        except Exception as exc:  # noqa: BLE001
            messages.warning(self.request, f"Чеклист оборудования не сформирован: {exc}")

        return redirect("shifts:shift_detail", pk=shift.pk)


class ShiftCheckCreateView(EditorRequiredMixin, View):
    def post(self, request, pk, **kwargs):
        shift = get_object_or_404(Shift, pk=pk)
        if not shift.is_open:
            messages.error(request, "Смена уже закрыта, изменения невозможны.")
            return redirect("shifts:shift_detail", pk=pk)
        form = ShiftCheckForm(request.POST)
        if form.is_valid():
            check = form.save(commit=False)
            check.shift = shift
            check.save()
            messages.success(request, "Проверка позиции добавлена.")
        else:
            messages.error(request, "Проверьте данные проверки.")
        return redirect("shifts:shift_detail", pk=pk)
