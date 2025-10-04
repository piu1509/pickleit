import json
from urllib.parse import parse_qs
from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer
from apps.user.models import User
from .models import *
from channels.consumer import AsyncConsumer
from channels.db import database_sync_to_async
from django.core.cache import cache
from django.utils import timezone
import pytz
import redis
from datetime import datetime
from .views import *
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from django.utils.timezone import localtime

def get_bad_words_list():
    with open('list_of_bad_words.txt', 'r') as file:
        bad_words = file.read().splitlines()
    return bad_words 

bad_words_list = get_bad_words_list()


class ChatConsumer(WebsocketConsumer):
    def connect(self):
        self.room_name = self.scope["url_route"]["kwargs"]["room_name"]
        self.room_group_name = "chat_%s" % self.room_name
        
        # Extracting query string from the scope
        query_string = self.scope["query_string"].decode("utf-8")
        # Parsing query string into a dictionary
        query_params = parse_qs(query_string)
        # Retrieving sender_uuid and sender_secret_key from the parsed query parameters
        self.sender_uuid = query_params.get('sender_uuid', [''])[0]
        self.sender_secret_key = query_params.get('sender_secret_key', [''])[0]
        self.sender_email = query_params.get('sender_email', [''])[0]
        self.room__name = self.room_name
        # set reciver
        check_sender = User.objects.filter(uuid=self.sender_uuid, secret_key=self.sender_secret_key)
        check_room = Room.objects.filter(name=self.room_name).filter(Q(user_one=check_sender.first()) | Q(user_two=check_sender.first()))
        print(check_sender)
        print(check_room)
        if check_sender.exists() and check_room.exists():
            self.get_check_sender = check_sender.first()
            self.get_room = check_room.first()
            u1 = self.get_room.user_one
            u2 = self.get_room.user_two
            print("checkkjdnksjdnk----",u1,u2)
            
            if self.get_check_sender == u1 :
                self.get_reciver_user = u2
            else:
                self.get_reciver_user = u1
        
        # making cache for online user
        cache.set(str(self.sender_uuid),str(self.sender_secret_key))
        cache.set(str(self.sender_email),True)
                    
        # Join room group
        async_to_sync(self.channel_layer.group_add)(
            self.room_group_name, self.channel_name
        )

        self.accept()
        # when socket connecting frist checking that user data and updating as seen ...
        self.send_initial_data()
        
    def send_initial_data(self):
        all_messages = MessageBox.objects.filter(room=self.get_room)
        check_sender = User.objects.filter(uuid=self.sender_uuid, secret_key=self.sender_secret_key)
        check_room = Room.objects.filter(name=self.room_name)
        if check_sender.exists() and check_room.exists():
            self.get_check_sender = check_sender.first()
            self.get_room = check_room.first()          
            u1 = self.get_room.user_one
            u2 = self.get_room.user_two
            if self.get_check_sender == u1 :
                self.get_reciver_user = u2
            else:
                self.get_reciver_user = u1
            all_msg = MessageBox.objects.filter(room=self.get_room, reciver_user=self.get_check_sender, is_read=False)
            online_user = []
            block_status = False

            if cache.get(str(self.sender_email)) :
                online_user.append(str(self.sender_email))
            if cache.get(str(self.get_reciver_user.email)) :
                online_user.append(str(self.get_reciver_user.email))

            if self.get_room.is_blocked_user_one and self.get_room.is_blocked_user_two:
                block_status = True
                if self.get_room.is_blocked_user_one and self.get_room.is_blocked_user_two and self.get_check_sender == self.get_room.user_one:
                    message = f"You have blocked {self.get_room.user_two.first_name} and even {self.get_room.user_two.first_name} has also blocked you."
                if self.get_room.is_blocked_user_one and self.get_room.is_blocked_user_two and self.get_check_sender == self.get_room.user_two:
                    message = f"You have blocked {self.get_room.user_one.first_name} and even {self.get_room.user_one.first_name} has also blocked you."
                
                

            elif self.get_room.is_blocked_user_one or self.get_room.is_blocked_user_two:   
                block_status = True             
                if self.get_room.is_blocked_user_one and self.get_check_sender == self.get_room.user_one:
                    message = f"{self.get_room.user_two.first_name} has blocked you."
                if self.get_room.is_blocked_user_one and self.get_check_sender == self.get_room.user_two:
                    message = f"You have blocked {self.get_room.user_one.first_name}"
                if self.get_room.is_blocked_user_two and self.get_check_sender == self.get_room.user_one:
                    message = f"You have blocked {self.get_room.user_two.first_name}."
                if self.get_room.is_blocked_user_two and self.get_check_sender == self.get_room.user_two:
                    message = f"{self.get_room.user_one.first_name} has blocked you."
            else:
                block_status = False
                message = None
            
            sender_messages = MessageBox.objects.filter(room=self.get_room, sender_user=check_sender.first())
            first_time_status = False
            if not sender_messages:
                first_time_status = True
            self.receive(text_data=json.dumps({"message": message,"get_datetime":"","online_user":online_user, "block_status":block_status, "first_time_chat":first_time_status}))
            
            for i in all_msg :
                self.send(text_data=json.dumps({"message": i.text_message,"get_datetime":str(i.created_at),"online_user":online_user, "block_status":block_status, "first_time_chat":first_time_status}))
                all_msg.filter(id=i.id).update(is_read=True)
            filtered_messages = all_messages.filter(Q(text_message__isnull=False) & ~Q(text_message=" "))
            serializer = MessageBoxSerializer(filtered_messages, many=True)   
            for i in serializer.data:
                get_user = User.objects.filter(uuid=self.sender_uuid,secret_key=self.sender_secret_key).first()
                check_sendor_id = get_user.id
                check_sendor_uuid = str(get_user.uuid)
                check_sendor_secret_key = str(get_user.secret_key)
                i["sendor_uuid"] = str(check_sendor_uuid)
                i["sendor_secret_key"] = str(check_sendor_secret_key)
                if check_sendor_id == i["sender_user_id"]:
                    i["is_sendor"] = True
                else:
                    i["is_sendor"] = False

            
            sender_messages = MessageBox.objects.filter(room=self.get_room, sender_user=check_sender.first())
            first_time_status = False
            if not sender_messages:
                first_time_status = True
                

            self.send(text_data=json.dumps({"message": message,"get_datetime":"","online_user":online_user,"messages": serializer.data, "block_status":block_status,"first_time_chat":first_time_status}))
            
    # Receive message from WebSocket
    def receive(self, text_data):
        text_data_json = json.loads(text_data)
        print(text_data_json)
        message = text_data_json["message"]
        if self.get_room.is_blocked_user_one and self.get_room.is_blocked_user_two:
            block_status = True
            if self.get_room.is_blocked_user_one and self.get_room.is_blocked_user_two and self.get_check_sender == self.get_room.user_one:
                message1 = f"You have blocked {self.get_room.user_two.first_name} and even {self.get_room.user_two.first_name} has also blocked you."
            if self.get_room.is_blocked_user_one and self.get_room.is_blocked_user_two and self.get_check_sender == self.get_room.user_two:
                message1 = f"You have blocked {self.get_room.user_one.first_name} and even {self.get_room.user_one.first_name} has also blocked you."
            
            

        elif self.get_room.is_blocked_user_one or self.get_room.is_blocked_user_two:   
            block_status = True             
            if self.get_room.is_blocked_user_one and self.get_check_sender == self.get_room.user_one:
                message1 = f"{self.get_room.user_two.first_name} has blocked you."
            if self.get_room.is_blocked_user_one and self.get_check_sender == self.get_room.user_two:
                message1 = f"You have blocked {self.get_room.user_one.first_name}"
            if self.get_room.is_blocked_user_two and self.get_check_sender == self.get_room.user_one:
                message1 = f"You have blocked {self.get_room.user_two.first_name}."
            if self.get_room.is_blocked_user_two and self.get_check_sender == self.get_room.user_two:
                message1 = f"{self.get_room.user_one.first_name} has blocked you."
        else:
            block_status = False
        # user_block_status = text_data_json["block_status"]
        online_user = []
        try:
            if text_data_json["online_user"]:
                online_user = text_data_json["online_user"]
        except:
            if cache.get(str(self.sender_email)) :
                online_user.append(str(self.sender_email))
            if cache.get(str(self.get_reciver_user.email)) :
                online_user.append(str(self.get_reciver_user.email))

        get_datetime = ""
        ######## Save message ....................
        check_sender = User.objects.filter(uuid=self.sender_uuid,secret_key=self.sender_secret_key)
        check_room = Room.objects.filter(name=self.room__name)
        if check_sender.exists() and check_room.exists():
            get_room = check_room.first()
            if cache.get(str(self.get_reciver_user.uuid)) :
                self.is_read = True 
            else:
                self.is_read = False
 
            if message != None :
                message_list = message.split(" ")
                new_message = ""
                for ch in message_list:
                    if ch.lower() in bad_words_list:
                        ch = "****"
                    new_message = new_message + " " + ch
                message = new_message

                if get_room.is_blocked_user_one or get_room.is_blocked_user_two:
                    if get_room.is_blocked_user_one:
                        blocking_user = get_room.user_two
                        blocked_user = get_room.user_one
                        messages = MessageBox.objects.filter(room__id=get_room.id, sender_user__id=blocked_user.id, reciver_user__id=blocking_user.id)
                        # messages.delete()
                    if get_room.is_blocked_user_two:
                        blocking_user = get_room.user_one
                        blocked_user = get_room.user_two
                        messages = MessageBox.objects.filter(room__id=get_room.id, sender_user__id=blocked_user.id, reciver_user__id=blocking_user.id)
                        # messages.delete()
                if  message != " " and not block_status:      
                    save_msg = MessageBox.objects.create(room=self.get_room,sender_user=self.get_check_sender,reciver_user=self.get_reciver_user,
                        is_read=self.is_read,text_message=message)
                
                    # Given datetime string
                    input_date_str = str(save_msg.created_at)
                    # Convert string to datetime object
                    input_datetime = timezone.datetime.strptime(input_date_str, "%Y-%m-%d %H:%M:%S.%f%z")
                    # Format the datetime object
                    formatted_date_time = input_datetime.strftime("%d %B, %I:%M %p")
                    get_datetime = str(formatted_date_time)
                else:
                    pass
        #...........  Save message ....................
        # Send message to room group
        all_messages = MessageBox.objects.filter(room=self.get_room)
        filtered_messages = all_messages.filter(Q(text_message__isnull=False) & ~Q(text_message=" "))
        serializer = MessageBoxSerializer(filtered_messages, many=True) 
        for i in serializer.data:
            get_user = User.objects.filter(uuid=self.sender_uuid,secret_key=self.sender_secret_key).first()
            check_sendor_id = get_user.id
            check_sendor_uuid = str(get_user.uuid)
            check_sendor_secret_key = str(get_user.secret_key)
            i["sendor_uuid"] = str(check_sendor_uuid)
            i["sendor_secret_key"] = str(check_sendor_secret_key)
            if check_sendor_id == i["sender_user_id"]:
                i["is_sendor"] = True
            else:
                i["is_sendor"] = False
        

        sender_messages = MessageBox.objects.filter(room=self.get_room, sender_user=check_sender.first())
        first_time_status = False
        if not sender_messages:
            first_time_status = True
        if block_status:
            message = message1
        async_to_sync(self.channel_layer.group_send)(
            self.room_group_name, {"type": "chat_message", "message": message,"get_datetime":get_datetime,"online_user":online_user,"messages": serializer.data, "first_time_chat":first_time_status, "block_status":block_status}
        )
        
    # Receive message from room group
    def chat_message(self, event):
        message = event["message"]
        get_datetime = event["get_datetime"]
        online_user = event["online_user"]
        # Send message to WebSocket
        all_messages = MessageBox.objects.filter(room=self.get_room)
        filtered_messages = all_messages.filter(Q(text_message__isnull=False) & ~Q(text_message=" "))
        serializer = MessageBoxSerializer(filtered_messages, many=True) 
        for i in serializer.data:
            get_user = User.objects.filter(uuid=self.sender_uuid,secret_key=self.sender_secret_key).first()
            check_sendor_id = get_user.id
            check_sendor_uuid = str(get_user.uuid)
            check_sendor_secret_key = str(get_user.secret_key)
            i["sendor_uuid"] = str(check_sendor_uuid)
            i["sendor_secret_key"] = str(check_sendor_secret_key)
            if check_sendor_id == i["sender_user_id"]:
                i["is_sendor"] = True
            else:
                i["is_sendor"] = False

        if self.get_room.is_blocked_user_one and self.get_room.is_blocked_user_two:
            block_status = True
            if self.get_room.is_blocked_user_one and self.get_room.is_blocked_user_two and self.get_check_sender == self.get_room.user_one:
                message1 = f"You have blocked {self.get_room.user_two.first_name} and even {self.get_room.user_two.first_name} has also blocked you."
            if self.get_room.is_blocked_user_one and self.get_room.is_blocked_user_two and self.get_check_sender == self.get_room.user_two:
                message1 = f"You have blocked {self.get_room.user_one.first_name} and even {self.get_room.user_one.first_name} has also blocked you."
            
            

        elif self.get_room.is_blocked_user_one or self.get_room.is_blocked_user_two:   
            block_status = True             
            if self.get_room.is_blocked_user_one and self.get_check_sender == self.get_room.user_one:
                message1 = f"{self.get_room.user_two.first_name} has blocked you."
            if self.get_room.is_blocked_user_one and self.get_check_sender == self.get_room.user_two:
                message1 = f"You have blocked {self.get_room.user_one.first_name}"
            if self.get_room.is_blocked_user_two and self.get_check_sender == self.get_room.user_one:
                message1 = f"You have blocked {self.get_room.user_two.first_name}."
            if self.get_room.is_blocked_user_two and self.get_check_sender == self.get_room.user_two:
                message1 = f"{self.get_room.user_one.first_name} has blocked you."
        else:
            block_status = False
        
        sender_messages = MessageBox.objects.filter(room=self.get_room, sender_user=self.get_check_sender)
        first_time_status = False
        if not sender_messages:
            first_time_status = True
        if block_status:
            message = message1
        self.send(text_data=json.dumps({"message": message,"get_datetime":get_datetime,"online_user":online_user,"messages": serializer.data,  "block_status":block_status, "first_time_chat":first_time_status}))

    def disconnect(self, close_code):
        all_cache_data = cache.keys('*')  # Get all keys in the cache
        cache_data = {key: cache.get(key) for key in all_cache_data}  # Retrieve data for each key
        cache.delete(str(self.sender_uuid))
        cache.delete(str(self.sender_email))
        online_user = []
        if cache.get(str(self.sender_email)) :
            online_user.append(str(self.sender_email))
        if cache.get(str(self.get_reciver_user.email)) :
            online_user.append(str(self.get_reciver_user.email))
            
        self.receive(text_data=json.dumps({"message": "","get_datetime":"","online_user":online_user}))
        # Leave room group
        async_to_sync(self.channel_layer.group_discard)(
            self.room_group_name, self.channel_name
        )
 
