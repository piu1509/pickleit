from datetime import datetime
from django.shortcuts import get_object_or_404
from apps.chat.models import *
from apps.user.helpers import *
from apps.team.models import *
from apps.pickleitcollection.models import *

from django.shortcuts import render, HttpResponse
from django.db.models import Q, Count, Exists, OuterRef

from rest_framework.response import Response
from rest_framework.decorators import api_view
from rest_framework import status, serializers
from rest_framework.pagination import PageNumberPagination


class LastMessageSerializer(serializers.ModelSerializer):
    room_name = serializers.CharField(source='room.name')
    time = serializers.DateTimeField(source='created_at')

    class Meta:
        model = MessageBox
        fields = ['room_name', 'text_message', 'time']


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'uuid', 'secret_key', 'first_name', 'last_name', 'gender')


class RoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = Room
        fields = ('id', 'name') 


class MessageBoxSerializer(serializers.ModelSerializer):
    room = RoomSerializer()    

    class Meta:
        model = MessageBox
        fields = ('id', 'room', 'sender_user_id', 'reciver_user_id', 'is_read', 'text_message', 'send_file', 'send_image', 'created_at')


class NotificationBoxSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationBox
        fields = "__all__"


class MessageSerializer(serializers.ModelSerializer):
    is_sendor = serializers.SerializerMethodField()
    class Meta:
        model = MessageBox
        fields = ['id', 'room', 'sender_user_id', 'reciver_user_id', 'is_read', 'text_message', 'send_file', 'send_image', 'created_at','is_sendor']

    def get_is_sendor(self, obj):        
        check_user_id = self.context.get('check_user_id')
        return obj.sender_user_id == check_user_id
    

@api_view(('GET',))
def chat_user_details(request):
    data = {'status': '','room_details':[],'user_details':[], 'message': ''}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key') 
        chat_user_uuid = request.GET.get('chat_user_uuid')
        chat_user_secret_key = request.GET.get('chat_user_secret_key')
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        check_chat_user = User.objects.filter(uuid=chat_user_uuid, secret_key=chat_user_secret_key)
        if check_user.exists() and check_chat_user.exists():
            get_user = check_user.first()
            get_chat_user = check_chat_user.first()
            check_room = Room.objects.filter(Q(user_one=get_user, user_two=get_chat_user) | Q(user_one=get_chat_user, user_two=get_user))
            if check_room.exists():
                get_room = check_room.first()
            else:
                get_room = Room.objects.create(name=f"{get_user.id}{get_chat_user.id}", user_one=get_user, user_two=get_chat_user)
            room_details = {"room_name": get_room.name,
                            "user_one": get_room.user_one.username,
                            "user_two": get_room.user_two.username,
                            'is_blocked_user_one': get_room.is_blocked_user_one,
                            'is_blocked_user_two': get_room.is_blocked_user_two
                            }
            user_details = check_chat_user.values("uuid","secret_key","username","email","first_name","last_name","phone","user_birthday","image","gender","street","city","state","country","postal_code")
            data["status"] = status.HTTP_200_OK
            data["room_details"] = room_details
            data["user_details"] = user_details
            data["message"] = "Data found."
        else:
            data["status"] = status.HTTP_401_UNAUTHORIZED
            data["message"] = "User not found."

    except Exception as e:
        data['status'] = status.HTTP_400_BAD_REQUEST
        data['message'] = str(e)
    return Response(data)


# @api_view(('GET',))
# def chat_list(request):
#     data = {'status': '', 'data': [], 'message': ''}
#     try:
#         user_uuid = request.GET.get('user_uuid')
#         user_secret_key = request.GET.get('user_secret_key')
#         search_text = request.GET.get('search_text')
#         param_value = request.query_params.get('param_name')
        
#         check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
#         if check_user.exists():
#             get_user = check_user.first()
#             all_users = User.objects.all().values("id","uuid","secret_key","username","email","first_name","last_name","phone","user_birthday","image","gender","street","city","state","country","postal_code","is_player","is_organizer","is_sponsor","is_ambassador","is_admin")
#             if not param_value:
#                 if not search_text:
#                     all_users = all_users
#                 else:
#                     all_users = all_users.filter(Q(first_name__icontains=search_text) | Q(last_name__icontains=search_text))
#             else:
#                 if param_value.lower() == "player":
#                     if not search_text:
#                         all_users = all_users.filter(is_player=True)
#                     else:
#                         all_users = all_users.filter(Q(first_name__icontains=search_text, is_player=True) | Q(last_name__icontains=search_text, is_player=True))
#                 if param_value.lower() == "admin":
#                     if not search_text:
#                         all_users = all_users.filter(is_admin=True)
#                     else:
#                         all_users = all_users.filter(Q(first_name__icontains=search_text, is_admin=True) | Q(last_name__icontains=search_text, is_admin=True))
#                 if param_value.lower() == "organizer":
#                     if not search_text:
#                         all_users = all_users.filter(is_organizer=True)
#                     else:
#                         all_users = all_users.filter(Q(first_name__icontains=search_text, is_organizer=True) | Q(last_name__icontains=search_text, is_organizer=True))

#                 if param_value.lower() == "sponsor":
#                     if not search_text:
#                         all_users = all_users.filter(is_sponsor=True)
#                     else:
#                         all_users = all_users.filter(Q(first_name__icontains=search_text, is_sponsor=True) | Q(last_name__icontains=search_text, is_sponsor=True))
#                 if param_value.lower() == "ambassador":
#                     if not search_text:
#                         all_users = all_users.filter(is_ambassador=True)
#                     else:
#                         all_users = all_users.filter(Q(first_name__icontains=search_text, is_ambassador=True) | Q(last_name__icontains=search_text, is_ambassador=True))
                
#             for user_data in all_users:
#                 user_id = user_data["id"]
                
