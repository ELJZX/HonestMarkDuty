from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import DeleteView, DetailView, ListView, TemplateView, View

from checklists.exports import save_checklist_file
from checklists.forms import ChecklistForm, MarkemForm
from checklists.markem_exports import save_markem_file
from checklists.models import ChecklistStatus, EquipmentChecklist, MarkemChecklist
from checklists.services import (
    apply_matrix,
    apply_markem_values,
    build_matrix,
    finalize_checklist,
    finalize_markem_checklist,
    markem_matrix,
)
from core.mixins import AdminRequiredMixin, EditorRequiredMixin
from shifts.models import Shift


class ChecklistHubView(LoginRequiredMixin, TemplateView):
    """Каталог доступных чеклистов."""

    template_name = "checklists/hub.html"


class CurrentArchiveMixin(LoginRequiredMixin, ListView):
    """Общая логика страниц чеклистов: активный (текущий) чеклист и архив."""

    paginate_by = None
    current_matrix_key = "current_matrix"
    select_related_fields: tuple[str, ...] = ()

    def get_queryset(self):
        return self.model.objects.select_related(*self.select_related_fields)

    def matrix_for(self, checklist) -> dict:
        raise NotImplementedError

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        open_shift = Shift.objects.open().first()

        current = None
        if open_shift is not None:
            current = (
                self.get_queryset()
                .filter(shift=open_shift)
                .order_by("-created_at")
                .first()
            )
        if current is None:
            current = (
                self.get_queryset()
                .filter(status=ChecklistStatus.DRAFT)
                .order_by("-date", "-created_at")
                .first()
            )

        ctx["open_shift"] = open_shift
        ctx["current_checklist"] = current
        ctx["archive_checklists"] = self.get_queryset().filter(status=ChecklistStatus.FINAL)
        if current is not None:
            ctx[self.current_matrix_key] = self.matrix_for(current)
        return ctx


class MarkemChecklistView(CurrentArchiveMixin):
    """Чеклист технического осмотра и обслуживания принтеров Markem Image 9450."""

    model = MarkemChecklist
    template_name = "checklists/markem.html"
    context_object_name = "markem_checklists"
    select_related_fields = ("performed_by", "checked_by", "shift")

    def matrix_for(self, checklist) -> dict:
        return markem_matrix(checklist)


def _ensure_editable(user, checklist: EquipmentChecklist) -> None:
    """Закрытый (сформированный) чеклист редактирует только администратор."""
    if checklist.status == ChecklistStatus.FINAL and not getattr(user, "is_admin", False):
        raise PermissionDenied("Закрытый чеклист может изменять только администратор.")


class ChecklistListView(CurrentArchiveMixin):
    """Чеклист технического осмотра оборудования «Честный знак»."""

    model = EquipmentChecklist
    template_name = "checklists/checklist_list.html"
    context_object_name = "checklists"
    select_related_fields = ("workshop", "performed_by", "shift")

    def matrix_for(self, checklist) -> dict:
        return build_matrix(checklist)


class ChecklistDetailView(LoginRequiredMixin, DetailView):
    model = EquipmentChecklist
    template_name = "checklists/checklist_detail.html"
    context_object_name = "checklist"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        matrix = build_matrix(self.object)
        ctx.update(matrix)
        ctx["matrix"] = matrix
        return ctx


def _render_form(request, form, checklist=None):
    context = {
        "form": form,
        "checklist": checklist,
        "title": "Редактирование чеклиста" if checklist else "Новый чеклист оборудования",
        "back_url": "checklists:checklist_list",
    }
    context.update(build_matrix(checklist))
    return render(request, "checklists/checklist_form.html", context)


class ChecklistCreateView(EditorRequiredMixin, View):
    def get(self, request):
        form = ChecklistForm(
            initial={"date": timezone.localdate(), "performed_by": request.user}
        )
        return _render_form(request, form)

    def post(self, request):
        form = ChecklistForm(request.POST)
        if form.is_valid():
            checklist = form.save(commit=False)
            checklist.created_by = request.user
            checklist.shift = (
                Shift.objects.open().filter(opened_by=request.user).first()
                or Shift.objects.open().first()
            )
            checklist.save()
            apply_matrix(checklist, request.POST)
            if request.POST.get("finalize"):
                finalize_checklist(checklist)
                messages.success(request, "Чеклист сохранён, файл сформирован и доступен для скачивания.")
            else:
                messages.success(request, "Чеклист сохранён.")
            return redirect("checklists:checklist_list")
        return _render_form(request, form)


class ChecklistUpdateView(EditorRequiredMixin, View):
    def get(self, request, pk):
        checklist = get_object_or_404(EquipmentChecklist, pk=pk)
        _ensure_editable(request.user, checklist)
        form = ChecklistForm(instance=checklist)
        return _render_form(request, form, checklist)

    def post(self, request, pk):
        checklist = get_object_or_404(EquipmentChecklist, pk=pk)
        _ensure_editable(request.user, checklist)
        form = ChecklistForm(request.POST, instance=checklist)
        if form.is_valid():
            checklist = form.save()
            apply_matrix(checklist, request.POST)
            if request.POST.get("finalize"):
                finalize_checklist(checklist)
                messages.success(request, "Чеклист обновлён и файл пересформирован.")
            else:
                messages.success(request, "Чеклист обновлён.")
            return redirect("checklists:checklist_list")
        return _render_form(request, form, checklist)