class NotificationConsumer(WebsocketConsumer):
    def connect(self):
        self.room_name = self.scope["url_route"]["kwargs"]["room_name"]
        self.room_group_name = f"notifications_{self.room_name}"

        # Join room group
        async_to_sync(self.channel_layer.group_add)(
            self.room_group_name, self.channel_name
        )

        self.accept()

        # Send initial data when connection is established
        self.send_initial_data()

    def send_initial_data(self):
        user = NotifiRoom.objects.filter(name=self.room_name).first().user
        unread_noti_count = NotificationBox.objects.filter(room__name=self.room_name, notify_for=user, is_read=False).count()
        notifications = NotificationBox.objects.filter(room__name=self.room_name).order_by("-id")
        # You might want to paginate or limit the number of notifications sent initially
        notification_data = NotificationBoxSerializer(notifications, many=True)  # Convert queryset to list for JSON serialization
        self.send(text_data=json.dumps({
            "message": "Get Notification",
            "notification":"",
            "all_notifications": notification_data.data,
            "unread_noti_count": unread_noti_count
        }))

    def receive(self, text_data):
        # Process incoming message from WebSocket client
        text_data_json = json.loads(text_data)
        message = text_data_json['message']

        # You can handle different types of messages here based on your application's requirements
        if message == "new_message":
            # Handle new message received from client
            self.handle_new_message(text_data_json)
        else:
            # Handle other types of messages
            pass


    def send_notification(self, event):
        notification = event["notification"]
        # Send notification to WebSocket client
        user = NotifiRoom.objects.filter(name=self.room_name).first().user
        unread_noti_count = NotificationBox.objects.filter(room__name=self.room_name, notify_for=user, is_read=False).count()
        notifications = NotificationBox.objects.filter(room__name=self.room_name).order_by("-id")
        # You might want to paginate or limit the number of notifications sent initially
        notification_data = NotificationBoxSerializer(notifications, many=True)
        self.send(text_data=json.dumps({
            "message": "Get Notification",
            "notification": notification,
            "all_notifications": notification_data.data,
            "unread_noti_count": unread_noti_count
        }))


    def disconnect(self, close_code):
        # Leave room group
        async_to_sync(self.channel_layer.group_discard)(
            self.room_group_name, self.channel_name
        )



