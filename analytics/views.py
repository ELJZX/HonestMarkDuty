from __future__ import annotations

from datetime import timedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, F, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.views.generic import TemplateView

from accounts.models import User
from checklists.models import EquipmentChecklist
from core.models import Workshop
from documents.models import Document, DocumentStatus
from equipment.models import Equipment, EquipmentStatus
from inventory.models import Condition, InventoryItem, ItemType
from journal.models import JournalEntry
from shifts.models import Shift


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "analytics/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = timezone.localdate()
        month_ago = today - timedelta(days=29)

        ctx["kpi"] = {
            "items": InventoryItem.objects.count(),
            "low_stock": InventoryItem.objects.filter(quantity__lte=F("min_quantity")).count(),
            "used": InventoryItem.objects.filter(condition=Condition.USED).count(),
            "equipment": Equipment.objects.filter(is_camera=False).count(),
            "equipment_repair": Equipment.objects.filter(
                is_camera=False,
                status__in=[EquipmentStatus.REPAIR, EquipmentStatus.MAINTENANCE],
            ).count(),
            "journal": JournalEntry.objects.count(),
            "checklists": EquipmentChecklist.objects.count(),
            "documents": Document.objects.count(),
        }

        ctx["open_shift"] = Shift.objects.open().select_related("opened_by", "workshop").first()
        ctx["shifts_this_month"] = Shift.objects.filter(date__gte=month_ago).count()

        start = today - timedelta(days=13)
        daily = (
            JournalEntry.objects.filter(occurred_at__date__gte=start)
            .annotate(day=TruncDate("occurred_at"))
            .values("day")
            .annotate(total=Count("id"))
            .order_by("day")
        )
        daily_map = {row["day"]: row["total"] for row in daily}
        ctx["journal_series_labels"] = [(start + timedelta(days=i)).strftime("%d.%m") for i in range(14)]
        ctx["journal_series_values"] = [
            daily_map.get(start + timedelta(days=i), 0) for i in range(14)
        ]

        status_labels = dict(EquipmentStatus.choices)
        ctx["equipment_labels"] = [status_labels[c] for c in status_labels]
        ctx["equipment_values"] = [
            Equipment.objects.filter(is_camera=False, status=c).count() for c in status_labels
        ]

        item_types = list(ItemType.objects.all())
        ctx["inventory_labels"] = [t.name for t in item_types]
        ctx["inventory_values"] = [InventoryItem.objects.filter(kind=t).count() for t in item_types]

        ctx["specialists"] = (
            User.objects.filter(is_active=True)
            .annotate(
                entries_created=Count("created_entries", distinct=True),
                shifts_count=Count("shifts_opened", distinct=True),
                checklists_count=Count("checklists_created", distinct=True),
            )
            .order_by("-entries_created")[:10]
        )

        ctx["critical_items"] = (
            InventoryItem.objects.filter(quantity__lte=F("min_quantity"))
            .select_related("location", "category")[:8]
        )
        ctx["maintenance_due"] = (
            Equipment.objects.filter(
                is_camera=False,
                next_maintenance_at__isnull=False,
                next_maintenance_at__lte=today,
            )
            .select_related("site", "workshop")[:8]
        )

        ctx["workshop_stats"] = (
            Workshop.objects.annotate(
                equipment_count=Count(
                    "equipment", filter=Q(equipment__is_camera=False), distinct=True
                ),
                shifts_count=Count("shifts", distinct=True),
                checklists_count=Count("checklists", distinct=True),
            )
            .order_by("-equipment_count")[:10]
        )
        return ctx


class StatisticsView(LoginRequiredMixin, TemplateView):
    template_name = "analytics/statistics.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = timezone.localdate()
        period_start = today - timedelta(days=29)

        ctx["journal_total"] = JournalEntry.objects.filter(occurred_at__date__gte=period_start).count()
        ctx["checklists_total"] = EquipmentChecklist.objects.filter(date__gte=period_start).count()
        ctx["shifts_total"] = Shift.objects.filter(date__gte=period_start).count()

        ctx["status_rows"] = [
            {"label": label, "count": Equipment.objects.filter(is_camera=False, status=value).count()}
            for value, label in EquipmentStatus.choices
        ]

        ctx["entry_rows"] = [
            {"label": label, "count": JournalEntry.objects.filter(entry_type=value).count()}
            for value, label in JournalEntry.EntryType.choices
        ]

        ctx["doc_rows"] = [
            {"label": label, "count": Document.objects.filter(status=value).count()}
            for value, label in DocumentStatus.choices
        ]

        ctx["workshop_rows"] = (
            Workshop.objects.annotate(
                equipment_count=Count(
                    "equipment", filter=Q(equipment__is_camera=False), distinct=True
                ),
                shifts_count=Count("shifts", distinct=True),
                checklists_count=Count("checklists", distinct=True),
            )
            .order_by("name")
        )
        return ctx
