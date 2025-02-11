import email
from django.shortcuts import render
from rest_framework.decorators import api_view
from rest_framework import status
from rest_framework.response import Response
from django.core.mail import send_mail
from apps.user.models import *
from apps.user.helpers import *
from apps.team.models import *
from django.db.models import Q, F, CharField, Value, ExpressionWrapper
from django.db.models.functions import Concat
from django.utils import timezone
from django.contrib.auth.hashers import make_password
from rest_framework import serializers
import random, json, base64, stripe
from django.conf import settings
from django.db.models import Sum
from django.db.models import Count, F, Q
from itertools import combinations
from django.forms.models import model_to_dict
from itertools import combinations
stripe.api_key = settings.STRIPE_PUBLIC_KEY
protocol = settings.PROTOCALL
# Create your views here.

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
    try:
        data = {'status':'','data':'','message':''}
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        if check_user.exists() :
            alldata = LeaguesTeamType.objects.all().order_by('name').values('uuid','secret_key','name')
            data["status"], data["data"], data["message"] = status.HTTP_200_OK, alldata,"Data found"
        else:
            data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "User not found"   
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
        
    return Response(data)

@api_view(('GET',))
def leagues_pesrsonType(request):
    try:
        data = {'status':'','message':''}
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


@api_view(('POST',))
def create_player(request):
    try:
        data = {'status':'','message':''}
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        p_first_name = request.data.get('p_first_name')
        p_last_name = request.data.get('p_last_name')
        p_email = request.data.get('p_email')
        p_phone_number = request.data.get('p_phone_number')
        p_ranking = request.data.get('p_ranking')
        p_image = request.FILES['p_image']

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
                                rank=p_ranking) 
            save_player.player = user
            save_player.save()
            # print(User.objects.all())
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
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
        
    return Response(data)


@api_view(('GET',))
def view_player(request):
    try:
        data = {'status':'','message':''}
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

                data["data"] = {"palyer_data":check_player.values("player__first_name","player__last_name","player_ranking","player__rank","player__image","player__email","player__phone"),
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
    try:
        data = {'status': '', 'message': ''}
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
                                                                                    <p style="font-size: 17px;font-weight: 500;color:#333333">If you face any Problem, please contact our support team immediately at pickle.it0987@gmail.com to secure your account.</p>
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
                'pickle.it0987@gmail.com',  # Replace with your email address
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
    try:
        data = {'status':'','message':''}
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        p_uuid = request.data.get('p_uuid')
        p_secret_key = request.data.get('p_secret_key')
        p_first_name = request.data.get('p_first_name')
        p_last_name = request.data.get('p_last_name')
        p_phone_number = request.data.get('p_phone_number')
        p_ranking = request.data.get('p_ranking')
        p_image = request.FILES.get('p_image')
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
                p_user = User.objects.filter(id=check_player.first().player.id)
                if p_user.exists() :
                    get_p_user = p_user.first()
                    get_p_user.first_name = p_first_name
                    get_p_user.last_name = p_last_name
                    get_p_user.rank = p_ranking
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
    try:
        data = {'status':'','message':''}
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
                    data["status"], data["message"] = status.HTTP_200_OK, "player Deleted successfully"
                if check_player.first().created_by == check_user.first():
                    get_player.delete()
                    check_player.delete()
                    data["status"], data["message"] = status.HTTP_200_OK, "player Deleted successfully"
                else:
                    data["status"], data["message"] = status.HTTP_200_OK, "Something is wrong"
            else:
                data["status"], data["message"] = status.HTTP_200_OK, "player not found"
        else:
            data["status"], data["message"] = status.HTTP_200_OK, "user not found"
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


@api_view(('GET',))
def list_player(request):
    try:
        data = {'status': '', 'data': [], 'message': ''}
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
                user_image = User.objects.filter(id=user_id).values("username","email","first_name","last_name","phone","uuid","secret_key","image","is_ambassador","is_sponsor","is_organizer","is_player")
                player_data["user"] = list(user_image)
                player_data["user_uuid"] = user_image[0]["uuid"]
                player_data["player__is_ambassador"] = user_image[0]["is_ambassador"]
                player_data["user_secret_key"] = user_image[0]["secret_key"]
                if user_image[0]["image"] is not None or user_image[0]["image"] != "":
                    player_data["player_image"] = user_image[0]["image"]
                else:
                    player_data["player_image"] = None 
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


# class TeamSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Team
#         fields = '__all__'

# class PlayerSerializer(serializers.ModelSerializer):
#     player_picture = serializers.ImageField(source='player_image')  # Change field name
#     team = TeamSerializer(many=True)
#     class Meta:
#         model = Player
#         fields = '__all__'

# #done
# @api_view(('GET',))
# def list_player(request):
#     try:
#         data = {'status': '', 'data': [], 'message': ''}
#         user_uuid = request.GET.get('user_uuid')
#         user_secret_key = request.GET.get('user_secret_key')
#         search_text = request.GET.get('search_text')
        
#         check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
#         if check_user.exists():
#             get_user = check_user.first()
#             if get_user.is_admin or get_user.is_organizer:
#                 if not search_text:
#                     all_players = Player.objects.all().order_by('-id')
#                 else:
#                     all_players = Player.objects.filter(Q(player_first_name__icontains=search_text) | Q(player_last_name__icontains=search_text)).order_by('-id')
#             elif get_user.is_team_manager or get_user.is_coach:
#                 if not search_text:
#                     all_players = Player.objects.filter(created_by_id=get_user.id).order_by('-id')
#                 else:
#                     all_players = Player.objects.filter(created_by_id=get_user.id).filter(Q(player_first_name__icontains=search_text) | Q(player_last_name__icontains=search_text)).order_by('-id')

#             player_serializer = PlayerSerializer(all_players, many=True)  # Instantiate the PlayerSerializer with queryset
#             serialized_data = player_serializer.data  # Serialize the queryset data


#             for jk in serialized_data:
#                 if jk["player_image"] is not None:
#                     jk["player__image"] = jk["player_image"].replace('/media', '')
#                 else:
#                     jk["player__image"] = None

#                 if jk["player_image"] is not None:
#                     jk["player_image"] = jk["player_image"].replace('/media', '')
#                 else:
#                     jk["player_image"] = None

#                 if jk["created_by"] == get_user.id:
#                     jk["is_edit"] = True
#                 else:
#                     jk["is_edit"] = False
#                 del jk["player_picture"]
#                 # del["player_picture"]



#             data["status"] = status.HTTP_200_OK
#             data["data"] = serialized_data
#             data["message"] = "Data found"

#         else:
#             data['status'] = status.HTTP_401_UNAUTHORIZED
#             data['message'] = "Unauthorized access"

#     except Exception as e:
#         data['status'] = status.HTTP_400_BAD_REQUEST
#         data['message'] = str(e)

#     return Response(data)




@api_view(('POST',))
def create_team(request):
    try:
        data = {'status':'','message':''}
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
        # print(team_image)
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        if check_user.exists() :
            if not team_name or not team_person :
                data["status"], data["message"] = status.HTTP_403_FORBIDDEN , "Team Name and Team Type (2 person or 4 person) required"
                return Response(data)
            else:
                if team_person == "Two Person Team" :
                    # if not p1_first_name or not p1_last_name or not p1_email or not p1_phone_number or not p2_first_name or not p2_last_name or not p2_email or not p2_phone_number :
                    if not p1_uuid or not p1_secret_key or not p2_uuid or not p2_secret_key  :
                        data["status"], data["message"] = status.HTTP_403_FORBIDDEN , "Player1 and Player2's eamil and phone number required"
                        return Response(data)
                    else:
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
                        save_team = Team(secret_key=team_secret_key,name=team_name,location=team_location,team_person=team_person,team_type=team_type,team_image=team_image,created_by_id=created_by_id)
                        save_team.save()
                        p1 = Player.objects.filter(uuid=p1_uuid,secret_key=p1_secret_key).first()
                        p1.team.add(save_team.id)
                        p2 = Player.objects.filter(uuid=p2_uuid,secret_key=p2_secret_key).first()
                        p2.team.add(save_team.id)
                        save_user = check_user.first()
                        save_user.is_team_manager = True
                        save_user.save()
                        data["status"], data["message"] = status.HTTP_200_OK, "Team and Player created successfully"
                elif team_person == "One Person Team" :
                    if not p1_uuid or not p1_secret_key or not p2_uuid or not p2_secret_key :
                        data["status"], data["message"] = status.HTTP_403_FORBIDDEN , "Player's eamil and phone number required"
                        return Response(data)
                    else:
                        obj = GenerateKey()
                        team_secret_key = obj.gen_team_key()
                        player1_secret_key = obj.gen_player_key()
                        created_by_id = check_user.first().id
                        if team_image is not None:
                            team_image = team_image
                        else:
                            team_image = None
                        save_team = Team(secret_key=team_secret_key,name=team_name,location=team_location, team_person=team_person,team_type=team_type,team_image=team_image,created_by_id=created_by_id)
                        save_team.save()
                        p1 = Player.objects.filter(uuid=p1_uuid,secret_key=p1_secret_key).first()
                        p1.team.add(save_team.id)
                        save_user = check_user.first()
                        save_user.is_team_manager = True
                        save_user.save()
                        data["status"], data["message"] = status.HTTP_200_OK, "Team and Player created successfully"
                else:
                    pass
        else:
            data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "User not found"
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
        
    return Response(data)



@api_view(('GET',))
def team_list(request):
    try:
        data = {'status':'','message':''}
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        search_text = request.GET.get('search_text')

        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        if check_user.exists() :
            main_data = []
            if check_user.first().is_admin or check_user.first().is_organizer:
                if search_text is not None:
                    alldata = Team.objects.filter(Q(name__icontains=search_text)).order_by('-id').values('id','uuid','secret_key','name','location','created_by__first_name','created_by__last_name',
                                                                    'team_image','created_by__uuid','created_by__secret_key','team_type','team_person','created_by_id')
                else:
                    alldata = Team.objects.all().order_by('-id').values('id','uuid','secret_key','name','location','created_by__first_name','created_by__last_name',
                                                                    'team_image','created_by__uuid','created_by__secret_key','team_type','team_person','created_by_id')
                # print(alldata)
                # for k in alldata:
                    

                for i in alldata:
                    if i["created_by_id"] == check_user.first().id:
                        is_edit = True
                    else:
                        is_edit = False
                    get_player = Player.objects.filter(team__id=i['id']).values('uuid','secret_key','player_full_name','player_ranking')
                    main_data.append({'team_uuid':i['uuid'],'team_secret_key':i['secret_key'],'team_name':i['name'],'location':i['location'],'created_by':f"{i['created_by__first_name']} {i['created_by__last_name']}",
                                        'created_by_uuid':i['created_by__uuid'],'created_by_secret_key':i['created_by__secret_key'],'team_image':i['team_image'],'player_data':get_player,'team_type':i['team_type'],'team_person':i['team_person'],'is_edit':is_edit})

                data["status"], data["data"], data["message"] = status.HTTP_200_OK, main_data,"Data found for Admin"
            else:
                get_user = check_user.first()
                if search_text is None:
                    check_manager_data = Team.objects.filter(created_by_id=get_user.id).order_by('-id').values('id','uuid','secret_key','name','location','created_by__first_name','created_by__last_name',
                                                                    'team_image','created_by__uuid','created_by__secret_key','team_type','team_person')
                else:
                    check_manager_data = Team.objects.filter(created_by_id=get_user.id).filter(Q(name__icontains=search_text)).order_by('-id').values('id','uuid','secret_key','name','location','created_by__first_name','created_by__last_name',
                                                                    'team_image','created_by__uuid','created_by__secret_key','team_type','team_person')
                
                get_player = Player.objects.filter(player_email=get_user.email).values('team__id','player_full_name','player_ranking')
                get_player_team_id = [i['team__id'] for i in get_player]
                check_player_data = Team.objects.filter(id__in=get_player_team_id).order_by('-id').values('id','uuid','secret_key','name','location','created_by__first_name','created_by__last_name',
                                                                    'team_image','created_by__uuid','created_by__secret_key','team_type','team_person')
                
                
                
                if check_manager_data.exists():
                    for i in check_manager_data :
                        get_player = Player.objects.filter(team__id=i['id']).values('uuid','secret_key','player_full_name','player_ranking')
                        main_data.append({'team_uuid':i['uuid'],'team_secret_key':i['secret_key'],'team_name':i['name'],'location':i['location'],'created_by':f"{i['created_by__first_name']} {i['created_by__last_name']}",
                                            'created_by_uuid':i['created_by__uuid'],'created_by_secret_key':i['created_by__secret_key'],'team_image':i['team_image'], 'is_manager':True,'player_data':get_player,'team_type':i['team_type'],'team_person':i['team_person']})
                
                if check_player_data.exists():
                    for i in check_player_data :
                        get_player = Player.objects.filter(team__id=i['id']).values('uuid','secret_key','player_full_name','player_ranking')
                        main_data.append({'team_uuid':i['uuid'],'team_secret_key':i['secret_key'],'team_name':i['name'],'location':i['location'],'created_by':f"{i['created_by__first_name']} {i['created_by__last_name']}",
                                            'created_by_uuid':i['created_by__uuid'],'created_by_secret_key':i['created_by__secret_key'],'team_image':i['team_image'], 'is_manager':False,'player_data':get_player, 'team_type':i['team_type'],'team_person':i['team_person'],'is_edit':True})
                data["status"], data["data"], data["message"] = status.HTTP_200_OK, main_data,"Data found"
        else:
            data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "User not found"  
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)



