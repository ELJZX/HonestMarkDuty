"""Цеха и линии в утверждённом порядке: python manage.py seed_structure"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import IntegrityError

from core.models import ProductionLine, Workshop

STRUCTURE = [
    ("Цех №1", "ЦЕХ1", ["New Serac", "Ecolean 1", "FP 1", "FP 2", "FP 3", "Old Serac"]),
    ("КМЦ", "КМЦ", ["AVE", "Finnah", "Trepko", "C3 Flex", "Джонга 1,2"]),
    ("ПМЦ", "ПМЦ", ["Humba"]),
    ("ПСМ", "ПСМ", ["Школьник (А1(1),А1(2))", "EL4", "A3 Flex", "Serac"]),
    ("Творожный цех", "ТВЦ", ["SB 3", "Mondini 4", "SP 4", "SP3", "SP 2", "SP1"]),
]


class Command(BaseCommand):
    help = "Создаёт цеха и линии в заданном порядке"

    def _unique_code(self, workshop, code: str, fallback: str) -> str:
        conflict = Workshop.objects.filter(code=code).exclude(pk=workshop.pk).exists()
        return fallback if conflict else code

    def handle(self, *args, **options):
        verbose = options.get("verbosity", 1) > 0
        listed_ids = []
        for w_index, (name, code, lines) in enumerate(STRUCTURE):
            workshop, _ = Workshop.objects.get_or_create(
                name=name, defaults={"code": code, "is_active": True}
            )
            workshop.code = self._unique_code(workshop, code, f"WS{w_index + 1}")
            workshop.sort_order = w_index
            workshop.is_active = True
            try:
                workshop.save()
            except IntegrityError:
                workshop.code = f"WS{w_index + 1}"
                workshop.save()
            listed_ids.append(workshop.pk)

            line_ids = []
            for l_index, line_name in enumerate(lines):
                line, _ = ProductionLine.objects.get_or_create(
                    workshop=workshop,
                    name=line_name,
                    defaults={"sort_order": l_index, "is_active": True},
                )
                line.sort_order = l_index
                line.is_active = True
                line.save()
                line_ids.append(line.pk)

            others = (
                ProductionLine.objects.filter(workshop=workshop).exclude(pk__in=line_ids)
            )
            others.update(is_active=False)

        remaining = Workshop.objects.exclude(pk__in=listed_ids)
        remaining.update(is_active=False)

        if not verbose:
            return
        self.stdout.write(self.style.SUCCESS("Структура цехов и линий обновлена."))
        for name, _code, lines in STRUCTURE:
            self.stdout.write(f"  {name}: {', '.join(lines)}")
