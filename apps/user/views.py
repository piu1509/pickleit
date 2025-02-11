
from xhtml2pdf import pisa
import jwt, re, base64, uuid
import random, json, requests
from datetime import datetime, date, timedelta

from django.db.models import Q
from django.conf import settings
from django.http import HttpResponse
from django.core.mail import send_mail
from django.contrib.auth import authenticate
from django.core.files.base import ContentFile
from django.template.loader import get_template
from django.shortcuts import render, HttpResponse
from django.contrib.auth.hashers import make_password
from django.contrib.sites.shortcuts import get_current_site

from rest_framework.response import Response
from rest_framework import status, serializers
from rest_framework.decorators import api_view
from rest_framework.authtoken.models import Token
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.chat.models import *
from apps.team.models import *
from apps.user.models import PDFFile
from apps.user.models import User, Role
from apps.user.helpers import GenerateKey
from apps.pickleitcollection.views import *
from apps.pickleitcollection.models import *
from apps.team.views import notify_edited_player, haversine

app_name = settings.APP_NAME
protocol = settings.PROTOCALL


def get_detailed_address(full_address, api_key):
  
    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={full_address}&key={api_key}"

    # Send request to Google Maps Geocoding API
    response = requests.get(url)
    data = response.json()
    print(data)
    
    # Check if request was successful
    if data['status'] == 'OK':
        # Extract required information from response
        components = data['results'][0]['address_components']
        state = country = pincode = street = None
        
        for component in components:
            types = component['types']
            if 'administrative_area_level_1' in types:
                state = component['long_name']
            elif 'country' in types:
                country = component['long_name']
            elif 'postal_code' in types:
                pincode = component['long_name']
            elif 'route' in types:
                street = component['long_name']
            elif 'locality' in types:
                city = component['long_name']

        return street, city, state, country, pincode 
    else:
        print("Failed to fetch address details. Status:", data['status'])
        return None, None, None, None, None
   

def get_location_from_coordinates(latitude, longitude):
    try:
        api_key = settings.MAP_API_KEY  # Replace with your API key
        url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {
            "latlng": f"{latitude},{longitude}",
            "key": api_key,
        }
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        if data.get("results"):
            address = data["results"][0].get("formatted_address", "Unknown location")
            return address
        return "Unknown location"
    except Exception as e:
        return f"Error: {e}"
 

@api_view(('GET',))
def get_api_version(request):
    data = {}
    try :
        with open("data.json", "r") as file:
            data_json = json.load(file)
        data['status'], data['version'], data['message'] = status.HTTP_200_OK, data_json["version"][-1], f"Get all version"
    except Exception as e :
        data['status'], data['data'], data['message'] = status.HTTP_400_BAD_REQUEST, [], f"{e}"
    return Response(data)


@api_view(('POST',))
def app_version_post(request):
    try :
        version =  request.data.get("version")
        
        with open("data.json", "r") as file:
            data = json.load(file)
        
        data["version"].append(str(version))

        # Write the updated JSON data back to the file
        with open("data.json", "w") as file:
            json.dump(data, file, indent=4)
        data['status'], data['message'] = status.HTTP_200_OK, f"Version is Updated"  
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


@api_view(('GET',))
def user_signup_email_check_api(request):
    data = {'status':'','message':''}
    try :        
        email = request.GET.get('email')
        check_email = User.objects.filter(username=email,email=email)
        # check_email2 = Player.objects.filter(player_email=email)

        if check_email.exists():
            data['status'], data['message'] = status.HTTP_409_CONFLICT, f"Email already exists"
        # elif check_email2.exists():
        #     data['status'], data['message'] = status.HTTP_409_CONFLICT, f"Email already exists"
        else:
            data['status'], data['message'] = status.HTTP_200_OK, f"HTTP_200_OK"
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"

    return Response(data)


@api_view(('POST',))
def user_login_api(request):
    data = {'status':'','message':''}
    try :        
        email = request.data.get('email')
        password = request.data.get('password')
        
        if not email or not password:
            return Response({
                'status': status.HTTP_400_BAD_REQUEST,
                'message': 'Username and password are required.'
            })
        email = str(email).strip()
        password = str(password).strip()
        user = authenticate(username=email, password=password)
        if user is not None and user.is_superuser:
            data = {
                    'status': status.HTTP_404_NOT_FOUND,
                    'jwt': '',
                    "message":"No user found with this credentials",
                }

        elif user is not None and user.get_role() is not None and user.is_verified :
            # secret_key_base64 = base64.b64encode(user.username.encode()).decode()
            secret_key_base64 = base64.b64encode('q5q#@qf)nt452'.encode()).decode()
            expiration_time = datetime.utcnow() + timedelta(hours=1)
            check_player = Player.objects.filter(player_email=user.email,player_phone_number=user.phone)
            if check_player.exists() :
                create_team_option = True
                team_name = ""
                # team_created_by = f"{str(check_player.first().team.created_by.first_name).capitalize()} {str(check_player.first().team.created_by.last_name).capitalize()}"
                team_created_by = ""
            else :
                create_team_option = False
                team_name = ""
                team_created_by = ""
            full_name = f"{user.first_name} {user.last_name}"
            payload = {
                'uuid': f"{user.uuid}",
                'secret_key': f"{user.secret_key}",
                "role":user.role.role,
                "email":user.email,
                "full_name":full_name,
                'timestamp': f"{datetime.now()}",
                'is_verified' : user.is_verified,
                'create_team_option' : create_team_option,
                'team_name' : team_name,
                'team_created_by' : team_created_by,
                'exp': expiration_time, 
                'is_organizer': user.is_organizer,
                "self_ranking":user.is_rank,
            }
            
            # algorithm = 'HS256'
            algorithm = 'HS384'
            token = jwt.encode(payload, secret_key_base64, algorithm=algorithm)
            refresh_token = jwt.encode({'uuid': str(user.uuid)}, secret_key_base64, algorithm=algorithm)
            check_room = NotifiRoom.objects.filter(user=user)
            if check_room.exists():
                room_name = check_room.first().name
            else:
                user_id = user.id
                room_name= f"user_{user_id}"
                room = NotifiRoom.objects.create(user=user, name=room_name)
                room = NotifiRoom.objects.filter(user__id=user.id)
                NotificationBox.objects.create(room=room.first(),titel=f"Profile completion.",text_message=f"Hi {user.username} Welcome to PickleIT! Remember to fully update your profile.", notify_for=user)
            data = {
                'status': status.HTTP_200_OK,
                'jwt': token,
                'refresh_token':refresh_token,
                'room_name': room_name,
                'is_show_screen': user.is_screen,
                "self_ranking":user.is_rank,
                "message":"Successfully logged in",  
                "test":"okay",              
            }
        elif user is not None and user.get_role() is not None and not user.is_verified :
            data = {
                'status': status.HTTP_401_UNAUTHORIZED,
                'jwt': '',
                'refresh_token':'',
                "message":"Please verify your email, a verification link is send to your email",               
            }
        else:
            check_user = User.objects.filter(username=email) 
            if check_user.exists() :
                data = {
                    'status': status.HTTP_404_NOT_FOUND,
                    'jwt': '',
                    "message":"Your password does not match our records",
                }
            else:
                data = {
                    'status': status.HTTP_404_NOT_FOUND,
                    'jwt': '',
                    "message":"No user found with this credentials",
                }
    except Exception as e :
        data = {
                'status': status.HTTP_400_BAD_REQUEST,
                'jwt': '',
                'message': f'{e}',
            }
    return Response(data)


@api_view(('POST',))
def get_user_access_token(request):
    data = {'status':'','message':''}
    try :        
        refresh_token = request.data.get('refresh_token')
        if refresh_token and refresh_token != "" :
            algorithm = 'HS384'
            secret_key_base64 = base64.b64encode('q5q#@qf)nt452'.encode()).decode()
            decoded_token = jwt.decode(refresh_token, secret_key_base64, algorithms=[algorithm])
            user_uuid = decoded_token['uuid']
            user = User.objects.filter(uuid=user_uuid)
            if user.first():
                user=user.first()
                if user is not None and user.get_role() is not None and user.is_verified :
                    # secret_key_base64 = base64.b64encode(user.username.encode()).decode()
                    secret_key_base64 = base64.b64encode('q5q#@qf)nt452'.encode()).decode()
                    expiration_time = datetime.utcnow() + timedelta(hours=1)
                    check_player = Player.objects.filter(player_email=user.email,player_phone_number=user.phone)
                    if check_player.exists() :
                        create_team_option = True
                        team_name = check_player.first().team.name
                        team_created_by = f"{str(check_player.first().team.created_by.first_name).capitalize()} {str(check_player.first().team.created_by.last_name).capitalize()}"
                    else :
                        create_team_option = False
                        team_name = ""
                        team_created_by = ""
                    payload = {
                        'uuid': f"{user.uuid}",
                        'secret_key': f"{user.secret_key}",
                        "role":user.role.role,
                        "email":user.email,
                        'timestamp': f"{datetime.now()}",
                        'is_verified' : user.is_verified,
                        'create_team_option' : create_team_option,
                        'team_name' : team_name,
                        'team_created_by' : team_created_by,
                        'exp': expiration_time, 
                        'is_organizer': user.is_organizer,
                    }
                    
                    # algorithm = 'HS256'
                    algorithm = 'HS384'
                    token = jwt.encode(payload, secret_key_base64, algorithm=algorithm)
                    refresh_token = jwt.encode({'uuid': str(user.uuid)}, secret_key_base64, algorithm=algorithm)
                    
                    data = {
                        'status': status.HTTP_200_OK,
                        'jwt': token,
                        'refresh_token':refresh_token,
                        "message":"Successfully logged in",               
                    }
                elif user is not None and user.get_role() is not None and not user.is_verified :
                    data = {
                        'status': status.HTTP_401_UNAUTHORIZED,
                        'jwt': '',
                        'refresh_token':'',
                        "message":"please verify your email, a verification link is send to your email",               
                    }
                else:
                    data = {
                        'status': status.HTTP_404_NOT_FOUND,
                        'jwt': '',
                        "message":"No user found with this credentials",
                    }
            else:
                data = {
                        'status': status.HTTP_404_NOT_FOUND,
                        'jwt': '',
                        "message":"No user found with this credentials",
                    }
        else:
            data = {
                    'status': status.HTTP_404_NOT_FOUND,
                    'jwt': '',
                    "message":"No user found with this credentials",
                }
    except Exception as e :
        data = {
                'status': status.HTTP_400_BAD_REQUEST,
                'jwt': '',
                'message': f'{e}',
            }
    return Response(data)