@api_view(('GET',))
def team_view(request):
    try:
        data = {'status':'','message':''}
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
                                                    "player__first_name","player__last_name","player__image")

                data["status"], data["data"], data["message"] = status.HTTP_200_OK, {"team_data":main_data,"player_data":player_data},"Data found"
            else:
                data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "Team not found"
        else:
            data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "User not found"  
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)



@api_view(('POST',))
def edit_team(request):
    try:
        data = {'status':'', 'message':''}
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

        full_image_path = f"team_image/{team_image}" if team_image else None

        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if check_user.exists(): 
            if not team_name or not team_person:
                data["status"], data["message"] = status.HTTP_403_FORBIDDEN , "Team Name and Team Type (2 person or 4 person) required"
                return Response(data)

            if team_person == "Two Person Team":
                if not p1_uuid or not p1_secret_key or not p2_uuid or not p2_secret_key:
                    data["status"], data["message"] = status.HTTP_403_FORBIDDEN , "Player1 and Player2's email and phone number required"
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
                        
                        
                        team_instance.team_image = team_image
                            
                        team_instance.save()
                        
                        pre_player_list = Player.objects.filter(team__id=team_instance.id)
                        pre_player1 = pre_player_list.first()
                        pre_player2 = pre_player_list.last()
                        player1_change_count = 0
                        player2_change_count = 0
                        
                        if check_player1 != pre_player1 or check_player1 != pre_player2:
                            player1_change_count += 1
                        if check_player2 != pre_player1 or check_player2 != pre_player2:
                            player2_change_count += 1
                            
                        if player1_change_count != 0 and player2_change_count != 0:
                            if team_instance.id != None:
                                pre_player1.team.remove(team_instance.id)
                                pre_player2.team.remove(team_instance.id)
                            check_player2.first().team.add(team_instance.id)
                            check_player1.first().team.add(team_instance.id)
                        if player1_change_count != 0 and player2_change_count == 0:
                            if team_instance.id != None:
                                pre_player1.team.remove(team_instance.id)
                            check_player2.first().team.add(team_instance.id)
                        if player1_change_count == 0 and player2_change_count != 0:
                            if team_instance.id != None:
                                pre_player1.team.remove(team_instance.id)
                            check_player2.first().team.add(team_instance.id)
                        
                        data["status"], data["message"] = status.HTTP_200_OK, "Team edited successfully"
                    else:
                        data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "Team not found"
                    return Response(data)
                
            if team_person == "One Person Team":
                if not p1_uuid or not p1_secret_key:
                    data["status"], data["message"] = status.HTTP_403_FORBIDDEN , "Player's email and phone number required"
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
                        
                        team_instance.team_image = team_image
                        team_instance.save()
                        
                        remove_player_team = Player.objects.filter(team__id=team_instance.id).first()

                        if remove_player_team is not None:
                            remove_player_team.team.remove(team_instance.id)
                        check_player.first().team.add(team_instance.id)
                        
                        data["status"], data["message"] = status.HTTP_200_OK, "Team edited successfully"
                    else:
                        data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "Team not found"
                    return Response(data)
            else:
                data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "Something is wrong"
        else:
            data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "User not found"
    except Exception as e:
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
        
    return Response(data)






@api_view(('POST',))
def delete_team(request):
    try:
        data = {'status':'','message':''}
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
                    team_league.first().delete()
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
                            'sdppppppppppp@gmail.com',
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
                            'sdppppppppppp@gmail.com',
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



import json
#changes start
@api_view(('POST',))
def create_leagues(request):
    try:
        data = {'status':'','data':[],'message':''}
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
        street = request.data.get('street')
        city = request.data.get('city')
        state = request.data.get('state')
        postal_code = request.data.get('postal_code')
        country = request.data.get('country')
        max_number_team = request.data.get('max_number_team')
        registration_fee = request.data.get('registration_fee')
        description = request.data.get('description')
        image = request.FILES.get('image')
        team_type = json.loads(team_type)
        team_person = json.loads(team_person)
        
        
        if int(max_number_team) % 2 != 0 or int(max_number_team) == 0 or int(max_number_team) == 1:
            data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "Max number of team is must be even"
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
                obj = GenerateKey()
                secret_key = obj.gen_leagues_key()
                save_leagues = Leagues(secret_key=secret_key,name=name,leagues_start_date=leagues_start_date,leagues_end_date=leagues_end_date,location=location,
                                    registration_start_date=registration_start_date,registration_end_date=registration_end_date,created_by_id=check_user.first().id,
                                    street=street,city=city,state=state,postal_code=postal_code,country=country,max_number_team=max_number_team, play_type=play_type,
                                    registration_fee=registration_fee,description=description,image=image)
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
                    set_msg = f"{message} tournament is already exists"
                elif len(mesage_box) > 1:
                    set_msg = f"{message} tournaments are already exists"
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
    try:
        data = {'status':'','data':[],'message':''}
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
            data["status"],data["data"], data["message"] = status.HTTP_200_OK,my_result,"User not found."
        else:
            data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "User not found."
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


# @api_view(('POST',))
# def set_tournamens_result(request):
#     try:
#         data = {'status': '', 'data': [], 'message': ''}
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

#             to_sets_result = TournamentSetsResult.objects.filter(tournament=tournament_obj, set_number=set_number)
            

#             if int(team1_point) > int(team2_point):
#                 win_team = tournament_obj.team1   
#             else:
#                 win_team = tournament_obj.team2
#             if check_user.first().is_organizer and check_user.first() == league.created_by:
#                 if to_sets_result.exists():
#                     to_sets_result.update(team1_point=team1_point, team2_point=team2_point, win_team=win_team, is_completed=True)
#                     data["status"], data["message"] = status.HTTP_200_OK, "This set's score is updated"
#                 else:
#                     TournamentSetsResult.objects.create(tournament=tournament_obj, set_number=set_number, team1_point=team1_point, team2_point=team2_point, win_team=win_team, is_completed=True)
#                     data["status"], data["message"] = status.HTTP_200_OK, "This set's score is added"
#                 if int(set_number) == 2:
#                     try:
#                         previous_set1 = TournamentSetsResult.objects.get(tournament=tournament_obj, set_number=1, is_completed=True)
#                         previous_set2 = TournamentSetsResult.objects.get(tournament=tournament_obj, set_number=2, is_completed=True)
#                         # print(previous_set1.win_team , previous_set2.win_team)
#                         if previous_set1.win_team == previous_set2.win_team:
#                             if previous_set1.win_team == tournament_obj.team1:
#                                 winner_team,loser_team = tournament_obj.team1,tournament_obj.team2
#                             else:
#                                 winner_team,loser_team = tournament_obj.team2,tournament_obj.team1
#                             Tournament.objects.filter(pk=tournament_obj.pk).update(winner_team=winner_team,loser_team=loser_team,winner_team_score=3,loser_team_score=0,is_completed=True)
#                         else:
#                             pass
#                     except:
#                         pass
#                 elif int(set_number) == 3:
#                     try:
#                         previous_set1 = TournamentSetsResult.objects.get(tournament=tournament_obj, set_number=1, is_completed=True)
#                         previous_set2 = TournamentSetsResult.objects.get(tournament=tournament_obj, set_number=2, is_completed=True)
#                         previous_set3 = TournamentSetsResult.objects.get(tournament=tournament_obj, set_number=3, is_completed=True)
#                         if previous_set2.win_team == previous_set3.win_team:
#                             if previous_set2.win_team == tournament_obj.team1:
#                                 winner_team,loser_team = tournament_obj.team1,tournament_obj.team2
#                             else:
#                                 winner_team,loser_team = tournament_obj.team2,tournament_obj.team1
#                             Tournament.objects.filter(pk=tournament_obj.pk).update(winner_team=winner_team,loser_team=loser_team,winner_team_score=3,loser_team_score=0,is_completed=True)
#                         else:
#                             if previous_set1.win_team == tournament_obj.team1:
#                                 winner_team,loser_team = tournament_obj.team1,tournament_obj.team2
#                             else:
#                                 winner_team,loser_team = tournament_obj.team2,tournament_obj.team1
#                         Tournament.objects.filter(pk=tournament_obj.pk).update(winner_team=winner_team,loser_team=loser_team,winner_team_score=3,loser_team_score=0,is_completed=True)        
#                     except:
#                         pass
#             elif check_user.first() == tournament_obj.team1.created_by or check_user.first() == tournament_obj.team2.created_by:
#                 if to_sets_result.exists():
#                     to_sets_result.update(team1_point=team1_point, team2_point=team2_point, win_team=win_team)
#                     data["status"], data["message"] = status.HTTP_200_OK, "Your set's score is updated and sent to Organizer for approval"
#                 else:
#                     TournamentSetsResult.objects.create(tournament=tournament_obj, set_number=set_number, team1_point=team1_point, team2_point=team2_point, win_team=win_team)
#                     data["status"], data["message"] = status.HTTP_200_OK, "Your set's score is added and sent to Organizer for approval"
#             else:
#                 data["status"], data["message"] = status.HTTP_403_FORBIDDEN, "You are not allowed to set this score"
#         else:
#             data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "User or Tournament not found."
#     except Exception as e:
#         data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, str(e)
#     return Response(data)


