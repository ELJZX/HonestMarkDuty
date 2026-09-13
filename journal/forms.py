from __future__ import annotations

from django import forms

from core.forms import StyledModelForm
from journal.models import JournalEntry

# Оборудование / линии (выпадающий список)
EQUIPMENT_LINES = [
    "Serac New",
    "Ecolean 1",
    "Ecolean 2",
    "FinPack 1",
    "FinPack 2",
    "FinPack 3",
    "Serac Old",
    "AVE",
    "Trepko",
    "Finnah",
    "C3 Flex",
    "Tetra top",
    "Джонгай",
    "Humba",
    "A3",
    "Serac (ЦСМ)",
    "SignalPack 1",
    "SignalPack 2",
    "Stabilobek 3",
    "Stabilobek 1",
    "Mondini 3",
    "Mondini 4",
    "Моцарелла (малыш)",
    "A1(1)",
    "A1(2)",
    "EL3",
    "EL4",
    "SignalPack 3",
    "SignalPack 4",
    "Малыш (цех творожного завода)",
    "Малыш (ручное сканирование)",
    "Малыш (цех глазированных сырков)",
]

PRINT_HEADS = ["53", "32"]


class JournalEntryForm(StyledModelForm):
    equipment_line = forms.ChoiceField(
        label="Оборудование / Линия", required=False, choices=[]
    )
    print_head = forms.ChoiceField(label="Печ. головка", required=False, choices=[])

    class Meta:
        model = JournalEntry
        fields = (
            "occurred_at",
            "specialist",
            "equipment_line",
            "downtime",
            "action_task",
            "solution",
            "print_head",
            "mileage",
        )
        widgets = {
            "occurred_at": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            ),
            "action_task": forms.Textarea(attrs={"rows": 3}),
            "solution": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["occurred_at"].input_formats = [
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
        ]
        self.fields["equipment_line"].choices = self._choices(
            EQUIPMENT_LINES, self._current("equipment_line")
        )
        self.fields["print_head"].choices = self._choices(
            PRINT_HEADS, self._current("print_head")
        )

    def _current(self, name: str):
        if self.instance and self.instance.pk:
            return getattr(self.instance, name) or None
        return None

    @staticmethod
    def _choices(values, extra):
        options = [("", "— выберите —")]
        seen = set()
        for value in values:
            if value not in seen:
                options.append((value, value))
                seen.add(value)
        if extra and extra not in seen:
            options.append((extra, extra))
        return options