@api_view(('POST',))
def user_signup_api(request):
    data = {'status':'','message':''}
    try:        
        email = request.data.get('email')
        first_name = request.data.get('first_name')
        last_name = request.data.get('last_name')
        password = request.data.get('password')
        confirm_password = request.data.get('confirm_password')
        phone = request.data.get('phone')
        rank = request.data.get('rank')
        gender = request.data.get('gender')
        latitude = request.data.get('latitude')
        longitude = request.data.get('longitude')
        current_location =  request.data.get('current_location')
        
        if gender is None:
            gender = "Male"

        if not email or not first_name or not password or not confirm_password :
            data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, 'Email, First name, Last name, Password  and Confirm_password are required'
            return Response(data)
        
        elif email == "" or first_name == "" or password =="" or confirm_password =="" :
            data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, 'Email, First name, Last name, Password  and Confirm_password are required'
            return Response(data)

        else:
            check_user = User.objects.filter(email=email,username=email).values('id')
            if password == confirm_password :
                if check_user.exists():
                    data['status'], data['message'] = status.HTTP_409_CONFLICT, 'User already exists'
                    return Response(data)
                else:
                    obj = GenerateKey()
                    obj2 = GenerateKey()
                    generated_otp = obj2.generated_otp()
                    secret_key = obj.gen_user_key()
                    raw_password = password
                    hash_password = make_password(password)
                    check_role = Role.objects.filter(role='User')
                    if check_role.exists():
                        save_user = User(secret_key=secret_key,email=email,username=email,first_name=first_name,last_name=last_name,rank=rank,phone=phone,
                                            role_id=check_role.first().id,password=hash_password,password_raw=raw_password,generated_otp=generated_otp,gender=gender,is_player=True, latitude=latitude, longitude=longitude, current_location=current_location, permanent_location=current_location)
                        save_user.save()
                        #add as a player
                        obj = GenerateKey()
                        secret_key = obj.gen_player_key()
                        save_player = Player(secret_key=secret_key,player_first_name=first_name,player_last_name=last_name,player_phone_number=phone,player_ranking=rank,
                                 player_full_name=f"{first_name} {last_name}",player_email=email,created_by=save_user)
                        save_player.save()
                        #####
                        check_player = Player.objects.filter(player_email=email)
                        if check_player.exists():
                            update_player = check_player.first()
                            update_player.player_id = save_user.id
                            update_player.save()
                            save_user.is_player = True
                            save_user.phone = update_player.player_phone_number
                            save_user.save()
                        data['status'], data['message'] = status.HTTP_200_OK, 'User account created successfully'
                    else:
                        data['status'], data['message'] = status.HTTP_200_OK, 'Please contact to the developer'
            else:
                data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, 'Password and confirm password does not match'
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
        
    return Response(data)


@api_view(('POST',))
def send_email_verification(request):
    data = {'status': '', 'message': ''}
    try:        
        email = request.data.get('email')
        check_email = User.objects.filter(email=str(email).strip())
        
        if check_email.exists():
            get_user = check_email.first()
            is_verified = get_user.is_verified

            if not is_verified:
                # current_site = request.META['wsgi.url_scheme'] + '://' + request.META['HTTP_HOST']
                #protocol = 'https' if request.is_secure() else 'http'
                host = request.get_host()
                current_site = f"{protocol}://{host}"
                verification_url = f"{current_site}/user/3342cb68e59a46aa0d8be6504ee298446bf1caff5aeae202ddec86de1e38436c/{get_user.uuid}/{get_user.secret_key}/{get_user.generated_otp}/"

                subject = f'{app_name} - Verify Your Email Address'
                # message = f"Dear {get_user.first_name} {get_user.last_name},\nThank you for signing up for {app_name}! To ensure the security of your account and to get started, we need to verify your email address. \nPlease click the button below to complete the verification process:"
                # message = f"Dear {get_user.first_name} {get_user.last_name}"
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
                                                                            <td><img src="{current_site}/static/images/email_verification.png" style="display: block;width: 100%;" width="100%;"></td>
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
                                                                                        <p style="font-size: 17px;font-weight: 500;color:#333333">Thank you for signing up for {app_name}! To ensure the security of your account and to get started, You need to verify your email address.Please click the button below to complete the verification process.</p>
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
                                                                                <td align="center">
                                                                                <a href="{verification_url}" style="font-size: 17px;font-weight: 500;color:#333333; background-color:#008CBA;color:white;padding:10px;text-align:center;text-decoration:none;display:inline-block;border-radius:5px;">Verify Email</a>
                                                                                </td>
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
                                                    <td style="text-align: center;"><img src="https://pickleit.app/media/logo_pickelit.png" width="100"></td>
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
                data['status'], data['message'] = status.HTTP_200_OK, f"Email verification link sent"
            else:
                data['status'], data['message'] = status.HTTP_409_CONFLICT, f"Email already verified"
        else:
            data['status'], data['message'] = status.HTTP_403_FORBIDDEN, f"Email not found"
    except Exception as e:
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, str(e)
    
    return Response(data)


def verification_link(request,uuid,skey,otp):
    data = {}
    context = {}
    try :        
        check_user = User.objects.filter(uuid=uuid,secret_key=skey,generated_otp=otp)
        # current_site = request.META['wsgi.url_scheme'] + '://' + request.META['HTTP_HOST']
        #protocol = 'https' if request.is_secure() else 'http'
        host = request.get_host()
        current_site = f"{protocol}://{host}"
        if check_user.exists():
            get_user = check_user.first()
            is_verified = get_user.is_verified
            if is_verified :
                # data = HttpResponse("email already verified")
                context['firstname'] = get_user.first_name
                context['lastname'] = get_user.last_name
                context['logo_url1'] = f"{current_site}/static/images/email_verification_complete.png"
                context['logo_url2'] = f"{current_site}/static/images/PickleIt_logo.png"
                return render (request,'email_verification_complete.html',context)
            else:
                get_user.is_verified = True
                get_user.save()
                context['firstname'] = get_user.first_name
                context['lastname'] = get_user.last_name
                context['logo_url1'] = f"{current_site}/static/images/email_verification_complete.png"
                context['logo_url2'] = f"{current_site}/static/images/PickleIt_logo.png"
                return render (request,'email_verification_complete.html',context)
        else:
            data = HttpResponse("Not a valid responce")
    except Exception as e :
        data = HttpResponse (f"{e}")
    return data


@api_view(('POST',))
def forgot_password(request):
    data = {'status': '', 'message': ''}
    try:        
        email = request.data.get('email')
        check_email = User.objects.filter(email=str(email).strip())
        if check_email.exists():
            obj = GenerateKey()
            generate_password = str(obj.generated_otp())[:6]
            get_user = check_email.first()
            get_user.password = make_password(generate_password)
            get_user.password_raw =  generate_password
            get_user.save()
            data['status'], data['message'] = status.HTTP_200_OK, f"New password is send to {email}"
        else:
            data['status'], data['message'] = status.HTTP_403_FORBIDDEN, f"Email not found"
    except Exception as e:
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, str(e)
    return Response(data)


@api_view(('POST',))
def change_password(request):
    data = {'status': '', 'message': ''}
    try:        
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        password = request.data.get('password')

        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if check_user.exists():
            obj = GenerateKey()
            generate_password = password
            get_user = check_user.first()
            get_user.password = make_password(generate_password)
            get_user.password_raw = password
            get_user.save()
            data['status'], data['message'] = status.HTTP_200_OK, f"Your password has been changed, use the new password when you login again"
        else:
            data['status'], data['message'] = status.HTTP_403_FORBIDDEN, f"User not found"
    except Exception as e:
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, str(e)
    return Response(data)


@api_view(('POST',))
def email_send_forgot_password(request):
    data = {'status': '', 'message': ''}
    try:        
        email = request.data.get('email')
        check_email = User.objects.filter(email=str(email).strip())
        if check_email.exists():
            #protocol = 'https' if request.is_secure() else 'http'
            host = request.get_host()
            current_site = f"{protocol}://{host}"
            # current_site = request.META['wsgi.url_scheme'] + '://' + request.META['HTTP_HOST']
            # verification_url = f"{current_site}/user/3342cb68e59a46aa0d8be6504ee298446bf1caff5aeae202ddec86de1e38436c/{get_user.uuid}/{get_user.secret_key}/{get_user.generated_otp}/"
            get_user = check_email.first()
            subject = f'{app_name} - Password Reset'
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
                                                                        <td><img src="{current_site}/static/images/update_password.jpg" style="display: block;width: 100%;" width="100%;"></td>
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
                                                                                    <p style="font-size: 17px;font-weight: 500;color:#333333">You recently requested a password reset for your account. As per your request, a new password has been generated for you. Please find your new login details below:</p>
                                                                                    <br>
                                                                                    <p style="font-size: 17px;font-weight: 500;color:#333333">Email: {email}</p>
                                                                                    <p style="font-size: 17px;font-weight: 500;color:#333333">New Password: {get_user.password_raw}</p>
                                                                                    <br>
                                                                                    <p style="font-size: 17px;font-weight: 500;color:#333333">Please use this new password to log in to your account. For security reasons, we highly recommend changing your password after logging in.</p>
                                                                                    <p style="font-size: 17px;font-weight: 500;color:#333333">If you did not request this password reset, please contact our support team immediately at pickleitnow1@gmail.com to secure your account.</p>
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
            data['status'], data['message'] = status.HTTP_200_OK, f"New password is send to {get_user.email}"
        else:
            data['status'], data['message'] = status.HTTP_403_FORBIDDEN, f"Email not found"
    except Exception as e:
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, str(e)
    return Response(data)


@api_view(('POST',))
def add_admin(request):
    data = {'status':'','message':''}
    try:        
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        email = request.data.get('email')
        first_name = request.data.get('first_name')
        last_name = request.data.get('last_name')
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        check_admin = User.objects.filter(email=email,username=email)
        if check_user.exists() and check_user.first().is_admin :
            if not email or not first_name or not last_name or email == "" or first_name == "" or last_name == "" :
                data["status"], data['data'], data["message"] = status.HTTP_200_OK, "","Email, First name and Last name required"
                return Response(data)
            if check_admin.exists():
                data["status"], data['data'], data["message"] = status.HTTP_200_OK, "","Admin already exist"
                return Response(data)
            obj = GenerateKey()
            obj2 = GenerateKey()
            generated_otp = obj2.generated_otp()
            secret_key = obj.gen_user_key()
            password = str(generated_otp)[:6]
            raw_password = password
            hash_password = make_password(password)
            role_id = Role.objects.filter(role='Admin').first().id
            save_user = User(secret_key=secret_key,email=email,username=email,first_name=first_name,last_name=last_name,is_admin=True,
                                     role_id=role_id,password=hash_password,password_raw=raw_password,generated_otp=generated_otp,
                                     is_verified=True)
            save_user.save()
            data["status"], data['data'], data["message"] = status.HTTP_200_OK, "","Admin created successfully"
        else:
            data["status"], data['data'], data["message"] = status.HTTP_404_NOT_FOUND, "","HTTP_404_NOT_FOUND. User not found."
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


