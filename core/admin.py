from django.contrib import admin

from .models import Property, Tenant


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ("name", "address", "owner")
    list_filter = ("owner",)
    search_fields = ("name", "address")


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("company_name", "contact_name", "email", "owner")
    list_filter = ("owner",)
    search_fields = ("company_name", "contact_name", "email")
