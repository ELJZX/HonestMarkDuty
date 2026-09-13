from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import DeleteView, DetailView, ListView, View

from checklists.forms import ChecklistForm
from checklists.models import EquipmentChecklist
from checklists.services import apply_matrix, build_matrix, finalize_checklist
from core.mixins import AdminRequiredMixin, EditorRequiredMixin
from shifts.models import Shift


class ChecklistListView(LoginRequiredMixin, ListView):
    model = EquipmentChecklist
    template_name = "checklists/checklist_list.html"
    context_object_name = "checklists"
    paginate_by = 25


class ChecklistDetailView(LoginRequiredMixin, DetailView):
    model = EquipmentChecklist
    template_name = "checklists/checklist_detail.html"
    context_object_name = "checklist"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(build_matrix(self.object))
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
                messages.success(request, "Черновик чеклиста сохранён.")
            return redirect("checklists:checklist_detail", pk=checklist.pk)
        return _render_form(request, form)


class ChecklistUpdateView(EditorRequiredMixin, View):
    def get(self, request, pk):
        checklist = get_object_or_404(EquipmentChecklist, pk=pk)
        form = ChecklistForm(instance=checklist)
        return _render_form(request, form, checklist)

    def post(self, request, pk):
        checklist = get_object_or_404(EquipmentChecklist, pk=pk)
        form = ChecklistForm(request.POST, instance=checklist)
        if form.is_valid():
            checklist = form.save()
            apply_matrix(checklist, request.POST)
            if request.POST.get("finalize"):
                finalize_checklist(checklist)
                messages.success(request, "Чеклист обновлён и файл пересформирован.")
            else:
                messages.success(request, "Чеклист обновлён.")
            return redirect("checklists:checklist_detail", pk=checklist.pk)
        return _render_form(request, form, checklist)


class ChecklistGenerateView(EditorRequiredMixin, View):
    def post(self, request, pk):
        checklist = get_object_or_404(EquipmentChecklist, pk=pk)
        finalize_checklist(checklist)
        messages.success(request, "Файл чеклиста сформирован.")
        return redirect("checklists:checklist_detail", pk=pk)


class ChecklistDeleteView(AdminRequiredMixin, DeleteView):
    model = EquipmentChecklist
    template_name = "core/confirm_delete.html"
    success_url = reverse_lazy("checklists:checklist_list")

    def form_valid(self, form):
        messages.success(self.request, "Чеклист удалён.")
        return super().form_valid(form)
