from django.test import TestCase

from core.models import Workshop
from documents.models import Document, DocumentTemplate, DocumentType
from documents.services import build_context, render_text


class DocumentRenderingTests(TestCase):
    def setUp(self):
        self.workshop = Workshop.objects.create(
            name="Мясной цех", code="МЦ", chief="Кузнецов Д.В."
        )
        self.template = DocumentTemplate.objects.create(
            name="Техническое заключение",
            doc_type=DocumentType.TECHNICAL_REPORT,
            title_template="Заключение по {{ workshop_name }}",
            body="Начальник {{ chief }}. Дата {{ date_long }}. Причина: {{ reason }}.",
        )

    def test_render_text_replaces_placeholders(self):
        result = render_text("Привет, {{ name }}!", {"name": "Иван"})
        self.assertEqual(result, "Привет, Иван!")

    def test_document_auto_fills_workshop_fields(self):
        document = Document.objects.create(
            template=self.template,
            workshop=self.workshop,
            number="ТЗ-1",
            context_data={"reason": "осмотр"},
        )
        document.render()
        self.assertIn("Мясной цех", document.title)
        self.assertIn("Кузнецов Д.В.", document.body)
        self.assertIn("осмотр", document.body)

    def test_build_context_contains_organization(self):
        document = Document.objects.create(template=self.template, workshop=self.workshop)
        context = build_context(document)
        self.assertEqual(context["workshop_code"], "МЦ")
        self.assertIn("organization", context)

    def test_docx_generation(self):
        document = Document.objects.create(template=self.template, workshop=self.workshop)
        document.render()
        from documents.services import build_docx

        content = build_docx(document)
        self.assertGreater(len(content.read()), 0)
