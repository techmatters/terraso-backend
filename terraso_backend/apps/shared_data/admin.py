from django.contrib import admin

from .models import DataEntry


@admin.register(DataEntry)
class DataEntryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "url", "resource_type", "created_by")
