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
from datetime import datetime
from apps.chat.views import *
from django.db.models import Q

def get_bad_words_list():
    with open('list_of_bad_words.txt', 'r') as file:
        bad_words = file.read().splitlines()
    return bad_words 

bad_words_list = get_bad_words_list()

# class ChatConsumer(WebsocketConsumer):
#     def connect(self):
#         self.room_name = self.scope["url_route"]["kwargs"]["room_name"]
#         self.room_group_name = "chat_%s" % self.room_name
        
#         # Extracting query string from the scope
#         query_string = self.scope["query_string"].decode("utf-8")
#         # Parsing query string into a dictionary
#         query_params = parse_qs(query_string)
#         # Retrieving sender_uuid and sender_secret_key from the parsed query parameters
#         self.sender_uuid = query_params.get('sender_uuid', [''])[0]
#         self.sender_secret_key = query_params.get('sender_secret_key', [''])[0]
#         self.sender_email = query_params.get('sender_email', [''])[0]
#         self.room__name = self.room_name
#         # set reciver
#         check_sender = User.objects.filter(uuid=self.sender_uuid, secret_key=self.sender_secret_key)
#         check_room = Room.objects.filter(name=self.room_name)
#         print(check_sender)
#         print(check_room)
#         if check_sender.exists() and check_room.exists():
#             self.get_sender = check_sender.first()
#             self.get_room = check_room.first()
#             u1 = self.get_room.user_one
#             u2 = self.get_room.user_two
#             print("checkkjdnksjdnk----",u1,u2)
            
#             if self.get_sender == u1 :
#                 self.get_reciver_user = u2
#             else:
#                 self.get_reciver_user = u1

#         # making cache for online user
#         cache.set(str(self.sender_uuid),str(self.sender_secret_key))
#         cache.set(str(self.sender_email),True)
                    
#         # Join room group
#         async_to_sync(self.channel_layer.group_add)(
#             self.room_group_name, self.channel_name
#         )

#         self.accept()
#         # when socket connecting frist checking that user data and updating as seen ...
#         self.send_initial_data()
        
#     def send_initial_data(self):
#         all_messages = MessageBox.objects.filter(room=self.get_room)
#         check_sender = User.objects.filter(uuid=self.sender_uuid, secret_key=self.sender_secret_key)
#         check_room = Room.objects.filter(name=self.room_name)
#         if check_sender.exists() and check_room.exists():
#             self.get_sender = check_sender.first()
#             self.get_room = check_room.first()          
#             u1 = self.get_room.user_one
#             u2 = self.get_room.user_two
#             if self.get_sender == u1 :
#                 self.get_reciver_user = u2
#             else:
#                 self.get_reciver_user = u1
#             all_msg = MessageBox.objects.filter(room=self.get_room, reciver_user=self.get_sender, is_read=False)
#             online_user = []

#             if cache.get(str(self.sender_email)) :
#                 online_user.append(str(self.sender_email))
#             if cache.get(str(self.get_reciver_user.email)) :
#                 online_user.append(str(self.get_reciver_user.email))

#             if self.get_room.is_blocked_user_one and self.get_room.is_blocked_user_two:
#                 if self.get_room.is_blocked_user_one and self.get_room.is_blocked_user_two and self.get_sender == self.get_room.user_one:
#                     message = f"You have blocked {self.get_room.user_two.first_name} and even {self.get_room.user_two.first_name} has also blocked you."
#                 if self.get_room.is_blocked_user_one and self.get_room.is_blocked_user_two and self.get_sender == self.get_room.user_two:
#                     message = f"You have blocked {self.get_room.user_one.first_name} and even {self.get_room.user_one.first_name} has also blocked you."
                

#             elif self.get_room.is_blocked_user_one or self.get_room.is_blocked_user_two:                
#                 if self.get_room.is_blocked_user_one and self.get_sender == self.get_room.user_one:
#                     message = f"{self.get_room.user_two.first_name} has blocked you."
#                 if self.get_room.is_blocked_user_one and self.get_sender == self.get_room.user_two:
#                     message = f"You have blocked {self.get_room.user_one.first_name}"
#                 if self.get_room.is_blocked_user_two and self.get_sender == self.get_room.user_one:
#                     message = f"You have blocked {self.get_room.user_two.first_name}."
#                 if self.get_room.is_blocked_user_two and self.get_sender == self.get_room.user_two:
#                     message = f"{self.get_room.user_one.first_name} has blocked you."
#             else:
#                 message = None
            
            
#             self.receive(text_data=json.dumps({"message": message,"get_datetime":"","online_user":online_user}))
            
