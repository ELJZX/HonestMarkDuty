from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import CharField, Q
from django.db.models.functions import Cast
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
    View,
)

from core.mixins import AdminRequiredMixin, EditorRequiredMixin
from core.models import Workshop
from documents.forms import DocumentForm, DocumentTemplateForm
from documents.models import (
    Document,
    DocumentKind,
    DocumentTemplate,
    DocumentType,
)
from documents.services import build_context, build_docx, render_text
from documents.workshop_docs import (
    DOC_KINDS,
    WORKSHOP_BY_CODE,
    WORKSHOP_DOCUMENTS,
    build_workshop_document,
)
from shifts.models import Shift


class DocumentTemplateListView(LoginRequiredMixin, ListView):
    model = DocumentTemplate
    template_name = "documents/template_list.html"
    context_object_name = "templates"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["workshop_rows"] = WORKSHOP_DOCUMENTS
        return ctx


class WorkshopDocumentDownloadView(LoginRequiredMixin, View):
    """Скачивание документа цеха (техническое заключение / служебная записка)."""

    DOCX_CONTENT_TYPE = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

    def get(self, request, code, kind):
        name = WORKSHOP_BY_CODE.get(code)
        if name is None or kind not in DOC_KINDS:
            raise Http404("Документ не найден")

        shift = Shift.objects.open().select_related("opened_by").first()
        specialist = shift.opened_by if shift and shift.opened_by_id else request.user
        stream = build_workshop_document(name, code, kind, specialist=specialist)
        filename = f"{code}_{kind}_{timezone.localdate():%d.%m.%Y}.docx"
        return FileResponse(
            stream,
            as_attachment=True,
            filename=filename,
            content_type=self.DOCX_CONTENT_TYPE,
        )


class DocumentTemplateCreateView(EditorRequiredMixin, CreateView):
    model = DocumentTemplate
    form_class = DocumentTemplateForm
    template_name = "documents/template_form.html"
    success_url = reverse_lazy("documents:template_list")
    extra_context = {"title": "Новый шаблон документа", "back_url": "documents:template_list"}

    def form_valid(self, form):
        messages.success(self.request, "Шаблон создан.")
        return super().form_valid(form)


class DocumentTemplateUpdateView(EditorRequiredMixin, UpdateView):
    model = DocumentTemplate
    form_class = DocumentTemplateForm
    template_name = "documents/template_form.html"
    success_url = reverse_lazy("documents:template_list")
    extra_context = {"title": "Редактирование шаблона", "back_url": "documents:template_list"}


class DocumentTemplateDeleteView(AdminRequiredMixin, DeleteView):
    model = DocumentTemplate
    template_name = "core/confirm_delete.html"
    success_url = reverse_lazy("documents:template_list")


ARCHIVE_FILENAME_RE = re.compile(
    r"^(?P<code>[a-z0-9]+)_(?P<kind>tz|sl)_(?P<date>\d{2}\.\d{2}\.\d{4})$",
    re.IGNORECASE,
)
DOCUMENT_NUMBER_RE = re.compile(r"^[А-Яа-яA-Za-z]{2}-(\d+)$")


def current_shift_specialist():
    """Дежурный специалист открытой смены (или None)."""
    from shifts.models import Shift

    shift = Shift.objects.open().select_related("opened_by").first()
    return shift.opened_by if shift else None


def next_document_number(kind: str) -> str:
    """Следующий номер документа: ТЗ-0001 / СЛ-0001."""
    prefix = "ТЗ" if kind == DocumentKind.TECHNICAL_REPORT else "СЛ"
    max_number = 0
    for number in Document.objects.filter(kind=kind).values_list("number", flat=True):
        match = DOCUMENT_NUMBER_RE.match(number or "")
        if match:
            max_number = max(max_number, int(match.group(1)))
    return f"{prefix}-{max_number + 1:04d}"


