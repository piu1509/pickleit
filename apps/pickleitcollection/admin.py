from django.contrib import admin
from apps.pickleitcollection.models import *
admin.site.register(AdvertisementDurationRate)
@admin.register(Advertisement)
class AdvertisementAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'name', 'company_name', 'approved_by_admin', 'admin_approve_status', 
        'start_date', 'end_date', 'view_count', 'created_at'
    )
    list_filter = ('admin_approve_status', 'approved_by_admin', 'start_date', 'end_date', 'created_at')
    search_fields = ('name', 'company_name', 'company_website', 'url', 'secret_key')
    readonly_fields = ('uuid', 'view_count', 'created_at')
    autocomplete_fields = ['created_by']
    fieldsets = (
        ('Basic Info', {
            'fields': ('uuid', 'secret_key', 'name', 'company_name', 'company_website', 'description')
        }),
        ('Advertisement Details', {
            'fields': ('duration', 'image', 'script_text', 'url')
        }),
        ('Status', {
            'fields': ('approved_by_admin', 'admin_approve_status', 'view_count')
        }),
        ('Timeline', {
            'fields': ('start_date', 'end_date', 'created_at', 'created_by')
        }),
    )
admin.site.register(ChargeAmount)
admin.site.register(AmbassadorsDetails)
admin.site.register(Tags)
admin.site.register(Notifications)
admin.site.register(AmbassadorsPost)
admin.site.register(AdvertiserFacility)
admin.site.register(PaymentDetails)