#                 user_data["unread"] = 0               
#                 get_user2 = User.objects.filter(id=user_id).first()
#                 room_user_one = Room.objects.filter(user_one=get_user, user_two=get_user2)
#                 room_user_two = Room.objects.filter(user_one=get_user2, user_two=get_user)
#                 if room_user_one.exists():
#                     get_room=room_user_one.first()
#                     message = MessageBox.objects.filter(room=get_room)
#                     if message.exists():
#                         get_last_msg = message.last()
#                         user_data["last_message"] = get_last_msg.text_message
#                         user_data["unread"] = MessageBox.objects.filter(sender_user__id=user_data["id"],reciver_user__id=get_user.id, is_read=False).count()
#                         serializer = LastMessageSerializer(get_last_msg)                
#                         user_data["last_message_data"] = serializer.data                                               
#                         user_data["time"] = serializer.data["time"]
                        
#                     else:
#                         user_data["last_message"] = "No message Yet!"
#                         user_data["time"] = None
#                 elif room_user_two.exists():
#                     get_room=room_user_two.first()
#                     message = MessageBox.objects.filter(room=get_room)
#                     if message.exists():
#                         get_last_msg = message.last()
#                         user_data["unread"] = MessageBox.objects.filter(sender_user__id=user_data["id"],reciver_user__id=get_user.id, is_read=False).count()
#                         user_data["last_message"] = get_last_msg.text_message
                        
#                         user_data["time"] = get_last_msg.created_at
                       
#                     else:
#                         user_data["last_message"] = "No message Yet!"
#                         user_data["time"] = None
#                 else:
#                     user_data["last_message"] = "No message Yet!"
#                     user_data["time"] = None
#             users_with_message = []
#             users_without_message = []
#             for user_data in all_users:
#                 if user_data["time"] is not None:
#                     users_with_message.append(user_data)
#                 else:
#                     users_without_message.append(user_data)

#             sorted_users_with_message = sorted(users_with_message, key=lambda user_data: user_data["time"], reverse=True) 
#             all_users = sorted_users_with_message + users_without_message
            
#             data["status"] = status.HTTP_200_OK
#             data["data"] = list(all_users)
#             data["message"] = "Data found"

#         else:
#             data['status'] = status.HTTP_401_UNAUTHORIZED
#             data['message'] = "Unauthorized access"

#     except Exception as e:
#         data['status'] = status.HTTP_400_BAD_REQUEST
#         data['message'] = str(e)
#     return Response(data)


@api_view(('GET',))
def chat_list(request):
    data = {'status': '', 'data': [], 'message': ''}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        search_text = request.GET.get('search_text')
        param_value = request.query_params.get('param_name')
        
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if check_user.exists():
            get_user = check_user.first()
            all_users = User.objects.all().values("id","uuid","secret_key","username","email","first_name","last_name","phone","user_birthday","image","gender","street","city","state","country","postal_code","is_player","is_organizer","is_sponsor","is_ambassador","is_admin")
            if not param_value:
                if not search_text:
                    all_users = all_users
                else:
                    all_users = all_users.filter(Q(first_name__icontains=search_text) | Q(last_name__icontains=search_text))
            else:
                if param_value.lower() == "player":
                    if not search_text:
                        all_users = all_users.filter(is_player=True)
                    else:
                        all_users = all_users.filter(Q(first_name__icontains=search_text, is_player=True) | Q(last_name__icontains=search_text, is_player=True))
                if param_value.lower() == "admin":
                    if not search_text:
                        all_users = all_users.filter(is_admin=True)
                    else:
                        all_users = all_users.filter(Q(first_name__icontains=search_text, is_admin=True) | Q(last_name__icontains=search_text, is_admin=True))
                if param_value.lower() == "organizer":
                    if not search_text:
                        all_users = all_users.filter(is_organizer=True)
                    else:
                        all_users = all_users.filter(Q(first_name__icontains=search_text, is_organizer=True) | Q(last_name__icontains=search_text, is_organizer=True))

                if param_value.lower() == "sponsor":
                    if not search_text:
                        all_users = all_users.filter(is_sponsor=True)
                    else:
                        all_users = all_users.filter(Q(first_name__icontains=search_text, is_sponsor=True) | Q(last_name__icontains=search_text, is_sponsor=True))
                if param_value.lower() == "ambassador":
                    if not search_text:
                        all_users = all_users.filter(is_ambassador=True).order_by("created_at")
                    else:
                        all_users = all_users.filter(Q(first_name__icontains=search_text, is_ambassador=True) | Q(last_name__icontains=search_text, is_ambassador=True)).order_by("created_at")
                
            for user_data in all_users:
                user_id = user_data["id"]
                
                user_data["unread"] = 0               
                get_user2 = User.objects.filter(id=user_id).first()
                room_user_one = Room.objects.filter(user_one=get_user, user_two=get_user2)
                room_user_two = Room.objects.filter(user_one=get_user2, user_two=get_user)
                if room_user_one.exists():
                    get_room=room_user_one.first()
                    message = MessageBox.objects.filter(room=get_room).exclude(text_message__isnull=True).exclude(text_message__in=["", " ", "  "])
                    if message.exists():
                        get_last_msg = message.last()
                        user_data["last_message"] = get_last_msg.text_message
                        user_data["unread"] = MessageBox.objects.filter(sender_user__id=user_data["id"],reciver_user__id=get_user.id, is_read=False).count()
                        serializer = LastMessageSerializer(get_last_msg)                
                        user_data["last_message_data"] = serializer.data                                               
                        user_data["time"] = serializer.data["time"]
                        
                    else:
                        user_data["last_message"] = "No message Yet!"
                        user_data["time"] = None

                    if get_room.is_blocked_user_one is False and get_room.is_blocked_user_two is False:
                        user_data["is_block"] = False
                    else:
                        user_data["is_block"] = True
                elif room_user_two.exists():
                    get_room=room_user_two.first()
                    message = MessageBox.objects.filter(room=get_room)
                    if message.exists():
                        get_last_msg = message.last()
                        user_data["last_message"] = get_last_msg.text_message
                        user_data["unread"] = MessageBox.objects.filter(sender_user__id=user_data["id"],reciver_user__id=get_user.id, is_read=False).count()
                        serializer = LastMessageSerializer(get_last_msg)                
                        user_data["last_message_data"] = serializer.data                                               
                        user_data["time"] = serializer.data["time"]
                       
                    else:
                        user_data["last_message"] = "No message Yet!"
                        user_data["time"] = None

                    if get_room.is_blocked_user_one is False and get_room.is_blocked_user_two is False:
                        user_data["is_block"] = False
                    else:
                        user_data["is_block"] = True
                else:
                    # print()
                    user_data["is_block"] = False
                    user_data["last_message"] = "No message Yet!"
                    user_data["time"] = None

                

            users_with_message = []
            users_without_message = []
            for user_data in all_users:
                if user_data["time"] is not None:
                    users_with_message.append(user_data)
                else:
                    users_without_message.append(user_data)

            # sorted_users_with_message = sorted(users_with_message, key=lambda user_data: user_data["time"], reverse=True) 
            # sorted_users_with_message = sorted(users_with_message, key=lambda user_data: user_data["time"] if user_data["time"] else datetime.min, reverse=True) 
            sorted_users_with_message = sorted(users_with_message, key=lambda x: x["time"], reverse=True)
            # sorted_users_with_message = sorted(users_with_message, key=lambda x: x["time"], reverse=True)
            all_users = sorted_users_with_message + users_without_message
            
            data["status"] = status.HTTP_200_OK
            data["data"] = list(all_users)
            data["message"] = "Data found"

        else:
            data['status'] = status.HTTP_401_UNAUTHORIZED
            data['message'] = "Unauthorized access"

    except Exception as e:
        data['status'] = status.HTTP_400_BAD_REQUEST
        data['message'] = str(e)
    return Response(data)