#             for i in all_msg :
#                 self.send(text_data=json.dumps({"message": i.text_message,"get_datetime":str(i.created_at),"online_user":online_user}))
#                 all_msg.filter(id=i.id).update(is_read=True)
#             serializer = MessageBoxSerializer(all_messages, many=True)   
#             for i in serializer.data:
#                 get_user = User.objects.filter(uuid=self.sender_uuid,secret_key=self.sender_secret_key).first()
#                 check_sendor_id = get_user.id
#                 check_sendor_uuid = str(get_user.uuid)
#                 check_sendor_secret_key = str(get_user.secret_key)
#                 i["sendor_uuid"] = str(check_sendor_uuid)
#                 i["sendor_secret_key"] = str(check_sendor_secret_key)
#                 if check_sendor_id == i["sender_user_id"]:
#                     i["is_sendor"] = True
#                 else:
#                     i["is_sendor"] = False

            
#             sender_messages = MessageBox.objects.filter(room=self.get_room, sender_user=check_sender.first())
#             first_time_status = False
#             if not sender_messages:
#                 first_time_status = True
                

#             self.send(text_data=json.dumps({"message": message,"get_datetime":"","online_user":online_user,"messages": serializer.data, "first_time_chat":first_time_status}))
            
#     # Receive message from WebSocket
#     def receive(self, text_data):
#         text_data_json = json.loads(text_data)
#         message = text_data_json["message"]
#         online_user = []
#         # all_cache_data = cache.keys('*')  # Get all keys in the cache
#         # cache_data = {key: cache.get(key) for key in all_cache_data}  # Retrieve data for each key
#         # print("All Cache Data:")
#         # print(cache_data)
#         try:
#             if text_data_json["online_user"]:
#                 online_user = text_data_json["online_user"]
#         except:
#             if cache.get(str(self.sender_email)) :
#                 online_user.append(str(self.sender_email))
#             if cache.get(str(self.get_reciver_user.email)) :
#                 online_user.append(str(self.get_reciver_user.email))

#         get_datetime = ""
#         ######## Save message ....................
#         check_sender = User.objects.filter(uuid=self.sender_uuid,secret_key=self.sender_secret_key)
#         check_room = Room.objects.filter(name=self.room__name)
#         if check_sender.exists() and check_room.exists():
#             get_room = check_room.first()
#             if cache.get(str(self.get_reciver_user.uuid)) :
#                 self.is_read = True 
#             else:
#                 self.is_read = False
 
#             if message != None :
#                 message_list = message.split(" ")
#                 new_message = ""
#                 for ch in message_list:
#                     if ch.lower() in bad_words_list:
#                         ch = "****"
#                     new_message = new_message + " " + ch
#                 message = new_message

#                 if get_room.is_blocked_user_one or get_room.is_blocked_user_two:
#                     if get_room.is_blocked_user_one:
#                         blocking_user = get_room.user_two
#                         blocked_user = get_room.user_one
#                         messages = MessageBox.objects.filter(room__id=get_room.id, sender_user__id=blocked_user.id, reciver_user__id=blocking_user.id)
#                         # messages.delete()
#                     if get_room.is_blocked_user_two:
#                         blocking_user = get_room.user_one
#                         blocked_user = get_room.user_two
#                         messages = MessageBox.objects.filter(room__id=get_room.id, sender_user__id=blocked_user.id, reciver_user__id=blocking_user.id)
#                         # messages.delete()
#                     return
#                 save_msg = MessageBox.objects.create(room=self.get_room,sender_user=self.get_sender,reciver_user=self.get_reciver_user,
#                         is_read=self.is_read,text_message=message)
                
#                 # Given datetime string
#                 input_date_str = str(save_msg.created_at)
#                 # Convert string to datetime object
#                 input_datetime = timezone.datetime.strptime(input_date_str, "%Y-%m-%d %H:%M:%S.%f%z")
#                 # Format the datetime object
#                 formatted_date_time = input_datetime.strftime("%d %B, %I:%M %p")
#                 get_datetime = str(formatted_date_time)
#         #...........  Save message ....................
#         # Send message to room group
#         all_messages = MessageBox.objects.filter(room=self.get_room)
#         serializer = MessageBoxSerializer(all_messages, many=True)
#         for i in serializer.data:
#             get_user = User.objects.filter(uuid=self.sender_uuid,secret_key=self.sender_secret_key).first()
#             check_sendor_id = get_user.id
#             check_sendor_uuid = str(get_user.uuid)
#             check_sendor_secret_key = str(get_user.secret_key)
#             i["sendor_uuid"] = str(check_sendor_uuid)
#             i["sendor_secret_key"] = str(check_sendor_secret_key)
#             if check_sendor_id == i["sender_user_id"]:
#                 i["is_sendor"] = True
#             else:
#                 i["is_sendor"] = False
#         async_to_sync(self.channel_layer.group_send)(
#             self.room_group_name, {"type": "chat_message", "message": message,"get_datetime":get_datetime,"online_user":online_user,"messages": serializer.data}
#         )
        
