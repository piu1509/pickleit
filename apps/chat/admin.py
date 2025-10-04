from django.contrib import admin
from apps.chat.models import *
from django.urls import path
from django.shortcuts import redirect, reverse
from apps.admin_side.views import send_universal_notification
from django.utils.html import format_html
# Register your models here.

admin.site.register(Room)
admin.site.register(MessageBox)
admin.site.register(NotifiRoom)
# admin.site.register(NotificationBox)

class NotificationBoxAdmin(admin.ModelAdmin):
    list_display = ('titel', 'text_message', 'is_read', 'created_at', 'is_universal', 'send_universal_link')
    list_filter = ('is_read', 'is_universal', 'created_at')
    search_fields = ('titel', 'text_message')

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('send_universal_notification/', self.admin_site.admin_view(send_universal_notification), name='send_universal_notification'),
        ]
        return custom_urls + urls

    def send_universal_link(self, obj):
        url = reverse('admin:send_universal_notification')
        return format_html(f'<a class="button" href="{url}">Send Universal Notification</a>')

    send_universal_link.short_description = 'Send Universal Notification'
    send_universal_link.allow_tags = True

# Register the model with the custom admin class
admin.site.register(NotificationBox, NotificationBoxAdmin)