@api_view(('GET',))
def user_chat_list(request):
    data = {'status': '', 'data': [], 'message': '', 'room_name': '', 'sender': [], 'receiver': []}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        reciver_uuid = request.GET.get('sender_uuid')
        reciver_secret_key = request.GET.get('sender_secret_key')

        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        check_sender = User.objects.filter(uuid=reciver_uuid, secret_key=reciver_secret_key)

        if check_user.exists() and check_sender.exists():
            user = check_user.first()
            sender= check_sender.first()
            room = Room.objects.filter(
                Q(user_one=user, user_two=sender) | Q(user_one=sender, user_two=user)
            ).first()
            
            if not room:
                name = f"{user.id}{sender.id}"
                room = Room.objects.create(name=name, user_one=user, user_two=sender)

            chat_data = MessageBox.objects.filter(room=room)
            paginator = PageNumberPagination()
            paginator.page_size = 30  # Adjust as needed
            chat_list = paginator.paginate_queryset(chat_data, request)
            serializer = MessageSerializer(chat_list, many=True, context={'check_user_id': user.id})
            paginated_response = paginator.get_paginated_response(serializer.data)
            sender_data = [
                {
                    "id":sender.id,
                    "first_name":sender.first_name,
                    "last_name":sender.last_name,
                    "uuid":sender.uuid,
                    "secret_key":sender.secret_key
                }
            ]
            receiver_data =  [
                {
                    "id":user.id,
                    "first_name":user.first_name,
                    "last_name":user.last_name,
                    "uuid":user.uuid,
                    "secret_key":user.secret_key
                }
            ]
            # print(sender_data,receiver_data)
            # bad_words_list = get_bad_words_list()
            # for replc in serializer.data:
            #     text_msg = replc["text_message"].split(" ")
            #     for i in range(len(text_msg)):
            #         if text_msg[i].lower() in bad_words_list:
            #             text_msg[i] = "****"
            #             replc["text_message"] = text_msg[i]

            data['sender'] = sender_data
            data['receiver'] = receiver_data
            data['status'] = status.HTTP_200_OK
            data['count '] = paginated_response.data["count"]
            data['previous'] = paginated_response.data["previous"]
            data["next"] = paginated_response.data["next"]
            data['data'] = paginated_response.data["results"]
            data['message'] = "Data found"
            data['room_name'] = room.name
        else:
            data["status"] = status.HTTP_404_NOT_FOUND
            data["message"] = "User not found"
    except Exception as e:
        data['status'] = status.HTTP_400_BAD_REQUEST
        data['message'] = str(e)
        
    return Response(data)