#     # Receive message from room group
#     def chat_message(self, event):
#         message = event["message"]
#         get_datetime = event["get_datetime"]
#         online_user = event["online_user"]
#         # Send message to WebSocket
#         all_messages = MessageBox.objects.filter(room=self.get_room)
#         serializer = MessageBoxSerializer(all_messages, many=True)
#         for i in serializer.data:
#             get_user = User.objects.filter(uuid=self.sender_uuid,secret_key=self.sender_secret_key).first()
#             check_sendor_id = get_user.id
#             check_sendor_uuid = str(get_user.uuid)
#             check_sendor_secret_key = str(get_user.secret_key)
#             i["sendor_uuid"] = str(check_sendor_uuid)
#             i["sendor_secret_key"] = str(check_sendor_secret_key)
#             if check_sendor_id == i["sender_user_id"]:
#                 i["is_sendor"] = True
#             else:
#                 i["is_sendor"] = False
#         self.send(text_data=json.dumps({"message": message,"get_datetime":get_datetime,"online_user":online_user,"messages": serializer.data}))

#     def disconnect(self, close_code):
#         all_cache_data = cache.keys('*')  # Get all keys in the cache
#         cache_data = {key: cache.get(key) for key in all_cache_data}  # Retrieve data for each key
#         cache.delete(str(self.sender_uuid))
#         cache.delete(str(self.sender_email))
#         online_user = []
#         if cache.get(str(self.sender_email)) :
#             online_user.append(str(self.sender_email))
#         if cache.get(str(self.get_reciver_user.email)) :
#             online_user.append(str(self.get_reciver_user.email))
            
#         self.receive(text_data=json.dumps({"message": "","get_datetime":"","online_user":online_user}))
#         # Leave room group
#         async_to_sync(self.channel_layer.group_discard)(
#             self.room_group_name, self.channel_name
#         )


# class ChatConsumer(WebsocketConsumer):
#     def connect(self):
#         self.room_name = self.scope["url_route"]["kwargs"]["room_name"]
#         self.room_group_name = "chat_%s" % self.room_name
        
#         # Extracting query string from the scope
#         query_string = self.scope["query_string"].decode("utf-8")
#         # Parsing query string into a dictionary
#         query_params = parse_qs(query_string)
#         # Retrieving sender_uuid and sender_secret_key from the parsed query parameters
#         self.sender_uuid = query_params.get('sender_uuid', [''])[0]
#         self.sender_secret_key = query_params.get('sender_secret_key', [''])[0]
#         self.sender_email = query_params.get('sender_email', [''])[0]
#         self.room__name = self.room_name
#         # set reciver
#         check_sender = User.objects.filter(uuid=self.sender_uuid, secret_key=self.sender_secret_key)
#         check_room = Room.objects.filter(name=self.room_name).filter(Q(user_one=check_sender.first()) | Q(user_two=check_sender.first()))
#         print(check_sender)
#         print(check_room)
#         if check_sender.exists() and check_room.exists():
#             self.get_sender = check_sender.first()
#             self.get_room = check_room.first()
#             u1 = self.get_room.user_one
#             u2 = self.get_room.user_two
#             print("checkkjdnksjdnk----",u1,u2)
            
#             if self.get_sender == u1 :
#                 self.get_reciver_user = u2
#             else:
#                 self.get_reciver_user = u1
        
#         # making cache for online user
#         cache.set(str(self.sender_uuid),str(self.sender_secret_key))
#         cache.set(str(self.sender_email),True)
                    
#         # Join room group
#         async_to_sync(self.channel_layer.group_add)(
#             self.room_group_name, self.channel_name
#         )

#         self.accept()
#         # when socket connecting frist checking that user data and updating as seen ...
#         self.send_initial_data()
        
#     def send_initial_data(self):
#         all_messages = MessageBox.objects.filter(room=self.get_room)
#         check_sender = User.objects.filter(uuid=self.sender_uuid, secret_key=self.sender_secret_key)
#         check_room = Room.objects.filter(name=self.room_name)
#         if check_sender.exists() and check_room.exists():
#             self.get_sender = check_sender.first()
#             self.get_room = check_room.first()          
#             u1 = self.get_room.user_one
#             u2 = self.get_room.user_two
#             if self.get_sender == u1 :
#                 self.get_reciver_user = u2
#             else:
#                 self.get_reciver_user = u1
#             all_msg = MessageBox.objects.filter(room=self.get_room, reciver_user=self.get_sender, is_read=False)
#             online_user = []
#             block_status = False

#             if cache.get(str(self.sender_email)) :
#                 online_user.append(str(self.sender_email))
#             if cache.get(str(self.get_reciver_user.email)) :
#                 online_user.append(str(self.get_reciver_user.email))

