import email
from datetime import timedelta
from itertools import combinations
import random, json, base64, stripe 
from math import radians, cos, sin, asin, sqrt
from dateutil.relativedelta import relativedelta

from django.conf import settings
from django.utils import timezone
from django.core.cache import cache
from django.core.mail import send_mail
from django.forms.models import model_to_dict
from django.contrib.auth.hashers import make_password
from django.shortcuts import render, get_object_or_404
from django.core.cache.backends.base import DEFAULT_TIMEOUT
from django.db.models.functions import TruncMonth, Cast, Concat
from django.db.models import Case, When, IntegerField, Value, FloatField, Avg, Count, F, Q, Sum

from apps.team.models import *
from apps.chat.models import *
from apps.user.models import *
from apps.user.models import *
from apps.user.helpers import *
from apps.team.serializers import *
from apps.pickleitcollection.models import *

from rest_framework.response import Response
from rest_framework import status, serializers
from rest_framework.decorators import api_view
from rest_framework.pagination import PageNumberPagination

stripe.api_key = settings.STRIPE_PUBLIC_KEY 
protocol = settings.PROTOCALL
CACHE_TTL = getattr(settings, 'CACHE_TTL', DEFAULT_TIMEOUT)

def haversine(lat1, lon1, lat2, lon2):
    """
    Calculate the great-circle distance between two points on the Earth (specified in decimal degrees).
    Returns distance in kilometers.
    """   
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    r = 6371  
    return c * r


@api_view(('GET',))
def api_list(request):
    data = {"USER":"","TEAM":""}
    # USER 
    data["USER"] = [
                    {"name": "SignUp", "path": "4eec011f0e4da0f19f576ac581ae8d77cd0191e51925c59ba843219390f205c9", "role": "ALL"},
                    {"name": "Login", "path": "7b87ea396289adfe5b192307cff9bd4a4e6512779efe14114f655363c17c3b20", "role": "ALL"},
                    {"name": "get_user_access_token", "path": "fd65514d783d0427c58482473b207b5eb5f92d864a738ccdd1f109c53ac9ca8a", "role": "ALL"},
                    {"name": "user_profile_view_api", "path": "89b449c603286a42377df664f16d7a2c9f5c5624250cadfacb1e0747c3e3f77d", "role": "ALL"},
                    {"name": "user_profile_edit_api", "path": "ed9b3852580d7da0fab6f3550acae26ee1ec94618a1fa74bddc62f9e892f3400", "role": "ALL"},
                    ]
    
    # TEAM
    data["TEAM"] = {"name":"leagues_teamType","path":"1963b18359229186f2817624c25bb11c613f9e30b9d2f6f18982064ae2e78d9e","role":"ALL",}
    data["TEAM"] = {"name":"leagues_teamType","path":"1963b18359229186f2817624c25bb11c613f9e30b9d2f6f18982064ae2e78d9e","role":"ALL",}
    return Response(data)


@api_view(('GET',))
def leagues_teamType(request):
    data = {'status':'','data':'','message':''}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        if check_user.exists() :
            alldata = LeaguesTeamType.objects.exclude(name="Open-team").order_by('name').values('uuid','secret_key','name')
            data["status"], data["data"], data["message"] = status.HTTP_200_OK, alldata,"Data found"
        else:
            data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "User not found"   
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
        
    return Response(data)


@api_view(('GET',))
def leagues_pesrsonType(request):
    data = {'status':'','message':''}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        if check_user.exists() :
            alldata = LeaguesPesrsonType.objects.all().order_by('name').values('uuid','secret_key','name')
            data["status"], data["data"], data["message"] = status.HTTP_200_OK, alldata,"Data found"
        else:
            data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "User not found"  
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
        
    return Response(data)


def notify_edited_player(user_id, titel, message):
    try:
        user = User.objects.filter(id=user_id).first()
        # message
        # titel
        Check_room = NotifiRoom.objects.filter(user=user)
        if Check_room.exists():
            room = Check_room.first()
            NotificationBox.objects.create(room=room, notify_for=user, titel=titel, text_message=message)
        else:
            room_name = f"user_{user_id}"
            room = NotifiRoom.objects.create(user=user, name=room_name)
            NotificationBox.objects.create(room=room, notify_for = user, titel = "Profile Completion", text_message=f"Hi {user.first_name}! welcome to PickleIT! Remember to fully update your profile.")
            NotificationBox.objects.create(room=room, notify_for = user, titel = titel, text_message = message)
        check_token = FCMTokenStore.objects.filter(user__id=user_id)
        print(check_token)
        if check_token.exists():            
            get_token = check_token.first().fcm_token["fcm_token"]
            send_push_notification(get_token,titel,message)
        return True
    except:
        return False


@api_view(('POST',))
def create_player(request):
    data = {'status':'','message':''}
    try:        
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        p_first_name = request.data.get('p_first_name')
        p_last_name = request.data.get('p_last_name')
        p_email = request.data.get('p_email')
        p_phone_number = request.data.get('p_phone_number')
        p_ranking = request.data.get('p_ranking')
        p_gender = request.data.get('p_gender')
        p_image = request.FILES.get('p_image')
        

        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        if check_user.exists() :
            check_player = User.objects.filter(email=p_email)
            if check_player.exists():
                data["status"], data["data"], data["message"] = status.HTTP_200_OK, [],"Player already exists in app"
            get_user = check_user.first()
            obj = GenerateKey()
            secret_key = obj.gen_player_key()
            player_full_name = f"{p_first_name} {p_last_name}"
            identify_player = f"{str(p_first_name)[0]} {str(p_last_name)[0]}"
            role = Role.objects.filter(role="User")
            if not role.exists():
                data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, "player role not exists"
                return Response(data)
            six_digit_number = str(random.randint(100000, 999999))
            # print(six_digit_number)
            save_player = Player(secret_key=secret_key,player_first_name=p_first_name,player_last_name=p_last_name,
                                 player_full_name=player_full_name,player_email=p_email,player_phone_number=p_phone_number,
                                 player_ranking=p_ranking,identify_player=identify_player,created_by=get_user, player_image=p_image)
            
            user_secret_key = obj.gen_user_key()
            user = User.objects.create(secret_key=user_secret_key,phone=p_phone_number,first_name=p_first_name, last_name=p_last_name, username=p_email,email=p_email, password=make_password(six_digit_number), password_raw=six_digit_number, is_player=True,role_id=role.first().id,is_verified=True,image=p_image,
                                rank=p_ranking, gender=p_gender) 
            save_player.player = user
            save_player.save()
            if cache.has_key("player_list"):
                cache.delete("player_list")
            app_name = "PICKLEit"
            login_link = "#"
            password = six_digit_number
            # app_image = "http://18.190.217.171/static/images/PickleIt_logo.png"
            send_email_this_user = send_email_for_invite_player(p_first_name, p_email, app_name, login_link, password)
            print(send_email_this_user)
            if get_user.is_admin :
                pass
            else:
                get_user.is_team_manager = True
                get_user.is_coach = True
                get_user.save()
            data["status"], data["data"], data["message"] = status.HTTP_200_OK, [],"Player created successfully"
        else:
            data["status"], data["data"], data["message"] = status.HTTP_404_NOT_FOUND, [],"User not found."
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
        
    return Response(data)


@api_view(('GET',))
def view_player(request):
    data = {'status':'','message':''}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        player_uuid = request.GET.get('player_uuid')
        player_secret_key = request.GET.get('player_secret_key')
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        if check_user.exists() :
            check_player = Player.objects.filter(uuid=player_uuid,secret_key=player_secret_key)
            check_player = Player.objects.filter(uuid=player_uuid,secret_key=player_secret_key)
            if check_player.exists():
                get_player = check_player.first()
                get_team = get_player.team.all()
                team_details = []
                if get_team :
                    for i in get_team :
                        team_details.append({"team_id":i.id,"team_name":i.name})

                data["data"] = {"palyer_data":check_player.values("player__first_name","player__last_name","player_ranking","player__rank","player__gender","player__image","player__email","player__phone"),
                                "team_details":team_details}
      
                data["status"], data["message"] = status.HTTP_200_OK, "Data found"
            else:
                data["status"], data["data"], data["message"] = status.HTTP_403_FORBIDDEN, "","Player not found"
        else:
            data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "User not found"  
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
        
    return Response(data)


@api_view(('POST',))
def email_send_for_create_user(request):
    data = {'status': '', 'message': ''}
    try:        
        email = request.data.get('email')
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        sender = "Someone"
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        if check_user.exists() :
            first_name = check_user.first().first_name
            last_name = check_user.first().last_name
            sender = f"{first_name} {last_name}"
        app_name = "PICKLEit"
        check_email = User.objects.filter(email=str(email).strip())
        if check_email.exists():
            #protocol = 'https' if request.is_secure() else 'http'
            host = request.get_host()
            current_site = f"{protocol}://{host}"
            # print(current_site)
            # verification_url = f"{current_site}/user/3342cb68e59a46aa0d8be6504ee298446bf1caff5aeae202ddec86de1e38436c/{get_user.uuid}/{get_user.secret_key}/{get_user.generated_otp}/"
            get_user = check_email.first()
            subject = f'{app_name} - Get Your User Credentials'
            message = ""
            html_message = f"""
                            <div style="background-color:#f4f4f4;">
                                <div style="margin:0px auto;border-radius:0px;max-width:600px;">
                                <table align="center" border="0" cellpadding="0" cellspacing="0" role="presentation" style="width:100%;border-radius:0px;">
                                    <tbody>
                                    <tr>
                                        <td style="font-size:0px;padding:5px 10px 5px 10px;text-align:center;">
                                        <div class="mj-column-per-100 mj-outlook-group-fix" style="font-size:0px;display:inline-block;vertical-align:top;width:100%;">
                                            <table border="0" cellpadding="0" cellspacing="0" role="presentation" style="vertical-align:top;" width="100%">
                                            <tbody>
                                                <tr>
                                                <td align="center" style="font-size:0px;padding:0 0px 20px 0px;word-break:break-word;">
                                                    <table border="0" cellpadding="0" cellspacing="0" role="presentation" style="border-collapse:collapse;border-spacing:0px;">
                                                    <tbody>
                                                        <tr>
                                                        <td style="width:560px;">
                                                            <table border="0" cellpadding="0" cellspacing="0" role="presentation" style="border-collapse:collapse;border-spacing:0px;width: 100%;">
                                                            <tbody>
                                                                <tr>
                                                                <td style="background-color: #fff;border-radius: 20px;padding: 15px 20px;">
                                                                    <table border="0" cellpadding="0" cellspacing="0" role="presentation" style="border-collapse:collapse;border-spacing:0px;width: 100%;">
                                                                    <tbody>
                                                                        <tr>
                                                                        <td height="20"></td>
                                                                        </tr>
                                                                        <tr>
                                                                        <td><img src="{current_site}/static/images/get_account.jpg" style="display: block;width: 100%;" width="100%;"></td>
                                                                        </tr>
                                                                        <tr>
                                                                        <td height="30"></td>
                                                                        </tr>
                                                                        <tr>
                                                                        <td>
                                                                            <table border="0" cellpadding="0" cellspacing="0" role="presentation"  bgcolor="#F6F6F6" style="border-collapse:collapse;border-spacing:0px;width: 100%; border-radius: 6px;">
                                                                            <tbody>
                                                                                <tr>
                                                                                <td height="20"></td>
                                                                                </tr>
                                                                                <tr>
                                                                                <td style="padding:20px 25px 0 25px;">
                                                                                    <p style=" font-size: 20px; font-weight: 500; line-height: 22px; color: #333333; margin: 0; padding: 0;">Dear {get_user.first_name},</p>
                                                                                </td>
                                                                                </tr>
                                                                                <tr>
                                                                                <td style="padding:0 25px 20px 25px;">
                                                                                    <p style="font-size: 17px;font-weight: 500;color:#333333">{sender} add you as a player of {app_name}</p>
                                                                                    <p style="font-size: 17px;font-weight: 500;color:#333333">Now You can access Your account</p>
                                                                                    <br>
                                                                                    <p style="font-size: 17px;font-weight: 500;color:#333333">Email: {email}</p>
                                                                                    <p style="font-size: 17px;font-weight: 500;color:#333333">New Password: {get_user.password_raw}</p>
                                                                                    <br>
                                                                                    <p style="font-size: 17px;font-weight: 500;color:#333333">Please use this new password to log in to your account. For security reasons, we highly recommend changing your password after logging in.</p>
                                                                                    <p style="font-size: 17px;font-weight: 500;color:#333333">If you face any Problem, please contact our support team immediately at pickleitnow1@gmail.com to secure your account.</p>
                                                                                </td>
                                                                                </tr>
                                                                                <tr>
                                                                                <td style="padding:20px 25px;">
                                                                                    <p style="font-size: 17px;font-weight: 500;color:#333333">Thank you, </p>
                                                                                    <p style="font-size: 17px;font-weight: 500;color:#333333">{app_name} Team</p>
                                                                                </td>
                                                                                </tr>
                                                                            </tbody>
                                                                            </table>
                                                                        </td>
                                                                        </tr>
                                                                        <tr>
                                                                        <td height="20"></td>
                                                                        </tr>
                                                                        
                                                                        <tr>
                                                                        <td height="10"></td>
                                                                    </tbody>
                                                                    </table>
                                                                </td>
                                                                </tr>
                                                            </tbody>
                                                            </table>
                                                        </td>
                                                        </tr>
                                                    </tbody>
                                                    </table>
                                                </td>
                                                </tr>
                                            </tbody>
                                            </table>
                                        </div>
                                        </td>
                                    </tr>
                                    </tbody>
                                </table>
                                </div>
                                <div style="margin:0px auto;border-radius:0px;max-width:600px;">
                                <table align="center" border="0" cellpadding="0" cellspacing="0" role="presentation" style="width:100%;border-radius:0px;">
                                    <tbody>
                                    <tr>
                                        <td style="font-size:0px;padding:5px 10px 5px 10px;text-align:center;">
                                        <div class="mj-column-per-75 mj-outlook-group-fix" style="font-size:0px;display:inline-block;vertical-align:top;width:100%;">
                                            <table border="0" cellpadding="0" cellspacing="0" role="presentation" style="vertical-align:top;" width="100%">
                                            <tbody>
                                                <tr>
                                                <td style="text-align: center;"><img src="{current_site}/static/images/PickleIt_logo.png" width="100"></td>
                                                </tr>
                                                <tr>
                                                <td style="text-align: center;"><p style=" font-size: 15px; font-weight: 500; color: #c1c1c1; line-height: 20px; margin: 0;">© 2024 {app_name}. All Rights Reserved.</p></td>
                                                </tr>
                                            </tbody>
                                            </table>
                                        </div>
                                        </td>
                                    </tr>
                                    </tbody>
                                </table>
                                </div>
                                <div style="margin:0px auto;border-radius:0px;max-width:600px;">
                                <table align="center" border="0" cellpadding="0" cellspacing="0" role="presentation" style="width:100%;border-radius:0px;">
                                    <tbody>
                                    <tr>
                                        <td style="font-size:0px;padding:0px 0px 0px 0px;text-align:center;">
                                        <div class="mj-column-per-100 mj-outlook-group-fix" style="font-size:0px;display:inline-block;vertical-align:top;width:100%;">
                                            <table border="0" cellpadding="0" cellspacing="0" role="presentation" style="vertical-align:top;" width="100%">
                                            <tbody>
                                                <tr>
                                                <td style="font-size:0px;word-break:break-word;">
                                                    <div style="height:20px;line-height:20px;">
                                                    &#8202;
                                                    </div>
                                                </td>
                                                </tr>
                                            </tbody>
                                            </table>
                                        </div>
                                        </td>
                                    </tr>
                                    </tbody>
                                </table>
                                </div>
                            </div>
                            """

            send_mail(
                subject,
                message,
                'pickleitnow1@gmail.com',  # Replace with your email address
                [get_user.email],
                fail_silently=False,
                html_message=html_message,
            )
            data['status'], data['message'] = status.HTTP_200_OK, f"User cradencial is send to {get_user.email}"
        else:
            data['status'], data['message'] = status.HTTP_403_FORBIDDEN, f"Email not found"
    except Exception as e:
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, str(e)
    return Response(data)


@api_view(('POST',))
def edit_player(request):
    data = {'status':'','message':''}
    try:        
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        p_uuid = request.data.get('p_uuid')
        p_secret_key = request.data.get('p_secret_key')
        p_first_name = request.data.get('p_first_name')
        p_last_name = request.data.get('p_last_name')
        p_phone_number = request.data.get('p_phone_number')
        p_ranking = request.data.get('p_ranking')
        p_image = request.FILES.get('p_image')
        p_gender = request.data.get('p_gender')

        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        if check_user.exists() :
            get_user = check_user.first()
            check_player = Player.objects.filter(uuid=p_uuid,secret_key=p_secret_key,created_by=get_user)
            if check_player.exists():
                player_full_name = f"{p_first_name} {p_last_name}"
                identify_player = f"{str(p_first_name)[0]} {str(p_last_name)[0]}"
                if p_image is not None:
                    check_player.update(
                                    player_first_name=p_first_name,
                                    player_last_name=p_last_name,
                                    player_full_name=player_full_name,
                                    player_phone_number=p_phone_number,
                                    player_ranking=p_ranking,
                                    identify_player=identify_player,
                                    player_image=p_image
                                )
                else:
                    check_player.update(
                                    player_first_name=p_first_name,
                                    player_last_name=p_last_name,
                                    player_full_name=player_full_name,
                                    player_phone_number=p_phone_number,
                                    player_ranking=p_ranking,
                                    identify_player=identify_player,
                                )
                if cache.has_key("player_list"):
                    cache.delete("player_list")
                p_user = User.objects.filter(id=check_player.first().player.id)
                if p_user.exists() :
                    get_p_user = p_user.first()
                    get_p_user.first_name = p_first_name
                    get_p_user.last_name = p_last_name
                    get_p_user.rank = p_ranking
                    get_p_user.gender = p_gender
                    get_p_user.phone = p_phone_number
                    if p_image is not None:
                        get_p_user.image = p_image
                    get_p_user.save()
                data["status"], data["message"] = status.HTTP_200_OK, "player Updated successfully"
            else:
                data["status"], data["message"] = status.HTTP_200_OK, "player not found"
        else:
            data["status"], data["message"] = status.HTTP_200_OK, "user not found"
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


@api_view(('POST',))
def delete_player(request):
    data = {'status':'','message':''}
    try:        
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        p_email = request.data.get('p_email')
        p_uuid = request.data.get('p_uuid')
        p_secret_key = request.data.get('p_secret_key')
        
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        if check_user.exists():
            get_player = User.objects.filter(email=p_email)
            check_player = Player.objects.filter(uuid=p_uuid,secret_key=p_secret_key)
            if get_player.exists() and check_player.exists():
                if check_user.first().is_admin:
                    get_player.delete()
                    check_player.delete()                    
                elif check_player.first().created_by == check_user.first():
                    get_player.delete()
                    check_player.delete()
                else:
                    pass
                if cache.has_key("player_list"):
                    cache.delete("player_list")
                data["status"], data["message"] = status.HTTP_200_OK, "player Deleted successfully"
            
            else:
                data["status"], data["message"] = status.HTTP_200_OK, "player not found"
        else:
            data["status"], data["message"] = status.HTTP_200_OK, "user not found"
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


@api_view(('GET',))
def list_player(request):
    data = {'status': '', 'data': [], 'message': ''}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        search_text = request.GET.get('search_text')
        
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if check_user.exists():
            get_user = check_user.first()
            # if get_user.is_admin or get_user.is_organizer or :
            if not search_text:
                all_players = Player.objects.all().order_by('-id').values()
            else:
                all_players = Player.objects.filter(Q(player_first_name__icontains=search_text) | Q(player_last_name__icontains=search_text)).order_by('-id').values()
            
            # elif get_user.is_team_manager or get_user.is_coach:
            #     if not search_text:
            #         all_players = Player.objects.filter(created_by_id=get_user.id).order_by('-id').values()
            #     else:
            #         all_players = Player.objects.filter(created_by_id=get_user.id).filter(Q(player_first_name__icontains=search_text) | Q(player_last_name__icontains=search_text)).order_by('-id').values()
            # else:
            #     all_players = []
            
            following = AmbassadorsDetails.objects.filter(ambassador=get_user)

            if following.exists():
                # Retrieve the existing AmbassadorsDetails instance for the ambassador
                following_instance = following.first()
                following_ids = list(following_instance.following.all().values_list("id", flat=True))
            else:
                # If AmbassadorsDetails doesn't exist for the ambassador, create a new one
                following_instance = AmbassadorsDetails.objects.create(ambassador=get_user)
                # Save the following instance before retrieving the following_ids
                following_instance.save()
                following_ids = list(following_instance.following.all().values_list("id", flat=True))
            for player_data in all_players:
                player_id = player_data["id"]
                user_id = player_data["player_id"]
                user_image = User.objects.filter(id=user_id).values("rank","username","email","first_name","last_name","phone","uuid","secret_key","image","is_ambassador","is_sponsor","is_organizer","is_player","gender")
                user_instance = User.objects.filter(id=user_id).first()
                if user_id in following_ids:
                    player_data["is_follow"] = True
                else:
                    player_data["is_follow"] = False
                player_data["user"] = list(user_image)
                if user_image[0]["gender"] is not None:
                    player_data["gender"] = user_image[0]["gender"]
                else:
                    player_data["gender"] = "Male"
                
                player_rank = user_image[0]["rank"]
                if player_rank == "null" or player_rank == "" or  not player_rank:
                    player_rank = 1
                else:
                    player_rank = float(player_rank)

                player_data["player_ranking"] = player_rank
                player_data["user_uuid"] = user_image[0]["uuid"]
                player_data["player__is_ambassador"] = user_image[0]["is_ambassador"]
                player_data["user_secret_key"] = user_image[0]["secret_key"]
                
                p_image = user_image[0]["image"]
                if str(p_image) == "" or str(p_image) == "null":
                    player_data["player_image"] = None
                else:
                    player_data["player_image"] = user_image[0]["image"]
                
                player_data["is_edit"] = player_data["created_by_id"] == get_user.id
                player_instance = Player.objects.get(id=player_id)
                team_ids = list(player_instance.team.values_list('id', flat=True))
                player_data["team"] = []
                for team_id in team_ids:
                    team = Team.objects.filter(id=team_id).values()
                    if team.exists():
                        player_data["team"].append(list(team))

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


@api_view(['GET'])
def player_list_using_pagination(request):
    data = {'status': '', 'count': '', 'previous': '', 'next': '', 'data': [], 'message': ''}
    try:
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        search_text = request.GET.get('search_text')
        ordering = request.GET.get('ordering')
        gender = request.GET.get('gender')        
        start_rank = request.GET.get('start_rank')
        end_rank = request.GET.get('end_rank')

        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if check_user.exists():
            get_user = check_user.first()
            if not search_text:
                all_players = Player.objects.all()
            else:
                all_players = Player.objects.filter(Q(player_first_name__icontains=search_text) | Q(player_last_name__icontains=search_text))

            following = AmbassadorsDetails.objects.filter(ambassador=get_user)
            if following.exists():
                following_instance = following.first()
                following_ids = list(following_instance.following.all().values_list("id", flat=True))
            else:
                following_instance = AmbassadorsDetails.objects.create(ambassador=get_user)
                following_instance.save()
                following_ids = list(following_instance.following.all().values_list("id", flat=True))

            if ordering == 'latest':
                all_players = all_players.order_by('-id')  # Order by latest ID
            elif ordering == 'a-z':
                all_players = all_players.order_by('player_first_name') 
            else:
                all_players = all_players.order_by('-id')

            if gender not in [None, "null", "", "None"]:
                all_players = all_players.filter(player__gender__iexact=gender).order_by("-id")

            if start_rank not in [None, "null", "", "None"] and end_rank not in [None, "null", "", "None"]:
                all_players = all_players.filter(player__rank__gte=start_rank, player__rank__lte=end_rank).order_by("-id")

            #cache implementation
            if not search_text and not ordering:
                players_list = f'player_list'
                if cache.get(players_list):
                    print('from cache........')
                    players = cache.get(players_list)
                else:
                    print('from db.............')
                    players = all_players
                    cache.set(players_list, players)
            elif search_text and not ordering:
                search_list = f'{search_text}'
                if cache.get(search_list):
                    print('from cache........')
                    players = cache.get(search_list)
                else:
                    print('from db.............')
                    players = all_players
                    cache.set(search_list, players)

            elif not search_text and ordering:
                ordered_list = f'{ordering}'
                if cache.get(ordered_list):
                    print('from cache........')
                    players = cache.get(ordered_list)
                else:
                    print('from db.............')
                    players = all_players
                    cache.set(ordered_list, players)
            else:
                cache_key = f'player_list_{search_text}_{ordering}'
                if cache.get(cache_key):
                    print('from cache........')
                    players = cache.get(cache_key)
                else:
                    print('from db.............')
                    players = all_players
                    cache.set(cache_key, players)
                    
            paginator = PageNumberPagination()
            paginator.page_size = 10  # Set the page size to 20
            result_page = paginator.paginate_queryset(all_players, request)
            serializer = PlayerSerializer(result_page, many=True, context={'request': request})
            serialized_data = serializer.data
            
            def add_additional_fields(player_data):
                player_data["is_edit"] = player_data["created_by_id"] == get_user.id
                player_data["is_follow"] = player_data["player_id"] in following_ids
                return player_data

            serialized_data = list(map(add_additional_fields, serialized_data))
                

            if not serialized_data:
                data["status"] = status.HTTP_200_OK
                data["count"] = 0
                data["previous"] = None
                data["next"] = None
                data["data"] = []
                data["message"] = "No Result found"
            else:
                paginated_response = paginator.get_paginated_response(serialized_data)
                data["status"] = status.HTTP_200_OK
                data["count"] = paginated_response.data["count"]
                data["previous"] = paginated_response.data["previous"]
                data["next"] = paginated_response.data["next"]
                data["data"] = paginated_response.data["results"]
                data["message"] = "Data found"
                # data["status"] = status.HTTP_200_OK
                # data["count"] = len(serialized_data)
                # data["previous"] = None
                # data["next"] = None
                # data["data"] = serialized_data
                # data["message"] = "Data found"
        else:
            data["count"] = 0
            data["previous"] = None
            data["next"] = None
            data["data"] = []
            data['status'] = status.HTTP_401_UNAUTHORIZED
            data['message'] = "Unauthorized access"

    except Exception as e:
        data["count"] = 0
        data["previous"] = None
        data["next"] = None
        data["data"] = []
        data['status'] = status.HTTP_200_OK
        data['message'] = str(e)

    return Response(data)


#change
@api_view(('POST',))
def create_team(request):
    data = {'status': '', 'message': ''}
    try:        
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')

        team_name = request.data.get('team_name')
        team_location = request.data.get('team_location')
        team_image = request.data.get('team_image')
        team_person = request.data.get('team_person')
        team_type = request.data.get('team_type')

        p1_uuid = request.data.get('p1_uuid')
        p1_secret_key = request.data.get('p1_secret_key')

        p2_uuid = request.data.get('p2_uuid')
        p2_secret_key = request.data.get('p2_secret_key')

        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)

        if not check_user.exists():
            data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "User not found"
            return Response(data)

        if not team_name or not team_person:
            data["status"], data["message"] = status.HTTP_403_FORBIDDEN, "Team Name and Team Type (2 person or 4 person) required"
            return Response(data)

        if team_person == "Two Person Team":
            if not p1_uuid or not p1_secret_key or not p2_uuid or not p2_secret_key:
                data["status"], data["message"] = status.HTTP_400_BAD_REQUEST, "Players details required for Two Person Team"
                return Response(data)
            if not Player.objects.filter(uuid=p1_uuid, secret_key=p1_secret_key).exists() or not Player.objects.filter(uuid=p2_uuid, secret_key=p2_secret_key).exists():
                data["status"], data["message"] = status.HTTP_400_BAD_REQUEST, "One or both players do not exist"
                return Response(data)
        elif team_person == "One Person Team":
            if not p1_uuid or not p1_secret_key:
                data["status"], data["message"] = status.HTTP_400_BAD_REQUEST, "Player details required for One Person Team"
                return Response(data)
            if not Player.objects.filter(uuid=p1_uuid, secret_key=p1_secret_key).exists():
                data["status"], data["message"] = status.HTTP_400_BAD_REQUEST, "Player does not exist"
                return Response(data)

        if team_person == "Two Person Team":
            obj = GenerateKey()
            team_secret_key = obj.gen_team_key()
            player1_secret_key = obj.gen_player_key()
            obj2 = GenerateKey()
            player2_secret_key = obj2.gen_player_key()
            created_by_id = check_user.first().id
            if team_image is not None:
                team_image = team_image
            else:
                team_image = None
            save_team = Team(secret_key=team_secret_key, name=team_name, location=team_location, team_person=team_person, team_type=team_type, team_image=team_image, created_by_id=created_by_id)
            save_team.save()
            if cache.has_key("team_list"):
                cache.delete("team_list")
            p1 = Player.objects.filter(uuid=p1_uuid, secret_key=p1_secret_key).first()
            p1.team.add(save_team.id)
            p2 = Player.objects.filter(uuid=p2_uuid, secret_key=p2_secret_key).first()
            p2.team.add(save_team.id)
            check_user.update(is_team_manager=True)
            ##
            # send notification
            #player 1
            player1 = p1.player
            player2 = p2.player
            titel="Team Created"
            notify_message1 = f"Hey {player1.first_name}! You have been added to an awesome team - {save_team.name}"
            notify_edited_player(player1.id, titel, notify_message1)
            
            #player 2
            notify_message2 = f"Hey {player2.first_name}! You have been added to an awesome team - {save_team.name}"
            notify_edited_player(player2.id, titel, notify_message2)
            data["status"], data["message"] = status.HTTP_200_OK, "Team and Player created successfully"
        
        elif team_person == "One Person Team":
            obj = GenerateKey()
            team_secret_key = obj.gen_team_key()
            created_by_id = check_user.first().id
            if team_image is not None:
                team_image = team_image
            else:
                team_image = None
            save_team = Team(secret_key=team_secret_key, name=team_name, location=team_location, team_person=team_person, team_type=team_type, team_image=team_image, created_by_id=created_by_id)
            save_team.save()
            if cache.has_key("team_list"):
                cache.delete("team_list")
            p1 = Player.objects.filter(uuid=p1_uuid, secret_key=p1_secret_key).first()
            p1.team.add(save_team.id)
            check_user.update(is_team_manager=True)
            ##
            # send notification
            #player 1
            
            player1 = p1.player
            titel="Team Created"
            notify_message = f"Hey {player1.first_name}! You have been added to an awesome team - {save_team.name}"
            notify_edited_player(player1.id, titel, notify_message)
            data["status"], data["message"] = status.HTTP_200_OK, "Team and Player created successfully"

    except Exception as e:
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, str(e)

    return Response(data)


@api_view(('GET',))
def team_list(request):
    data = {'status': '', 'message': ''}
    try:
        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        search_text = request.GET.get('search_text')

        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if check_user.exists():
            main_data = []
            user = check_user.first()
            if user.is_admin or user.is_organizer:
                # Admin or organizer can see all teams
                teams_query = Team.objects.all()
            else:
                # Other users can only see their own teams
                teams_query = Team.objects.filter(created_by=user)

            if search_text is not None:
                teams_query = teams_query.filter(Q(name__icontains=search_text))

            teams = teams_query.order_by('-id').values('id', 'uuid', 'secret_key', 'name', 'location', 'created_by__first_name', 'created_by__last_name',
                                                        'team_image', 'created_by__uuid', 'created_by__secret_key', 'team_type', 'team_person', 'created_by_id')
            store_ids = []
            for team in teams:
                store_ids.append(team["id"])
                if team['created_by_id'] == user.id:
                    is_edit = True  
                else:
                    is_edit = False
                get_player = Player.objects.filter(team__id=team['id']).values('uuid', 'secret_key', 'player_full_name', 'player_ranking', 'player__rank')
                for player in get_player:
                    if player['player__rank'] == "" or player['player__rank'] == "null" or not player['player__rank']:
                        player['player_ranking'] = 1
                    else:
                        player['player_ranking'] = float(player['player__rank'])
                
                #team image
                if team['team_image'] == "" or team['team_image'] == "null":
                    team_image = None
                else:
                    team_image = team['team_image']  
                 
                main_data.append({
                    'id':team["id"],
                    'team_uuid': team['uuid'],
                    'team_secret_key': team['secret_key'],
                    'team_name': team['name'],
                    'location': team['location'],
                    'created_by': f"{team['created_by__first_name']} {team['created_by__last_name']}",
                    'created_by_uuid': team['created_by__uuid'],
                    'created_by_secret_key': team['created_by__secret_key'],
                    'team_image': team_image,
                    'player_data': get_player,
                    'team_type': team['team_type'],
                    'team_person': team['team_person'],
                    'is_edit': is_edit
                })
            if user.is_player and (not user.is_admin or not user.is_organizer):
                check_player = Player.objects.filter(player=user)
                if check_player.exists():
                    player = check_player.first()
                    all_team_ids = player.team.all().values_list("id", flat=True)
                    # data["ids"] = all_team_ids
                    for mj in all_team_ids:
                        if mj not in store_ids:
                            team_instance = Team.objects.filter(id=mj).values('id', 'uuid', 'secret_key', 'name', 'location', 'created_by__first_name', 'created_by__last_name',
                                                        'team_image', 'created_by__uuid', 'created_by__secret_key', 'team_type', 'team_person', 'created_by_id').first()
                            is_edit = False
                            get_player = Player.objects.filter(team__id=mj).values('uuid', 'secret_key', 'player_full_name', 'player_ranking', 'player__rank')
                            for player in get_player:
                                player['player_ranking'] = player['player__rank']
                            
                            #team image
                            if team_instance['team_image'] == "" or team_instance['team_image'] == "null":
                                team_image = None
                            else:
                                team_image = team_instance['team_image']
                            
                            main_data.append({
                                'id': team_instance['id'],
                                'team_uuid': team_instance['uuid'],
                                'team_secret_key': team_instance['secret_key'],
                                'team_name': team_instance['name'],
                                'location': team_instance['location'],
                                'created_by': f"{team_instance['created_by__first_name']} {team_instance['created_by__last_name']}",
                                'created_by_uuid': team_instance['created_by__uuid'],
                                'created_by_secret_key': team_instance['created_by__secret_key'],
                                'team_image': team_image,
                                'player_data': get_player,
                                'team_type': team_instance['team_type'],
                                'team_person': team_instance['team_person'],
                                'is_edit': is_edit
                            })
            
            data["status"], data["data"], data["message"] = status.HTTP_200_OK, main_data, "Data found for Admin" if user.is_admin or user.is_organizer else "Data found"
        else:
            data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "User not found"  
    except Exception as e:
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, str(e)
    return Response(data)


# Updated team_list_for pagination
@api_view(('GET',))
def team_list_using_pagination(request):
    data = {
        'status': '',
        'count': '',
        'previous': '',
        'next': '',
        'data': [],
        'message': ''
    }
    try:    
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        search_text = request.GET.get('search_text')
        ordering = request.GET.get('ordering')
        team_person = request.GET.get('team_person')
        team_type = request.GET.get('team_type')
        start_rank = request.GET.get('start_rank')
        end_rank = request.GET.get('end_rank')
        
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if check_user.exists():
            user = check_user.first()
            if user.is_admin or user.is_organizer:
                teams_query = Team.objects.annotate(
                    team_rank=Avg(
                        Case(
                            When(
                                player__player__rank__isnull=False,
                                then=Cast(F("player__player__rank"), output_field=FloatField()),
                            ),
                            default=Value(1.0, output_field=FloatField()),
                            output_field=FloatField(),
                        )
                    )
                )
            else:
                teams_query = Team.objects.filter(created_by=user).annotate(
                    team_rank=Avg(
                        Case(
                            When(
                                player__player__rank__isnull=False,
                                then=Cast(F("player__player__rank"), output_field=FloatField()),
                            ),
                            default=Value(1.0, output_field=FloatField()),
                            output_field=FloatField(),
                        )
                    )
                )

            if search_text:
                teams_query = teams_query.filter(name__icontains=search_text)

            if ordering == "latest":
                teams_query = teams_query.order_by('-id')
            elif ordering == "a-z":
                teams_query = teams_query.order_by('name')
            else:
                teams_query = teams_query.order_by('-id')

            if team_person not in [None, "null", "", "None"]:
                teams_query = teams_query.filter(team_person__icontains=team_person)

            if team_type not in [None, "null", "", "None"]:
                teams_query = teams_query.filter(team_type__iexact=team_type)

            if start_rank not in [None, "null", "", "None"] and end_rank not in [None, "null", "", "None"]:
                teams_query = teams_query.filter(
                Q(team_rank__gte=start_rank) &
                Q(team_rank__lte=end_rank)
            )

            #cache implementation
            # if not search_text and not ordering:
            #     if cache.get('team_list'):
            #         print('from cache........')
            #         teams = cache.get('team_list')
            #     else:
            #         print('from db.............')
            #         teams = teams_query
            #         cache.set('team_list', teams)
            # elif search_text and not ordering:
            #     if cache.get(search_text):
            #         print('from cache........')
            #         teams = cache.get(search_text)
            #     else:
            #         print('from db.............')
            #         teams = teams_query
            #         cache.set(search_text, teams)

            # elif not search_text and ordering:
            #     if cache.get(ordering):
            #         print('from cache........')
            #         teams = cache.get(ordering)
            #     else:
            #         print('from db.............')
            #         teams = teams_query
            #         cache.set(ordering, teams)
            # else:
            #     cache_key = f"team_list_{user_uuid}_{search_text}_{ordering}"
            #     if cache.get(cache_key):
            #         print('from cache........')
            #         teams = cache.get(cache_key)
            #     else:
            #         print('from db.............')
            #         teams = teams_query
            #         cache.set(cache_key, teams)

            paginator = PageNumberPagination()
            paginator.page_size = 10
            paginated_teams = paginator.paginate_queryset(teams_query, request)

            main_data = []
            for team in paginated_teams:
                players = Player.objects.filter(team=team)
                team_rank = sum(float(player.player.rank) if player.player.rank not in ["", "null", None] else 1 for player in players) / max(len(players), 1)
                
                team_data = TeamListSerializer(team).data
                team_data['team_uuid'] = team_data.pop('uuid')
                team_data['team_secret_key'] = team_data.pop('secret_key')
                team_data['team_name'] = team_data.pop('name')
                team_data['location'] = team_data.pop('location')
                team_data['team_rank'] = team_rank
                team_data['is_edit'] = team.created_by_id == user.id
                main_data.append(team_data)

            paginated_response = paginator.get_paginated_response(main_data)
            
            data["status"] = status.HTTP_200_OK
            data["count"] = paginated_response.data["count"]
            data["previous"] = paginated_response.data["previous"]
            data["next"] = paginated_response.data["next"]
            data["data"] = paginated_response.data["results"]
            data["message"] = "Data found for Admin" if user.is_admin or user.is_organizer else "Data found"
            # data["status"] = status.HTTP_200_OK
            # data["count"] = len(main_data)
            # data["previous"] = None
            # data["next"] = None
            # data["data"] = main_data
            # data["message"] = "Data found for Admin" if user.is_admin or user.is_organizer else "Data found"
            
        else:
            data["count"] = 0
            data["previous"] = None
            data["next"] = None
            data["data"] = []
            data['status'] = status.HTTP_401_UNAUTHORIZED
            data['message'] = "Unauthorized access"

    except Exception as e:
        data["count"] = 0
        data["previous"] = None
        data["next"] = None
        data["data"] = []
        data['status'] = status.HTTP_200_OK
        data['message'] = str(e)

    return Response(data)


@api_view(('GET',))
def team_view(request):
    data = {'status':'','message':''}
    try:
        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        t_uuid = request.GET.get('t_uuid')
        t_secret_key = request.GET.get('t_secret_key')

        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        if check_user.exists() :
            check_team = Team.objects.filter(uuid=t_uuid,secret_key=t_secret_key)
            if check_team.exists() :
                main_data = check_team.values('id','uuid','secret_key','name','location','created_by__first_name','created_by__last_name',
                                            'team_image','created_by__uuid','created_by__secret_key','team_type','team_person')
                
                
                
                get_team = check_team.first()

                player_data = Player.objects.filter(team__id=get_team.id).values("id","uuid","secret_key","player__email",
                                                    "player__first_name","player__last_name","player__gender","player__image")

                data["status"], data["data"], data["message"] = status.HTTP_200_OK, {"team_data":main_data,"player_data":player_data},"Data found"
            else:
                data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "Team not found"
        else:
            data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "User not found"  
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


def check_add_player(a, b):
    if a == b:
        return [],[]
    else:
        common_elements = set(a).intersection(b)
        uncommon_a = [x for x in a if x not in common_elements]
        uncommon_b = [x for x in b if x not in common_elements]

        if common_elements:
            return uncommon_a, uncommon_b
        else:
            return a, b
    

@api_view(('POST',))
def edit_team(request):
    data = {'status':'', 'message':''}
    try:        
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')

        t_uuid = request.data.get('t_uuid')
        t_secret_key = request.data.get('t_secret_key')

        team_name = request.data.get('team_name')
        team_location = request.data.get('team_location')
        team_image = request.data.get('team_image')
        team_person = request.data.get('team_person')
        team_type = request.data.get('team_type')

        p1_uuid = request.data.get('p1_uuid')
        p1_secret_key = request.data.get('p1_secret_key')

        p2_uuid = request.data.get('p2_uuid')
        p2_secret_key = request.data.get('p2_secret_key')

        removed_players = []
        new_players = []

        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if check_user.exists(): 
            if not team_name or not team_person:
                data["status"], data["message"] = status.HTTP_403_FORBIDDEN, "Team Name and Team Type (2 person or 4 person) required"
                return Response(data)

            if team_person == "Two Person Team":
                if not p1_uuid or not p1_secret_key or not p2_uuid or not p2_secret_key:
                    data["status"], data["message"] = status.HTTP_403_FORBIDDEN, "Player1 and Player2's email and phone number required"
                    return Response(data)
                else:
                    check_team = Team.objects.filter(uuid=t_uuid, secret_key=t_secret_key)
                    check_player1 = Player.objects.filter(uuid=p1_uuid, secret_key=p1_secret_key)
                    check_player2 = Player.objects.filter(uuid=p2_uuid, secret_key=p2_secret_key)
                    
                    if check_team.exists():
                        team_instance = check_team.first()
                        team_instance.name = team_name
                        team_instance.location = team_location
                        team_instance.team_person = team_person
                        team_instance.team_type = team_type
                        
                        if team_image is not None:
                            team_instance.team_image = team_image
                            
                        pre_player_list = Player.objects.filter(team__id=team_instance.id)
                        for pre_player in pre_player_list:
                            removed_players.append(pre_player.id)
                            pre_player.team.remove(team_instance.id)

                        check_player1_instance = check_player1.first()
                        check_player1_instance.team.add(team_instance.id)
                        new_players.append(check_player1_instance.id)
                        
                        check_player2_instance = check_player2.first()
                        check_player2_instance.team.add(team_instance.id)
                        new_players.append(check_player2_instance.id)
                        team_instance.save()
                        if cache.has_key("team_list"):
                            cache.delete("team_list")
                        #add notification
                        add, rem = check_add_player(new_players, removed_players)
                        
                        titel = "Team Membership Modification"
                        # notification for added player
                        for r in rem:
                            message = f"You have been removed from team {team_instance.name}"
                            user_id = Player.objects.filter(id=r).first().player.id
                            notify_edited_player(user_id, titel, message)
                        
                        titel = "Team Membership Modification"
                        for r in add:
                            message = f"You have been added to team {team_instance.name}"
                            user_id = Player.objects.filter(id=r).first().player.id
                            notify_edited_player(user_id, titel, message)
                        data["status"], data["message"] = status.HTTP_200_OK, f"Team edited successfully"
                    else:
                        data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "Team not found"
                    return Response(data)
                    
                
            if team_person == "One Person Team":
                if not p1_uuid or not p1_secret_key:
                    data["status"], data["message"] = status.HTTP_403_FORBIDDEN, "Player's email and phone number required"
                    return Response(data)
                else:
                    check_team = Team.objects.filter(uuid=t_uuid, secret_key=t_secret_key)
                    check_player = Player.objects.filter(uuid=p1_uuid, secret_key=p1_secret_key)
                    
                    if check_team.exists() and check_player.exists():
                        team_instance = check_team.first()
                        team_instance.name = team_name
                        team_instance.location = team_location
                        team_instance.team_person = team_person
                        team_instance.team_type = team_type
                        
                        if team_image is not None:
                            team_instance.team_image = team_image
                        
                        team_instance.save() 
                        if cache.has_key("team_list"):
                            cache.delete("team_list")                       
                        remove_player_team = Player.objects.filter(team__id=team_instance.id)
                        for remove_player in remove_player_team:
                            removed_players.append(remove_player.id)
                            remove_player.team.remove(team_instance.id)

                        check_player_instance = check_player.first()
                        check_player_instance.team.add(team_instance.id)
                        new_players.append(check_player_instance.id)
                        # notification
                        add, rem = check_add_player(new_players, removed_players)
                        
                        titel = "Team Membership Modification"
                        # notification for added player
                        for r in rem:
                            message = f"You have been removed from team {team_instance.name}"
                            user_id = Player.objects.filter(id=r).first().player.id
                            notify_edited_player(user_id, titel, message)
                        
                        for r in add:
                            message = f"You have been added to team {team_instance.name}"
                            user_id = Player.objects.filter(id=r).first().player.id
                            notify_edited_player(user_id, titel, message)
                        data["status"], data["message"] = status.HTTP_200_OK, f"Team edited successfully"
                    else:
                        data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "Team not found"
                    
                    add, rem = check_add_player(new_players, removed_players)
                    print(add, rem)
                    return Response(data)
            else:
                data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "Something is wrong"
        else:
            data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "User not found"
    except Exception as e:
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    
    print(removed_players)  
    print(new_players)  
    
    return Response(data)


@api_view(('POST',))
def delete_team(request):
    data = {'status':'','message':''}
    try:        
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')

        team_uuid = request.data.get('team_uuid')
        team_secret_key = request.data.get('team_secret_key')

        team_league  = Team.objects.filter(uuid=team_uuid,secret_key=team_secret_key)
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        if check_user.exists():
            team_league  = Team.objects.filter(uuid=team_uuid,secret_key=team_secret_key, created_by=check_user.first())
            if team_league.exists():
                team_id = team_league.first().id 
                check_team_have_any_tournament = Leagues.objects.filter(registered_team__in=[team_id], is_complete=False)
                if not check_team_have_any_tournament.exists():
                    #notify player when delete the team.
                    team_name = team_league.first().name
                    players = Player.objects.filter(team__id=team_id)
                    players_list = list(players)

                    team_league.first().delete()
                    if cache.has_key("team_list"):
                        cache.delete("team_list")
                    titel = "Team Membership Modification"
                    message = f"Hey player! the team {team_name} has been deleted."
                    for player in players_list:
                        notify_edited_player(player.player.id, titel, message)

                    data["status"], data["message"] = status.HTTP_200_OK, "Team Deleted"
                else:
                    data["status"], data["message"] = status.HTTP_200_OK, "Unable to delete team. This team cannot be deleted as it is currently participating in a tournament."
            else:
                data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "Team not found"
        else:
            data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "User not found"
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


@api_view(('POST',))
def send_team_member_notification(request):
    data = {'status':'','message':''}
    try:
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        team_person = request.data.get('team_person')
        player1_email = request.data.get('player1_email')
        player1_first_name = request.data.get('player1_first_name')
        player1_last_name = request.data.get('player1_last_name')
        player1_phone = request.data.get('player1_phone')

        player2_email = request.data.get('player2_email')
        player2_first_name = request.data.get('player2_first_name')
        player2_last_name = request.data.get('player2_last_name')
        player2_phone = request.data.get('player2_phone')

        player3_email = request.data.get('player3_email')
        player3_first_name = request.data.get('player3_first_name')
        player3_last_name = request.data.get('player3_last_name')
        player3_phone = request.data.get('player3_phone')

        player4_email = request.data.get('player4_email')
        player4_first_name = request.data.get('player4_first_name')
        player4_last_name = request.data.get('player4_last_name')
        player4_phone = request.data.get('player4_phone')
        app_name = "PICKLEit"
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        subject = f'You are invited to register in {app_name}'
        #protocol = 'https' if request.is_secure() else 'http'
        host = request.get_host()
        current_site = f"{protocol}://{host}"
        message = ""
        android_url = "https://docs.google.com/uc?export=download&id=1OzRKC3QT-tZg8oSSE9U302stRRXn0aRG"
        ios_url = ""
        if check_user.exists() and team_person and  team_person != "":
            created_by = f"{str(check_user.first().first_name)} {str(check_user.first().last_name)}"
            if team_person == "Two Person Team" :
                for i in range(1,3):
                    player_email = request.data.get('player{}_email'.format(i))
                    player_first_name = request.data.get('player{}_first_name'.format(i))
                    player_last_name = request.data.get('player{}_last_name'.format(i))
                    html_message = f"""
                                <div style="background-color:#f4f4f4;">
                                    <div style="margin:0px auto;border-radius:0px;max-width:600px;">
                                    <table align="center" border="0" cellpadding="0" cellspacing="0" role="presentation" style="width:100%;border-radius:0px;">
                                        <tbody>
                                        <tr>
                                            <td style="font-size:0px;padding:5px 10px 5px 10px;text-align:center;">
                                            <div class="mj-column-per-100 mj-outlook-group-fix" style="font-size:0px;display:inline-block;vertical-align:top;width:100%;">
                                                <table border="0" cellpadding="0" cellspacing="0" role="presentation" style="vertical-align:top;" width="100%">
                                                <tbody>
                                                    <tr>
                                                    <td align="center" style="font-size:0px;padding:0 0px 20px 0px;word-break:break-word;">
                                                        <table border="0" cellpadding="0" cellspacing="0" role="presentation" style="border-collapse:collapse;border-spacing:0px;">
                                                        <tbody>
                                                            <tr>
                                                            <td style="width:560px;">
                                                                <table border="0" cellpadding="0" cellspacing="0" role="presentation" style="border-collapse:collapse;border-spacing:0px;width: 100%;">
                                                                <tbody>
                                                                    <tr>
                                                                    <td style="background-color: #fff;border-radius: 20px;padding: 15px 20px;">
                                                                        <table border="0" cellpadding="0" cellspacing="0" role="presentation" style="border-collapse:collapse;border-spacing:0px;width: 100%;">
                                                                        <tbody>
                                                                            <tr>
                                                                            <td height="20"></td>
                                                                            </tr>
                                                                            <tr>
                                                                            <td><img src="{current_site}/static/images/send_team_member_notification.png" style="display: block;width: 100%;" width="100%;"></td>
                                                                            </tr>
                                                                            <tr>
                                                                            <td height="30"></td>
                                                                            </tr>
                                                                            <tr>
                                                                            <td>
                                                                                <table border="0" cellpadding="0" cellspacing="0" role="presentation"  bgcolor="#F6F6F6" style="border-collapse:collapse;border-spacing:0px;width: 100%; border-radius: 6px;">
                                                                                <tbody>
                                                                                    <tr>
                                                                                    <td height="20"></td>
                                                                                    </tr>
                                                                                    <tr>
                                                                                    <td style="padding:20px 25px 0 25px;">
                                                                                        <p style=" font-size: 20px; font-weight: 500; line-height: 22px; color: #333333; margin: 0; padding: 0;">Dear {player_first_name},</p>
                                                                                    </td>
                                                                                    </tr>
                                                                                    <tr>
                                                                                    <td style="padding:0 25px 20px 25px;">
                                                                                        <p style="font-size: 17px;font-weight: 500;color:#333333">{created_by} have invited you to register in this app.\nClick here and download the app to complete your registration.</p>
                                                                                        <a href="{android_url}" style="margin-right:10px; margin-bottom:10px; font-size: 17px;font-weight: 500;color:#333333; background-color:#008CBA;color:white;padding:10px;text-align:center;text-decoration:none;display:inline-block;border-radius:5px;">android download</a>
                                                                                        <a href="{ios_url}" style="font-size: 17px;font-weight: 500;color:#333333; background-color:#008CBA;color:white;padding:10px;text-align:center;text-decoration:none;display:inline-block;border-radius:5px;">ios download</a>
                                                                                    </td>
                                                                                    </tr>
                                                                                    <tr>
                                                                                    <td style="padding:20px 25px;">
                                                                                        <p style="font-size: 17px;font-weight: 500;color:#333333">Thank you, </p>
                                                                                        <p style="font-size: 17px;font-weight: 500;color:#333333">Pickleball Team</p>
                                                                                    </td>
                                                                                    </tr>
                                                                                </tbody>
                                                                                </table>
                                                                            </td>
                                                                            </tr>
                                                                            
                                                                        </tbody>
                                                                        </table>
                                                                    </td>
                                                                    </tr>
                                                                </tbody>
                                                                </table>
                                                            </td>
                                                            </tr>
                                                        </tbody>
                                                        </table>
                                                    </td>
                                                    </tr>
                                                </tbody>
                                                </table>
                                            </div>
                                            </td>
                                        </tr>
                                        </tbody>
                                    </table>
                                    </div>
                                    <div style="margin:0px auto;border-radius:0px;max-width:600px;">
                                    <table align="center" border="0" cellpadding="0" cellspacing="0" role="presentation" style="width:100%;border-radius:0px;">
                                        <tbody>
                                        <tr>
                                            <td style="font-size:0px;padding:5px 10px 5px 10px;text-align:center;">
                                            <div class="mj-column-per-75 mj-outlook-group-fix" style="font-size:0px;display:inline-block;vertical-align:top;width:100%;">
                                                <table border="0" cellpadding="0" cellspacing="0" role="presentation" style="vertical-align:top;" width="100%">
                                                <tbody>
                                                    <tr>
                                                    <td style="text-align: center;"><img src="{current_site}/static/images/logo.png" width="100"></td>
                                                    </tr>
                                                    <tr>
                                                    <td style="text-align: center;"><p style=" font-size: 15px; font-weight: 500; color: #c1c1c1; line-height: 20px; margin: 0;">© 2023 Pickleball. All Rights Reserved.</p></td>
                                                    </tr>
                                                </tbody>
                                                </table>
                                            </div>
                                            </td>
                                        </tr>
                                        </tbody>
                                    </table>
                                    </div>
                                    <div style="margin:0px auto;border-radius:0px;max-width:600px;">
                                    <table align="center" border="0" cellpadding="0" cellspacing="0" role="presentation" style="width:100%;border-radius:0px;">
                                        <tbody>
                                        <tr>
                                            <td style="font-size:0px;padding:0px 0px 0px 0px;text-align:center;">
                                            <div class="mj-column-per-100 mj-outlook-group-fix" style="font-size:0px;display:inline-block;vertical-align:top;width:100%;">
                                                <table border="0" cellpadding="0" cellspacing="0" role="presentation" style="vertical-align:top;" width="100%">
                                                <tbody>
                                                    <tr>
                                                    <td style="font-size:0px;word-break:break-word;">
                                                        <div style="height:20px;line-height:20px;">
                                                        &#8202;
                                                        </div>
                                                    </td>
                                                    </tr>
                                                </tbody>
                                                </table>
                                            </div>
                                            </td>
                                        </tr>
                                        </tbody>
                                    </table>
                                    </div>
                                </div>
                                """
                    send_mail(
                            subject,
                            message,
                            'pickleitnow1@gmail.com',
                            [player_email],
                            fail_silently=False,
                            html_message=html_message,
                        )
                
                data['status'], data['message'] = status.HTTP_200_OK, f"Email verification link sent"
            
            elif team_person == "Four Person Team" :
                for i in range(1,5):
                    player_email = request.data.get('player{}_email'.format(i))
                    player_first_name = request.data.get('player{}_first_name'.format(i))
                    player_last_name = request.data.get('player{}_last_name'.format(i))
                    html_message = f"""
                                <div style="background-color:#f4f4f4;">
                                    <div style="margin:0px auto;border-radius:0px;max-width:600px;">
                                    <table align="center" border="0" cellpadding="0" cellspacing="0" role="presentation" style="width:100%;border-radius:0px;">
                                        <tbody>
                                        <tr>
                                            <td style="font-size:0px;padding:5px 10px 5px 10px;text-align:center;">
                                            <div class="mj-column-per-100 mj-outlook-group-fix" style="font-size:0px;display:inline-block;vertical-align:top;width:100%;">
                                                <table border="0" cellpadding="0" cellspacing="0" role="presentation" style="vertical-align:top;" width="100%">
                                                <tbody>
                                                    <tr>
                                                    <td align="center" style="font-size:0px;padding:0 0px 20px 0px;word-break:break-word;">
                                                        <table border="0" cellpadding="0" cellspacing="0" role="presentation" style="border-collapse:collapse;border-spacing:0px;">
                                                        <tbody>
                                                            <tr>
                                                            <td style="width:560px;">
                                                                <table border="0" cellpadding="0" cellspacing="0" role="presentation" style="border-collapse:collapse;border-spacing:0px;width: 100%;">
                                                                <tbody>
                                                                    <tr>
                                                                    <td style="background-color: #fff;border-radius: 20px;padding: 15px 20px;">
                                                                        <table border="0" cellpadding="0" cellspacing="0" role="presentation" style="border-collapse:collapse;border-spacing:0px;width: 100%;">
                                                                        <tbody>
                                                                            <tr>
                                                                            <td height="20"></td>
                                                                            </tr>
                                                                            <tr>
                                                                            <td><img src="{current_site}/static/images/send_team_member_notification.png" style="display: block;width: 100%;" width="100%;"></td>
                                                                            </tr>
                                                                            <tr>
                                                                            <td height="30"></td>
                                                                            </tr>
                                                                            <tr>
                                                                            <td>
                                                                                <table border="0" cellpadding="0" cellspacing="0" role="presentation"  bgcolor="#F6F6F6" style="border-collapse:collapse;border-spacing:0px;width: 100%; border-radius: 6px;">
                                                                                <tbody>
                                                                                    <tr>
                                                                                    <td height="20"></td>
                                                                                    </tr>
                                                                                    <tr>
                                                                                    <td style="padding:20px 25px 0 25px;">
                                                                                        <p style=" font-size: 20px; font-weight: 500; line-height: 22px; color: #333333; margin: 0; padding: 0;">Dear {player_first_name} {player_last_name},</p>
                                                                                    </td>
                                                                                    </tr>
                                                                                    <tr>
                                                                                    <td style="padding:0 25px 20px 25px;">
                                                                                        <p style="font-size: 17px;font-weight: 500;color:#333333">{created_by} have invited you to register in this app.\nClick here and download the app to complete your registration.</p>
                                                                                        <a href="{android_url}" style="margin-right:10px; font-size: 17px;font-weight: 500;color:#333333; background-color:#008CBA;color:white;padding:10px;text-align:center;text-decoration:none;display:inline-block;border-radius:5px;">android download</a>
                                                                                        <a href="{ios_url}" style="font-size: 17px;font-weight: 500;color:#333333; background-color:#008CBA;color:white;padding:10px;text-align:center;text-decoration:none;display:inline-block;border-radius:5px;">ios download</a>
                                                                                    </td>
                                                                                    </tr>
                                                                                    <tr>
                                                                                    <td style="padding:20px 25px;">
                                                                                        <p style="font-size: 17px;font-weight: 500;color:#333333">Thank you, </p>
                                                                                        <p style="font-size: 17px;font-weight: 500;color:#333333">Pickleball Team</p>
                                                                                    </td>
                                                                                    </tr>
                                                                                </tbody>
                                                                                </table>
                                                                            </td>
                                                                            </tr>
                                                                            
                                                                        </tbody>
                                                                        </table>
                                                                    </td>
                                                                    </tr>
                                                                </tbody>
                                                                </table>
                                                            </td>
                                                            </tr>
                                                        </tbody>
                                                        </table>
                                                    </td>
                                                    </tr>
                                                </tbody>
                                                </table>
                                            </div>
                                            </td>
                                        </tr>
                                        </tbody>
                                    </table>
                                    </div>
                                    <div style="margin:0px auto;border-radius:0px;max-width:600px;">
                                    <table align="center" border="0" cellpadding="0" cellspacing="0" role="presentation" style="width:100%;border-radius:0px;">
                                        <tbody>
                                        <tr>
                                            <td style="font-size:0px;padding:5px 10px 5px 10px;text-align:center;">
                                            <div class="mj-column-per-75 mj-outlook-group-fix" style="font-size:0px;display:inline-block;vertical-align:top;width:100%;">
                                                <table border="0" cellpadding="0" cellspacing="0" role="presentation" style="vertical-align:top;" width="100%">
                                                <tbody>
                                                    <tr>
                                                    <td style="text-align: center;"><img src="{current_site}/static/images/logo.png" width="100"></td>
                                                    </tr>
                                                    <tr>
                                                    <td style="text-align: center;"><p style=" font-size: 15px; font-weight: 500; color: #c1c1c1; line-height: 20px; margin: 0;">© 2023 Pickleball. All Rights Reserved.</p></td>
                                                    </tr>
                                                </tbody>
                                                </table>
                                            </div>
                                            </td>
                                        </tr>
                                        </tbody>
                                    </table>
                                    </div>
                                    <div style="margin:0px auto;border-radius:0px;max-width:600px;">
                                    <table align="center" border="0" cellpadding="0" cellspacing="0" role="presentation" style="width:100%;border-radius:0px;">
                                        <tbody>
                                        <tr>
                                            <td style="font-size:0px;padding:0px 0px 0px 0px;text-align:center;">
                                            <div class="mj-column-per-100 mj-outlook-group-fix" style="font-size:0px;display:inline-block;vertical-align:top;width:100%;">
                                                <table border="0" cellpadding="0" cellspacing="0" role="presentation" style="vertical-align:top;" width="100%">
                                                <tbody>
                                                    <tr>
                                                    <td style="font-size:0px;word-break:break-word;">
                                                        <div style="height:20px;line-height:20px;">
                                                        &#8202;
                                                        </div>
                                                    </td>
                                                    </tr>
                                                </tbody>
                                                </table>
                                            </div>
                                            </td>
                                        </tr>
                                        </tbody>
                                    </table>
                                    </div>
                                </div>
                                """
                    send_mail(
                            subject,
                            message,
                            'pickleitnow1@gmail.com',
                            [player_email],
                            fail_silently=False,
                            html_message=html_message,
                        )
                
                data['status'], data['message'] = status.HTTP_200_OK, f"Email verification link sent"
            else:
                data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "HTTP_404_NOT_FOUND. team_person parameter not found."
        else:
            data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "User not found."
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


@api_view(('POST',))
def create_leagues(request):
    data = {'status':'','data':[],'message':''}
    try:        
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        name = request.data.get('name')
        leagues_start_date = request.data.get('leagues_start_date')
        leagues_end_date = request.data.get('leagues_end_date')
        registration_start_date = request.data.get('registration_start_date')
        registration_end_date = request.data.get('registration_end_date')
        team_type = request.data.get('team_type')
        play_type = request.data.get('play_type')
        team_person = request.data.get('team_person')
        location = request.data.get('location')
        city = request.data.get('city')
        others_fees = request.data.get('others_fees')
        max_number_team = request.data.get('max_number_team')
        registration_fee = request.data.get('registration_fee')
        description = request.data.get('description')
        image = request.FILES.get('image')
        team_type = json.loads(team_type)
        team_person = json.loads(team_person)
        others_fees = json.loads(others_fees)
        league_type = request.data.get('league_type')
        invited_code = request.data.get('invited_code')

        start_rank = request.data.get('start_rank') 
        end_rank = request.data.get('end_rank')       
        
        if int(max_number_team) % 2 != 0 or int(max_number_team) == 0 or int(max_number_team) == 1:
            data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "Max number of team must be even"
            return Response(data)
        leagues_start_date = datetime.strptime(leagues_start_date, '%m/%d/%Y').strftime('%Y-%m-%d')
        leagues_end_date = datetime.strptime(leagues_end_date, '%m/%d/%Y').strftime('%Y-%m-%d')
        registration_start_date = datetime.strptime(registration_start_date, '%m/%d/%Y').strftime('%Y-%m-%d')
        registration_end_date = datetime.strptime(registration_end_date, '%m/%d/%Y').strftime('%Y-%m-%d')
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        leagues_id = []
        if check_user.exists() and check_user.first().is_admin or check_user.first().is_organizer:
            mesage_box = []
            counter = 0
            for kk in team_type:
                check_leagues = LeaguesTeamType.objects.filter(name=str(kk))
                check_person = LeaguesPesrsonType.objects.filter(name=str(team_person[counter]))
                
                if check_leagues.exists() and check_person.exists():
                    check_leagues_id = check_leagues.first().id
                    check_person_id = check_person.first().id
                    check_unq = Leagues.objects.filter(team_person_id=check_person_id,team_type_id=check_leagues_id,name=name,created_by=check_user.first())
                    if check_unq.exists():
                        message = f"{name}-{kk}"
                        mesage_box.append(message)
                        continue
                    else:
                        pass
                
                full_address = location
                api_key = settings.MAP_API_KEY
                state, country, pincode, latitude, longitude = get_address_details(full_address,api_key)

                if latitude is None:
                    latitude = 38.908683
                if longitude is None:
                    longitude = -76.937352
                obj = GenerateKey()
                secret_key = obj.gen_leagues_key()
                save_leagues = Leagues(secret_key=secret_key,name=name,leagues_start_date=leagues_start_date,leagues_end_date=leagues_end_date,location=location,
                                    registration_start_date=registration_start_date,registration_end_date=registration_end_date,created_by_id=check_user.first().id,
                                    street=state,city=city,state=state,postal_code=pincode,country=country,max_number_team=max_number_team, play_type=play_type,
                                    registration_fee=registration_fee,description=description,image=image,league_type=league_type)
                if league_type == "Invites only":
                    save_leagues.invited_code = invited_code 
                cleaned_others_fees = {k: v for k, v in others_fees.items() if k and v is not None}
                save_leagues.others_fees = cleaned_others_fees
                save_leagues.save() 
                
                # if lat is not None and long is not None:
                save_leagues.latitude=latitude
                save_leagues.longitude=longitude
                save_leagues.save()
                if start_rank and end_rank:
                    save_leagues.any_rank = False
                    save_leagues.start_rank = start_rank
                    save_leagues.end_rank = end_rank
                    save_leagues.save()
                counter = counter+1
                if check_leagues.exists() and check_person.exists():
                    check_leagues_id = check_leagues.first().id
                    check_person_id = check_person.first().id
                    save_leagues.team_type_id = check_leagues_id
                    save_leagues.team_person_id = check_person_id
                    save_leagues.save()
                leagues_id.append(save_leagues.id)
                
            result = []
            for dat in leagues_id:
                main_data = Leagues.objects.filter(id=dat)
                tournament_play_type = play_type
                data_structure = [{"name": "Round Robin", "number_of_courts": 0, "sets": 0, "point": 0},
                          {"name": "Elimination", "number_of_courts": 0, "sets": 0, "point": 0},
                          {"name": "Final", "number_of_courts": 0, "sets": 0, "point": 0}]
                for se in data_structure:
                    if tournament_play_type == "Group Stage":
                        se["is_show"] = True
                    elif tournament_play_type == "Round Robin": 
                        if se["name"] == "Round Robin":
                            se["is_show"] = True
                        else:
                            se["is_show"] = False
                    elif tournament_play_type == "Single Elimination":
                        if se["name"] != "Round Robin":
                            se["is_show"] = True
                        else:
                            se["is_show"] = False
                    elif tournament_play_type == "Individual Match Play":
                        if se["name"] == "Final":
                            se["is_show"] = True
                        else:
                            se["is_show"] = False 
                pt = LeaguesPlayType.objects.create(type_name=save_leagues.play_type,league_for=main_data.first(),data=data_structure)
                main_data = main_data.values()
                for i in main_data:
                    i["team_type"] = LeaguesTeamType.objects.filter(id = i["team_type_id"]).first().name
                    i["team_person"] = LeaguesPesrsonType.objects.filter(id = i["team_person_id"]).first().name
                    user_first_name = check_user.first().first_name
                    user_last_name = check_user.first().last_name
                    i["created_by"] = f"{user_first_name} {user_last_name}"
                    i["play_type_data"] = list(LeaguesPlayType.objects.filter(id=pt.id).values())
                    del i ["team_person_id"]
                    del i ["team_type_id"]
                    del i ["created_by_id"]
                result.append(main_data[0])
            message = ""
            if len(mesage_box) != 0:
                for ij in mesage_box:
                    if message == "":
                        message = message+ij
                    else:
                        message = message + "," +ij
                if len(mesage_box) == 1:
                    set_msg = f"{message} tournament already exists"
                elif len(mesage_box) > 1:
                    set_msg = f"{message} tournaments already exist"
            else:
                set_msg = "Tournament created successfully"
            data["status"], data["data"],data["message"] = status.HTTP_200_OK, result, set_msg
        else:
            data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "User not found."
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


@api_view(('POST',))
def create_play_type_details(request):
    data = {'status':'','data':[],'message':''}
    try:        
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        total_data = request.data.get('data')
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        if check_user.exists() and check_user.first().is_admin or check_user.first().is_organizer:
            my_result = []
            # print(len(total_data))
            for fo in total_data:
                l_uuid = fo["l_uuid"]
                l_secret_key = fo["l_secret_key"]
                get_data = fo["data"]
                Leagues_check = Leagues.objects.filter(uuid=l_uuid, secret_key=l_secret_key)
                if Leagues_check.exists:
                    pt = LeaguesPlayType.objects.filter(league_for=Leagues_check.first())
                    pt_update = pt.update(data=get_data)
                    #league_data
                    league_data = Leagues_check.values()
                    # print(league_data)
                    for i in league_data:
                        i["team_type"] = LeaguesTeamType.objects.filter(id = i["team_type_id"]).first().name
                        i["team_person"] = LeaguesPesrsonType.objects.filter(id = i["team_person_id"]).first().name
                        user_first_name = check_user.first().first_name
                        user_last_name = check_user.first().last_name
                        i["created_by"] = f"{user_first_name} {user_last_name}"
                        i["play_type_data"] = list(LeaguesPlayType.objects.filter(id=pt.first().id).values())
                        del i ["team_person_id"]
                        del i ["team_type_id"]
                        del i ["created_by_id"]
                    # print(league_data[0])
                    my_result.append(league_data[0])
                else:
                    my_result.append({"error":"League not found"})
            data["status"],data["data"], data["message"] = status.HTTP_200_OK,my_result,"Created playtype successfully"
        else:
            data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "User not found."
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)

#new12
@api_view(('POST',))
def create_open_play_tournament(request):
    data = {'status': '', 'message': ''}
    try:        
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        leagues_start_date = request.data.get('leagues_start_date')
        location = request.data.get('location')
        play_type = request.data.get('play_type')
        team_type = "Open-team"
        team_person = request.data.get('team_person')
        team_id_list = request.data.get('team_id_list')
        team_id_list = json.loads(team_id_list)
        
        court = request.data.get('court')
        sets = request.data.get('sets')
        points = request.data.get('points')
        
        max_number_team = 2
        registration_fee = 0
        description = "None"
        league_type = "Open to all"

        if len(team_id_list) != 2:
            data["status"], data["message"] = status.HTTP_400_BAD_REQUEST, "Max number of team is Two"
            return Response(data)
        
        team_1_id = team_id_list[0]
        team_2_id = team_id_list[1]
        team1_players = list(Player.objects.filter(team__id=team_1_id).values_list("id", flat=True))
        team2_players = list(Player.objects.filter(team__id=team_2_id).values_list("id", flat=True))
        for player_id in team1_players:
            if player_id in team2_players:
                data["status"], data["message"] = status.HTTP_400_BAD_REQUEST, "Same player cannot be in both teams."
                return Response(data)

        leagues_start_date = datetime.strptime(leagues_start_date, '%m/%d/%Y').strftime('%Y-%m-%d')
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        counter = 0
        team_names = {}
        for team in team_id_list:
            counter += 1
            team_instance = Team.objects.filter(id=team).first()
            team_names[f'team{counter}_name'] = team_instance.name
        tournament_name = f"{team_names['team1_name']} VS {team_names['team2_name']}"
        if check_user.exists():
            check_leagues = LeaguesTeamType.objects.filter(name=team_type)
            check_person = LeaguesPesrsonType.objects.filter(name=team_person)
            full_address = location
            api_key = settings.MAP_API_KEY
            state, country, pincode, latitude, longitude = get_address_details(full_address, api_key)
            if latitude is None:
                latitude = 38.908683
            if longitude is None:
                longitude = -76.937352
            obj = GenerateKey()
            secret_key = obj.gen_leagues_key()

            save_leagues = Leagues(
                secret_key=secret_key,
                name=tournament_name,
                leagues_start_date=leagues_start_date,
                location=location,
                created_by_id=check_user.first().id,
                street=state,
                city="Extract city from full_address",
                state=state,
                postal_code=pincode,
                country=country,
                max_number_team=max_number_team,
                play_type=play_type,
                registration_fee=registration_fee,
                description=description,
                league_type=league_type
            )

            save_leagues.save()

            save_leagues.latitude = latitude
            save_leagues.longitude = longitude
            save_leagues.save()
            if check_leagues.exists() and check_person.exists():
                check_leagues_id = check_leagues.first().id
                check_person_id = check_person.first().id
                save_leagues.team_type_id = check_leagues_id
                save_leagues.team_person_id = check_person_id
                save_leagues.save()

            for team in team_id_list:
                team_instance = Team.objects.filter(id=team).first()
                save_leagues.registered_team.add(team_instance)

            if not court:
                court = 0
            else:
                court = int(court)

            if not sets:
                sets = 0
            else:
                sets = int(sets)

            if not points:
                points = 0
            else:
                points = int(points)

            play_type_data = [{"name": "Round Robin", "number_of_courts": 0, "sets": 0, "point": 0},
                              {"name": "Elimination", "number_of_courts": 0, "sets": 0, "point": 0},
                              {"name": "Final", "number_of_courts": court, "sets": sets, "point": points}]
            for j in play_type_data:
                if play_type == "Individual Match Play":
                    j["is_show"] = True
                else:
                    j["is_show"] = False
            LeaguesPlayType.objects.create(type_name=save_leagues.play_type, league_for=save_leagues,
                                           data=play_type_data)
            #notification           
            for team_id in team_id_list:
                team_instance = Team.objects.filter(id=team_id).first()
                titel = "Open play created."
                notify_message = f"Hey player! Your team {team_instance.name} has been added for an open play - {tournament_name}"
                players = Player.objects.filter(team=team_instance)
                for player in players:
                    notify_edited_player(player.player.id, titel, notify_message)

            set_msg = "Tournament created successfully"
            data["status"], data["message"] = status.HTTP_200_OK, set_msg
        else:
            data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "User not found."
    except Exception as e:
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


@api_view(('GET',))
def view_match_result(request):
    data = {'status': '', 'data': [], 'message': '','set':''}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        tournament_uuid = request.data.get('tournament_uuid')
        tournament_secret_key = request.data.get('tournament_secret_key')
        

        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        check_tournament = Tournament.objects.filter(uuid=tournament_uuid, secret_key=tournament_secret_key)
        
        if check_user.exists() and check_tournament.exists():
            tournament = check_tournament.first()
            data = TournamentSetsResult.objects.filter(tournament=tournament).values()
            data["set"] = LeaguesPlayType.objects.filter(league_for=tournament.leagues).first().data
            data["data"] = data
            data["status"], data["message"] = status.HTTP_200_OK, "view the match score"
        else:
            data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "User or League not found."
    except Exception as e:
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, str(e)
    
    return Response(data)

#updated
@api_view(('GET',))
def view_leagues_for_edit(request):
    data = {
            'status': '',
            'is_organizer': False,
            'data': [],
            'tournament_details': [],
            'message': ''
        }
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        league_uuid = request.GET.get('league_uuid')
        league_secret_key = request.GET.get('league_secret_key')

        # Use get_object_or_404 to simplify the existence check
        user = get_object_or_404(User, uuid=user_uuid, secret_key=user_secret_key)
        league = get_object_or_404(Leagues, uuid=league_uuid, secret_key=league_secret_key)

        if user.is_organizer:
            data['is_organizer'] = True

        leagues = Leagues.objects.filter(uuid=league_uuid, secret_key=league_secret_key).values(
            'uuid', 'secret_key', 'name', 'location', 'leagues_start_date', 'leagues_end_date',
            'registration_start_date', 'registration_end_date', 'team_type__name', 'team_person__name',
            "street", "city", "state", "postal_code", "country", "complete_address", "latitude", "longitude",
            "play_type", "registration_fee", "description", "image", "others_fees", "league_type"
        )

        t_details = LeaguesPlayType.objects.filter(league_for=league).values()
        tournament_play_type = league.play_type

        data_structure = [{"name": "Round Robin", "number_of_courts": 0, "sets": 0, "point": 0},
                          {"name": "Elimination", "number_of_courts": 0, "sets": 0, "point": 0},
                          {"name": "Final", "number_of_courts": 0, "sets": 0, "point": 0}]

        for t in t_details:
            if not t["data"]:
                t["data"] = data_structure
            else:
                data_structure = t["data"]

            for se in data_structure:
                if tournament_play_type == "Group Stage":
                    se["is_show"] = True
                elif tournament_play_type == "Round Robin": 
                    if se["name"] == "Round Robin":
                        se["is_show"] = True
                    else:
                        se["is_show"] = False
                elif tournament_play_type == "Single Elimination":
                    if se["name"] != "Round Robin":
                        se["is_show"] = True
                    else:
                        se["is_show"] = False
                elif tournament_play_type == "Individual Match Play":
                    if se["name"] == "Final":
                        se["is_show"] = True
                    else:
                        se["is_show"] = False 

            t["data"] = data_structure

        data['tournament_details'] = t_details
        data['data'] = leagues
        data['status'] = status.HTTP_200_OK
        data['message'] = "Data Found"

    except Exception as e:
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, str(e)

    return Response(data)


@api_view(('POST',))
def edit_leagues(request):
    data = {'status':'','message':''}
    try:        
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        league_uuid = request.data.get('league_uuid')
        league_secret_key = request.data.get('league_secret_key')
        total_data = request.data.get('data')
        data_list = json.loads(total_data)
        
        
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        check_league  = Leagues.objects.filter(uuid=league_uuid,secret_key=league_secret_key)
        if check_user.exists() and check_league.exists():
            get_tornament = check_league.first()
            get_user = check_user.first()
            if get_tornament.created_by==get_user:
                check_play_type = LeaguesPlayType.objects.filter(league_for = get_tornament)
                if check_play_type.exists():
                    for i in data_list:
                        if not i["number_of_courts"]:
                            i["number_of_courts"] = int(i["number_of_courts"])
                        if not i["sets"]:
                            i["sets"] = int(i["sets"])
                        if not i["point"]:
                            i["point"] = int(i["point"])
                    check_play_type.update(data=data_list)
                else:
                    LeaguesPlayType.objects.create(play_type=get_tornament.play_type,league_for = get_tornament,data=data_list)
                data["status"], data["message"] = status.HTTP_200_OK, "League updated successfully"
            else:
                data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "This is not your league."
        else:
            data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "User or League not found"
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)

#new
# @api_view(('POST',))
# def set_tournamens_result(request):
#     data = {'status': '', 'data': [], 'message': ''}
#     try:
#         user_uuid = request.data.get('user_uuid')
#         user_secret_key = request.data.get('user_secret_key')
#         league_uuid = request.data.get('league_uuid')
#         league_secret_key = request.data.get('league_secret_key')
#         tournament_uuid = request.data.get('tournament_uuid')
#         tournament_secret_key = request.data.get('tournament_secret_key')
#         team1_point = request.data.get('team1_point')
#         team2_point = request.data.get('team2_point')
#         set_number = request.data.get('set_number')
        
#         check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
#         check_leagues = Leagues.objects.filter(uuid=league_uuid, secret_key=league_secret_key)
#         tournament = Tournament.objects.filter(uuid=tournament_uuid, secret_key=tournament_secret_key, leagues=check_leagues.first())
        
#         if check_user.exists() and check_leagues.exists() and tournament.exists():
#             league = check_leagues.first()
#             tournament_obj = tournament.first()
#             get_user = check_user.first()

#             team1_point_list = team1_point.split(",")
#             team2_point_list = team2_point.split(",")
#             set_number_list = set_number.split(",")
#             t_sets = tournament_obj.set_number
#             org_list = list(league.add_organizer.all().values_list("id", flat=True))
#             team1_p_list = list(Player.objects.filter(team__id = tournament_obj.team1.id).values_list("player_id", flat=True))
#             team2_p_list = list(Player.objects.filter(team__id = tournament_obj.team2.id).values_list("player_id", flat=True))
#             if(tournament_obj.team1.created_by == get_user) or (tournament_obj.team2.created_by == get_user) or (league.created_by == get_user) or (get_user.id in org_list) or (get_user.id in team1_p_list) or (get_user.id in team2_p_list):
#                 if int(t_sets) == len(team1_point_list):
#                     te1_win=[]
#                     te2_win=[]
#                     for up_ in range(len(team1_point_list)):
#                         set_num = up_ + 1
#                         team1_point = team1_point_list[up_]
#                         team2_point = team2_point_list[up_]
#                         if int(team1_point) >= int(team2_point):
#                             winner = tournament_obj.team1
#                             te1_win.append(True)
#                             te2_win.append(False)
#                         else:
#                             te1_win.append(False)
#                             te2_win.append(True)
#                             winner = tournament_obj.team2
#                         check_score = TournamentSetsResult.objects.filter(tournament=tournament_obj, set_number=set_num)
#                         check_status_score = False
#                         if ((tournament_obj.team1.created_by == get_user) or (tournament_obj.team2.created_by == get_user) or (get_user.id in team1_p_list) or (get_user.id in team2_p_list)) and (league.created_by != get_user) and (get_user.id not in org_list):
#                             if check_score.exists():
#                                 if check_score.first().is_completed:
#                                     data["status"], data["message"] = status.HTTP_200_OK, "The Score is already updated"
#                                     return Response(data)
#                                 else:
#                                     check_score.update(team1_point=team1_point, team2_point=team2_point)
#                             else:
#                                 TournamentSetsResult.objects.create(tournament=tournament_obj, set_number=set_num, team1_point=team1_point, team2_point=team2_point)
#                         elif (league.created_by == get_user) or (get_user.id in org_list):
#                             if check_score.exists():
#                                 check_score.update(team1_point=team1_point, team2_point=team2_point,is_completed=True,win_team=winner)
#                             else:
#                                 TournamentSetsResult.objects.create(tournament=tournament_obj, set_number=set_num, team1_point=team1_point, team2_point=team2_point,is_completed=True,win_team=winner)
#                             check_status_score = True
#                     # calculate match win status
#                     te1_wins = sum(1 for result in te1_win if result)
#                     te2_wins = sum(1 for result in te2_win if result)
#                     is_drow = False
#                     # print(te1_wins,te2_wins,is_drow)
#                     if te1_wins > te2_wins:
#                         winner = tournament_obj.team1
#                         looser = tournament_obj.team2
#                     elif te2_wins > te1_wins:
#                         winner = tournament_obj.team2
#                         looser = tournament_obj.team1
#                     else:
#                         winner = None
#                         looser = None
#                         is_drow = True
#                     tournament_obj.winner_team = winner
#                     tournament_obj.loser_team = looser
#                     if is_drow is True:
#                         tournament_obj.is_drow = True
#                         tournament_obj.winner_team_score = 1
#                         tournament_obj.loser_team_score = 1
#                     else:
#                         tournament_obj.winner_team_score = 3
#                         tournament_obj.loser_team_score = 0

#                     #for notification
#                     title = "Match score update"
#                     if winner is not None and looser is not None:
#                         if check_status_score is False:
                            
#                             message = f"Your Match {tournament_obj.match_number} scores are all updated, awaiting approval"
#                             message2 = f"Your Match {tournament_obj.match_number} scores are all updated, awaiting approval"
#                         if check_status_score is True:
#                             message = f"Wow, you have won the match {tournament_obj.match_number}, the scores are approved"
#                             message2 = f"Sorry, you have lost the match {tournament_obj.match_number}, the scores are approved"
                        
#                         winner_player = Player.objects.filter(team__id=winner.id)
#                         if winner_player.exists():
#                             for pl in winner_player:
#                                 user_id = pl.player.id
#                                 notify_edited_player(user_id, title, message)
#                         looser_player = Player.objects.filter(team__id=looser.id)
                        
#                         if looser_player.exists():
#                             for pl in looser_player:
#                                 user_id = pl.player.id
#                                 notify_edited_player(user_id, title, message2)
#                     else:
#                         if check_status_score is False:
#                             message = f"Your match {tournament_obj.match_number} scores are all updated, awaiting approval"
#                             # message2 = f"Your match number {tournament_obj.match_number} score is updated, after checking the organizer status will updated"
#                         if check_status_score is True:
#                             message = f"The match {tournament_obj.match_number} was drawn, the scores are approved"

#                         team_1_ins = tournament_obj.team1
#                         team_2_ins = tournament_obj.team2
#                         team_one_player_list = Player.objects.filter(team__id = team_1_ins.id)
#                         team_two_player_list = Player.objects.filter(team__id = team_2_ins.id)
#                         for pl1 in team_one_player_list:
#                             user_id = pl1.player.id
#                             notify_edited_player(user_id, title, message) 
#                         for pl2 in team_two_player_list:
#                             user_id = pl2.player.id
#                             notify_edited_player(user_id, title, message) 
#                     org_list.append(league.created_by.id)
#                     if check_status_score is False:
#                         title = "Matchs score update" 
#                         message = f"Your Match {tournament_obj.match_number} scores are all updated, please give the approval"
#                         for us in  org_list:
#                             user_id = int(us)
#                             notify_edited_player(user_id, title, message)
#                     # notification end

#                     tournament_obj.is_completed = check_status_score
#                     tournament_obj.save()
#                 else:
#                     for up_ in range(len(team1_point_list)):
#                         set_num = up_ + 1
#                         team1_point = team1_point_list[up_]
#                         team2_point = team2_point_list[up_]
#                         if int(team1_point) >= int(team2_point):
#                             winner = tournament_obj.team1
#                         else:
#                             winner = tournament_obj.team2
#                         check_score = TournamentSetsResult.objects.filter(tournament=tournament_obj, set_number=set_num)
#                         check_status_score = False
#                         if ((tournament_obj.team1.created_by == get_user) or (tournament_obj.team2.created_by == get_user) or (get_user.id in team1_p_list) or (get_user.id in team2_p_list)) and (league.created_by != get_user) and (get_user.id not in org_list):
#                             if check_score.exists():
#                                 if check_score.first().is_completed:
#                                     data["status"], data["message"] = status.HTTP_200_OK, "The Score is already updated"
#                                     return Response(data)
#                                 else:
#                                     check_score.update(team1_point=team1_point, team2_point=team2_point)
#                             else:
#                                 TournamentSetsResult.objects.create(tournament=tournament_obj, set_number=set_num, team1_point=team1_point, team2_point=team2_point)
#                         elif (league.created_by == get_user) or (get_user.id in org_list):
#                             if check_score.exists():
#                                 check_score.update(team1_point=team1_point, team2_point=team2_point,is_completed=True,win_team=winner)
#                             else:
#                                 TournamentSetsResult.objects.create(tournament=tournament_obj, set_number=set_num, team1_point=team1_point, team2_point=team2_point,is_completed=True,win_team=winner)
#                             check_status_score = True
#                     #for notification
#                     if check_status_score is False:
#                         message = f"Scores in Match {tournament_obj.match_number} are placed. Subjected to approval."
#                     elif check_status_score is True:
#                         message = f"Scores in Match {tournament_obj.match_number} are placed"
#                     title = "Match score update"
#                     team_1_ins = tournament_obj.team1
#                     team_2_ins = tournament_obj.team2
#                     team_one_player_list = Player.objects.filter(team__id = team_1_ins.id)
#                     team_two_player_list = Player.objects.filter(team__id = team_2_ins.id)
#                     for pl1 in team_one_player_list:
#                         user_id = pl1.player.id
#                         notify_edited_player(user_id, title, message) 
#                     for pl2 in team_two_player_list:
#                         user_id = pl2.player.id
#                         message = f"Scores in Match {tournament_obj.match_number} are placed. Subjected to approval."
#                         notify_edited_player(user_id, title, message) 
                    
#                     org_list.append(league.created_by.id)
#                     if check_status_score is False:
#                         title = "Matchs score update" 
#                         message = f"Your Match {tournament_obj.match_number} scores are all updated, please give the approval"
#                         for us in  org_list:
#                             user_id = int(us)
#                             notify_edited_player(user_id, title, message)
                    
#                     # notification end
#                 data["status"], data["message"] = status.HTTP_200_OK, "Your set's score is Updated"
#             else:
#                 data["status"], data["message"] = status.HTTP_200_OK, "You can't update the score"
#         else:
#             data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "User or Tournament not found."
#     except Exception as e:
#         data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, str(e)
#     return Response(data)

#updated
@api_view(('POST',))
def set_tournamens_result(request):
    data = {'status': '', 'data': [], 'message': ''}
    try:        
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        league_uuid = request.data.get('league_uuid')
        league_secret_key = request.data.get('league_secret_key')
        tournament_uuid = request.data.get('tournament_uuid')
        tournament_secret_key = request.data.get('tournament_secret_key')
        team1_point = request.data.get('team1_point')
        team2_point = request.data.get('team2_point')
        set_number = request.data.get('set_number')
        
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        check_leagues = Leagues.objects.filter(uuid=league_uuid, secret_key=league_secret_key)
        tournament = Tournament.objects.filter(uuid=tournament_uuid, secret_key=tournament_secret_key, leagues=check_leagues.first())
        
        if check_user.exists() and check_leagues.exists() and tournament.exists():
            league = check_leagues.first()
            tournament_obj = tournament.first()
            get_user = check_user.first()

            team1_point_list = team1_point.split(",")
            team2_point_list = team2_point.split(",")
            set_number_list = set_number.split(",")
            t_sets = tournament_obj.set_number

            org_list = list(league.add_organizer.all().values_list("id", flat=True))
            team1_p_list = list(Player.objects.filter(team__id = tournament_obj.team1.id).values_list("player_id", flat=True))
            team2_p_list = list(Player.objects.filter(team__id = tournament_obj.team2.id).values_list("player_id", flat=True))

            check_reported_score = TournamentScoreReport.objects.filter(tournament=tournament_obj, status="Pending")

            if check_reported_score.exists():
                if get_user.id in org_list:
                    check_reported_score.update(status="Resolved")
                    check_approve = TournamentScoreApproval.objects.filter(tournament=tournament_obj)
                    if check_approve.exists():
                        check_approve.update(team1_approval=True, team2_approval=True)
                    else:
                        TournamentScoreApproval.objects.create(tournament=tournament_obj, team1_approval=True, team2_approval=True)

                    te1_win=[]
                    te2_win=[]
                    for up_ in range(len(team1_point_list)):
                        set_num = up_ + 1
                        team1_point = team1_point_list[up_]
                        team2_point = team2_point_list[up_]
                        if int(team1_point) >= int(team2_point):
                            winner = tournament_obj.team1
                            te1_win.append(True)
                            te2_win.append(False)
                        else:
                            te1_win.append(False)
                            te2_win.append(True)
                            winner = tournament_obj.team2
                        check_score = TournamentSetsResult.objects.filter(tournament=tournament_obj, set_number=set_num)
                        check_score.update(team1_point=team1_point, team2_point=team2_point)

                    # calculate match win status
                    te1_wins = sum(1 for result in te1_win if result)
                    te2_wins = sum(1 for result in te2_win if result)
                    is_drow = False
                    # print(te1_wins,te2_wins,is_drow)
                    if te1_wins > te2_wins:
                        winner = tournament_obj.team1
                        looser = tournament_obj.team2
                    elif te2_wins > te1_wins:
                        winner = tournament_obj.team2
                        looser = tournament_obj.team1
                    else:
                        winner = None
                        looser = None
                        is_drow = True
                    tournament_obj.winner_team = winner
                    tournament_obj.loser_team = looser
                    if is_drow is True:
                        tournament_obj.is_drow = True
                        tournament_obj.winner_team_score = 1
                        tournament_obj.loser_team_score = 1
                    else:
                        tournament_obj.winner_team_score = 3
                        tournament_obj.loser_team_score = 0

                    tournament_obj.is_completed = True
                    tournament_obj.save()

                    #for notification
                    title = "Match score update"
                    if winner is not None and looser is not None:                            
                        message = f"Wow, you have won the match {tournament_obj.match_number}, the scores are approved"
                        message2 = f"Sorry, you have lost the match {tournament_obj.match_number}, the scores are approved"
                        
                        winner_player = list(Player.objects.filter(team__id=winner.id).values_list("player_id", flat=True))
                        
                        if len(winner_player) > 0:
                            winner_player.append(tournament_obj.winner_team.created_by.id)
                            for user_id in winner_player:                                
                                notify_edited_player(user_id, title, message)
                                
                        looser_player = list(Player.objects.filter(team__id=looser.id).values_list("player_id", flat=True))                      
                        if len(looser_player) > 0:
                            looser_player.append(tournament_obj.loser_team.created_by.id)
                            for user_id in looser_player:                                
                                notify_edited_player(user_id, title, message2)
                    else:                            
                        message = f"The match {tournament_obj.match_number} was drawn, the scores are approved"
                        team_1_ins = tournament_obj.team1
                        team_2_ins = tournament_obj.team2
                        team_one_player_list = Player.objects.filter(team__id = team_1_ins.id)
                        team_two_player_list = Player.objects.filter(team__id = team_2_ins.id)

                        for pl1 in team_one_player_list:
                            user_id = pl1.player.id
                            notify_edited_player(user_id, title, message) 
                        for pl2 in team_two_player_list:
                            user_id = pl2.player.id
                            notify_edited_player(user_id, title, message)

                    data["status"], data["message"] = status.HTTP_200_OK, "Your set's score is Updated"
                else:
                    data["status"], data["message"] = status.HTTP_200_OK, "You can't update the score"
            else:
                if (tournament_obj.team1.created_by == get_user) or (tournament_obj.team2.created_by == get_user) or (get_user.id in team1_p_list) or (get_user.id in team2_p_list):
                    if int(t_sets) == len(team1_point_list):
                        te1_win=[]
                        te2_win=[]
                        for up_ in range(len(team1_point_list)):
                            set_num = up_ + 1
                            team1_point = team1_point_list[up_]
                            team2_point = team2_point_list[up_]
                            if int(team1_point) >= int(team2_point):
                                winner = tournament_obj.team1
                                te1_win.append(True)
                                te2_win.append(False)
                            else:
                                te1_win.append(False)
                                te2_win.append(True)
                                winner = tournament_obj.team2
                            check_score = TournamentSetsResult.objects.filter(tournament=tournament_obj, set_number=set_num)
                            
                            if ((tournament_obj.team1.created_by == get_user) or (tournament_obj.team2.created_by == get_user) or (get_user.id in team1_p_list) or (get_user.id in team2_p_list)):
                                if check_score.exists():
                                    if check_score.first().is_completed:
                                        data["status"], data["message"] = status.HTTP_200_OK, "The Score is already updated"
                                        return Response(data)
                                    else:
                                        check_score.update(team1_point=team1_point, team2_point=team2_point)
                                else:
                                    TournamentSetsResult.objects.create(tournament=tournament_obj, set_number=set_num, team1_point=team1_point, team2_point=team2_point)

                                # Send notification to opposite team for approval.    
                                message = f"Your Match {tournament_obj.match_number} scores are all updated. You can approve or report them."
                                if ((tournament_obj.team1.created_by == get_user) or (get_user.id in team1_p_list)):
                                    notify_users = team2_p_list
                                    notify_users.append(tournament_obj.team2.created_by.id)
                                else:
                                    notify_users = team1_p_list
                                    notify_users.append(tournament_obj.team1.created_by.id)
                                
                                title = "Match score update"
                                for user_id in notify_users:
                                    notify_edited_player(user_id, title, message)

                        # calculate match win status
                        te1_wins = sum(1 for result in te1_win if result)
                        te2_wins = sum(1 for result in te2_win if result)
                        is_drow = False
                        # print(te1_wins,te2_wins,is_drow)
                        if te1_wins > te2_wins:
                            winner = tournament_obj.team1
                            looser = tournament_obj.team2
                        elif te2_wins > te1_wins:
                            winner = tournament_obj.team2
                            looser = tournament_obj.team1
                        else:
                            winner = None
                            looser = None
                            is_drow = True
                        tournament_obj.winner_team = winner
                        tournament_obj.loser_team = looser
                        if is_drow is True:
                            tournament_obj.is_drow = True
                            tournament_obj.winner_team_score = 1
                            tournament_obj.loser_team_score = 1
                        else:
                            tournament_obj.winner_team_score = 3
                            tournament_obj.loser_team_score = 0                  

                        tournament_obj.save()
                    else:
                        for up_ in range(len(team1_point_list)):
                            set_num = up_ + 1
                            team1_point = team1_point_list[up_]
                            team2_point = team2_point_list[up_]
                            if int(team1_point) >= int(team2_point):
                                winner = tournament_obj.team1
                            else:
                                winner = tournament_obj.team2
                            check_score = TournamentSetsResult.objects.filter(tournament=tournament_obj, set_number=set_num)
                            
                            if ((tournament_obj.team1.created_by == get_user) or (tournament_obj.team2.created_by == get_user) or (get_user.id in team1_p_list) or (get_user.id in team2_p_list)):
                                if check_score.exists():
                                    if check_score.first().is_completed:
                                        data["status"], data["message"] = status.HTTP_200_OK, "The Score is already updated"
                                        return Response(data)
                                    else:
                                        check_score.update(team1_point=team1_point, team2_point=team2_point)
                                else:
                                    TournamentSetsResult.objects.create(tournament=tournament_obj, set_number=set_num, team1_point=team1_point, team2_point=team2_point)
                                
                                # Send notification.    
                                message = f"Scores of match {tournament_obj.match_number} are placed."
                                if ((tournament_obj.team1.created_by == get_user) or (get_user.id in team1_p_list)):
                                    notify_users = team2_p_list
                                    notify_users.append(tournament_obj.team2.created_by.id)
                                else:
                                    notify_users = team1_p_list
                                    notify_users.append(tournament_obj.team1.created_by.id)
                                
                                title = "Match score update"
                                for user_id in notify_users:
                                    notify_edited_player(user_id, title, message)                        
                        
                    data["status"], data["message"] = status.HTTP_200_OK, "Your set's score is Updated"
                else:
                    data["status"], data["message"] = status.HTTP_200_OK, "You can't update the score"
        else:
            data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "User or Tournament not found."
    except Exception as e:
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, str(e)
    return Response(data)


@api_view(('POST',))
def approve_set_tournament_result(request):
    data = {'status': '', 'data': [], 'message': ''}
    try:
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        league_uuid = request.data.get('league_uuid')
        league_secret_key = request.data.get('league_secret_key')
        tournament_uuid = request.data.get('tournament_uuid')
        tournament_secret_key = request.data.get('tournament_secret_key')    

        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        check_leagues = Leagues.objects.filter(uuid=league_uuid, secret_key=league_secret_key)
        tournament = Tournament.objects.filter(uuid=tournament_uuid, secret_key=tournament_secret_key, leagues=check_leagues.first())
        
        if check_user.exists() and check_leagues.exists() and tournament.exists():
            league = check_leagues.first()
            tournament_obj = tournament.first()
            get_user = check_user.first()

            team1_p_list = list(Player.objects.filter(team__id = tournament_obj.team1.id).values_list("player_id", flat=True))
            team2_p_list = list(Player.objects.filter(team__id = tournament_obj.team2.id).values_list("player_id", flat=True))

            if (tournament_obj.team1.created_by == get_user) or (tournament_obj.team2.created_by == get_user) or (get_user.id in team1_p_list) or (get_user.id in team2_p_list):
                check_approval = TournamentScoreApproval.objects.filter(tournament=tournament_obj)
                if check_approval.exists():
                    if (tournament_obj.team1.created_by == get_user) or (get_user.id in team1_p_list):
                        check_approval.update(team1_approval = True)                        
                    else:
                        check_approval.update(team2_approval = True)
                    
                    tournament_obj.is_completed = True
                    tournament_obj.save()

                    #for notification                  

                    title = "Match score update"
                    if not tournament_obj.is_drow:                            
                        message = f"Wow, you have won the match {tournament_obj.match_number}, the scores are approved"
                        message2 = f"Sorry, you have lost the match {tournament_obj.match_number}, the scores are approved"
                        
                        winner_player = list(Player.objects.filter(team__id=tournament_obj.winner_team.id).values_list("player_id", flat=True))
                        if len(winner_player) > 0:
                            winner_player.append(tournament_obj.winner_team.created_by.id)
                            for user_id in winner_player:                            
                                notify_edited_player(user_id, title, message)
                                
                        looser_player = list(Player.objects.filter(team__id=tournament_obj.loser_team.id).values_list("player_id", flat=True))
                        
                        if len(looser_player) > 0:
                            looser_player.append(tournament_obj.loser_team.created_by.id)
                            for user_id in looser_player:                                
                                notify_edited_player(user_id, title, message2)
                    else:                            
                        message = f"The match {tournament_obj.match_number} was drawn, the scores are approved"                        
                        team_one_player_list = list(Player.objects.filter(team__id = tournament_obj.team1.id).values_list("player_id", flat=True))
                        team_two_player_list = list(Player.objects.filter(team__id = tournament_obj.team2.id).values_list("player_id", flat=True))

                        team_one_player_list.append(tournament_obj.team1.created_by.id)
                        for user_id in team_one_player_list:                            
                            notify_edited_player(user_id, title, message) 

                        team_two_player_list.append(tournament_obj.team2.created_by.id)
                        for user_id in team_two_player_list:
                            notify_edited_player(user_id, title, message) 
                else:
                    if (tournament_obj.team1.created_by == get_user) or (get_user.id in team1_p_list):
                        TournamentScoreApproval.objects.create(tournament=tournament_obj, team1_approval = True)                        
                    else:
                        TournamentScoreApproval.objects.create(tournament=tournament_obj, team1_approval = True)

                data["status"], data["message"] = status.HTTP_200_OK, f"The scores of the match {tournament_obj.match_number} has been successfully approved."     
            else:
                data["status"], data["message"] = status.HTTP_200_OK, "You can't approve the score"
        else:
            data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "User or Tournament not found."

    except Exception as e:
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, str(e)
    return Response(data)


@api_view(('POST',))
def report_set_tournament_result(request):
    data = {'status': '', 'data': [], 'message': ''}
    try:
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        league_uuid = request.data.get('league_uuid')
        league_secret_key = request.data.get('league_secret_key')
        tournament_uuid = request.data.get('tournament_uuid')
        tournament_secret_key = request.data.get('tournament_secret_key')  

        report_text = request.data.get('report_text') 

        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        check_leagues = Leagues.objects.filter(uuid=league_uuid, secret_key=league_secret_key)
        tournament = Tournament.objects.filter(uuid=tournament_uuid, secret_key=tournament_secret_key, leagues=check_leagues.first())
        
        if check_user.exists() and check_leagues.exists() and tournament.exists():
            league = check_leagues.first()
            tournament_obj = tournament.first()
            get_user = check_user.first()
            team1_p_list = list(Player.objects.filter(team__id = tournament_obj.team1.id).values_list("player_id", flat=True))
            team2_p_list = list(Player.objects.filter(team__id = tournament_obj.team2.id).values_list("player_id", flat=True))

            if (tournament_obj.team1.created_by == get_user) or (tournament_obj.team2.created_by == get_user) or (get_user.id in team1_p_list) or (get_user.id in team2_p_list):
                TournamentScoreReport.objects.create(tournament=tournament_obj, text=report_text, created_by=get_user,status="Pending")

                #Notification for organizer
                org_list = list(league.add_organizer.all().values_list("id", flat=True))
                title = "Match score update"
                message = f'{get_user.first_name} {get_user.last_name} has reported the scores of match {tournament_obj.match_number} of league {tournament_obj.leagues.name}. Please resolve this and update the score.'
                for user_id in org_list:
                    notify_edited_player(user_id, title, message)

                data["status"], data["message"] = status.HTTP_200_OK, f"You have successfully reported the scores of match {tournament_obj.match_number}"
            else:
                data["status"], data["message"] = status.HTTP_200_OK, "You can't report the score"
        else:
            data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "User or Tournament not found."

    except Exception as e:
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, str(e)
    return Response(data)

        
# autometic match assigne
def create_group(lst, num_parts):
    num_parts = int(num_parts)
    if num_parts <= 0:
        return "Number of parts should be greater than zero."

    random.shuffle(lst)

    # Calculate approximately how many elements each part should have
    avg_part_length = len(lst) // num_parts
    remainder = len(lst) % num_parts

    # Distribute the remainder among the first few parts
    parts_lengths = [avg_part_length + 1 if i < remainder else avg_part_length for i in range(num_parts)]

    # Generate the divided parts
    group_list = []
    start_index = 0
    for length in parts_lengths:
        group_list.append(lst[start_index:start_index+length])
        start_index += length

    return group_list


### completly updated
@api_view(('POST',))
def assigne_match(request):
    data = {'status': '', 'message': ''}
    user_uuid = request.data.get('user_uuid')
    user_secret_key = request.data.get('user_secret_key')
    league_uuid = request.data.get('league_uuid')
    league_secret_key = request.data.get('league_secret_key')
    check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
    check_leagues = Leagues.objects.filter(uuid=league_uuid, secret_key=league_secret_key)
    # print("check_user", check_user, "check_leagues", check_leagues)
    #if tournament found 

    if check_user.exists() and check_leagues.exists():
        league = check_leagues.first()
        playtype = league.play_type
        get_details = LeaguesPlayType.objects.filter(league_for=league).values("data")
        
        registered_teams = league.registered_team.all() if league else None
        team_details_list = [team.id for team in registered_teams] if registered_teams else []
        max_team = league.max_number_team
        if int(max_team) != len(team_details_list):
            data["status"],  data["message"] = status.HTTP_200_OK, f"All teams are not registered"
            return Response(data)
        
        #round rabin
        court_num_r = int(get_details[0]["data"][0]["number_of_courts"])
        set_num_r = int(get_details[0]["data"][0]["sets"])
        point_num_r = int(get_details[0]["data"][0]["point"])

        #elemination
        # if get_details[0]["data"][1]["number_of_courts"] == 0 or not get_details[0]["data"][1]["number_of_courts"]:
        court_num_e = int(get_details[0]["data"][1]["number_of_courts"])
        set_num_e = int(get_details[0]["data"][1]["sets"])
        point_num_e = int(get_details[0]["data"][1]["point"])


        #final
        court_num_f = int(get_details[0]["data"][2]["number_of_courts"])
        set_num_f = int(get_details[0]["data"][2]["sets"])
        point_num_f = int(get_details[0]["data"][2]["point"])

        # tournamnet start notification all team
        try:
            # If start the tournament
            #backup 
            if not Tournament.objects.filter(leagues = league).exists():
                league_name = league.name
                # send the notification
                all_team = league.registered_team.all().values_list("id", flat=True)
                for s_team in list(all_team):
                    team_manager_message = f"The tournament {league_name}, has started."
                    team_manager = Team.objects.filter(id=s_team).first().created_by
                    print(team_manager)
                    titel=f"Start Tournament"
                    notify_edited_player(team_manager.id, titel, team_manager_message)

                    # how many player in team and player details
                    player_in_team = Player.objects.filter(team__id = s_team)
                    for p in player_in_team:
                        message_s = f"Player, get ready! The tournament {league_name}, has started."
                        user = p.player
                        titel=f"Start Tournament"
                        notify_edited_player(user.id, titel, message_s)
        except:
            pass
        #done
        if playtype == "Single Elimination":
            register_team = league.registered_team.all().count()
            if league.max_number_team != register_team:
                data["status"], data["message"] = status.HTTP_200_OK, "All teams are not joined"
                return Response(data)
            
            check_pre_game =  Tournament.objects.filter(leagues=league)
            if check_pre_game.exists():
                check_leagues_com = check_pre_game.filter(is_completed=True)
                if len(check_pre_game) == len(check_leagues_com) and len(check_leagues_com) != 0:
                    pre_match_round = check_leagues_com.last().elimination_round
                    pre_round_details =  Tournament.objects.filter(leagues=league,elimination_round=pre_match_round)
                    teams = list(pre_round_details.values_list("winner_team_id", flat=True))
                    pre_match_number = check_leagues_com.last().match_number
                    court_num = 0
                    if len(teams) == 4:
                        sets__ = set_num_e
                        courts__ = court_num_e
                        points__ = point_num_e
                        match_type = "Semi Final"
                        round_number = 0
                        random.shuffle(teams)
                        match_number_now = pre_match_number
                        
                        for i in range(0, len(teams), 2):
                            team1 = teams[i]
                            team2 = teams[i + 1]
                            obj = GenerateKey()
                            secret_key = obj.generate_league_unique_id()
                            match_number_now = match_number_now + 1
                            court_num = court_num + 1
                            if courts__ <= court_num:
                                court_num = 1
                            Tournament.objects.create(set_number=sets__,court_num=court_num,points=points__,court_sn=court_num,match_number=match_number_now, secret_key=secret_key, leagues=league, team1_id=team1, team2_id=team2, match_type=match_type, elimination_round=round_number)
                        data["status"], data["message"] = status.HTTP_200_OK, f"Matches created for {match_type}"
                        return Response(data)   
                    elif len(teams) == 2:
                        sets__ = set_num_f
                        courts__ = court_num_f
                        points__ = point_num_f
                        match_type = "Final"
                        round_number = 0
                        random.shuffle(teams)
                        match_number_now = pre_match_number
                        for i in range(0, len(teams), 2):
                            team1 = teams[i]
                            team2 = teams[i + 1]
                            obj = GenerateKey()
                            secret_key = obj.generate_league_unique_id()
                            match_number_now = match_number_now + 1
                            court_num = court_num + 1
                            if courts__ <= court_num:
                                court_num = 1
                            Tournament.objects.create(set_number=sets__,court_num=court_num,points=points__,court_sn=court_num,match_number=match_number_now, secret_key=secret_key, leagues=league, team1_id=team1, team2_id=team2, match_type=match_type, elimination_round=round_number)
                        data["status"], data["message"] = status.HTTP_200_OK, f"Matches created for {match_type}"
                        return Response(data)
                    else:
                        sets__ = set_num_e
                        courts__ = court_num_e
                        points__ = point_num_e
                        match_type = "Elimination Round"
                        round_number = pre_match_round + 1
                        random.shuffle(teams)
                        match_number_now = pre_match_number
                        for i in range(0, len(teams), 2):
                            team1 = teams[i]
                            team2 = teams[i + 1]
                            obj = GenerateKey()
                            secret_key = obj.generate_league_unique_id()
                            match_number_now = match_number_now + 1
                            court_num = court_num + 1
                            if courts__ <= court_num:
                                court_num = 1
                            Tournament.objects.create(set_number=sets__,court_num=court_num,points=points__,court_sn=court_num,match_number=match_number_now, secret_key=secret_key, leagues=league, team1_id=team1, team2_id=team2, match_type=match_type, elimination_round=round_number)
                        data["status"], data["message"] = status.HTTP_200_OK, f"Matches created for {match_type}-{round_number}"
                        return Response(data)
                else:
                    data["status"], data["message"] = status.HTTP_200_OK, "Previous Round is not completed or not updated"
                    return Response(data)
            else:
                teams = []
                court_num = 0
                sets__ = set_num_e
                courts__ = court_num_e
                points__ = point_num_e
                for grp in check_leagues:
                    teams__ = grp.registered_team.all()
                    for te in teams__:
                        teams.append(te.id)
                if len(teams) == 4:
                    match_type = "Semi Final"
                    random.shuffle(teams)
                    match_number_now = 0
                    for i in range(0, len(teams), 2):
                        team1 = teams[i]
                        team2 = teams[i + 1]
                        obj = GenerateKey()
                        secret_key = obj.generate_league_unique_id()
                        match_number_now = match_number_now + 1
                        court_num = court_num + 1
                        if courts__ <= court_num:
                            court_num = 1
                        Tournament.objects.create(set_number=sets__,court_num=court_num,points=points__,court_sn=court_num,match_number=match_number_now, secret_key=secret_key, leagues=league, team1_id=team1, team2_id=team2, match_type=match_type, elimination_round=0)
                    data["status"], data["message"] = status.HTTP_200_OK, f"Matches created for {match_type}"
                    return Response(data)
                if len(teams) == 2:
                    sets__ = set_num_f
                    courts__ = court_num_f
                    points__ = point_num_f
                    match_type = "Final"
                    random.shuffle(teams)
                    match_number_now = 0
                    for i in range(0, len(teams), 2):
                        team1 = teams[i]
                        team2 = teams[i + 1]
                        obj = GenerateKey()
                        secret_key = obj.generate_league_unique_id()
                        match_number_now = match_number_now + 1
                        court_num = court_num + 1
                        if courts__ <= court_num:
                            court_num = 1
                        Tournament.objects.create(set_number=sets__,court_num=court_num,points=points__,court_sn=court_num,match_number=match_number_now, secret_key=secret_key, leagues=league, team1_id=team1, team2_id=team2, match_type=match_type, elimination_round=0)
                    data["status"], data["message"] = status.HTTP_200_OK, f"Matches created for {match_type}"
                    return Response(data)
                else:
                    print("hit")
                    match_type = "Elimination Round"
                    random.shuffle(teams)
                    match_number_now = 0
                    for i in range(0, len(teams), 2):
                        team1 = teams[i]
                        team2 = teams[i + 1]
                        obj = GenerateKey()
                        secret_key = obj.generate_league_unique_id()
                        match_number_now = match_number_now + 1
                        court_num = court_num + 1
                        if courts__ <= court_num:
                            court_num = 1
                        Tournament.objects.create(set_number=sets__,court_num=court_num,points=points__,court_sn=court_num,match_number=match_number_now, secret_key=secret_key, leagues=league, team1_id=team1, team2_id=team2, match_type=match_type, elimination_round=1)
                    data["status"], data["message"] = status.HTTP_200_OK, f"Matches created for {match_type}"
                    return Response(data)
        
        #done
        elif playtype == "Group Stage":
            check_pre_game =  Tournament.objects.filter(leagues=league)
            if check_pre_game.exists():
                all_round_robin_match = Tournament.objects.filter(leagues=league)
                all_completed_round_robin_match = Tournament.objects.filter(leagues=league, is_completed=True)
                if all_round_robin_match.exists() and all_completed_round_robin_match.exists() and all_round_robin_match.count() == all_completed_round_robin_match.count():
                    check_pre_game =  Tournament.objects.filter(leagues=league)
                    last_match_type = check_pre_game.last().match_type
                    last_round = check_pre_game.last().elimination_round
                    last_match_number = check_pre_game.last().match_number
                    if last_match_type == "Round Robin":
                        all_group_details = RoundRobinGroup.objects.filter(league_for=league)
                        for grp in all_group_details:
                            teams = grp.all_teams.all()
                            group_score_point_table = []
                            for team in teams:
                                team_score = {}
                                total_match_detals = Tournament.objects.filter(leagues=league).filter(Q(team1=team) | Q(team2=team))
                                completed_match_details = total_match_detals.filter(is_completed=True)
                                win_match_details = completed_match_details.filter(winner_team=team).count()
                                loss_match_details = completed_match_details.filter(loser_team=team).count()
                                drow_match = len(completed_match_details) - (win_match_details + loss_match_details)
                                point = (win_match_details * 3) + (drow_match * 1)
                                match_list = list(total_match_detals.values_list("id", flat=True))
                                for_score = 0
                                aginst_score = 0
                                for sc in match_list:
                                    co_team_position = Tournament.objects.filter(id=sc).first()
                                    set_score = TournamentSetsResult.objects.filter(tournament_id=sc)
                                    if co_team_position.team1 == team:
                                        for_score = for_score + sum(list(set_score.values_list("team1_point", flat=True)))
                                        aginst_score = aginst_score + sum(list(set_score.values_list("team2_point", flat=True)))
                                    else:
                                        for_score = for_score + sum(list(set_score.values_list("team2_point", flat=True)))
                                        aginst_score = aginst_score + sum(list(set_score.values_list("team1_point", flat=True)))
                                team_score["uuid"], team_score["secret_key"] = team.uuid, team.secret_key
                                team_score["completed_match"] = len(completed_match_details)
                                team_score["win_match"], team_score["loss_match"] = win_match_details, loss_match_details
                                team_score["drow_match"], team_score["for_score"] = drow_match, drow_match
                                team_score["aginst_score"], team_score["point"] = drow_match, point
                                group_score_point_table.append(team_score)
    
                            grp_team = sorted(group_score_point_table, key=lambda x: (x['point'], x['for_score']), reverse=True)
                            select_team_instance = Team.objects.filter(uuid=grp_team[0]["uuid"],secret_key=grp_team[0]["secret_key"])
                            RoundRobinGroup.objects.filter(id=grp.id).update(seleced_teams=select_team_instance.first())
                        match_type = "Elimination Round"
                        round_number = 1
                        teams = list(RoundRobinGroup.objects.filter(league_for=league).values_list("seleced_teams_id", flat=True))
                        if len(teams) != len(RoundRobinGroup.objects.filter(league_for=league)):
                            data["status"],  data["message"] = status.HTTP_200_OK, f"Not all groups have winners selected"
                            return Response(data)
                        # print(teams)
                        sets__ = set_num_e
                        courts__ = court_num_e
                        points__ = point_num_e
                        if len(teams) == 2:
                            match_type = "Final"
                            round_number = 0
                            sets__ = set_num_f
                            courts__ = court_num_f
                            points__ = point_num_f
                        elif len(teams) == 4:
                            match_type = "Semi Final"
                            round_number = 0
                            sets__ = set_num_e
                            courts__ = court_num_e
                            points__ = point_num_e
                        random.shuffle(teams)
                        match_number_now = last_match_number
                        court_num = 0
                        for i in range(0, len(teams), 2):
                            team1 = teams[i]
                            team2 = teams[i + 1]
                            obj = GenerateKey()
                            secret_key = obj.generate_league_unique_id()
                            match_number_now = match_number_now + 1
                            court_num += 1
                            if courts__ <= court_num:
                                court_num = 1
                            Tournament.objects.create(set_number=sets__,court_num=court_num,points=points__,court_sn=court_num,match_number=match_number_now,secret_key=secret_key, leagues=league,team1_id=team1, team2_id=team2,match_type=match_type,elimination_round=round_number)
                        data["status"], data["message"] = status.HTTP_200_OK, f"Matches are created for {match_type} {round_number}"
                        return Response(data)
                    elif last_match_type == "Elimination Round":
                        match_type = "Elimination Round"
                        round_number = last_round + 1
                        # win_teams
                        sets__ = set_num_e
                        courts__ = court_num_e
                        points__ = point_num_e
                        teams = list(Tournament.objects.filter(leagues=league, elimination_round=last_round).values_list("winner_team_id", flat=True))
                        if len(teams) != len(Tournament.objects.filter(leagues=league, elimination_round=last_round)):
                            data["status"],  data["message"] = status.HTTP_200_OK, f"Not all groups have winners selected"
                            return Response(data)
                        
                        elif len(teams) == 2:
                            match_type = "Final"
                            round_number = 0
                            sets__ = set_num_f
                            courts__ = court_num_f
                            points__ = point_num_f
                        elif len(teams) == 4:
                            match_type = "Semi Final"
                            round_number = 0
                        random.shuffle(teams)
                        match_number_now = last_match_number
                        court_num = 0
                        for i in range(0, len(teams), 2):
                            team1 = teams[i]
                            team2 = teams[i + 1]
                            obj = GenerateKey()
                            secret_key = obj.generate_league_unique_id()
                            match_number_now = match_number_now + 1
                            court_num += 1
                            if courts__ <= court_num:
                                court_num = 1
                            Tournament.objects.create(set_number=sets__,court_num=court_num,points=points__,court_sn=court_num,match_number=match_number_now,secret_key=secret_key, leagues=league,team1_id=team1, team2_id=team2,match_type=match_type,elimination_round=round_number)
                        data["status"], data["message"] = status.HTTP_200_OK, f"Matches are created for {match_type} {round_number}"
                        return Response(data)
                    elif last_match_type == "Semi Final":
                        match_type = "Final"
                        round_number = 0
                        sets__ = set_num_f
                        courts__ = court_num_f
                        points__ = point_num_f
                        winning_teams = list(Tournament.objects.filter(leagues=league, match_type="Semi Final").values_list('winner_team_id', flat=True))
                        
                        #Tournament.objects.filter(leagues=league, match_type="Semi Final") #backup
                        if len(winning_teams) != 2:
                            data["status"],  data["message"] = status.HTTP_200_OK, f"Not all groups have winners selected"
                            return Response(data)
                        random.shuffle(winning_teams)
                        match_number_now = last_match_number
                        court_num = 0
                        for i in range(0, len(winning_teams), 2):
                            team1 = winning_teams[i]
                            team2 = winning_teams[i + 1]
                            obj = GenerateKey()
                            secret_key = obj.generate_league_unique_id()
                            match_number_now = match_number_now + 1
                            court_num += 1
                            if courts__ <= court_num:
                                court_num = 1
                            Tournament.objects.create(set_number=sets__,court_num=court_num,points=points__,court_sn=court_num,match_number=match_number_now,secret_key=secret_key, leagues=league,team1_id=team1, team2_id=team2,match_type=match_type,elimination_round=round_number)
                        data["status"], data["message"] = status.HTTP_200_OK, f"Matches are created for {match_type} ."
                        return Response(data)
                    elif last_match_type == "Final":
                        data["status"],  data["message"] = status.HTTP_200_OK, f"The tournament results are out! The tournament is completed successfully."
                        return Response(data)
                else:
                    data["status"],  data["message"] = status.HTTP_200_OK, f"All matches in this round are not completed yet."
                    return Response(data)
            else:
                #create Robin Round
                registered_teams = league.registered_team.all() if league else None
                team_details_list = [team.id for team in registered_teams] if registered_teams else []
                
                play_details = LeaguesPlayType.objects.filter(league_for=league).first()
                number_of_group = court_num_r
                
                group_list = create_group(team_details_list, number_of_group)
                
                round_robin_group_details = RoundRobinGroup.objects.filter(league_for=league)
                if round_robin_group_details.exists():
                    if len(round_robin_group_details) == number_of_group:
                        # chek_tour = Tournament.objects.filter(leagues=league, is_completed=True)
                        # if not chek_tour.exists():
                        #     group_list = []
                        #     for grp in round_robin_group_details:
                        #         team_id_list = list(grp.all_teams.values_list("id", flat=True))
                        #         group_list.append(team_id_list)
                        #     serial_number = 0
                    
                        #     for index, group_teams in enumerate(group_list, start=1):
                        #         group = RoundRobinGroup.objects.create(court=index, league_for=league, number_sets=set_num_r)
                        #         for team_id in group_teams:
                        #             team = Team.objects.get(id=team_id)
                        #             group.all_teams.add(team)
                                
                        #         match_combinations = list(combinations(group_teams, 2))
                        #         for teams in match_combinations:
                        #             obj = GenerateKey()
                        #             secret_key = obj.generate_league_unique_id()
                        #             team1, team2 = teams
                        #             serial_number = serial_number+1
                        #             Tournament.objects.create(set_number=set_num_r,court_num=index,points=point_num_r,match_number=serial_number,secret_key=secret_key, leagues=league, team1_id=team1, team2_id=team2, group_id=group.id,match_type="Round Robin")
                        #     data["status"], data["message"] = status.HTTP_200_OK, f"Matches are created for Round Robin"
                        #     return Response(data)
                        # else:
                        data["status"],  data["message"] = status.HTTP_200_OK, f"Round Robin matches already created for {league.name}"
                        return Response(data)
                    else:
                        for gr in round_robin_group_details:
                            Tournament.objects.filter(group_id=gr.id).delete
                            gr.delete()
                serial_number = 0
                
                for index, group_teams in enumerate(group_list, start=1):
                    group = RoundRobinGroup.objects.create(court=index, league_for=league, number_sets=set_num_r)
                    for team_id in group_teams:
                        team = Team.objects.get(id=team_id)
                        group.all_teams.add(team)
                    
                    # match_combinations = list(combinations(group_teams, 2))
                    match_combinations = [(team1, team2) for i, team1 in enumerate(group_teams) for team2 in group_teams[i+1:]]

                    # Shuffle the matches to randomize
                    random.shuffle(match_combinations)
                    for teams in match_combinations:
                        obj = GenerateKey()
                        secret_key = obj.generate_league_unique_id()
                        team1, team2 = teams
                        serial_number = serial_number+1
                        Tournament.objects.create(set_number=set_num_r,court_num=index,points=point_num_r,match_number=serial_number,secret_key=secret_key, leagues=league, team1_id=team1, team2_id=team2, group_id=group.id,match_type="Round Robin")
                data["status"], data["message"] = status.HTTP_200_OK, f"Matches are created for Round Robin"
                return Response(data)
        
        #done
        elif playtype == "Round Robin":
            match_type = playtype
            registered_teams = league.registered_team.all() if league else None
            team_details_list = [team.id for team in registered_teams] if registered_teams else []
            max_team = league.max_number_team
            play_details = LeaguesPlayType.objects.filter(league_for=league).first()
            number_of_group = 1
            if int(max_team) != len(team_details_list):
                data["status"],  data["message"] = status.HTTP_200_OK, f"All teams are not registered"
                return Response(data)
            group_list = create_group(team_details_list, number_of_group)
            round_robin_group_details = RoundRobinGroup.objects.filter(league_for=league)
            if round_robin_group_details.exists():
                if len(round_robin_group_details) == number_of_group:
                    data["status"],  data["message"] = status.HTTP_200_OK, f"Round Robin group already created for {league.name}"
                    return Response(data)
                else:
                    for gr in round_robin_group_details:
                        Tournament.objects.filter(group_id=gr.id).delete
                        gr.delete()
            serial_number = 0
            
            for index, group_teams in enumerate(group_list, start=1):
                group = RoundRobinGroup.objects.create(court=index, league_for=league, number_sets=set_num_r)
                for team_id in group_teams:
                    team = Team.objects.get(id=team_id)
                    group.all_teams.add(team)
                
                # match_combinations = list(combinations(group_teams, 2))
                match_combinations = [(team1, team2) for i, team1 in enumerate(group_teams) for team2 in group_teams[i+1:]]

                # Shuffle the matches to randomize
                random.shuffle(match_combinations)
                for teams in match_combinations:
                    obj = GenerateKey()
                    secret_key = obj.generate_league_unique_id()
                    team1, team2 = teams
                    serial_number = serial_number+1
                    Tournament.objects.create(set_number=set_num_r,court_num=index,points=point_num_r,match_number=serial_number,secret_key=secret_key, leagues=league, team1_id=team1, team2_id=team2, group_id=group.id,match_type="Round Robin")
            data["status"], data["message"] = status.HTTP_200_OK, f"Matches created for {match_type}"
            return Response(data)
        
        elif playtype == "Individual Match Play":
            print("enter")
            match_type = playtype
            team____ = league.registered_team.all()
            teams = []
            for te in team____:
                teams.append(te.id)
            check_tournament = Tournament.objects.filter(leagues=league,match_type=match_type)
            if check_tournament.exists():
                data["status"], data["message"] = status.HTTP_200_OK, "Matches are already created"
                return Response(data) 
            if len(teams) != 2:
                data["status"], data["message"] = status.HTTP_200_OK, "Mininum 2 teams are needed for individual match play"
                return Response(data) 
            sets__ = set_num_f
            courts__ = court_num_f
            points__ = point_num_f
            round_number = 0
            random.shuffle(teams)
            match_number_now = 0
            # court_num = 0

            set_court = 8
            court_num = 0
            print("vdfjshfjh",courts__)
            for count in range(courts__):
                print("dhfvhd", count)
                court_num = court_num + 1
                match_number_now = court_num
                for i in range(0, len(teams), 2):
                    team1 = teams[i]
                    team2 = teams[i + 1]
                    obj = GenerateKey()
                    secret_key = obj.generate_league_unique_id()
                    Tournament.objects.create(set_number=sets__,court_num=court_num,points=points__,court_sn=court_num,match_number=match_number_now,secret_key=secret_key, leagues=league,team1_id=team1, team2_id=team2,match_type=match_type,elimination_round=round_number) 
            
            data["status"], data["message"] = status.HTTP_200_OK, f"Matches created for {match_type}"
            return Response(data)
    # if tournamnet not found
    else:
        data["status"], data["data"],data["ttt"],data["uuu"], data["message"] = status.HTTP_404_NOT_FOUND, [user_uuid,user_secret_key,league_uuid,league_secret_key],list(check_leagues),list(check_user), "User or Tournament not found."
    return Response(data)


## notification organizer to all team of tournament
@api_view(['POST'])
def send_notification_organizer_to_player(request):
    data = {'status': '', 'message': ''}
    try:        
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        league_uuid = request.data.get('league_uuid')
        league_secret_key = request.data.get('league_secret_key')
        n_title = request.data.get('n_title')
        n_message = request.data.get('n_message')
        
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key).exists()
        check_league = Leagues.objects.filter(uuid=league_uuid, secret_key=league_secret_key).first()

        if check_user and check_league:
            all_teams = check_league.registered_team.all()
            title = n_title
            if not title:
                title = f"{check_league.name} information."
            message = n_message

            notification_user_list = []
            
            for team in all_teams:
                players = Player.objects.filter(team=team)
                for player in players:
                    if player.player.id not in notification_user_list:

                        notification_user_list.append(player.player.id)
                        notify_edited_player(player.player.id, title, message)
            save_league_user = list(SaveLeagues.objects.filter(ch_league=check_league).values_list('created_by_id', flat=True))
            for user in save_league_user:
                if user not in notification_user_list:
                    notify_edited_player(user, title, message)

            data["status"], data["message"] = status.HTTP_200_OK, "Successfully sent notifications to all team's players"
        else:
            data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "User or League not found"
    except Exception as e:
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, str(e)
    return Response(data)


### completly updated
@api_view(('GET',))
def view_leagues(request):
        data = {
             'status':'',
             'create_group_status':False,
             'max_team': None,
             'total_register_team':None,
             'is_organizer': False,
             'is_register': False,
             'sub_organizer_data':[],
             'organizer_name_data':[],
             'invited_code':None,
             'winner_team': 'Not Declared',
             'data':[],
             'tournament_detais':[],
             'point_table':[],
             'elemination':[], 
             'final':[], 
             'message':'',
             'match':[]
             }
    # try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        league_uuid = request.GET.get('league_uuid')
        league_secret_key = request.GET.get('league_secret_key')
        protocol = 'https' if request.is_secure() else 'http'
        host = request.get_host()
        media_base_url = f"{protocol}://{host}{settings.MEDIA_URL}"
        '''
        registration_open, future, past
        '''
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        check_leagues = Leagues.objects.filter(uuid=league_uuid,secret_key=league_secret_key)
        if check_user.exists() and check_leagues.exists():
            leagues = check_leagues.values('uuid','secret_key','name','location','leagues_start_date','leagues_end_date',
                               'registration_start_date','registration_end_date','team_type__name','team_person__name',
                               "street","city","state","postal_code","country","complete_address","latitude","longitude","play_type","registration_fee","description","image","others_fees", "league_type")
            league = check_leagues.first()
            get_user = check_user.first()

            today_date = datetime.today().date()
            if league.registration_end_date not in [None, "null", "", "None"]:
                if league.registration_end_date.date() >= today_date and league.league_type != "Invites only" and league.max_number_team > league.registered_team.count() and not league.is_complete:
                    data["is_register"] = True
            
            organizers = list(User.objects.filter(id=league.created_by.id).values('id','uuid','secret_key','username','first_name','last_name','email','phone','gender','user_birthday','role','rank','image','street','city','state','country','postal_code'))
            sub_organizer_data = list(league.add_organizer.all().values('id','uuid','secret_key','username','first_name','last_name','email','phone','gender','user_birthday','role','rank','image','street','city','state','country','postal_code'))
            
            organizer_list = organizers + sub_organizer_data
            for nu in organizer_list:
                nu["phone"] = str(nu["phone"])
            data['sub_organizer_data'] = organizer_list
            
            organizer_list = []
            for org in data['sub_organizer_data']:
                first_name = org["first_name"]
                last_name = org["last_name"]
                if not first_name:
                    first_name = " "
                if not last_name:
                    last_name = " "
                name = f"{first_name} {last_name}"
                organizer_list.append(name)
            data['organizer_name_data'] = organizer_list

            sub_org_list = list(league.add_organizer.all().values_list("id", flat=True))  
            if get_user == league.created_by or get_user.id in sub_org_list:
                data['is_organizer'] =  True
                data['invited_code'] =  league.invited_code
            
            data['max_team'] =  league.max_number_team
            data['total_register_team'] =  league.registered_team.all().count()
            data['tournament_detais'] = LeaguesPlayType.objects.filter(league_for = check_leagues.first()).values()
            data['data'] = leagues

            ######## tournament matches details ########
            #working
            tournament_details = Tournament.objects.filter(leagues=check_leagues.first()).order_by("match_number").values("id","match_number","uuid","secret_key","leagues__name",
                                                                                                                          "team1_id", "team2_id", "team1__team_image", "team2__team_image", 
                                                                                                                          "team1__name", "team2__name", "winner_team_id", "winner_team__name", 
                                                                                                                          "playing_date_time","match_type","group__court","is_completed",
                                                                                                                          "elimination_round","court_sn","set_number","court_num","points","is_drow")
            
            for sc in tournament_details:
                if sc["group__court"] is None:
                    sc["group__court"] = sc["court_sn"]

                team_1_player = list(Player.objects.filter(team__id=sc["team1_id"]).values_list("player_id", flat=True))
                team_2_player = list(Player.objects.filter(team__id=sc["team2_id"]).values_list("player_id", flat=True))
                team_1_created_by = Team.objects.filter(id=sc["team1_id"]).first().created_by
                team_2_created_by = Team.objects.filter(id=sc["team2_id"]).first().created_by

                if (get_user == league.created_by) or (get_user.id in sub_org_list) or (get_user.id in team_1_player) or (get_user == team_1_created_by) or (get_user.id in team_2_player) or ((get_user == team_2_created_by)):
                    sc["is_edit"] = True
                else:
                    sc["is_edit"] = False

                check_score_approved = TournamentScoreApproval.objects.filter(tournament__id=sc["id"], team1_approval=True, team2_approval=True)

                if check_score_approved.exists():
                    sc["is_score_approved"] = True
                    sc["is_edit"] = False
                else:
                    sc["is_score_approved"] = False                    
                
                check_score_reported = TournamentScoreReport.objects.filter(tournament__id=sc["id"], status="Pending")
                if check_score_reported.exists():
                    sc["is_score_reported"] = True 
                    if (get_user == league.created_by) or (get_user.id in sub_org_list):
                        sc["is_edit"] = True
                    else:
                        sc["is_edit"] = False
                else:
                    sc["is_score_reported"] = False   

                team1_approval = TournamentScoreApproval.objects.filter(tournament__id=sc["id"], team1_approval=True).exists()
                team2_approval = TournamentScoreApproval.objects.filter(tournament__id=sc["id"], team1_approval=True).exists()
                check_score_set = TournamentSetsResult.objects.filter(tournament__id=sc["id"])

                if check_score_set.exists() and not team1_approval and ((get_user.id in team_1_player) or (get_user == team_1_created_by)):
                    sc["is_button_show"] = True
                
                elif check_score_set.exists() and not team2_approval and ((get_user.id in team_2_player) or (get_user == team_2_created_by)):
                    sc["is_button_show"] = True
                else:
                    sc["is_button_show"] = False

                if sc["team1__team_image"] != "":
                    img_str = sc["team1__team_image"]
                    sc["team1__team_image"] = f"{media_base_url}{img_str}"
                if sc["team2__team_image"] != "":
                    img_str = sc["team2__team_image"]
                    sc["team2__team_image"] = f"{media_base_url}{img_str}"
                #"set_number","court_num","points"
                set_list_team1 = []
                set_list_team2 = []
                score_list_team1 = []
                score_list_team2 = []
                win_status_team1 = []
                win_status_team2 = []
                is_completed_match = sc["is_completed"]
                is_win_match_team1 = False
                is_win_match_team2 = False
                team1_name = sc["team1__name"]
                team2_name = sc["team2__name"]
                if sc["team1_id"] == sc["winner_team_id"] and sc["winner_team_id"] is not None:
                    is_win_match_team1 = True
                    is_win_match_team2 = False
                elif sc["team2_id"] == sc["winner_team_id"] and sc["winner_team_id"] is not None:
                    is_win_match_team2 = True
                    is_win_match_team1 = False
                # else:
                #     is_win_match_team2 = False
                #     is_win_match_team1 = False
                for s in range(sc["set_number"]):
                    index = s+1
                    set_str = f"s{index}"
                    set_list_team1.append(set_str)
                    set_list_team2.append(set_str)
                    score_details_for_set = TournamentSetsResult.objects.filter(tournament_id=sc["id"],set_number=index).values()
                    if len(score_details_for_set)!=0:
                        team_1_score = score_details_for_set[0]["team1_point"]
                        team_2_score = score_details_for_set[0]["team2_point"]
                    else:
                        team_1_score = None
                        team_2_score = None
                    score_list_team1.append(team_1_score)
                    score_list_team2.append(team_2_score)
                    if team_1_score is not None and team_2_score is not None:
                        if team_1_score >= team_2_score:
                            win_status_team1.append(True)
                            win_status_team2.append(False)
                        else:
                            win_status_team1.append(False)
                            win_status_team2.append(True)
                    else:
                        win_status_team1.append(False)
                        win_status_team2.append(False)
                score = [
                    {
                     "name": team1_name,"set": set_list_team2,
                     "score": score_list_team1,"win_status": win_status_team1,
                     "is_win": is_win_match_team1,"is_completed": is_completed_match
                     },
                    {
                    "name": team2_name,"set": set_list_team2,
                    "score": score_list_team2,"win_status": win_status_team1,
                    "is_win": is_win_match_team2,"is_completed": is_completed_match
                    }
                    ]
                sc["score"] = score
                # print(score)
            
              
            data['match'] = tournament_details
            ######## tournament matches details ########

            ########### Knock Out part ####################

            #this data for Elimination Round   
            knock_out_tournament_elimination_data = Tournament.objects.filter(leagues=check_leagues.first(),match_type="Elimination Round").values("id","uuid","secret_key","match_number","match_type","elimination_round","team1__name", "team1_id", "team2_id"
                                                                                                            ,"team1__team_image","team2__name","team2__team_image","winner_team__name", "winner_team_id", "loser_team_id", "winner_team__team_image","loser_team__name","loser_team__team_image","is_completed","play_ground_name")
            for ele_tour in knock_out_tournament_elimination_data:
                # ele_tour["is_edit"] = get_user.is_organizer and check_leagues.first().created_by == get_user or ele_tour["team1_id"] == get_user.id or ele_tour["team2_id"] == get_user.id
                if get_user == league.created_by or get_user.id in sub_org_list or sc["team1_id"] == get_user.id or sc["team2_id"] == get_user.id:
                    sc["is_edit"] = True
                else:
                    sc["is_edit"] = False

                check_score_approved = TournamentScoreApproval.objects.filter(tournament__id=sc["id"], team1_approval=True, team2_approval=True)

                if check_score_approved.exists():
                    sc["is_score_approved"] = True
                    sc["is_edit"] = False
                else:
                    sc["is_score_approved"] = False                    
                
                check_score_reported = TournamentScoreReport.objects.filter(tournament__id=sc["id"], status="Pending")
                if check_score_reported.exists():
                    sc["is_score_reported"] = True 
                    if (get_user == league.created_by) or (get_user.id in sub_org_list):
                        sc["is_edit"] = True
                    else:
                        sc["is_edit"] = False
                else:
                    sc["is_score_reported"] = False   

                team1_approval = TournamentScoreApproval.objects.filter(tournament__id=sc["id"], team1_approval=True).exists()
                team2_approval = TournamentScoreApproval.objects.filter(tournament__id=sc["id"], team1_approval=True).exists()
                check_score_set = TournamentSetsResult.objects.filter(tournament__id=sc["id"])

                if check_score_set.exists() and not team1_approval and ((get_user.id in team_1_player) or (get_user == team_1_created_by)):
                    sc["is_button_show"] = True
                
                elif check_score_set.exists() and not team2_approval and ((get_user.id in team_2_player) or (get_user == team_2_created_by)):
                    sc["is_button_show"] = True
                else:
                    sc["is_button_show"] = False

                score = [{"name": "","set": [],"score": [],"win_status": [],"is_win": True,"is_completed": True},{"name": "","set": [],"score": [],"win_status": [],"is_win": True,"is_completed": True}]
                
                if ele_tour["team1_id"] == ele_tour["winner_team_id"] and ele_tour["winner_team_id"] is not None:
                    score[0]["is_win"] = True
                    score[1]["is_win"] = False
                elif ele_tour["team2_id"] == ele_tour["winner_team_id"] and ele_tour["winner_team_id"] is not None:
                    score[1]["is_win"] = True
                    score[0]["is_win"] = False
                else:
                    score[1]["is_win"] = None
                    score[0]["is_win"] = None
                score_details = TournamentSetsResult.objects.filter(tournament_id=ele_tour["id"]).values()
                score[0]["name"] = ele_tour["team1__name"]
                score[1]["name"] = ele_tour["team2__name"]
                score[0]["set"] = ["s1","s2","s3"]
                score[1]["set"] = ["s1","s2","s3"]
                for l__ in range(3):
                    
                    if l__ < len(score_details):
                        l = {"team1_point":score_details[l__]["team1_point"],"team2_point":score_details[l__]["team2_point"]}
                    else:
                        l = {"team1_point":None,"team2_point":None}
                    
                    score[0]["score"].append(l["team1_point"])
                    score[1]["score"].append(l["team2_point"])
                    
                    if l["team1_point"] == None or l["team1_point"] == None:
                        score[0]["win_status"].append(None)
                        score[1]["win_status"].append(None)
                    elif l["team1_point"] > l["team2_point"]:
                        score[0]["win_status"].append(True)
                        score[1]["win_status"].append(False)
                    else:
                        score[0]["win_status"].append(False)
                        score[1]["win_status"].append(True)
                ele_tour["score"] = score
            data['elemination'] = list(knock_out_tournament_elimination_data)

            #this data for Semi Final   
            knock_out_semifinal_tournament_data = Tournament.objects.filter(leagues=check_leagues.first(),match_type="Semi Final").values("id","uuid","secret_key","match_number","match_type","elimination_round","team1__name", "team1_id", "team2_id"
                                                                                                            ,"team1__team_image","team2__name","team2__team_image","winner_team__name", "winner_team_id", "loser_team_id", "winner_team__team_image","loser_team__name","loser_team__team_image","is_completed","play_ground_name")
            for semi_tour in knock_out_semifinal_tournament_data:
                if get_user == league.created_by or get_user.id in sub_org_list or sc["team1_id"] == get_user.id or sc["team2_id"] == get_user.id:
                    sc["is_edit"] = True
                else:
                    sc["is_edit"] = False
                
                check_score_approved = TournamentScoreApproval.objects.filter(tournament__id=sc["id"], team1_approval=True, team2_approval=True)

                if check_score_approved.exists():
                    sc["is_score_approved"] = True
                    sc["is_edit"] = False
                else:
                    sc["is_score_approved"] = False                    
                
                check_score_reported = TournamentScoreReport.objects.filter(tournament__id=sc["id"], status="Pending")
                if check_score_reported.exists():
                    sc["is_score_reported"] = True 
                    if (get_user == league.created_by) or (get_user.id in sub_org_list):
                        sc["is_edit"] = True
                    else:
                        sc["is_edit"] = False
                else:
                    sc["is_score_reported"] = False   

                team1_approval = TournamentScoreApproval.objects.filter(tournament__id=sc["id"], team1_approval=True).exists()
                team2_approval = TournamentScoreApproval.objects.filter(tournament__id=sc["id"], team1_approval=True).exists()
                check_score_set = TournamentSetsResult.objects.filter(tournament__id=sc["id"])

                if check_score_set.exists() and not team1_approval and ((get_user.id in team_1_player) or (get_user == team_1_created_by)):
                    sc["is_button_show"] = True
                
                elif check_score_set.exists() and not team2_approval and ((get_user.id in team_2_player) or (get_user == team_2_created_by)):
                    sc["is_button_show"] = True
                else:
                    sc["is_button_show"] = False

                score = [{"name": "","set": [],"score": [],"win_status": [],"is_win": True,"is_completed": True},{"name": "","set": [],"score": [],"win_status": [],"is_win": True,"is_completed": True}]
                
                if semi_tour["team1_id"] == semi_tour["winner_team_id"] and semi_tour["winner_team_id"] is not None:
                    score[0]["is_win"] = True
                    score[1]["is_win"] = False
                elif semi_tour["team2_id"] == semi_tour["winner_team_id"] and semi_tour["winner_team_id"] is not None:
                    score[1]["is_win"] = True
                    score[0]["is_win"] = False
                else:
                    score[1]["is_win"] = None
                    score[0]["is_win"] = None
                score_details = TournamentSetsResult.objects.filter(tournament_id=semi_tour["id"]).values()
                score[0]["name"] = semi_tour["team1__name"]
                score[1]["name"] = semi_tour["team2__name"]
                score[0]["set"] = ["s1","s2","s3"]
                score[1]["set"] = ["s1","s2","s3"]
                for l__ in range(3):
                    
                    if l__ < len(score_details):
                        l = {"team1_point":score_details[l__]["team1_point"],"team2_point":score_details[l__]["team2_point"]}
                    else:
                        l = {"team1_point":None,"team2_point":None}
                    
                    score[0]["score"].append(l["team1_point"])
                    score[1]["score"].append(l["team2_point"])
                    
                    if l["team1_point"] == None or l["team1_point"] == None:
                        score[0]["win_status"].append(None)
                        score[1]["win_status"].append(None)
                    elif l["team1_point"] > l["team2_point"]:
                        score[0]["win_status"].append(True)
                        score[1]["win_status"].append(False)
                    else:
                        score[0]["win_status"].append(False)
                        score[1]["win_status"].append(True)
                semi_tour["score"] = score
            data['semi_final'] = list(knock_out_semifinal_tournament_data)

            #this data for Final 
            knock_out_final_tournament_data = Tournament.objects.filter(leagues=check_leagues.first(),match_type="Final").values("id","uuid","secret_key","match_number","match_type","elimination_round","team1__name", "team1_id", "team2_id"
                                                                                                            ,"team1__team_image","team2__name","team2__team_image","winner_team__name", "winner_team_id", "loser_team_id", "winner_team__team_image","loser_team__name","loser_team__team_image","is_completed","play_ground_name")
            for final_tour in knock_out_final_tournament_data:
                if get_user == league.created_by or get_user.id in sub_org_list or sc["team1_id"] == get_user.id or sc["team2_id"] == get_user.id:
                    sc["is_edit"] = True
                else:
                    sc["is_edit"] = False

                check_score_approved = TournamentScoreApproval.objects.filter(tournament__id=sc["id"], team1_approval=True, team2_approval=True)

                if check_score_approved.exists():
                    sc["is_score_approved"] = True
                    sc["is_edit"] = False
                else:
                    sc["is_score_approved"] = False                    
                
                check_score_reported = TournamentScoreReport.objects.filter(tournament__id=sc["id"], status="Pending")
                if check_score_reported.exists():
                    sc["is_score_reported"] = True 
                    if (get_user == league.created_by) or (get_user.id in sub_org_list):
                        sc["is_edit"] = True
                    else:
                        sc["is_edit"] = False
                else:
                    sc["is_score_reported"] = False   

                team1_approval = TournamentScoreApproval.objects.filter(tournament__id=sc["id"], team1_approval=True).exists()
                team2_approval = TournamentScoreApproval.objects.filter(tournament__id=sc["id"], team1_approval=True).exists()
                check_score_set = TournamentSetsResult.objects.filter(tournament__id=sc["id"])

                if check_score_set.exists() and not team1_approval and ((get_user.id in team_1_player) or (get_user == team_1_created_by)):
                    sc["is_button_show"] = True
                
                elif check_score_set.exists() and not team2_approval and ((get_user.id in team_2_player) or (get_user == team_2_created_by)):
                    sc["is_button_show"] = True
                else:
                    sc["is_button_show"] = False

                score = [{"name": "","set": [],"score": [],"win_status": [],"is_win": True,"is_completed": True},{"name": "","set": [],"score": [],"win_status": [],"is_win": True,"is_completed": True}]
                
                if final_tour["team1_id"] == final_tour["winner_team_id"] and final_tour["winner_team_id"] is not None:
                    score[0]["is_win"] = True
                    score[1]["is_win"] = False
                elif final_tour["team2_id"] == final_tour["winner_team_id"] and final_tour["winner_team_id"] is not None:
                    score[1]["is_win"] = True
                    score[0]["is_win"] = False
                else:
                    score[1]["is_win"] = None
                    score[0]["is_win"] = None
                score_details = TournamentSetsResult.objects.filter(tournament_id=final_tour["id"]).values()
                score[0]["name"] = final_tour["team1__name"]
                score[1]["name"] = final_tour["team2__name"]
                score[0]["set"] = ["s1","s2","s3"]
                score[1]["set"] = ["s1","s2","s3"]
                for l__ in range(3):
                    
                    if l__ < len(score_details):
                        l = {"team1_point":score_details[l__]["team1_point"],"team2_point":score_details[l__]["team2_point"]}
                    else:
                        l = {"team1_point":None,"team2_point":None}
                    
                    score[0]["score"].append(l["team1_point"])
                    score[1]["score"].append(l["team2_point"])
                    
                    if l["team1_point"] == None or l["team1_point"] == None:
                        score[0]["win_status"].append(None)
                        score[1]["win_status"].append(None)
                    elif l["team1_point"] > l["team2_point"]:
                        score[0]["win_status"].append(True)
                        score[1]["win_status"].append(False)
                    else:
                        score[0]["win_status"].append(False)
                        score[1]["win_status"].append(True)
                final_tour["score"] = score
            data['final'] = list(knock_out_final_tournament_data)

            ########### Knock Out part ####################
            
            ########### declear winner team and update ##########
            play_type_check_win = league.play_type
            if play_type_check_win == "Group Stage" or play_type_check_win == "Single Elimination":
                check_final = Tournament.objects.filter(leagues=check_leagues.first(),match_type="Final",is_completed=True)
                if check_final.exists():
                    final_match = check_final.first()
                    winner_team = final_match.winner_team
                    winner_team_name = final_match.winner_team.name
                    league.winner_team = winner_team
                    league.is_complete = True
                    league.save()
                    data["winner_team"] = winner_team_name
                else:
                    pass

            else:
                check_final = Tournament.objects.filter(leagues=check_leagues.first(),match_type="Individual Match Play",is_completed=True)
                if check_final.exists():
                    final_match = check_final.first()
                    if not final_match.is_drow:
                        winner_team = final_match.winner_team
                        winner_team_name = final_match.winner_team.name
                        league.winner_team = winner_team
                        league.is_complete = True
                        league.save()
                        data["winner_team"] = winner_team_name
                    else:
                        winner_team1 = final_match.team1
                        winner_team2 = final_match.team2
                        # league.winner_team = None
                        league.is_complete = True
                        league.save()
                        data["winner_team"] = f"{winner_team1.name}, {winner_team2.name}"
                else:
                    pass
            ########### declear winner team and update ##########


            #If Tournament is Group stage or Round Robin
            ############# point table ########################
            all_group_details = RoundRobinGroup.objects.filter(league_for=league)
            for grp in all_group_details:
                teams = grp.all_teams.all()
                group_score_point_table = []
                # print(teams)
                for team in teams:
                    team_score = {}
                    total_match_detals = Tournament.objects.filter(leagues=league, match_type="Round Robin").filter(Q(team1=team) | Q(team2=team))
                    completed_match_details = total_match_detals.filter(is_completed=True)
                    win_match_details = completed_match_details.filter(winner_team=team).count()
                    loss_match_details = completed_match_details.filter(loser_team=team).count()
                    drow_match = len(completed_match_details) - (win_match_details + loss_match_details)
                    match_list = list(total_match_detals.values_list("id", flat=True))
                    for_score = 0
                    aginst_score = 0
                    for sc in match_list:
                        co_team_position = Tournament.objects.filter(id=sc).first()
                        set_score = TournamentSetsResult.objects.filter(tournament_id=sc)
                        if co_team_position.team1 == team:
                           for_score = for_score + sum(list(set_score.values_list("team1_point", flat=True)))
                           aginst_score = aginst_score + sum(list(set_score.values_list("team2_point", flat=True)))
                        else:
                            for_score = for_score + sum(list(set_score.values_list("team2_point", flat=True)))
                            aginst_score = aginst_score + sum(list(set_score.values_list("team1_point", flat=True)))
                    
                    point = (win_match_details * 3) + (drow_match * 1)
                    team_score["uuid"], team_score["secret_key"] = team.uuid, team.secret_key
                    team_score["name"], team_score["completed_match"] = team.name, len(completed_match_details)
                    team_score["win_match"], team_score["loss_match"] = win_match_details, loss_match_details
                    team_score["drow_match"], team_score["for_score"] = drow_match, for_score
                    team_score["aginst_score"], team_score["point"] = aginst_score, point
                    group_score_point_table.append(team_score)
                # Append team details to group data
                tournament_details_group = Tournament.objects.filter(leagues=league,group=grp).values("id","uuid","secret_key","team1__name","team2__name","leagues__name","match_type","is_completed","group__court","play_ground_name","playing_date_time","group_id")
                for k_ in tournament_details_group:
                    round_robin_group_detals = RoundRobinGroup.objects.filter(league_for=league, id=k_["group_id"]).first()
                    k_["sets"] = round_robin_group_detals.number_sets
                    k_["court"] = round_robin_group_detals.court
                    k_["score"] = list(TournamentSetsResult.objects.filter(tournament_id=k_["id"]).values())
                
                group_score_point_table = sorted(group_score_point_table, key=lambda x: (x['point'], x['for_score']), reverse=True)
                # print(group_score_point_table)

                ###### tournament winning team update and declare
                if play_type_check_win == "Round Robin":
                    total_tournament = Tournament.objects.filter(leagues=check_leagues.first(),match_type="Round Robin",leagues__play_type="Round Robin")
                    completed_tournament = total_tournament.filter(is_completed=True)
                    if total_tournament.count() == completed_tournament.count():
                        winner_team = Team.objects.filter(uuid=group_score_point_table[0]["uuid"]).first()
                        winner_team_name = winner_team.name
                        league.winner_team = winner_team
                        league.is_complete = True
                        league.save()
                        data["winner_team"] = winner_team_name
                grp_data = {
                    "id": grp.id,
                    "court": grp.court,
                    "league_for_id": grp.league_for_id,
                    "all_games_status": grp.all_games_status,
                    "all_tems": group_score_point_table,
                    "tournament": tournament_details_group,
                    "seleced_teams_id": grp.seleced_teams_id
                }
                data['point_table'].append(grp_data)

            all_team = check_leagues.first().registered_team.all()
            ############# point table ########################


            ######### Tornament all teams details ############
            teams = []
            for t in all_team:
                team_d = Team.objects.filter(id=t.id).values()
                teams.append(team_d[0])
            for im in teams:
                if im["team_image"] != "":
                    img_str = im["team_image"]
                    im["team_image"] = f"{media_base_url}{img_str}"
            
            data['teams'] = teams
            ######### Tornament all teams details ############
            
            
            data["create_group_status"] = get_user.is_organizer and check_leagues.first().created_by == get_user
            data["status"], data["message"] = status.HTTP_200_OK, "League data"
        else:
            data["status"], data['data'], data["message"] = status.HTTP_404_NOT_FOUND, [],  "User or League not found."
    # except Exception as e :
    #     data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
        return Response(data)

#old
# @api_view(('POST',))
# def edit_leagues_max_team(request):
#     data = {'status':'','message':''}
#     try:
#         user_uuid = request.data.get('user_uuid')
#         user_secret_key = request.data.get('user_secret_key')
#         league_uuid = request.data.get('league_uuid')
#         league_secret_key = request.data.get('league_secret_key')
#         max_team = request.data.get('max_team')
        
#         if int(max_team) < 2:
#             data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "Minimun need two teams for assigne match"
#             return Response(data)
        
#         check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
#         check_league  = Leagues.objects.filter(uuid=league_uuid,secret_key=league_secret_key)
#         if check_user.exists() and check_league.exists():
#             get_tornament = check_league.first()
#             get_user = check_user.first()
#             if get_tornament.created_by==get_user:
#                 check_have_match = Tournament.objects.filter(leagues=get_tornament)
#                 if not check_have_match.exists():
#                     check_league.update(max_number_team=int(max_team))
#                     data["status"], data["message"] = status.HTTP_200_OK, "League updated successfully"
#                 else:
#                     data["status"], data["message"] = status.HTTP_200_OK, "This Tournament already start"
#             else:
#                 data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "This is not your tournamnet"
#         else:
#             data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "User or League not found"
#     except Exception as e :
#         data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
#     return Response(data)


#new
@api_view(('POST',))
def edit_leagues_max_team(request):
    data = {'status':'','message':''}
    try:        
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        league_uuid = request.data.get('league_uuid')
        league_secret_key = request.data.get('league_secret_key')
        max_team = request.data.get('max_team')
        
        if int(max_team) < 2:
            data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "Minimun need two teams for assigning match"
            return Response(data)
        
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        check_league  = Leagues.objects.filter(uuid=league_uuid,secret_key=league_secret_key)
        if check_user.exists() and check_league.exists():
            get_tornament = check_league.first()
            get_user = check_user.first()
            all_org_list = list(get_tornament.add_organizer.all().values_list("id", flat=True))
            if get_tornament.created_by==get_user or get_user.id in all_org_list:
                check_have_match = Tournament.objects.filter(leagues=get_tornament)
                if not check_have_match.exists():
                    check_league.update(max_number_team=int(max_team))
                    data["status"], data["message"] = status.HTTP_200_OK, "League updated successfully"
                else:
                    data["status"], data["message"] = status.HTTP_200_OK, "This Tournament already start"
            else:
                data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "This is not your tournamnet"
        else:
            data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "User or League not found"
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)

###################################### updated work ########################################


@api_view(('POST',))
def delete_leagues(request):
    data = {'status':'','message':''}
    try:        
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        leagues_id = request.data.get('leagues_id')
        
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        check_league  = Leagues.objects.filter(id=leagues_id)
        if check_user.exists() and check_league.exists():
            get_tornament = check_league.first()
            get_user = check_user.first()
            join_team = get_tornament.registered_team.all().count()
            if join_team != 0:
                data["status"], data["message"] = status.HTTP_200_OK, "You cann't  delete this tournament"
            else:
                check_league.delete()
                data["status"], data["message"] = status.HTTP_200_OK, "League deleted successfully"
        else:
            data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "User or League not found"
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


#old
# @api_view(('GET',))
# def list_leagues_user(request):
#     data = {'status':'','data':'','message':''}
#     try:
#         user_uuid = request.GET.get('user_uuid')
#         user_secret_key = request.GET.get('user_secret_key')
#         filter_by = request.GET.get('filter_by')
#         search_text = request.GET.get('search_text')
#         '''
#         registration_open, future, past
#         '''
#         check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
#         if check_user.exists() :
#             get_user = check_user.first()
#             leagues = []
#             if search_text:
#                 all_leagues = Leagues.objects.filter(Q(name__icontains=search_text)).filter(created_by=get_user)
#             else:
#                 all_leagues = Leagues.objects.filter(created_by=get_user)
#             today_date = datetime.now()
            
#             if filter_by == "future" :
#                 all_leagues = all_leagues.filter(registration_start_date__date__gte=today_date).order_by('registration_start_date')
#             elif filter_by == "past" :
#                 all_leagues = all_leagues.filter(leagues_end_date__date__lte=today_date).order_by('-leagues_end_date')
#             elif filter_by == "registration_open":
#                 all_leagues = all_leagues.filter(registration_start_date__date__lte=today_date,registration_end_date__date__gte=today_date).order_by('registration_end_date')
#             elif filter_by == "ongoing":
#                 all_leagues = all_leagues.filter(leagues_start_date__date__lte=today_date,leagues_end_date__date__gte=today_date).order_by('leagues_start_date')
            
#             else:
#                 all_leagues = all_leagues.order_by('leagues_start_date')
#             leagues = all_leagues.values("id",'uuid','secret_key','name','location','leagues_start_date','leagues_end_date',
#                                'registration_start_date','registration_end_date','team_type__name','team_person__name',
#                                "street","city","state","postal_code","country","complete_address","latitude","longitude","image","others_fees", "league_type","registration_fee")
            
            
#             output = []
#             # Grouping data by 'name'
#             grouped_data = {}
#             for item in list(leagues):
#                 item["is_reg_diable"] = True
#                 match_ = Tournament.objects.filter(leagues_id=item["id"]).values()
#                 if match_.exists():
#                     item["is_reg_diable"] = False
#                 le = Leagues.objects.filter(id=item["id"]).first()
#                 reg_team =le.registered_team.all().count()
#                 max_team = le.max_number_team
#                 if max_team <= reg_team:
#                     item["is_reg_diable"] = False
#                 key = item['name']
#                 if key not in grouped_data:
#                     grouped_data[key] = {
#                                         'name': item['name'], 
#                                         'lat':item['latitude'], 
#                                         'long':item["longitude"],
#                                         'registration_start_date':item["registration_start_date"],
#                                         'registration_end_date':item["registration_end_date"],
#                                         'leagues_start_date':item["leagues_start_date"],
#                                         'leagues_end_date':item["leagues_end_date"],
#                                         'location':item["location"],
#                                         'image':item["image"],
#                                         'type': [item['team_type__name']], 
#                                         'data': [item]
#                                         }
#                 else:
#                     grouped_data[key]['type'].append(item['team_type__name'])
#                     grouped_data[key]['data'].append(item)

#             # Building the final output
#             for key, value in grouped_data.items():
#                 output.append(value)

#             # print(output)
#             leagues = output
            
#             for i in leagues:
#                 i["is_edit"] = True
#                 i["is_delete"] = True
#             data["status"], data['data'], data["message"] = status.HTTP_200_OK, leagues, "League data"
#         else:
#             data["status"], data['data'], data["message"] = status.HTTP_404_NOT_FOUND, "","User not found."
#     except Exception as e :
#         data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
#     return Response(data)


#new
@api_view(('GET',))
def list_leagues_user(request):
    data = {'status':'','data':'','message':''}
    try:        
        user_uuid = request.GET.get('user_uuid') 
        user_secret_key = request.GET.get('user_secret_key')
        filter_by = request.GET.get('filter_by')
        search_text = request.GET.get('search_text')
        '''
        registration_open, future, past
        '''
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        if check_user.exists() :
            get_user = check_user.first()
            leagues = []
            if search_text:
                all_leagues = Leagues.objects.filter(is_created=True).filter(Q(name__icontains=search_text) &
                                                    (Q(created_by=get_user) | Q(add_organizer__id=get_user.id)))
            else:
                all_leagues = Leagues.objects.filter(is_created=True).filter((Q(created_by=get_user) | Q(add_organizer__id=get_user.id)))
            today_date = datetime.now()
            if filter_by == "future" :
                all_leagues = all_leagues.filter(registration_start_date__date__gte=today_date).order_by('registration_start_date')
            elif filter_by == "past" :
                all_leagues = all_leagues.filter(leagues_end_date__date__lte=today_date).order_by('-leagues_end_date')
            elif filter_by == "registration_open":
                all_leagues = all_leagues.filter(registration_start_date__date__lte=today_date,registration_end_date__date__gte=today_date).order_by('registration_end_date')
            elif filter_by == "ongoing":
                all_leagues = all_leagues.filter(leagues_start_date__date__lte=today_date,leagues_end_date__date__gte=today_date).order_by('leagues_start_date')
            
            else:
                all_leagues = all_leagues.order_by('leagues_start_date')
            leagues = all_leagues.values("id",'uuid','secret_key','name','location','leagues_start_date','leagues_end_date',
                               'registration_start_date','registration_end_date','team_type__name','team_person__name','any_rank','start_rank','end_rank',
                               "street","city","state","postal_code","country","complete_address","latitude","longitude","image","others_fees", "league_type","registration_fee")
            
            
            output = []
            # Grouping data by 'name'
            grouped_data = {}
            for item in list(leagues):
                # registratrion controle
                item["is_reg_diable"] = True
                match_ = Tournament.objects.filter(leagues_id=item["id"]).values()
                if match_.exists():
                    item["is_reg_diable"] = False
                le = Leagues.objects.filter(id=item["id"], ).first()
                sub_organizer_list = list(le.add_organizer.all().values_list("id", flat=True))
                reg_team =le.registered_team.all().count()
                max_team = le.max_number_team
                if max_team <= reg_team:
                    item["is_reg_diable"] = False
                if get_user == le.created_by:
                    item["main_organizer"] = True
                    item["sub_organizer"] = False
                elif get_user.id in sub_organizer_list:
                    item["main_organizer"] = False
                    item["sub_organizer"] = True
                else:
                    item["main_organizer"] = False
                    item["sub_organizer"] = False
                key = item['name']
                if key not in grouped_data:
                    grouped_data[key] = {
                                        'name': item['name'], 
                                        'lat':item['latitude'], 
                                        'long':item["longitude"],
                                        'registration_start_date':item["registration_start_date"],
                                        'registration_end_date':item["registration_end_date"],
                                        'leagues_start_date':item["leagues_start_date"],
                                        'leagues_end_date':item["leagues_end_date"],
                                        'type': [item['team_type__name']],
                                        'location':item["location"],
                                        'image':item["image"],                                         
                                        'data': [item]
                                        }
                else:
                    grouped_data[key]['type'].append(item['team_type__name'])
                    grouped_data[key]['data'].append(item)

            # Building the final output
            for key, value in grouped_data.items():
                output.append(value)

            # print(output)
            leagues = output
            
            for i in leagues:
                i["is_edit"] = True
                i["is_delete"] = True
            data["status"], data['data'], data["message"] = status.HTTP_200_OK, leagues, "League data"
        else:
            data["status"], data['data'], data["message"] = status.HTTP_404_NOT_FOUND, "","User not found."
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)

#new12

@api_view(('POST',))
def tournament_edit(request):
    data = {'status':'', 'message':''}
    try:        
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        league_uuid = request.data.get('League_uuid')
        league_secret_key = request.data.get('League_secret_key')
        matches_data = request.data.get('data')

        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        
        if check_user.exists() and check_user.first().is_admin:
            get_league = Leagues.objects.filter(uuid=league_uuid, secret_key=league_secret_key)
            
            if get_league.exists():
                league = get_league.first()
                
                for match_data in matches_data:
                    Tournament.objects.filter(secret_key=match_data.get("secret_key"),leagues=league).update(location=match_data.get("location"),playing_date_time=match_data.get("playing_date_time"))
                data["status"], data["message"] = status.HTTP_200_OK, "Matches location and date updated successfully"
            else:
                data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "League not found"
        else:   
            data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "No user found"
    except Exception as e:
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, str(e)
    
    return Response(data)


#new
@api_view(('POST',))
def add_organizer_league(request):
    data = {'status': '', 'message': ''}
    try:
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        league_uuid = request.data.get('league_uuid')  
        league_secret_key = request.data.get('league_secret_key')  
        organizer_id_list = request.data.get('organizer_id_list')
        organizer_id_list = json.loads(organizer_id_list)
        # Check if user and league exist
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        check_league = Leagues.objects.filter(uuid=league_uuid, secret_key=league_secret_key)
        if check_user.exists() and check_league.exists(): 
            get_user = check_user.first()
            get_league = check_league.first()
            if get_league.created_by == get_user:
                # Add organizers to the league
                org_list = get_league.add_organizer.all().count()
                if org_list == 0:
                    for org_id in organizer_id_list:
                        organizer_ins = User.objects.filter(id=int(org_id)).first()
                        if organizer_ins:
                            get_league.add_organizer.add(organizer_ins)
                    get_league.save()
                else:
                    get_league.add_organizer.clear()
                    for org_id in organizer_id_list:
                        organizer_ins = User.objects.filter(id=int(org_id)).first()
                        if organizer_ins:
                            get_league.add_organizer.add(organizer_ins)
                    get_league.save()
                data["status"], data["message"] = status.HTTP_200_OK, "Tournament organizers updated successfully."
            else:
                data["status"], data["message"] = status.HTTP_403_FORBIDDEN, "User does not have permission to add the organizer of this tournament."
        else:
            data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "Tournament or user not found."
    except Exception as e:
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, str(e)

    return Response(data)


@api_view(('GET',))
def team_register_user(request):
    data = {'status': '', 'data': '', 'message': ''}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        league_uuid = request.GET.get('league_uuid')
        league_secret_key = request.GET.get('league_secret_key')

        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if check_user.exists():
            get_user = check_user.first()            
            get_teams = Team.objects.filter(created_by=get_user)            
            check_league = Leagues.objects.filter(uuid=league_uuid, secret_key=league_secret_key)
            if check_league.exists():
                league = check_league.first()
                team_type = league.team_type.name
                team_person = league.team_person.name
                team_data = []
                
                team_id_list = list(league.registered_team.all().values_list("id", flat=True))
                
                for team in get_teams:
                    flg = True
                    flg_text = ""
                    register_team_id_list = list(league.registered_team.all().values_list("id", flat=True))
                    is_view = False
                    if team.id not in register_team_id_list:
                       is_view = True 
                    if team_type and team.team_type and team_person and team.team_person:
                        if not (team_type.strip() == team.team_type.strip() and team_person.strip() == team.team_person.strip()):
                            flg = False
                            if team_type.strip() != team.team_type.strip():
                                flg_text = "Team type does not match for this league"
                            elif team_person.strip() != team.team_person.strip():
                                flg_text = "Person type does not match for this league"
                    else:
                        flg = False
                        flg_text = "Team type or Person type is not provided"
                    
                    player_data = Player.objects.filter(team=team).values("player_full_name", "player_ranking", "player__rank")
                    team_rank = 0
                    for pla in player_data:
                        pla["player_ranking"] = pla["player__rank"]                  
                        if pla["player__rank"] == "0" or pla["player__rank"] in [0,"", "null", None]:
                            team_rank += 1
                        else:
                            team_rank += float(pla["player__rank"])
                    team_rank = team_rank / len(player_data)

                    team_info = {
                        "uuid": team.uuid,
                        "secret_key": team.secret_key,
                        "team_name": team.name,
                        "team_rank":team_rank,
                        "team_image": str(team.team_image),
                        "location": team.location,
                        "created_by_name": f"{team.created_by.first_name} {team.created_by.last_name}",
                        "flg": flg,
                        "is_view":is_view,
                        "flg_text": flg_text,
                        "team_person": team.team_person,
                        "team_type": team.team_type,
                        "player_data": player_data,
                    }
                    if team_info["flg"] == True and team.id not in team_id_list:
                        team_data.append(team_info)
                    else:
                        pass

                league_data = {
                    "uuid": league.uuid,
                    "secret_key": league.secret_key,
                    "name": league.name,
                    "leagues_start_date": league.leagues_start_date,
                    "leagues_end_date": league.leagues_end_date,
                    "registration_start_date": league.registration_start_date,
                    "registration_end_date": league.registration_end_date,
                    "team_type__name": league.team_type.name,
                    "team_person__name": league.team_person.name,
                    "max_join_team":league.max_number_team,
                    "total_join_team":len(team_id_list),
                    "any_rank_status":league.any_rank,
                    "league_start_rank":league.start_rank,
                    "league_end_rank":league.end_rank
                    # "image": league.image,
                    # "description": league.description,
                    # "registration_fee":league.registration_fee
                }

                main_data = {"league_data": [league_data], "team_data": team_data}
                data["status"], data['data'], data["message"] = status.HTTP_200_OK, main_data, "Data found."
            else:
                data["status"], data['data'], data["message"] = status.HTTP_404_NOT_FOUND, "", "Tournament  not found"
        else:
            data["status"], data['data'], data["message"] = status.HTTP_404_NOT_FOUND, "", "User not found."
    except Exception as e:
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, str(e)
    return Response(data)


# @api_view(('POST',))
# def add_team_to_leagues(request):
#     data = {'status':'','data':'','message':''}
#     try:
#         user_uuid = request.data.get('user_uuid')
#         user_secret_key = request.data.get('user_secret_key')
#         league_uuid = request.data.get('league_uuid')
#         league_secret_key = request.data.get('league_secret_key')
#         team_uuid_all = request.data.get('team_uuid')
#         team_secret_key_all = request.data.get('team_secret_key')       
     
#         check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
#         chaek_leagues = Leagues.objects.filter(uuid=league_uuid,secret_key=league_secret_key)
#         if not check_user.exists() and not chaek_leagues.exists():
#             data['status'] = status.HTTP_400_BAD_REQUEST
#             data['message'] =  f"User or Tournament not found"
#             return Response(data)
            
#         get_league = chaek_leagues.first()
#         total_registered_teams = get_league.registered_team.all().count()
#         today_date = datetime.now().astimezone(utc)
#         if get_league.registration_end_date < today_date or get_league.max_number_team == total_registered_teams or get_league.is_complete == True:
#             data['status'] = status.HTTP_400_BAD_REQUEST
#             data['message'] =  f"Registration is over."
#             return Response(data)
        
#         user_id = check_user.first().id
#         tournament_id = chaek_leagues.first().id
#         team_uuid_all = str(team_uuid_all).split(",")
#         team_secret_key_all = str(team_secret_key_all).split(",")
#         all_team_id = []
#         for t in range(len(team_uuid_all)):
#             team = Team.objects.filter(uuid=team_uuid_all[t],secret_key=team_secret_key_all[t])
#             if team.exists():
#                 team_id = team.first().id
#                 all_team_id.append(team_id)
#         #parse_json data
#         make_request_data = {"tournament_id":tournament_id,"user_id":user_id,"team_id_list":all_team_id}
        
#         #json bytes
#         json_bytes = json.dumps(make_request_data).encode('utf-8')
        
#         # Encode bytes to base64
#         my_data = base64.b64encode(json_bytes).decode('utf-8')

#         if check_user.exists() and chaek_leagues.exists():
#             number_of_team_join = len(all_team_id)
#             get_le = chaek_leagues.first()
#             oth = get_le.others_fees
#             try:
#                 others_total = sum(oth.values()) if oth else 0
#             except TypeError:
#                 others_total = 0
#             total_ammount = get_le.registration_fee + others_total
#             chage_amount =  total_ammount * 100 * number_of_team_join
             
#             product_name = "Payment For Register Team"
#             product_description = "Payment received by Pickleit"
#             stripe.api_key = settings.STRIPE_SECRET_KEY
#             get_user = check_user.first()
#             if get_user.stripe_customer_id :
#                 stripe_customer_id = get_user.stripe_customer_id
#             else:
#                 customer = stripe.Customer.create(email=get_user.email).to_dict()
#                 stripe_customer_id = customer["id"]
#                 get_user.stripe_customer_id = stripe_customer_id
#                 get_user.save()
            
#             # current_site = request.META['wsgi.url_scheme'] + '://' + request.META['HTTP_HOST']
#             #protocol = 'https' if request.is_secure() else 'http'
#             host = request.get_host()
#             current_site = f"{protocol}://{host}"
#             main_url = f"{current_site}/team/c80e2caf03546f11a39db8703fb7f7457afc5cb20db68b5701497fd992a0c29f/{chage_amount}/{my_data}/"
#             product = stripe.Product.create(name=product_name,description=product_description,).to_dict()
#             price = stripe.Price.create(unit_amount=chage_amount,currency='usd',product=product["id"],).to_dict()
#             checkout_session = stripe.checkout.Session.create(
#                 customer=stripe_customer_id,
#                 line_items=[
#                     {
#                         # Provide the exact Price ID (for example, pr_1234) of the product you want to sell
#                         'price': price["id"],
#                         'quantity': 1,
#                     },
#                 ],
#                 mode='payment',
#                 success_url= main_url + "{CHECKOUT_SESSION_ID}" + "/",
#                 cancel_url="https://example.com/success" + '/cancel.html',
#             )
#             return Response({"strip_url":checkout_session.url})
#     except Exception as e :
#         data['status'] = status.HTTP_400_BAD_REQUEST
#         data['message'] =  f"{e}"
#         return Response(data)


@api_view(('POST',))
def add_team_to_leagues(request):
    data = {'status':'','data':[],'message':''}
    try:        
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        league_uuid = request.data.get('league_uuid')
        league_secret_key = request.data.get('league_secret_key')
        team_uuid_all = request.data.get('team_uuid')
        team_secret_key_all = request.data.get('team_secret_key')       
     
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        chaek_leagues = Leagues.objects.filter(uuid=league_uuid,secret_key=league_secret_key)
        if not check_user.exists() and not chaek_leagues.exists():
            data['status'] = status.HTTP_400_BAD_REQUEST
            data['message'] =  f"User or Tournament not found"
            return Response(data)
        
        get_league = chaek_leagues.first()      

        total_registered_teams = get_league.registered_team.all().count()
        today_date = timezone.now()
        if get_league.registration_end_date < today_date or get_league.max_number_team == total_registered_teams or get_league.is_complete == True:
            data['status'] = status.HTTP_400_BAD_REQUEST
            data['message'] =  f"Registration is over."
            return Response(data)
        
        user_id = check_user.first().id
        tournament_id = chaek_leagues.first().id
        team_uuid_all = str(team_uuid_all).split(",")
        team_secret_key_all = str(team_secret_key_all).split(",")
        all_team_id = []
        for t in range(len(team_uuid_all)):
            team = Team.objects.filter(uuid=team_uuid_all[t],secret_key=team_secret_key_all[t])
            if team.exists():
                team_id = team.first().id
                all_team_id.append(team_id)

        if get_league.start_rank and get_league.end_rank:
            for id in all_team_id: 
                team = Team.objects.filter(id=id).values().first()              
                players = Player.objects.filter(team__id=team["id"])
                team_rank = 0
                for player in players:
                    if player.player.rank == "0" or player.player.rank in [0,"", "null", None]:
                        # player.player_ranking = 1.0
                        team_rank += 1
                    else:
                        team_rank += float(player.player.rank)
                team_rank = team_rank / len(players)
                team["rank"] = team_rank
                if not get_league.start_rank<=team["rank"]<=get_league.end_rank:
                    data['status'] = status.HTTP_400_BAD_REQUEST
                    data['message'] =  f"{team['name']} does not have the desired rank."
                    return Response(data)
        #parse_json data
        make_request_data = {"tournament_id":tournament_id,"user_id":user_id,"team_id_list":all_team_id}
        
        #json bytes
        json_bytes = json.dumps(make_request_data).encode('utf-8')
        
        # Encode bytes to base64
        my_data = base64.b64encode(json_bytes).decode('utf-8')

        if check_user.exists() and chaek_leagues.exists():
            number_of_team_join = len(all_team_id)
            get_le = chaek_leagues.first()
            oth = get_le.others_fees
            try:
                others_total = sum(oth.values()) if oth else 0
            except TypeError:
                others_total = 0
            total_ammount = get_le.registration_fee + others_total
            chage_amount =  total_ammount * 100 * number_of_team_join
             
            product_name = "Payment For Register Team"
            product_description = "Payment received by Pickleit"
            stripe.api_key = settings.STRIPE_SECRET_KEY
            get_user = check_user.first()
            if get_user.stripe_customer_id :
                stripe_customer_id = get_user.stripe_customer_id
            else:
                customer = stripe.Customer.create(email=get_user.email).to_dict()
                stripe_customer_id = customer["id"]
                get_user.stripe_customer_id = stripe_customer_id
                get_user.save()
            
            # current_site = request.META['wsgi.url_scheme'] + '://' + request.META['HTTP_HOST']
            #protocol = 'https' if request.is_secure() else 'http'
            host = request.get_host()
            current_site = f"{protocol}://{host}"
            main_url = f"{current_site}/team/c80e2caf03546f11a39db8703fb7f7457afc5cb20db68b5701497fd992a0c29f/{chage_amount}/{my_data}/"
            product = stripe.Product.create(name=product_name,description=product_description,).to_dict()
            price = stripe.Price.create(unit_amount=chage_amount,currency='usd',product=product["id"],).to_dict()
            checkout_session = stripe.checkout.Session.create(
                customer=stripe_customer_id,
                line_items=[
                    {
                        # Provide the exact Price ID (for example, pr_1234) of the product you want to sell
                        'price': price["id"],
                        'quantity': 1,
                    },
                ],
                mode='payment',
                success_url= main_url + "{CHECKOUT_SESSION_ID}" + "/",
                cancel_url="https://example.com/success" + '/cancel.html',
            )
            return Response({"strip_url":checkout_session.url})
    except Exception as e :
        data['status'] = status.HTTP_400_BAD_REQUEST
        data['message'] =  f"{e}"
        return Response(data)


def payment_for_team_registration(request,charge_for,my_data,checkout_session_id):
    try:
        context ={}
        stripe.api_key = settings.STRIPE_SECRET_KEY
        # context['stripe_api_key'] = settings.STRIPE_PUBLIC_KEY
        pay = stripe.checkout.Session.retrieve(checkout_session_id).to_dict()    
        stripe_customer_id = pay["customer"]
        payment_status = pay["payment_status"]
        expires_at = pay["expires_at"]
        amount_total = float(pay["amount_total"]) / 100
        payment_method_types = pay["payment_method_types"]
        payment_status = True if payment_status == "paid" else False
        json_bytes = base64.b64decode(my_data)
        request_data = json.loads(json_bytes.decode('utf-8'))
        # store payment details
        # demo data forment
        """
        {'tournament_id': 112, 'user_id': 3, 'team_id_list': [3]}
        """
        teams_list = list(request_data["team_id_list"])
        teams_count = len(request_data["team_id_list"])
        payment_for = f"Register {teams_count} Team"
        check_tournament = Leagues.objects.filter(id=request_data["tournament_id"]).first()
        payment = PaymentDetailsForRegister(
            tournament=check_tournament,
            payment_for=payment_for,
            payment_by_id=request_data["user_id"],
            charge_amount=amount_total,
            teams_ids={"team_ids":request_data["team_id_list"]},
            payment_status=payment_status
        )
        payment.save()
        if payment_status is True:
            check_tournament.registered_team.add(*teams_list)
            return render(request,"success_payment_for_register_team.html")
        else: 
            return render(request,"failed_paymentregister_team.html")
    except:
        return render(request,"failed_paymentregister_team.html")


@api_view(('GET',))
def player_or_manager_details(request):
    data = {'status':'','data':'','message':''}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        player_uuid = request.GET.get('player_uuid')
        player_secret_key = request.GET.get('player_secret_key')
        flag = request.GET.get('flag')
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        if check_user.exists() :
            if flag == "is_team_manager" :
                pass
            elif flag == "is_player" :
                check_player = Player.objects.filter(uuid=player_uuid,secret_key=player_secret_key)
                if check_player.exists():
                    get_player = check_player.first()
                else:
                    data["status"], data['data'], data["message"] = status.HTTP_404_NOT_FOUND, "","Player not found."
            else:
                pass
            # data["status"], data['data'], data["message"] = status.HTTP_200_OK, main_data,"Data found."
        else:
            data["status"], data['data'], data["message"] = status.HTTP_404_NOT_FOUND, "","User not found."
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


@api_view(('GET',))
def registered_team_for_leauge_list(request):
    data = {'status':'','data':'','message':''}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        leauge_uuid = request.GET.get('leauge_uuid')
        leauge_secret_key = request.GET.get('leauge_secret_key')
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        if check_user.exists() :
            get_user = check_user.first()
            main_data = []
            if get_user.is_admin :
                check_leauge = Leagues.objects.filter(uuid=leauge_uuid,secret_key=leauge_secret_key)
                get_leauge = check_leauge.first()
                team_data = []
                leauge_data = {"uuid":get_leauge.uuid,"secret_key":get_leauge.secret_key,"name":get_leauge.name,
                               "location":get_leauge.location,"leagues_start_date":get_leauge.leagues_start_date,"leagues_end_date":get_leauge.leagues_end_date,
                               "registration_start_date":get_leauge.registration_start_date,"registration_end_date":get_leauge.registration_end_date,
                               "team_type__name":get_leauge.team_type.name,"team_person__name":get_leauge.team_person.name}
                get_team = Team.objects.filter(leagues__id = get_leauge.id).order_by("name")
                for i in get_team :
                    team = [{"uuid":i.uuid,"secret_key":i.secret_key,"name":i.name,"location":i.location,"team_image": str(i.team_image) ,"created_by":f"{i.created_by.first_name} {i.created_by.last_name}"}]
                    player_data = []
                    get_player = Player.objects.filter(team__in=[i.id])
                    for i in get_player :
                        player_data.append({"uuid":i.uuid,"secret_key":i.secret_key,"player_full_name":i.player_full_name,"player_ranking":i.player.rank})
                    team_data.append({"team":team,"player_data":player_data})
                main_data = {"leauge_data":leauge_data,"team_data":team_data}
            else:
                check_leauge = Leagues.objects.filter(uuid=leauge_uuid,secret_key=leauge_secret_key)
                get_leauge = check_leauge.first()
                team_data = []
                leauge_data = {"uuid":get_leauge.uuid,"secret_key":get_leauge.secret_key,"name":get_leauge.name,
                               "location":get_leauge.location,"leagues_start_date":get_leauge.leagues_start_date,"leagues_end_date":get_leauge.leagues_end_date,
                               "registration_start_date":get_leauge.registration_start_date,"registration_end_date":get_leauge.registration_end_date,
                               "team_type__name":get_leauge.team_type.name,"team_person__name":get_leauge.team_person.name}
                get_team = Team.objects.filter(leagues__id = get_leauge.id,created_by_id=get_user.id).order_by("name")
                for i in get_team :
                    team = [{"uuid":i.uuid,"secret_key":i.secret_key,"name":i.name,"location":i.location,"team_image": str(i.team_image) ,"created_by":f"{i.created_by.first_name} {i.created_by.last_name}"}]
                    player_data = []
                    get_player = Player.objects.filter(team__in=[i.id])
                    for i in get_player :
                        player_data.append({"uuid":i.uuid,"secret_key":i.secret_key,"player_full_name":i.player_full_name,"player_ranking":i.player.rank})
                    team_data.append({"team":team,"player_data":player_data})
                main_data = {"leauge_data":leauge_data,"team_data":team_data}
            data["status"], data['data'], data["message"] = status.HTTP_200_OK, main_data,"Data found."
        else:
            data["status"], data['data'], data["message"] = status.HTTP_404_NOT_FOUND, "","User not found."
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


# @api_view(('POST',))
# def add_advertisement(request):
#     data = {'status':'','data':'','message':''}
#     try:
#         user_uuid = request.data.get('user_uuid')
#         user_secret_key = request.data.get('user_secret_key')
#         advertisement_name = request.data.get('advertisement_name')
#         check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
#         if check_user.exists() :
#             obj = GenerateKey()
#             advertisement_key = obj.gen_advertisement_key()
#             advertisement = Advertisement(secret_key=advertisement_key,name=advertisement_name)
#     except Exception as e :
#         data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
#     return Response(data)


# def payment(request):
#     context = {}
#     context['publishable_key'] = stripe.api_key
#     if request.method == "POST":
#         pass
#     return render (request,'payment.html',context)


# @api_view(('GET',))
# def stats_details(request):
#     data = {'status':'','data':[], 'message':''}
#     try:
#         user_uuid = request.GET.get('user_uuid')
#         user_secret_key = request.GET.get('user_secret_key')
#         check_user = User.objects.filter(secret_key=user_secret_key,uuid=user_uuid)
#         # print(check_user)
        
#         if check_user.exists():
#             get_user = check_user.first()
            
#             stats_details = {}
#             stats_details["rank"] = get_user.rank
#             try:
#                 image = request.build_absolute_uri(get_user.image.url)
#             except:
#                 image = None
#             stats_details["name"] = get_user.username
#             stats_details["first_name"] = get_user.first_name
#             stats_details["last_name"] = get_user.last_name
#             stats_details["profile_image"] = image

#             player_details = Player.objects.filter(player=get_user)
#             if player_details.exists():
#                 total_league = 0
#                 win_league = 0
                
#                 team_ids = []
#                 for player_instance in player_details:
#                     team_ids.extend(list(player_instance.team.values_list('id', flat=True)))
#                 total_play_matches = 0
#                 win_match = 0 
#                 for team_id in team_ids:
#                     team_ = Team.objects.filter(id=team_id).first()
#                     lea = Leagues.objects.filter(registered_team__in=[team_id])
#                     check_match = Tournament.objects.filter(Q(team1=team_) | Q(team2=team_))
#                     win_check_match = check_match.filter(winner_team=team_).count()
#                     total_play_matches += check_match.count()
#                     win_match += win_check_match
#                     total_league += lea.count()

                
#                 stats_details["total_completed_turnament"] = total_league
#                 stats_details["total_win_turnament"] = win_league
#                 stats_details["total_completed_match"] = total_league
#                 stats_details["total_win_match"] = win_league
#             else:
                
#                 stats_details["total_completed_turnament"] = 0
#                 stats_details["total_win_turnament"] = 0
#                 stats_details["total_completed_match"] = 0
#                 stats_details["total_win_match"] = 0
#             data['message'] = "This user not in player list"
#             data['data'] = [stats_details]
#             data['status'] = status.HTTP_200_OK
#         else:
#             data['status'], data['data'], data['message'] = status.HTTP_400_BAD_REQUEST, [], f"user not found"
#     except Exception as e :
#         data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
#     return Response(data)


# updated


@api_view(('GET',))
def tournament_details(request):
    data = {'status':'','upcoming_leagues':[], 'previous_matches':[], 'signed_up_matches':[], 'save_league':[], 'message':''}
    try:
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        order_by = request.GET.get('order_by')
        check_user = User.objects.filter(secret_key=user_secret_key,uuid=user_uuid)
        today_date = timezone.now()
        # print(check_user)
        if check_user.exists():
            get_user = check_user.first()
            if get_user.is_coach is True or get_user.is_team_manager is True:
                created_by_leagues = Leagues.objects.filter(registered_team__created_by=get_user)
                #print(created_by_leagues.values("id"))
                previous_matches = created_by_leagues.filter(leagues_end_date__date__lte=today_date).order_by(str(order_by)).values("id","name","leagues_start_date","leagues_end_date","registration_start_date","registration_end_date")
                upcoming_leagues = Leagues.objects.filter(registration_start_date__date__lte=today_date,registration_end_date__date__gte=today_date).order_by(str(order_by)).values("id","name","leagues_start_date","leagues_end_date","registration_start_date","registration_end_date")
                signed_up_matches = created_by_leagues.filter(registration_start_date__date__lte=today_date,leagues_end_date__date__gte=today_date).order_by(str(order_by)).values("id","name","leagues_start_date","leagues_end_date","registration_start_date","registration_end_date")
                save_code_order_by = f"ch_league__{order_by}"
                save_league = SaveLeagues.objects.filter(created_by=get_user, ch_league__registration_end_date__date__gte=today_date).order_by(save_code_order_by).values("id","ch_league__name","ch_league__leagues_start_date","ch_league__leagues_end_date","ch_league__registration_start_date","ch_league__registration_end_date")
                data['status'], data['upcoming_leagues'], data['previous_matches'],data['signed_up_matches'], data['save_league'], data['message'] = status.HTTP_200_OK, upcoming_leagues,previous_matches,signed_up_matches,save_league, f""
            else:
                data['status'], data['upcoming_leagues'], data['previous_matches'], data['signed_up_matches'], data['save_league'], data['message'] = status.HTTP_200_OK, [],[],[],[], f"user not found"
        else:
            data['status'], data['upcoming_leagues'], data['previous_matches'],data['signed_up_matches'],data['save_league'], data['message'] = status.HTTP_200_OK, [],[],[],[], f"user not found"
    except Exception as e :
        data['status'],data['upcoming_leagues'], data['previous_matches'],data['signed_up_matches'],data['save_league'], data['message'] = status.HTTP_400_BAD_REQUEST,[],[],[],[], f"{e}"
    return Response(data)


@api_view(('POST',))
def save_league(request):
    data = {'status':'','message':''}
    try:
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        # team_uuid = request.data.get('team_uuid')
        league_uuid = request.data.get('league_uuid')
        check_user = User.objects.filter(secret_key=user_secret_key,uuid=user_uuid)
        obj = GenerateKey()
        _key = obj.gen_advertisement_key()
        # if user_uuid is None or user_secret_key is None:
        #         data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"Both 'user_uuid' and 'user_secret_key' are required parameters."
        if league_uuid is None:
                data['status'], data['message'] = status.HTTP_200_OK, f"League_uuid is required parameter."
        if check_user.exists():
            get_user = check_user.first()
            try:
                league_name = Leagues.objects.filter(uuid=league_uuid).first().name
                league_id = Leagues.objects.filter(uuid=league_uuid).first().id
                # team_id = Team.objects.filter(uuid=team_uuid).first().id
                ch_leaugh = SaveLeagues.objects.filter(ch_league_id=int(league_id),created_by=get_user)
                if ch_leaugh.exists():
                    pass
                else:
                    SaveLeagues.objects.create(secret_key=_key, ch_league_id=int(league_id),created_by=get_user)
                data['status'], data['message'] = status.HTTP_200_OK, f"You saved the {league_name} in your account"
            except Exception as e :
                data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
        else:
            data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"user not found"
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


class AddSponsorSerializer(serializers.Serializer):
    user_uuid = serializers.UUIDField()
    user_secret_key = serializers.CharField()
    username = serializers.CharField()
    email = serializers.EmailField()
    contact = serializers.CharField()
    league_uuid = serializers.UUIDField()
    league_secret_key = serializers.CharField()
    role = serializers.CharField()
    description = serializers.CharField()


@api_view(('POST',))
def add_sponsor(request):
    data = {'status': '', 'message': '','send_maile_status': False}
    try:
        serializer = AddSponsorSerializer(data=request.data)
        if not serializer.is_valid():
            data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, serializer.errors
            return Response(data)

        user_uuid = serializer.validated_data['user_uuid']
        user_secret_key = serializer.validated_data['user_secret_key']
        username = serializer.validated_data['username']
        email = serializer.validated_data['email']
        contact = serializer.validated_data['contact']
        league_uuid = serializer.validated_data['league_uuid']
        league_secret_key = serializer.validated_data['league_secret_key']
        role = serializer.validated_data['role']
        description = serializer.validated_data['description']
        check_user = User.objects.filter(secret_key=user_secret_key, uuid=user_uuid)
        obj = GenerateKey()
        secret_key = obj.gen_advertisement_key()

        if not check_user.exists():
            data['status'], data['message'] = status.HTTP_404_NOT_FOUND, "User not found"
            return Response(data)

        check_league = Leagues.objects.filter(uuid=league_uuid, secret_key=league_secret_key)
        if not check_league.exists():
            data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, "League does not exist"
            return Response(data)

        role_check = Role.objects.filter(role=role)
        if not role_check.exists():
            data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, "Role does not exist"
            return Response(data)

        password = GenerateKey.generate_password(5)
        mp = make_password(password)

        sponsor = User.objects.create(
            first_name=username,
            username=email,
            email=email,
            phone=contact,
            password=mp,
            password_raw=password,
            secret_key=secret_key,
            is_sponsor_expires_at=check_league.first().leagues_end_date,
            role=role_check.first(),
            is_verified=True,
            is_sponsor = True
        )

        IsSponsorDetails.objects.create(
            secret_key=secret_key,
            sponsor=sponsor,
            sponsor_added_by=check_user.first(),
            league_uuid=league_uuid,
            league_secret_key=league_secret_key,
            description=description
        )
        league = check_league.first().name
        current_site = 'https' + '://' + request.META['HTTP_HOST']
        send_type = "send"
        send_email_status = send_email_for_invite_sponsor(current_site, email, league, send_type)
        # print(send_email_status)
        data['status'], data['message'],data['send_maile_status'] = status.HTTP_201_CREATED, "Sponsor created successfully", send_email_status
    except Exception as e:
        data['status'], data['message'] = "400", str(e)
    return Response(data)


class IsSponsorDetailsSerializer(serializers.ModelSerializer):
    sponsor_name = serializers.CharField(source='sponsor.first_name', read_only=True)
    sponsor_email = serializers.CharField(source='sponsor.email', read_only=True)
    sponsor_uuid = serializers.CharField(source='uuid', read_only=True)
    sponsor_image = serializers.CharField(source='sponsor.image', read_only=True)
    sponsor_secret_key = serializers.CharField(source='secret_key', read_only=True)
    user_uuid = serializers.CharField(source='sponsor.uuid', read_only=True)
    user_secret_key = serializers.CharField(source='sponsor.secret_key', read_only=True)
    is_sponsor = serializers.CharField(source='sponsor.is_sponsor', read_only=True)
    is_sponsor_expires_at = serializers.CharField(source='sponsor.is_sponsor_expires_at', read_only=True)
    is_verified = serializers.CharField(source='sponsor.is_verified', read_only=True)
    # league = Leagues.objects.filter()
    
    class Meta:
        model = IsSponsorDetails
        fields = ["sponsor_uuid", "sponsor_secret_key", "user_uuid", "user_secret_key", "league_uuid","league_secret_key", "sponsor_name", "sponsor_image", "sponsor_email", "sponsor_email", "is_sponsor", "is_sponsor_expires_at", "is_verified", "sponsor_added_by", "description"]

#up
@api_view(['GET'])
def view_sponsor_list(request):
    data = {'status': '', 'message': '', 'data': []}
    try:
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        search_text = request.GET.get('search_text')
        
        check_user = User.objects.filter(secret_key=user_secret_key, uuid=user_uuid)
        if check_user.exists():
            get_user = check_user.first()
            
            try:
                if get_user.is_admin:
                    if search_text:
                        sponsor_details = IsSponsorDetails.objects.filter(Q(sponsor__first_name__icontains=search_text) | Q(sponsor__last_name__icontains=search_text))
                    else:
                        sponsor_details = IsSponsorDetails.objects.all()
                else:
                    if search_text:
                        sponsor_details = IsSponsorDetails.objects.filter(sponsor_added_by=get_user).filter(Q(sponsor__first_name__icontains=search_text) | Q(sponsor__last_name__icontains=search_text))
                    else:
                        sponsor_details = IsSponsorDetails.objects.filter(sponsor_added_by=get_user)

                if sponsor_details.exists():
                    serializer = IsSponsorDetailsSerializer(sponsor_details, many=True)
                    data['data'] = serializer.data
                    data['status'], data['message'] = status.HTTP_200_OK, ""
                else:
                    data['status'], data['message'] = status.HTTP_200_OK, "no result found"
            except Exception as e:
                data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, str(e)
        else:
            data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, "User not found"
    except Exception as e:
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, str(e)
    
    return Response(data)


# new
# @api_view(('GET',))
# def view_sponsor(request):
#     data = {'status': '', 'message': '', 'data': {}}
#     try:
#         sponsor_uuid = request.GET.get('sponsor_uuid')
#         sponsor_secret_key = request.GET.get('sponsor_secret_key')
#         print("sponsor_uuid",sponsor_uuid)
#         print("sponsor_secret_key",sponsor_secret_key)
#         check_user = IsSponsorDetails.objects.filter(uuid=sponsor_uuid, secret_key=sponsor_secret_key)
#         # check_user = IsSponsorDetails.objects.filter(sponsor__uuid=sponsor_uuid, sponsor__secret_key=sponsor_secret_key)
#         print("check_user",check_user)
#         if check_user.exists():
#             print("check_user",check_user)
#             sponsor_instance = check_user.first()
#             serializer = IsSponsorDetailsSerializer(sponsor_instance)
#             data['data'] = [serializer.data]
#             data['status'] = status.HTTP_200_OK
#         else:
#             data['status'], data['message'] = status.HTTP_404_NOT_FOUND, "Sponsor not found"
#     except Exception as e:
#         data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, str(e)
    
#     return Response(data)


# new
@api_view(('GET',))
def view_sponsor(request):
    data = {'status': '', 'message': '', 'data': {},'league_name':''}
    try:
        sponsor_uuid = request.GET.get('sponsor_uuid')
        sponsor_secret_key = request.GET.get('sponsor_secret_key')
        print("sponsor_uuid",sponsor_uuid)
        print("sponsor_secret_key",sponsor_secret_key)
        check_user = IsSponsorDetails.objects.filter(uuid=sponsor_uuid, secret_key=sponsor_secret_key)
        # check_user = IsSponsorDetails.objects.filter(sponsor__uuid=sponsor_uuid, sponsor__secret_key=sponsor_secret_key)
        print("check_user",check_user)
        if check_user.exists():
            # print("check_user",check_user)
            sponsor_instance = check_user.first()
            serializer = IsSponsorDetailsSerializer(sponsor_instance)
            get_user = sponsor_instance.sponsor
            ads_list = Advertisement.objects.filter(created_by=get_user).values()
            data["league_name"] = Leagues.objects.filter(uuid=serializer.data["league_uuid"]).first().name
            data['data'] = [serializer.data]
            data['ads_data'] = list(ads_list)
            data['status'] = status.HTTP_200_OK
        else:
            data['status'], data['message'] = status.HTTP_404_NOT_FOUND, "Sponsor not found"
    except Exception as e:
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, str(e)
    
    return Response(data)


@api_view(('POST',))
def resend_email_sponsor(request):
    data = {'status': '', 'message': '', 'data': []}
    try:
        sponsor_uuid = request.data.get('sponsor_uuid')
        sponsor_secret_key = request.data.get('sponsor_secret_key')
        email = request.data.get('email')
        send_type = "resend"
        league_uuid = request.data.get('league_uuid')
        league_secret_key = request.data.get('league_secret_key')

        check_user = IsSponsorDetails.objects.filter(uuid=sponsor_uuid, secret_key=sponsor_secret_key)
        check_league = Leagues.objects.filter(uuid=league_uuid, secret_key=league_secret_key)
        if check_user.exists() and check_league.exists():
            league = check_league.first().name
            #protocol = 'https' if request.is_secure() else 'http'
            host = request.get_host()
            current_site = f"{protocol}://{host}"
            send_email_status = send_email_for_invite_sponsor(current_site, email, league, send_type)
            if send_email_status is True:
                data['status'], data['message'] = status.HTTP_200_OK, "Send Email successfully"
            else:
                data['status'], data['message'] = status.HTTP_404_NOT_FOUND, f"Somthing is wrong"
        else:
            data['status'], data['message'] = status.HTTP_404_NOT_FOUND, "Sponsor or league not found"
    except Exception as e:
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, str(e)
    
    return Response(data)


@api_view(('GET',))
def list_leagues_for_sponsor(request):
    data = {'status':'','data':'','message':''}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        filter_by = request.GET.get('filter_by')
        search_text = request.GET.get('search_text')
        '''
        registration_open, future, past
        '''
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        if check_user.first().is_organizer:
            leagues = []
            if search_text:
                all_leagues = Leagues.objects.filter(is_created=True).filter(created_by=check_user.first()).filter(Q(name__icontains=search_text))
            else:
                all_leagues = Leagues.objects.filter(is_created=True).filter(created_by=check_user.first())
            today_date = datetime.now()
            if filter_by == "future" :
                all_leagues = all_leagues.filter(registration_start_date__date__gte=today_date).order_by('-id')
            elif filter_by == "past" :
                all_leagues = all_leagues.filter(registration_end_date__date__lte=today_date).order_by('-id')
            elif filter_by == "registration_open" :
                all_leagues = all_leagues.filter(registration_start_date__date__lte=today_date,registration_end_date__date__gte=today_date).order_by('-id')
            
            elif filter_by == "registration_open_date" :
                all_leagues = all_leagues.filter(registration_start_date__date__lte=today_date,registration_end_date__date__gte=today_date).order_by("leagues_start_date")
            elif filter_by == "registration_open_name" :
                all_leagues = all_leagues.filter(registration_start_date__date__lte=today_date,registration_end_date__date__gte=today_date).order_by("name")
            elif filter_by == "registration_open_city" :
                all_leagues = all_leagues.filter(registration_start_date__date__lte=today_date,registration_end_date__date__gte=today_date).order_by("city")
            elif filter_by == "registration_open_state" :
                all_leagues = all_leagues.filter(registration_start_date__date__lte=today_date,registration_end_date__date__gte=today_date).order_by("state")
            elif filter_by == "registration_open_country" :
                all_leagues = all_leagues.filter(registration_start_date__date__lte=today_date,registration_end_date__date__gte=today_date).order_by("country")
            
            else:
                all_leagues = all_leagues
            leagues = all_leagues.values('uuid','secret_key','name','location','leagues_start_date','leagues_end_date',
                               'registration_start_date','registration_end_date','team_type__name','team_person__name','any_rank','start_rank','end_rank',
                               "street","city","state","postal_code","country","complete_address","latitude","longitude")
            if len(leagues) == 0:
                data["status"], data['data'], data["message"] = status.HTTP_200_OK, leagues, "You have no create Tournament"
            else:
                data["status"], data['data'], data["message"] = status.HTTP_200_OK, leagues, "League data"
        else:
            data["status"], data['data'], data["message"] = status.HTTP_404_NOT_FOUND, "","User not found."
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


####### turnaments ######
@api_view(('GET',))
def my_league(request):
    data = {'status':'','data':[], 'message':''}
    try:
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        search_text = request.GET.get('search_text')
        filter_by = request.GET.get('filter_by')
        check_user = User.objects.filter(secret_key=user_secret_key,uuid=user_uuid)
        today_date = datetime.now()
        if check_user.exists():
            get_user = check_user.first()
            all_leagues = Leagues.objects.filter(is_created= True, created_by=get_user).exclude(play_type = "Individual Match Play").order_by('-id')
            if search_text:
               all_leagues = all_leagues.filter(name__icontains=search_text)
            else:
                all_leagues = all_leagues
            
            if filter_by == "future" :
                all_leagues = all_leagues.filter(Q(registration_start_date__date__lte=today_date, registration_end_date__date__gte=today_date) | Q(registration_start_date__date__gte=today_date))
            elif filter_by == "past" :
                all_leagues = all_leagues.filter(leagues_end_date__date__lte=today_date, is_complete=True)
            elif filter_by == "registration_open" :
                all_leagues = all_leagues.filter(leagues_start_date__date__lte=today_date, leagues_end_date__date__gte=today_date, is_complete=False)
                
            leagues = all_leagues.values('id','uuid','secret_key','name','location','leagues_start_date','leagues_end_date',
                               'registration_start_date','registration_end_date','team_type__name','team_person__name','any_rank','start_rank','end_rank',
                               "street","city","state","postal_code","country","complete_address","latitude","longitude","image","others_fees", "league_type","registration_fee")
            
            inditour_data = []
            individual_match = []
            if get_user.is_player:
                get_player = Player.objects.filter(player=get_user).first()
                team_list = list(get_player.team.all().values_list("id", flat=True))
                individual_match =  Leagues.objects.filter(is_created=True, created_by=get_user, play_type="Individual Match Play")
                
            for tour in individual_match:
                team_list2 = list(tour.registered_team.all().values_list("id", flat=True))
                for team_id in team_list2:
                    if team_id in team_list:
                        tour_data = {
                            'id': tour.id,
                            'uuid': tour.uuid,
                            'secret_key': tour.secret_key,
                            'name': tour.name,
                            'location': tour.location,
                            'leagues_start_date': tour.leagues_start_date,
                            'leagues_end_date': tour.leagues_end_date,
                            'registration_start_date': tour.registration_start_date,
                            'registration_end_date': tour.registration_end_date,
                            'team_type__name': tour.team_type.name,
                            'team_person__name': tour.team_person.name,
                            "street": tour.street,
                            "city": tour.city,
                            "state": tour.state,
                            "postal_code": tour.postal_code,
                            "country": tour.country,
                            "complete_address": tour.complete_address,
                            "latitude": tour.latitude,
                            "longitude": tour.longitude,
                            "others_fees": tour.others_fees,
                            "league_type": tour.league_type,
                            "registration_fee": tour.registration_fee,
                            
                        }
                        if tour.image:
                            tour_data["image"] = tour.image
                        else:
                            tour_data["image"] = None
                        registered_team = tour.registered_team.all().values_list("id", flat=True)
                        team1_id = registered_team[0]
                        players = Player.objects.filter(team__id=team1_id)
                        team1_players = []
                        for player in players:
                            player_name = f"{player.player.first_name} {player.player.last_name}"
                            team1_players.append(player_name)
                        tour_data["team_1_players"] = team1_players
                        team2_id = registered_team[1]
                        players = Player.objects.filter(team__id=team2_id)
                        team2_players = []
                        for player in players:
                            player_name = f"{player.player.first_name} {player.player.last_name}"
                            team2_players.append(player_name)
                        tour_data["team_2_players"] = team2_players
                        inditour_data.append(tour_data)
                    else:
                        pass
                                      
            sorted_data = sorted(inditour_data, key=lambda x: x['id'], reverse=True)
            unique_dicts = []
            prev_id = None
            for d in sorted_data:
                if d['id'] != prev_id:
                    unique_dicts.append(d)
                    prev_id = d['id']            
            leagues = list(leagues) + unique_dicts            
            output = []
            grouped_data = {}
            for item in list(leagues):
                item["is_reg_diable"] = True
                match_ = Tournament.objects.filter(leagues_id=item["id"]).values()
                if match_.exists():
                    item["is_reg_diable"] = False
                le = Leagues.objects.filter(id=item["id"],  ).first()
                reg_team =le.registered_team.all().count()
                max_team = le.max_number_team
                if max_team <= reg_team:
                    item["is_reg_diable"] = False
                key = item['name']
                if key not in grouped_data:
                    grouped_data[key] = {
                                        'name': item['name'], 
                                        'lat':item['latitude'], 
                                        'long':item["longitude"],
                                        'registration_start_date':item["registration_start_date"],
                                        'registration_end_date':item["registration_end_date"],
                                        'leagues_start_date':item["leagues_start_date"],
                                        'leagues_end_date':item["leagues_end_date"],
                                        'location':item["location"],
                                        'image':item["image"],
                                        'type': [item['team_type__name']], 
                                        'data': [item]
                                        }
                else:
                    grouped_data[key]['type'].append(item['team_type__name'])
                    grouped_data[key]['data'].append(item)
            for key, value in grouped_data.items():
                output.append(value)
            leagues = output 
            for item in leagues:
                item["data"] = sorted(item["data"], key=lambda x: x["id"], reverse=True)

            leagues_sorted = sorted(leagues, key=lambda x: x["data"][0]["id"], reverse=True)
            
            data['status'], data['data'], data['message'] = status.HTTP_200_OK, leagues_sorted, f"Data found"
        else:
            data['status'], data['data'], data['message'] = status.HTTP_400_BAD_REQUEST, [], f"user not found"
    except Exception as e :
        data['status'], data['data'], data['message'] = status.HTTP_400_BAD_REQUEST, [], f"{e}"
    return Response(data)


@api_view(('GET',))
def tournament_schedule(request):
    data = {'status':'','data':[], 'message':''}
    try:
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        check_user = User.objects.filter(secret_key=user_secret_key,uuid=user_uuid)
        today_date = timezone.now()
        # print(check_user)
        if check_user.exists():
            get_user = check_user.first()
            all_leagues = Leagues.objects.exclude(registration_end_date__date__lte=today_date)
            
            if get_user.is_coach is True or get_user.is_team_manager is True or get_user.is_player is True or get_user.is_organizer is True:
                all_leagues_for_join = all_leagues.filter(registered_team__created_by=get_user).values('uuid','secret_key','name','location','leagues_start_date','leagues_end_date',
                               'registration_start_date','registration_end_date','team_type__name','team_person__name',
                               "street","city","state","postal_code","country","complete_address","latitude","longitude")
                save_leagues = SaveLeagues.objects.filter(created_by=get_user).values("ch_league_id")
                leagues_ids = [i["ch_league_id"] for i in save_leagues]
                all_leagues_for_save = all_leagues.filter(id__in=leagues_ids).values('uuid','secret_key','name','location','leagues_start_date','leagues_end_date',
                               'registration_start_date','registration_end_date','team_type__name','team_person__name',
                               "street","city","state","postal_code","country","complete_address","latitude","longitude")
                all_created_leagues = Leagues.objects.exclude(registration_end_date__date__lte=today_date).filter(created_by=get_user).values('uuid','secret_key','name','location','leagues_start_date','leagues_end_date',
                               'registration_start_date','registration_end_date','team_type__name','team_person__name',
                               "street","city","state","postal_code","country","complete_address","latitude","longitude")
                
                for i in all_created_leagues:
                    i["league_for"] = "Tournament Create"
                for k in all_leagues_for_save:
                    k["league_for"] = "Tournament Saved"
                for l in all_leagues_for_join:
                    l["league_for"] = "Tournament Joined"
                my_all_schedule = list(all_created_leagues)+list(all_leagues_for_save)+list(all_leagues_for_join)
                output = {}
                output_list = []
                for item in my_all_schedule:
                    key = (item["name"])
                    league_for = item["league_for"]
                    if key in output:
                        output[key].append(league_for)
                    else:
                        output[key] = [league_for]
                # print(output)
                # Combine the league_for values into a comma-separated string
                for key in output:
                    output[key] = ",".join(sorted(set(output[key])))
                    counter = 0
                    for k in my_all_schedule:
                        if k["name"] == key and counter==0:
                            k["league_for"] = output[key]
                            output_list.append(k)
                            counter += 1
                        if counter != 0:
                            break
                print(output_list)
                data['status'], data['data'], data['message'] = status.HTTP_200_OK, output_list, f"Data found"
            else:
                data['status'], data['data'], data['message'] = status.HTTP_200_OK, output_list, f"you have no schedule"
        else:
            data['status'], data['data'], data['message'] = status.HTTP_400_BAD_REQUEST, [], f"user not found"
    except Exception as e :
        data['status'], data['data'], data['message'] = status.HTTP_400_BAD_REQUEST, [], f"{e}"
    return Response(data)         


#### for admin##############
@api_view(('GET',))
def get_organizer_details(request):
    data = {'status':'', 'message':''}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if check_user.exists():
            get_user = check_user.first()
            if get_user.is_admin or get_user.is_organizer:
                data['data'] = list(User.objects.filter(is_organizer=True).values('id','uuid','secret_key','username','first_name','last_name','email','phone','gender','user_birthday','role','rank','image','street','city','state','country','postal_code'))
                data['message'] = "Data found"
                data['status'] = status.HTTP_200_OK
            else:
                data['status'] = status.HTTP_404_NOT_FOUND
                data['message'] = "User is not an organizer or admin"
        else:
            data['status'] = status.HTTP_404_NOT_FOUND
            data['message'] = "User not found."
        return Response(data)
    except Exception as e:
        data['status'] = status.HTTP_400_BAD_REQUEST
        data['message'] = f"{e}"
    return Response(data)
 

@api_view(('GET',))
def get_sponsor_details(request):
    data = {'status':'', 'message':''}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if check_user.exists():
            get_user = check_user.first()
            if get_user.is_admin == True:
                data['data'] = list(User.objects.filter(is_sponsor=True).values('uuid','secret_key','username','first_name','last_name','email','phone','gender','user_birthday','role','rank','image','street','city','state','country','postal_code','fb_link','twitter_link','youtube_link','instagram_link'))
                data['message'] = "Data found"
                data['status'] = status.HTTP_200_OK
            else:
                data['status'] = status.HTTP_404_NOT_FOUND
                data['message'] = "User is not a sponsor"
        else:
            data['status'] = status.HTTP_404_NOT_FOUND
            data['message'] = "User not found."
        return Response(data)
    except Exception as e:
        data['status'] = status.HTTP_400_BAD_REQUEST
        data['message'] = f"{e}"
    return Response(data)


@api_view(('GET',))
def get_admin_details(request):
    data = {'status':'', 'message':''}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if check_user.exists():
            get_user = check_user.first()
            if get_user.is_admin == True:
                data['data'] = list(User.objects.filter(is_admin=True).values('uuid','secret_key','username','first_name','last_name','email','phone','gender','user_birthday','role','rank','image','street','city','state','country','postal_code','fb_link','twitter_link','youtube_link','instagram_link'))
                data['message'] = "Data found"
                data['status'] = status.HTTP_200_OK
            else:
                data['status'] = status.HTTP_404_NOT_FOUND
                data['message'] = "User is not admin."
        else:
            data['status'] = status.HTTP_404_NOT_FOUND
            data['message'] = "User not found."
        return Response(data)
    except Exception as e:
        data['status'] = status.HTTP_400_BAD_REQUEST
        data['message'] = f"{e}"
    return Response(data)


@api_view(('GET',))
def get_ambassador_details(request):
    data = {'status':'', 'message':''}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if check_user.exists():
            get_user = check_user.first()
            if get_user.is_admin == True:
                data['data'] = list(User.objects.filter(is_ambassador=True).values('uuid','secret_key','username','first_name','last_name','email','phone','gender','user_birthday','role','rank','image','street','city','state','country','postal_code','fb_link','twitter_link','youtube_link','instagram_link'))
                data['message'] = "Data found"
                data['status'] = status.HTTP_200_OK
            else:
                data['status'] = status.HTTP_404_NOT_FOUND
                data['message'] = "User is not an ambassador."
        else:
            data['status'] = status.HTTP_404_NOT_FOUND
            data['message'] = "User not found."
        return Response(data)
    except Exception as e:
        data['status'] = status.HTTP_400_BAD_REQUEST
        data['message'] = f"{e}"
    return Response(data)


################# remove form sponsor ###############
@api_view(('POST',))
def remove_organizer(request):
    data = {'status':'', 'message':''}
    try:        
        user_uuid = request.POST.get('user_uuid')
        user_secret_key = request.POST.get('user_secret_key')
        r_uuid = request.POST.get('r_uuid')
        r_secret_key = request.POST.get('r_secret_key')
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        r_user = User.objects.filter(uuid=r_uuid, secret_key=r_secret_key)
        if check_user.exists() and r_user.exists() and check_user.first().is_admin:
            r_user.update(is_organizer=False)
            data['message'] = "Remove from organizer"
            data['status'] = status.HTTP_200_OK
        else:
            data['status'] = status.HTTP_404_NOT_FOUND
            data['message'] = "User not found."
        return Response(data)
    except Exception as e:
        data['status'] = status.HTTP_400_BAD_REQUEST
        data['message'] = f"{e}"
    return Response(data)

    
@api_view(('POST',))
def remove_sponsor(request):
    data = {'status':'', 'message':''}
    try:        
        user_uuid = request.POST.get('user_uuid')
        user_secret_key = request.POST.get('user_secret_key')
        r_uuid = request.POST.get('r_uuid')
        r_secret_key = request.POST.get('r_secret_key')
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        r_user = User.objects.filter(uuid=r_uuid, secret_key=r_secret_key)
        if check_user.exists() and r_user.exists():
            IsSponsorDetails.objects.filter(sponsor=r_user.first()).delete()
            r_user.update(is_sponsor=False, role="",is_verified=False)
            data['message'] = "Remove from Sponsor"
            data['status'] = status.HTTP_200_OK
        else:
            data['status'] = status.HTTP_404_NOT_FOUND
            data['message'] = "User not found."
        return Response(data)
    except Exception as e:
        data['status'] = status.HTTP_400_BAD_REQUEST
        data['message'] = f"{e}"
    return Response(data)


@api_view(('POST',))
def remove_admin(request):
    data = {'status':'', 'message':''}
    try:        
        user_uuid = request.POST.get('user_uuid')
        user_secret_key = request.POST.get('user_secret_key')
        r_uuid = request.POST.get('r_uuid')
        r_secret_key = request.POST.get('r_secret_key')
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        r_user = User.objects.filter(uuid=r_uuid, secret_key=r_secret_key)
        if check_user.exists() and r_user.exists() and check_user.first().is_admin:
            r_user.update(is_admin=False)
            data['message'] = "Remove from admin"
            data['status'] = status.HTTP_200_OK
        else:
            data['status'] = status.HTTP_404_NOT_FOUND
            data['message'] = "User not found."
        return Response(data)
    except Exception as e:
        data['status'] = status.HTTP_400_BAD_REQUEST
        data['message'] = f"{e}"
    return Response(data)

    
@api_view(('POST',))
def remove_ambassador(request):
    data = {'status':'', 'message':''}
    try:        
        user_uuid = request.POST.get('user_uuid')
        user_secret_key = request.POST.get('user_secret_key')
        r_uuid = request.POST.get('r_uuid')
        r_secret_key = request.POST.get('r_secret_key')
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        r_user = User.objects.filter(uuid=r_uuid, secret_key=r_secret_key)
        if check_user.exists() and r_user.exists() and check_user.first().is_admin:
            r_user.update(is_ambassador=False)
            data['message'] = "Remove from ambassador"
            data['status'] = status.HTTP_200_OK
        else:
            data['status'] = status.HTTP_404_NOT_FOUND
            data['message'] = "User not found."
        return Response(data)
    except Exception as e:
        data['status'] = status.HTTP_400_BAD_REQUEST
        data['message'] = f"{e}"
    return Response(data)


# added 
@api_view(('POST',))
def check_invited_code(request):
    data = {'status':'', 'message':''}
    try:        
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        league_uuid = request.data.get('league_uuid')
        league_secret_key = request.data.get('league_secret_key')
        invited_code = request.data.get('invited_code')
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        check_league = Leagues.objects.filter(uuid=league_uuid, secret_key=league_secret_key)
        if check_user.exists() and check_league.exists():
            get_league = check_league.first()
            if get_league.invited_code == invited_code:
                data['status'], data['message'] = status.HTTP_200_OK, "Successfully matched."
            else:
                data['status'], data['message'] = status.HTTP_403_FORBIDDEN, "Didn't match."
        else:
            data['status'] = status.HTTP_404_NOT_FOUND
            data['message'] = "User or league not found"
        return Response(data)
    except Exception as e:
        data['status'] = status.HTTP_400_BAD_REQUEST
        data['message'] = f"{e}"
    return Response(data)


@api_view(('GET',))
def del_code(request):
    # TournamentSetsResult.objects.all().delete()
    return Response({"data":"data"})


###########updated view league############
@api_view(('GET',))
def view_playtype_details(request):    
    data = {
            'status':'',
            'create_group_status':False,
            'max_team': None,
            'total_register_team':None,
            'is_organizer': False,
            'is_register':False,
            'sub_organizer_data':[],
            'organizer_name_data':[],
            'invited_code':None,
            'winner_team': 'Not Declared',
            'data':[],
            'tournament_detais':[],
            'message':''            
            }
    user_uuid = request.GET.get('user_uuid')
    user_secret_key = request.GET.get('user_secret_key')
    league_uuid = request.GET.get('league_uuid')
    league_secret_key = request.GET.get('league_secret_key')
    protocol = 'https'
    host = request.get_host()
    media_base_url = f"{protocol}://{host}{settings.MEDIA_URL}"
    '''
    registration_open, future, past
    '''
    check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
    check_leagues = Leagues.objects.filter(uuid=league_uuid,secret_key=league_secret_key)
    if check_user.exists() and check_leagues.exists():
        leagues = check_leagues.values('uuid','secret_key','name','location','leagues_start_date','leagues_end_date',
                            'registration_start_date','registration_end_date','team_type__name','team_person__name',
                            "street","city","state","postal_code","country","complete_address","latitude","longitude","play_type","registration_fee","description","image","others_fees", "league_type")
        league = check_leagues.first()
        get_user = check_user.first()

        today_date = datetime.today().date()
        if league.registration_end_date not in [None, "null", "", "None"]:
            if league.registration_end_date.date() >= today_date and league.league_type != "Invites only" and league.max_number_team > league.registered_team.count() and not league.is_complete:
                data["is_register"] = True
        
        organizers = list(User.objects.filter(id=league.created_by.id).values('id','uuid','secret_key','username','first_name','last_name','email','phone','gender','user_birthday','role','rank','image','street','city','state','country','postal_code'))
        sub_organizer_data = list(league.add_organizer.all().values('id','uuid','secret_key','username','first_name','last_name','email','phone','gender','user_birthday','role','rank','image','street','city','state','country','postal_code'))
        
        organizer_list = organizers + sub_organizer_data
        for nu in organizer_list:
            nu["phone"] = str(nu["phone"])
        data['sub_organizer_data'] = organizer_list
        
        organizer_list = []
        for org in data['sub_organizer_data']:
            first_name = org["first_name"]
            last_name = org["last_name"]
            if not first_name:
                first_name = " "
            if not last_name:
                last_name = " "
            name = f"{first_name} {last_name}"
            organizer_list.append(name)
        data['organizer_name_data'] = organizer_list

        sub_org_list = list(league.add_organizer.all().values_list("id", flat=True))  
        if get_user == league.created_by or get_user.id in sub_org_list:
            data['is_organizer'] =  True
            data['invited_code'] =  league.invited_code
        all_team = check_leagues.first().registered_team.all()
        
        teams = []
        for t in all_team:
            team_d = Team.objects.filter(id=t.id).values()
            teams.append(team_d[0])
        for im in teams:
            if im["team_image"] != "":
                img_str = im["team_image"]
                im["team_image"] = f"{media_base_url}{img_str}"
        
        data['teams'] = teams        
        data['max_team'] =  league.max_number_team
        data['total_register_team'] =  league.registered_team.all().count()
        data['tournament_detais'] = LeaguesPlayType.objects.filter(league_for = check_leagues.first()).values()
        data["create_group_status"] = get_user.is_organizer and check_leagues.first().created_by == get_user
        data['data'] = leagues
        if league.winner_team:
            data['winner_team'] = league.winner_team.name
        data['message'] = "Play type details fetched successfully."
        data['status'] = status.HTTP_200_OK
    else:
        data["status"], data["message"] = status.HTTP_404_NOT_FOUND, f"User or league not found."
    return Response(data)


@api_view(("GET",))
def view_match_details(request):
    data = {
             'status':'',             
             'message':'',
             'match':[]
             }
    user_uuid = request.GET.get('user_uuid')
    user_secret_key = request.GET.get('user_secret_key')
    league_uuid = request.GET.get('league_uuid')
    league_secret_key = request.GET.get('league_secret_key')
    protocol = 'https' if request.is_secure() else 'http'
    host = request.get_host()
    media_base_url = f"{protocol}://{host}{settings.MEDIA_URL}"
    '''
    registration_open, future, past
    '''
    check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
    check_leagues = Leagues.objects.filter(uuid=league_uuid,secret_key=league_secret_key)
    if check_user.exists() and check_leagues.exists():
        league = check_leagues.first()
        get_user = check_user.first()
        tournament_details = Tournament.objects.filter(leagues=check_leagues.first()).order_by("match_number").values("id","match_number","uuid","secret_key","leagues__name"
                                                                                                                        ,"team1_id", "team2_id", "team1__team_image", "team2__team_image", 
                                                                                                                        "team1__name", "team2__name", "winner_team_id", "winner_team__name", 
                                                                                                                        "playing_date_time","match_type","group__court","is_completed"
                                                                                                                        ,"elimination_round","court_sn","set_number","court_num","points","is_drow")
        
        sub_org_list = list(league.add_organizer.all().values_list("id", flat=True))
        for sc in tournament_details:
            if sc["group__court"] is None:
                sc["group__court"] = sc["court_sn"]

            team_1_player = list(Player.objects.filter(team__id=sc["team1_id"]).values_list("player_id", flat=True))
            team_2_player = list(Player.objects.filter(team__id=sc["team2_id"]).values_list("player_id", flat=True))
            team_1_created_by = Team.objects.filter(id=sc["team1_id"]).first().created_by
            team_2_created_by = Team.objects.filter(id=sc["team2_id"]).first().created_by

            if (get_user == league.created_by) or (get_user.id in sub_org_list) or (get_user.id in team_1_player) or (get_user == team_1_created_by) or (get_user.id in team_2_player) or ((get_user == team_2_created_by)):
                sc["is_edit"] = True
            else:
                sc["is_edit"] = False

            check_score_approved = TournamentScoreApproval.objects.filter(tournament__id=sc["id"], team1_approval=True, team2_approval=True)

            if check_score_approved.exists():
                sc["is_score_approved"] = True
                sc["is_edit"] = False
            else:
                sc["is_score_approved"] = False                    
            
            check_score_reported = TournamentScoreReport.objects.filter(tournament__id=sc["id"], status="Pending")
            if check_score_reported.exists():
                sc["is_score_reported"] = True 
                if (get_user == league.created_by) or (get_user.id in sub_org_list):
                    sc["is_edit"] = True
                else:
                    sc["is_edit"] = False
            else:
                sc["is_score_reported"] = False   

            team1_approval = TournamentScoreApproval.objects.filter(tournament__id=sc["id"], team1_approval=True).exists()
            team2_approval = TournamentScoreApproval.objects.filter(tournament__id=sc["id"], team1_approval=True).exists()
            check_score_set = TournamentSetsResult.objects.filter(tournament__id=sc["id"])

            if check_score_set.exists() and not team1_approval and ((get_user.id in team_1_player) or (get_user == team_1_created_by)):
                sc["is_button_show"] = True
            
            elif check_score_set.exists() and not team2_approval and ((get_user.id in team_2_player) or (get_user == team_2_created_by)):
                sc["is_button_show"] = True
            else:
                sc["is_button_show"] = False

            if sc["team1__team_image"] != "":
                img_str = sc["team1__team_image"]
                sc["team1__team_image"] = f"{media_base_url}{img_str}"
            if sc["team2__team_image"] != "":
                img_str = sc["team2__team_image"]
                sc["team2__team_image"] = f"{media_base_url}{img_str}"
            #"set_number","court_num","points"
            set_list_team1 = []
            set_list_team2 = []
            score_list_team1 = []
            score_list_team2 = []
            win_status_team1 = []
            win_status_team2 = []
            is_completed_match = sc["is_completed"]
            is_win_match_team1 = False
            is_win_match_team2 = False
            team1_name = sc["team1__name"]
            team2_name = sc["team2__name"]
            if sc["team1_id"] == sc["winner_team_id"] and sc["winner_team_id"] is not None:
                is_win_match_team1 = True
                is_win_match_team2 = False
            elif sc["team2_id"] == sc["winner_team_id"] and sc["winner_team_id"] is not None:
                is_win_match_team2 = True
                is_win_match_team1 = False
            # else:
            #     is_win_match_team2 = False
            #     is_win_match_team1 = False
            for s in range(sc["set_number"]):
                index = s+1
                set_str = f"s{index}"
                set_list_team1.append(set_str)
                set_list_team2.append(set_str)
                score_details_for_set = TournamentSetsResult.objects.filter(tournament_id=sc["id"],set_number=index).values()
                if len(score_details_for_set)!=0:
                    team_1_score = score_details_for_set[0]["team1_point"]
                    team_2_score = score_details_for_set[0]["team2_point"]
                else:
                    team_1_score = None
                    team_2_score = None
                score_list_team1.append(team_1_score)
                score_list_team2.append(team_2_score)
                if team_1_score is not None and team_2_score is not None:
                    if team_1_score >= team_2_score:
                        win_status_team1.append(True)
                        win_status_team2.append(False)
                    else:
                        win_status_team1.append(False)
                        win_status_team2.append(True)
                else:
                    win_status_team1.append(False)
                    win_status_team2.append(False)
            score = [
                {
                    "name": team1_name,"set": set_list_team2,
                    "score": score_list_team1,"win_status": win_status_team1,
                    "is_win": is_win_match_team1,"is_completed": is_completed_match,
                    "is_drow":sc["is_drow"]
                    },
                {
                "name": team2_name,"set": set_list_team2,
                "score": score_list_team2,"win_status": win_status_team1,
                "is_win": is_win_match_team2,"is_completed": is_completed_match,
                "is_drow":sc["is_drow"]
                }
                ]
            sc["score"] = score
            # print(score)
        
            # List to store data for the point table
        
        data['match'] = tournament_details
        data['message'] = "Match details fetched successfully."
        data['status'] = status.HTTP_200_OK
    else:
        data["status"], data["message"] = status.HTTP_404_NOT_FOUND, f"User or league not found."
    return Response(data)


@api_view(("GET",))
def view_elimination_details(request):
    data = {
             'status':'',             
             'elemination':[], 
             'semi_final':[],
             'final':[], 
             'message':''
             }
    user_uuid = request.GET.get('user_uuid')
    user_secret_key = request.GET.get('user_secret_key')
    league_uuid = request.GET.get('league_uuid')
    league_secret_key = request.GET.get('league_secret_key')
    protocol = 'https' if request.is_secure() else 'http'
    host = request.get_host()
    media_base_url = f"{protocol}://{host}{settings.MEDIA_URL}"
    '''
    registration_open, future, past
    '''
    check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
    check_leagues = Leagues.objects.filter(uuid=league_uuid,secret_key=league_secret_key)
    if check_user.exists() and check_leagues.exists():
        league = check_leagues.first()
        get_user = check_user.first()
        sub_org_list = list(league.add_organizer.all().values_list("id", flat=True))
        knock_out_tournament_elimination_data = Tournament.objects.filter(leagues=check_leagues.first(),match_type="Elimination Round").values("id","uuid","secret_key","match_number","match_type","elimination_round","team1__name", "team1_id", "team2_id"
                                                                                                            ,"team1__team_image","team2__name","team2__team_image","winner_team__name", "winner_team_id", "loser_team_id", "winner_team__team_image","loser_team__name","loser_team__team_image","is_completed","play_ground_name")
        for ele_tour in knock_out_tournament_elimination_data:

            team_1_player = list(Player.objects.filter(team__id=ele_tour["team1_id"]).values_list("player_id", flat=True))
            team_2_player = list(Player.objects.filter(team__id=ele_tour["team2_id"]).values_list("player_id", flat=True))
            team_1_created_by = Team.objects.filter(id=ele_tour["team1_id"]).first().created_by
            team_2_created_by = Team.objects.filter(id=ele_tour["team2_id"]).first().created_by

            # ele_tour["is_edit"] = get_user.is_organizer and check_leagues.first().created_by == get_user or ele_tour["team1_id"] == get_user.id or ele_tour["team2_id"] == get_user.id
            if get_user == league.created_by or get_user.id in sub_org_list or ele_tour["team1_id"] == get_user.id or ele_tour["team2_id"] == get_user.id:
                ele_tour["is_edit"] = True
            else:
                ele_tour["is_edit"] = False
            
            check_score_approved = TournamentScoreApproval.objects.filter(tournament__id=ele_tour["id"], team1_approval=True, team2_approval=True)

            if check_score_approved.exists():
                ele_tour["is_score_approved"] = True
                ele_tour["is_edit"] = False
            else:
                ele_tour["is_score_approved"] = False                    
            
            check_score_reported = TournamentScoreReport.objects.filter(tournament__id=ele_tour["id"], status="Pending")
            if check_score_reported.exists():
                ele_tour["is_score_reported"] = True 
                if (get_user == league.created_by) or (get_user.id in sub_org_list):
                    ele_tour["is_edit"] = True
                else:
                    ele_tour["is_edit"] = False
            else:
                ele_tour["is_score_reported"] = False   

            team1_approval = TournamentScoreApproval.objects.filter(tournament__id=ele_tour["id"], team1_approval=True).exists()
            team2_approval = TournamentScoreApproval.objects.filter(tournament__id=ele_tour["id"], team1_approval=True).exists()
            check_score_set = TournamentSetsResult.objects.filter(tournament__id=ele_tour["id"])

            if check_score_set.exists() and not team1_approval and ((get_user.id in team_1_player) or (get_user == team_1_created_by)):
                ele_tour["is_button_show"] = True
            
            elif check_score_set.exists() and not team2_approval and ((get_user.id in team_2_player) or (get_user == team_2_created_by)):
                ele_tour["is_button_show"] = True
            else:
                ele_tour["is_button_show"] = False

            score = [{"name": "","set": [],"score": [],"win_status": [],"is_win": True,"is_completed": True},{"name": "","set": [],"score": [],"win_status": [],"is_win": True,"is_completed": True}]
            
            if ele_tour["team1_id"] == ele_tour["winner_team_id"] and ele_tour["winner_team_id"] is not None:
                score[0]["is_win"] = True
                score[1]["is_win"] = False
            elif ele_tour["team2_id"] == ele_tour["winner_team_id"] and ele_tour["winner_team_id"] is not None:
                score[1]["is_win"] = True
                score[0]["is_win"] = False
            else:
                score[1]["is_win"] = None
                score[0]["is_win"] = None
            score_details = TournamentSetsResult.objects.filter(tournament_id=ele_tour["id"]).values()
            score[0]["name"] = ele_tour["team1__name"]
            score[1]["name"] = ele_tour["team2__name"]
            score[0]["set"] = ["s1","s2","s3"]
            score[1]["set"] = ["s1","s2","s3"]
            for l__ in range(3):
                
                if l__ < len(score_details):
                    l = {"team1_point":score_details[l__]["team1_point"],"team2_point":score_details[l__]["team2_point"]}
                else:
                    l = {"team1_point":None,"team2_point":None}
                
                score[0]["score"].append(l["team1_point"])
                score[1]["score"].append(l["team2_point"])
                
                if l["team1_point"] == None or l["team1_point"] == None:
                    score[0]["win_status"].append(None)
                    score[1]["win_status"].append(None)
                elif l["team1_point"] > l["team2_point"]:
                    score[0]["win_status"].append(True)
                    score[1]["win_status"].append(False)
                else:
                    score[0]["win_status"].append(False)
                    score[1]["win_status"].append(True)
            ele_tour["score"] = score
        data['elemination'] = list(knock_out_tournament_elimination_data)

        #this data for Semi Final   
        knock_out_semifinal_tournament_data = Tournament.objects.filter(leagues=check_leagues.first(),match_type="Semi Final").values("id","uuid","secret_key","match_number","match_type","elimination_round","team1__name", "team1_id", "team2_id"
                                                                                                        ,"team1__team_image","team2__name","team2__team_image","winner_team__name", "winner_team_id", "loser_team_id", "winner_team__team_image","loser_team__name","loser_team__team_image","is_completed","play_ground_name")
        for semi_tour in knock_out_semifinal_tournament_data:
            team_1_player = list(Player.objects.filter(team__id=semi_tour["team1_id"]).values_list("player_id", flat=True))
            team_2_player = list(Player.objects.filter(team__id=semi_tour["team2_id"]).values_list("player_id", flat=True))
            team_1_created_by = Team.objects.filter(id=semi_tour["team1_id"]).first().created_by
            team_2_created_by = Team.objects.filter(id=semi_tour["team2_id"]).first().created_by

            if get_user == league.created_by or get_user.id in sub_org_list or semi_tour["team1_id"] == get_user.id or semi_tour["team2_id"] == get_user.id:
                semi_tour["is_edit"] = True
            else:
                semi_tour["is_edit"] = False
            
            check_score_approved = TournamentScoreApproval.objects.filter(tournament__id=semi_tour["id"], team1_approval=True, team2_approval=True)

            if check_score_approved.exists():
                semi_tour["is_score_approved"] = True
                semi_tour["is_edit"] = False
            else:
                semi_tour["is_score_approved"] = False                    
            
            check_score_reported = TournamentScoreReport.objects.filter(tournament__id=semi_tour["id"], status="Pending")

            if check_score_reported.exists():
                semi_tour["is_score_reported"] = True 
                if (get_user == league.created_by) or (get_user.id in sub_org_list):
                    semi_tour["is_edit"] = True
                else:
                    semi_tour["is_edit"] = False
            else:
                semi_tour["is_score_reported"] = False   

            team1_approval = TournamentScoreApproval.objects.filter(tournament__id=semi_tour["id"], team1_approval=True).exists()
            team2_approval = TournamentScoreApproval.objects.filter(tournament__id=semi_tour["id"], team1_approval=True).exists()
            check_score_set = TournamentSetsResult.objects.filter(tournament__id=semi_tour["id"])

            if check_score_set.exists() and not team1_approval and ((get_user.id in team_1_player) or (get_user == team_1_created_by)):
                semi_tour["is_button_show"] = True
            
            elif check_score_set.exists() and not team2_approval and ((get_user.id in team_2_player) or (get_user == team_2_created_by)):
                semi_tour["is_button_show"] = True
            else:
                semi_tour["is_button_show"] = False

            score = [{"name": "","set": [],"score": [],"win_status": [],"is_win": True,"is_completed": True},{"name": "","set": [],"score": [],"win_status": [],"is_win": True,"is_completed": True}]
            
            if semi_tour["team1_id"] == semi_tour["winner_team_id"] and semi_tour["winner_team_id"] is not None:
                score[0]["is_win"] = True
                score[1]["is_win"] = False
            elif semi_tour["team2_id"] == semi_tour["winner_team_id"] and semi_tour["winner_team_id"] is not None:
                score[1]["is_win"] = True
                score[0]["is_win"] = False
            else:
                score[1]["is_win"] = None
                score[0]["is_win"] = None
            score_details = TournamentSetsResult.objects.filter(tournament_id=semi_tour["id"]).values()
            score[0]["name"] = semi_tour["team1__name"]
            score[1]["name"] = semi_tour["team2__name"]
            score[0]["set"] = ["s1","s2","s3"]
            score[1]["set"] = ["s1","s2","s3"]
            for l__ in range(3):
                
                if l__ < len(score_details):
                    l = {"team1_point":score_details[l__]["team1_point"],"team2_point":score_details[l__]["team2_point"]}
                else:
                    l = {"team1_point":None,"team2_point":None}
                
                score[0]["score"].append(l["team1_point"])
                score[1]["score"].append(l["team2_point"])
                
                if l["team1_point"] == None or l["team1_point"] == None:
                    score[0]["win_status"].append(None)
                    score[1]["win_status"].append(None)
                elif l["team1_point"] > l["team2_point"]:
                    score[0]["win_status"].append(True)
                    score[1]["win_status"].append(False)
                else:
                    score[0]["win_status"].append(False)
                    score[1]["win_status"].append(True)
            semi_tour["score"] = score
        data['semi_final'] = list(knock_out_semifinal_tournament_data)

        #this data for Final 
        knock_out_final_tournament_data = Tournament.objects.filter(leagues=check_leagues.first(),match_type="Final").values("id","uuid","secret_key","match_number","match_type","elimination_round","team1__name", "team1_id", "team2_id"
                                                                                                        ,"team1__team_image","team2__name","team2__team_image","winner_team__name", "winner_team_id", "loser_team_id", "winner_team__team_image","loser_team__name","loser_team__team_image","is_completed","play_ground_name")
        for final_tour in knock_out_final_tournament_data:
            team_1_player = list(Player.objects.filter(team__id=final_tour["team1_id"]).values_list("player_id", flat=True))
            team_2_player = list(Player.objects.filter(team__id=final_tour["team2_id"]).values_list("player_id", flat=True))
            team_1_created_by = Team.objects.filter(id=final_tour["team1_id"]).first().created_by
            team_2_created_by = Team.objects.filter(id=final_tour["team2_id"]).first().created_by

            if get_user == league.created_by or get_user.id in sub_org_list or final_tour["team1_id"] == get_user.id or final_tour["team2_id"] == get_user.id:
                final_tour["is_edit"] = True
            else:
                final_tour["is_edit"] = False
            
            check_score_approved = TournamentScoreApproval.objects.filter(tournament__id=final_tour["id"], team1_approval=True, team2_approval=True)

            if check_score_approved.exists():
                final_tour["is_score_approved"] = True
                final_tour["is_edit"] = False
            else:
                final_tour["is_score_approved"] = False                    
            
            check_score_reported = TournamentScoreReport.objects.filter(tournament__id=final_tour["id"], status="Pending")

            if check_score_reported.exists():
                final_tour["is_score_reported"] = True 
                if (get_user == league.created_by) or (get_user.id in sub_org_list):
                    final_tour["is_edit"] = True
                else:
                    final_tour["is_edit"] = False
            else:
                final_tour["is_score_reported"] = False   

            team1_approval = TournamentScoreApproval.objects.filter(tournament__id=final_tour["id"], team1_approval=True).exists()
            team2_approval = TournamentScoreApproval.objects.filter(tournament__id=final_tour["id"], team1_approval=True).exists()
            check_score_set = TournamentSetsResult.objects.filter(tournament__id=final_tour["id"])

            if check_score_set.exists() and not team1_approval and ((get_user.id in team_1_player) or (get_user == team_1_created_by)):
                final_tour["is_button_show"] = True
            
            elif check_score_set.exists() and not team2_approval and ((get_user.id in team_2_player) or (get_user == team_2_created_by)):
                final_tour["is_button_show"] = True
            else:
                final_tour["is_button_show"] = False

            score = [{"name": "","set": [],"score": [],"win_status": [],"is_win": True,"is_completed": True},{"name": "","set": [],"score": [],"win_status": [],"is_win": True,"is_completed": True}]
            
            if final_tour["team1_id"] == final_tour["winner_team_id"] and final_tour["winner_team_id"] is not None:
                score[0]["is_win"] = True
                score[1]["is_win"] = False
            elif final_tour["team2_id"] == final_tour["winner_team_id"] and final_tour["winner_team_id"] is not None:
                score[1]["is_win"] = True
                score[0]["is_win"] = False
            else:
                score[1]["is_win"] = None
                score[0]["is_win"] = None
            score_details = TournamentSetsResult.objects.filter(tournament_id=final_tour["id"]).values()
            score[0]["name"] = final_tour["team1__name"]
            score[1]["name"] = final_tour["team2__name"]
            score[0]["set"] = ["s1","s2","s3"]
            score[1]["set"] = ["s1","s2","s3"]
            for l__ in range(3):
                
                if l__ < len(score_details):
                    l = {"team1_point":score_details[l__]["team1_point"],"team2_point":score_details[l__]["team2_point"]}
                else:
                    l = {"team1_point":None,"team2_point":None}
                
                score[0]["score"].append(l["team1_point"])
                score[1]["score"].append(l["team2_point"])
                
                if l["team1_point"] == None or l["team1_point"] == None:
                    score[0]["win_status"].append(None)
                    score[1]["win_status"].append(None)
                elif l["team1_point"] > l["team2_point"]:
                    score[0]["win_status"].append(True)
                    score[1]["win_status"].append(False)
                else:
                    score[0]["win_status"].append(False)
                    score[1]["win_status"].append(True)
            final_tour["score"] = score
        data['final'] = list(knock_out_final_tournament_data)
        data['message'] = "Elimination details fetched successfully."
        data['status'] = status.HTTP_200_OK
        
    else:
        data["status"], data["message"] = status.HTTP_404_NOT_FOUND, f"User or league not found."
    return Response(data)


@api_view(("GET",))
def view_point_table_details(request):
    data = {
             'status':'',             
             'point_table':[],              
             'message':''             
             }
    user_uuid = request.GET.get('user_uuid')
    user_secret_key = request.GET.get('user_secret_key')
    league_uuid = request.GET.get('league_uuid')
    league_secret_key = request.GET.get('league_secret_key')
    protocol = 'https' if request.is_secure() else 'http'
    host = request.get_host()
    media_base_url = f"{protocol}://{host}{settings.MEDIA_URL}"
    '''
    registration_open, future, past
    '''
    check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
    check_leagues = Leagues.objects.filter(uuid=league_uuid,secret_key=league_secret_key)
    if check_user.exists() and check_leagues.exists():
        league = check_leagues.first()
        get_user = check_user.first()
        play_type_check_win = league.play_type        
        all_group_details = RoundRobinGroup.objects.filter(league_for=league)
        for grp in all_group_details:
            teams = grp.all_teams.all()
            group_score_point_table = []
            # print(teams)
            for team in teams:
                team_score = {}
                total_match_detals = Tournament.objects.filter(leagues=league, match_type="Round Robin").filter(Q(team1=team) | Q(team2=team))
                completed_match_details = total_match_detals.filter(is_completed=True)
                win_match_details = completed_match_details.filter(winner_team=team).count()
                loss_match_details = completed_match_details.filter(loser_team=team).count()
                drow_match = len(completed_match_details) - (win_match_details + loss_match_details)
                match_list = list(total_match_detals.values_list("id", flat=True))
                for_score = 0
                aginst_score = 0
                for sc in match_list:
                    co_team_position = Tournament.objects.filter(id=sc).first()
                    set_score = TournamentSetsResult.objects.filter(tournament_id=sc)
                    if co_team_position.team1 == team:
                        for_score = for_score + sum(list(set_score.values_list("team1_point", flat=True)))
                        aginst_score = aginst_score + sum(list(set_score.values_list("team2_point", flat=True)))
                    else:
                        for_score = for_score + sum(list(set_score.values_list("team2_point", flat=True)))
                        aginst_score = aginst_score + sum(list(set_score.values_list("team1_point", flat=True)))
                
                point = (win_match_details * 3) + (drow_match * 1)
                team_score["uuid"], team_score["secret_key"] = team.uuid, team.secret_key
                team_score["name"], team_score["completed_match"] = team.name, len(completed_match_details)
                team_score["win_match"], team_score["loss_match"] = win_match_details, loss_match_details
                team_score["drow_match"], team_score["for_score"] = drow_match, for_score
                team_score["aginst_score"], team_score["point"] = aginst_score, point
                group_score_point_table.append(team_score)
            # Append team details to group data
            tournament_details_group = Tournament.objects.filter(leagues=league,group=grp).values("id","uuid","secret_key","team1__name","team2__name","leagues__name","match_type","is_completed","group__court","play_ground_name","playing_date_time","group_id")
            for k_ in tournament_details_group:
                round_robin_group_detals = RoundRobinGroup.objects.filter(league_for=league, id=k_["group_id"]).first()
                k_["sets"] = round_robin_group_detals.number_sets
                k_["court"] = round_robin_group_detals.court
                k_["score"] = list(TournamentSetsResult.objects.filter(tournament_id=k_["id"]).values())
            
            group_score_point_table = sorted(group_score_point_table, key=lambda x: (x['point'], x['for_score']), reverse=True)
            # print(group_score_point_table)

            ###### tournament winning team update and declare
            if play_type_check_win == "Round Robin":
                total_tournament = Tournament.objects.filter(leagues=check_leagues.first(),match_type="Round Robin",leagues__play_type="Round Robin")
                completed_tournament = total_tournament.filter(is_completed=True)
                if total_tournament.count() == completed_tournament.count():
                    winner_team = Team.objects.filter(uuid=group_score_point_table[0]["uuid"]).first()
                    winner_team_name = winner_team.name
                    league.winner_team = winner_team
                    league.is_complete = True
                    league.save()
                    data["winner_team"] = winner_team_name
            grp_data = {
                "id": grp.id,
                "court": grp.court,
                "league_for_id": grp.league_for_id,
                "all_games_status": grp.all_games_status,
                "all_tems": group_score_point_table,
                "tournament": tournament_details_group,
                "seleced_teams_id": grp.seleced_teams_id
            }
            data['point_table'].append(grp_data)
        
        data["status"], data["message"] = status.HTTP_200_OK, "Point table data fetched successfully."
    else:
        data["status"], data['data'], data["message"] = status.HTTP_404_NOT_FOUND, [],  "User or League not found."
    return Response(data)


@api_view(("GET",))
def get_match_result(request):
    data = {'status': '', 'match_details':[], 'message': ''}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        match_id = request.GET.get('match_id')
        # tournament_secret_key = request.data.get('tournament_secret_key')
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        check_match = Tournament.objects.filter(id=match_id)
        print(check_user,check_match)
        protocol = 'https' if request.is_secure() else 'http'
        host = request.get_host()
        media_base_url = f"{protocol}://{host}{settings.MEDIA_URL}"
        if check_user.exists() and check_match.exists():
            get_match = check_match.first()
            get_user= check_user.first()
            league = get_match.leagues

            tournament_details = Tournament.objects.filter(id=match_id).order_by("match_number").values("id","match_number","uuid","secret_key","leagues__name"
                                                                                                                        ,"team1_id", "team2_id", "team1__team_image", "team2__team_image", 
                                                                                                                        "team1__name", "team2__name", "winner_team_id", "winner_team__name", 
                                                                                                                        "playing_date_time","match_type","group__court","is_completed"
                                                                                                                        ,"elimination_round","court_sn","set_number","court_num","points","is_drow")
            
            sub_org_list = list(league.add_organizer.all().values_list("id", flat=True))
            for sc in tournament_details:
                if sc["group__court"] is None:
                    sc["group__court"] = sc["court_sn"]

                team_1_player = list(Player.objects.filter(team__id=sc["team1_id"]).values_list("player_id", flat=True))
                team_2_player = list(Player.objects.filter(team__id=sc["team2_id"]).values_list("player_id", flat=True))
                team_1_created_by = Team.objects.filter(id=sc["team1_id"]).first().created_by
                team_2_created_by = Team.objects.filter(id=sc["team2_id"]).first().created_by

                if (get_user == league.created_by) or (get_user.id in sub_org_list) or (get_user.id in team_1_player) or (get_user == team_1_created_by) or (get_user.id in team_2_player) or ((get_user == team_2_created_by)):
                    sc["is_edit"] = True
                else:
                    sc["is_edit"] = False

                check_score_approved = TournamentScoreApproval.objects.filter(tournament__id=sc["id"], team1_approval=True, team2_approval=True)

                if check_score_approved.exists():
                    sc["is_score_approved"] = True
                    sc["is_edit"] = False
                else:
                    sc["is_score_approved"] = False                    
                
                check_score_reported = TournamentScoreReport.objects.filter(tournament__id=sc["id"], status="Pending")
                if check_score_reported.exists():
                    sc["is_score_reported"] = True 
                    if (get_user == league.created_by) or (get_user.id in sub_org_list):
                        sc["is_edit"] = True
                    else:
                        sc["is_edit"] = False
                else:
                    sc["is_score_reported"] = False   

                team1_approval = TournamentScoreApproval.objects.filter(tournament__id=sc["id"], team1_approval=True).exists()
                team2_approval = TournamentScoreApproval.objects.filter(tournament__id=sc["id"], team1_approval=True).exists()
                check_score_set = TournamentSetsResult.objects.filter(tournament__id=sc["id"])

                if check_score_set.exists() and not team1_approval and ((get_user.id in team_1_player) or (get_user == team_1_created_by)):
                    sc["is_button_show"] = True
                
                elif check_score_set.exists() and not team2_approval and ((get_user.id in team_2_player) or (get_user == team_2_created_by)):
                    sc["is_button_show"] = True
                else:
                    sc["is_button_show"] = False

                if sc["team1__team_image"] != "":
                    img_str = sc["team1__team_image"]
                    sc["team1__team_image"] = f"{media_base_url}{img_str}"
                if sc["team2__team_image"] != "":
                    img_str = sc["team2__team_image"]
                    sc["team2__team_image"] = f"{media_base_url}{img_str}"
                #"set_number","court_num","points"
                set_list_team1 = []
                set_list_team2 = []
                score_list_team1 = []
                score_list_team2 = []
                win_status_team1 = []
                win_status_team2 = []
                is_completed_match = sc["is_completed"]
                is_win_match_team1 = False
                is_win_match_team2 = False
                team1_name = sc["team1__name"]
                team2_name = sc["team2__name"]
                if sc["team1_id"] == sc["winner_team_id"] and sc["winner_team_id"] is not None:
                    is_win_match_team1 = True
                    is_win_match_team2 = False
                elif sc["team2_id"] == sc["winner_team_id"] and sc["winner_team_id"] is not None:
                    is_win_match_team2 = True
                    is_win_match_team1 = False
                # else:
                #     is_win_match_team2 = False
                #     is_win_match_team1 = False
                for s in range(sc["set_number"]):
                    index = s+1
                    set_str = f"s{index}"
                    set_list_team1.append(set_str)
                    set_list_team2.append(set_str)
                    score_details_for_set = TournamentSetsResult.objects.filter(tournament_id=sc["id"],set_number=index).values()
                    if len(score_details_for_set)!=0:
                        team_1_score = score_details_for_set[0]["team1_point"]
                        team_2_score = score_details_for_set[0]["team2_point"]
                    else:
                        team_1_score = None
                        team_2_score = None
                    score_list_team1.append(team_1_score)
                    score_list_team2.append(team_2_score)
                    if team_1_score is not None and team_2_score is not None:
                        if team_1_score >= team_2_score:
                            win_status_team1.append(True)
                            win_status_team2.append(False)
                        else:
                            win_status_team1.append(False)
                            win_status_team2.append(True)
                    else:
                        win_status_team1.append(False)
                        win_status_team2.append(False)
                score = [
                    {
                        "name": team1_name,"set": set_list_team2,
                        "score": score_list_team1,"win_status": win_status_team1,
                        "is_win": is_win_match_team1,"is_completed": is_completed_match,
                        "is_drow":sc["is_drow"]
                        },
                    {
                    "name": team2_name,"set": set_list_team2,
                    "score": score_list_team2,"win_status": win_status_team1,
                    "is_win": is_win_match_team2,"is_completed": is_completed_match,
                    "is_drow":sc["is_drow"]
                    }
                    ]
                sc["score"] = score
                # print(score)
            
                # List to store data for the point table
            
            data['match_details'] = tournament_details
            data['message'] = "Match result fetched successfully."
            data['status'] = status.HTTP_200_OK

        else:
            data["status"], data["message"], data["match_details"] = status.HTTP_404_NOT_FOUND, "User or Match not found.",[]
    except Exception as e:
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, str(e)
    return Response(data)


################ Old Implementation (New from: 7340 ) #################
@api_view(('get',))
def all_map_data(request):
    data = {'status':'','data':[], 'message':''}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        user_current_location_lat = request.GET.get('user_current_location_lat')
        user_current_location_long = request.GET.get('user_current_location_long')
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if check_user.exists():
            result = []
            today_date = datetime.now()
            all_leagues = Leagues.objects.filter(registration_start_date__date__lte=today_date,registration_end_date__date__gte=today_date)
            leagues = all_leagues.values('id','uuid','secret_key','name','location','leagues_start_date','leagues_end_date',
                               'registration_start_date','registration_end_date','team_type__name','team_person__name',
                               "street","city","state","postal_code","country","complete_address","latitude","longitude","image","created_by__phone")
            output = []

            # Grouping data by 'name'
            grouped_data = {}
            for item in list(leagues):
                item["is_reg_diable"] = True
                match_ = Tournament.objects.filter(leagues_id=item["id"]).values()
                if match_.exists():
                    item["is_reg_diable"] = False
                le = Leagues.objects.filter(id=item["id"]).first()
                reg_team =le.registered_team.all().count()
                max_team = le.max_number_team
                if max_team <= reg_team:
                    item["is_reg_diable"] = False
                key = item['name']
                item["type_show"] = "tournament"
            facility_data = AdvertiserFacility.objects.all().values()
            for k in facility_data:
                k["type_show"]="facility"
            
            result = list(leagues) + list(facility_data)
            
            default_st = {"id": 0,"uuid": "","secret_key": "","name": "","location": "","leagues_start_date": "","leagues_end_date": "","registration_start_date": "","registration_end_date": "","team_type__name": "","team_person__name": "","street": "","city": "","state": "","postal_code": "","country": "","complete_address": "","latitude": 0,"longitude": 0,"image": "","created_by__phone": "","is_reg_diable": 0,"type_show": ""}
            if not user_current_location_lat:
                user_current_location_lat = "33.7488"
            if not user_current_location_long:
                user_current_location_long = "84.3877"
            
            default_st["location"] = ""
            default_st["latitude"] = user_current_location_lat
            default_st["longitude"] = user_current_location_long
            default_st["type_show"] = "Current Location"
            result.append(default_st)

            json_file_path = 'Pickleball_Venues.json'

            # Read the JSON file
            with open(json_file_path, 'r') as file:
                data2 = json.load(file)
            
            # for ij in data2:
            #     result.append(ij)
            # dat = json.dump(data)
            result = result + data2
            data["data"] = result
            data['message'] = "data found"
            data['status'] = status.HTTP_200_OK
        else:
            data['status'] = status.HTTP_404_NOT_FOUND
            data['message'] = "User not found."
        return Response(data)
    except Exception as e:
        data['status'] = status.HTTP_400_BAD_REQUEST
        data['message'] = f"{e}"
    return Response(data)


@api_view(('get',))
def all_map_data_new(request):
    # try:
    data = {'status':'','data':[], 'message':''}
    user_uuid = request.GET.get('user_uuid')
    user_secret_key = request.GET.get('user_secret_key')
    user_current_location_lat = request.GET.get('user_current_location_lat')
    user_current_location_long = request.GET.get('user_current_location_long')
    check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
    if check_user.exists():
        # result = []
        today_date = datetime.now()
        all_leagues = Leagues.objects.filter(registration_start_date__date__lte=today_date,registration_end_date__date__gte=today_date)
        leagues = all_leagues.values('id','uuid','secret_key','name','location','leagues_start_date','leagues_end_date',
                            'registration_start_date','registration_end_date','team_type__name','team_person__name',
                            "street","city","state","postal_code","country","complete_address","latitude","longitude","image","created_by__phone")
        output = []

        # Grouping data by 'name'
        grouped_data = {}
        for item in list(leagues):
            key = item['name']
            if key not in grouped_data:
                grouped_data[key] = {
                                    'latitude':item['latitude'],
                                    'type_show':'league', 
                                    'longitude':item["longitude"],
                                    'name': item['name'], 
                                    'org_phone':str(item['created_by__phone']),
                                    'location':item['location'],
                                    'registration_start_date':item["registration_start_date"],
                                    'registration_end_date':item["registration_end_date"],
                                    'leagues_start_date':item["leagues_start_date"],
                                    'leagues_end_date':item["leagues_end_date"],
                                    'location':item["location"],
                                    'image':item["image"],
                                    'type': [item['team_type__name']], 
                                    'data':[item]
                                    }
            else:
                grouped_data[key]['type'].append(item['team_type__name'])
                grouped_data[key]['data'].append(item)

        # Building the final output
        for key, value in grouped_data.items():
            output.append(value)

        facility_data = AdvertiserFacility.objects.all().values()
        for k in facility_data:
            k["type_show"]="facility"
            try:
                k["created_by__phone"] = str(User.objects.filter(id=k["created_by_id"]).first().phone)
            except:
                k["created_by__phone"] = None
        # print(output)
        result = list(output) + list(facility_data)
        #code after this point
        organized_data = {}

        # Iterate through the data
        for item in result:
            # Check if the 'lat', 'long', and 'type_show' are the same
            key = (item['latitude'], item['longitude'], item['type_show'])
            
            # If the key doesn't exist in the organized data, create it with an empty list
            if key not in organized_data:
                organized_data[key] = {'lat': key[0], 'long': key[1], 'type_show': key[2], 'data': []}
            
            # Append the item to the 'data' list corresponding to the key
            organized_data[key]['data'].append(item)

        # Convert the organized data dictionary values to a list
        result = list(organized_data.values())
        default_st = {"name": "","lat": 0,"long": 0,"type_show": "current_location", "data":[]}
        if not user_current_location_lat:
            user_current_location_lat = "34.0289259"
        if not user_current_location_long:
            user_current_location_long = "-84.198579"
        default_st["name"] = ""
        default_st["lat"] = float(user_current_location_lat)
        default_st["long"] = float(user_current_location_long)
        result.append(default_st)
        json_file_path = 'Pickleball_Venues.json'

        # Read the JSON file
        with open(json_file_path, 'r') as file:
            data2 = json.load(file)


        result = result+data2

        for c in result:
            if c["lat"] and c["long"]:
                c["lat"] = float(c["lat"])
                c["long"] = float(c["long"])
            else:
                c["lat"] = float("34.0289259")
                c["long"] = float("-84.198579")
        data["data"] = result
        data['message'] = "data found"
        data['status'] = status.HTTP_200_OK
    else:
        data['status'] = status.HTTP_404_NOT_FOUND
        data['message'] = "User not found."
    return Response(data)
    # except Exception as e:
    #     data['status'] = status.HTTP_400_BAD_REQUEST
    #     data['message'] = f"{e}"
    # return Response(data)


@api_view(('GET',))
def tournament_joined_details(request):
    data = {'status':'','data':[], 'message':''}
    try:
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        order_by = request.GET.get('order_by')
        check_user = User.objects.filter(secret_key=user_secret_key,uuid=user_uuid)
        today_date = timezone.now()
        # print(check_user)
        if check_user.exists():
            get_user = check_user.first()
            all_leagues = Leagues.objects.exclude(registration_end_date__date__lte=today_date)
            if get_user.is_coach is True or get_user.is_team_manager is True:
                all_leagues = all_leagues.filter(registered_team__created_by=get_user)
            elif get_user.is_player :
                check_player = Player.objects.filter(player_email=get_user.email)
                if check_player.exists():
                    get_player = check_player.first()
                    # get_player_id = get_player.id
                    get_player_team = get_player.team.all()
                    team_id = [i.id for i in get_player_team]
                    all_leagues = all_leagues.filter(registered_team__id__in=team_id)
                else:
                    data['status'], data['data'], data['message'] = status.HTTP_400_BAD_REQUEST, [], f"user not found"
                    return Response(data)
            else:
                data['status'], data['data'], data['message'] = status.HTTP_200_OK, [], f"Data Found"
                return Response(data)

            if order_by == "registration_open_date" :
                all_leagues = all_leagues.order_by("leagues_start_date")
            elif order_by == "registration_open_name" :
                all_leagues = all_leagues.order_by("name")
            elif order_by == "registration_open_city" :
                all_leagues = all_leagues.order_by("city")
            elif order_by == "registration_open_state" :
                all_leagues = all_leagues.order_by("state")
            elif order_by == "registration_open_country" :
                all_leagues = all_leagues.order_by("country")
            else:
                all_leagues = all_leagues

            all_leagues = all_leagues.values('uuid','secret_key','name','location','leagues_start_date','leagues_end_date',
                               'registration_start_date','registration_end_date','team_type__name','team_person__name',
                               "street","city","state","postal_code","country","complete_address","latitude","longitude")
            # data['status'], data['data'], data['message'] = status.HTTP_200_OK, all_leagues, f"Data Found"
            unique_ids = set()  # Using a set to store unique IDs
            output = []

            for item in all_leagues:
                if item["uuid"] not in unique_ids:
                    output.append(item)
                    unique_ids.add(item["uuid"])         

            data['status'], data['data'], data['message'] = status.HTTP_200_OK, output, f"Data Found"
            # if get_user.is_coach is True or get_user.is_team_manager is True:
            #     created_by_leagues = Tournament.objects.filter(leagues__registered_team__created_by=get_user)
            #     # print(created_by_leagues)
            #     joined_league = created_by_leagues.filter(playing_date_time__gte=today_date).order_by(str(order_by)).values("uuid","secret_key","leagues__uuid","leagues__secret_key","leagues__name","leagues__leagues_start_date","leagues__leagues_end_date","leagues__registration_start_date","leagues__registration_end_date","playing_date_time")
                # data['status'], data['data'], data['message'] = status.HTTP_200_OK, all_leagues, f"Data Found"
            # else:

            #     data['status'], data['data'], data['message'] = status.HTTP_400_BAD_REQUEST, [], f"user not found"
        else:
            data['status'], data['data'], data['message'] = status.HTTP_400_BAD_REQUEST, [], f"user not found"
    except Exception as e :
        data['status'], data['data'], data['message'] = status.HTTP_400_BAD_REQUEST, [], f"{e}"
    return Response(data)


@api_view(('GET',))
def tournament_saved_details(request):
    data = {'status':'','data':[], 'message':''}
    try:
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        order_by = request.GET.get('order_by')
        check_user = User.objects.filter(secret_key=user_secret_key,uuid=user_uuid)
        today_date = timezone.now()
        if check_user.exists():
            get_user = check_user.first()
            all_leagues = Leagues.objects.exclude(registration_end_date__date__lte=today_date)
            if get_user.is_coach is True or get_user.is_team_manager is True:
                save_leagues = SaveLeagues.objects.filter(created_by=get_user).values("ch_league_id")
                leagues_ids = [i["ch_league_id"] for i in save_leagues]
                all_leagues = all_leagues.filter(id__in=leagues_ids)
            elif get_user.is_player :
                check_player = Player.objects.filter(player_email=get_user.email)
                if check_player.exists():
                    get_player = check_player.first()
                    get_player_team = get_player.team.all()
                    team_id = [i.id for i in get_player_team]
                    save_leagues = SaveLeagues.objects.filter(created_by=get_user,ch_team_id__in=team_id).values("ch_league_id")
                    leagues_ids = [i["ch_league_id"] for i in save_leagues]
                    all_leagues = all_leagues.filter(id__in=leagues_ids)
                else:
                    data['status'], data['data'], data['message'] = status.HTTP_400_BAD_REQUEST, [], f"user not found"
                    return Response(data)
            else:
                save_leagues = SaveLeagues.objects.filter(created_by=get_user).values("ch_league_id")
                leagues_ids = [i["ch_league_id"] for i in save_leagues]
                all_leagues = all_leagues.filter(id__in=leagues_ids)
                # data['status'], data['data'], data['message'] = status.HTTP_200_OK, [], f"Data Found"
                # return Response(data)

            if order_by == "registration_open_date" :
                all_leagues = all_leagues.order_by("leagues_start_date")
            elif order_by == "registration_open_name" :
                order_by = all_leagues.order_by("name")
            elif order_by == "registration_open_city" :
                all_leagues = all_leagues.order_by("city")
            elif order_by == "registration_open_state" :
                all_leagues = all_leagues.order_by("state")
            elif order_by == "registration_open_country" :
                all_leagues = all_leagues.order_by("country")
            all_leagues = all_leagues

            all_leagues = all_leagues.values('id','uuid','secret_key','name','location','leagues_start_date','leagues_end_date',
                               'registration_start_date','registration_end_date','team_type__name','team_person__name',
                               "street","city","state","postal_code","country","complete_address","latitude","longitude")
            for item in all_leagues:
                item["is_reg_diable"] = True
                match_ = Tournament.objects.filter(leagues_id=item["id"]).values()
                if match_.exists():
                    item["is_reg_diable"] = False
                le = Leagues.objects.filter(id=item["id"]).first()
                reg_team =le.registered_team.all().count()
                max_team = le.max_number_team
                if max_team <= reg_team:
                    item["is_reg_diable"] = False
            data['status'], data['data'], data['message'] = status.HTTP_200_OK, all_leagues, f"Data Found"
        else:
            data['status'], data['data'], data['message'] = status.HTTP_400_BAD_REQUEST, [], f"user not found"
    except Exception as e :
        data['status'], data['data'], data['message'] = status.HTTP_400_BAD_REQUEST, [], f"{e}"
    return Response(data)


@api_view(('GET',))
def tournament_created_details(request):
    data = {'status':'','data':[], 'message':''}
    try:
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        order_by = request.GET.get('order_by')
        check_user = User.objects.filter(secret_key=user_secret_key,uuid=user_uuid)
        today_date = timezone.now()
        if check_user.exists():
            get_user = check_user.first()
            all_leagues = Leagues.objects.exclude(registration_end_date__date__lte=today_date).filter(created_by=get_user)
            if order_by == "registration_open_date" :
                all_leagues = all_leagues.order_by("leagues_start_date")
            elif order_by == "registration_open_name" :
                order_by = all_leagues.order_by("name")
            elif order_by == "registration_open_city" :
                all_leagues = all_leagues.order_by("city")
            elif order_by == "registration_open_state" :
                all_leagues = all_leagues.order_by("state")
            elif order_by == "registration_open_country" :
                all_leagues = all_leagues.order_by("country")

            all_leagues = all_leagues.values('uuid','secret_key','name','location','leagues_start_date','leagues_end_date',
                               'registration_start_date','registration_end_date','team_type__name','team_person__name',
                               "street","city","state","postal_code","country","complete_address","latitude","longitude")
            data['status'], data['data'], data['message'] = status.HTTP_200_OK, all_leagues, f"Data found"
        else:
            data['status'], data['data'], data['message'] = status.HTTP_400_BAD_REQUEST, [], f"user not found"
    except Exception as e :
        data['status'], data['data'], data['message'] = status.HTTP_400_BAD_REQUEST, [], f"{e}"
    return Response(data)


@api_view(('GET',))
def tournament_joined_completed_details(request):
    data = {'status':'','data':[], 'message':''}
    try:
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        order_by = request.GET.get('order_by')
        check_user = User.objects.filter(secret_key=user_secret_key,uuid=user_uuid)
        today_date = timezone.now()
        if check_user.exists():
            get_user = check_user.first()
            all_leagues1 = []
            all_leagues2 = []
            all_leagues_main = Leagues.objects.filter(registration_end_date__date__lte=today_date,is_complete=True)
            if get_user.is_coach is True or get_user.is_team_manager is True:
                all_leagues1 = list(all_leagues_main.filter(registered_team__created_by=get_user))
            if get_user.is_player :
                check_player = Player.objects.filter(player_email=get_user.email)
                if check_player.exists():
                    get_player = check_player.first()
                    get_player_team = get_player.team.all()
                    team_id = [i.id for i in get_player_team]
                    all_leagues2 = list(all_leagues_main.filter(registered_team__id__in=team_id))
                else:
                    data['status'], data['data'], data['message'] = status.HTTP_400_BAD_REQUEST, [], f"user not found"
                    return Response(data)
            
            all_leagues = all_leagues1 + all_leagues2
            if len(all_leagues) > 0 :
                all_leagues_id = [i.id for i in all_leagues]
                all_leagues = all_leagues_main.filter(id__in=all_leagues_id)

                if order_by == "registration_open_date" :
                    all_leagues = all_leagues.order_by("leagues_start_date")
                elif order_by == "registration_open_name" :
                    order_by = all_leagues.order_by("name")
                elif order_by == "registration_open_city" :
                    all_leagues = all_leagues.order_by("city")
                elif order_by == "registration_open_state" :
                    all_leagues = all_leagues.order_by("state")
                elif order_by == "registration_open_country" :
                    all_leagues = all_leagues.order_by("country")
                else:
                    all_leagues = all_leagues

                all_leagues = all_leagues.values('uuid','secret_key','name','location','leagues_start_date','leagues_end_date',
                                'registration_start_date','registration_end_date','team_type__name','team_person__name',
                                "street","city","state","postal_code","country","complete_address","latitude","longitude")
            
                data['status'], data['data'], data['message'] = status.HTTP_200_OK, all_leagues, f"Data found"
        else:
            data['status'], data['data'], data['message'] = status.HTTP_400_BAD_REQUEST, [], f"user not found"
    except Exception as e :
        data['status'], data['data'], data['message'] = status.HTTP_400_BAD_REQUEST, [], f"{e}"
    return Response(data)


@api_view(('GET',))
def tournament_saved_completed_details(request):
    data = {'status':'','data':[], 'message':''}
    try:
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        order_by = request.GET.get('order_by')
        check_user = User.objects.filter(secret_key=user_secret_key,uuid=user_uuid)
        today_date = timezone.now()
        if check_user.exists():
            get_user = check_user.first()
            all_leagues1 = []
            all_leagues2 = []
            sv = SaveLeagues.objects.filter(ch_league__registration_end_date__date__lte=today_date).values("ch_league_id")
            sv_id = [i["ch_league_id"] for i in sv]
            all_leagues_main = Leagues.objects.filter(id__in=sv_id,is_complete=True)
            if get_user.is_coach is True or get_user.is_team_manager is True:
                all_leagues1 = list(all_leagues_main.filter(registered_team__created_by=get_user))
            if get_user.is_player :
                check_player = Player.objects.filter(player_email=get_user.email)
                if check_player.exists():
                    get_player = check_player.first()
                    get_player_team = get_player.team.all()
                    team_id = [i.id for i in get_player_team]
                    all_leagues2 = list(all_leagues_main.filter(registered_team__id__in=team_id))
                else:
                    data['status'], data['data'], data['message'] = status.HTTP_400_BAD_REQUEST, [], f"user not found"
                    return Response(data)
            
            all_leagues = all_leagues1 + all_leagues2
            if len(all_leagues) > 0 :
                all_leagues_id = [i.id for i in all_leagues]
                all_leagues = all_leagues_main.filter(id__in=all_leagues_id)

                if order_by == "registration_open_date" :
                    all_leagues = all_leagues.order_by("leagues_start_date")
                elif order_by == "registration_open_name" :
                    order_by = all_leagues.order_by("name")
                elif order_by == "registration_open_city" :
                    all_leagues = all_leagues.order_by("city")
                elif order_by == "registration_open_state" :
                    all_leagues = all_leagues.order_by("state")
                elif order_by == "registration_open_country" :
                    all_leagues = all_leagues.order_by("country")
                else:
                    all_leagues = all_leagues

                all_leagues = all_leagues.values('uuid','secret_key','name','location','leagues_start_date','leagues_end_date',
                                'registration_start_date','registration_end_date','team_type__name','team_person__name',
                                "street","city","state","postal_code","country","complete_address","latitude","longitude")
                
                data['status'], data['data'], data['message'] = status.HTTP_200_OK, all_leagues, f"Data found"
        else:
            data['status'], data['data'], data['message'] = status.HTTP_400_BAD_REQUEST, [], f"user not found"
    except Exception as e :
        data['status'], data['data'], data['message'] = status.HTTP_400_BAD_REQUEST, [], f"{e}"
    return Response(data)


@api_view(('GET',))
def stats_details(request):
    data = {'status':'','data':[], 'message':''}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        check_user = User.objects.filter(secret_key=user_secret_key,uuid=user_uuid)
        if check_user.exists():
            get_user = check_user.first()
            stats_details = {}
            stats_details["rank"] = get_user.rank
            try:
                image = request.build_absolute_uri(get_user.image.url)
            except:
                image = None
            stats_details["name"] = get_user.username
            stats_details["first_name"] = get_user.first_name
            stats_details["last_name"] = get_user.last_name
            stats_details["is_rank"] = get_user.is_rank
            stats_details["profile_image"] = image
            check_player_details = Player.objects.filter(player__id=get_user.id)
            if check_player_details.exists():
                total_league = 0
                win_league = 0
                get_player_details = check_player_details.first()
                team_ids = list(get_player_details.team.values_list('id', flat=True))
                total_played_matches = 0
                win_match = 0 
                for team_id in team_ids:
                    team_ = Team.objects.filter(id=team_id).first()
                    lea = Leagues.objects.filter(registered_team__in=[team_id], is_complete=True)
                    total_league += lea.count()
                    win_leagues_count = lea.filter(winner_team=team_).count()
                    check_match = Tournament.objects.filter(Q(team1=team_, is_completed=True) | Q(team2=team_, is_completed=True))
                    win_check_match = check_match.filter(winner_team=team_).count()
                    total_played_matches += check_match.count()
                    win_match += win_check_match
                    win_league += win_leagues_count

                stats_details["total_completed_turnament"] = total_league
                stats_details["total_win_turnament"] = win_league
                stats_details["total_completed_match"] = total_played_matches
                stats_details["total_win_match"] = win_match
                data['message'] = "Stats for this player is fetched successfully."
            else:
                
                stats_details["total_completed_turnament"] = 0
                stats_details["total_win_turnament"] = 0
                stats_details["total_completed_match"] = 0
                stats_details["total_win_match"] = 0
                data['message'] = "This user is not in player list"
            data['data'] = [stats_details]
            data['status'] = status.HTTP_200_OK
        else:
            data['status'], data['data'], data['message'] = status.HTTP_400_BAD_REQUEST, [], f"user not found"

    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


@api_view(('GET',))
def list_leagues_admin(request):
    data = {'status':'','data':'','message':''}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        filter_by = request.GET.get('filter_by')
        search_text = request.GET.get('search_text')
        '''
        registration_open, future, past
        '''
        leagues = []
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        today_date = datetime.now()
        if check_user.exists() and check_user.first().is_admin:
            if search_text:
               all_leagues = Leagues.objects.filter(Q(name__icontains=search_text) & Q(is_created=True)).order_by('-id')
            else:
                all_leagues = Leagues.objects.filter(is_created=True).order_by('-id')
            
            if filter_by == "future" :
                all_leagues = all_leagues.filter(Q(registration_start_date__date__lte=today_date, registration_end_date__date__gte=today_date) | Q(registration_start_date__date__gte=today_date))
            elif filter_by == "past" :
                all_leagues = all_leagues.filter(leagues_end_date__date__lte=today_date, is_complete=True)
            elif filter_by == "registration_open" :
                all_leagues = all_leagues.filter(leagues_start_date__date__lte=today_date, leagues_end_date__date__gte=today_date, is_complete=False)
                
            
            elif filter_by == "registration_open_date" :
                all_leagues = all_leagues.filter(leagues_start_date__date__lte=today_date, leagues_end_date__date__gte=today_date, is_complete=False).order_by("leagues_start_date")
            elif filter_by == "registration_open_name" :
                all_leagues = all_leagues.filter(leagues_start_date__date__lte=today_date, leagues_end_date__date__gte=today_date, is_complete=False).order_by("name")
            elif filter_by == "registration_open_city" :
                all_leagues = all_leagues.filter(leagues_start_date__date__lte=today_date, leagues_end_date__date__gte=today_date, is_complete=False).order_by("city")
            elif filter_by == "registration_open_state" :
                all_leagues = all_leagues.filter(leagues_start_date__date__lte=today_date, leagues_end_date__date__gte=today_date, is_complete=False).order_by("state")
            elif filter_by == "registration_open_country" :
                all_leagues = all_leagues.filter(leagues_start_date__date__lte=today_date, leagues_end_date__date__gte=today_date, is_complete=False).order_by("country")

            else:
                all_leagues = all_leagues
            leagues = all_leagues.values('id','uuid','secret_key','name','location','leagues_start_date','leagues_end_date',
                               'registration_start_date','registration_end_date','team_type__name','team_person__name','any_rank','start_rank','end_rank',
                               "street","city","state","postal_code","country","complete_address","latitude","longitude","image", "others_fees", "league_type","registration_fee")
            output = []

            # Grouping data by 'name'
            grouped_data = {}
            for item in list(leagues):
                item["is_reg_diable"] = True
                match_ = Tournament.objects.filter(leagues_id=item["id"]).values()
                if match_.exists():
                    item["is_reg_diable"] = False
                le = Leagues.objects.filter(id=item["id"]).first()
                reg_team =le.registered_team.all().count()
                max_team = le.max_number_team
                if max_team <= reg_team:
                    item["is_reg_diable"] = False
                key = item['name']
                if key not in grouped_data:
                    grouped_data[key] = {
                                        'name': item['name'], 
                                        'lat':item['latitude'], 
                                        'long':item["longitude"],
                                        'registration_start_date':item["registration_start_date"],
                                        'registration_end_date':item["registration_end_date"],
                                        'leagues_start_date':item["leagues_start_date"],
                                        'leagues_end_date':item["leagues_end_date"],
                                        'location':item["location"],
                                        'image':item["image"],
                                        'type': [item['team_type__name']], 
                                        'data': [item]
                                        }
                else:
                    grouped_data[key]['type'].append(item['team_type__name'])
                    grouped_data[key]['data'].append(item)

            # Building the final output
            for key, value in grouped_data.items():
                output.append(value)

            # print(output)
            leagues = output
            
            data["status"], data['data'], data["message"] = status.HTTP_200_OK, leagues, "League data"
        elif check_user.exists():
            if search_text:
               all_leagues = Leagues.objects.filter(is_created=True).filter(Q(name__icontains=search_text)).exclude(play_type = "Individual Match Play").order_by('-id')
            else:
                all_leagues = Leagues.objects.filter(is_created=True).exclude(play_type = "Individual Match Play").order_by('-id')
            if filter_by == "future" :
                all_leagues = all_leagues.filter(Q(registration_start_date__date__lte=today_date, registration_end_date__date__gte=today_date) | Q(registration_start_date__date__gte=today_date))
            elif filter_by == "past" :
                all_leagues = all_leagues.filter(leagues_end_date__date__lte=today_date, is_complete=True)
            elif filter_by == "registration_open" :
                all_leagues = all_leagues.filter(leagues_start_date__date__lte=today_date, leagues_end_date__date__gte=today_date, is_complete=False)
            
            elif filter_by == "registration_open_date" :
                all_leagues = all_leagues.filter(leagues_start_date__date__lte=today_date, leagues_end_date__date__gte=today_date, is_complete=False).order_by("leagues_start_date")
            elif filter_by == "registration_open_name" :
                all_leagues = all_leagues.filter(leagues_start_date__date__lte=today_date, leagues_end_date__date__gte=today_date, is_complete=False).order_by("name")
            elif filter_by == "registration_open_city" :
                all_leagues = all_leagues.filter(leagues_start_date__date__lte=today_date, leagues_end_date__date__gte=today_date, is_complete=False).order_by("city")
            elif filter_by == "registration_open_state" :
                all_leagues = all_leagues.filter(leagues_start_date__date__lte=today_date, leagues_end_date__date__gte=today_date, is_complete=False).order_by("state")
            elif filter_by == "registration_open_country" :
                all_leagues = all_leagues.filter(leagues_start_date__date__lte=today_date, leagues_end_date__date__gte=today_date, is_complete=False).order_by("country")
            
            else:
                all_leagues = all_leagues
            leagues = all_leagues.values('id','uuid','secret_key','name','location','leagues_start_date','leagues_end_date',
                               'registration_start_date','registration_end_date','team_type__name','team_person__name','any_rank','start_rank','end_rank',
                               "street","city","state","postal_code","country","complete_address","latitude","longitude","image","others_fees", "league_type","registration_fee")
            inditour_data = []
                       
            get_user = check_user.first()
            
            if get_user.is_player:
                get_player = Player.objects.filter(player=get_user).first()
                team_list = list(get_player.team.all().values_list("id", flat=True))
                individual_match =  Leagues.objects.filter(is_created=True).filter(play_type = "Individual Match Play")
                # individual_match_values = individual_match.values('id','uuid','secret_key','name','location','leagues_start_date','leagues_end_date',
                #                'registration_start_date','registration_end_date','team_type__name','team_person__name',
                #                "street","city","state","postal_code","country","complete_address","latitude","longitude","image","others_fees", "league_type","registration_fee","registered_team")
               
                # print(team_list)
                
                for tour in individual_match:
                    team_list2 = list(tour.registered_team.all().values_list("id", flat=True))
                    for team_id in team_list2:
                        if team_id in team_list:
                            tour_data = {
                                'id': tour.id,
                                'uuid': tour.uuid,
                                'secret_key': tour.secret_key,
                                'name': tour.name,
                                'location': tour.location,
                                'leagues_start_date': tour.leagues_start_date,
                                'leagues_end_date': tour.leagues_end_date,
                                'registration_start_date': tour.registration_start_date,
                                'registration_end_date': tour.registration_end_date,
                                'team_type__name': tour.team_type.name,
                                'team_person__name': tour.team_person.name,
                                "street": tour.street,
                                "city": tour.city,
                                "state": tour.state,
                                "postal_code": tour.postal_code,
                                "country": tour.country,
                                "complete_address": tour.complete_address,
                                "latitude": tour.latitude,
                                "longitude": tour.longitude,
                                # "image": tour.image,
                                "others_fees": tour.others_fees,
                                "league_type": tour.league_type,
                                "registration_fee": tour.registration_fee,
                                
                            }
                            if tour.image:
                                tour_data["image"] = tour.image
                            else:
                                tour_data["image"] = None
                            registered_team = tour.registered_team.all().values_list("id", flat=True)
                            team1_id = registered_team[0]
                            players = Player.objects.filter(team__id=team1_id)
                            team1_players = []
                            for player in players:
                                player_name = f"{player.player.first_name} {player.player.last_name}"
                                team1_players.append(player_name)
                            tour_data["team_1_players"] = team1_players
                            team2_id = registered_team[1]
                            players = Player.objects.filter(team__id=team2_id)
                            team2_players = []
                            for player in players:
                                player_name = f"{player.player.first_name} {player.player.last_name}"
                                team2_players.append(player_name)
                            tour_data["team_2_players"] = team2_players
                            inditour_data.append(tour_data)
                        else:
                            pass
                            
            sorted_data = sorted(inditour_data, key=lambda x: x['id'], reverse=True)
            unique_dicts = []
            prev_id = None
            for d in sorted_data:
                if d['id'] != prev_id:
                    unique_dicts.append(d)
                    prev_id = d['id']
            
            leagues = list(leagues) + unique_dicts
            output = []
            grouped_data = {}
            for item in list(leagues):
                item["is_reg_diable"] = True
                match_ = Tournament.objects.filter(leagues_id=item["id"]).values()
                if match_.exists():
                    item["is_reg_diable"] = False
                le = Leagues.objects.filter(id=item["id"],  ).first()
                reg_team =le.registered_team.all().count()
                max_team = le.max_number_team
                if max_team <= reg_team:
                    item["is_reg_diable"] = False
                key = item['name']
                if key not in grouped_data:
                    grouped_data[key] = {
                                        'name': item['name'], 
                                        'lat':item['latitude'], 
                                        'long':item["longitude"],
                                        'registration_start_date':item["registration_start_date"],
                                        'registration_end_date':item["registration_end_date"],
                                        'leagues_start_date':item["leagues_start_date"],
                                        'leagues_end_date':item["leagues_end_date"],
                                        'location':item["location"],
                                        'image':item["image"],
                                        'type': [item['team_type__name']], 
                                        'data': [item]
                                        }
                else:
                    grouped_data[key]['type'].append(item['team_type__name'])
                    grouped_data[key]['data'].append(item)

            for key, value in grouped_data.items():
                output.append(value)

            leagues = output 
            for item in leagues:
                item["data"] = sorted(item["data"], key=lambda x: x["id"], reverse=True)

            leagues_sorted = sorted(leagues, key=lambda x: x["data"][0]["id"], reverse=True)                  
            data["status"], data['data'], data["message"] = status.HTTP_200_OK, leagues_sorted,"Data found"
        else:
            data["status"], data['data'], data["message"] = status.HTTP_404_NOT_FOUND, "","User not found."
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


################ New modified ###################
@api_view(["GET"])
def profile_stats_match_history(request):
    data = {'status': '', 'message': ''}
    try:
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        user_info = {}
        tournament_stats = {}
        match_stats = {}
        matches = []

        if check_user.exists():
            get_user = check_user.first()

            user_info["rank"] = get_user.rank
            try:
                image = get_user.image.url if get_user.image not in ["null", None, "", " "] else None
            except:
                image = None

            user_info["first_name"] = get_user.first_name
            user_info["last_name"] = get_user.last_name
            user_info["is_rank"] = get_user.is_rank
            user_info["profile_image"] = image
            check_player = Player.objects.filter(player__id=get_user.id)

            if check_player.exists():
                total_league = 0
                win_league = 0
                get_player = check_player.first()
                team_ids = list(get_player.team.values_list('id', flat=True))

                if len(team_ids) > 0:
                    total_played_matches = 0
                    win_match = 0

                    for team_id in team_ids:
                        lea = Leagues.objects.filter(registered_team__in=[team_id], is_complete=True)
                        total_league += lea.count()
                        win_leagues_count = lea.filter(winner_team_id=team_id).count()
                        check_match = Tournament.objects.filter(
                            Q(team1_id=team_id, is_completed=True) | Q(team2_id=team_id, is_completed=True)
                        )
                        win_check_match = check_match.filter(winner_team_id=team_id).count()
                        total_played_matches += check_match.count()
                        win_match += win_check_match
                        win_league += win_leagues_count

                        matches.extend(
                            Tournament.objects.filter(Q(team1_id=team_id) | Q(team2_id=team_id)).filter(is_completed=True).order_by("playing_date_time")
                        )

                    paginator = PageNumberPagination()
                    paginator.page_size = 5
                    result_page = paginator.paginate_queryset(matches, request)
                    serializer = TournamentSerializer(result_page, many=True, context={'request': request})

                    paginated_response = paginator.get_paginated_response(serializer.data)

                    for match in paginated_response.data["results"]:
                        match["team1"]["player_images"] = [
                            player_image if player_image else None
                            for player_image in Player.objects.filter(team__id=match["team1"]["id"]).values_list("player__image", flat=True)
                        ]
                        match["team2"]["player_images"] = [
                            player_image if player_image else None
                            for player_image in Player.objects.filter(team__id=match["team2"]["id"]).values_list("player__image", flat=True)
                        ]
                        match["team1"]["player_names"] = [
                            player_name for player_name in Player.objects.filter(team__id=match["team1"]["id"]).values_list("player_full_name", flat=True)
                        ]
                        match["team2"]["player_names"] = [
                            player_name for player_name in Player.objects.filter(team__id=match["team2"]["id"]).values_list("player_full_name", flat=True)
                        ]
                        match["is_win"] = match["winner_team_id"] in team_ids

                    tournament_stats["total_completed_turnament"] = total_league
                    tournament_stats["total_win_turnament"] = win_league
                    match_stats["total_completed_match"] = total_played_matches
                    match_stats["total_win_match"] = win_match
                    data["matches"] = paginated_response.data["results"]
                    data["count"] = paginated_response.data["count"]
                    data["previous"] = paginated_response.data["previous"]
                    data["next"] = paginated_response.data["next"]

                else:
                    tournament_stats["total_completed_turnament"] = 0
                    tournament_stats["total_win_turnament"] = 0
                    match_stats["total_completed_match"] = 0
                    match_stats["total_win_match"] = 0
                    data["matches"] = []
                    data["count"] = 0
                    data["previous"] = None
                    data["next"] = None
            else:
                tournament_stats["total_completed_turnament"] = 0
                tournament_stats["total_win_turnament"] = 0
                match_stats["total_completed_match"] = 0
                match_stats["total_win_match"] = 0
                data["matches"] = []
                data["count"] = 0
                data["previous"] = None
                data["next"] = None

            data['status'] = status.HTTP_200_OK
            data["user_info"] = user_info
            data["tournament_stats"] = tournament_stats
            data["match_stats"] = match_stats
            data['message'] = "Stats and match history fetched successfully."
        else:
            data['status'] = status.HTTP_404_NOT_FOUND
            data['message'] = "User not found."
    except Exception as e :
        data['status'], data['data'], data['message'] = status.HTTP_400_BAD_REQUEST, [], f"{e}"
    return Response(data)
 

@api_view(("GET",))
def get_tournament_count(request):
    data = {'status':'', 'message':''}
    try:
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
       
        check_user = User.objects.filter(secret_key=user_secret_key,uuid=user_uuid)
        today = datetime.now()        
        if check_user:
            get_user = check_user.first() 
            created = list(Leagues.objects.filter(created_by=get_user).values())        
            
            check_player = Player.objects.filter(player=get_user)
            if check_player:
                print('0000000000')
                get_player = check_player.first()
                player_teams = get_player.team.values_list("id", flat=True) if get_player else []
                
                joined = list(Leagues.objects.filter(
                                    Q(registered_team__in=player_teams) | 
                                    Q(created_by=get_user) | 
                                    Q(add_organizer__in=[get_user.id])
                                ).values())
                saved = list(SaveLeagues.objects.filter(created_by=get_user,ch_league__is_complete=False).values())  
                completed = list(Leagues.objects.filter(
                                    Q(registered_team__in=player_teams, is_complete=True) |
                                    Q(add_organizer__in=[get_user.id], is_complete=True) |
                                    Q(created_by=get_user, is_complete=True)
                                ).values()) 
                data["total_joined"] = len(joined)
                data["total_saved"] = len(saved)
                data["total_created"] = len(created)
                data["total_completed"] = len(completed)                
            else:   
                data["total_joined"] = 0
                data["total_saved"] = 0
                data["total_created"] = 0
                data["total_completed"] = 0   
            data["status"] = status.HTTP_200_OK            
            data["message"] = f"Tournament count fetched successfully."
        else:
            data["status"] = status.HTTP_404_NOT_FOUND
            data["total_joined"] = 0
            data["total_saved"] = 0
            data["total_created"] = 0
            data["total_completed"] = 0
            data["message"] = f"User not found."
    except Exception as e :
        data['status'], data['data'], data['message'] = status.HTTP_400_BAD_REQUEST, [], f"{e}"
    return Response(data)


@api_view(("GET",))
def get_leagues_list(request):
    data = {'status':'', 'message':''}
    try:
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')       
        check_user = User.objects.filter(secret_key=user_secret_key,uuid=user_uuid)
        if check_user:
            get_user = check_user.first()
            today_date = datetime.now()
            live_leagues = Leagues.objects.filter(leagues_start_date__date__lte=today_date, leagues_end_date__date__gte=today_date)
            upcoming_leagues = Leagues.objects.filter(Q(registration_start_date__date__lte=today_date, registration_end_date__date__gte=today_date) | Q(registration_start_date__date__gte=today_date) | Q(registration_end_date__date__lte=today_date, leagues_start_date__date__gte=today_date))
            serializer_live_leagues = LeagueSerializer(live_leagues, many=True)
            serializer_upcoming_leagues = LeagueSerializer(upcoming_leagues, many=True)
            unique_leagues = {}
            for league in serializer_live_leagues.data + serializer_upcoming_leagues.data:
                league_id = league.get('id')  
                if league_id not in unique_leagues:
                    unique_leagues[league_id] = league
            
            data_list = list(unique_leagues.values())
                
            data['status'], data['data'], data['message'] = status.HTTP_200_OK, data_list, f"Leagues fetched successfully."
        else:
            data['status'], data['data'], data['message'] = status.HTTP_404_NOT_FOUND, [], f"User not found."               
    except Exception as e :
        data['status'], data['data'], data['message'] = status.HTTP_400_BAD_REQUEST, [], f"{e}"
    return Response(data)


@api_view(("GET",))
def my_player_list(request):
    data = {'status': '', 'count': '', 'previous': '', 'next': '', 'data': [], 'message': ''}
    try:
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        search_text = request.GET.get('search_text')
        ordering = request.GET.get('ordering')
        gender = request.GET.get('gender')        
        start_rank = request.GET.get('start_rank')
        end_rank = request.GET.get('end_rank')

        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if check_user.exists():
            get_user = check_user.first()
            my_players = Player.objects.filter(created_by_id=get_user.id)
            if not search_text:
                my_players = my_players
            else:
                my_players = my_players.filter(Q(player_first_name__icontains=search_text) | Q(player_last_name__icontains=search_text))

            following = AmbassadorsDetails.objects.filter(ambassador=get_user)
            if following.exists():
                following_instance = following.first()
                following_ids = list(following_instance.following.all().values_list("id", flat=True))
            else:
                following_instance = AmbassadorsDetails.objects.create(ambassador=get_user)
                following_instance.save()
                following_ids = list(following_instance.following.all().values_list("id", flat=True))

            if ordering == 'latest':
                my_players = my_players.order_by('-id')  # Order by latest ID
            elif ordering == 'a-z':
                my_players = my_players.order_by('player_first_name') 
            else:
                my_players = my_players.order_by('-id')

            if gender not in [None, "null", "", "None"]:
                my_players = my_players.filter(player__gender__iexact=gender).order_by("-id")

            if start_rank not in [None, "null", "", "None"] and end_rank not in [None, "null", "", "None"]:
                my_players = my_players.filter(player__rank__gte=start_rank, player__rank__lte=end_rank).order_by("-id")

            #cache implementation
            if not search_text and not ordering:
                players_list = f'player_list'
                if cache.get(players_list):
                    print('from cache........')
                    players = cache.get(players_list)
                else:
                    print('from db.............')
                    players = my_players
                    cache.set(players_list, players)
            elif search_text and not ordering:
                search_list = f'{search_text}'
                if cache.get(search_list):
                    print('from cache........')
                    players = cache.get(search_list)
                else:
                    print('from db.............')
                    players = my_players
                    cache.set(search_list, players)

            elif not search_text and ordering:
                ordered_list = f'{ordering}'
                if cache.get(ordered_list):
                    print('from cache........')
                    players = cache.get(ordered_list)
                else:
                    print('from db.............')
                    players = my_players
                    cache.set(ordered_list, players)
            else:
                cache_key = f'player_list_{search_text}_{ordering}'
                if cache.get(cache_key):
                    print('from cache........')
                    players = cache.get(cache_key)
                else:
                    print('from db.............')
                    players = my_players
                    cache.set(cache_key, players)

            paginator = PageNumberPagination()
            paginator.page_size = 10  # Set the page size to 20
            result_page = paginator.paginate_queryset(my_players, request)
            serializer = PlayerSerializer(result_page, many=True, context={'request': request})
            serialized_data = serializer.data
            
            def add_additional_fields(player_data):
                player_data["is_edit"] = player_data["created_by_id"] == get_user.id
                player_data["is_follow"] = player_data["player_id"] in following_ids
                return player_data

            serialized_data = list(map(add_additional_fields, serialized_data))
                
            if not serialized_data:
                data["status"] = status.HTTP_200_OK
                data["count"] = 0
                data["previous"] = None
                data["next"] = None
                data["data"] = []
                data["message"] = "No Result found"
            else:
                paginated_response = paginator.get_paginated_response(serialized_data)
                data["status"] = status.HTTP_200_OK
                data["count"] = paginated_response.data["count"]
                data["previous"] = paginated_response.data["previous"]
                data["next"] = paginated_response.data["next"]
                data["data"] = paginated_response.data["results"]
                data["message"] = "Data found"
        else:
            data["count"] = 0
            data["previous"] = None
            data["next"] = None
            data["data"] = []
            data['status'] = status.HTTP_401_UNAUTHORIZED
            data['message'] = "Unauthorized access"

    except Exception as e:
        data["count"] = 0
        data["previous"] = None
        data["next"] = None
        data["data"] = []
        data['status'] = status.HTTP_200_OK
        data['message'] = str(e)

    return Response(data)


@api_view(("GET",))
def my_team_list(request):
    data = {
        'status': '',
        'count': '',
        'previous': '',
        'next': '',
        'data': [],
        'message': ''
    }
    try:
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        search_text = request.GET.get('search_text')
        ordering = request.GET.get('ordering')
        team_person = request.GET.get('team_person')
        team_type = request.GET.get('team_type')
        start_rank = request.GET.get('start_rank')
        end_rank = request.GET.get('end_rank')

        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key).first()
        if check_user:
            
            teams_query = Team.objects.filter(
                Q(created_by=check_user) | Q(player__player=check_user)
            ).distinct()

            if search_text:
                teams_query = teams_query.filter(name__icontains=search_text)

            ordering_map = {
                "latest": '-id',
                "a-z": 'name'
            }
            teams_query = teams_query.order_by(ordering_map.get(ordering, '-id'))

            # Prefetch related data
            teams_query = teams_query.prefetch_related('player_set')
            
            if team_person not in [None, "null", "", "None"]:
                teams_query = teams_query.filter(team_person__icontains=team_person)

            if team_type not in [None, "null", "", "None"]:
                teams_query = teams_query.filter(team_type__iexact=team_type)

            # Add annotations for rank
            teams_query = teams_query.annotate(
                team_rank=Avg(
                        Case(
                            When(
                                player__player__rank__isnull=False,
                                then=Cast(F("player__player__rank"), output_field=FloatField()),
                            ),
                            default=Value(1.0, output_field=FloatField()),
                            output_field=FloatField(),
                        )
                    )
                )
            if start_rank not in [None, "null", "", "None"] and end_rank not in [None, "null", "", "None"]:
                teams_query = teams_query.filter(
                Q(team_rank__gte=start_rank) &
                Q(team_rank__lte=end_rank)
            )

            paginator = PageNumberPagination()
            paginator.page_size = 10
            paginated_teams = paginator.paginate_queryset(teams_query, request)

            main_data = []
            for team in paginated_teams:               
                team_data = TeamListSerializer(team).data
                team_data['team_uuid'] = team_data.pop('uuid')
                team_data['team_secret_key'] = team_data.pop('secret_key')
                team_data['team_name'] = team_data.pop('name')
                team_data['location'] = team_data.pop('location')                
                team_data['is_edit'] = team.created_by_id == check_user.id
                main_data.append(team_data)

            paginated_response = paginator.get_paginated_response(main_data)

            data["status"] = status.HTTP_200_OK
            data["count"] = paginated_response.data["count"]
            data["previous"] = paginated_response.data["previous"]
            data["next"] = paginated_response.data["next"]
            data["data"] = paginated_response.data["results"]
            data["message"] = "Data found for Admin" if check_user.is_admin or check_user.is_organizer else "Data found"

        else:
            data["status"] = status.HTTP_401_UNAUTHORIZED
            data["message"] = "Unauthorized access"

    except Exception as e:
        data["status"] = status.HTTP_200_OK
        data["message"] = str(e)

    return Response(data)


@api_view(("GET",))
def player_profile_details(request):
    data = {'status':'','message':''}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        player_uuid = request.GET.get('player_uuid')
        player_secret_key = request.GET.get('player_secret_key')
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        if check_user.exists() :
            check_player = Player.objects.filter(uuid=player_uuid,secret_key=player_secret_key)
            if check_player:
                player = check_player.first()
                player_data = check_player.values("id", "player__first_name","player__last_name","player__email","player__rank","player__gender","player__phone","player__image","player__bio")
                check_ambassador = AmbassadorsDetails.objects.filter(ambassador=player.player)
                if check_ambassador:
                    follower_count = check_ambassador.first().follower.count()
                    following_count = check_ambassador.first().following.count()
                    is_follow = True if check_user.first() in check_ambassador.first().follower.all() else False
                    posts = AmbassadorsPost.objects.filter(created_by=player.player)
                    post_count = posts.count()
                    post_data = posts.values()
                else:
                    is_follow = False
                    follower_count = 0
                    following_count = 0
                    post_count = 0
                    post_data = []
                ambassador_data = {"follower":follower_count,
                                  "following":following_count,
                                  "is_follow":is_follow,
                                  "posts":post_count,
                                  "post_data":post_data}
                data['status'] = status.HTTP_200_OK
                data['player_data'] = player_data
                data['ambassador_data'] = ambassador_data
                data['message'] = f'Data fetched successfully.'
            else:
                data['status'] = status.HTTP_404_NOT_FOUND
                data['player_data'] = []
                data['ambassador_data'] = []
                data['message'] = f'User is not a player'
        else:
            data['status'] = status.HTTP_404_NOT_FOUND
            data['player_data'] = []
            data['ambassador_data'] = []
            data['message'] = f'User not found'
    except Exception as e:
        data['status'] = status.HTTP_400_BAD_REQUEST
        data['player_data'] = []
        data['ambassador_data'] = []
        data['message'] = f'{str(e)}'
    return Response(data)


@api_view(("GET",))
def player_team_details(request):
    data = {'status':'','message':''}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        player_uuid = request.GET.get('player_uuid')
        player_secret_key = request.GET.get('player_secret_key')
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        if check_user.exists() :
            user = check_user.first()
            check_player = Player.objects.filter(uuid=player_uuid,secret_key=player_secret_key)
            if check_player:
                player = check_player.first()
                team_details = player.team.all()
                paginator = PageNumberPagination()
                paginator.page_size = 20
                paginated_teams = paginator.paginate_queryset(team_details, request)
                serializer  = TeamListSerializer(paginated_teams, many=True)
                main_data = serializer.data
                for team_data in main_data:
                    team_data['is_edit'] = team_data['created_by_uuid'] == user.uuid
                paginated_response = paginator.get_paginated_response(main_data)

                data['status'] = status.HTTP_200_OK
                data["count"] = paginated_response.data["count"]
                data["previous"] = paginated_response.data["previous"]
                data["next"] = paginated_response.data["next"]
                data['team_data'] = paginated_response.data["results"]
                data['message'] = f'Team details fetched successfully.'
            else:
                data['status'] = status.HTTP_404_NOT_FOUND
                data["count"] = 0
                data["previous"] = None
                data["next"] = None
                data['team_data'] = []
                data['message'] = f'User is not a player.' 
        else:
            data['status'] = status.HTTP_404_NOT_FOUND
            data["count"] = 0
            data["previous"] = None
            data["next"] = None
            data['team_data'] = []
            data['message'] = f'User not found.'
    except Exception as e:
        data['status'] = status.HTTP_400_BAD_REQUEST
        data["count"] = 0
        data["previous"] = None
        data["next"] = None
        data['team_data'] = []
        data['message'] = f'{str(e)}'
    return Response(data)  


@api_view(("GET",))
def player_match_statistics(request):
    data = {'status': '', 'message': ''}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        player_uuid = request.GET.get('player_uuid')
        player_secret_key = request.GET.get('player_secret_key')

        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if check_user.exists():
            check_player = Player.objects.filter(uuid=player_uuid, secret_key=player_secret_key)
            if check_player:
                player = check_player.first()
                total_played_matches = 0
                win_match = 0
                matches = []
                team_ids = list(player.team.values_list('id', flat=True))

                today = timezone.now().date()
                twelve_months_ago = today - timedelta(days=365)
                if len(team_ids) > 0:
                    for team_id in team_ids:
                        check_match = Tournament.objects.filter(
                            Q(team1_id=team_id, is_completed=True) | Q(team2_id=team_id, is_completed=True))
                        win_check_match = check_match.filter(winner_team_id=team_id).count()
                        total_played_matches += check_match.count()
                        win_match += win_check_match
                        match = Tournament.objects.filter(
                                    Q(team1=team_id) | Q(team2=team_id),
                                    is_completed=True,
                                    playing_date_time__date__gte=twelve_months_ago,
                                    playing_date_time__date__lte=today
                                ).annotate(
                                    month=TruncMonth('playing_date_time')
                                ).values(
                                    'month'
                                ).annotate(
                                    matches_played=Count('id'),
                                    wins=Count(Case(
                                        When(winner_team=team_id, then=1),
                                        output_field=IntegerField()
                                    )),
                                ).order_by('month')
                        matches.extend(match)
                lost_match = total_played_matches - win_match

                match_count = {"total_matches": total_played_matches,
                            "wim_matches": win_match,
                            "lost_matches": lost_match
                            }

                months = []
                for i in range(12):
                    month = today - relativedelta(months=i)
                    first_day_of_month = month.replace(day=1)
                    months.append(first_day_of_month.strftime('%Y-%m'))
                months = sorted(list(set(months)))
                match_data = {month: {'matches_played': 0, 'wins': 0} for month in months}

                for mat in matches:
                    month_str = mat['month'].strftime('%Y-%m')
                    match_data[month_str]['matches_played'] += mat['matches_played']
                    match_data[month_str]['wins'] += mat['wins']

                sorted_months = sorted(months) 
                matches_played = [match_data[month]['matches_played'] for month in sorted_months]
                wins = [match_data[month]['wins'] for month in sorted_months]

                data_set = {"month": sorted_months,
                            "match_played": matches_played,
                            "win": wins
                            }
                data['status'] = status.HTTP_200_OK
                data['match_count'] = match_count
                data['data_set'] = data_set
                data['message'] = 'Data fetched successfully.'
            else:
                data['status'] = status.HTTP_200_OK
                data['match_count'] = []
                data['data_set'] = []
                data['message'] = 'User is not a player.'
        else:
            data['status'] = status.HTTP_200_OK
            data['match_count'] = []
            data['data_set'] = []
            data['message'] = 'User not found.'
    except Exception as e:
        data['status'] = status.HTTP_400_BAD_REQUEST
        data['match_count'] = []
        data['data_set'] = []
        data['message'] = f'{str(e)}'
    return Response(data)


@api_view(("GET",))
def team_profile_details(request):
    data = {'status':'','message':''}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        t_uuid = request.GET.get('t_uuid')
        t_secret_key = request.GET.get('t_secret_key')
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        if check_user.exists() :
            user = check_user.first()
            check_team = Team.objects.filter(uuid=t_uuid,secret_key=t_secret_key)
            if check_team.exists() :
                team = check_team.first()
                serializer  = TeamListSerializer(team)
                team_data = serializer.data
                team_data['is_edit'] = team_data['created_by_uuid'] == str(user.uuid)
                data['status'] = status.HTTP_200_OK
                data['team_data'] = team_data
                data['message'] = f'Team details fetched successfully.'
            else:
                data['status'] = status.HTTP_404_NOT_FOUND
                data['team_data'] = []
                data['message'] = f'Team not found.' 
        else:
            data['status'] = status.HTTP_404_NOT_FOUND
            data['team_data'] = []
            data['message'] = f'User not found.'

    except Exception as e:
        data['status'] = status.HTTP_400_BAD_REQUEST
        data['team_data'] = []
        data['message'] = f'{str(e)}'
    return Response(data)


@api_view(("GET",))
def team_statistics(request):
    data = {'status':'','message':''}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        t_uuid = request.GET.get('t_uuid')
        t_secret_key = request.GET.get('t_secret_key')
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        if check_user.exists() :
            check_team = Team.objects.filter(uuid=t_uuid,secret_key=t_secret_key)
            if check_team.exists() :
                team = check_team.first()
                today = timezone.now().date()
                twelve_months_ago = today - timedelta(days=365)
                check_match = Tournament.objects.filter(
                            Q(team1_id=team.id, is_completed=True) | Q(team2_id=team.id, is_completed=True))
                win_check_match = check_match.filter(winner_team_id=team.id).count()
                total_played_matches = check_match.count()
                win_match = win_check_match
                matches = Tournament.objects.filter(
                            Q(team1=team.id) | Q(team2=team.id),
                            is_completed=True,
                            playing_date_time__date__gte=twelve_months_ago,
                            playing_date_time__date__lte=today
                        ).annotate(
                            month=TruncMonth('playing_date_time')
                        ).values(
                            'month'
                        ).annotate(
                            matches_played=Count('id'),
                            wins=Count(Case(
                                When(winner_team=team.id, then=1),
                                output_field=IntegerField()
                            )),
                        ).order_by('month')
                lost_match = total_played_matches - win_match

                match_count = {"total_matches": total_played_matches,
                            "wim_matches": win_match,
                            "lost_matches": lost_match
                            }
                months = []
                for i in range(12):
                    month = today - relativedelta(months=i)
                    first_day_of_month = month.replace(day=1)
                    months.append(first_day_of_month.strftime('%Y-%m'))
                months = sorted(list(set(months)))
                match_data = {month: {'matches_played': 0, 'wins': 0} for month in months}

                for mat in matches:
                    month_str = mat['month'].strftime('%Y-%m')
                    match_data[month_str]['matches_played'] += mat['matches_played']
                    match_data[month_str]['wins'] += mat['wins']

                sorted_months = sorted(months) 
                matches_played = [match_data[month]['matches_played'] for month in sorted_months]
                wins = [match_data[month]['wins'] for month in sorted_months]

                data_set = {"month": sorted_months,
                            "match_played": matches_played,
                            "win": wins
                            }
                data['status'] = status.HTTP_200_OK
                data['match_count'] = match_count
                data['data_set'] = data_set
                data['message'] = 'Data fetched successfully.'
            else:
                data['status'] = status.HTTP_200_OK
                data['match_count'] = []
                data['data_set'] = []
                data['message'] = 'Data fetched successfully.'
        else:
            data['status'] = status.HTTP_200_OK
            data['match_count'] = []
            data['data_set'] = []
            data['message'] = 'Data fetched successfully.'

    except Exception as e:
        data['status'] = status.HTTP_400_BAD_REQUEST
        data['team_data'] = []
        data['message'] = f'{str(e)}'
    return Response(data)


@api_view(("GET",))
def team_match_history(request):
    data = {'status':'', 'message':''}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        t_uuid = request.GET.get('t_uuid')
        t_secret_key = request.GET.get('t_secret_key')
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        matches = []
        if check_user.exists() :
            check_team = Team.objects.filter(uuid=t_uuid,secret_key=t_secret_key)
            if check_team.exists() :
                team = check_team.first()
                match = Tournament.objects.filter(Q(team1_id=team.id) | Q(team2_id=team.id)).filter(is_completed=True).order_by("playing_date_time")
                if match:
                    serializer = TournamentSerializer(match, many=True)
                    matches.append(serializer.data)
                for match in matches:
                    for mat in match:                    
                        mat["team1"]["player_images"] = [
                                player_image if player_image else None 
                                for player_image in Player.objects.filter(team__id=mat["team1"]["id"]).values_list("player__image", flat=True)
                            ]
                        mat["team2"]["player_images"] = [
                                player_image if player_image else None 
                                for player_image in Player.objects.filter(team__id=mat["team2"]["id"]).values_list("player__image", flat=True)
                            ]
                        mat["team1"]["player_names"] = [
                                player_name for player_name in Player.objects.filter(team__id=mat["team1"]["id"]).values_list("player_full_name", flat=True)
                            ]
                        mat["team2"]["player_names"] = [
                                player_name for player_name in Player.objects.filter(team__id=mat["team2"]["id"]).values_list("player_full_name", flat=True)
                            ]    
                data['status'] = status.HTTP_200_OK
                data['message'] = f"Data fetched successfully."  
                data['data'] = matches    
            else:
                data['status'] = status.HTTP_404_NOT_FOUND
                data['message'] = f"Team not found."  
                data['data'] = []                      
        else:
            data['status'] = status.HTTP_404_NOT_FOUND
            data['message'] = f"User not found."  
            data['data'] = []
    except Exception as e:
        data['status'] = status.HTTP_400_BAD_REQUEST
        data['message'] = f"{e}"
        data['data'] = []
    return Response(data)    


@api_view(("GET",))
def team_tournament_history(request):
    data = {'status':'', 'message':''}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        t_uuid = request.GET.get('t_uuid')
        t_secret_key = request.GET.get('t_secret_key')
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        matches = []
        if check_user.exists() :
            check_team = Team.objects.filter(uuid=t_uuid,secret_key=t_secret_key)
            if check_team.exists() :
                team = check_team.first()
                check_leagues = Leagues.objects.filter(registered_team__in=[team.id], is_complete=True)
                serializer = LeagueListSerializer(check_leagues, many=True)
                league_data = serializer.data
                for item in league_data:
                    league_id = item.get("id")
                    total_matches = Tournament.objects.filter(leagues_id=league_id)
                    team_matches = total_matches.filter(Q(team1_id=team.id) | Q(team2_id=team.id))
                    team_win_matches = team_matches.filter(winner_team_id=team.id)
                    team_lost_matches = team_matches.count() - team_win_matches.count()
                    item["total_matches"] = total_matches.count()
                    item["team_matches"] = team_matches.count()
                    item["team_win_matches"] = team_win_matches.count()
                    item["team_lost_matches"] = team_lost_matches
                    item["is_winner"] = item["winner_team"] == team.name

                data['status'] = status.HTTP_200_OK
                data['message'] = f"Data fetched successfully."  
                data['data'] = league_data   
            else:
                data['status'] = status.HTTP_404_NOT_FOUND
                data['message'] = f"Team not found."  
                data['data'] = []                      
        else:
            data['status'] = status.HTTP_404_NOT_FOUND
            data['message'] = f"User not found."  
            data['data'] = []
    except Exception as e:
        data['status'] = status.HTTP_400_BAD_REQUEST
        data['message'] = f"{e}"
        data['data'] = []
    return Response(data)


@api_view(("GET",))
def get_final_match_details(request):
    data = {'status':'', 'message':'', 'data':[]}
    try:
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        league_uuid = request.GET.get('league_uuid')
        league_secret_key = request.GET.get('league_secret_key')
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        check_league = Leagues.objects.filter(uuid=league_uuid, secret_key=league_secret_key)
        if check_user and check_league:
            league = check_league.first()
            league_type = league.play_type
            tournaments = Tournament.objects.filter(leagues=league)
            if tournaments:
                if league_type == 'Group Stage' or league_type == 'Single Elimination':
                    final_match = tournaments.filter(match_type='Final').first()
                 
                    serializer = TournamentSerializer(final_match)
                    data['status'] = status.HTTP_200_OK
                    data['message'] = 'Final match data fetched successfully.'
                    data['data'] = serializer.data
                else:
                    data['status'] = status.HTTP_200_OK
                    data['message'] = 'No final match, check tournament details.'
                    data['data'] = serializer.data
            else:
                data['status'] = status.HTTP_404_NOT_FOUND
                data['message'] = 'Matches have not started yet.'
                data['data'] = []
        else:
            data['status'] = status.HTTP_404_NOT_FOUND
            data['message'] = 'User or League not found.'
            data['data'] = []
    except Exception as e:
        data['status'] = status.HTTP_400_BAD_REQUEST
        data['message'] = f'{str(e)}'
        data['data'] = []
    return Response(data)
                

@api_view(("GET",))
def home_page_stats_count(request):
    data = {'status':'', 'message':''}
    try:
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if check_user.exists():
            get_user = check_user.first()
            today_date = datetime.now()
            total_courts = AdvertiserFacility.objects.all().count()
            total_tournaments = Leagues.objects.filter(leagues_start_date__date__lte=today_date,leagues_end_date__date__gte=today_date, is_complete=False).count()

            created_teams = Team.objects.filter(created_by=get_user).count()
            if get_user.is_player:
                player = Player.objects.filter(player=get_user).first()
                player_teams = player.team.all().count()
            total_teams = created_teams + player_teams

            total_players = Player.objects.all().count()
            total_clubs_resorts = 0
            total_open_plays = 0
            team_type = LeaguesTeamType.objects.filter(name="Open-team").first()
            player = Player.objects.filter(player_email=get_user.email).first()
            if player:
                teams = player.team.all()
                if teams.exists():                    
                    open_plays = Leagues.objects.filter(registered_team__in=teams, team_type=team_type, is_complete=False).distinct().count()
                    total_open_plays += open_plays

            data["status"] = status.HTTP_200_OK
            data["message"] = "Stats count fetched successfully."        
            data["total_courts"] = total_courts
            data["total_tournaments"] = total_tournaments
            data["total_teams"] = total_teams
            data["total_players"] = total_players
            data["total_open_plays"] = total_open_plays
            data["total_clubs_resorts"] = total_clubs_resorts
        else:
            data["status"] = status.HTTP_404_NOT_FOUND
            data["message"] = "User not found."        
            data["total_courts"] = 0
            data["total_tournaments"] = 0
            data["total_teams"] = 0
            data["total_players"] = 0
            data["total_open_plays"] = 0
            data["total_clubs_resorts"] = 0

    except Exception as e:
        data['status'] = status.HTTP_400_BAD_REQUEST
        data['message'] = f'{str(e)}'
       
    return Response(data)


@api_view(('GET',))
def open_play_details(request):
    data = {'status': '', 'data': [], 'message': ''}
    try:
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')

        if not user_uuid or not user_secret_key:
            data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, "Missing required parameters"
            return Response(data)

        check_user = User.objects.filter(secret_key=user_secret_key, uuid=user_uuid).first()
        if not check_user:
            data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, "User not found"
            return Response(data)
                
        all_leagues = []

        if check_user.is_player:
            check_player = Player.objects.filter(player_email=check_user.email).first()
            if check_player:
                team_ids = check_player.team.values_list('id', flat=True)
                all_leagues = Leagues.objects.filter(
                    Q(is_complete=False) & 
                    (Q(registered_team__id__in=team_ids) | Q(created_by=check_user)),
                    team_type__name="Open-team"
                ).distinct()

            leagues = all_leagues.values(
                "id", "uuid", "secret_key", "name", "location", "leagues_start_date", "leagues_end_date",
                "registration_start_date", "registration_end_date", "team_type__name", "team_person__name",
                "any_rank", "start_rank", "end_rank", "street", "city", "state", "postal_code", "country",
                "complete_address", "latitude", "longitude", "image", "others_fees", "league_type", "registration_fee"
            )

            output = []
            grouped_data = {}

            for item in list(leagues):
  
                item["is_reg_diable"] = True
                match_ = Tournament.objects.filter(leagues_id=item["id"]).values()
                if match_.exists():
                    item["is_reg_diable"] = False

                le = Leagues.objects.filter(id=item["id"]).first()
                sub_organizer_list = list(le.add_organizer.all().values_list("id", flat=True))
                reg_team = le.registered_team.all().count()
                max_team = le.max_number_team
                if max_team <= reg_team:
                    item["is_reg_diable"] = False

                if check_user == le.created_by:
                    item["main_organizer"] = True
                    item["sub_organizer"] = False
                elif check_user.id in sub_organizer_list:
                    item["main_organizer"] = False
                    item["sub_organizer"] = True
                else:
                    item["main_organizer"] = False
                    item["sub_organizer"] = False

                key = item['name']
                if key not in grouped_data:
                    grouped_data[key] = {
                        'name': item['name'],
                        'lat': item['latitude'],
                        'long': item["longitude"],
                        'registration_start_date': item["registration_start_date"],
                        'registration_end_date': item["registration_end_date"],
                        'leagues_start_date': item["leagues_start_date"],
                        'leagues_end_date': item["leagues_end_date"],
                        'location': item["location"],
                        'image': item["image"],
                        'type': [item['team_type__name']],
                        'data': [item]
                    }
                else:
                    grouped_data[key]['type'].append(item['team_type__name'])
                    grouped_data[key]['data'].append(item)

            for key, value in grouped_data.items():
                value["is_edit"] = True
                value["is_delete"] = True
                output.append(value)

            leagues = output

            data['status'], data['data'], data['message'] = status.HTTP_200_OK, leagues, "Data found"
        else:
            data['status'], data['message'] = status.HTTP_200_OK, "No leagues found"

    except Exception as e:
        data['status'], data['message'] = status.HTTP_500_INTERNAL_SERVER_ERROR, f"Error: {str(e)}"

    return Response(data)


# @api_view(["GET"])
# def search_players_by_location(request):
#     data = {'status': '', 'message': ''}
#     try:      
#         user_uuid = request.GET.get('user_uuid')
#         user_secret_key = request.GET.get('user_secret_key')
#         latitude = float(request.GET.get('latitude', 0))
#         longitude = float(request.GET.get('longitude', 0))
#         radius = float(request.GET.get('radius', 20))

#         check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
#         if not check_user.exists():
#             data.update({
#                 "count": 0,
#                 "previous": None,
#                 "next": None,
#                 "data": [],
#                 "status": status.HTTP_401_UNAUTHORIZED,
#                 "message": "Unauthorized access"
#             })
#             return Response(data)

#         get_user = check_user.first()
#         nearby_players = []

#         players = Player.objects.all()
#         for player in players:
#             print(latitude, longitude, player)
#             if player.player.latitude and player.player.longitude:
#                 distance = haversine(latitude, longitude, player.player.latitude, player.player.longitude)
#                 if distance <= radius:
#                     nearby_players.append({
#                         'player': player,
#                         'distance_km': distance
#                     })

#         following_instance, created = AmbassadorsDetails.objects.get_or_create(ambassador=get_user)
#         following_ids = list(following_instance.following.all().values_list("id", flat=True))

#         nearby_players.sort(key=lambda x: x['distance_km'])

#         paginator = PageNumberPagination()
#         paginator.page_size = 10
#         result_page = paginator.paginate_queryset(nearby_players, request)
#         serializer = PlayerSerializer([item['player'] for item in result_page], many=True, context={'request': request})
#         serialized_data = serializer.data

#         for index, p_data in enumerate(serialized_data):
#             p_data["is_edit"] = p_data["created_by_id"] == get_user.id
#             p_data["is_follow"] = p_data["id"] in following_ids
#             p_data["distance_km"] = result_page[index]["distance_km"]

#         if not serialized_data:
#             data.update({
#                 "status": status.HTTP_200_OK,
#                 "count": 0,
#                 "previous": None,
#                 "next": None,
#                 "data": [],
#                 "message": "No results found"
#             })
#         else:
#             paginated_response = paginator.get_paginated_response(serialized_data)
#             data.update({
#                 "status": status.HTTP_200_OK,
#                 "count": paginated_response.data["count"],
#                 "previous": paginated_response.data["previous"],
#                 "next": paginated_response.data["next"],
#                 "data": paginated_response.data["results"],
#                 "message": "Data found"
#             })

#     except Exception as e:
#         data.update({
#             "count": 0,
#             "previous": None,
#             "next": None,
#             "data": [],
#             "status": status.HTTP_400_BAD_REQUEST,
#             "message": str(e)
#         })

#     return Response(data)


# @api_view(["GET"])
# def search_players_by_location(request):
#     data = {'status': '', 'message': ''}
#     try:      
#         user_uuid = request.GET.get('user_uuid')
#         user_secret_key = request.GET.get('user_secret_key')
#         latitude = float(request.GET.get('latitude', 0))
#         longitude = float(request.GET.get('longitude', 0))
#         radius = float(request.GET.get('radius', 20))

#         check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
#         if not check_user.exists():
#             data.update({
#                 "count": 0,
#                 "previous": None,
#                 "next": None,
#                 "data": [],
#                 "status": status.HTTP_401_UNAUTHORIZED,
#                 "message": "Unauthorized access"
#             })
#             return Response(data)

#         get_user = check_user.first()
#         nearby_players = []

#         players = Player.objects.all()
#         for player in players:
#             print(latitude, longitude, player)
#             if player.player.latitude and player.player.longitude:
#                 distance = haversine(latitude, longitude, player.player.latitude, player.player.longitude)
#                 if distance <= radius:
#                     nearby_players.append({
#                         "player_id":player.id,
#                         "player_uuid":player.uuid,
#                         "player_secret_key":player.secret_key,
#                         "user_id":player.player.id,
#                         "user_uuid": player.player.uuid,
#                         "user_secret_key":player.player.secret_key,
#                         "username": player.player.username,
#                         "first_name":player.player.first_name,
#                         "last_name": player.player.last_name,
#                         "image":player.player.image.url,
#                         "distance_km": distance,
#                         "latitude": player.player.latitude,
#                         "longitude": player.player.longitude,
#                         "location":player.player.full_location

#                     })       

#         nearby_players.sort(key=lambda x: x['distance_km'])

#         paginator = PageNumberPagination()
#         paginator.page_size = 10
#         result_page = paginator.paginate_queryset(nearby_players, request)
        
#         if not result_page:
#             data.update({
#                 "status": status.HTTP_200_OK,
#                 "count": 0,
#                 "previous": None,
#                 "next": None,
#                 "data": [],
#                 "message": "No results found"
#             })
#         else:
#             paginated_response = paginator.get_paginated_response(result_page)
#             data.update({
#                 "status": status.HTTP_200_OK,
#                 "count": paginated_response.data["count"],
#                 "previous": paginated_response.data["previous"],
#                 "next": paginated_response.data["next"],
#                 "data": paginated_response.data["results"],
#                 "message": "Data found"
#             })

#     except Exception as e:
#         data.update({
#             "count": 0,
#             "previous": None,
#             "next": None,
#             "data": [],
#             "status": status.HTTP_400_BAD_REQUEST,
#             "message": str(e)
#         })

#     return Response(data)


# @api_view(["GET"])
# def search_players_by_location(request):
#     data = {'status': '', 'message': ''}
#     try:      
#         user_uuid = request.GET.get('user_uuid')
#         user_secret_key = request.GET.get('user_secret_key')
#         latitude = request.GET.get('latitude', '')
#         longitude = request.GET.get('longitude', '')
#         radius = float(request.GET.get('radius', 20))

#         check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
#         if not check_user.exists():
#             data.update({
#                 "count": 0,
#                 "previous": None,
#                 "next": None,
#                 "data": [],
#                 "status": status.HTTP_401_UNAUTHORIZED,
#                 "message": "Unauthorized access"
#             })
#             return Response(data)

#         get_user = check_user.first()
#         nearby_players = []

#         players = Player.objects.all()

#         if latitude in [0, '', None] or longitude in [0, '', None]:            
#             nearby_players = [{'player': player, 'distance_km': None} for player in players]
#         else:
#             latitude = float(latitude)
#             longitude = float(longitude)

#             for player in players:
#                 if player.player.latitude and player.player.longitude:
#                     distance = haversine(latitude, longitude, float(player.player.latitude), float(player.player.longitude))
#                     if distance <= radius:
#                         nearby_players.append({
#                             'player': player,
#                             'distance_km': distance
#                         })

#         following_instance, created = AmbassadorsDetails.objects.get_or_create(ambassador=get_user)
#         following_ids = list(following_instance.following.all().values_list("id", flat=True))

#         nearby_players.sort(key=lambda x: x['distance_km'] if x['distance_km'] is not None else float('inf'))

#         paginator = PageNumberPagination()
#         paginator.page_size = 10
#         result_page = paginator.paginate_queryset(nearby_players, request)
#         serializer = PlayerSerializer([item['player'] for item in result_page], many=True, context={'request': request})
#         serialized_data = serializer.data

#         for index, p_data in enumerate(serialized_data):
#             p_data["is_edit"] = p_data["created_by_id"] == get_user.id
#             p_data["is_follow"] = p_data["id"] in following_ids
#             p_data["distance_km"] = result_page[index].get("distance_km")

#         if not serialized_data:
#             data.update({
#                 "status": status.HTTP_200_OK,
#                 "count": 0,
#                 "previous": None,
#                 "next": None,
#                 "data": [],
#                 "message": "No results found"
#             })
#         else:
#             paginated_response = paginator.get_paginated_response(serialized_data)
#             data.update({
#                 "status": status.HTTP_200_OK,
#                 "count": paginated_response.data["count"],
#                 "previous": paginated_response.data["previous"],
#                 "next": paginated_response.data["next"],
#                 "data": paginated_response.data["results"],
#                 "message": "Data found"
#             })

#     except Exception as e:
#         data.update({
#             "count": 0,
#             "previous": None,
#             "next": None,
#             "data": [],
#             "status": status.HTTP_400_BAD_REQUEST,
#             "message": str(e)
#         })

#     return Response(data)


@api_view(["GET"])
def search_players_by_location(request):
    data = {'status': '', 'message': ''}
    
    try:
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        latitude = request.GET.get('latitude', '')
        longitude = request.GET.get('longitude', '')
        radius = float(request.GET.get('radius', 100))
        search_text = request.GET.get('search_text')
        gender = request.GET.get('gender')
        start_rank = request.GET.get('start_rank')
        end_rank = request.GET.get('end_rank')

        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if not check_user.exists():
            return Response({
                "count": 0, "previous": None, "next": None, "data": [],
                "status": status.HTTP_401_UNAUTHORIZED, "message": "Unauthorized access"
            })
        
        get_user = check_user.first()
        all_players = []
        available_players = []
        
        players = Player.objects.all()
        
        if search_text not in ['', None, "null"]:
            all_players = [  
                    {'player': player, 'distance_km': None} 
                    for player in players 
                    if search_text.lower() in player.player.first_name.lower() or 
                    search_text.lower() in player.player.last_name.lower()
                ]

            if latitude not in [0, '', None, "null"] and longitude not in [0, '', None, "null"]:
                latitude, longitude = float(latitude), float(longitude)
                
                for p in all_players:
                    # Check that the player's latitude and longitude are valid
                    if p['player'].player.latitude not in ["null", '', None] and p['player'].player.longitude not in ["null", '', None]:
                        distance = haversine(latitude, longitude, float(p['player'].player.latitude), float(p['player'].player.longitude))
                        if distance <= radius:
                            # Append only the player instance with the computed distance
                            available_players.append({'player': p['player'], 'distance_km': distance})
            
        else:            
            if latitude not in [0, '', None, "null"] and longitude not in [0, '', None, "null"]:
                latitude, longitude = float(latitude), float(longitude)
                
                for player in players:
                    if player.player.latitude not in ["null", '', None] and player.player.longitude not in ["null", '', None]:
                        distance = haversine(latitude, longitude, float(player.player.latitude), float(player.player.longitude))
                        if distance <= radius:
                            all_players.append({'player': player, 'distance_km': distance})
                            available_players.append({'player': player, 'distance_km': distance})

        if gender not in [None, "null", "", "None"]:
            if len(all_players) > 0:
                all_players = [p for p in all_players if p['player'].player.gender.lower() == gender.lower()]
            if len(available_players) > 0:
                available_players = [p for p in available_players if p['player'].player.gender.lower() == gender.lower()]
        
        if start_rank not in [None, "null", "", "None"] and end_rank not in [None, "null", "", "None"]:
            start_rank, end_rank = float(start_rank), float(end_rank)
            if len(all_players) > 0:
                all_players = [p for p in all_players if start_rank <= float(p['player'].player.rank) <= end_rank]
            if len(available_players) > 0:
                available_players = [p for p in available_players if start_rank <= float(p['player'].player.rank) <= end_rank]

        
        all_players.sort(key=lambda x: x['distance_km'] if x.get('distance_km') is not None else float('inf'))
        available_players.sort(key=lambda x: x['distance_km'] if x.get('distance_km') is not None else float('inf'))

        following_instance, _ = AmbassadorsDetails.objects.get_or_create(ambassador=get_user)
        following_ids = list(following_instance.following.all().values_list("id", flat=True))

        all_players_serialized = SearchPlayerSerializer(
            [p['player'] for p in all_players], many=True, context={'request': request}
        ).data
        
        available_players_serialized = SearchPlayerSerializer(
            [p['player'] for p in available_players], many=True, context={'request': request}
        ).data

        for p_data in all_players_serialized:            
            p_data["is_follow"] = p_data["id"] in following_ids
        
        for p_data in available_players_serialized:           
            p_data["is_follow"] = p_data["id"] in following_ids

        data.update({
            "status": status.HTTP_200_OK,
            "message": "Data found" if all_players_serialized or available_players_serialized else "No results found",
            "data": all_players_serialized,           
            "count": len(all_players_serialized),
            "available_count": len(available_players_serialized),
            "available_data": available_players_serialized,
        })

    except Exception as e:
        data.update({
            "status": status.HTTP_400_BAD_REQUEST,
            "message": str(e),
            "count": 0, "previous": None, "next": None, "data": [], "available_data": [], "available_count":0,
        })

    return Response(data)


# @api_view(["GET"])
# def search_tournaments_by_location(request):
#     data = {'status': '', 'message': '', 'data': []}
#     try:
#         user_uuid = request.GET.get('user_uuid')
#         user_secret_key = request.GET.get('user_secret_key')
#         latitude = float(request.GET.get('latitude', 0))
#         longitude = float(request.GET.get('longitude', 0))
#         radius = float(request.GET.get('radius', 20))

#         check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
#         if not check_user.exists():
#             data.update({
#                 "count": 0,
#                 "previous": None,
#                 "next": None,
#                 "data": [],
#                 "status": status.HTTP_401_UNAUTHORIZED,
#                 "message": "Unauthorized access"
#             })
#             return Response(data)

#         today_date = datetime.now()

#         live_leagues = Leagues.objects.filter(leagues_start_date__date__lte=today_date, leagues_end_date__date__gte=today_date)
#         upcoming_leagues = Leagues.objects.filter(
#             Q(registration_start_date__date__lte=today_date, registration_end_date__date__gte=today_date) |
#             Q(registration_start_date__date__gte=today_date) |
#             Q(registration_end_date__date__lte=today_date, leagues_start_date__date__gte=today_date)
#         )

#         current_leagues = {}
#         for league in live_leagues.union(upcoming_leagues):
#             current_leagues[league.id] = league

#         nearby_tournaments = []
#         for league_id, league in current_leagues.items():
#             if league.latitude and league.longitude:
#                 distance = haversine(latitude, longitude, float(league.latitude), float(league.longitude))
#                 if distance <= radius:
#                     nearby_tournaments.append({
#                         'league': league, 
#                         'distance_km': distance
#                     })

#         nearby_tournaments.sort(key=lambda x: x['distance_km'])

#         paginator = PageNumberPagination()
#         paginator.page_size = 10
#         result_page = paginator.paginate_queryset(nearby_tournaments, request)
#         response_data = [
#             {
#                 **tournament,
#                 "league": LeagueSerializer(tournament['league']).data  
#             }
#             for tournament in result_page
#         ]

#         if not response_data:
#             data.update({
#                 "count": 0,
#                 "previous": None,
#                 "next": None,
#                 "data": [],
#                 "status": status.HTTP_200_OK,
#                 "message": "No tournaments found"
#             })
#         else:
#             paginated_response = paginator.get_paginated_response(response_data)
#             data.update({
#                 "status": status.HTTP_200_OK,
#                 "count": paginated_response.data["count"],
#                 "previous": paginated_response.data["previous"],
#                 "next": paginated_response.data["next"],
#                 "data": paginated_response.data["results"],
#                 "message": "Tournaments found"
#             })

#     except Exception as e:
#         data.update({
#             "count": 0,
#             "previous": None,
#             "next": None,
#             "data": [],
#             "status": status.HTTP_400_BAD_REQUEST,
#             "message": str(e)
#         })

#     return Response(data)


@api_view(["GET"])
def search_tournaments_by_location(request):
    data = {'status': '', 'message': '', 'data': []}
    try:
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        latitude = request.GET.get('latitude', '')
        longitude = request.GET.get('longitude', '')
        radius = float(request.GET.get('radius', 20))

        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if not check_user.exists():
            data.update({
                "count": 0,
                "previous": None,
                "next": None,
                "data": [],
                "status": status.HTTP_401_UNAUTHORIZED,
                "message": "Unauthorized access"
            })
            return Response(data)

        today_date = datetime.now()

        live_leagues = Leagues.objects.filter(leagues_start_date__date__lte=today_date, leagues_end_date__date__gte=today_date)
        upcoming_leagues = Leagues.objects.filter(
            Q(registration_start_date__date__lte=today_date, registration_end_date__date__gte=today_date) |
            Q(registration_start_date__date__gte=today_date) |
            Q(registration_end_date__date__lte=today_date, leagues_start_date__date__gte=today_date)
        )

        current_leagues = {}
        for league in live_leagues.union(upcoming_leagues):
            current_leagues[league.id] = league

        nearby_tournaments = []

        if latitude in [0, '', None] or longitude in [0, '', None]:
            nearby_tournaments = [{'league': league, 'distance_km': None} for league in current_leagues.values()]
        else:
            latitude = float(latitude)
            longitude = float(longitude)

            for league_id, league in current_leagues.items():
                if league.latitude and league.longitude:
                    distance = haversine(latitude, longitude, float(league.latitude), float(league.longitude))
                    if distance <= radius:
                        nearby_tournaments.append({
                            'league': league, 
                            'distance_km': distance
                        })

        nearby_tournaments.sort(key=lambda x: x['distance_km'] if x['distance_km'] is not None else float('inf'))

        paginator = PageNumberPagination()
        paginator.page_size = 10
        result_page = paginator.paginate_queryset(nearby_tournaments, request)
        response_data = [
            LeagueSerializer(tournament['league']).data  
            for tournament in result_page
        ]

        if not response_data:
            data.update({
                "count": 0,
                "previous": None,
                "next": None,
                "data": [],
                "status": status.HTTP_200_OK,
                "message": "No tournaments found"
            })
        else:
            paginated_response = paginator.get_paginated_response(response_data)
            data.update({
                "status": status.HTTP_200_OK,
                "count": paginated_response.data["count"],
                "previous": paginated_response.data["previous"],
                "next": paginated_response.data["next"],
                "data": paginated_response.data["results"],
                "message": "Tournaments found"
            })

    except Exception as e:
        data.update({
            "count": 0,
            "previous": None,
            "next": None,
            "data": [],
            "status": status.HTTP_400_BAD_REQUEST,
            "message": str(e)
        })
    return Response(data)


# @api_view(["GET"])
# def filter_player_by_gender_and_rank(request):
#     data = {'status': '', 'message': '', 'data': []}
#     try:
#         user_uuid = request.GET.get('user_uuid')
#         user_secret_key = request.GET.get('user_secret_key')
#         filter_by = request.GET.get('filter_by')
#         value = request.GET.get('value')
#         start_rank = request.GET.get('start_rank')
#         end_rank = request.GET.get('end_rank')

#         if not (user_uuid and user_secret_key and filter_by and value):
#             data["status"], data["message"] = status.HTTP_400_BAD_REQUEST, "Missing required parameters."
#             return Response(data)

#         if filter_by not in ["gender", "rank"]:
#             data["status"], data["message"] = status.HTTP_400_BAD_REQUEST, "Invalid filter_by parameter. Use 'gender' or 'rank'."
#             return Response(data)

#         check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
#         if not check_user.exists():
#             data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "User not found."
#             return Response(data)
        
#         get_user = check_user.first()        
#         if filter_by == "gender":           
            
#             if value.lower() not in ["male", "female", "other"]:
#                 data["status"], data["message"] = status.HTTP_400_BAD_REQUEST, "Invalid gender value. Use 'male', 'female' or 'other."
#                 return Response(data)
#             else:
#                 players = Player.objects.filter(player__gender__iexact=value).order_by("-id")

#         elif filter_by == "rank":
            
#             if not (start_rank and end_rank):
#                 data["status"], data["message"] = status.HTTP_400_BAD_REQUEST, "Both start_rank and end_rank are required."
#                 return Response(data)
#             try:
#                 start_rank = float(start_rank)
#                 end_rank = float(end_rank)
#             except ValueError:
#                 data["status"], data["message"] = status.HTTP_400_BAD_REQUEST, "Invalid rank format. Must be a number."
#                 return Response(data)
            
#             players = Player.objects.filter(player__rank__gte=start_rank, player__rank__lte=end_rank).order_by("-id")
            
#         following = AmbassadorsDetails.objects.filter(ambassador=get_user)
#         if following.exists():
#             following_instance = following.first()
#             following_ids = list(following_instance.following.all().values_list("id", flat=True))
#         else:
#             following_instance = AmbassadorsDetails.objects.create(ambassador=get_user)
#             following_instance.save()
#             following_ids = list(following_instance.following.all().values_list("id", flat=True))
        
#         paginator = PageNumberPagination()
#         paginator.page_size = 10  
#         result_page = paginator.paginate_queryset(players, request)
#         serializer = PlayerSerializer(result_page, many=True, context={'request': request})
#         serialized_data = serializer.data
        
#         def add_additional_fields(player_data):
#             player_data["is_edit"] = player_data["created_by_id"] == get_user.id
#             player_data["is_follow"] = player_data["player_id"] in following_ids
#             return player_data

#         serialized_data = list(map(add_additional_fields, serialized_data))            

#         if not serialized_data:
#             data["status"] = status.HTTP_200_OK
#             data["count"] = 0
#             data["previous"] = None
#             data["next"] = None
#             data["data"] = []
#             data["message"] = "No Result found"
#         else:
#             paginated_response = paginator.get_paginated_response(serialized_data)
#             data["status"] = status.HTTP_200_OK
#             data["count"] = paginated_response.data["count"]
#             data["previous"] = paginated_response.data["previous"]
#             data["next"] = paginated_response.data["next"]
#             data["data"] = paginated_response.data["results"]
#             data["message"] = "Data found"  

#     except Exception as e:        
#         data["status"], data["message"] = status.HTTP_400_BAD_REQUEST, f"Error: {e}"
#     return Response(data)
    
   
# @api_view(["GET"])
# def filter_team(request):
#     data = {'status': '', 'message': '', 'data': []}
#     try:
#         user_uuid = request.GET.get('user_uuid')
#         user_secret_key = request.GET.get('user_secret_key')
#         filter_by = request.GET.get('filter_by')
#         value = request.GET.get('value')
#         start_rank = request.GET.get('start_rank')
#         end_rank = request.GET.get('end_rank')

#         if not (user_uuid and user_secret_key and filter_by and value):
#             data["status"], data["message"] = status.HTTP_400_BAD_REQUEST, "Missing required parameters."
#             return Response(data)
        
#         if filter_by not in ["team_person", "team_type", "rank"]:
#             data["status"], data["message"] = status.HTTP_400_BAD_REQUEST, "Invalid filter_by parameter. Use 'team_person', 'team_type' or 'rank'."
#             return Response(data)
        
#         check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
#         if not check_user.exists():
#             data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "User not found."
#             return Response(data)
        
#         get_user = check_user.first()
#         teams = Team.objects.annotate(
#             avg_rank=Avg(
#                 Case(
#                     When(
#                         player__player__rank__isnull=False,
#                         then=Cast(F("player__player__rank"), output_field=FloatField()),
#                     ),
#                     default=Value(1.0, output_field=FloatField()),
#                     output_field=FloatField(),
#                 )
#             )
#         )
#         if filter_by == "team_person":
#             if value.lower() not in ["one", "two"]:
#                 data["status"], data["message"] = status.HTTP_400_BAD_REQUEST, "Invalid team person value. Use 'one' or 'two'."
#                 return Response(data)
#             teams = teams.filter(team_person__icontains=value)

#         elif filter_by == "team_type":
#             if value.lower() not in ["men", "women", "co-ed", "open-team"]:
#                 data["status"], data["message"] = status.HTTP_400_BAD_REQUEST, "Invalid team type value. Use 'men', 'women', 'co-ed' or 'open-team'."
#                 return Response(data)
#             teams = teams.filter(team_type__iexact=value)

#         elif filter_by == "rank":
#             if not (start_rank and end_rank):
#                 data["status"], data["message"] = status.HTTP_400_BAD_REQUEST, "Both start_rank and end_rank are required."
#                 return Response(data)
#             try:
#                 start_rank = float(start_rank)
#                 end_rank = float(end_rank)
#             except ValueError:
#                 data["status"], data["message"] = status.HTTP_400_BAD_REQUEST, "Invalid rank format. Must be a number."
#                 return Response(data)
            
#             teams = teams.filter(
#                 Q(avg_rank__gte=start_rank) &
#                 Q(avg_rank__lte=end_rank)
#             )

#         paginator = PageNumberPagination()
#         paginator.page_size = 20
#         paginated_teams = paginator.paginate_queryset(teams.order_by("-id"), request)
        
#         main_data = []
#         for team in paginated_teams:
#             team_data = TeamListSerializer(team).data
#             team_data['team_uuid'] = team_data.pop('uuid')
#             team_data['team_secret_key'] = team_data.pop('secret_key')
#             team_data['team_name'] = team_data.pop('name')
#             team_data['location'] = team_data.pop('location')
#             team_data['team_rank'] = team.avg_rank
#             team_data['is_edit'] = team.created_by_id == get_user.id
#             main_data.append(team_data)

#         paginated_response = paginator.get_paginated_response(main_data)
        
#         data["status"] = status.HTTP_200_OK
#         data["count"] = paginated_response.data["count"]
#         data["previous"] = paginated_response.data["previous"]
#         data["next"] = paginated_response.data["next"]
#         data["data"] = paginated_response.data["results"]
#         data["message"] = "Data found for Admin" if get_user.is_admin or get_user.is_organizer else "Data found"

#     except Exception as e:        
#         data["status"], data["message"] = status.HTTP_400_BAD_REQUEST, f"Error: {e}"
#     return Response(data)