@api_view(('POST',))
def set_tournamens_result(request):
    try:
        data = {'status': '', 'data': [], 'message': ''}
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

            my_data = []
            for i in range(3):
                try:
                    team1_point = int(team1_point_list[i])
                except:
                    team1_point = None
                try:
                    team2_point = int(team2_point_list[i])
                except:
                    team2_point = None
                set_obj = {"set": i+1, "team1_point": team1_point, "team2_point": team2_point, "winner": None}
                my_data.append(set_obj)

            team1_wins = 0
            team2_wins = 0
            for match in my_data:
                team1_point = match['team1_point']
                team2_point = match['team2_point']
                if team1_point is not None and team2_point is not None:
                    if team1_point > team2_point:
                        team1_wins += 1
                        match["winner"] = "team1"
                    elif team2_point > team1_point:
                        team2_wins += 1
                        match["winner"] = "team2"
                else:
                    match["winner"] = None

            winner_team = None
            losser_team = None
            if team1_wins > team2_wins:
                winner_team = tournament_obj.team1
                losser_team = tournament_obj.team2
            elif team2_wins > team1_wins:
                winner_team = tournament_obj.team2
                losser_team = tournament_obj.team1
            # if get_user.is_organizer == get_user:
            #     is_organizer = True
            # else:
            #     is_organizer = False

            if (tournament_obj.team1.created_by == get_user and not get_user.is_organizer) or (tournament_obj.team2.created_by == get_user and not get_user.is_organizer):
                for up_score in my_data:
                    if up_score["team1_point"] is not None or up_score["team2_point"] is not None:
                        check_score = TournamentSetsResult.objects.filter(tournament=tournament_obj, set_number=up_score["set"])
                        if up_score["winner"] == "team1":
                            set_win_team = tournament_obj.team1
                        elif up_score["winner"] == "team2":
                            set_win_team = tournament_obj.team2
                        else:
                            set_win_team = None
                        if check_score.exists():
                            check_score.update(team1_point=up_score["team1_point"], team2_point=up_score["team2_point"], win_team=set_win_team)
                        else:
                            TournamentSetsResult.objects.create(tournament=tournament_obj, set_number=up_score["set"], team1_point=up_score["team1_point"], team2_point=up_score["team2_point"], win_team=set_win_team)
                data["status"], data["message"] = status.HTTP_200_OK, "Your set's score is Updated and sent to Organizer for approval" 
            elif (get_user.is_organizer and league.created_by == get_user) or (tournament_obj.team1.created_by == get_user and get_user.is_organizer) or (tournament_obj.team2.created_by == get_user and get_user.is_organizer):
                for up_score in my_data:
                    if up_score["team1_point"] is not None or up_score["team2_point"] is not None:
                        check_score = TournamentSetsResult.objects.filter(tournament=tournament_obj, set_number=up_score["set"])
                        if up_score["winner"] == "team1":
                            set_win_team = tournament_obj.team1
                        elif up_score["winner"] == "team2":
                            set_win_team = tournament_obj.team2
                        else:
                            set_win_team = None
                        if check_score.exists():
                            check_score.update(team1_point=up_score["team1_point"], team2_point=up_score["team2_point"], win_team=set_win_team,is_completed=True)
                        else:
                            TournamentSetsResult.objects.create(tournament=tournament_obj, set_number=up_score["set"], team1_point=up_score["team1_point"], team2_point=up_score["team2_point"], win_team=set_win_team, is_completed=True)
                tournament_obj.winner_team = winner_team
                tournament_obj.loser_team = losser_team
                tournament_obj.winner_team_score = 3
                tournament_obj.loser_team_score = 0
                tournament_obj.is_completed = True
                tournament_obj.save()
                data["status"], data["message"] = status.HTTP_200_OK, "Your set's score is Updated" 
            else:
                data["status"], data["message"] = status.HTTP_403_FORBIDDEN, "You are not allowed to set this score"
        else:
            data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "User or Tournament not found."
    except Exception as e:
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, str(e)
    return Response(data)



@api_view(('GET',))
def view_match_result(request):
    try:
        data = {'status': '', 'data': [], 'message': '','set':''}
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



# autometic match assigne
def create_group(lst, num_parts):
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




# @api_view(('POST',))
# def assigne_match(request):
#     data = {'status': '', 'message': ''}
#     user_uuid = request.data.get('user_uuid')
#     user_secret_key = request.data.get('user_secret_key')
#     league_uuid = request.data.get('league_uuid')
#     league_secret_key = request.data.get('league_secret_key')
    
#     check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
#     check_leagues = Leagues.objects.filter(uuid=league_uuid, secret_key=league_secret_key)
    
#     if check_user.exists() and check_leagues.exists():
#         league = check_leagues.first()
#         playtype = league.play_type     
#         if playtype == "Single Elimination":
#             check_pre_game =  Tournament.objects.filter(leagues=league)
#             if check_pre_game.exists():
#                 check_leagues_com = check_pre_game.filter(is_completed=True)
#                 if len(check_pre_game) == len(check_leagues_com) and len(check_leagues_com) != 0:
#                     pre_match_round = check_leagues_com.last().elimination_round
#                     pre_round_details =  Tournament.objects.filter(leagues=league,elimination_round=pre_match_round)
#                     teams = list(pre_round_details.values_list("winner_team_id", flat=True))
#                     pre_match_number = check_leagues_com.last().match_number
#                     define_court = LeaguesPlayType.objects.filter(league_for=league).data[1]["number_of_courts"]
#                     court_num = 0
#                     if len(teams) == 4:
#                         match_type = "Semi Final"
#                         round_number = 0
#                         random.shuffle(teams)
#                         match_number_now = pre_match_number
                        
#                         for i in range(0, len(teams), 2):
#                             team1 = teams[i]
#                             team2 = teams[i + 1]
#                             obj = GenerateKey()
#                             secret_key = obj.generate_league_unique_id()
#                             match_number_now = match_number_now + 1
#                             court_num = court_num + 1
#                             Tournament.objects.create(court_sn=court_num,match_number=match_number_now, secret_key=secret_key, leagues=league, team1_id=team1, team2_id=team2, match_type=match_type, elimination_round=round_number)
#                         data["status"], data["message"] = status.HTTP_200_OK, f"create matches for {match_type} , {round_number}"
#                         return Response(data)   
#                     elif len(teams) == 2:
#                         match_type = "Final"
#                         round_number = pre_match_number
#                         random.shuffle(teams)
#                         match_number_now = 0
#                         for i in range(0, len(teams), 2):
#                             team1 = teams[i]
#                             team2 = teams[i + 1]
#                             obj = GenerateKey()
#                             secret_key = obj.generate_league_unique_id()
#                             match_number_now = match_number_now + 1
#                             court_num = court_num + 1
#                             Tournament.objects.create(court_sn=court_num,match_number=match_number_now, secret_key=secret_key, leagues=league, team1_id=team1, team2_id=team2, match_type=match_type, elimination_round=round_number)
#                         data["status"], data["message"] = status.HTTP_200_OK, f"create matches for {match_type} , {round_number}"
#                         return Response(data)
#                     else:
#                         match_type = "Elimination Round"
#                         round_number = pre_match_round + 1
#                         random.shuffle(teams)
#                         match_number_now = pre_match_number
#                         for i in range(0, len(teams), 2):
#                             team1 = teams[i]
#                             team2 = teams[i + 1]
#                             obj = GenerateKey()
#                             secret_key = obj.generate_league_unique_id()
#                             match_number_now = match_number_now + 1
#                             court_num = court_num + 1
#                             Tournament.objects.create(court_sn=court_num,match_number=match_number_now, secret_key=secret_key, leagues=league, team1_id=team1, team2_id=team2, match_type=match_type, elimination_round=round_number)
#                         data["status"], data["message"] = status.HTTP_200_OK, f"create matches for {match_type} , {round_number}"
#                         return Response(data)
#                 else:
#                     data["status"], data["message"] = status.HTTP_200_OK, "Previous Round is not completed or not updated"
#                     return Response(data)
#             else:
#                 teams = []
#                 court_num = 0
#                 for grp in check_leagues:
#                     teams__ = grp.registered_team.all()
#                     for te in teams__:
#                         teams.append(te.id)
#                 if len(teams) == 4:
#                     match_type = "Semi Final"
#                     random.shuffle(teams)
#                     match_number_now = 0
#                     for i in range(0, len(teams), 2):
#                         team1 = teams[i]
#                         team2 = teams[i + 1]
#                         obj = GenerateKey()
#                         secret_key = obj.generate_league_unique_id()
#                         match_number_now = match_number_now + 1
#                         court_num = court_num + 1
#                         Tournament.objects.create(court_sn=court_num,match_number=match_number_now, secret_key=secret_key, leagues=league, team1_id=team1, team2_id=team2, match_type=match_type, elimination_round=0)
#                     data["status"], data["message"] = status.HTTP_200_OK, f"create matches for {match_type}"
#                     return Response(data)
#                 if len(teams) == 2:
#                     match_type = "Final"
#                     random.shuffle(teams)
#                     match_number_now = 0
#                     for i in range(0, len(teams), 2):
#                         team1 = teams[i]
#                         team2 = teams[i + 1]
#                         obj = GenerateKey()
#                         secret_key = obj.generate_league_unique_id()
#                         match_number_now = match_number_now + 1
#                         court_num = court_num + 1
#                         Tournament.objects.create(court_sn=court_num,match_number=match_number_now, secret_key=secret_key, leagues=league, team1_id=team1, team2_id=team2, match_type=match_type, elimination_round=0)
#                     data["status"], data["message"] = status.HTTP_200_OK, f"create matches for {match_type}"
#                     return Response(data)
#                 else:
#                     match_type = "Elimination Round"
#                     random.shuffle(teams)
#                     match_number_now = 0
#                     for i in range(0, len(teams), 2):
#                         team1 = teams[i]
#                         team2 = teams[i + 1]
#                         obj = GenerateKey()
#                         secret_key = obj.generate_league_unique_id()
#                         match_number_now = match_number_now + 1
#                         court_num = court_num + 1
#                         Tournament.objects.create(court_sn=court_num,match_number=match_number_now, secret_key=secret_key, leagues=league, team1_id=team1, team2_id=team2, match_type=match_type, elimination_round=1)
#         elif playtype == "Group Stage":
#             check_pre_game =  Tournament.objects.filter(leagues=league)
#             if check_pre_game.exists():
#                 all_round_robin_match = Tournament.objects.filter(leagues=league)
#                 all_completed_round_robin_match = Tournament.objects.filter(leagues=league, is_completed=True)
#                 if all_round_robin_match.exists() and all_completed_round_robin_match.exists() and all_round_robin_match.count() == all_completed_round_robin_match.count():
#                     check_pre_game =  Tournament.objects.filter(leagues=league)
#                     last_match_type = check_pre_game.last().match_type
#                     last_round = check_pre_game.last().elimination_round
#                     last_match_number = check_pre_game.last().match_number
#                     if last_match_type == "Round Robin":
#                         # part set result for Round Robin # data add
#                         all_group_details = RoundRobinGroup.objects.filter(league_for=league)
#                         for grp in all_group_details:
#                             teams = grp.all_teams.all()
#                             group_score_point_table = []
#                             for team in teams:
#                                 team_score = {}
#                                 total_match_detals = Tournament.objects.filter(leagues=league).filter(Q(team1=team) | Q(team2=team))
#                                 completed_match_details = total_match_detals.filter(is_completed=True)
#                                 win_match_details = completed_match_details.filter(winner_team=team).count()
#                                 loss_match_details = completed_match_details.filter(loser_team=team).count()
#                                 drow_match = len(completed_match_details) - (win_match_details + loss_match_details)
#                                 point = (win_match_details * 3) + (drow_match * 1)
#                                 team_score["uuid"], team_score["secret_key"] = team.uuid, team.secret_key
#                                 team_score["completed_match"] = len(completed_match_details)
#                                 team_score["win_match"], team_score["loss_match"] = win_match_details, loss_match_details
#                                 team_score["drow_match"], team_score["for_score"] = drow_match, drow_match
#                                 team_score["aginst_score"], team_score["point"] = drow_match, point
#                                 group_score_point_table.append(team_score)
#                             grp_team = sorted(group_score_point_table, key=lambda x: x['point'], reverse=True)
#                             select_team_instance = Team.objects.filter(uuid=grp_team[0]["uuid"],secret_key=grp_team[0]["secret_key"])
#                             RoundRobinGroup.objects.filter(id=grp.id).update(seleced_teams=select_team_instance.first())
#                         match_type = "Elimination Round"
#                         round_number = 1
#                         teams = list(RoundRobinGroup.objects.filter(league_for=league).values_list("seleced_teams_id", flat=True))
#                         if len(teams) != len(RoundRobinGroup.objects.filter(league_for=league)):
#                             data["status"],  data["message"] = status.HTTP_200_OK, f"Not selected all  winner"
#                             return Response(data)
#                         # print(teams)
#                         if len(teams) == 2:
#                             match_type = "Final"
#                             round_number = 0
#                         elif len(teams) == 4:
#                             match_type = "Semi Final"
#                             round_number = 0
#                         random.shuffle(teams)
#                         match_number_now = last_match_number
#                         court_num = 0
#                         for i in range(0, len(teams), 2):
#                             team1 = teams[i]
#                             team2 = teams[i + 1]
#                             obj = GenerateKey()
#                             secret_key = obj.generate_league_unique_id()
#                             match_number_now = match_number_now + 1
#                             court_num += 1
#                             Tournament.objects.create(court_sn=court_num,match_number=match_number_now,secret_key=secret_key, leagues=league,team1_id=team1, team2_id=team2,match_type=match_type,elimination_round=round_number)
#                         data["status"], data["message"] = status.HTTP_200_OK, f"Matches are created for {match_type} {round_number}"
#                         return Response(data)
#                     elif last_match_type == "Elimination Round":
                        