#### new update

def find_room(user1, user2):
    """
    Find the chat room between two users.
    Ensures that the room is returned regardless of user order.
    """
    # Ensure user1 is always the first user and user2 is the second user
    if user1.id > user2.id:
        user1, user2 = user2, user1

    # Find the room where user1 and user2 are in the same room
    room = Room.objects.filter(
        Q(user1=user1, user2=user2) | Q(user1=user2, user2=user1)
    ).first()

    return room

def get_chat_history(room, user):
    try:  
        messages = MessageBox.objects.filter(room=room).order_by("created_at")  # Oldest first

        chat_history = []
        for msg in messages:
            chat_history.append({
                "id": msg.id,
                "msg": msg.text_message if msg.text_message else None,
                "is_read": msg.is_read,
                "created_at": localtime(msg.created_at).strftime('%Y-%m-%d %H:%M:%S') if msg.created_at else None,
                "position": "right" if msg.sender_user == user else "left"  
            })

        return chat_history
    except Room.DoesNotExist:
        return []

def get_block_status(room, user):
    try:
        if room.user_one == user:
            return room.is_blocked_user_one, room.is_blocked_user_two
        else:
            return room.is_blocked_user_two, room.is_blocked_user_one
    except:
        return False, False

def get_room_details(room, user):
        if room.user_one == user:
            return room.user_one, room.user_two
        else:
            return room.user_two, room.user_one