@api_view(('POST',))
def edit_admin(request):
    data = {'status':'','message':''}
    try:        
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        update_user_uuid = request.data.get('update_user_uuid')
        update_user_secret_key = request.data.get('update_user_secret_key')
        email = request.data.get('email')
        first_name = request.data.get('first_name')
        last_name = request.data.get('last_name')
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        check_update_user = User.objects.filter(uuid=update_user_uuid,secret_key=update_user_secret_key)
        if check_user.exists() and check_user.first().is_admin and check_update_user.exists():
            update_user = check_update_user.first()
            update_user.email = email
            update_user.username = email
            update_user.first_name = first_name
            update_user.last_name = last_name
            update_user.save()
            data["status"], data['data'], data["message"] = status.HTTP_200_OK, "","Admin edited successfully"
        else:
            data["status"], data['data'], data["message"] = status.HTTP_404_NOT_FOUND, "","HTTP_404_NOT_FOUND. User not found."
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


@api_view(('GET',))
def list_admin(request):
    data = {'status':'','message':''}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        if check_user.exists() and check_user.first().is_admin :
            get_admin = User.objects.exclude(is_superuser=True).filter(is_admin=True).values('uuid','secret_key','username','first_name','last_name','image').order_by('first_name')
            data["status"], data['data'], data["message"] = status.HTTP_200_OK, get_admin,"HTTP_200_OK. Data found."
        else:
            data["status"], data['data'], data["message"] = status.HTTP_404_NOT_FOUND, "","User not found"
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


@api_view(('POST',))
def send_admin_password_email(request):
    data = {'status':'','message':''}
    try:        
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        send_mail_user = request.data.get('send_mail_user')
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key,is_admin=True)
        check_user2 = User.objects.filter(email=send_mail_user,is_admin=True)
        if check_user.exists() and check_user.first().is_admin and check_user2.exists():
            get_user = check_user2.first()
            #protocol = 'https' if request.is_secure() else 'http'
            host = request.get_host()
            current_site = f"{protocol}://{host}"
            # current_site = request.META['wsgi.url_scheme'] + '://' + request.META['HTTP_HOST']
            subject = f'{app_name} - Your Login Credentials'
            # message = f"Dear {get_user.first_name} {get_user.last_name},\nThank you for signing up for {app_name}! To ensure the security of your account and to get started, we need to verify your email address. \nPlease click the button below to complete the verification process:"
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
                                                                        <td><img src="{current_site}/static/images/admin_password_send.png" style="display: block;width: 100%;" width="100%;"></td>
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
                                                                                    <p style=" font-size: 20px; font-weight: 500; line-height: 22px; color: #333333; margin: 0; padding: 0;">Dear {get_user.first_name} {get_user.last_name},</p>
                                                                                </td>
                                                                                </tr>
                                                                                <tr>
                                                                                <td style="padding:0 25px 20px 25px;">
                                                                                    <p style="font-size: 17px;font-weight: 500;color:#333333">We hope this email finds you well. As requested, we are sending you the login credentials for your account. Please find your username and a temporary password below:</p>
                                                                                    <p style="font-size: 17px;font-weight: 500;color:#333333">Username: {get_user.username}</p>
                                                                                    <p style="font-size: 17px;font-weight: 500;color:#333333">Password: {get_user.password_raw}</p>
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
                                                <td style="text-align: center;"><p style=" font-size: 15px; font-weight: 500; color: #c1c1c1; line-height: 20px; margin: 0;">© 2023 {app_name}. All Rights Reserved.</p></td>
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
            data['status'], data['message'] = status.HTTP_200_OK, f"Email verification link sent"
        else:
            data["status"], data['data'], data["message"] = status.HTTP_404_NOT_FOUND, "","HTTP_404_NOT_FOUND. User not found."
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


@api_view(('GET',))
def list_user(request):
    data = {'status':'','message':''}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        filter_by = request.GET.get('filter_by')
        all_user = User.objects.exclude(is_superuser=True).order_by('first_name')
        check_user = all_user.filter(uuid=user_uuid,secret_key=user_secret_key)
        if check_user.exists() :
            get_user = check_user.first()
            if get_user.is_admin :
                if filter_by == "manager":
                    all_user = all_user.filter(is_team_manager=True).values('uuid','secret_key','username','first_name','last_name','image','is_team_manager','is_player').order_by('-id')
                    data["status"], data['data'], data["message"] = status.HTTP_200_OK, all_user,"Data found"
                elif filter_by == "player":
                    all_user = all_user.filter(is_player=True).values('uuid','secret_key','username','first_name','last_name','image','is_team_manager','is_player').order_by('-id')
                    data["status"], data['data'], data["message"] = status.HTTP_200_OK, all_user,"Data found"
                else:
                    all_user = all_user.exclude(is_admin=True).values('uuid','secret_key','username','first_name','last_name','image','is_team_manager','is_player').order_by('-id')
                    data["status"], data['data'], data["message"] = status.HTTP_200_OK, all_user,"Data found"
                return Response(data)
            else:
                data["status"], data['data'], data["message"] = status.HTTP_404_NOT_FOUND, "","User is not Admin"
        else:
            data["status"], data['data'], data["message"] = status.HTTP_404_NOT_FOUND, "","User not found"
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


@api_view(('POST',))
def add_user(request):
    data = {'status':'','message':''}
    try:        
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        email = request.data.get('email')
        first_name = request.data.get('first_name')
        last_name = request.data.get('last_name')
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        check_user_ad = User.objects.filter(email=email,username=email)
        if check_user.exists() and check_user.first().is_admin :
            if not email or not first_name or not last_name or email == "" or first_name == "" or last_name == "" :
                data["status"], data['data'], data["message"] = status.HTTP_200_OK, "","Email, First name and Last name required"
                return Response(data)
            if check_user_ad.exists():
                data["status"], data['data'], data["message"] = status.HTTP_200_OK, "","User already exist"
                return Response(data)
            obj = GenerateKey()
            obj2 = GenerateKey()
            generated_otp = obj2.generated_otp()
            secret_key = obj.gen_user_key()
            password = str(generated_otp)[:6]
            raw_password = password
            hash_password = make_password(password)
            role_id = Role.objects.filter(role='User').first().id
            save_user = User(secret_key=secret_key,email=email,username=email,first_name=first_name,last_name=last_name,is_team_manager=True,
                                     role_id=role_id,password=hash_password,password_raw=raw_password,generated_otp=generated_otp,
                                     is_verified=True)
            save_user.save()
            data["status"], data['data'], data["message"] = status.HTTP_200_OK, "","User created successfully"
        else:
            data["status"], data['data'], data["message"] = status.HTTP_404_NOT_FOUND, "","HTTP_404_NOT_FOUND. User not found."
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


# @api_view(('GET',))
# def user_profile_view_api(request):
#     data = {'status':'', 'message':''}
#     try:
#         user_uuid = request.GET.get('user_uuid')
#         user_secret_key = request.GET.get('user_secret_key')
#         check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        
#         if check_user.exists():
#             get_user = check_user.first()
#             user_data = check_user.values('uuid','secret_key','username','first_name','last_name','phone','user_birthday','image','gender','street',
#                                           'city','state','postal_code','country','fb_link','twitter_link','youtube_link','tictok_link','instagram_link',
#                                           'is_admin','is_team_manager','is_player','is_coach','is_organizer','is_ambassador','is_sponsor')
            
#             # Convert phone number to string
#             user_data = list(user_data)
#             for user in user_data:
#                 user['phone'] = str(user['phone'])
            
#             data["status"], data['data'], data["message"] = status.HTTP_200_OK, {"user_data": user_data, "player_data":""}, "Data found"
            
#             if get_user.is_player:
#                 player_rank = Player.objects.filter(player_id=get_user.id).first()
#                 data['data']["player_data"] = {"player_rank":player_rank.player_ranking,"player_rank_lock":player_rank.player_rank_lock}
#             else:
#                 data['data']["player_data"] = {"player_rank":get_user.rank,"player_rank_lock":False}
#         else:
#             data["status"], data['data'], data["message"] = status.HTTP_404_NOT_FOUND, "", "User not found"
#     except Exception as e:
#         data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    
#     # Serialize the data
#     # serialized_data = json.dumps(data, cls=DjangoJSONEncoder)
#     # print(data)
#     return Response(data, content_type='application/json')