#                         match_type = "Elimination Round"
#                         round_number = last_round + 1
#                         # win_teams
#                         teams = list(Tournament.objects.filter(leagues=league, elimination_round=last_round).values_list("winner_team_id", flat=True))
#                         if len(teams) != len(Tournament.objects.filter(leagues=league, elimination_round=last_round)):
#                             data["status"],  data["message"] = status.HTTP_200_OK, f"Not selected all winner"
#                             return Response(data)
#                         elif len(teams) == 2:
#                             match_type = "Final"
#                             round_number = 0
#                         elif len(teams) == 4:
#                             match_type = "Semi Final"
#                             round_number = 0
#                         random.shuffle(teams)
#                         match_number_now = last_match_number
#                         court_num = 0
#                         for i in range(0, len(teams), 2):
#                             team1 = teams[i]
#                             team2 = teams[i + 1]
#                             obj = GenerateKey()
#                             secret_key = obj.generate_league_unique_id()
#                             match_number_now = match_number_now + 1
#                             court_num += 1
#                             Tournament.objects.create(court_sn=court_num,match_number=match_number_now,secret_key=secret_key, leagues=league,team1_id=team1, team2_id=team2,match_type=match_type,elimination_round=round_number)
#                         data["status"], data["message"] = status.HTTP_200_OK, f"Matches are created for {match_type} {round_number}"
#                         return Response(data)
#                     elif last_match_type == "Semi Final":
#                         match_type = "Final"
#                         round_number = 0
#                         # print()
#                         winning_teams = list(Tournament.objects.filter(leagues=league, match_type="Semi Final").values_list('winner_team_id', flat=True))
                        
#                         #Tournament.objects.filter(leagues=league, match_type="Semi Final") #backup
#                         if len(winning_teams) != 2:
#                             data["status"],  data["message"] = status.HTTP_200_OK, f"Not selected all winner"
#                             return Response(data)
#                         random.shuffle(winning_teams)
#                         match_number_now = last_match_number
#                         court_num = 0
#                         for i in range(0, len(winning_teams), 2):
#                             team1 = winning_teams[i]
#                             team2 = winning_teams[i + 1]
#                             obj = GenerateKey()
#                             secret_key = obj.generate_league_unique_id()
#                             match_number_now = match_number_now + 1
#                             court_num += 1
#                             Tournament.objects.create(court_sn=court_num,match_number=match_number_now,secret_key=secret_key, leagues=league,team1_id=team1, team2_id=team2,match_type=match_type,elimination_round=round_number)
#                         data["status"], data["message"] = status.HTTP_200_OK, f"Matches are created for {match_type} ."
#                         return Response(data)
#                     elif last_match_type == "Final":
#                         data["status"],  data["message"] = status.HTTP_200_OK, f"The tournament results are out! The tournament has concluded successfully."
#                         return Response(data)
#                 else:
#                     data["status"],  data["message"] = status.HTTP_200_OK, f"All matches in this round are not completed yet."
#                     return Response(data)
#             else:
#                 #create Robin Round
#                 registered_teams = league.registered_team.all() if league else None
#                 team_details_list = [team.id for team in registered_teams] if registered_teams else []
                
#                 play_details = LeaguesPlayType.objects.filter(league_for=league).first()
#                 number_of_group = play_details.data[0]["number_of_courts"] if play_details else 0
                
#                 group_list = create_group(team_details_list, number_of_group)
                
#                 round_robin_group_details = RoundRobinGroup.objects.filter(league_for=league)
#                 if round_robin_group_details.exists():
#                     if len(round_robin_group_details) == number_of_group:
#                         data["status"],  data["message"] = status.HTTP_200_OK, f"Round robin group already created for {league.name}"
#                         return Response(data)
#                     else:
#                         for gr in round_robin_group_details:
#                             Tournament.objects.filter(group_id=gr.id).delete
#                             gr.delete()
#                 set_number = LeaguesPlayType.objects.filter(league_for=league)
#                 if not set_number.exists():
#                     data["status"],  data["message"] = status.HTTP_200_OK, team_details_list, "Group Created Successfully"
#                     return Response(data)
#                 set_number = set_number.first().data[0]["sets"]
#                 serial_number = 0
#                 print(group_list)
#                 for index, group_teams in enumerate(group_list, start=1):
#                     group = RoundRobinGroup.objects.create(court=index, league_for=league, number_sets=set_number)
#                     for team_id in group_teams:
#                         team = Team.objects.get(id=team_id)
#                         group.all_teams.add(team)
                    
#                     match_combinations = list(combinations(group_teams, 2))
#                     for teams in match_combinations:
#                         obj = GenerateKey()
#                         secret_key = obj.generate_league_unique_id()
#                         team1, team2 = teams
#                         serial_number = serial_number+1
#                         Tournament.objects.create(match_number=serial_number,secret_key=secret_key, leagues=league, team1_id=team1, team2_id=team2, group_id=group.id,match_type="Round Robin")
#                 data["status"], data["message"] = status.HTTP_200_OK, f"Matches are created for Round Robin"
#                 return Response(data)
#         elif playtype == "Round Robin":
#             registered_teams = league.registered_team.all() if league else None
#             team_details_list = [team.id for team in registered_teams] if registered_teams else []
            
#             play_details = LeaguesPlayType.objects.filter(league_for=league).first()
#             number_of_group = 1
            
#             group_list = create_group(team_details_list, number_of_group)
#             round_robin_group_details = RoundRobinGroup.objects.filter(league_for=league)
#             if round_robin_group_details.exists():
#                 if len(round_robin_group_details) == number_of_group:
#                     data["status"],  data["message"] = status.HTTP_200_OK, f"Round robin group already created for {league.name}"
#                     return Response(data)
#                 else:
#                     for gr in round_robin_group_details:
#                         Tournament.objects.filter(group_id=gr.id).delete
#                         gr.delete()
#             set_number = LeaguesPlayType.objects.filter(league_for=league)
#             if not set_number.exists():
#                 data["status"],  data["message"] = status.HTTP_200_OK, team_details_list, "Group Created Successfully"
#                 return Response(data)
#             set_number = set_number.first().data[0]["sets"]
#             serial_number = 0
#             for index, group_teams in enumerate(group_list, start=1):
#                 group = RoundRobinGroup.objects.create(court=index, league_for=league, number_sets=set_number)
#                 for team_id in group_teams:
#                     team = Team.objects.get(id=team_id)
#                     group.all_teams.add(team)
                
#                 match_combinations = list(combinations(group_teams, 2))
#                 for teams in match_combinations:
#                     obj = GenerateKey()
#                     secret_key = obj.generate_league_unique_id()
#                     team1, team2 = teams
#                     serial_number = serial_number+1
#                     Tournament.objects.create(match_number=serial_number,secret_key=secret_key, leagues=league, team1_id=team1, team2_id=team2, group_id=group.id,match_type="Round Robin")
#                 data["status"], data["message"] = status.HTTP_200_OK, f"create matches for {match_type} group"
#                 return Response(data)
#         elif playtype == "Individual Match Play":
#             team____ = league.registered_team.all()
#             teams = []
#             for te in team____:
#                 teams.append(te.id)
#             if len(teams) != 2:
#                 data["status"], data["message"] = status.HTTP_200_OK, "Team must be two For Individual Match Play"
#                 return Response(data) 
#             match_type = "Individual Match Play"
#             round_number = 0
#             random.shuffle(teams)
#             match_number_now = pre_match_number
#             court_num = 0
#             for i in range(0, len(teams), 2):
#                 team1 = teams[i]
#                 team2 = teams[i + 1]
#                 obj = GenerateKey()
#                 secret_key = obj.generate_league_unique_id()
#                 match_number_now = match_number_now + 1
#                 court_num = court_num + 1
#                 Tournament.objects.create(court_sn=court_num,match_number=match_number_now,secret_key=secret_key, leagues=league,team1_id=team1, team2_id=team2,match_type=match_type,elimination_round=round_number) 
#             data["status"], data["message"] = status.HTTP_200_OK, f"create matches for {match_type}"
#             return Response(data)
#     else:
#         data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "User or League not found."
#     return Response(data)



# @api_view(('GET',))
# def view_leagues(request):
#     try:
#         data = {
#              'status':'',
#              'create_group_status':False,
#              'is_organizer': False,
#              'winner_team': 'Not Declared',
#              'data':[],
#              'tournament_detais':[],
#              'point_table':[],
#              'elemination':[], 
#              'final':[], 
#              'message':''
#              }
#         user_uuid = request.GET.get('user_uuid')
#         user_secret_key = request.GET.get('user_secret_key')
#         league_uuid = request.GET.get('league_uuid')
#         league_secret_key = request.GET.get('league_secret_key')
#         #protocol = 'https' if request.is_secure() else 'http'
#         host = request.get_host()
#         # Construct the complete URL for media files
#         media_base_url = f"{protocol}://{host}{settings.MEDIA_URL}"
#         '''
#         registration_open, future, past
#         '''
#         check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
#         check_leagues = Leagues.objects.filter(uuid=league_uuid,secret_key=league_secret_key)
#         if check_user.exists() and check_leagues.exists():
#             leagues = check_leagues.values('uuid','secret_key','name','location','leagues_start_date','leagues_end_date',
#                                'registration_start_date','registration_end_date','team_type__name','team_person__name',
#                                "street","city","state","postal_code","country","complete_address","latitude","longitude","play_type","registration_fee","description","image")
#             league = check_leagues.first()
#             get_user = check_user.first()
#             if get_user.is_organizer:
#                 data['is_organizer'] =  True

#             #this data for Elimination Round   
#             knock_out_tournament_elimination_data = Tournament.objects.filter(leagues=check_leagues.first(),match_type="Elimination Round").values("id","uuid","secret_key","match_number","match_type","elimination_round","team1__name", "team1_id", "team2_id"
#                                                                                                             ,"team1__team_image","team2__name","team2__team_image","winner_team__name", "winner_team_id", "loser_team_id", "winner_team__team_image","loser_team__name","loser_team__team_image","is_completed","play_ground_name")
#             for ele_tour in knock_out_tournament_elimination_data:
#                 ele_tour["is_edit"] = get_user.is_organizer and check_leagues.first().created_by == get_user or ele_tour["team1_id"] == get_user.id or ele_tour["team2_id"] == get_user.id
                