def get_chat_users_with_last_message(user):
    rooms = Room.objects.filter(
        Q(user_one=user, is_blocked_user_one=False) |
        Q(user_two=user, is_blocked_user_two=False)
    )

    
    # Fetch all online users from Redis in a single call
    online_users = cache.get("online_users", set())
    
    chat_data = []

    for room in rooms:
        other_user = room.user_two if room.user_one == user else room.user_one
        last_message = MessageBox.objects.filter(room=room).order_by('-created_at').first()
        unread_count = MessageBox.objects.filter(room=room, reciver_user=user, is_read=False).count()
        if last_message:
            chat_data.append({
                "user_id": other_user.id,  # This should refer to the User instance
                "uuid": str(other_user.uuid),  # Ensure UUID is included
                "secret_key": str(other_user.secret_key),
                "email": str(other_user.email),
                "first_name": other_user.first_name,
                "last_name": other_user.last_name,
                "room": room.name,
                "image": other_user.image.url if other_user.image else None,
                "last_message": last_message.text_message if last_message.text_message else "File/Image",
                "is_read": last_message.is_read,
                "unread_count": unread_count,
                "created_at": localtime(last_message.created_at).strftime('%Y-%m-%d %H:%M:%S') if last_message.created_at else None,
                "online": str(other_user.uuid) in online_users  # O(1) lookup
            })

    # Sort by latest message timestamp (Descending order)
    chat_data.sort(key=lambda x: x["created_at"], reverse=True)

    return chat_data