#change
@api_view(('GET',))
def user_profile_view_api(request):
    data = {'status':'', 'data':"", 'message':'','is_sponsor':False, 'is_ambassador':False}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        #protocol = 'https' if request.is_secure() else 'http'
        host = request.get_host()
        # Construct the complete URL for media files
        media_base_url = f"{protocol}://{host}{settings.MEDIA_URL}"
        if check_user.exists():
            get_user = check_user.first()
            user_data = check_user.values('uuid','secret_key','username','first_name','last_name','phone','user_birthday','image','gender','street',
                                          'city','state','postal_code','country','fb_link','twitter_link','youtube_link','tictok_link','instagram_link',
                                          'is_admin','is_team_manager','is_player','is_coach','is_organizer','is_ambassador','is_sponsor', 'latitude', 'longitude')
            
            user_rank = get_user.rank
            if user_rank == "null" or user_rank == "" or  not user_rank:
                user_rank = 1
            else:
                user_rank = float(user_rank)

            if get_user.is_ambassador == True:
                data["is_ambassador"] = True
            if get_user.is_sponsor == True:
                data["is_sponsor"] = True
            # Convert phone number to string
            user_data = list(user_data)
            for user in user_data:
                user['phone'] = str(user['phone'])
                for key, value in user.items():
                    # If the value is an empty string or "null", set it to None
                    if value == "" or value == "null":
                        user[key] = None

                if user.get('latitude') and user.get('longitude'):
                    try:
                        location = get_location_from_coordinates(
                            user['latitude'], user['longitude']
                        )
                        user['location'] = location
                    except Exception as e:
                        user['location'] = None
                else:
                    user['location'] = None
            data["status"], data['data'], data["message"] = status.HTTP_200_OK, {"user_data": user_data, "player_data":""}, "Data found"
            counter = 0
            if get_user.is_player and counter == 0:
                # print("hit")
                # player_rank = Player.objects.filter(player_id=get_user.id)
                # if player_rank.exists():
                #     player_rank=player_rank.first()
                #     data['data']["player_data"] = {"player_rank":player_rank.player.rank,"player_rank_lock":player_rank.player_rank_lock}
                # else:
                data['data']["player_data"] = {"player_rank":user_rank,"player_rank_lock":False}
                    
                foll__ = AmbassadorsDetails.objects.filter(ambassador_id=get_user.id)
                
                if not foll__.exists():
                    foll__ = AmbassadorsDetails.objects.create(ambassador_id=get_user.id)
                    data['data']["followers"] = {"followers":0,"following":0}
                # print(foll_.values(), get_user.id)
                else:
                    data['data']["followers"] = {"followers":foll__.first().follower.count(),"following":foll__.first().following.count()}
                data['data']["post"] = []
                data['data']["ads_data"] = []
            
            if get_user.is_ambassador and counter == 0:
                counter += 1
                # player_rank = Player.objects.filter(player_id=get_user.id)
                # if player_rank.exists():
                #     player_rank=player_rank.first()
                #     data['data']["player_data"] = {"player_rank":player_rank.player_ranking,"player_rank_lock":player_rank.player_rank_lock}
                # else:
                data['data']["player_data"] = {"player_rank":user_rank,"player_rank_lock":False}
                # foll_ = AmbassadorsDetails.objects.all()
                foll__ = AmbassadorsDetails.objects.filter(ambassador_id=get_user.id)
                
                if not foll__.exists():
                    foll__ = AmbassadorsDetails.objects.create(ambassador_id=get_user.id)
                    data['data']["followers"] = {"followers":0,"following":0}
                # print(foll_.values(), get_user.id)
                else:
                    data['data']["followers"] = {"followers":foll__.first().follower.count(),"following":foll__.first().following.count()}
                
                post_data = AmbassadorsPost.objects.filter(created_by=get_user).values()
                print(post_data)
                for i in post_data:
                    i["file"] = i["file"]
                data['data']["post"] = list(post_data)
                data['data']["ads_data"] = []
                # return Response(data, content_type='application/json')
            if get_user.is_sponsor and counter == 0:
                counter += 1
                # print(Advertisement.objects.filter(created_by=get_user).values())
                data['data']["followers"] = {"followers":0,"following":0}
                data['data']["post"] = []
                data['data']["ads_data"] = list(Advertisement.objects.filter(created_by=get_user).values())
                # return Response(data, content_type='application/json')
            if counter == 0:
                print("elase")
                data['data']["ads_data"]=[]
                data['data']["post"]=[]
                data['data']["player_data"] = {"player_rank":user_rank,"player_rank_lock":False}
                # return Response(data, content_type='application/json')
        else:
            data["status"], data['data'], data["message"] = status.HTTP_404_NOT_FOUND, "", "User not found"
    except Exception as e:
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data, content_type='application/json')


@api_view(('GET',))
def user_profile_view_using_pagination(request):
    data = {'status':'', 'data':"", 'message':'','is_sponsor':False, 'is_ambassador':False}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        #protocol = 'https' if request.is_secure() else 'http'
        host = request.get_host()
        # Construct the complete URL for media files
        media_base_url = f"{protocol}://{host}{settings.MEDIA_URL}"
        if check_user.exists():
            get_user = check_user.first()
            user_data = check_user.values('uuid','secret_key','username','first_name','last_name','phone','user_birthday','image','gender','street',
                                          'city','state','postal_code','country','fb_link','twitter_link','youtube_link','tictok_link','instagram_link',
                                          'is_admin','is_team_manager','is_player','is_coach','is_organizer','is_ambassador','is_sponsor', 'latitude', 
                                          'longitude', 'permanent_location', 'current_location')
            
            user_rank = get_user.rank
            if user_rank == "null" or user_rank == "" or  not user_rank:
                user_rank = 1
            else:
                user_rank = float(user_rank)

            if get_user.is_ambassador == True:
                data["is_ambassador"] = True
            if get_user.is_sponsor == True:
                data["is_sponsor"] = True
            # Convert phone number to string
            user_data = list(user_data)
            for user in user_data:
                user['phone'] = str(user['phone'])
                for key, value in user.items():
                    # If the value is an empty string or "null", set it to None
                    if value == "" or value == "null":
                        user[key] = None

                if user.get('latitude') and user.get('longitude'):
                    try:
                        location = get_location_from_coordinates(
                            user['latitude'], user['longitude']
                        )
                        user['location'] = location
                    except Exception as e:
                        user['location'] = None
                else:
                    user['location'] = None
            data["status"], data['data'], data["message"] = status.HTTP_200_OK, {"user_data": user_data, "player_data":""}, "Data found"
            counter = 0
            if get_user.is_player and counter == 0:
                # print("hit")
                # player_rank = Player.objects.filter(player_id=get_user.id)
                # if player_rank.exists():
                #     player_rank=player_rank.first()
                #     data['data']["player_data"] = {"player_rank":player_rank.player.rank,"player_rank_lock":player_rank.player_rank_lock}
                # else:
                data['data']["player_data"] = {"player_rank":user_rank,"player_rank_lock":False}
                    
                foll__ = AmbassadorsDetails.objects.filter(ambassador_id=get_user.id)
                
                if not foll__.exists():
                    foll__ = AmbassadorsDetails.objects.create(ambassador_id=get_user.id)
                    data['data']["followers"] = {"followers":0,"following":0}
                # print(foll_.values(), get_user.id)
                else:
                    data['data']["followers"] = {"followers":foll__.first().follower.count(),"following":foll__.first().following.count()}
                data['data']["post"] = []
                data['data']["ads_data"] = []
            
            if get_user.is_ambassador and counter == 0:
                # counter += 1
                # player_rank = Player.objects.filter(player_id=get_user.id)
                # if player_rank.exists():
                #     player_rank=player_rank.first()
                #     data['data']["player_data"] = {"player_rank":player_rank.player_ranking,"player_rank_lock":player_rank.player_rank_lock}
                # else:
                data['data']["player_data"] = {"player_rank":user_rank,"player_rank_lock":False}
                # foll_ = AmbassadorsDetails.objects.all()
                foll__ = AmbassadorsDetails.objects.filter(ambassador_id=get_user.id)
                
                if not foll__.exists():
                    foll__ = AmbassadorsDetails.objects.create(ambassador_id=get_user.id)
                    data['data']["followers"] = {"followers":0,"following":0}
                # print(foll_.values(), get_user.id)
                else:
                    data['data']["followers"] = {"followers":foll__.first().follower.count(),"following":foll__.first().following.count()}
                
                post_data = AmbassadorsPost.objects.filter(created_by=get_user).values("id","uuid","secret_key","file","thumbnail","post_text","approved_by_admin","created_at","created_by_id","likes")
                paginator = PageNumberPagination()
                paginator.page_size = 2  # Set the page size to 20
                posts = paginator.paginate_queryset(post_data, request)
                paginated_response = paginator.get_paginated_response(posts)
                for i in post_data:
                    i["file"] = i["file"]
                
                data['data']["post"] = paginated_response.data
                data['data']["ads_data"] = []
                return Response(data, content_type='application/json')
            if get_user.is_sponsor and counter == 0:
                counter += 1
                # print(Advertisement.objects.filter(created_by=get_user).values())
                ads_data = Advertisement.objects.filter(created_by=get_user).values()
                paginator = PageNumberPagination()
                paginator.page_size = 2  # Set the page size to 20
                ads = paginator.paginate_queryset(ads_data, request)
                paginated_response = paginator.get_paginated_response(ads)
                data['data']["followers"] = {"followers":0,"following":0}
                data['data']["post"] = []
                data['data']["ads_data"] = paginated_response.data
                return Response(data, content_type='application/json')
            if counter == 0:
                print("elase")
                data['data']["ads_data"]=[]
                data['data']["post"]=[]
                data['data']["player_data"] = {"player_rank":user_rank,"player_rank_lock":False}
                return Response(data, content_type='application/json')
        else:
            data["status"], data['data'], data["message"] = status.HTTP_404_NOT_FOUND, "", "User not found"
    except Exception as e:
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data, content_type='application/json')


@api_view(('POST',))
def user_profile_edit_api(request):
    data = {'status':'','message':''}
    try:        
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        first_name = request.data.get('first_name')
        last_name = request.data.get('last_name')
        user_birthday = request.data.get('user_birthday')
        image = request.data.get('image')
        gender = request.data.get('gender')
        permanent_location = request.data.get('permanent_location')
        latitude = request.data.get('latitude')
        longitude = request.data.get('longitude')
        current_location = request.data.get('current_location')        
        phone = request.data.get('phone')
        player_rank = request.data.get('player_rank')
        player_rank_lock = request.data.get('player_rank_lock')
        bio = request.data.get('bio')
        fb_link = request.data.get('fb_link')
        twitter_link = request.data.get('twitter_link')
        youtube_link = request.data.get('youtube_link')
        tictok_link = request.data.get('tictok_link')
        instagram_link = request.data.get('instagram_link')

        street, city, state, country, postal_code = get_detailed_address(permanent_location, settings.MAP_API_KEY)

        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        if check_user.exists():
            if user_birthday and user_birthday not in ["", "null", " ", None,'undefined'] :
                # mm/dd/yy
                user_birthday = datetime.strptime(user_birthday, '%m/%d/%Y').strftime('%Y-%m-%d')
            else:
                user_birthday = None

            get_user = check_user.first()
            get_user.first_name = first_name
            get_user.last_name = last_name
            get_user.user_birthday = user_birthday
            get_user.image = image
            get_user.gender = gender
            get_user.rank = player_rank
            get_user.bio = bio
            get_user.street = street
            get_user.city = city
            get_user.state = state
            get_user.postal_code = postal_code
            get_user.country = country
            get_user.latitude = latitude
            get_user.longitude = longitude
            get_user.permanent_location = permanent_location
            get_user.current_location = current_location

            check_delivery_address = ProductDeliveryAddress.objects.filter(created_by_id=get_user.id)
            if street and city and state and postal_code and country and not check_delivery_address.exists() :
                obj = GenerateKey()
                delivery_address_key = obj.gen_delivery_address_sk()
                complete_address = f'{street}, {city}, {state}, {country}, PIN-{postal_code}'
                save_delivery_address = ProductDeliveryAddress(secret_key=delivery_address_key,
                                        street=street,city=city,state=state,postal_code=postal_code,
                                        country=country,complete_address=complete_address,
                                        created_by_id=get_user.id)
                save_delivery_address.save()
            get_user.fb_link = fb_link
            get_user.twitter_link = twitter_link
            get_user.youtube_link = youtube_link
            get_user.tictok_link = tictok_link
            get_user.instagram_link = instagram_link
            get_user.phone = phone
            
            get_player = Player.objects.filter(player_email=get_user.email,player_phone_number=phone)
            if get_player.exists() and get_user.is_player:
                for i in range(len(get_player)) :
                    upadate_player = get_player[i]
                    upadate_player.player_image = image
                    upadate_player.player_first_name = first_name
                    upadate_player.player_last_name = last_name
                    player_full_name = f"{first_name} {last_name}"
                    upadate_player.player_full_name = player_full_name
                    
                    upadate_player.player_ranking = player_rank

                    if player_rank_lock == "True" :
                        upadate_player.player_rank_lock = True
                    
                    upadate_player.save()
            else:
                get_user.rank = player_rank
            get_user.save()
            data["status"], data['data'], data["message"] = status.HTTP_200_OK, "","Your profile edited successfully"
        else:
            data["status"], data['data'], data["message"] = status.HTTP_404_NOT_FOUND, "","User not found"
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