#                 score = [{"name": "","set": [],"score": [],"win_status": [],"is_win": True,"is_completed": True},{"name": "","set": [],"score": [],"win_status": [],"is_win": True,"is_completed": True}]
                
#                 if ele_tour["team1_id"] == ele_tour["winner_team_id"] and ele_tour["winner_team_id"] is not None:
#                     score[0]["is_win"] = True
#                     score[1]["is_win"] = False
#                 elif ele_tour["team2_id"] == ele_tour["winner_team_id"] and ele_tour["winner_team_id"] is not None:
#                     score[1]["is_win"] = True
#                     score[0]["is_win"] = False
#                 else:
#                     score[1]["is_win"] = None
#                     score[0]["is_win"] = None
#                 score_details = TournamentSetsResult.objects.filter(tournament_id=ele_tour["id"]).values()
#                 score[0]["name"] = ele_tour["team1__name"]
#                 score[1]["name"] = ele_tour["team2__name"]
#                 score[0]["set"] = ["s1","s2","s3"]
#                 score[1]["set"] = ["s1","s2","s3"]
#                 for l__ in range(3):
                    
#                     if l__ < len(score_details):
#                         l = {"team1_point":score_details[l__]["team1_point"],"team2_point":score_details[l__]["team2_point"]}
#                     else:
#                         l = {"team1_point":None,"team2_point":None}
                    
#                     score[0]["score"].append(l["team1_point"])
#                     score[1]["score"].append(l["team2_point"])
                    
#                     if l["team1_point"] == None or l["team1_point"] == None:
#                         score[0]["win_status"].append(None)
#                         score[1]["win_status"].append(None)
#                     elif l["team1_point"] > l["team2_point"]:
#                         score[0]["win_status"].append(True)
#                         score[1]["win_status"].append(False)
#                     else:
#                         score[0]["win_status"].append(False)
#                         score[1]["win_status"].append(True)
#                 ele_tour["score"] = score
#             data['elemination'] = list(knock_out_tournament_elimination_data)

#             #this data for Semi Final   
#             knock_out_semifinal_tournament_data = Tournament.objects.filter(leagues=check_leagues.first(),match_type="Semi Final").values("id","uuid","secret_key","match_number","match_type","elimination_round","team1__name", "team1_id", "team2_id"
#                                                                                                             ,"team1__team_image","team2__name","team2__team_image","winner_team__name", "winner_team_id", "loser_team_id", "winner_team__team_image","loser_team__name","loser_team__team_image","is_completed","play_ground_name")
#             for semi_tour in knock_out_semifinal_tournament_data:
#                 semi_tour["is_edit"] = get_user.is_organizer and check_leagues.first().created_by == get_user or semi_tour["team1_id"] == get_user.id or semi_tour["team2_id"] == get_user.id
                
#                 score = [{"name": "","set": [],"score": [],"win_status": [],"is_win": True,"is_completed": True},{"name": "","set": [],"score": [],"win_status": [],"is_win": True,"is_completed": True}]
                
#                 if semi_tour["team1_id"] == semi_tour["winner_team_id"] and semi_tour["winner_team_id"] is not None:
#                     score[0]["is_win"] = True
#                     score[1]["is_win"] = False
#                 elif semi_tour["team2_id"] == semi_tour["winner_team_id"] and semi_tour["winner_team_id"] is not None:
#                     score[1]["is_win"] = True
#                     score[0]["is_win"] = False
#                 else:
#                     score[1]["is_win"] = None
#                     score[0]["is_win"] = None
#                 score_details = TournamentSetsResult.objects.filter(tournament_id=semi_tour["id"]).values()
#                 score[0]["name"] = semi_tour["team1__name"]
#                 score[1]["name"] = semi_tour["team2__name"]
#                 score[0]["set"] = ["s1","s2","s3"]
#                 score[1]["set"] = ["s1","s2","s3"]
#                 for l__ in range(3):
                    
#                     if l__ < len(score_details):
#                         l = {"team1_point":score_details[l__]["team1_point"],"team2_point":score_details[l__]["team2_point"]}
#                     else:
#                         l = {"team1_point":None,"team2_point":None}
                    
#                     score[0]["score"].append(l["team1_point"])
#                     score[1]["score"].append(l["team2_point"])
                    
#                     if l["team1_point"] == None or l["team1_point"] == None:
#                         score[0]["win_status"].append(None)
#                         score[1]["win_status"].append(None)
#                     elif l["team1_point"] > l["team2_point"]:
#                         score[0]["win_status"].append(True)
#                         score[1]["win_status"].append(False)
#                     else:
#                         score[0]["win_status"].append(False)
#                         score[1]["win_status"].append(True)
#                 semi_tour["score"] = score
#             data['semi_final'] = list(knock_out_semifinal_tournament_data)

#             #this data for Final 
#             knock_out_final_tournament_data = Tournament.objects.filter(leagues=check_leagues.first(),match_type="Final").values("id","uuid","secret_key","match_number","match_type","elimination_round","team1__name", "team1_id", "team2_id"
#                                                                                                             ,"team1__team_image","team2__name","team2__team_image","winner_team__name", "winner_team_id", "loser_team_id", "winner_team__team_image","loser_team__name","loser_team__team_image","is_completed","play_ground_name")
#             for final_tour in knock_out_final_tournament_data:
#                 final_tour["is_edit"] = get_user.is_organizer and check_leagues.first().created_by == get_user or final_tour["team1_id"] == get_user.id or final_tour["team2_id"] == get_user.id
                
#                 score = [{"name": "","set": [],"score": [],"win_status": [],"is_win": True,"is_completed": True},{"name": "","set": [],"score": [],"win_status": [],"is_win": True,"is_completed": True}]
                
#                 if final_tour["team1_id"] == final_tour["winner_team_id"] and final_tour["winner_team_id"] is not None:
#                     score[0]["is_win"] = True
#                     score[1]["is_win"] = False
#                 elif final_tour["team2_id"] == final_tour["winner_team_id"] and final_tour["winner_team_id"] is not None:
#                     score[1]["is_win"] = True
#                     score[0]["is_win"] = False
#                 else:
#                     score[1]["is_win"] = None
#                     score[0]["is_win"] = None
#                 score_details = TournamentSetsResult.objects.filter(tournament_id=final_tour["id"]).values()
#                 score[0]["name"] = final_tour["team1__name"]
#                 score[1]["name"] = final_tour["team2__name"]
#                 score[0]["set"] = ["s1","s2","s3"]
#                 score[1]["set"] = ["s1","s2","s3"]
#                 for l__ in range(3):
                    
#                     if l__ < len(score_details):
#                         l = {"team1_point":score_details[l__]["team1_point"],"team2_point":score_details[l__]["team2_point"]}
#                     else:
#                         l = {"team1_point":None,"team2_point":None}
                    
#                     score[0]["score"].append(l["team1_point"])
#                     score[1]["score"].append(l["team2_point"])
                    
#                     if l["team1_point"] == None or l["team1_point"] == None:
#                         score[0]["win_status"].append(None)
#                         score[1]["win_status"].append(None)
#                     elif l["team1_point"] > l["team2_point"]:
#                         score[0]["win_status"].append(True)
#                         score[1]["win_status"].append(False)
#                     else:
#                         score[0]["win_status"].append(False)
#                         score[1]["win_status"].append(True)
#                 final_tour["score"] = score
#             data['final'] = list(knock_out_final_tournament_data)

            
#             if len(knock_out_final_tournament_data) == 1:
#                 if knock_out_final_tournament_data[0]["winner_team__name"] != "":
#                     data['winner_team'] = str(knock_out_final_tournament_data[0]["winner_team__name"])
#                 else:
#                     pass
#             else:
#                 pass

#             all_group_details = RoundRobinGroup.objects.filter(league_for=league)
#             for grp in all_group_details:
#                 teams = grp.all_teams.all()
#                 group_score_point_table = []
#                 # print(teams)
#                 for team in teams:
#                     team_score = {}
#                     total_match_detals = Tournament.objects.filter(leagues=league, match_type="Round Robin").filter(Q(team1=team) | Q(team2=team))
#                     completed_match_details = total_match_detals.filter(is_completed=True)
#                     win_match_details = completed_match_details.filter(winner_team=team).count()
#                     loss_match_details = completed_match_details.filter(loser_team=team).count()
#                     drow_match = len(completed_match_details) - (win_match_details + loss_match_details)
#                     match_list = list(total_match_detals.values_list("id", flat=True))
#                     for_score = 0
#                     aginst_score = 0
#                     for sc in match_list:
#                         co_team_position = Tournament.objects.filter(id=sc).first()
#                         set_score = TournamentSetsResult.objects.filter(tournament_id=sc)
#                         if co_team_position.team1 == team:
#                            for_score = for_score + sum(list(set_score.values_list("team1_point", flat=True)))
#                            aginst_score = aginst_score + sum(list(set_score.values_list("team2_point", flat=True)))
#                         else:
#                             for_score = for_score + sum(list(set_score.values_list("team2_point", flat=True)))
#                             aginst_score = aginst_score + sum(list(set_score.values_list("team1_point", flat=True)))
                    
#                     point = (win_match_details * 3) + (drow_match * 1)
#                     team_score["uuid"], team_score["secret_key"] = team.uuid, team.secret_key
#                     team_score["name"], team_score["completed_match"] = team.name, len(completed_match_details)
#                     team_score["win_match"], team_score["loss_match"] = win_match_details, loss_match_details
#                     team_score["drow_match"], team_score["for_score"] = drow_match, for_score
#                     team_score["aginst_score"], team_score["point"] = aginst_score, point
#                     group_score_point_table.append(team_score)
#                 # Append team details to group data
#                 tournament_details_group = Tournament.objects.filter(leagues=league,group=grp).values("id","uuid","secret_key","team1__name","team2__name","leagues__name","match_type","is_completed","group__court","play_ground_name","playing_date_time","group_id")
#                 for k_ in tournament_details_group:
#                     round_robin_group_detals = RoundRobinGroup.objects.filter(league_for=league, id=k_["group_id"]).first()
#                     k_["sets"] = round_robin_group_detals.number_sets
#                     k_["court"] = round_robin_group_detals.court
#                     k_["score"] = list(TournamentSetsResult.objects.filter(tournament_id=k_["id"]).values())
                
#                 group_score_point_table = sorted(group_score_point_table, key=lambda x: (x['point'], x['for_score']), reverse=True)
#                 # print(group_score_point_table)

#                 grp_data = {
#                     "id": grp.id,
#                     "court": grp.court,
#                     "league_for_id": grp.league_for_id,
#                     "all_games_status": grp.all_games_status,
#                     "all_tems": group_score_point_table,
#                     "tournament": tournament_details_group,
#                     "seleced_teams_id": grp.seleced_teams_id
#                 }
#                 data['point_table'].append(grp_data)

#             all_team = check_leagues.first().registered_team.all()
#             teams = []
#             for t in all_team:
#                 team_d = Team.objects.filter(id=t.id).values()
#                 teams.append(team_d[0])
#             for im in teams:
#                 if im["team_image"] != "":
#                     img_str = im["team_image"]
#                     im["team_image"] = f"{media_base_url}{img_str}"
            
            
#             tournament_details = Tournament.objects.filter(leagues=check_leagues.first()).order_by("match_number").values("id","match_number","uuid","secret_key","leagues__name","team1_id", "team2_id", "team1__team_image", "team2__team_image", "team1__name", "team2__name", "winner_team_id", "winner_team__name", "playing_date_time","match_type","group__court","is_completed","elimination_round","court_sn")
            
#             for sc in tournament_details:
#                 if sc["group__court"] is None:
#                     sc["group__court"] = sc["court_sn"]
#                 sc["is_edit"] = get_user.is_organizer and check_leagues.first().created_by == get_user or sc["team1_id"] == get_user.id or sc["team2_id"] == get_user.id
                