class ChatHistory(WebsocketConsumer):
    def connect(self):
        query_string = self.scope["query_string"].decode("utf-8")
        query_params = parse_qs(query_string)
        self.uuid = query_params.get("uuid", [None])[0]
        self.room_group_name = f"chat_user_{self.uuid}"

        if self.uuid:
            async_to_sync(self.channel_layer.group_add)(self.room_group_name, self.channel_name)
            self.accept()
            self.mark_user_online(self.uuid)
            self.update_user_list()

    def disconnect(self, close_code):
        if self.uuid:
            self.mark_user_offline(self.uuid)
            async_to_sync(self.channel_layer.group_discard)(self.room_group_name, self.channel_name)

    def update_user_list(self):
        """Update and send the list of users, ordered by recent chat time."""
        self.receive_user = User.objects.filter(uuid=self.uuid).first()
        if self.receive_user:
            chat_users = get_chat_users_with_last_message(self.receive_user)
            # print(self.receive_user, [user["first_name"]+user["last_name"] for user in chat_users])
            async_to_sync(self.channel_layer.group_send)(
                self.room_group_name,
                {"type": "send_update", "data": json.dumps(chat_users)}
            )

    def send_update(self, event):
        """Send updated user list to all connected WebSocket clients."""
        self.send(text_data=event["data"])

    def update_user_list_chat_user(self):
        """Update chat users for all connected clients."""
        self.receive_user = User.objects.filter(uuid=self.uuid).first()
        if self.receive_user:
            chat_users = get_chat_users_with_last_message(self.receive_user)
            for user in chat_users:
                user_int = User.objects.filter(uuid=user["uuid"]).first()
                chat_user_update = get_chat_users_with_last_message(user_int)
                async_to_sync(self.channel_layer.group_send)(
                    f"chat_user_{user_int.uuid}",
                    {"type": "send_update", "data": json.dumps(chat_user_update)}
                )
        

    def mark_user_online(self, uuid):
        """Store the user in Redis as online."""
        redis_key = "online_users"
        online_users = cache.get(redis_key, set())
        online_users.add(uuid)
        cache.set(redis_key, online_users, timeout=None)  # Persist the set
        self.update_user_list_chat_user()

    def mark_user_offline(self, uuid):
        """Remove the user from Redis when they disconnect."""
        redis_key = "online_users"
        online_users = cache.get(redis_key, set())
        if uuid in online_users:
            online_users.discard(uuid)
            cache.set(redis_key, online_users, timeout=None)  # Persist the set
            self.update_user_list_chat_user()

    def get_online_users(self):
        """Fetch all online users from Redis."""
        return cache.get("online_users", set())

