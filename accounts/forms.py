from __future__ import annotations

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from accounts.models import User
from core.forms import StyledModelForm


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        label="Логин",
        widget=forms.TextInput(attrs={"class": "field-input", "autofocus": True, "placeholder": "username"}),
    )
    password = forms.CharField(
        label="Пароль",
        widget=forms.PasswordInput(attrs={"class": "field-input", "placeholder": "••••••••"}),
    )


class UserCreateForm(UserCreationForm):
    class Meta:
        model = User
        fields = (
            "username",
            "last_name",
            "first_name",
            "patronymic",
            "email",
            "role",
            "position",
            "phone",
            "is_active",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", "field-checkbox")
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs.setdefault("class", "field-input field-select")
            else:
                field.widget.attrs.setdefault("class", "field-input")


class UserUpdateForm(StyledModelForm):
    class Meta:
        model = User
        fields = (
            "username",
            "last_name",
            "first_name",
            "patronymic",
            "email",
            "role",
            "position",
            "phone",
            "is_active",
        )
