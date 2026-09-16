from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
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
from documents.forms import DocumentForm, DocumentTemplateForm
from documents.models import Document, DocumentStatus, DocumentTemplate
from documents.services import build_context, build_docx, render_text
from documents.workshop_docs import (
    DOC_KINDS,
    WORKSHOP_BY_CODE,
    WORKSHOP_DOCUMENTS,
    build_workshop_document,
)


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

        stream = build_workshop_document(name, code, kind)
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


class DocumentListView(LoginRequiredMixin, ListView):
    model = Document
    template_name = "documents/document_list.html"
    context_object_name = "documents"
    paginate_by = 25

    def get_queryset(self):
        qs = Document.objects.select_related("template", "workshop", "created_by")
        params = self.request.GET
        if params.get("q"):
            q = params["q"]
            qs = qs.filter(title__icontains=q) | qs.filter(number__icontains=q)
        if params.get("type"):
            qs = qs.filter(template__doc_type=params["type"])
        if params.get("workshop"):
            qs = qs.filter(workshop_id=params["workshop"])
        if params.get("status"):
            qs = qs.filter(status=params["status"])
        return qs

    def get_context_data(self, **kwargs):
        from core.models import Workshop
        from documents.models import DocumentType

        ctx = super().get_context_data(**kwargs)
        ctx["types"] = DocumentType.choices
        ctx["statuses"] = DocumentStatus.choices
        ctx["workshops"] = Workshop.objects.all()
        ctx["current"] = self.request.GET
        return ctx


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
        if not document.file:
            document.file.save(f"document_{document.pk}.docx", build_docx(document), save=True)
        filename = f"{document.template.doc_type}_{document.number or document.pk}.docx".replace(" ", "_")
        return FileResponse(
            document.file.open("rb"),
            as_attachment=True,
            filename=filename,
            content_type=self.DOCX_CONTENT_TYPE,
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
