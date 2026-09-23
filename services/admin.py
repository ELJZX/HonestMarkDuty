from django.contrib import admin

from services.models import Service


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "url", "sort_order", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "url")
