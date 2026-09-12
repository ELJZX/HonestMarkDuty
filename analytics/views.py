from __future__ import annotations

from datetime import timedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Avg, Count, F, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.views.generic import TemplateView

from accounts.models import User
from core.models import Workshop
from documents.models import Document, DocumentStatus
from equipment.models import Equipment, EquipmentStatus
from inventory.models import Condition, InventoryItem, ItemKind
from journal.models import JournalEntry
from shifts.models import Shift


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "analytics/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = timezone.localdate()
        week_ago = today - timedelta(days=6)
        month_ago = today - timedelta(days=29)

        # --- KPI ---
        ctx["kpi"] = {
            "items": InventoryItem.objects.count(),
            "low_stock": InventoryItem.objects.filter(quantity__lte=F("min_quantity")).count(),
            "worn": InventoryItem.objects.filter(
                condition__in=[Condition.WORN, Condition.NEEDS_REPAIR, Condition.BROKEN]
            ).count(),
            "equipment": Equipment.objects.count(),
            "equipment_repair": Equipment.objects.filter(
                status__in=[EquipmentStatus.REPAIR, EquipmentStatus.MAINTENANCE]
            ).count(),
            "open_journal": JournalEntry.objects.exclude(status=JournalEntry.Status.DONE).count(),
            "documents": Document.objects.count(),
        }

        # --- Смена ---
        ctx["open_shift"] = Shift.objects.open().select_related("opened_by", "workshop").first()
        ctx["shifts_this_month"] = Shift.objects.filter(date__gte=month_ago).count()

        # --- Журнал по дням (14 дней) ---
        start = today - timedelta(days=13)
        daily = (
            JournalEntry.objects.filter(received_at__date__gte=start)
            .annotate(day=TruncDate("received_at"))
            .values("day")
            .annotate(total=Count("id"))
            .order_by("day")
        )
        daily_map = {row["day"]: row["total"] for row in daily}
        ctx["journal_series_labels"] = [(start + timedelta(days=i)).strftime("%d.%m") for i in range(14)]
        ctx["journal_series_values"] = [
            daily_map.get(start + timedelta(days=i), 0) for i in range(14)
        ]

        # --- Оборудование по состояниям ---
        status_labels = dict(EquipmentStatus.choices)
        ctx["equipment_labels"] = [status_labels[c] for c in status_labels]
        ctx["equipment_values"] = [
            Equipment.objects.filter(status=c).count() for c in status_labels
        ]

        # --- Склад по типам ---
        kind_labels = dict(ItemKind.choices)
        ctx["inventory_labels"] = [kind_labels[k] for k in kind_labels]
        ctx["inventory_values"] = [InventoryItem.objects.filter(kind=k).count() for k in kind_labels]

        # --- Журнал по приоритетам (открытые) ---
        priority_labels = dict(JournalEntry.Priority.choices)
        ctx["priority_labels"] = [priority_labels[p] for p in priority_labels]
        ctx["priority_values"] = [
            JournalEntry.objects.filter(priority=p)
            .exclude(status=JournalEntry.Status.DONE)
            .count()
            for p in priority_labels
        ]

        # --- Статистика специалистов ---
        ctx["specialists"] = (
            User.objects.filter(is_active=True)
            .annotate(
                entries_created=Count("created_entries", distinct=True),
                entries_done=Count(
                    "created_entries",
                    filter=Q(created_entries__status=JournalEntry.Status.DONE),
                    distinct=True,
                ),
                shifts_count=Count("shifts_opened", distinct=True),
            )
            .order_by("-entries_created")[:10]
        )

        # --- Критические позиции ---
        ctx["critical_items"] = (
            InventoryItem.objects.filter(quantity__lte=F("min_quantity"))
            .select_related("location", "category")[:8]
        )
        ctx["maintenance_due"] = (
            Equipment.objects.filter(next_maintenance_at__isnull=False, next_maintenance_at__lte=today)
            .select_related("site", "workshop")[:8]
        )

        # --- Активность по цехам ---
        ctx["workshop_stats"] = (
            Workshop.objects.annotate(
                journal_count=Count("journal_entries", distinct=True),
                equipment_count=Count("equipment", distinct=True),
            )
            .order_by("-journal_count")[:10]
        )

        ctx["avg_wear"] = InventoryItem.objects.aggregate(avg=Avg("wear_percent"))["avg"] or 0
        return ctx


class StatisticsView(LoginRequiredMixin, TemplateView):
    template_name = "analytics/statistics.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = timezone.localdate()
        period_start = today - timedelta(days=29)

        ctx["journal_total"] = JournalEntry.objects.filter(received_at__date__gte=period_start).count()
        ctx["journal_done"] = JournalEntry.objects.filter(
            received_at__date__gte=period_start, status=JournalEntry.Status.DONE
        ).count()
        ctx["shifts_total"] = Shift.objects.filter(date__gte=period_start).count()

        ctx["status_rows"] = [
            {
                "label": label,
                "count": Equipment.objects.filter(status=value).count(),
            }
            for value, label in EquipmentStatus.choices
        ]

        ctx["entry_rows"] = [
            {
                "label": label,
                "count": JournalEntry.objects.filter(status=value).count(),
            }
            for value, label in JournalEntry.Status.choices
        ]

        ctx["doc_rows"] = [
            {
                "label": label,
                "count": Document.objects.filter(status=value).count(),
            }
            for value, label in DocumentStatus.choices
        ]

        ctx["workshop_rows"] = (
            Workshop.objects.annotate(
                journal_count=Count("journal_entries", distinct=True),
                equipment_count=Count("equipment", distinct=True),
                shifts_count=Count("shifts", distinct=True),
            )
            .order_by("name")
        )
        return ctx