#                 score = [{"name": "","set": [],"score": [],"win_status": [],"is_win": True,"is_completed": True},{"name": "","set": [],"score": [],"win_status": [],"is_win": True,"is_completed": True}]
                
#                 if sc["team1_id"] == sc["winner_team_id"] and sc["winner_team_id"] is not None:
#                     score[0]["is_win"] = True
#                     score[1]["is_win"] = False
#                 elif sc["team2_id"] == sc["winner_team_id"] and sc["winner_team_id"] is not None:
#                     score[1]["is_win"] = True
#                     score[0]["is_win"] = False
#                 else:
#                     score[1]["is_win"] = None
#                     score[0]["is_win"] = None
#                 score_details = TournamentSetsResult.objects.filter(tournament_id=sc["id"]).values()
#                 score[0]["name"] = sc["team1__name"]
#                 score[1]["name"] = sc["team2__name"]
#                 score[0]["set"] = ["s1","s2","s3"]
#                 score[1]["set"] = ["s1","s2","s3"]
#                 for l__ in range(3):
                    
#                     if l__ < len(score_details):
#                         l = {"team1_point":score_details[l__]["team1_point"],"team2_point":score_details[l__]["team2_point"]}
#                     else:
#                         l = {"team1_point":None,"team2_point":None}
                    
#                     score[0]["score"].append(l["team1_point"])
#                     score[1]["score"].append(l["team2_point"])
                    
#                     if l["team1_point"] == None or l["team1_point"] == None:
#                         score[0]["win_status"].append(None)
#                         score[1]["win_status"].append(None)
#                     elif l["team1_point"] > l["team2_point"]:
#                         score[0]["win_status"].append(True)
#                         score[1]["win_status"].append(False)
#                     else:
#                         score[0]["win_status"].append(False)
#                         score[1]["win_status"].append(True)
#                 sc["score"] = score
                
#                 if sc["team1__team_image"] != "":
#                     img_str = sc["team1__team_image"]
#                     sc["team1__team_image"] = f"{media_base_url}{img_str}"
#                 if sc["team2__team_image"] != "":
#                     img_str = sc["team2__team_image"]
#                     sc["team2__team_image"] = f"{media_base_url}{img_str}"
            
#               # List to store data for the point table
            

#             data['teams'] = teams
#             data['match'] = tournament_details
#             data['tournament_detais'] = LeaguesPlayType.objects.filter(league_for = check_leagues.first()).values()
            
#             #notcomplete
            
#             data["create_group_status"] = get_user.is_organizer and check_leagues.first().created_by == get_user
#             data["status"], data['data'], data["message"] = status.HTTP_200_OK, leagues, "League data"
#         else:
#             data["status"], data['data'], data["message"] = status.HTTP_404_NOT_FOUND, [],  "User or League not found."
#     except Exception as e :
#         data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
#     return Response(data)

# # end


@api_view(('POST',))
def assigne_match(request):
    data = {'status': '', 'message': ''}
    user_uuid = request.data.get('user_uuid')
    user_secret_key = request.data.get('user_secret_key')
    league_uuid = request.data.get('league_uuid')
    league_secret_key = request.data.get('league_secret_key')
    
    check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
    check_leagues = Leagues.objects.filter(uuid=league_uuid, secret_key=league_secret_key)
    
    if check_user.exists() and check_leagues.exists():
        league = check_leagues.first()
        playtype = league.play_type   
        set_court = 8

        if playtype == "Single Elimination":
            check_pre_game =  Tournament.objects.filter(leagues=league)
            if check_pre_game.exists():
                check_leagues_com = check_pre_game.filter(is_completed=True)
                if len(check_pre_game) == len(check_leagues_com) and len(check_leagues_com) != 0:
                    pre_match_round = check_leagues_com.last().elimination_round
                    pre_round_details =  Tournament.objects.filter(leagues=league,elimination_round=pre_match_round)
                    teams = list(pre_round_details.values_list("winner_team_id", flat=True))
                    pre_match_number = check_leagues_com.last().match_number
                    define_court = LeaguesPlayType.objects.filter(league_for=league).data[1]["number_of_courts"]
                    court_num = 0
                    if len(teams) == 4:
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
                            Tournament.objects.create(court_sn=court_num,match_number=match_number_now, secret_key=secret_key, leagues=league, team1_id=team1, team2_id=team2, match_type=match_type, elimination_round=round_number)
                        data["status"], data["message"] = status.HTTP_200_OK, f"Matches created for {match_type}"
                        return Response(data)   
                    elif len(teams) == 2:
                        match_type = "Final"
                        round_number = pre_match_number
                        random.shuffle(teams)
                        match_number_now = 0
                        for i in range(0, len(teams), 2):
                            team1 = teams[i]
                            team2 = teams[i + 1]
                            obj = GenerateKey()
                            secret_key = obj.generate_league_unique_id()
                            match_number_now = match_number_now + 1
                            court_num = court_num + 1
                            Tournament.objects.create(court_sn=court_num,match_number=match_number_now, secret_key=secret_key, leagues=league, team1_id=team1, team2_id=team2, match_type=match_type, elimination_round=round_number)
                        data["status"], data["message"] = status.HTTP_200_OK, f"Matches created for {match_type}"
                        return Response(data)
                    else:
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
                            Tournament.objects.create(court_sn=court_num,match_number=match_number_now, secret_key=secret_key, leagues=league, team1_id=team1, team2_id=team2, match_type=match_type, elimination_round=round_number)
                        data["status"], data["message"] = status.HTTP_200_OK, f"Matches created for {match_type}-{round_number}"
                        return Response(data)
                else:
                    data["status"], data["message"] = status.HTTP_200_OK, "Previous Round is not completed or not updated"
                    return Response(data)
            else:
                teams = []
                court_num = 0
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
                        Tournament.objects.create(court_sn=court_num,match_number=match_number_now, secret_key=secret_key, leagues=league, team1_id=team1, team2_id=team2, match_type=match_type, elimination_round=0)
                    data["status"], data["message"] = status.HTTP_200_OK, f"Matches created for {match_type}"
                    return Response(data)
                if len(teams) == 2:
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
                        Tournament.objects.create(court_sn=court_num,match_number=match_number_now, secret_key=secret_key, leagues=league, team1_id=team1, team2_id=team2, match_type=match_type, elimination_round=0)
                    data["status"], data["message"] = status.HTTP_200_OK, f"Matches created for {match_type}"
                    return Response(data)
                else:
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
                        if set_court < court_num:
                            court_num = 1
                        Tournament.objects.create(court_sn=court_num,match_number=match_number_now, secret_key=secret_key, leagues=league, team1_id=team1, team2_id=team2, match_type=match_type, elimination_round=1)
                    data["status"], data["message"] = status.HTTP_200_OK, f"Matches created for {match_type}"
                    return Response(data)
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
                                team_score["uuid"], team_score["secret_key"] = team.uuid, team.secret_key
                                team_score["completed_match"] = len(completed_match_details)
                                team_score["win_match"], team_score["loss_match"] = win_match_details, loss_match_details
                                team_score["drow_match"], team_score["for_score"] = drow_match, drow_match
                                team_score["aginst_score"], team_score["point"] = drow_match, point
                                group_score_point_table.append(team_score)
                            grp_team = sorted(group_score_point_table, key=lambda x: x['point'], reverse=True)
                            select_team_instance = Team.objects.filter(uuid=grp_team[0]["uuid"],secret_key=grp_team[0]["secret_key"])
                            RoundRobinGroup.objects.filter(id=grp.id).update(seleced_teams=select_team_instance.first())
                        match_type = "Elimination Round"
                        round_number = 1
                        teams = list(RoundRobinGroup.objects.filter(league_for=league).values_list("seleced_teams_id", flat=True))
                        if len(teams) != len(RoundRobinGroup.objects.filter(league_for=league)):
                            data["status"],  data["message"] = status.HTTP_200_OK, f"Not all groups have winners selected"
                            return Response(data)
                        # print(teams)
                        if len(teams) == 2:
                            match_type = "Final"
                            round_number = 0
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
                            Tournament.objects.create(court_sn=court_num,match_number=match_number_now,secret_key=secret_key, leagues=league,team1_id=team1, team2_id=team2,match_type=match_type,elimination_round=round_number)
                        data["status"], data["message"] = status.HTTP_200_OK, f"Matches are created for {match_type} {round_number}"
                        return Response(data)
                    elif last_match_type == "Elimination Round":
                        match_type = "Elimination Round"
                        round_number = last_round + 1
                        # win_teams
                        teams = list(Tournament.objects.filter(leagues=league, elimination_round=last_round).values_list("winner_team_id", flat=True))
                        if len(teams) != len(Tournament.objects.filter(leagues=league, elimination_round=last_round)):
                            data["status"],  data["message"] = status.HTTP_200_OK, f"Not all groups have winners selected"
                            return Response(data)
                        elif len(teams) == 2:
                            match_type = "Final"
                            round_number = 0
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
                            Tournament.objects.create(court_sn=court_num,match_number=match_number_now,secret_key=secret_key, leagues=league,team1_id=team1, team2_id=team2,match_type=match_type,elimination_round=round_number)
                        data["status"], data["message"] = status.HTTP_200_OK, f"Matches are created for {match_type} {round_number}"
                        return Response(data)
                    elif last_match_type == "Semi Final":
                        match_type = "Final"
                        round_number = 0
                        # print()
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
                            Tournament.objects.create(court_sn=court_num,match_number=match_number_now,secret_key=secret_key, leagues=league,team1_id=team1, team2_id=team2,match_type=match_type,elimination_round=round_number)
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
                number_of_group = play_details.data[0]["number_of_courts"] if play_details else 0
                
                group_list = create_group(team_details_list, number_of_group)
                
                round_robin_group_details = RoundRobinGroup.objects.filter(league_for=league)
                if round_robin_group_details.exists():
                    if len(round_robin_group_details) == number_of_group:
                        data["status"],  data["message"] = status.HTTP_200_OK, f"Round Robin matches already created for {league.name}"
                        return Response(data)
                    else:
                        for gr in round_robin_group_details:
                            Tournament.objects.filter(group_id=gr.id).delete
                            gr.delete()
                set_number = LeaguesPlayType.objects.filter(league_for=league)
                if not set_number.exists():
                    data["status"],  data["message"] = status.HTTP_200_OK, team_details_list, "Sets and points not defined, please edit tournament"
                    return Response(data)
                set_number = set_number.first().data[0]["sets"]
                serial_number = 0
                print(group_list)
                for index, group_teams in enumerate(group_list, start=1):
                    group = RoundRobinGroup.objects.create(court=index, league_for=league, number_sets=set_number)
                    for team_id in group_teams:
                        team = Team.objects.get(id=team_id)
                        group.all_teams.add(team)
                    
                    match_combinations = list(combinations(group_teams, 2))
                    for teams in match_combinations:
                        obj = GenerateKey()
                        secret_key = obj.generate_league_unique_id()
                        team1, team2 = teams
                        serial_number = serial_number+1
                        Tournament.objects.create(match_number=serial_number,secret_key=secret_key, leagues=league, team1_id=team1, team2_id=team2, group_id=group.id,match_type="Round Robin")
                data["status"], data["message"] = status.HTTP_200_OK, f"Matches are created for Round Robin"
                return Response(data)
        elif playtype == "Round Robin":
            match_type = playtype
            registered_teams = league.registered_team.all() if league else None
            team_details_list = [team.id for team in registered_teams] if registered_teams else []
            max_team = league.max_number_team
            play_details = LeaguesPlayType.objects.filter(league_for=league).first()
            number_of_group = 1
            # print(max_team)
            # print(len(team_details_list))
            # print(int(max_team) != len(team_details_list))
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
            set_number = LeaguesPlayType.objects.filter(league_for=league)
            if not set_number.exists():
                data["status"],  data["message"] = status.HTTP_200_OK, team_details_list, "Group Created Successfully"
                return Response(data)
            set_number = set_number.first().data[0]["sets"]
            serial_number = 0
            court_num = 0
            
            for index, group_teams in enumerate(group_list, start=1):
                group = RoundRobinGroup.objects.create(court=index, league_for=league, number_sets=set_number)
                for team_id in group_teams:
                    team = Team.objects.get(id=team_id)
                    group.all_teams.add(team)
                
                match_combinations = list(combinations(group_teams, 2))
                for teams in match_combinations:
                    obj = GenerateKey()
                    secret_key = obj.generate_league_unique_id()
                    team1, team2 = teams
                    serial_number = serial_number+1
                    court_num += court_num 
                    if set_court < court_num:
                        court_num = 1
                    Tournament.objects.create(court_sn=court_num,match_number=serial_number,secret_key=secret_key, leagues=league, team1_id=team1, team2_id=team2, group_id=group.id,match_type="Round Robin")
            data["status"], data["message"] = status.HTTP_200_OK, f"Matches created for {match_type}"
            return Response(data)
        elif playtype == "Individual Match Play":
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
            
            round_number = 0
            random.shuffle(teams)
            match_number_now = 0
            # court_num = 0
            set_court = 8
            for i in range(0, len(teams), 2):
                team1 = teams[i]
                team2 = teams[i + 1]
                obj = GenerateKey()
                secret_key = obj.generate_league_unique_id()
                match_number_now = match_number_now + 1
                # court_num = court_num + 1
                # if set_court < court_num:
                #     court_num = 1
                court_num = 1
                Tournament.objects.create(court_sn=court_num,match_number=match_number_now,secret_key=secret_key, leagues=league,team1_id=team1, team2_id=team2,match_type=match_type,elimination_round=round_number) 
            data["status"], data["message"] = status.HTTP_200_OK, f"Matches created for {match_type}"
            return Response(data)
    else:
        data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "User or Tournament not found."
    return Response(data)



