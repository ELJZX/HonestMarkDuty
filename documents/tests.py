import tempfile
from io import BytesIO
from pathlib import Path

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from docx import Document as DocxDocument

from accounts.models import User
from core.models import Workshop
from documents.forms import DocumentForm
from documents.models import Document, DocumentStatus, DocumentTemplate, DocumentType
from documents.services import build_context, build_docx, render_text
from documents.workshop_docs import WORKSHOP_DOCUMENTS


class DocumentTemplateModelTests(TestCase):
    def setUp(self):
        self.workshop = Workshop.objects.create(name="Мясной цех", code="МЦ", chief="Кузнецов Д.В.")
        self.template = DocumentTemplate.objects.create(
            name="Заключение",
            doc_type=DocumentType.TECHNICAL_REPORT,
            title_template="Заключение по {{ workshop_name }}",
            body="Начальник {{ chief }}. Причина: {{ reason }}.",
        )

    def test_placeholders_extracted(self):
        self.assertEqual(self.template.placeholders, ["chief", "reason", "workshop_name"])

    def test_available_for_all_when_no_workshops(self):
        self.assertTrue(self.template.available_for(self.workshop))

    def test_available_for_specific_workshop(self):
        other = Workshop.objects.create(name="Другой", code="Д")
        self.template.workshops.set([self.workshop])
        self.assertTrue(self.template.available_for(self.workshop))
        self.assertFalse(self.template.available_for(other))

    def test_str(self):
        self.assertEqual(str(self.template), "Заключение")


class DocumentServiceTests(TestCase):
    def setUp(self):
        self.workshop = Workshop.objects.create(name="Мясной цех", code="МЦ", chief="Кузнецов Д.В.")
        self.template = DocumentTemplate.objects.create(
            name="Заключение",
            title_template="Заключение по {{ workshop_name }}",
            body="Начальник {{ chief }}. Причина: {{ reason }}.",
        )

    def test_render_text(self):
        self.assertEqual(render_text("Привет, {{ name }}!", {"name": "Иван"}), "Привет, Иван!")

    def test_render_keeps_unknown(self):
        self.assertEqual(render_text("{{ unknown }}", {}), "{{ unknown }}")

    def test_document_render_autofills(self):
        document = Document.objects.create(
            template=self.template, workshop=self.workshop, context_data={"reason": "осмотр"}
        )
        document.render()
        self.assertIn("Мясной цех", document.title)
        self.assertIn("Кузнецов Д.В.", document.body)
        self.assertIn("осмотр", document.body)

    def test_build_context(self):
        document = Document.objects.create(template=self.template, workshop=self.workshop)
        context = build_context(document)
        self.assertEqual(context["workshop_code"], "МЦ")
        self.assertIn("organization", context)
        self.assertIn("date_long", context)

    def test_build_docx_non_empty(self):
        document = Document.objects.create(template=self.template, workshop=self.workshop)
        document.render()
        content = build_docx(document)
        self.assertGreater(len(content.read()), 0)


class DocumentFormTests(TestCase):
    def setUp(self):
        self.template = DocumentTemplate.objects.create(
            name="Заключение",
            title_template="Заголовок {{ workshop_name }}",
            body="Причина: {{ reason }}. Дата: {{ date_long }}",
        )

    def test_dynamic_fields_exclude_auto(self):
        form = DocumentForm(initial={"template": self.template.pk})
        self.assertIn("reason", form.dynamic_field_names)
        self.assertNotIn("workshop_name", form.dynamic_field_names)
        self.assertNotIn("date_long", form.dynamic_field_names)

    def test_collect_context(self):
        form = DocumentForm(
            data={"template": self.template.pk, "doc_date": "2026-09-12", "status": "saved", "reason": "тест"}
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.collect_context(), {"reason": "тест"})


class DocumentViewTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin", password="x", role=User.Role.ADMIN, is_superuser=True, is_staff=True
        )
        self.specialist = User.objects.create_user(
            username="spec", password="x", role=User.Role.SPECIALIST
        )
        self.workshop = Workshop.objects.create(name="Мясной цех", code="МЦ", chief="Кузнецов")
        self.template = DocumentTemplate.objects.create(
            name="Заключение",
            doc_type=DocumentType.TECHNICAL_REPORT,
            title_template="Заключение по {{ workshop_name }}",
            body="Причина: {{ reason }}.",
        )
        self.template.workshops.set([self.workshop])

    def test_template_views(self):
        self.client.force_login(self.specialist)
        self.assertEqual(self.client.get(reverse("documents:template_list")).status_code, 200)
        response = self.client.post(
            reverse("documents:template_create"),
            {
                "name": "Новый шаблон",
                "doc_type": DocumentType.SERVICE_NOTE,
                "title_template": "Записка {{ workshop_name }}",
                "body": "Текст {{ reason }}",
                "is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(DocumentTemplate.objects.filter(name="Новый шаблон").exists())

    def test_document_list_renders(self):
        self.client.force_login(self.specialist)
        self.assertEqual(self.client.get(reverse("documents:document_list")).status_code, 200)

    def test_create_document_generates_docx(self):
        self.client.force_login(self.specialist)
        response = self.client.post(
            reverse("documents:document_create"),
            {
                "template": self.template.pk,
                "workshop": self.workshop.pk,
                "number": "ТЗ-1",
                "doc_date": "2026-09-12",
                "status": DocumentStatus.SAVED,
                "reason": "плановый осмотр",
            },
        )
        self.assertEqual(response.status_code, 302)
        document = Document.objects.get(number="ТЗ-1")
        self.assertIn("Мясной цех", document.title)
        self.assertTrue(document.file)
        self.assertEqual(document.created_by, self.specialist)

    def test_detail_print_download_regenerate(self):
        document = Document.objects.create(
            template=self.template, workshop=self.workshop, number="ТЗ-2", context_data={"reason": "x"}
        )
        document.render()
        document.file.save(f"document_{document.pk}.docx", build_docx(document), save=True)
        self.client.force_login(self.specialist)
        self.assertEqual(self.client.get(reverse("documents:document_detail", args=[document.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("documents:document_print", args=[document.pk])).status_code, 200)
        download = self.client.get(reverse("documents:document_download", args=[document.pk]))
        self.assertEqual(download.status_code, 200)
        self.assertIn("officedocument", download["Content-Type"])
        response = self.client.post(reverse("documents:document_regenerate", args=[document.pk]))
        self.assertEqual(response.status_code, 302)

    def test_update_document(self):
        document = Document.objects.create(
            template=self.template, workshop=self.workshop, number="ТЗ-3", context_data={"reason": "a"}
        )
        document.render()
        self.client.force_login(self.specialist)
        response = self.client.post(
            reverse("documents:document_update", args=[document.pk]),
            {
                "template": self.template.pk,
                "workshop": self.workshop.pk,
                "number": "ТЗ-3",
                "doc_date": "2026-09-12",
                "status": DocumentStatus.SAVED,
                "reason": "обновлено",
            },
        )
        self.assertEqual(response.status_code, 302)
        document.refresh_from_db()
        self.assertIn("обновлено", document.body)

    def test_document_list_filters(self):
        Document.objects.create(
            template=self.template,
            workshop=self.workshop,
            number="ТЗ-9",
            title="Заключение",
            status=DocumentStatus.SAVED,
        )
        self.client.force_login(self.specialist)
        response = self.client.get(
            reverse("documents:document_list"),
            {
                "q": "ТЗ-9",
                "type": DocumentType.TECHNICAL_REPORT,
                "workshop": self.workshop.pk,
                "status": DocumentStatus.SAVED,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ТЗ-9")

    def test_create_form_preview_with_template(self):
        self.client.force_login(self.specialist)
        response = self.client.get(
            reverse("documents:document_create"),
            {"template": self.template.pk, "workshop": self.workshop.pk},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["preview_title"], "Заключение по Мясной цех")

    def test_download_generates_missing_file(self):
        document = Document.objects.create(
            template=self.template,
            workshop=self.workshop,
            number="ТЗ-4",
            context_data={"reason": "x"},
        )
        document.render()
        self.client.force_login(self.specialist)
        response = self.client.get(reverse("documents:document_download", args=[document.pk]))
        self.assertEqual(response.status_code, 200)
        document.refresh_from_db()
        self.assertTrue(document.file)


class WorkshopDocumentViewTests(TestCase):
    def setUp(self):
        self.specialist = User.objects.create_user(
            username="wspec", password="x", role=User.Role.SPECIALIST
        )

    def test_template_list_lists_workshops_and_buttons(self):
        self.client.force_login(self.specialist)
        response = self.client.get(reverse("documents:template_list"))
        self.assertEqual(response.status_code, 200)
        for item in WORKSHOP_DOCUMENTS:
            self.assertContains(response, item["name"])
        self.assertContains(response, "Скачать техническое заключение")
        self.assertContains(response, "Скачать служебную записку")
        self.assertContains(
            response,
            reverse("documents:workshop_document_download", args=["ceh1", "tz"]),
        )

    def test_download_placeholder_document(self):
        self.client.force_login(self.specialist)
        response = self.client.get(
            reverse("documents:workshop_document_download", args=["kmc", "sl"])
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("officedocument", response["Content-Type"])
        expected = f"kmc_sl_{timezone.localdate():%d.%m.%Y}.docx"
        self.assertIn(expected, response["Content-Disposition"])
        body = b"".join(response.streaming_content)
        self.assertGreater(len(body), 0)
        text = "\n".join(p.text for p in DocxDocument(BytesIO(body)).paragraphs)
        self.assertIn("Служебная записка", text)
        self.assertIn("Кисломолочный цех", text)

    def test_download_uses_sample_when_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            sample = Path(tmp) / "tv_tz.docx"
            docx = DocxDocument()
            docx.add_paragraph("Цех: {{ workshop_name }} ({{ workshop_code }})")
            docx.add_paragraph("Дата: {{ date }}")
            docx.save(str(sample))

            with override_settings(DOCUMENT_SAMPLES_DIR=tmp):
                self.client.force_login(self.specialist)
                response = self.client.get(
                    reverse("documents:workshop_document_download", args=["tv", "tz"])
                )
                body = b"".join(response.streaming_content)

        text = "\n".join(p.text for p in DocxDocument(BytesIO(body)).paragraphs)
        self.assertIn("Творожный цех", text)
        self.assertIn("(tv)", text)
        self.assertIn(timezone.localdate().strftime("%d.%m.%Y"), text)
        self.assertNotIn("{{", text)

    def test_unknown_code_returns_404(self):
        self.client.force_login(self.specialist)
        response = self.client.get(
            reverse("documents:workshop_document_download", args=["nope", "tz"])
        )
        self.assertEqual(response.status_code, 404)

    def test_requires_login(self):
        response = self.client.get(
            reverse("documents:workshop_document_download", args=["ceh1", "tz"])
        )
        self.assertEqual(response.status_code, 302)


class WorkshopDocumentSampleEdgeTests(TestCase):
    def setUp(self):
        self.specialist = User.objects.create_user(
            username="ws-sample", password="x", role=User.Role.SPECIALIST
        )

    def test_sample_with_plain_paragraph_and_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            sample = Path(tmp) / "tv_tz.docx"
            docx = DocxDocument()
            docx.add_paragraph("Обычный текст без подстановок")
            table = docx.add_table(rows=1, cols=1)
            table.cell(0, 0).text = "Цех: {{ workshop_name }}"
            docx.save(str(sample))

            with override_settings(DOCUMENT_SAMPLES_DIR=tmp):
                self.client.force_login(self.specialist)
                response = self.client.get(
                    reverse("documents:workshop_document_download", args=["tv", "tz"])
                )
                body = b"".join(response.streaming_content)

        parsed = DocxDocument(BytesIO(body))
        paragraphs = "\n".join(p.text for p in parsed.paragraphs)
        self.assertIn("Обычный текст без подстановок", paragraphs)
        table_text = "\n".join(
            cell.text for table in parsed.tables for row in table.rows for cell in row.cells
        )
        self.assertIn("Творожный цех", table_text)


class DocumentFormEdgeTests(TestCase):
    def test_form_without_template_has_no_dynamic_fields(self):
        form = DocumentForm()
        self.assertIsNone(form.template_obj)
        self.assertEqual(form.dynamic_field_names, [])


class DocumentCreatePreviewEdgeTests(TestCase):
    def setUp(self):
        self.specialist = User.objects.create_user(
            username="preview-edge", password="x", role=User.Role.SPECIALIST
        )
        self.workshop = Workshop.objects.create(name="Цех", code="Ц")
        self.template = DocumentTemplate.objects.create(
            name="Шаблон",
            title_template="Т {{ workshop_name }}",
            body="Причина: {{ reason }}",
        )
        self.template.workshops.set([self.workshop])

    def test_invalid_post_builds_preview_with_bad_date(self):
        self.client.force_login(self.specialist)
        response = self.client.post(
            reverse("documents:document_create"),
            {
                "template": self.template.pk,
                "workshop": self.workshop.pk,
                "number": "",
                "doc_date": "не дата",
                "reason": "значение",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("reason", response.context["form"].dynamic_field_names)