#             if self.get_room.is_blocked_user_one and self.get_room.is_blocked_user_two:
#                 block_status = True
#                 if self.get_room.is_blocked_user_one and self.get_room.is_blocked_user_two and self.get_sender == self.get_room.user_one:
#                     message = f"You have blocked {self.get_room.user_two.first_name} and even {self.get_room.user_two.first_name} has also blocked you."
#                 if self.get_room.is_blocked_user_one and self.get_room.is_blocked_user_two and self.get_sender == self.get_room.user_two:
#                     message = f"You have blocked {self.get_room.user_one.first_name} and even {self.get_room.user_one.first_name} has also blocked you."
                
                

#             elif self.get_room.is_blocked_user_one or self.get_room.is_blocked_user_two:   
#                 block_status = True             
#                 if self.get_room.is_blocked_user_one and self.get_sender == self.get_room.user_one:
#                     message = f"{self.get_room.user_two.first_name} has blocked you."
#                 if self.get_room.is_blocked_user_one and self.get_sender == self.get_room.user_two:
#                     message = f"You have blocked {self.get_room.user_one.first_name}"
#                 if self.get_room.is_blocked_user_two and self.get_sender == self.get_room.user_one:
#                     message = f"You have blocked {self.get_room.user_two.first_name}."
#                 if self.get_room.is_blocked_user_two and self.get_sender == self.get_room.user_two:
#                     message = f"{self.get_room.user_one.first_name} has blocked you."
#             else:
#                 block_status = False
#                 message = None
            
#             sender_messages = MessageBox.objects.filter(room=self.get_room, sender_user=check_sender.first())
#             first_time_status = False
#             if not sender_messages:
#                 first_time_status = True
#             self.receive(text_data=json.dumps({"message": message,"get_datetime":"","online_user":online_user, "block_status":block_status, "first_time_chat":first_time_status}))
            
#             for i in all_msg :
#                 self.send(text_data=json.dumps({"message": i.text_message,"get_datetime":str(i.created_at),"online_user":online_user, "block_status":block_status, "first_time_chat":first_time_status}))
#                 all_msg.filter(id=i.id).update(is_read=True)
#             filtered_messages = all_messages.filter(Q(text_message__isnull=False) & ~Q(text_message=" "))
#             serializer = MessageBoxSerializer(filtered_messages, many=True)   
#             for i in serializer.data:
#                 get_user = User.objects.filter(uuid=self.sender_uuid,secret_key=self.sender_secret_key).first()
#                 check_sendor_id = get_user.id
#                 check_sendor_uuid = str(get_user.uuid)
#                 check_sendor_secret_key = str(get_user.secret_key)
#                 i["sendor_uuid"] = str(check_sendor_uuid)
#                 i["sendor_secret_key"] = str(check_sendor_secret_key)
#                 if check_sendor_id == i["sender_user_id"]:
#                     i["is_sendor"] = True
#                 else:
#                     i["is_sendor"] = False

            
#             sender_messages = MessageBox.objects.filter(room=self.get_room, sender_user=check_sender.first())
#             first_time_status = False
#             if not sender_messages:
#                 first_time_status = True
                

#             self.send(text_data=json.dumps({"message": message,"get_datetime":"","online_user":online_user,"messages": serializer.data, "block_status":block_status,"first_time_chat":first_time_status}))
            
#     # Receive message from WebSocket
#     def receive(self, text_data):
#         text_data_json = json.loads(text_data)
#         print(text_data_json)
#         message = text_data_json["message"]
#         if self.get_room.is_blocked_user_one and self.get_room.is_blocked_user_two:
#             block_status = True
#             if self.get_room.is_blocked_user_one and self.get_room.is_blocked_user_two and self.get_sender == self.get_room.user_one:
#                 message1 = f"You have blocked {self.get_room.user_two.first_name} and even {self.get_room.user_two.first_name} has also blocked you."
#             if self.get_room.is_blocked_user_one and self.get_room.is_blocked_user_two and self.get_sender == self.get_room.user_two:
#                 message1 = f"You have blocked {self.get_room.user_one.first_name} and even {self.get_room.user_one.first_name} has also blocked you."
            
            

#         elif self.get_room.is_blocked_user_one or self.get_room.is_blocked_user_two:   
#             block_status = True             
#             if self.get_room.is_blocked_user_one and self.get_sender == self.get_room.user_one:
#                 message1 = f"{self.get_room.user_two.first_name} has blocked you."
#             if self.get_room.is_blocked_user_one and self.get_sender == self.get_room.user_two:
#                 message1 = f"You have blocked {self.get_room.user_one.first_name}"
#             if self.get_room.is_blocked_user_two and self.get_sender == self.get_room.user_one:
#                 message1 = f"You have blocked {self.get_room.user_two.first_name}."
#             if self.get_room.is_blocked_user_two and self.get_sender == self.get_room.user_two:
#                 message1 = f"{self.get_room.user_one.first_name} has blocked you."
#         else:
#             block_status = False
#         # user_block_status = text_data_json["block_status"]
#         online_user = []
#         try:
#             if text_data_json["online_user"]:
#                 online_user = text_data_json["online_user"]
#         except:
#             if cache.get(str(self.sender_email)) :
#                 online_user.append(str(self.sender_email))
#             if cache.get(str(self.get_reciver_user.email)) :
#                 online_user.append(str(self.get_reciver_user.email))

