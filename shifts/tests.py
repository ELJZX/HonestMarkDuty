from django.test import TestCase
from django.utils import timezone

from journal.models import JournalEntry, JournalExport
from shifts.models import Shift


class ShiftAndJournalTests(TestCase):
    def setUp(self):
        self.shift = Shift.objects.create(status=Shift.Status.OPEN)

    def test_done_entry_sets_resolved_at(self):
        entry = JournalEntry.objects.create(
            shift=self.shift,
            source_location="Линия №1",
            problem="Не читается код",
            status=JournalEntry.Status.DONE,
        )
        self.assertIsNotNone(entry.resolved_at)

    def test_new_entry_has_no_resolved_at(self):
        entry = JournalEntry.objects.create(
            shift=self.shift,
            source_location="Линия №2",
            problem="Проблема",
        )
        self.assertIsNone(entry.resolved_at)

    def test_shift_close_exports_excel(self):
        JournalEntry.objects.create(
            shift=self.shift, source_location="Цех", problem="Тест", solution="Готово",
            status=JournalEntry.Status.DONE,
        )
        from journal.exports import export_shift_to_excel

        self.shift.status = Shift.Status.CLOSED
        self.shift.closed_at = timezone.now()
        self.shift.save()
        export = export_shift_to_excel(self.shift, None)
        self.assertIsInstance(export, JournalExport)
        self.assertEqual(export.entries_count, 1)
        self.assertTrue(export.file.name.endswith(".xlsx"))

    def test_export_skipped_for_empty_shift(self):
        from journal.exports import export_shift_to_excel

        self.assertIsNone(export_shift_to_excel(self.shift, None))