@api_view(('GET',))
def chat_user_list(request):
    data = {'status': '', 'data': [], 'message': ''}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        search_text = request.GET.get('search_text')
        
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if check_user.exists():
            get_user = check_user.first()
            if get_user.is_admin or get_user.is_organizer:
                if not search_text:
                    all_players = Player.objects.all().values()
                else:
                    all_players = Player.objects.filter(Q(player_first_name__icontains=search_text) | Q(player_last_name__icontains=search_text)).values()
            elif get_user.is_team_manager or get_user.is_coach:
                if not search_text:
                    all_players = Player.objects.filter(created_by_id=get_user.id).values()
                else:
                    all_players = Player.objects.filter(created_by_id=get_user.id).filter(Q(player_first_name__icontains=search_text) | Q(player_last_name__icontains=search_text)).values()
            for player_data in all_players:
                player_id = player_data["id"]
                user_id = player_data["player_id"]
                user_image = User.objects.filter(id=user_id).values()
                player_data["user_uuid"] = user_image[0]["uuid"]
                player_data["unread"] = 0
                player_data["user_secret_key"] = user_image[0]["secret_key"]
                if user_image[0]["image"] is not None or user_image[0]["image"] != "":
                    player_data["player_image"] = user_image[0]["image"]
                else:
                    player_data["player_image"] = None 
                player_data["is_edit"] = player_data["created_by_id"] == get_user.id

                get_user2 = User.objects.filter(id=user_id).first()
                room_user_one = Room.objects.filter(user_one=get_user, user_two=get_user2)
                room_user_two = Room.objects.filter(user_one=get_user2, user_two=get_user)
                if room_user_one.exists():
                    get_room=room_user_one.first()
                    message = MessageBox.objects.filter(room=get_room)
                    if message.exists():
                        get_last_msg = message.last()
                        player_data["last_message"] = get_last_msg.text_message
                        player_data["unread"] = MessageBox.objects.filter(sender_user__id=user_image[0]["id"],reciver_user__id=get_user.id, is_read=False).count()
                        serializer = LastMessageSerializer(instance=get_last_msg)                
                        player_data["last_message_data"] = serializer.data                                               
                        player_data["time"] = serializer.data["time"]
                        
                    else:
                        player_data["last_message"] = "No message Yet!"
                        player_data["time"] = None
                elif room_user_two.exists():
                    get_room=room_user_two.first()
                    message = MessageBox.objects.filter(room=get_room)
                    if message.exists():
                        get_last_msg = message.last()
                        player_data["unread"] = MessageBox.objects.filter(sender_user__id=user_image[0]["id"],reciver_user__id=get_user.id, is_read=False).count()
                        player_data["last_message"] = get_last_msg.text_message
                        
                        player_data["time"] = get_last_msg.created_at
                       
                    else:
                        player_data["last_message"] = "No message Yet!"
                        player_data["time"] = None
                else:
                    player_data["last_message"] = "No message Yet!"
                    player_data["time"] = None
            players_with_message = []
            players_without_message = []
            for player_data in all_players:
                if player_data["time"] is not None:
                    players_with_message.append(player_data)
                else:
                    players_without_message.append(player_data)

            sorted_players_with_message = sorted(players_with_message, key=lambda player_data: player_data["time"], reverse=True) 
            all_players = sorted_players_with_message + players_without_message
            
            data["status"] = status.HTTP_200_OK
            data["data"] = list(all_players)
            data["message"] = "Data found"

        else:
            data['status'] = status.HTTP_401_UNAUTHORIZED
            data['message'] = "Unauthorized access"

    except Exception as e:
        data['status'] = status.HTTP_400_BAD_REQUEST
        data['message'] = str(e)
    return Response(data)


@api_view(('GET',))
def unread_chat_users(request):
    data = {'status': '', 'data': [], 'message': ''}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')       
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if check_user.exists():
            get_user = check_user.first()
            # unread_chat_messages = MessageBox.objects.filter(reciver_user__id=get_user.id, is_read=False).count()
            # unread_chat_users = []
            # unique_sender_ids = set()
            # for message in unread_chat_messages:
            #     sender_id = message["sender_user"]
            #     if sender_id not in unique_sender_ids:
            #         unread_chat_users.append({
            #             "sender_id": sender_id,
            #             "sender_username": User.objects.filter(id=sender_id).first().username
            #         })
            #         unique_sender_ids.add(sender_id)
            unread_chat_messages = (
                MessageBox.objects
                .filter(reciver_user__id=get_user.id, is_read=False)
                .aggregate(unread_count=Count('id'))
            )['unread_count']
            data['status'] = status.HTTP_200_OK
            data['data'] = {"unread_chat_users_count": unread_chat_messages}
            data['message'] = "Data found"
        else:
            data['status'] = status.HTTP_401_UNAUTHORIZED
            data['message'] = "Unauthorized access"

    except Exception as e:
        data['status'] = status.HTTP_400_BAD_REQUEST
        data['message'] = str(e)
    return Response(data)


# @api_view(['POST'])
# def block_or_unblock_chat_user(request):
#     data = {'status': '', 'message': ''}

#     try:
#         user_uuid = request.data.get('user_uuid')
#         user_secret_key = request.data.get('user_secret_key')
#         block_user_uuid = request.data.get('block_user_uuid')
#         block_user_secret_key = request.data.get('block_user_secret_key')
#         status_field = request.data.get('status')

#         if status_field is None:
#             return Response({"status": status.HTTP_400_BAD_REQUEST, "message": "Status field is required"})

#         # Convert status to boolean
#         status_true = str(status_field).lower() in ['true', '1']

#         check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
#         check_block_user = User.objects.filter(uuid=block_user_uuid, secret_key=block_user_secret_key)
#         if not check_user.exists() or not check_block_user.exists():
#             return Response({"status": status.HTTP_401_UNAUTHORIZED, "message": "Unauthorized access"})

#         get_user, get_block_user = check_user.first(), check_block_user.first()

#         # Check if room exists
#         get_room = Room.objects.filter(
#             Q(user_one=get_user, user_two=get_block_user) | 
#             Q(user_one=get_block_user, user_two=get_user)
#         ).first()

#         # Create room if it doesn't exist
#         if not get_room:
#             get_room = Room.objects.create(name=f"{get_user.id}{get_block_user.id}", user_one=get_user, user_two=get_block_user)

#         # Update block status
#         if get_room.user_one == get_user:
#             get_room.is_blocked_user_two = status_true
#         else:
#             get_room.is_blocked_user_one = status_true

#         get_room.save()

#         data["status"] = status.HTTP_200_OK
#         data["message"] = "User blocked successfully" if status_true else "User unblocked successfully"

#     except Exception as e:
#         data["status"], data["message"] = status.HTTP_400_BAD_REQUEST, str(e)

#     return Response(data)


