from django.db import models
from apps.user.models import *

from apps.team.models import *
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
# Create your models here.

class Room(models.Model):
    name = models.CharField(max_length=100)
    user_one = models.ForeignKey(User, on_delete=models.CASCADE,related_name="user_one")
    user_two = models.ForeignKey(User, on_delete=models.CASCADE,related_name="user_two")
    is_blocked_user_one = models.BooleanField(default=False)
    is_blocked_user_two = models.BooleanField(default=False)

    def __str__(self) :
        return f"{self.name}, {self.user_one.email}, {self.user_two.email}"
    

class MessageBox(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name="room")
    sender_user = models.ForeignKey(User, on_delete=models.CASCADE,related_name="sender_user")
    reciver_user = models.ForeignKey(User, on_delete=models.CASCADE,related_name="reciver_user")
    is_read = models.BooleanField(default=False)
    text_message = models.TextField()
    send_file = models.FileField(upload_to="chat_file/", null=True, blank=True)
    send_image = models.FileField(upload_to="chat_image/", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    def __str__(self) :
        return f"Room: {self.room.name}, Sender:{self.sender_user.email}, Reciver:{self.reciver_user.email}"



class NotifiRoom(models.Model):
    name = models.CharField(max_length=100)
    user = models.ForeignKey(User, on_delete=models.CASCADE,related_name="room_user",null=True, blank=True)
    
    def __str__(self) :
        return f"{self.name}"   

class NotificationBox(models.Model):
    room = models.ForeignKey(NotifiRoom, on_delete=models.CASCADE, related_name="NotifiRoom", null=True, blank=True)
    titel = models.CharField(max_length=100)
    text_message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    notify_for = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notification_for",null=True, blank=True)
    is_universal = models.BooleanField(default=False)

    def __str__(self) :
        return f"{self.titel}:-{self.text_message}, Read-status{self.is_read}"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super(NotificationBox, self).save(*args, **kwargs)
        # Send notification to WebSocket clients only if the instance is being updated, not when it's being created.
        self.send_notification()

    def send_notification(self):
        channel_layer = get_channel_layer()
        
        if self.is_universal:
            group_name = "universal_notifications"
        else:
            group_name = f"notifications_{self.room.name}"
        
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "send_notification",
                "notification": {
                    "id": self.id,
                    "title": self.titel,
                    "text_message": self.text_message,
                    "is_read": self.is_read,
                    "created_at": self.created_at.isoformat(),
                }
            }
        )