#         get_datetime = ""
#         ######## Save message ....................
#         check_sender = User.objects.filter(uuid=self.sender_uuid,secret_key=self.sender_secret_key)
#         check_room = Room.objects.filter(name=self.room__name)
#         if check_sender.exists() and check_room.exists():
#             get_room = check_room.first()
#             if cache.get(str(self.get_reciver_user.uuid)) :
#                 self.is_read = True 
#             else:
#                 self.is_read = False
 
#             if message != None :
#                 message_list = message.split(" ")
#                 new_message = ""
#                 for ch in message_list:
#                     if ch.lower() in bad_words_list:
#                         ch = "****"
#                     new_message = new_message + " " + ch
#                 message = new_message

#                 if get_room.is_blocked_user_one or get_room.is_blocked_user_two:
#                     if get_room.is_blocked_user_one:
#                         blocking_user = get_room.user_two
#                         blocked_user = get_room.user_one
#                         messages = MessageBox.objects.filter(room__id=get_room.id, sender_user__id=blocked_user.id, reciver_user__id=blocking_user.id)
#                         # messages.delete()
#                     if get_room.is_blocked_user_two:
#                         blocking_user = get_room.user_one
#                         blocked_user = get_room.user_two
#                         messages = MessageBox.objects.filter(room__id=get_room.id, sender_user__id=blocked_user.id, reciver_user__id=blocking_user.id)
#                         # messages.delete()
#                 if  message != " " and not block_status:      
#                     save_msg = MessageBox.objects.create(room=self.get_room,sender_user=self.get_sender,reciver_user=self.get_reciver_user,
#                         is_read=self.is_read,text_message=message)
                
#                     # Given datetime string
#                     input_date_str = str(save_msg.created_at)
#                     # Convert string to datetime object
#                     input_datetime = timezone.datetime.strptime(input_date_str, "%Y-%m-%d %H:%M:%S.%f%z")
#                     # Format the datetime object
#                     formatted_date_time = input_datetime.strftime("%d %B, %I:%M %p")
#                     get_datetime = str(formatted_date_time)
#                 else:
#                     pass
#         #...........  Save message ....................
#         # Send message to room group
#         all_messages = MessageBox.objects.filter(room=self.get_room)
#         filtered_messages = all_messages.filter(Q(text_message__isnull=False) & ~Q(text_message=" "))
#         serializer = MessageBoxSerializer(filtered_messages, many=True) 
#         for i in serializer.data:
#             get_user = User.objects.filter(uuid=self.sender_uuid,secret_key=self.sender_secret_key).first()
#             check_sendor_id = get_user.id
#             check_sendor_uuid = str(get_user.uuid)
#             check_sendor_secret_key = str(get_user.secret_key)
#             i["sendor_uuid"] = str(check_sendor_uuid)
#             i["sendor_secret_key"] = str(check_sendor_secret_key)
#             if check_sendor_id == i["sender_user_id"]:
#                 i["is_sendor"] = True
#             else:
#                 i["is_sendor"] = False
        

#         sender_messages = MessageBox.objects.filter(room=self.get_room, sender_user=check_sender.first())
#         first_time_status = False
#         if not sender_messages:
#             first_time_status = True
#         if block_status:
#             message = message1
#         async_to_sync(self.channel_layer.group_send)(
#             self.room_group_name, {"type": "chat_message", "message": message,"get_datetime":get_datetime,"online_user":online_user,"messages": serializer.data, "first_time_chat":first_time_status, "block_status":block_status}
#         )
        
#     # Receive message from room group
#     def chat_message(self, event):
#         message = event["message"]
#         get_datetime = event["get_datetime"]
#         online_user = event["online_user"]
#         # Send message to WebSocket
#         all_messages = MessageBox.objects.filter(room=self.get_room)
#         filtered_messages = all_messages.filter(Q(text_message__isnull=False) & ~Q(text_message=" "))
#         serializer = MessageBoxSerializer(filtered_messages, many=True) 
#         for i in serializer.data:
#             get_user = User.objects.filter(uuid=self.sender_uuid,secret_key=self.sender_secret_key).first()
#             check_sendor_id = get_user.id
#             check_sendor_uuid = str(get_user.uuid)
#             check_sendor_secret_key = str(get_user.secret_key)
#             i["sendor_uuid"] = str(check_sendor_uuid)
#             i["sendor_secret_key"] = str(check_sendor_secret_key)
#             if check_sendor_id == i["sender_user_id"]:
#                 i["is_sendor"] = True
#             else:
#                 i["is_sendor"] = False

