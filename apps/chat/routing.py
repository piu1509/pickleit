from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(r"ws/chat/(?P<room_name>\w+)/$", consumers.ChatConsumer.as_asgi()),
    re_path(r"ws/notify/(?P<room_name>\w+)/$", consumers.NotificationConsumer.as_asgi()),


    #updated
    re_path(r"ws/chat_history/$", consumers.ChatHistory.as_asgi()),
    re_path(r"ws/chat_room/(?P<room_name>\w+)/$", consumers.ChatUser.as_asgi()),
]