@api_view(('POST',))
def get_all_user(request):
    data = {'status':'','message':'','data':[]}
    try:        
        user_data = User.objects.all().order_by('-id').values()
        # print(user_data)
        data["status"], data['data'], data["message"] = status.HTTP_200_OK, list(user_data),"Your profile edited successfully"
    except Exception as e :
        data['status'],data['data'], data['message'] = status.HTTP_400_BAD_REQUEST,[], f"{e}"
    return Response(data)


@api_view(('POST',))
def delete_user_profile(request):
    data = {'status':'','message':''}
    try:        
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        if check_user.exists() :
            get_user = check_user.first()
            get_user.is_verified = False
            get_user.save()
            data["status"], data["message"] = status.HTTP_200_OK, "User profile deleted."
        else:
            data["status"], data["message"] = status.HTTP_404_NOT_FOUND,"User not found"
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


@api_view(('POST',))
def update_notification_status(request):
    data = {'status':'','message':''}
    try:        
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        notification_id = request.data.get('notification_id')
        
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key) 
        if check_user.exists():          
            if notification_id: 
                notification_id = json.loads(notification_id)        
                for k in notification_id:
                    check_notification = NotificationBox.objects.filter(id=int(k))
                    get_notification = check_notification.first()
                    if check_notification.exists() and get_notification.notify_for == check_user.first():
                        get_notification.is_read = True
                        get_notification.save()
                    else:
                        pass
            else:
                check_all_notification = NotificationBox.objects.filter(notify_for=check_user.first())
                for notification in check_all_notification:
                    notification.is_read = True
                    notification.save()
            data["status"], data["message"] = status.HTTP_200_OK, "Status updated successfully."                        

        else:
            data["status"], data["message"] = status.HTTP_404_NOT_FOUND,"User or notification not found or notification is not for user."
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


@api_view(("POST",))
def delete_all_notifications_for_user(request):
    data = {'status':'','message':''}
    try:        
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        notification_id_list = request.data.get('notification_id_list')
        notification_id_list = json.loads(notification_id_list)
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        if check_user.exists():
            
            deleted_count = 0
            for notification_id in notification_id_list:
                notification = NotificationBox.objects.filter(id=notification_id, notify_for=check_user.first()).first()
                if notification:
                    notification.delete()         
                    deleted_count += 1

            if deleted_count > 0:
                data["status"], data["message"] = status.HTTP_200_OK, f"Successfully deleted {deleted_count} notifications."
            else:
                data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "No notifications found to delete."        
        else:
            data["status"], data["message"] = status.HTTP_404_NOT_FOUND,"User not found."
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


@api_view(('POST',))
def app_update(request):
    data = {"status":"","message":""}
    try:
        user_uuid = request.data.get('user_uuid')
        update = request.data.get('update')
        check_user = User.objects.filter(uuid=user_uuid)
        # data["data"] = f"{update}{check_user.exists()}{update == "False"}"
        if update == "False" and check_user.exists():
            get_user = check_user.first()
            new_update = AppUpdate.objects.filter(update="True").first()
            new_update.updated_users.add(get_user)
            data["status"] = status.HTTP_200_OK
            data["message"] = "updated"
        else:
            data["status"] = status.HTTP_200_OK
            data["message"] = "App not updated"
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


@api_view(('GET',))
def get_update_responce(request):
    data = {"status":"","message":"","update":True}
    try:
        user_uuid = request.GET.get('user_uuid')
        check_user = User.objects.filter(uuid=user_uuid)
        if check_user.exists():
            get_user = check_user.first()
            new_update = AppUpdate.objects.filter(update="True").first()
            try:
                user_id_list = list(new_update.updated_users.all().values_list("id", flat=True))
            except:
                user_id_list = []
            if get_user.id in user_id_list:
                data["update"] = False
            else:
                data["update"] = True
            data["status"] = status.HTTP_200_OK
            data["message"] = "data found"
        else:
            data["status"] = status.HTTP_200_OK
            data["message"] = "data found"
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


@api_view(('POST',))
def post_user_show_screen(request):
    data = {"status": "", "message": ""}
    user_uuid = request.data.get('user_uuid')
    check_user = User.objects.filter(uuid=user_uuid)
    if check_user.exists():
        check_user.update(is_screen=True)
        data["status"] = status.HTTP_200_OK
        data["message"] = "Show screen updated"
    else:
        data["status"] = status.HTTP_400_BAD_REQUEST
        data["message"] = "User not found"
    return Response(data)


def calculate_rank(user):
    total_value = 0
    user_answers = UserAnswer.objects.filter(user=user)
    if user_answers.filter(question__is_last=True).exists():
        for user_answer in user_answers:
            try:            
                options = user_answer.question.options
                for option in options:
                    if option["option_name"] == user_answer.answer:
                        total_value += option['value']
            except (KeyError, IndexError, ValueError):
                pass
    return total_value


@api_view(('POST',))
def get_user_questions(request):
    data = {"status": "", "message": "", "data": [], "post_status": False}    
    user_uuid = request.data.get('user_uuid')
    que_id = request.data.get('que_id')
    ans = request.data.get('ans')    
    check_user = User.objects.filter(uuid=user_uuid)
    
    if check_user.exists():
        get_user = check_user.first()
        check_ans_question = UserAnswer.objects.filter(user=get_user)
        
        if check_ans_question.exists():
            # print(que_id, )
            if que_id and ans:
                
                check_questions = BasicQuestionsUser.objects.filter(id=que_id)
                
                if check_questions.exists():
                    get_que = check_questions.first()
                    check_ans = UserAnswer.objects.filter(user=get_user, question=get_que)
                    
                    if check_ans.exists():
                        check_ans.update(answer=ans)
                    else:
                        UserAnswer.objects.create(user=get_user, question=get_que, answer=ans)
                    
                    # Next question found
                    if get_que.question_for == "Beginner":
                        next_questions = list(BasicQuestionsUser.objects.filter(parent=get_que, when_ans=ans).values())
                    else:
                        next_questions = list(BasicQuestionsUser.objects.filter(parent=get_que).values())
                    data["status"] = status.HTTP_200_OK
                    data["data"] = next_questions
                    data["message"] = "Your answer is submitted"
                    data["post_status"] = True
                    if len(next_questions) == 0:
                        total_value = calculate_rank(get_user)
                        if total_value != 0:
                            get_user.is_rank=True
                            get_user.save()
                        data["rank"] = total_value
                else:
                    data["status"] = status.HTTP_400_BAD_REQUEST
                    data["message"] = "Question not found"
            else:
                last_question = check_ans_question.last().question
                if last_question.question_for == "All":
                    next_questions = list(BasicQuestionsUser.objects.filter(parent=last_question,when_ans=check_ans_question.last().answer).values())
                else:
                    next_questions = list(BasicQuestionsUser.objects.filter(parent=last_question).values())
                
                data["status"] = status.HTTP_200_OK
                data["data"] = next_questions
                data["message"] = ""
                # data["post_status"] = True
                if len(next_questions) == 0:
                    total_value = calculate_rank(get_user)
                    if total_value != 0:
                        get_user.is_rank=True
                        get_user.save()
                    data["rank"] = total_value
        elif not check_ans_question.exists() and que_id and ans:
            
            check_questions = BasicQuestionsUser.objects.filter(id=que_id)
            if check_questions.exists():
                get_que = check_questions.first()
                check_ans = UserAnswer.objects.filter(user=get_user, question=get_que)
                
                if check_ans.exists():
                    check_ans.update(answer=ans)
                else:
                    UserAnswer.objects.create(user=get_user, question=get_que, answer=ans)
                
                # Next question found
                next_questions = list(BasicQuestionsUser.objects.filter(parent=get_que, when_ans=ans).values())
                data["status"] = status.HTTP_200_OK
                data["data"] = next_questions
                data["message"] = "Your answer is submitted"
                # data["post_status"] = True
            else:
                data["status"] = status.HTTP_400_BAD_REQUEST
                data["message"] = "Question not found"
        else:
            next_questions = list(BasicQuestionsUser.objects.filter(question_for="All").values())
            data["status"] = status.HTTP_200_OK
            data["data"] = next_questions
            data["message"] = ""
    else:
        data["status"] = status.HTTP_400_BAD_REQUEST
        data["message"] = "User not found"
        
    return Response(data)


@api_view(('POST',))
def update_rank(request):
    data = {"status": "", "message": ""} 
    try:        
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        rank = request.data.get('rank')
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if check_user.exists():
            get_user = check_user.first()
            check_user.update(rank=rank, is_rank=True)
            check_player = Player.objects.filter(player_email=get_user.email)
            if check_player.exists():
                check_player.update(player_ranking=rank)
                notify_message = f"Hey player! Your rank has been updated."
                titel = f"Rank update notification."
                notify_edited_player(check_player.first().player.id, titel, notify_message)
                data["status"], data["message"] = status.HTTP_200_OK, "Rank updated successfully."
            else:
                data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "Player not found."
        else:
            data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "User not found."
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


@api_view(('POST',))
def delete_self_ranking_answers_per_user(request):
    data = {"status": "", "message": ""} 
    try:        
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if check_user.exists():
            get_user_id = check_user.first().id
            user_answers = UserAnswer.objects.filter(user__id=get_user_id)
            if user_answers.exists():
                user_answers.delete()
                check_user.update(is_rank=False)                
                data["status"], data["message"] = status.HTTP_200_OK, f"All answers of this user are deleted successfully."
            else:
                data["status"], data["message"] = status.HTTP_404_NOT_FOUND, f"No answer found for this user."
        else:
            data["status"], data["message"] = status.HTTP_404_NOT_FOUND, f"User not found."
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


def render_to_pdf(template_src, context_dict, league_name):
    template = get_template(template_src)
    html = template.render(context_dict)
    css = """
        <style>
            td {
                
                word-wrap: break-word;
            }
            .p-tag{
                margin:0;
            }
        </style>
    """
    html_with_css = f"{css}{html}"
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="pickleball_{league_name}.pdf"'

    # create a PDF
    pisa_status = pisa.CreatePDF(
        html, dest=response, encoding='utf-8')

    if pisa_status.err:
        return HttpResponse('We had some errors <pre>' + html + '</pre>')
    return response


