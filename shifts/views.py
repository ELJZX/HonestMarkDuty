from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DetailView, ListView, UpdateView, View

from core.mixins import EditorRequiredMixin
from journal.exports import export_full_journal
from journal.models import JournalEntry
from shifts.forms import ShiftCheckForm, ShiftCloseForm, ShiftOpenForm
from shifts.models import Shift


def _plural_ru(count: int, one: str, few: str, many: str) -> str:
    """Русская форма существительного: 1 запись, 2 записи, 5 записей."""
    number = abs(int(count)) % 100
    if 11 <= number <= 14:
        return many
    number %= 10
    if number == 1:
        return one
    if 2 <= number <= 4:
        return few
    return many


def open_shift_for(request):
    """Открывает смену текущим пользователем. Возвращает (shift, message)."""
    existing = Shift.objects.open().filter(opened_by=request.user).first()
    if existing:
        return None, "У вас уже есть открытая смена."
    shift = Shift.objects.create(
        opened_by=request.user,
        opened_at=timezone.now(),
        date=timezone.localdate(),
        status=Shift.Status.OPEN,
    )
    JournalEntry.objects.create(
        shift=shift,
        entry_type=JournalEntry.EntryType.SHIFT_START,
        occurred_at=shift.opened_at,
        specialist=request.user,
        action_task="Смену принял +",
        created_by=request.user,
    )
    return shift, "Смена открыта"


def close_shift_with(request, shift: Shift) -> Shift:
    """Сдаёт смену, добавляет запись журнала и формирует выгрузки."""
    shift.closed_by = request.user
    shift.closed_at = timezone.now()
    shift.status = Shift.Status.CLOSED
    shift.save()

    JournalEntry.objects.create(
        shift=shift,
        entry_type=JournalEntry.EntryType.SHIFT_END,
        occurred_at=shift.closed_at,
        specialist=request.user,
        action_task="Смену сдал",
        created_by=request.user,
    )

    try:
        export_full_journal(user=request.user, shift=shift)
    except Exception:  # noqa: BLE001
        pass

    try:
        from checklists.services import finalize_shift_checklists

        finalize_shift_checklists(shift, request.user)
    except Exception:  # noqa: BLE001
        pass

    return shift


class ShiftListView(LoginRequiredMixin, ListView):
    model = Shift
    template_name = "shifts/shift_list.html"
    context_object_name = "shifts"
    paginate_by = 25

    def get(self, request, *args, **kwargs):
        from shifts.integration import quick_sync

        try:
            quick_sync()
        except Exception:  # синк не должен ломать страницу
            pass
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        qs = Shift.objects.select_related("opened_by", "closed_by", "workshop")
        status = self.request.GET.get("status")
        if status:
            qs = qs.filter(status=status)
        date = self.request.GET.get("date")
        if date:
            qs = qs.filter(date=date)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["open_shift"] = Shift.objects.open().select_related("opened_by").first()
        ctx["last_shift"] = (
            Shift.objects.closed().select_related("opened_by").first()
        )
        ctx["current"] = self.request.GET
        return ctx


class ShiftDetailView(LoginRequiredMixin, DetailView):
    model = Shift
    template_name = "shifts/shift_detail.html"
    context_object_name = "shift"

    def get_queryset(self):
        return Shift.objects.select_related(
            "opened_by", "closed_by", "handover_to", "workshop"
        ).prefetch_related("journal_entries")


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
        shift, message = open_shift_for(self.request)
        if shift is None:
            messages.warning(self.request, message)
            return redirect("shifts:shift_list")
        messages.success(self.request, "Смена открыта")
        return redirect("shifts:shift_detail", pk=shift.pk)


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
        close_shift_with(self.request, shift)
        messages.success(self.request, "Смена сдана")
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


@require_POST
def shift_open_ajax(request):
    """AJAX-открытие смены без перехода на отдельную страницу."""
    if not request.user.is_authenticated:
        return JsonResponse({"ok": False, "message": "Требуется вход в систему."}, status=403)
    if not getattr(request.user, "can_edit", False):
        return JsonResponse({"ok": False, "message": "Недостаточно прав."}, status=403)
    shift, message = open_shift_for(request)
    return JsonResponse(
        {"ok": shift is not None, "message": message}, status=200 if shift else 400
    )


@require_POST
def shift_close_ajax(request, pk):
    """AJAX-сдача смены без перехода на отдельную страницу."""
    if not request.user.is_authenticated:
        return JsonResponse({"ok": False, "message": "Требуется вход в систему."}, status=403)
    if not getattr(request.user, "can_edit", False):
        return JsonResponse({"ok": False, "message": "Недостаточно прав."}, status=403)
    shift = get_object_or_404(Shift.objects.open(), pk=pk)
    close_shift_with(request, shift)
    return JsonResponse({"ok": True, "message": "Смена сдана"})