def kind_from_template(template) -> str:
    if not template:
        return ""
    mapping = {
        DocumentType.TECHNICAL_REPORT: DocumentKind.TECHNICAL_REPORT,
        DocumentType.SERVICE_NOTE: DocumentKind.SERVICE_NOTE,
    }
    return mapping.get(template.doc_type, "")


class DocumentListView(LoginRequiredMixin, ListView):
    model = Document
    template_name = "documents/document_list.html"
    context_object_name = "documents"
    paginate_by = 25

    def get_queryset(self):
        qs = Document.objects.select_related("template", "workshop", "created_by")
        params = self.request.GET
        query = (params.get("q") or "").strip()
        if query:
            qs = qs.annotate(
                doc_date_text=Cast("doc_date", output_field=CharField())
            ).filter(
                Q(number__icontains=query)
                | Q(title__icontains=query)
                | Q(workshop__name__icontains=query)
                | Q(created_by__last_name__icontains=query)
                | Q(created_by__first_name__icontains=query)
                | Q(created_by__patronymic__icontains=query)
                | Q(created_by__username__icontains=query)
                | Q(doc_date_text__icontains=query)
            )
        if params.get("kind"):
            qs = qs.filter(kind=params["kind"])
        if params.get("workshop"):
            qs = qs.filter(workshop__name=params["workshop"])
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["kinds"] = DocumentKind.choices
        ctx["workshop_rows"] = WORKSHOP_DOCUMENTS
        ctx["current"] = self.request.GET
        return ctx

    def render_to_response(self, context, **response_kwargs):
        if self.request.GET.get("partial"):
            return render(self.request, "documents/partials/document_rows.html", context)
        return super().render_to_response(context, **response_kwargs)


class DocumentUploadView(EditorRequiredMixin, View):
    """Добавление готового документа в архив по имени файла."""

    def post(self, request):
        upload = request.FILES.get("file")
        if upload is None:
            messages.error(request, "Файл не выбран.")
            return redirect("documents:document_list")

        match = ARCHIVE_FILENAME_RE.match(Path(upload.name).stem)
        if not match:
            messages.error(
                request,
                "Имя файла должно быть вида «код_tz_ДД.ММ.ГГГГ» или «код_sl_ДД.ММ.ГГГГ», "
                "например ceh1_tz_16.09.2026.",
            )
            return redirect("documents:document_list")

        try:
            doc_date = datetime.strptime(match.group("date"), "%d.%m.%Y").date()
        except ValueError:
            messages.error(request, "Не удалось распознать дату в имени файла.")
            return redirect("documents:document_list")

        kind = match.group("kind").lower()
        code = match.group("code").lower()
        workshop_name = WORKSHOP_BY_CODE.get(code)
        workshop = (
            Workshop.objects.filter(name=workshop_name).first() if workshop_name else None
        )

        document = Document(
            kind=kind,
            workshop=workshop,
            doc_date=doc_date,
            number=next_document_number(kind),
            created_by=current_shift_specialist() or request.user,
        )
        document.file.save(Path(upload.name).name, upload, save=False)
        document.save()
        messages.success(request, f"Документ {document.number} добавлен в архив.")
        return redirect("documents:document_list")


