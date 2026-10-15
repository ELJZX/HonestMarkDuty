from __future__ import annotations

from core.forms import StyledModelForm
from services.models import Service


class ServiceForm(StyledModelForm):
    class Meta:
        model = Service
        fields = ("name", "url")