# @api_view(('POST',))
# def continue_chat_with_user(request):
#     data = {'status': '', 'message': ''}
#     try:        
#         user_uuid = request.data.get('user_uuid')
#         user_secret_key = request.data.get('user_secret_key') 
#         chat_user_uuid = request.data.get('chat_user_uuid')
#         chat_user_secret_key = request.data.get('chat_user_secret_key')
#         check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
#         check_chat_user = User.objects.filter(uuid=chat_user_uuid, secret_key=chat_user_secret_key)
#         if check_user.exists() and check_chat_user.exists():
#             get_user = check_user.first()
#             get_chat_user = check_chat_user.first()
#             check_room = Room.objects.filter(Q(user_one=get_user, user_two=get_chat_user) | Q(user_one=get_chat_user, user_two=get_user))
#             if check_room.exists():
#                 get_room = check_room.first()
#             else:
#                 get_room = Room.objects.create(name=f"{get_user.id}{get_chat_user.id}", user_one=get_user, user_two=get_chat_user)
#             u1 = get_room.user_one
#             u2 = get_room.user_two
#             data["status"] = status.HTTP_200_OK
#             data["data"] = {"room_id": get_room.id,
#                             "room_name": get_room.name,
#                             "user_one": f"{u1.first_name} {u1.last_name}",
#                             "user_two": f"{u2.first_name} {u2.last_name}"
#                             }
#             data["message"] = "You can continue chatting with this user."
#         else:
#             data["status"] = status.HTTP_401_UNAUTHORIZED
#             data["message"] = "User not found."

#     except Exception as e:
#         data['status'] = status.HTTP_400_BAD_REQUEST
#         data['message'] = str(e)
#     return Response(data)


# @api_view(('POST',))
# def report_chat_user(request):
#     data = {'status': '', 'message': ''}
#     try:        
#         user_uuid = request.data.get('user_uuid')
#         user_secret_key = request.data.get('user_secret_key') 
#         report_user_uuid = request.data.get('report_user_uuid')
#         report_user_secret_key = request.data.get('report_user_secret_key')
#         check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
#         check_report_user = User.objects.filter(uuid=report_user_uuid, secret_key=report_user_secret_key)
#         if check_user.exists() and check_report_user.exists():
#             get_user = check_user.first()
#             get_report_user = check_report_user.first()
#             check_room = Room.objects.filter(Q(user_one=get_user, user_two=get_report_user) | Q(user_one=get_report_user, user_two=get_user))
#             if check_room.exists():
#                 get_room = check_room.first()
#             else:
#                 get_room = Room.objects.create(name=f"{get_user.id}{get_report_user.id}", user_one=get_user, user_two=get_report_user)
#             u1 = get_room.user_one
#             u2 = get_room.user_two 
#             if u1 == get_user:
#                 get_room.is_blocked_user_two = True
#                 get_room.save()
#             if u2 == get_user:
#                 get_room.is_blocked_user_one = True
#                 get_room.save()
#             data["status"] = status.HTTP_200_OK
#             data["message"] = "User reported and blocked successfully."
#         else:
#             data["status"] = status.HTTP_401_UNAUTHORIZED
#             data["message"] = "User not found."

#     except Exception as e:
#         data['status'] = status.HTTP_400_BAD_REQUEST
#         data['message'] = str(e)
#     return Response(data)


@api_view(['POST'])
def block_or_unblock_chat_user(request):
    data = {'status': '', 'message': ''}

    try:
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        block_user_uuid = request.data.get('block_user_uuid')
        block_user_secret_key = request.data.get('block_user_secret_key')
        status_field = request.data.get('status')

        if status_field is None:
            return Response({"status": status.HTTP_400_BAD_REQUEST, "message": "Status field is required"})

        # Convert status to boolean
        status_true = str(status_field).lower() in ['true', '1']

        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        check_block_user = User.objects.filter(uuid=block_user_uuid, secret_key=block_user_secret_key)
        if not check_user.exists() or not check_block_user.exists():
            return Response({"status": status.HTTP_401_UNAUTHORIZED, "message": "Unauthorized access"})

        get_user, get_block_user = check_user.first(), check_block_user.first()

        # Check if room exists
        get_room = Room.objects.filter(
            Q(user_one=get_user, user_two=get_block_user) | 
            Q(user_one=get_block_user, user_two=get_user)
        ).first()

        # Create room if it doesn't exist
        if not get_room:
            get_room = Room.objects.create(name=f"{get_user.id}{get_block_user.id}", user_one=get_user, user_two=get_block_user)

        # Update block status
        if get_room.user_one == get_user:
            get_room.is_blocked_user_two = status_true
        else:
            get_room.is_blocked_user_one = status_true

        get_room.save()

        data["status"] = status.HTTP_200_OK
        data["message"] = "User blocked successfully" if status_true else "User unblocked successfully"

    except Exception as e:
        data["status"], data["message"] = status.HTTP_400_BAD_REQUEST, str(e)

    return Response(data)


@api_view(('POST',))
def continue_chat_with_user(request):
    data = {'status': '', 'message': ''}
    try:        
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key') 
        chat_user_uuid = request.data.get('chat_user_uuid')
        chat_user_secret_key = request.data.get('chat_user_secret_key')

        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        check_chat_user = User.objects.filter(uuid=chat_user_uuid, secret_key=chat_user_secret_key)

        if not check_user.exists() or not check_chat_user.exists():
            return Response({"status": status.HTTP_401_UNAUTHORIZED, "message": "Unauthorized access"})
        
        get_user = check_user.first()
        get_chat_user = check_chat_user.first()
        get_room = Room.objects.filter(
            Q(user_one=get_user, user_two=get_chat_user) | 
            Q(user_one=get_chat_user, user_two=get_user)
        ).first()

        # Create room if it doesn't exist
        if not get_room:
            get_room = Room.objects.create(name=f"{get_user.id}{get_chat_user.id}", user_one=get_user, user_two=get_chat_user) 

        data["status"] = status.HTTP_200_OK
        data["data"] = {"room_id": get_room.id,
                        "room_name": get_room.name,
                        "user_one": f"{get_room.user_one.first_name} {get_room.user_one.last_name}",
                        "user_two": f"{get_room.user_two.first_name} {get_room.user_two.last_name}"
                        }
        data["message"] = "You can continue chatting with this user."
        
    except Exception as e:
        data['status'] = status.HTTP_400_BAD_REQUEST
        data['message'] = str(e)
    return Response(data)