class ChecklistCloseView(EditorRequiredMixin, View):
    """Закрывает чеклист: формирует файл и переносит его в архив."""

    def post(self, request, pk):
        checklist = get_object_or_404(EquipmentChecklist, pk=pk)
        finalize_checklist(checklist)
        messages.success(request, "Чеклист закрыт и перенесён в архив.")
        return redirect("checklists:checklist_list")


class ChecklistGenerateView(EditorRequiredMixin, View):
    def post(self, request, pk):
        checklist = get_object_or_404(EquipmentChecklist, pk=pk)
        finalize_checklist(checklist)
        messages.success(request, "Файл чеклиста сформирован.")
        return redirect("checklists:checklist_detail", pk=pk)


class ChecklistDownloadView(LoginRequiredMixin, View):
    """Скачивание чеклиста; при отсутствии файла — формирует его."""

    def get(self, request, pk):
        checklist = get_object_or_404(EquipmentChecklist, pk=pk)
        if not checklist.file:
            save_checklist_file(checklist)
        return redirect(checklist.file.url)


class ChecklistDeleteView(AdminRequiredMixin, DeleteView):
    model = EquipmentChecklist
    template_name = "core/confirm_delete.html"
    success_url = reverse_lazy("checklists:checklist_list")

    def form_valid(self, form):
        messages.success(self.request, "Чеклист удалён.")
        return super().form_valid(form)


# --- Чеклист принтеров Markem Image 9450 -----------------------------------


def _ensure_markem_editable(user, checklist: MarkemChecklist) -> None:
    if checklist.status == ChecklistStatus.FINAL and not getattr(user, "is_admin", False):
        raise PermissionDenied("Закрытый чеклист может изменять только администратор.")


def _render_markem_form(request, form, checklist=None):
    context = {
        "form": form,
        "checklist": checklist,
        "title": "Редактирование чеклиста Markem" if checklist else "Новый чеклист Markem Image 9450",
    }
    context.update(markem_matrix(checklist))
    return render(request, "checklists/markem_form.html", context)


class MarkemCreateView(EditorRequiredMixin, View):
    def get(self, request):
        form = MarkemForm(
            initial={"date": timezone.localdate(), "performed_by": request.user}
        )
        return _render_markem_form(request, form)

    def post(self, request):
        form = MarkemForm(request.POST)
        if form.is_valid():
            checklist = form.save(commit=False)
            checklist.created_by = request.user
            checklist.shift = (
                Shift.objects.open().filter(opened_by=request.user).first()
                or Shift.objects.open().first()
            )
            checklist.save()
            apply_markem_values(checklist, request.POST)
            if request.POST.get("finalize"):
                finalize_markem_checklist(checklist)
                messages.success(
                    request, "Чеклист сохранён, файл сформирован и доступен для скачивания."
                )
            else:
                messages.success(request, "Чеклист сохранён.")
            return redirect("checklists:markem")
        return _render_markem_form(request, form)


class MarkemUpdateView(EditorRequiredMixin, View):
    def get(self, request, pk):
        checklist = get_object_or_404(MarkemChecklist, pk=pk)
        _ensure_markem_editable(request.user, checklist)
        form = MarkemForm(instance=checklist)
        return _render_markem_form(request, form, checklist)

    def post(self, request, pk):
        checklist = get_object_or_404(MarkemChecklist, pk=pk)
        _ensure_markem_editable(request.user, checklist)
        form = MarkemForm(request.POST, instance=checklist)
        if form.is_valid():
            checklist = form.save()
            apply_markem_values(checklist, request.POST)
            if request.POST.get("finalize"):
                finalize_markem_checklist(checklist)
                messages.success(request, "Чеклист обновлён и файл пересформирован.")
            else:
                messages.success(request, "Чеклист обновлён.")
            return redirect("checklists:markem")
        return _render_markem_form(request, form, checklist)


class MarkemCloseView(EditorRequiredMixin, View):
    """Закрывает чеклист Markem: формирует файл и переносит его в архив."""

    def post(self, request, pk):
        checklist = get_object_or_404(MarkemChecklist, pk=pk)
        finalize_markem_checklist(checklist)
        messages.success(request, "Чеклист закрыт и перенесён в архив.")
        return redirect("checklists:markem")


class MarkemDownloadView(LoginRequiredMixin, View):
    """Скачивание чеклиста Markem; при отсутствии файла — формирует его."""

    def get(self, request, pk):
        checklist = get_object_or_404(MarkemChecklist, pk=pk)
        if not checklist.file:
            save_markem_file(checklist)
        return redirect(checklist.file.url)


class MarkemDeleteView(AdminRequiredMixin, DeleteView):
    model = MarkemChecklist
    template_name = "core/confirm_delete.html"
    success_url = reverse_lazy("checklists:markem")

    def form_valid(self, form):
        messages.success(self.request, "Чеклист удалён.")
        return super().form_valid(form)