#         if self.get_room.is_blocked_user_one and self.get_room.is_blocked_user_two:
#             block_status = True
#             if self.get_room.is_blocked_user_one and self.get_room.is_blocked_user_two and self.get_sender == self.get_room.user_one:
#                 message1 = f"You have blocked {self.get_room.user_two.first_name} and even {self.get_room.user_two.first_name} has also blocked you."
#             if self.get_room.is_blocked_user_one and self.get_room.is_blocked_user_two and self.get_sender == self.get_room.user_two:
#                 message1 = f"You have blocked {self.get_room.user_one.first_name} and even {self.get_room.user_one.first_name} has also blocked you."
            
            

#         elif self.get_room.is_blocked_user_one or self.get_room.is_blocked_user_two:   
#             block_status = True             
#             if self.get_room.is_blocked_user_one and self.get_sender == self.get_room.user_one:
#                 message1 = f"{self.get_room.user_two.first_name} has blocked you."
#             if self.get_room.is_blocked_user_one and self.get_sender == self.get_room.user_two:
#                 message1 = f"You have blocked {self.get_room.user_one.first_name}"
#             if self.get_room.is_blocked_user_two and self.get_sender == self.get_room.user_one:
#                 message1 = f"You have blocked {self.get_room.user_two.first_name}."
#             if self.get_room.is_blocked_user_two and self.get_sender == self.get_room.user_two:
#                 message1 = f"{self.get_room.user_one.first_name} has blocked you."
#         else:
#             block_status = False
        
#         sender_messages = MessageBox.objects.filter(room=self.get_room, sender_user=self.get_sender)
#         first_time_status = False
#         if not sender_messages:
#             first_time_status = True
#         if block_status:
#             message = message1
#         self.send(text_data=json.dumps({"message": message,"get_datetime":get_datetime,"online_user":online_user,"messages": serializer.data,  "block_status":block_status, "first_time_chat":first_time_status}))

#     def disconnect(self, close_code):
#         all_cache_data = cache.keys('*')  # Get all keys in the cache
#         cache_data = {key: cache.get(key) for key in all_cache_data}  # Retrieve data for each key
#         cache.delete(str(self.sender_uuid))
#         cache.delete(str(self.sender_email))
#         online_user = []
#         if cache.get(str(self.sender_email)) :
#             online_user.append(str(self.sender_email))
#         if cache.get(str(self.get_reciver_user.email)) :
#             online_user.append(str(self.get_reciver_user.email))
            
#         self.receive(text_data=json.dumps({"message": "","get_datetime":"","online_user":online_user}))
#         # Leave room group
#         async_to_sync(self.channel_layer.group_discard)(
#             self.room_group_name, self.channel_name
#         )