def insert_line_breaks(text, chars_per_line):
    return '\n'.join(text[i:i+chars_per_line] for i in range(0, len(text), chars_per_line))


@api_view(('GET',))
def show_pdf(request, leaug_uuid, user_uuid):
    league_details_for_all = Leagues.objects.filter(uuid=leaug_uuid).first()
    all_team = league_details_for_all.registered_team.all().values()
    total_player = 0
    context={
        "league_name": league_details_for_all.name,
        "start_date": league_details_for_all.leagues_start_date,
        "end_date": league_details_for_all.leagues_end_date,
        "location": league_details_for_all.location,
        "data" : []
        }  
    league_ids = list(Leagues.objects.filter(name=league_details_for_all.name).values_list("id", flat=True))
    t_data = []
    for league_ in league_ids:
        league_details = Leagues.objects.filter(id=league_).first()
        if league_details is not None:
            all_team = league_details.registered_team.all().values() if league_details.registered_team.exists() else []
        else:
            all_team = []

        total_player = 0
        player_list = []
        for team in list(all_team):
            team["players"] = list(Player.objects.filter(team__id=team["id"]).values("player__first_name","player__last_name","player__email","player__phone","player__city","player__state","player__country","player__rank","player__gender"))
            for player in team["players"]:
                player_details = {}
                # Modify fields to enforce line breaks after 10 characters
                player_details["player__first_name"] = insert_line_breaks(str(player["player__first_name"]), 10)
                player_details["player__last_name"] = insert_line_breaks(str(player["player__last_name"]), 10)
                if player["player__rank"] == "null" or player["player__rank"] == "" or not player["player__rank"]:
                    player_details["player__rank"] = 1
                else:
                    player_details["player__rank"] = float(player["player__rank"])
                
                player_details["player__gender"] = player["player__gender"]
                player_details["player__phone"] = player["player__phone"]
                player_details["player__email"] = insert_line_breaks(str(player["player__email"]), 22)
                player_details["team_name"] = insert_line_breaks(str(team["name"]), 10)
                full_address = ""
                city = player["player__city"] if player["player__city"] else ""
                state = player["player__state"] if player["player__state"] else ""
                country = player["player__country"] if player["player__country"] else ""

                # Concatenate city, state, and country to form the full address
                full_address = " ".join(filter(None, [city, state, country]))

                # If full_address is empty, set it to None
                if not full_address:
                    full_address = None
                else:
                    player_details["full_address"] = insert_line_breaks(full_address, 10)
                
                player_list.append(player_details)
            total_player = total_player + len(team["players"])

        player_list = sorted(player_list, key=lambda x: x['player__first_name'])

        tournamnet_data = {
            "team_type":league_details.team_type.name,
            "total_team": len(all_team),
            "total_player": total_player,
            "player_details": list(player_list)
        }
        t_data.append(tournamnet_data)
    context["data"] = t_data
    print(context)
    league_name = f"{league_details_for_all.name}_{league_details_for_all.team_type.name}"
    pdf = render_to_pdf('export/export_league.html', context, league_name)
    get_user = User.objects.filter(uuid=user_uuid).first()
    # Save PDF content to the database
    pdf_file = PDFFile(filename=f'pickleball_{league_name}.pdf', user=get_user,tournament=league_details_for_all.id)
    pdf_file.file.save(pdf_file.filename, ContentFile(pdf.content))
    pdf_file.save()

    # Generate a link to access the stored PDF file
    pdf_link = request.build_absolute_uri(pdf_file.file.url)

    return Response({"pdf_link":pdf_link, "status":"200"})
     

@api_view(('POST',))
def update_rank(request):
    data = {"status": "", "message": ""} 
    try:        
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        rank = request.data.get('rank')
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if check_user.exists():
            get_user = check_user.first()
            check_user.update(rank=rank)
            check_player = Player.objects.filter(player_email=get_user.email)
            if check_player.exists():
                check_player.update(player_ranking=rank)
                notify_message = f"Hey player! Your rank has been updated."
                titel = f"Rank update notification."
                notify_edited_player(check_player.first().player.id, titel, notify_message)
                data["status"], data["message"] = status.HTTP_200_OK, "Rank updated successfully."
            else:
                data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "Player not found."
        else:
            data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "User not found."
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


@api_view(('POST',))
def add_matching_player(request):
    data = {}
    try:        
        user_uuid = request.data.get("user_uuid")
        user_secret_key = request.data.get("user_secret_key")
        # location = request.data.get("location")
        city = request.data.get("city")
        state = request.data.get("state")
        self_rank = request.data.get("self_rank")
        rank1_range = request.data.get("rank1_range")
        rank2_range = request.data.get("rank2_range")
        preference = request.data.get("preference")
        available_from = request.data.get("available_from")
        available_to = request.data.get("available_to")
        matching_image = request.FILES.get("matching_image")
        if available_from not in ["","null"," ",None] and available_to not in ["","null"," ",None]:
            available_from = datetime.strptime(available_from, '%m/%d/%Y').strftime('%Y-%m-%d')
            available_to = datetime.strptime(available_to, '%m/%d/%Y').strftime('%Y-%m-%d')
        else:
            available_from = None
            available_to = None
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if check_user.exists() and check_user.first().is_player:
            get_user = check_user.first()
            if city and state:
                location = f"{city},{state}"
            elif city:
                location = f"{city},"
            elif state:
                location = f",{state}"
            else:
                location = None
            api_key = settings.MAP_API_KEY
            check_matching_player = MatchingPlayers.objects.filter(player=get_user)
            if self_rank not in ["", "null", " ", None]:
                get_user.rank = self_rank
            # if city not in ["", "null", " ", None]:
            #     get_user.city = city
            # if state not in ["", "null", " ", None]:
            #     get_user.state = state
            if matching_image not in ["", "null", " ", None]:
                get_user.image = matching_image
            get_user.save()

            if not check_matching_player:
                matching_player_instance = MatchingPlayers(player=get_user,self_rank=self_rank, preference=preference,rank1_range=rank1_range, rank2_range=rank2_range,location=location, available_from=available_from, available_to=available_to, matching_image=matching_image)
                state, country, pincode, latitude, longitude = get_address_details(location, api_key)
                matching_player_instance.latitude = latitude
                matching_player_instance.longitude = longitude
                matching_player_instance.save()
                data["status"], data["message"] = status.HTTP_200_OK, f"Preferences for matching added successfully."
            else:
                check_matching_player.update(self_rank=self_rank, preference=preference,rank1_range=rank1_range, rank2_range=rank2_range,location=location, available_from=available_from, available_to=available_to, matching_image=matching_image)
                get_matching_player = check_matching_player.first()
                state, country, pincode, latitude, longitude = get_address_details(location, api_key)
                get_matching_player.latitude = latitude
                get_matching_player.longitude = longitude
                get_matching_player.save()
                data["status"], data["message"] = status.HTTP_200_OK, f"Preferences for matching updated successfully."
        else:
            data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "User not found or user is not player."
    except Exception as e:
        data['status'] = status.HTTP_400_BAD_REQUEST
        data['message'] = f"{e}"
    return Response(data)


@api_view(('GET',))
def view_matching_player(request):
    data = {}
    try:
        
        user_uuid = request.GET.get("user_uuid")
        user_secret_key = request.GET.get("user_secret_key")
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if check_user.exists():
            get_user = check_user.first()
            check_matching_player = MatchingPlayers.objects.filter(player=get_user)
            if get_user.rank in ["", "null", " ", None]:
                rank = None
            else:
                rank = get_user.rank
            if get_user.city in ["", "null", " ", None]:
                city = None
            else:
                city = get_user.city
            if get_user.state in ["", "null", " ", None]:
                state = None
            else:
                state = get_user.state
            if get_user.image in ["", "null", " ", None]:
                image = None
            else:
                image = get_user.image.url
            if check_matching_player.exists():
                get_matching_player = check_matching_player.first()
                location = get_matching_player.location
                city = location.split(",")[0]
                state = location.split(",")[1]
                if city in ["", "null", " ", None]:
                    city = get_user.city
                
                if state in ["", "null", " ", None]:
                    state = get_user.state
                data["result"]  = {
                    "user_id":get_user.id,
                    "user_uuid":get_user.uuid,
                    "user_secret_key":get_user.secret_key,
                    "id":get_matching_player.id,                                
                    
                    "preference":get_matching_player.preference,
                    "self_rank":rank,
                    "rank1_range":get_matching_player.rank1_range,
                    "rank2_range":get_matching_player.rank2_range,
                    "image": image,
                    # "location":get_matching_player.location,
                    "city": city,
                    "state":state
                    }
                if get_matching_player.available_from not in ["","null"," ",None] and get_matching_player.available_to not in ["","null"," ",None]:
                    available_from = get_matching_player.available_from
                    available_to = get_matching_player.available_to
                    data["result"]["available_from"] = available_from
                    data["result"]["available_to"] = available_to
                    data["result"]["any_time"] = False

                elif get_matching_player.available_from not in ["","null"," ",None]:
                    available_from = get_matching_player.available_from
                    data["result"]["available_from"] = available_from                    
                    data["result"]["any_time"] = False

                elif get_matching_player.available_to not in ["","null"," ",None]:
                    available_to = get_matching_player.available_to
                    data["result"]["available_to"] = available_to                    
                    data["result"]["any_time"] = False

                else:
                    data["result"]["available_to"] = None
                    data["result"]["available_to"] = None                   
                    data["result"]["any_time"] = True

                data["rank"] = rank 
                data["image"] = image
                data["status"] = status.HTTP_200_OK
                data["message"] = f"Details fetched successfully."

            else:
                data["result"]  = {
                        "user_id":get_user.id,
                        "user_uuid":get_user.uuid,
                        "user_secret_key":get_user.secret_key,
                        "id":None,                                
                        "available_from":None,
                        "available_to":None,
                        "any_time": True,
                        "preference":None,
                        "self_rank":rank,
                        "rank1_range":None,
                        "rank2_range":None,
                        "image": image,
                        # "location":get_matching_player.location,
                        "city": city,
                        "state":state
                    }
                data["rank"] = rank 
                data["image"] = image
                data["status"] = status.HTTP_200_OK
                data["message"] = f"Preferences for matching is not found."

        else:
            data["rank"] = 0
            data["image"] = None
            data['status'],data["result"], data["message"] = status.HTTP_404_NOT_FOUND, [], f"User not found."

    except Exception as e:
        data["rank"] = 0
        data["image"] = None
        data['status'] = status.HTTP_400_BAD_REQUEST
        data['message'] = f"{e}"
    return Response(data)


