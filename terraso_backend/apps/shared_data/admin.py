from django.contrib import admin

from .models import DataEntry, VisualizationConfig


@admin.register(DataEntry)
class DataEntryAdmin(admin.ModelAdmin):
    list_display = ("name", "url", "resource_type", "created_by")


@admin.register(VisualizationConfig)
class VisualizationConfigAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "data_entry", "configuration", "created_by", "created_at")