class ChatConsumer(WebsocketConsumer):
    def connect(self):
        self.room_name = self.scope["url_route"]["kwargs"]["room_name"]
        self.room_group_name = "chat_%s" % self.room_name
        
        query_params = parse_qs(self.scope["query_string"].decode("utf-8"))        
        self.sender_uuid = query_params.get('sender_uuid', [''])[0]
        self.sender_secret_key = query_params.get('sender_secret_key', [''])[0]
        self.sender_email = query_params.get('sender_email', [''])[0]
       
        # set reciver
        check_sender = User.objects.filter(uuid=self.sender_uuid, secret_key=self.sender_secret_key)
        check_room = Room.objects.filter(Q(user_one=check_sender.first()) | Q(user_two=check_sender.first()), name=self.room_name)
        
        self.get_sender = check_sender.first()
        self.get_room = check_room.first()
        
        self.get_reciver_user = self.get_room.user_two if self.get_sender == self.get_room.user_one else self.get_room.user_one
        
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
            self.get_sender = check_sender.first()
            self.get_room = check_room.first()          
            
            self.get_reciver_user = self.get_room.user_two if self.get_sender == self.get_room.user_one else self.get_room.user_one
            all_msg = MessageBox.objects.filter(room=self.get_room, reciver_user=self.get_sender, is_read=False)

            online_users = [
                email for email in [self.get_sender.email, self.get_reciver_user.email] if cache.get(email)
            ]

            first_time_chat = not all_msg.filter(sender_user=self.sender).exists()

            if self.get_room.is_blocked_user_one and self.get_room.is_blocked_user_two:
                block_status = True
                if self.get_room.is_blocked_user_one and self.get_room.is_blocked_user_two and self.get_sender == self.get_room.user_one:
                    message = f"You have blocked {self.get_room.user_two.first_name} and even {self.get_room.user_two.first_name} has also blocked you."
                if self.get_room.is_blocked_user_one and self.get_room.is_blocked_user_two and self.get_sender == self.get_room.user_two:
                    message = f"You have blocked {self.get_room.user_one.first_name} and even {self.get_room.user_one.first_name} has also blocked you."
                
                
            elif self.get_room.is_blocked_user_one or self.get_room.is_blocked_user_two:   
                block_status = True             
                if self.get_room.is_blocked_user_one and self.get_sender == self.get_room.user_one:
                    message = f"{self.get_room.user_two.first_name} has blocked you."
                if self.get_room.is_blocked_user_one and self.get_sender == self.get_room.user_two:
                    message = f"You have blocked {self.get_room.user_one.first_name}"
                if self.get_room.is_blocked_user_two and self.get_sender == self.get_room.user_one:
                    message = f"You have blocked {self.get_room.user_two.first_name}."
                if self.get_room.is_blocked_user_two and self.get_sender == self.get_room.user_two:
                    message = f"{self.get_room.user_one.first_name} has blocked you."
            else:
                block_status = False
                message = None
            
            sender_messages = MessageBox.objects.filter(room=self.get_room, sender_user=check_sender.first())
            first_time_status = False
            if not sender_messages:
                first_time_status = True
            self.receive(text_data=json.dumps({"message": message,"get_datetime":"","online_user":online_users, "block_status":block_status, "first_time_chat":first_time_status}))
            
            for i in all_msg :
                self.send(text_data=json.dumps({"message": i.text_message,"get_datetime":str(i.created_at),"online_user":online_users, "block_status":block_status, "first_time_chat":first_time_status}))
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
                
            self.send(text_data=json.dumps({"message": message,"get_datetime":"","online_user":online_users,"messages": serializer.data, "block_status":block_status,"first_time_chat":first_time_status}))
            
    # Receive message from WebSocket
    def receive(self, text_data):
        text_data_json = json.loads(text_data)
        print(text_data_json)
        message = text_data_json["message"]
        if self.get_room.is_blocked_user_one and self.get_room.is_blocked_user_two:
            block_status = True
            if self.get_room.is_blocked_user_one and self.get_room.is_blocked_user_two and self.get_sender == self.get_room.user_one:
                message1 = f"You have blocked {self.get_room.user_two.first_name} and even {self.get_room.user_two.first_name} has also blocked you."
            if self.get_room.is_blocked_user_one and self.get_room.is_blocked_user_two and self.get_sender == self.get_room.user_two:
                message1 = f"You have blocked {self.get_room.user_one.first_name} and even {self.get_room.user_one.first_name} has also blocked you." 

        elif self.get_room.is_blocked_user_one or self.get_room.is_blocked_user_two:   
            block_status = True             
            if self.get_room.is_blocked_user_one and self.get_sender == self.get_room.user_one:
                message1 = f"{self.get_room.user_two.first_name} has blocked you."
            if self.get_room.is_blocked_user_one and self.get_sender == self.get_room.user_two:
                message1 = f"You have blocked {self.get_room.user_one.first_name}"
            if self.get_room.is_blocked_user_two and self.get_sender == self.get_room.user_one:
                message1 = f"You have blocked {self.get_room.user_two.first_name}."
            if self.get_room.is_blocked_user_two and self.get_sender == self.get_room.user_two:
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
        check_room = Room.objects.filter(name=self.room_name)
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
                    save_msg = MessageBox.objects.create(room=self.get_room,sender_user=self.get_sender,reciver_user=self.get_reciver_user,
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
            if self.get_room.is_blocked_user_one and self.get_room.is_blocked_user_two and self.get_sender == self.get_room.user_one:
                message1 = f"You have blocked {self.get_room.user_two.first_name} and even {self.get_room.user_two.first_name} has also blocked you."
            if self.get_room.is_blocked_user_one and self.get_room.is_blocked_user_two and self.get_sender == self.get_room.user_two:
                message1 = f"You have blocked {self.get_room.user_one.first_name} and even {self.get_room.user_one.first_name} has also blocked you."
            
        elif self.get_room.is_blocked_user_one or self.get_room.is_blocked_user_two:   
            block_status = True             
            if self.get_room.is_blocked_user_one and self.get_sender == self.get_room.user_one:
                message1 = f"{self.get_room.user_two.first_name} has blocked you."
            if self.get_room.is_blocked_user_one and self.get_sender == self.get_room.user_two:
                message1 = f"You have blocked {self.get_room.user_one.first_name}"
            if self.get_room.is_blocked_user_two and self.get_sender == self.get_room.user_one:
                message1 = f"You have blocked {self.get_room.user_two.first_name}."
            if self.get_room.is_blocked_user_two and self.get_sender == self.get_room.user_two:
                message1 = f"{self.get_room.user_one.first_name} has blocked you."
        else:
            block_status = False
        
        sender_messages = MessageBox.objects.filter(room=self.get_room, sender_user=self.get_sender)
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


# class ChatConsumer(WebsocketConsumer):
#     def connect(self):
#         self.room_name = self.scope["url_route"]["kwargs"]["room_name"]
#         self.room_group_name = f"chat_{self.room_name}"

#         query_params = parse_qs(self.scope["query_string"].decode("utf-8"))
#         self.sender_uuid = query_params.get('sender_uuid', [''])[0]
#         self.sender_secret_key = query_params.get('sender_secret_key', [''])[0]
#         self.sender_email = query_params.get('sender_email', [''])[0]

#         self.sender = User.objects.filter(uuid=self.sender_uuid, secret_key=self.sender_secret_key).first()
#         self.room = Room.objects.filter(Q(user_one=self.sender) | Q(user_two=self.sender), name=self.room_name).select_related("user_one", "user_two").first()

#         if not self.sender or not self.room:
#             self.close()
#             return
        
#         # Determine receiver
#         self.receiver = self.room.user_two if self.sender == self.room.user_one else self.room.user_one

#         # Cache online status
#         cache.set(self.sender_uuid, self.sender_secret_key)
#         cache.set(self.sender_email, True)

#         # Join room group
#         async_to_sync(self.channel_layer.group_add)(
#             self.room_group_name, self.channel_name
#         )
#         self.accept()

#         # Send initial chat data
#         self.send_initial_data()

#     def send_initial_data(self):
#         """Sends initial messages, online users, and block status."""
#         all_messages = MessageBox.objects.filter(room=self.room)
#         unread_messages = all_messages.filter(reciver_user=self.sender, is_read=False)

#         online_users = [
#             email for email in [self.sender_email, self.receiver.email] if cache.get(email)
#         ]

#         block_status, block_message = self.get_block_status()

#         first_time_chat = not all_messages.filter(sender_user=self.sender).exists()

#         # Mark unread messages as read and send them
#         unread_messages.update(is_read=True)
#         serializer = MessageBoxSerializer(
#             all_messages.filter(Q(text_message__isnull=False) & ~Q(text_message=" ")),
#             many=True
#         )

#         for msg in serializer.data:
#             msg["is_sender"] = msg["sender_user_id"] == self.sender.id

#         response = {
#             "message": block_message,
#             "online_users": online_users,
#             "block_status": block_status,
#             "first_time_chat": first_time_chat,
#             "messages": serializer.data
#         }
#         self.send(text_data=json.dumps(response))

#     def get_block_status(self):
#         """Returns the block status and message for the sender."""
#         if self.room.is_blocked_user_one and self.room.is_blocked_user_two:
#             return True, f"You and {self.receiver.first_name} have blocked each other."

#         if self.room.is_blocked_user_one and self.sender == self.room.user_one:
#             return True, f"{self.receiver.first_name} has blocked you."
#         if self.room.is_blocked_user_one and self.sender == self.room.user_two:
#             return True, f"You have blocked {self.receiver.first_name}."

#         if self.room.is_blocked_user_two and self.sender == self.room.user_one:
#             return True, f"You have blocked {self.receiver.first_name}."
#         if self.room.is_blocked_user_two and self.sender == self.room.user_two:
#             return True, f"{self.receiver.first_name} has blocked you."

#         return False, None

#     def receive(self, text_data):
#         """Handles incoming WebSocket messages."""
#         data = json.loads(text_data)
#         message_text = data.get("message", "")

#         block_status, block_message = self.get_block_status()
#         if block_status:
#             self.send(text_data=json.dumps({"message": block_message}))
#             return

#         MessageBox.objects.create(
#             room=self.room,
#             sender_user=self.sender,
#             reciver_user=self.receiver,
#             text_message=message_text,
#             is_read=False
#         )

#         online_users = [
#             email for email in [self.sender_email, self.receiver.email] if cache.get(email)
#         ]

#         response = {
#             "message": message_text,
#             "sender": self.sender.email,
#             "receiver": self.receiver.email,
#             "online_users": online_users
#         }

#         # Send to WebSocket and room group
#         self.send(text_data=json.dumps(response))
#         async_to_sync(self.channel_layer.group_send)(
#             self.room_group_name, {
#                 "type": "chat_message",
#                 "message": response
#             }
#         )

#     def chat_message(self, event):
#         """Receives messages sent to the room group."""
#         self.send(text_data=json.dumps(event["message"]))

#     def disconnect(self, close_code):
#         """Handles WebSocket disconnection."""
#         cache.delete(self.sender_email)
#         async_to_sync(self.channel_layer.group_discard)(
#             self.room_group_name, self.channel_name
#         )

   
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

  