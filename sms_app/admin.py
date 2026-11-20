from django.contrib import admin

from .models import SMSLog


@admin.register(SMSLog)
class SMSLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "recipient", "status", "provider_sid")
    list_filter = ("status",)
    search_fields = ("recipient", "body", "provider_sid")