from apps.team.views import notify_edited_player
@api_view(('POST',))
def report_chat_user(request):
    data = {'status': '', 'message': ''}
    try:        
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key') 
        report_user_uuid = request.data.get('report_user_uuid')
        report_user_secret_key = request.data.get('report_user_secret_key')
        reason_for_reporting = request.data.get('reason_for_reporting')

        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        check_report_user = User.objects.filter(uuid=report_user_uuid, secret_key=report_user_secret_key)

        if not check_user.exists() or not check_report_user.exists():
            return Response({"status": status.HTTP_401_UNAUTHORIZED, "message": "Unauthorized access"})
        
        get_user, get_block_user = check_user.first(), check_report_user.first()

        # Check if room exists
        get_room = Room.objects.filter(
            Q(user_one=get_user, user_two=get_block_user) | 
            Q(user_one=get_block_user, user_two=get_user)
        ).first()

        # Create room if it doesn't exist
        if not get_room:
            get_room = Room.objects.create(name=f"{get_user.id}{get_block_user.id}", user_one=get_user, user_two=get_block_user)

        if get_room.user_one == get_user:
            get_room.is_blocked_user_two = True
            get_room.save()
        if get_room.user_two == get_user:
            get_room.is_blocked_user_one = True
            get_room.save()

        admin_user = User.objects.filter(is_superuser=True, is_admin=True).first()
        title = "Report Chat User"
        notify_edited_player(admin_user.id, title, reason_for_reporting)

        data["status"] = status.HTTP_200_OK
        data["message"] = "User reported and blocked successfully."
        
    except Exception as e:
        data['status'] = status.HTTP_400_BAD_REQUEST
        data['message'] = str(e)
    return Response(data)


@api_view(('GET',))
def chat_list_using_pagination(request):
    data = {'status': '', 'data': [], 'message': ''}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        search_text = request.GET.get('search_text')
        param_value = request.query_params.get('param_name')
        
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if check_user.exists():
            get_user = check_user.first()
            all_users = User.objects.all().values("id","uuid","secret_key","username","email","first_name","last_name","phone","user_birthday","image","gender","street","city","state","country","postal_code","is_player","is_organizer","is_sponsor","is_ambassador","is_admin")
            if not param_value:
                if not search_text:
                    all_users = all_users
                else:
                    all_users = all_users.filter(Q(first_name__icontains=search_text) | Q(last_name__icontains=search_text))
            else:
                if param_value.lower() == "player":
                    if not search_text:
                        all_users = all_users.filter(is_player=True)
                    else:
                        all_users = all_users.filter(Q(first_name__icontains=search_text, is_player=True) | Q(last_name__icontains=search_text, is_player=True))
                if param_value.lower() == "admin":
                    if not search_text:
                        all_users = all_users.filter(is_admin=True)
                    else:
                        all_users = all_users.filter(Q(first_name__icontains=search_text, is_admin=True) | Q(last_name__icontains=search_text, is_admin=True))
                if param_value.lower() == "organizer":
                    if not search_text:
                        all_users = all_users.filter(is_organizer=True)
                    else:
                        all_users = all_users.filter(Q(first_name__icontains=search_text, is_organizer=True) | Q(last_name__icontains=search_text, is_organizer=True))

                if param_value.lower() == "sponsor":
                    if not search_text:
                        all_users = all_users.filter(is_sponsor=True)
                    else:
                        all_users = all_users.filter(Q(first_name__icontains=search_text, is_sponsor=True) | Q(last_name__icontains=search_text, is_sponsor=True))
                if param_value.lower() == "ambassador":
                    if not search_text:
                        all_users = all_users.filter(is_ambassador=True).order_by("created_at")
                    else:
                        all_users = all_users.filter(Q(first_name__icontains=search_text, is_ambassador=True) | Q(last_name__icontains=search_text, is_ambassador=True)).order_by("created_at")
                
            for user_data in all_users:
                user_id = user_data["id"]
                
                user_data["unread"] = 0               
                get_user2 = User.objects.filter(id=user_id).first()
                room_user_one = Room.objects.filter(user_one=get_user, user_two=get_user2)
                room_user_two = Room.objects.filter(user_one=get_user2, user_two=get_user)
                if room_user_one.exists():
                    get_room=room_user_one.first()
                    message = MessageBox.objects.filter(room=get_room).exclude(text_message__isnull=True).exclude(text_message__in=["", " ", "  "])
                    if message.exists():
                        get_last_msg = message.last()
                        user_data["last_message"] = get_last_msg.text_message
                        user_data["unread"] = MessageBox.objects.filter(sender_user__id=user_data["id"],reciver_user__id=get_user.id, is_read=False).count()
                        serializer = LastMessageSerializer(get_last_msg)                
                        user_data["last_message_data"] = serializer.data                                               
                        user_data["time"] = serializer.data["time"]
                        
                    else:
                        user_data["last_message"] = "No message Yet!"
                        user_data["time"] = None

                    if get_room.is_blocked_user_one is False and get_room.is_blocked_user_two is False:
                        user_data["is_block"] = False
                    else:
                        user_data["is_block"] = True
                elif room_user_two.exists():
                    get_room=room_user_two.first()
                    message = MessageBox.objects.filter(room=get_room)
                    if message.exists():
                        get_last_msg = message.last()
                        user_data["unread"] = MessageBox.objects.filter(sender_user__id=user_data["id"],reciver_user__id=get_user.id, is_read=False).count()
                        user_data["last_message"] = get_last_msg.text_message
                        
                        serializer = LastMessageSerializer(get_last_msg)                
                        user_data["last_message_data"] = serializer.data                                               
                        user_data["time"] = serializer.data["time"]
                       
                    else:
                        user_data["last_message"] = "No message Yet!"
                        user_data["time"] = None

                    if get_room.is_blocked_user_one is False and get_room.is_blocked_user_two is False:
                        user_data["is_block"] = False
                    else:
                        user_data["is_block"] = True
                else:
                    # print()
                    user_data["is_block"] = False
                    user_data["last_message"] = "No message Yet!"
                    user_data["time"] = None

                

            users_with_message = []
            users_without_message = []
            for user_data in all_users:
                if user_data["time"] is not None:
                    users_with_message.append(user_data)
                else:
                    users_without_message.append(user_data)

            # sorted_users_with_message = sorted(users_with_message, key=lambda user_data: user_data["time"], reverse=True) 
            # sorted_users_with_message = sorted(users_with_message, key=lambda user_data: user_data["time"] if user_data["time"] else datetime.min, reverse=True) 
            sorted_users_with_message = sorted(users_with_message, key=lambda x: x["time"], reverse=True)
            all_users = sorted_users_with_message + users_without_message
            
            paginator = PageNumberPagination()
            paginator.page_size = 20  # Set the page size to 20
            users_data = paginator.paginate_queryset(all_users, request)
            paginated_response = paginator.get_paginated_response(users_data)
            
            data["status"] = status.HTTP_200_OK
            data["count"] = paginated_response.data["count"]
            data["previous"] = paginated_response.data["previous"]
            data["next"] = paginated_response.data["next"]
            data["data"] = paginated_response.data["results"]
            data["message"] = "Data found"

        else:
            data["count"] = ""
            data["previous"] = ""
            data["next"] = ""
            data["data"] = []
            data['status'] = status.HTTP_401_UNAUTHORIZED
            data['message'] = "Unauthorized access"

    except Exception as e:
        data["count"] = ""
        data["previous"] = ""
        data["next"] = ""
        data["data"] = []
        data['status'] = status.HTTP_400_BAD_REQUEST
        data['message'] = str(e)
    return Response(data)


