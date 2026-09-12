from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView

from accounts.forms import LoginForm, UserCreateForm, UserUpdateForm
from accounts.models import User
from core.mixins import AdminRequiredMixin


class AppLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True


class AppLogoutView(LogoutView):
    next_page = reverse_lazy("accounts:login")


class UserListView(AdminRequiredMixin, ListView):
    model = User
    template_name = "accounts/user_list.html"
    context_object_name = "users"
    paginate_by = 30


class UserCreateView(AdminRequiredMixin, CreateView):
    model = User
    form_class = UserCreateForm
    template_name = "accounts/user_form.html"
    success_url = reverse_lazy("accounts:user_list")
    extra_context = {"title": "Новый пользователь", "back_url": "accounts:user_list"}

    def form_valid(self, form):
        messages.success(self.request, "Пользователь создан.")
        return super().form_valid(form)


class UserUpdateView(AdminRequiredMixin, UpdateView):
    model = User
    form_class = UserUpdateForm
    template_name = "accounts/user_form.html"
    success_url = reverse_lazy("accounts:user_list")
    extra_context = {"title": "Редактирование пользователя", "back_url": "accounts:user_list"}

    def form_valid(self, form):
        messages.success(self.request, "Пользователь обновлён.")
        return super().form_valid(form)