@api_view(('GET',))
def get_all_matching_players(request):
    data = {}
    try:        
        user_uuid = request.GET.get("user_uuid")
        check_user = User.objects.filter(uuid=user_uuid)
        if check_user.exists():
            get_user = check_user.first()
            check_matching_player = MatchingPlayers.objects.filter(player=get_user)
            if check_matching_player.exists():
                get_matching_player = check_matching_player.first()
                gender = get_user.gender
                preference = get_matching_player.preference
                rank_from = get_matching_player.rank1_range
                rank_to = get_matching_player.rank1_range
                available_from = get_matching_player.available_from
                available_to = get_matching_player.available_to
                avaialable_any_time = False
                if not available_from and not available_to:
                    avaialable_any_time = True
                if preference == "Singles" or preference == "Doubles":    
                    matching_players_details = Player.objects.filter(player__gender = gender)
                else:
                    matching_players_details = Player.objects.filter()
                location = get_matching_player.location
                if location:
                    location = get_matching_player.location.split(",")
                    state = location[1].strip()
                    city = location[0].strip()
                    print(state, city)
                    if not state in ["", "null"," ",None]:
                        matching_players_details = matching_players_details.filter(player__state=state)
                    if not city in ["", "null"," ", None]:
                        matching_players_details = matching_players_details.filter(player__city=city)
                matching_players_details = list(matching_players_details.filter(player__rank__lte=get_matching_player.rank2_range, player__rank__gte=get_matching_player.rank1_range).values("id","player__id","player__uuid","player__secret_key","player__first_name","player__last_name","player__gender","player__rank","player__image","player__city","player__state"))
                # ,"self_rank","available_from", "available_to","preference","matching_image"
                main_data = []
                check_player = Player.objects.filter(player_email= get_user.email)
                get_player = check_player.first()
                get_player_data = {"id":get_player.id,
                                   "player__id":get_player.player.id,
                                   "player__uuid": get_player.player.uuid,
                                   "player__secret_key": get_player.player.secret_key,
                                   "player__first_name": get_player.player.first_name,
                                   "player__last_name":get_player.player.last_name,
                                   "player__gender": get_player.player.gender,
                                   "player__rank":get_player.player.rank,
                                   "player__city":get_player.player.city,
                                   "player__state": get_player.player.state,
                                   "is_selected": True
                                   }
                if not get_player.player.image in ["","null"," ",None]:
                    get_player_data["player__image"] = get_player.player.image.url
                else:
                    get_player_data["player__image"] = None
                if available_from and available_to:
                    get_player_data["available_from"] = available_from
                    get_player_data["available_to"] = available_to
                    get_player_data["any_time"] = False

                else:
                    get_player_data["available_from"] = None
                    get_player_data["available_to"] = None
                    get_player_data["any_time"] = True

                get_player_data["preference"] = preference
                get_player_data["self_rank"] = get_user.rank

                if str(get_user.id) not in [str(player["player__id"]) for player in matching_players_details]:
                    main_data.append(get_player_data)

                for ply in matching_players_details:
                    user = ply["player__id"]

                    if user == get_user.id:
                        ply["is_selected"] = True
                    else:
                        ply["is_selected"] = False

                    check_match_details = MatchingPlayers.objects.filter(player_id = user)
                    user_instance = User.objects.filter(id=user).first()
                    if user_instance.image in ["", "null", " ", None]:
                        image = None
                        # get_match.player.image = None
                    else:
                        image = user_instance.image.url

                    if check_match_details.exists():
                        today_date = datetime.now().date()
                        get_match = check_match_details.first()
                        if avaialable_any_time:
                            if (not get_match.available_from and not get_match.available_to ):
                                ply["available_from"] = get_match.available_from
                                ply["available_to"] = get_match.available_to
                                ply["any_time"] = True
                                ply["preference"] = get_match.preference
                                ply["player__image"] = image
                                ply["self_rank"] = ply["player__rank"]
                                main_data.append(ply) 

                            elif (get_match.available_from <= today_date <= get_match.available_to):
                                ply["available_from"] = get_match.available_from
                                ply["available_to"] = get_match.available_to
                                ply["any_time"] = True
                                ply["preference"] = get_match.preference
                                ply["player__image"] = image
                                ply["self_rank"] = ply["player__rank"]
                                main_data.append(ply)
                            else:
                                pass 

                        elif (not get_match.available_from and not get_match.available_to ) and not avaialable_any_time:                            
                            ply["available_from"] = get_match.available_from
                            ply["available_to"] = get_match.available_to
                            ply["any_time"] = True
                            ply["preference"] = get_match.preference
                            ply["player__image"] = image
                            ply["self_rank"] = ply["player__rank"]
                            main_data.append(ply) 

                        elif (get_match.available_from <= available_from and get_match.available_to >= available_to) and not avaialable_any_time:
                            ply["available_from"] = get_match.available_from
                            ply["available_to"] = get_match.available_to
                            ply["any_time"] = False
                            ply["preference"] = get_match.preference
                            ply["player__image"] = image
                            ply["self_rank"] = ply["player__rank"]
                            main_data.append(ply)
                        else:
                            pass
                    else:
                        ply["available_from"] = None
                        ply["available_to"] = None
                        ply["any_time"] = True
                        ply["preference"] = None
                        ply["player__image"] = image
                        ply["self_rank"] = ply["player__rank"]
                        main_data.append(ply)

                main_data = sorted(main_data, key=lambda x: x["is_selected"], reverse=True)
                data["matching_player_details"] = main_data
                data["self_details"] = list(check_matching_player.values())
                data["status"] = status.HTTP_200_OK
                data["message"] = f"All matching players fetched successfully." 

            else:
                data["matching_player_details"] = []
                data["status"] = status.HTTP_404_NOT_FOUND
                data["rank"] = get_user.rank
                data["message"] = f"Please add your prefernces first."
                
        else:
            data["status"] = status.HTTP_404_NOT_FOUND
            data["message"] = f"User not found."   

    except Exception as e:
        data['status'] = status.HTTP_400_BAD_REQUEST
        data['message'] = f"{e}"
    return Response(data)


@api_view(('POST',))
def create_teams_and_open_play(request):
    data = {}
    try:        
        user_uuid = request.data.get("user_uuid")
        user_secret_key = request.data.get("user_secret_key")
        team1_player_id_list = json.loads(request.data.get("team1_player_id_list", "[]"))
        team2_player_id_list = json.loads(request.data.get("team2_player_id_list", "[]"))
        leagues_start_date = None
        max_number_team = 2
        registration_fee = 0
        description = "None"
        league_type = "Open to all"
        team_type = "Open-team"
        play_type = "Individual Match Play"

        # leagues_start_date = datetime.strptime(leagues_start_date, '%m/%d/%Y').strftime('%Y-%m-%d')
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key, is_player=True)

        if check_user.exists():
            get_user = check_user.first()

            if not (len(team1_player_id_list) in [1, 2]) or len(team1_player_id_list) != len(team2_player_id_list):
                return Response({"status": status.HTTP_400_BAD_REQUEST, "message": "Please select one or two player teams and ensure both teams have equal players."})

            teams = []
            for team_player_id_list in [team1_player_id_list, team2_player_id_list]:
                if len(team_player_id_list) == 1:
                    team_person = "One Person Team"
                    three_digit_code = random.randint(0, 999)
                    user = User.objects.filter(id=team_player_id_list[0]).first()
                    team_name = f"{user.first_name}_{three_digit_code}"
                else:
                    team_person = "Two Person Team" 
                    three_digit_code = random.randint(0, 999)
                    user_1 = User.objects.filter(id=team_player_id_list[0]).first()
                    user_2 = User.objects.filter(id=team_player_id_list[1]).first()
                    user_1_first_name = user_1.first_name
                    user_2_first_name = user_2.first_name
                    team_name = f"{user_1_first_name[0]}{user_2_first_name[0]}_{three_digit_code}" 

                obj = GenerateKey()
                team_secret_key = obj.gen_team_key() 
                matching_image = MatchingPlayers.objects.filter(player=get_user).first().matching_image
                team_image = None
                location = MatchingPlayers.objects.filter(player=get_user).first().location
                team_location = location if location else None
                team = Team.objects.create(secret_key=team_secret_key, name=team_name, location=team_location, team_person=team_person, team_type=team_type, team_image=team_image, created_by=get_user)
                teams.append(team)

                for id in team_player_id_list:
                    user = User.objects.filter(id=id).first()
                    player = Player.objects.filter(player_email=user.email).first()
                    if player:
                        player.team.add(team)

            tournament_name = f"{teams[0].name} VS {teams[1].name}"
            obj3 = GenerateKey()
            secret_key = obj3.gen_leagues_key()
            check_leagues = LeaguesTeamType.objects.filter(name=team_type)
            check_person = LeaguesPesrsonType.objects.filter(name=team_person)

            save_leagues = Leagues(
                secret_key=secret_key,
                name=tournament_name,
                leagues_start_date=leagues_start_date,
                created_by=get_user,
                postal_code="",
                country="",
                max_number_team=max_number_team,
                play_type=play_type,
                registration_fee=registration_fee,
                description=description,
                league_type=league_type,
                is_created = False,
            )
            save_leagues.save()
            if check_leagues.exists() and check_person.exists():
                check_leagues_id = check_leagues.first().id
                check_person_id = check_person.first().id
                save_leagues.team_type_id = check_leagues_id
                save_leagues.team_person_id = check_person_id
                save_leagues.save()

            for team in teams:
                save_leagues.registered_team.add(team)

            play_type_data = [{"name": "Round Robin", "number_of_courts": 0, "sets": 0, "point": 0},
                              {"name": "Elimination", "number_of_courts": 0, "sets": 0, "point": 0},
                              {"name": "Final", "number_of_courts": 0, "sets": 0, "point": 0}]
            for j in play_type_data:
                j["is_show"] = play_type == "Individual Match Play"

            LeaguesPlayType.objects.create(type_name=save_leagues.play_type, league_for=save_leagues,
                                           data=play_type_data)

            titel = "Open play created."
            for team in teams:
                notify_message = f"Hey player! Your team {team.name} has been added for an open play - {tournament_name}"
                team_players = Player.objects.filter(team=team)
                for player in team_players:
                    notify_edited_player(player.player.id, titel, notify_message)
            open_play_id = save_leagues.id
            return Response({"status": status.HTTP_200_OK, "message": "Teams and tournament created successfully.", "open_play_id": open_play_id})
        else:
            return Response({"status": status.HTTP_404_NOT_FOUND, "message": "User not found.", "open_play_id": None})

    except Exception as e:
        return Response({"status": status.HTTP_400_BAD_REQUEST, "message": str(e), "open_play_id": None})