class ChatUser(WebsocketConsumer):
    
    def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f"chat_{self.room_name}"

        query_string = self.scope["query_string"].decode("utf-8")
        query_params = parse_qs(query_string)
        self.uuid = query_params.get("uuid", [None])[0]

        self.room_group_name = f"room_{self.room_name}"

        if self.uuid and self.room_name:
            self.room = Room.objects.filter(name=self.room_name).first()
            self.user = User.objects.filter(uuid=self.uuid).first()

            if self.user:
                async_to_sync(self.channel_layer.group_add)(
                    self.room_group_name, self.channel_name
                )
                self.accept()
                self.user_chat_history()

    def disconnect(self, close_code):
        """Remove user from group on disconnect"""
        async_to_sync(self.channel_layer.group_discard)(
            self.room_group_name, self.channel_name
        )

    def receive(self, text_data):
        """Handle messages from WebSocket"""
        data = json.loads(text_data)
        message = data.get("message", "").strip()
        sender, reciver = get_room_details(self.room, self.user)
        
        # Save message to the database
        chat_message = MessageBox.objects.create(
            room=self.room,
            sender_user=sender,
            reciver_user=reciver,
            text_message=message
        )
        # print("chat_message", chat_message)
        # Broadcast the message to the chat group
        async_to_sync(self.channel_layer.group_send)(
            self.room_group_name,
            {
                "type": "chat_message",
                "message": message,
                "sender": sender.first_name,
                "receiver": reciver.first_name,
                "timestamp": chat_message.created_at.strftime("%Y-%m-%d %H:%M:%S")
            },
        )

    def chat_message(self, event):
        """Send message to WebSocket"""
        self.send(text_data=json.dumps({
            "message": event["message"]
        }))

    def user_chat_history(self, event=None):
        chat_history = get_chat_history(self.room, self.user)
        is_blocked, other_blocked = get_block_status(self.room, self.user)
        self.send(text_data=json.dumps({"chat": chat_history, "is_blocked":is_blocked, "other_blocked":other_blocked}))
                  

  