@api_view(('GET',))
def view_leagues(request):
    try:
        data = {
             'status':'',
             'create_group_status':False,
             'max_team': None,
             'total_register_team':None,
             'is_organizer': False,
             'winner_team': 'Not Declared',
             'data':[],
             'tournament_detais':[],
             'point_table':[],
             'elemination':[], 
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
            leagues = check_leagues.values('uuid','secret_key','name','location','leagues_start_date','leagues_end_date',
                               'registration_start_date','registration_end_date','team_type__name','team_person__name',
                               "street","city","state","postal_code","country","complete_address","latitude","longitude","play_type","registration_fee","description","image")
            league = check_leagues.first()
            get_user = check_user.first()
            if get_user.is_organizer:
                data['is_organizer'] =  True
            
            data['max_team'] =  league.max_number_team
            data['total_register_team'] =  league.registered_team.all().count()

            #this data for Elimination Round   
            knock_out_tournament_elimination_data = Tournament.objects.filter(leagues=check_leagues.first(),match_type="Elimination Round").values("id","uuid","secret_key","match_number","match_type","elimination_round","team1__name", "team1_id", "team2_id"
                                                                                                            ,"team1__team_image","team2__name","team2__team_image","winner_team__name", "winner_team_id", "loser_team_id", "winner_team__team_image","loser_team__name","loser_team__team_image","is_completed","play_ground_name")
            for ele_tour in knock_out_tournament_elimination_data:
                ele_tour["is_edit"] = get_user.is_organizer and check_leagues.first().created_by == get_user or ele_tour["team1_id"] == get_user.id or ele_tour["team2_id"] == get_user.id
                
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
                semi_tour["is_edit"] = get_user.is_organizer and check_leagues.first().created_by == get_user or semi_tour["team1_id"] == get_user.id or semi_tour["team2_id"] == get_user.id
                
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
                final_tour["is_edit"] = get_user.is_organizer and check_leagues.first().created_by == get_user or final_tour["team1_id"] == get_user.id or final_tour["team2_id"] == get_user.id
                
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

            
            if len(knock_out_final_tournament_data) == 1:
                if knock_out_final_tournament_data[0]["winner_team__name"] != "":
                    data['winner_team'] = str(knock_out_final_tournament_data[0]["winner_team__name"])
                else:
                    pass
            else:
                pass

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
            teams = []
            for t in all_team:
                team_d = Team.objects.filter(id=t.id).values()
                teams.append(team_d[0])
            for im in teams:
                if im["team_image"] != "":
                    img_str = im["team_image"]
                    im["team_image"] = f"{media_base_url}{img_str}"
            
            
            tournament_details = Tournament.objects.filter(leagues=check_leagues.first()).order_by("match_number").values("id","match_number","uuid","secret_key","leagues__name","team1_id", "team2_id", "team1__team_image", "team2__team_image", "team1__name", "team2__name", "winner_team_id", "winner_team__name", "playing_date_time","match_type","group__court","is_completed","elimination_round","court_sn")
            
            for sc in tournament_details:
                if sc["group__court"] is None:
                    sc["group__court"] = sc["court_sn"]
                sc["is_edit"] = get_user.is_organizer and check_leagues.first().created_by == get_user or sc["team1_id"] == get_user.id or sc["team2_id"] == get_user.id
                
                score = [{"name": "","set": [],"score": [],"win_status": [],"is_win": False,"is_completed": sc["is_completed"]},{"name": "","set": [],"score": [],"win_status": [],"is_win": False,"is_completed": sc["is_completed"]}]
                
                if sc["team1_id"] == sc["winner_team_id"] and sc["winner_team_id"] is not None:
                    score[0]["is_win"] = True
                    score[1]["is_win"] = False
                elif sc["team2_id"] == sc["winner_team_id"] and sc["winner_team_id"] is not None:
                    score[1]["is_win"] = True
                    score[0]["is_win"] = False
                else:
                    score[1]["is_win"] = False
                    score[0]["is_win"] = False
                score_details = TournamentSetsResult.objects.filter(tournament_id=sc["id"]).values()
                score[0]["name"] = sc["team1__name"]
                score[1]["name"] = sc["team2__name"]
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
                sc["score"] = score
                
                if sc["team1__team_image"] != "":
                    img_str = sc["team1__team_image"]
                    sc["team1__team_image"] = f"{media_base_url}{img_str}"
                if sc["team2__team_image"] != "":
                    img_str = sc["team2__team_image"]
                    sc["team2__team_image"] = f"{media_base_url}{img_str}"
            
              # List to store data for the point table
            

            data['teams'] = teams
            data['match'] = tournament_details
            data['tournament_detais'] = LeaguesPlayType.objects.filter(league_for = check_leagues.first()).values()
            
            #notcomplete
            
            data["create_group_status"] = get_user.is_organizer and check_leagues.first().created_by == get_user
            data["status"], data['data'], data["message"] = status.HTTP_200_OK, leagues, "League data"
        else:
            data["status"], data['data'], data["message"] = status.HTTP_404_NOT_FOUND, [],  "User or League not found."
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)
# end


#updated
from django.shortcuts import get_object_or_404
@api_view(('GET',))
def view_leagues_for_edit(request):
    try:
        data = {
            'status': '',
            'is_organizer': False,
            'data': [],
            'tournament_details': [],
            'message': ''
        }
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
            "play_type", "registration_fee", "description", "image"
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
    try:
        data = {'status':'','message':''}
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
                    check_play_type.update(data=data_list)
                else:
                    LeaguesPlayType.objects.create(play_type=get_tornament.play_type,league_for = get_tornament,data=data_list)
                data["status"], data["message"] = status.HTTP_200_OK, "League updated successfully"
            else:
                data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "This is not your tournamnet"
        else:
            data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "User or League not found"
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)




@api_view(('POST',))
def edit_leagues_max_team(request):
    try:
        data = {'status':'','message':''}
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        league_uuid = request.data.get('league_uuid')
        league_secret_key = request.data.get('league_secret_key')
        max_team = request.data.get('max_team')
        
        
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        check_league  = Leagues.objects.filter(uuid=league_uuid,secret_key=league_secret_key)
        if check_user.exists() and check_league.exists():
            get_tornament = check_league.first()
            get_user = check_user.first()
            if get_tornament.created_by==get_user:
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




#update today
@api_view(('POST',))
def delete_leagues(request):
    try:
        data = {'status':'','message':''}
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        leagues_id = request.data.get('leagues_id')
        
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        check_league  = Leagues.objects.filter(id=leagues_id)
        if check_user.exists() and check_league.exists():
            get_tornament = check_league.first()
            get_user = check_user.first()
            # if get_tornament.created_by==get_user:
            check_league.delete()
            data["status"], data["message"] = status.HTTP_200_OK, "League deleted successfully"
            # else:
            #     data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "This is not your tournamnet"
        else:
            data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "User or League not found"
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


#update today
@api_view(('GET',))
def list_leagues_user(request):
    try:
        data = {'status':'','data':'','message':''}
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
                all_leagues = Leagues.objects.filter(Q(name__icontains=search_text)).filter(created_by=get_user)
            else:
                all_leagues = Leagues.objects.filter(created_by=get_user)
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
                               'registration_start_date','registration_end_date','team_type__name','team_person__name',
                               "street","city","state","postal_code","country","complete_address","latitude","longitude")
            output = []

            # Grouping data by 'name'
            grouped_data = {}
            for item in list(leagues):
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
            
            for i in leagues:
                i["is_edit"] = True
                i["is_delete"] = True
            data["status"], data['data'], data["message"] = status.HTTP_200_OK, leagues, "League data"
        else:
            data["status"], data['data'], data["message"] = status.HTTP_404_NOT_FOUND, "","User not found."
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)



@api_view(('GET',))
def list_leagues_admin(request):
    try:
        data = {'status':'','data':'','message':''}
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        filter_by = request.GET.get('filter_by')
        search_text = request.GET.get('search_text')
        '''
        registration_open, future, past
        '''
        leagues = []
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        if check_user.exists() and check_user.first().is_admin:
            if search_text:
               all_leagues = Leagues.objects.filter(Q(name__icontains=search_text)).order_by('-id')
            else:
                all_leagues = Leagues.objects.all().order_by('-id')
            today_date = datetime.now()
            if filter_by == "future" :
                all_leagues = all_leagues.filter(registration_start_date__date__gte=today_date)
            elif filter_by == "past" :
                all_leagues = all_leagues.filter(registration_end_date__date__lte=today_date)
            elif filter_by == "registration_open" :
                all_leagues = all_leagues.filter(registration_start_date__date__lte=today_date,registration_end_date__date__gte=today_date)
            
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
            leagues = all_leagues.values('id','uuid','secret_key','name','location','leagues_start_date','leagues_end_date',
                               'registration_start_date','registration_end_date','team_type__name','team_person__name',
                               "street","city","state","postal_code","country","complete_address","latitude","longitude")
            output = []

            # Grouping data by 'name'
            grouped_data = {}
            for item in list(leagues):
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
               all_leagues = Leagues.objects.filter(Q(name__icontains=search_text)).order_by('-id')
            else:
                all_leagues = Leagues.objects.all().order_by('-id')
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
            leagues = all_leagues.values('id','uuid','secret_key','name','location','leagues_start_date','leagues_end_date',
                               'registration_start_date','registration_end_date','team_type__name','team_person__name',
                               "street","city","state","postal_code","country","complete_address","latitude","longitude")
            output = []
            # b = {
            #     'name': item['name'], 
            #     'lat':item['latitude'], 
            #     'long':item["longitude"],
            #     'registration_start_date':item["registration_start_date"],
            #     'registration_end_date':item["registration_end_date"],
            #     'leagues_start_date':item["leagues_start_date"],
            #     'leagues_end_date':item["leagues_end_date"],
            #     'location':item["location"],
            #     'type': [item['team_type__name']], 
            #     'data': [item]
            #     }
            # Grouping data by 'name'
            grouped_data = {}
            for item in list(leagues):
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
            
            
            
            data["status"], data['data'], data["message"] = status.HTTP_200_OK, leagues,"Data found"
        else:
            data["status"], data['data'], data["message"] = status.HTTP_404_NOT_FOUND, "","User not found."
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