class DocumentCreateView(EditorRequiredMixin, CreateView):
    model = Document
    form_class = DocumentForm
    template_name = "documents/document_form.html"

    def get_initial(self):
        initial = super().get_initial()
        if self.request.GET.get("template"):
            initial["template"] = self.request.GET["template"]
        if self.request.GET.get("workshop"):
            initial["workshop"] = self.request.GET["workshop"]
        return initial

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        form = ctx["form"]
        ctx["title"] = "Новый документ"
        ctx["back_url"] = "documents:document_list"
        ctx["preview_title"] = ""
        ctx["preview_body"] = ""
        template = getattr(form, "template_obj", None)
        if template:
            from datetime import date as date_cls

            from django.utils import timezone

            raw_date = form["doc_date"].value()
            doc_date = None
            if raw_date:
                try:
                    doc_date = date_cls.fromisoformat(str(raw_date))
                except ValueError:
                    doc_date = None
            draft = Document(
                template=template,
                workshop=self._workshop(form),
                number=form["number"].value() or "",
                doc_date=doc_date or timezone.localdate(),
                created_by=self.request.user,
                context_data=self._posted_context(form),
            )
            context = build_context(draft)
            ctx["preview_title"] = render_text(template.title_template, context)
            ctx["preview_body"] = render_text(template.body, context)
        return ctx

    @staticmethod
    def _workshop(form):
        from core.models import Workshop

        value = form["workshop"].value()
        return Workshop.objects.filter(pk=value).first() if value else None

    @staticmethod
    def _posted_context(form):
        data = {}
        for name in getattr(form, "dynamic_field_names", []):
            value = form[name].value()
            if value:
                data[name] = value
        return data

    def form_valid(self, form):
        document = form.save(commit=False)
        document.created_by = self.request.user
        document.kind = kind_from_template(document.template)
        document.context_data = form.collect_context()
        document.save()
        document.render(save=False)
        document.file.save(f"document_{document.pk}.docx", build_docx(document), save=False)
        document.save()
        messages.success(self.request, "Документ сформирован.")
        return redirect("documents:document_detail", pk=document.pk)


class DocumentUpdateView(EditorRequiredMixin, UpdateView):
    model = Document
    form_class = DocumentForm
    template_name = "documents/document_form.html"
    extra_context = {"title": "Редактирование документа", "back_url": "documents:document_list"}

    def form_valid(self, form):
        document = form.save(commit=False)
        document.kind = kind_from_template(document.template)
        document.context_data = form.collect_context()
        document.save()
        document.render(save=False)
        document.file.save(f"document_{document.pk}.docx", build_docx(document), save=False)
        document.save()
        messages.success(self.request, "Документ обновлён и пересформирован.")
        return redirect("documents:document_detail", pk=document.pk)


class DocumentDetailView(LoginRequiredMixin, DetailView):
    model = Document
    template_name = "documents/document_detail.html"
    context_object_name = "document"

    def get_queryset(self):
        return Document.objects.select_related("template", "workshop", "created_by")


class DocumentPrintView(LoginRequiredMixin, DetailView):
    model = Document
    template_name = "documents/document_print.html"
    context_object_name = "document"


class DocumentDownloadView(LoginRequiredMixin, View):
    DOCX_CONTENT_TYPE = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

    def get(self, request, pk):
        document = get_object_or_404(Document, pk=pk)
        if not document.file and document.template:
            document.file.save(f"document_{document.pk}.docx", build_docx(document), save=True)
        if not document.file:
            raise Http404("Файл документа не найден.")

        extension = Path(document.file.name).suffix.lower() or ".docx"
        content_types = {
            ".docx": self.DOCX_CONTENT_TYPE,
            ".doc": "application/msword",
        }
        filename = f"{document.kind or 'document'}_{document.number or document.pk}{extension}".replace(" ", "_")
        return FileResponse(
            document.file.open("rb"),
            as_attachment=True,
            filename=filename,
            content_type=content_types.get(extension, "application/octet-stream"),
        )


class DocumentRegenerateView(EditorRequiredMixin, View):
    def post(self, request, pk):
        document = get_object_or_404(Document, pk=pk)
        document.render(save=False)
        document.file.save(f"document_{document.pk}.docx", build_docx(document), save=False)
        document.save()
        messages.success(request, "Документ пересформирован.")
        return redirect("documents:document_detail", pk=pk)


class DocumentDeleteView(AdminRequiredMixin, DeleteView):
    model = Document
    template_name = "core/confirm_delete.html"
    success_url = reverse_lazy("documents:document_list")