def notify_all_users(titel, message):
    try:
       
        users_with_rooms = User.objects.annotate(
            has_room=Exists(NotifiRoom.objects.filter(user_id=OuterRef('pk')))
        )
        
        for user in users_with_rooms:
            if not user.has_room:
                NotifiRoom.objects.create(user=user, name=f'user_{user.id}')

        users_with_rooms = users_with_rooms.prefetch_related('room_user')

        notifications = []
        for user in users_with_rooms:
            room = user.room_user.first()  
            if room:
                notification = NotificationBox.objects.create(room=room, notify_for=user, titel=titel, text_message=message)
                # check_token = FCMTokenStore.objects.filter(user__id=user.id)
                # if check_token.exists():
                #     get_token = check_token.first().fcm_token["fcm_token"]
                #     send_push_notification(get_token,titel, message)

        return True
    except Exception as e:
        print(e)  
        return False


@api_view(('GET',))
def search_chat_user_by_name(request):
    data = {"status": "", "message": ""}
    try:
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        search_text = request.GET.get('search_text')
        
        user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key).first()
        if not user:
            return Response({"status": status.HTTP_401_UNAUTHORIZED, "message": "Unauthorized access", "data": []})
        
        users = User.objects.filter(
            Q(first_name__icontains=search_text) | Q(last_name__icontains=search_text)
        ).only(
            "id", "uuid", "username", "email", "first_name", "last_name", "phone", "image",
            "gender", "street", "city", "state", "country", "postal_code", "is_player",
            "is_organizer", "is_sponsor", "is_ambassador", "is_admin"
        )
        
        user_ids = [u.id for u in users]
        rooms = Room.objects.filter(
            Q(user_one=user, user_two_id__in=user_ids) | Q(user_two=user, user_one_id__in=user_ids)
        ).select_related("user_one", "user_two")
        
        messages = MessageBox.objects.filter(
            room__in=rooms
        ).exclude(
            text_message__isnull=True
        ).exclude(
            text_message__in=["", " ", "  "]
        ).order_by("-created_at")
        
        unread_counts = MessageBox.objects.filter(
            sender_user_id__in=user_ids, reciver_user=user, is_read=False
        ).values("sender_user_id").annotate(unread=Count("id"))
        
        unread_dict = {entry["sender_user_id"]: entry["unread"] for entry in unread_counts}
        last_message_dict = {}
        
        for msg in messages:
            last_message_dict[msg.room.user_one_id] = msg
            last_message_dict[msg.room.user_two_id] = msg
        
        user_data_list = []
        for u in users:
            last_msg = last_message_dict.get(u.id)
            user_data = {
                "id": u.id,
                "uuid": u.uuid,
                "username": u.username,
                "email": u.email,
                "first_name": u.first_name,
                "last_name": u.last_name,
                "phone": u.phone,
                "image": u.image.url if u.image else None,
                "gender": u.gender,
                "street": u.street,
                "city": u.city,
                "state": u.state,
                "country": u.country,
                "postal_code": u.postal_code,
                "is_player": u.is_player,
                "is_organizer": u.is_organizer,
                "is_sponsor": u.is_sponsor,
                "is_ambassador": u.is_ambassador,
                "is_admin": u.is_admin,
                "unread": unread_dict.get(u.id, 0),
                "last_message": last_msg.text_message if last_msg else "No message Yet!",
                "time": last_msg.created_at if last_msg else None,
                "is_block": last_msg.room.is_blocked_user_one or last_msg.room.is_blocked_user_two if last_msg else False
            }
            user_data_list.append(user_data)
        
        sorted_users = sorted(user_data_list, key=lambda x: x["time"].timestamp() if x["time"] else float('-inf'), reverse=True)

        paginator = PageNumberPagination()
        paginator.page_size = 20
        paginated_users = paginator.paginate_queryset(sorted_users, request)
        
        return paginator.get_paginated_response({
            "status": status.HTTP_200_OK,
            "data": paginated_users,
            "message": "Data found"
        })
    
    except Exception as e:
        return Response({"status": status.HTTP_400_BAD_REQUEST, "message": str(e), "data": []})
    