def generate_random_scores():
    # Generate random scores for 3 rounds
    random_scores = []
    for _ in range(3):
        while True:
            score1 = random.randint(0, 15)
            score2 = random.randint(0, 15)
            # Ensure scores are not the same and have a minimum difference of 2
            if score1 != score2 and abs(score1 - score2) >= 2:
                random_scores.append((score1, score2))
                break
    return random_scores



@api_view(('POST',))
def tournament_edit(request):
    try:
        data = {'status':'', 'message':''}
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




@api_view(('GET',))
def team_register_user(request):
    data = {'status': '', 'data': '', 'message': ''}
    try:
        # Extract parameters from the request
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        league_uuid = request.GET.get('league_uuid')
        league_secret_key = request.GET.get('league_secret_key')

        # Check if the user exists and is a team manager
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key, is_team_manager=True)
        if check_user.exists():
            get_user = check_user.first()
            # Retrieve teams created by the user
            get_teams = Team.objects.filter(created_by=get_user)
            # Check if league exists
            check_league = Leagues.objects.filter(uuid=league_uuid, secret_key=league_secret_key)
            if check_league.exists():
                league = check_league.first()
                team_type = league.team_type.name
                team_person = league.team_person.name
                team_data = []
                
                team_id_list = list(league.registered_team.all().values_list("id", flat=True))
                # print(team_id_list)
                # Iterate through user's teams
                for team in get_teams:
                    flg = True
                    flg_text = ""
                    
                    # Check if team's type and person type match the league's requirements
                    if team_type and team.team_type and team_person and team.team_person:
                        if not (team_type.strip() == team.team_type.strip() and team_person.strip() == team.team_person.strip()):
                            flg = False
                            if team_type.strip() != team.team_type.strip():
                                flg_text = "Team type does not match for this league"
                            elif team_person.strip() != team.team_person.strip():
                                flg_text = "Person type does not match for this league"
                    else:
                        # Handle the case where team_type or team_person is None
                        flg = False
                        flg_text = "Team type or Person type is not provided"
                    
                    # Retrieve players in the team
                    player_data = Player.objects.filter(team=team).values("player_full_name", "player_ranking")
                    
                    # Append team details to the response
                    team_info = {
                        "uuid": team.uuid,
                        "secret_key": team.secret_key,
                        "team_name": team.name,
                        "team_image": str(team.team_image),
                        "location": team.location,
                        "created_by_name": f"{team.created_by.first_name} {team.created_by.last_name}",
                        "flg": flg,
                        "flg_text": flg_text,
                        "team_person": team.team_person,
                        "team_type": team.team_type,
                        "player_data": player_data,
                    }
                    if team_info["flg"] == True and team.id not in team_id_list:
                        team_data.append(team_info)
                    else:
                        pass
                # Prepare league data
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
                    # "image": league.image,
                    # "description": league.description,
                    # "registration_fee":league.registration_fee
                }
                # Prepare response data
                main_data = {"league_data": [league_data], "team_data": team_data}
                data["status"], data['data'], data["message"] = status.HTTP_200_OK, main_data, "Data found."
            else:
                data["status"], data['data'], data["message"] = status.HTTP_404_NOT_FOUND, "", "Tournament  not found"
        else:
            data["status"], data['data'], data["message"] = status.HTTP_404_NOT_FOUND, "", "User not found."
    except Exception as e:
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, str(e)
    return Response(data)




@api_view(('POST',))
def add_team_to_leagues(request):
    try:
        data = {'status':'','data':'','message':''}
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
        #parse_json data
        make_request_data = {"tournament_id":tournament_id,"user_id":user_id,"team_id_list":all_team_id}
        
        #json bytes
        json_bytes = json.dumps(make_request_data).encode('utf-8')
        
        # Encode bytes to base64
        my_data = base64.b64encode(json_bytes).decode('utf-8')

        if check_user.exists() and chaek_leagues.exists():
            number_of_team_join = len(team_uuid_all)
            chage_amount = int(number_of_team_join) * chaek_leagues.first().registration_fee*100

            
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
        PaymentDetailsForRegister(
            tournament=check_tournament,
            payment_for=payment_for,
            payment_by_id=request_data["user_id"],
            charge_amount=amount_total,
            teams_ids={"team_ids":request_data["team_id_list"]},
            payment_status=payment_status
        )
        if payment_status is True:
            check_tournament.registered_team.add(*teams_list)
            return render(request,"success_payment_for_register_team.html")
        else: 
            return render(request,"failed_paymentregister_team.html")
    except:
        return render(request,"failed_paymentregister_team.html")




@api_view(('GET',))
def player_or_manager_details(request):
    try:
        data = {'status':'','data':'','message':''}
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
    try:
        data = {'status':'','data':'','message':''}
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
                    get_player = Player.objects.filter(team_id=i.id)
                    for i in get_player :
                        player_data.append({"uuid":i.uuid,"secret_key":i.secret_key,"player_full_name":i.player_full_name,"player_ranking":i.player_ranking})
                    team_data.append({"team":team,"player_data":player_data})
                main_data = {"leauge_data":leauge_data,"team_data":team_data}
            elif get_user.is_team_manager :
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
                    get_player = Player.objects.filter(team__id=i.id)
                    for i in get_player :
                        player_data.append({"uuid":i.uuid,"secret_key":i.secret_key,"player_full_name":i.player_full_name,"player_ranking":i.player_ranking})
                    team_data.append({"team":team,"player_data":player_data})
                main_data = {"leauge_data":leauge_data,"team_data":team_data}
            elif get_user.is_player :
                pass
            
            data["status"], data['data'], data["message"] = status.HTTP_200_OK, main_data,"Data found."
        else:
            data["status"], data['data'], data["message"] = status.HTTP_404_NOT_FOUND, "","User not found."
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)



# @api_view(('POST',))
# def add_advertisement(request):
#     try:
#         data = {'status':'','data':'','message':''}
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




@api_view(('GET',))
def stats_details(request):
    data = {'status':'','data':[], 'message':''}
    try:
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        check_user = User.objects.filter(secret_key=user_secret_key,uuid=user_uuid)
        # print(check_user)
        
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
            stats_details["profile_image"] = image

            player_details = Player.objects.filter(player=get_user)
            if player_details.exists():
                total_league = 0
                win_league = 0
                
                team_ids = []
                for player_instance in player_details:
                    team_ids.extend(list(player_instance.team.values_list('id', flat=True)))
                total_play_matches = 0
                win_match = 0 
                for team_id in team_ids:
                    team_ = Team.objects.filter(id=team_id).first()
                    lea = Leagues.objects.filter(registered_team__in=[team_id])
                    check_match = Tournament.objects.filter(Q(team1=team_) | Q(team2=team_))
                    win_check_match = check_match.filter(winner_team=team_).count()
                    total_play_matches += check_match.count()
                    win_match += win_check_match
                    total_league += lea.count()

                
                stats_details["total_completed_turnament"] = total_league
                stats_details["total_win_turnament"] = win_league
                stats_details["total_completed_match"] = total_league
                stats_details["total_win_match"] = win_league
            else:
                
                stats_details["total_completed_turnament"] = 0
                stats_details["total_win_turnament"] = 0
                stats_details["total_completed_match"] = 0
                stats_details["total_win_match"] = 0
            data['message'] = "This user not in player list"
            data['data'] = [stats_details]
            data['status'] = status.HTTP_200_OK
        else:
            data['status'], data['data'], data['message'] = status.HTTP_400_BAD_REQUEST, [], f"user not found"
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)



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
                data['status'], data['message'] = status.HTTP_200_OK, f"League_uuid is required parameters."
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
        current_site = 'http' + '://' + request.META['HTTP_HOST']
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
    is_sponsor = serializers.CharField(source='sponsor.is_sponsor', read_only=True)
    is_sponsor_expires_at = serializers.CharField(source='sponsor.is_sponsor_expires_at', read_only=True)
    is_verified = serializers.CharField(source='sponsor.is_verified', read_only=True)
    
    class Meta:
        model = IsSponsorDetails
        fields = ["sponsor_uuid", "sponsor_secret_key","league_uuid","league_secret_key", "sponsor_name", "sponsor_image", "sponsor_email", "sponsor_email", "is_sponsor", "is_sponsor_expires_at", "is_verified", "sponsor_added_by", "description"]

#up
@api_view(('GET',))
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
                if search_text:
                   sponsor_details = IsSponsorDetails.objects.filter(sponsor_added_by=get_user).filter(Q(sponsor__first_name__icontains=search_text)|Q(sponsor__last_name__icontains=search_text))
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
    except Exception as e:
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, str(e)
    return Response(data)


# new
@api_view(('GET',))
def view_sponsor(request):
    data = {'status': '', 'message': '', 'data': {}}
    try:
        sponsor_uuid = request.GET.get('sponsor_uuid')
        sponsor_secret_key = request.GET.get('sponsor_secret_key')
        print("sponsor_uuid",sponsor_uuid)
        print("sponsor_secret_key",sponsor_secret_key)
        check_user = IsSponsorDetails.objects.filter(uuid=sponsor_uuid, secret_key=sponsor_secret_key)
        # check_user = IsSponsorDetails.objects.filter(sponsor__uuid=sponsor_uuid, sponsor__secret_key=sponsor_secret_key)
        print("check_user",check_user)
        if check_user.exists():
            print("check_user",check_user)
            sponsor_instance = check_user.first()
            serializer = IsSponsorDetailsSerializer(sponsor_instance)
            data['data'] = [serializer.data]
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
    try:
        data = {'status':'','data':'','message':''}
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
                all_leagues = Leagues.objects.filter(created_by=check_user.first()).filter(Q(name__icontains=search_text))
            else:
                all_leagues = Leagues.objects.filter(created_by=check_user.first())
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
                               'registration_start_date','registration_end_date','team_type__name','team_person__name',
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
                all_leagues = all_leagues

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
            data['status'], data['data'], data['message'] = status.HTTP_200_OK, all_leagues, f"Data Found"
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
                all_leagues=all_leagues

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

            all_leagues = all_leagues.values('uuid','secret_key','name','location','leagues_start_date','leagues_end_date',
                               'registration_start_date','registration_end_date','team_type__name','team_person__name',
                               "street","city","state","postal_code","country","complete_address","latitude","longitude")
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
def my_league(request):
    data = {'status':'','data':[], 'message':''}
    try:
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        search_text = request.GET.get('search_text')
        check_user = User.objects.filter(secret_key=user_secret_key,uuid=user_uuid)
        today_date = timezone.now()
        if check_user.exists() and check_user.first().is_organizer:
            get_user = check_user.first()
            all_leagues_main = Leagues.objects.filter(registration_end_date__date__lte=today_date)
            all_leagues = all_leagues_main.filter(registered_team__created_by=get_user)
            if search_text:
                all_leagues = all_leagues.filter(Q(name__icontains=search_text))
            all_leagues = all_leagues.values('uuid','secret_key','name','location','leagues_start_date','leagues_end_date',
                            'registration_start_date','registration_end_date','team_type__name','team_person__name',
                            "street","city","state","postal_code","country","complete_address","latitude","longitude","is_complete")

            data['status'], data['data'], data['message'] = status.HTTP_200_OK, all_leagues, f"Data found"
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