@api_view(('GET',))
def get_open_play_details(request):
    data = {}
    try:        
        user_uuid = request.GET.get("user_uuid")
        user_secret_key = request.GET.get("user_secret_key")
        tournament_id = request.GET.get("tournament_id")

        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key, is_player=True)
        tournament = Leagues.objects.filter(id=int(tournament_id))
        
        if check_user.exists() and tournament.exists():
            get_tour = tournament.first()
            register_teams = get_tour.registered_team.all().values("id","name","team_person","team_image","team_type")
            
            tournament_details = tournament.values().first()
            register_teams = list(register_teams)
            team_1 = register_teams[0]
            team_2 = register_teams[1]
            team1_players = []
            team_1_players = Player.objects.filter(team__id=team_1["id"])
            for player in team_1_players:
                player_name = f"{player.player.first_name} {player.player.last_name}"
                team1_players.append(player_name)
            team2_players = []
            team_2_players = Player.objects.filter(team__id=team_2["id"])
            for player in team_2_players:
                player_name = f"{player.player.first_name} {player.player.last_name}"
                team2_players.append(player_name)
            tournament_details["registered_teams"] = register_teams
            tournament_details["team_1_players"] = team1_players
            tournament_details["team_2_players"] = team2_players
            data["status"] = status.HTTP_200_OK
            data["message"] = "Data found."
            data["tournament_details"] = tournament_details
        elif not check_user.exists():
            data["status"] = status.HTTP_404_NOT_FOUND
            data["message"] = "User not found."
            data["tournament_details"] = {}
        else:
            data["status"] = status.HTTP_404_NOT_FOUND
            data["message"] = "Tournament not found."
            data["tournament_details"] = {}
    except Exception as e:
        data['status'] = status.HTTP_400_BAD_REQUEST
        data['message'] = str(e)
        data["tournament_details"] = {}
    return Response(data)


@api_view(('POST',))
def edit_open_play_tournament(request):
    data = {}
    try:        
        user_uuid = request.data.get("user_uuid")
        user_secret_key = request.data.get("user_secret_key")
        tournament_id = request.data.get("tournament_id")
        location = request.data.get('location')
        leagues_start_date = request.data.get("open_play_date")
        court = request.data.get('court')
        sets = request.data.get('sets')
        points = request.data.get('points')
        leagues_start_date = datetime.strptime(leagues_start_date, '%m/%d/%Y').strftime('%Y-%m-%d')
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key, is_player=True)
        tournament = Leagues.objects.filter(id=int(tournament_id))
        
        if not court or not sets or not points:
            data["status"] = status.HTTP_400_BAD_REQUEST
            data["message"] = "Courts/Sets/Points must be provided."
        elif check_user.exists() and tournament.exists():
            get_tour = tournament.first()
            get_tour.location = location
            get_tour.leagues_start_date = leagues_start_date
            full_address = location
            api_key = settings.MAP_API_KEY
            state, country, pincode, latitude, longitude = get_address_details(full_address, api_key)
            if latitude is None:
                latitude = 38.908683
            if longitude is None:
                longitude = -76.937352
            get_tour.state = state
            get_tour.country = country
            get_tour.postal_code = pincode
            get_tour.latitude = latitude
            get_tour.longitude = longitude
            

            get_play_details = LeaguesPlayType.objects.filter(league_for=get_tour).first()
            play_details = get_play_details.data
            play_details[2]["number_of_courts"] = court
            play_details[2]["sets"] = sets
            play_details[2]["point"] = points
            get_play_details.data = play_details
            get_play_details.save()
            get_tour.is_created = True
            get_tour.save()
            data["status"] = status.HTTP_200_OK
            data["message"] = f"{get_tour.name} updated successfully."
        elif not check_user.exists():
            data["status"] = status.HTTP_404_NOT_FOUND
            data["message"] = "User not found."
        else:
            data["status"] = status.HTTP_404_NOT_FOUND
            data["message"] = "Tournament not found."
    except Exception as e:
        data['status'] = status.HTTP_400_BAD_REQUEST
        data['message'] = str(e)
    return Response(data)


@api_view(("POST",))
def fcm_token_store(request):
    data = {"status":"", "message":"", "data":[]}
    try:        
        user_uuid = request.data.get("user_uuid")
        user_secret_key = request.data.get("user_secret_key")
        fcm_token = request.data.get("fcm_token")
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if check_user.exists():
            get_user = check_user.first()
            check_token = FCMTokenStore.objects.filter(user=get_user)
            if check_token.exists():
                get_token = check_token.first()
                token_list = get_token.fcm_token["fcm_token"]
                if str(fcm_token) not in token_list:
                    token_list.append(str(fcm_token))
                get_token.save()
            else:
                get_token = FCMTokenStore.objects.create(user=get_user,fcm_token={"fcm_token":[fcm_token]})
            data["status"] = status.HTTP_200_OK
            data["message"] = "FCM Token saved successfully."
        else:
            data["status"] = status.HTTP_404_NOT_FOUND
            data["message"] = "User not found."

    except Exception as e:
        data['status'] = status.HTTP_400_BAD_REQUEST
        data['message'] = str(e)
    return Response(data)


@api_view(("POST",))
def delete_fcm_token_at_logout(request):
    data = {"status":"", "message":"", "data":[]}
    try:        
        user_uuid = request.data.get("user_uuid")
        user_secret_key = request.data.get("user_secret_key")
        fcm_token = request.data.get("fcm_token")
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if check_user.exists():
            get_user = check_user.first()
            check_token = FCMTokenStore.objects.filter(user=get_user)
            if check_token.exists():
                get_token = check_token.first()
                get_token_list = get_token.fcm_token["fcm_token"]
                if str(fcm_token) in get_token_list:
                    get_token_list.remove(str(fcm_token))
                get_token.save()
                data["status"] = status.HTTP_200_OK
                data["message"] = "FCM Token deleted successfully."
            else:
                data["status"] = status.HTTP_404_NOT_FOUND
                data["message"] = "FCm Token not found."
        else:
            data["status"] = status.HTTP_404_NOT_FOUND
            data["message"] = "User not found."
    except Exception as e:
        data['status'] = status.HTTP_400_BAD_REQUEST
        data['message'] = str(e)
    return Response(data)


@api_view(['POST',])
def edit_profile_(request):
    data = {"status":"", "message":""}
    try:        
        user_uuid = request.data.get("user_uuid")
        user_secret_key = request.data.get("user_secret_key")
        user_image = request.FILES.get("user_image")
        user_bio = request.data.get("user_bio")
        
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if check_user.exists():           
            user_instance = check_user.first()
            print(user_instance)
            if user_image is not None or user_bio is not None:
                if user_image is not None:
                    user_instance.image = user_image
                    user_instance.save()
                if user_bio is not None:
                    user_instance.bio = user_bio
                    user_instance.save() 
                data["status"] = status.HTTP_200_OK
                data["image"] = user_instance.image.url if user_instance.image else None
                data["bio"] = user_instance.bio
                data["message"] = "User profile image and bio updated successfully."
            else:                
                data["status"] = status.HTTP_200_OK
                data["image"] = user_instance.image.url if user_instance.image else None
                data["bio"] = user_instance.bio
                data["message"] = "User profile image and bio fetched successfully."
        else:
            data["status"] = status.HTTP_404_NOT_FOUND
            data["data"] = []
            data["message"] = "User not found"
    except Exception as e:
        data['status'] = status.HTTP_400_BAD_REQUEST
        data["data"] = []
        data['message'] = str(e)
    return Response(data)


@api_view(("GET",))
def check_update_status(request):
    data = {"status":"","message":"", "update":True}
    user_uuid = request.GET.get("user_uuid")
    user_secret_key = request.GET.get("user_secret_key")
    check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key) 
    if check_user:
        user_id = check_user.first().id
        latest_app_version = AppVersionUpdate.objects.latest('release_date')
        latest_version_user_list = list(latest_app_version.updated_users.all().values_list("id", flat=True))
        if int(user_id) in latest_version_user_list:
            data["update"] = False
        else:
            data["update"] = True
        data["status"] = status.HTTP_200_OK
        data["message"] = "Update status fetched successfully."
    else:
        data["status"] = status.HTTP_404_NOT_FOUND
        data["message"] = "User not found."
    return Response(data)


@api_view(('POST',))
def update_version(request):
    data = {"status":"","message":""}
    user_uuid = request.GET.get("user_uuid")
    user_secret_key = request.GET.get("user_secret_key")
    update_status = request.data.get("status")
    check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
    if check_user:
        get_user = check_user.first()
        if update_status == "True":
            latest_app_version = AppVersionUpdate.objects.latest('release_date')
            latest_app_version.updated_users.add(get_user)
        data["status"] = status.HTTP_200_OK
        data["message"] = "Version updated succesfully."
    else:
        data["status"] = status.HTTP_404_NOT_FOUND
        data["message"] = "User not found."
    return Response(data)


@api_view(('GET',))
def location_update_alert(request):
    data = {"status": "", "message": ""} 
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        
        latitude = request.GET.get('latitude')
        longitude = request.GET.get('longitude')
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)

        if not (user_uuid and user_secret_key and latitude and longitude):
            data["status"], data["message"] = status.HTTP_400_BAD_REQUEST, "Missing required parameters."
            return Response(data)

        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if not check_user.exists():
            data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "User not found."
            return Response(data)
        
        get_user = check_user.first()
        
        alert = False   
        
        if not get_user.is_sponsor:
            if get_user.current_location in [None, "null", "", " "]:
                alert = True  
            else:
                try:
                    previous_lat = float(get_user.latitude)
                    previous_long = float(get_user.longitude)
                    current_lat = float(latitude)
                    current_long = float(longitude)
                    
                    distance = haversine(previous_lat, previous_long, current_lat, current_long)
                    if distance > 100:
                        alert = True  
                except ValueError:
                    data["message"] = "Invalid latitude or longitude format."
                    return Response(data, status=status.HTTP_400_BAD_REQUEST)

        data["status"] = status.HTTP_200_OK
        data["message"] = "Location check completed."
        data["alert"] = alert

    except Exception as e:
        data["status"], data["message"] = status.HTTP_400_BAD_REQUEST, f"Error: {e}"

    return Response(data)


@api_view(('POST',))
def update_location(request):
    data = {"status": "", "message": ""} 
    try:        
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')        
        latitude = request.data.get('latitude')
        longitude = request.data.get('longitude')
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if check_user.exists():  
            current_location = get_location_from_coordinates(float(latitude), float(longitude))          
            check_user.update(current_location=current_location, latitude=latitude, longitude=longitude)          
                
            data["status"], data["message"] = status.HTTP_200_OK, "Location updated successfully."
        else:
            data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "User not found."
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


