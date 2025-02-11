from django.urls import re_path

from apps.chat import consumers

websocket_urlpatterns = [
    re_path(r"ws/chat/(?P<room_name>\w+)/$", consumers.ChatConsumer.as_asgi()),
    # re_path(r"ws/notification/(?P<notification_name>\w+)/$", consumers.Natification.as_asgi()),
    re_path(r"ws/notify/(?P<room_name>\w+)/$", consumers.NotificationConsumer.as_asgi()),
]