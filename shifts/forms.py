from __future__ import annotations

from core.forms import StyledModelForm
from shifts.models import Shift, ShiftCheck


class ShiftOpenForm(StyledModelForm):
    """Приём смены без полей ввода — дата и время проставляются автоматически."""

    class Meta:
        model = Shift
        fields = ()


class ShiftCloseForm(StyledModelForm):
    """Сдача смены без полей ввода — только подтверждение действия."""

    class Meta:
        model = Shift
        fields = ()


class ShiftCheckForm(StyledModelForm):
    class Meta:
        model = ShiftCheck
        fields = ("item", "condition", "comment")