@api_view(('POST',))
def create_chat_room(request):
    data = {"status": "", "message": ""}
    try:
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        chat_user_uuid = request.data.get('chat_user_uuid')
        chat_user_secret_key = request.data.get('chat_user_secret_key')

        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        check_chat_user = User.objects.filter(uuid=chat_user_uuid, secret_key=chat_user_secret_key)

        if not check_user.exists() or not check_chat_user.exists():
            return Response({"status": status.HTTP_401_UNAUTHORIZED, "message": "Unauthorized access"})
        
        get_user = check_user.first()
        get_chat_user = check_chat_user.first()
        get_room = Room.objects.filter(
            Q(user_one=get_user, user_two=get_chat_user) | 
            Q(user_one=get_chat_user, user_two=get_user)
        ).first()

        # Create room if it doesn't exist
        if not get_room:
            get_room = Room.objects.create(name=f"{get_user.id}{get_chat_user.id}", user_one=get_user, user_two=get_chat_user) 

        data["status"] = status.HTTP_200_OK
        data["message"] = "Room created successfully." 
        
        return Response(data)
    except Exception as e:
        return Response({"status": status.HTTP_400_BAD_REQUEST, "message": str(e), "data": []})
    

@api_view(('POST',))
def mark_msgs_as_read(request):
    data = {"status": "", "message": ""}
    try:
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        chat_user_uuid = request.data.get('chat_user_uuid')
        chat_user_secret_key = request.data.get('chat_user_secret_key')

        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        check_chat_user = User.objects.filter(uuid=chat_user_uuid, secret_key=chat_user_secret_key)

        if not check_user.exists() or not check_chat_user.exists():
            return Response({"status": status.HTTP_401_UNAUTHORIZED, "message": "Unauthorized access"})
        
        get_user = check_user.first()
        get_chat_user = check_chat_user.first()
        get_room = Room.objects.filter(
            Q(user_one=get_user, user_two=get_chat_user) | 
            Q(user_one=get_chat_user, user_two=get_user)
        ).first()

        if not get_room:
            get_room = Room.objects.create(name=f"{get_user.id}{get_chat_user.id}", user_one=get_user, user_two=get_chat_user) 

        unread_msgs = MessageBox.objects.filter(room=get_room, reciver_user=get_user, is_read=False)
        unread_msgs.update(is_read=True)

        data["status"] = status.HTTP_200_OK
        data["message"] = "Unread messages are marked as read."
        return Response(data)

    except Exception as e:
        return Response({"status": status.HTTP_400_BAD_REQUEST, "message": str(e), "data": []})


@api_view(('GET',))
def get_room_user_status(request):
    data = {"status": "", "message": ""}
    try:
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        room_name = request.GET.get('room_name')
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if not check_user.exists():
            return Response({"status": status.HTTP_401_UNAUTHORIZED, "message": "Unauthorized access"})

        check_room = Room.objects.filter(Q(user_one=check_user.first()) | Q(user_two=check_user.first()), name=room_name)
        if not check_room.exists():
            return Response({"status": status.HTTP_401_UNAUTHORIZED, "message": "Invalid room name."})
        
        get_user, get_room = check_user.first(), check_room.first()
        block_status = True
        unblock_status = False

        if get_room.is_blocked_user_one and get_room.user_one == get_user:
            block_status = True
            unblock_status = False 

        elif get_room.is_blocked_user_one and get_room.user_two == get_user:
            block_status = False
            unblock_status = True

        elif get_room.is_blocked_user_two and get_room.user_one == get_user:
            block_status = False
            unblock_status = True

        elif get_room.is_blocked_user_two and get_room.user_two == get_user:
            block_status = True
            unblock_status = False

        first_time_chat_status = True
        check_msg = MessageBox.objects.filter(room__name=room_name, sender_user=get_user)
        if check_msg.exists():
            first_time_chat_status = False
        
        data["status"] = status.HTTP_200_OK
        data["message"] = "Room details fetched successfully."
        data["block_status"] = block_status
        data["unblock_status"] = unblock_status
        data["continue_status"] = first_time_chat_status

        return Response(data)
    except Exception as e:
        return Response({"status": status.HTTP_400_BAD_REQUEST, "message": str(e), "data": []})
 


class UserSearchSerializer(serializers.ModelSerializer):
    uuid = serializers.UUIDField()
    secret_key = serializers.CharField()
    email = serializers.EmailField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    room = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'uuid', 'secret_key', 'email', 'first_name', 'last_name',
            'room', 'image'
        ]

    def get_room(self, obj):
        user = self.context.get('user')
        room = Room.objects.filter(Q(user_one=obj, user_two=user) | Q(user_one=user, user_two=obj)).first()
        return room.name if room else None

@api_view(['GET'])
def get_user_search(request):
    uid = request.GET.get('uuid')
    search_text = request.GET.get('search_text')
    user = get_object_or_404(User, uuid=uid)
    users = User.objects.all()
    if search_text:
        users = users.filter(
            Q(first_name__icontains=search_text) |
            Q(last_name__icontains=search_text) |
            Q(email__icontains=search_text)
        )
    users = users.order_by('first_name')[:30]

       
    serializer = UserSearchSerializer(users, many=True, context={'user': user})
    res = {
        'status': 'success',
        'data': serializer.data,
        'count': len(serializer.data)
    }
    return Response(res, status=status.HTTP_200_OK)



