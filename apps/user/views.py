import json
import random
import requests
from xhtml2pdf import pisa
from decimal import Decimal, ROUND_DOWN
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
import jwt, re, base64, uuid
from datetime import datetime, date, timedelta
from math import radians, sin, cos, sqrt, atan2
from django.shortcuts import render, HttpResponse
from django.contrib.auth import authenticate
from django.core.mail import send_mail
from django.contrib.sites.shortcuts import get_current_site
from django.contrib.auth.hashers import make_password
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.template.loader import get_template
from django.core.files.base import ContentFile
from django.db.models import Q
from apps.chat.models import *
from apps.clubs.models import Club
from apps.courts.models import Courts
from apps.team.models import *
from apps.user.helpers import GenerateKey
from apps.pickleitcollection.views import *
from apps.pickleitcollection.models import *
from apps.team.views import notify_edited_player, haversine
from apps.user.models import User, Role, PDFFile
from apps.user.serializers import *

from rest_framework.response import Response
from rest_framework import serializers, status
from rest_framework.decorators import api_view
from rest_framework.authtoken.models import Token
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

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
        api_key = settings.MAP_API_KEY  
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
    try :
        data = {'status':'','message':''}
        email = request.GET.get('email')
        check_email = User.objects.filter(username=email,email=email)
        # check_email2 = Player.objects.filter(player_email=email)

        if check_email.exists():
            get_user = check_email.first()
            if get_user.is_active:
                data['status'], data['message'] = status.HTTP_409_CONFLICT, f"Email already exists"
    
        else:
            data['status'], data['message'] = status.HTTP_200_OK, f"HTTP_200_OK"
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"

    return Response(data)

@api_view(('POST',))
def user_login_api(request):
    try:
        data = {'status': '', 'message': ''}
        email = request.data.get('email')
        password = request.data.get('password')

        if not email or not password:
            return Response({
                'status': status.HTTP_400_BAD_REQUEST,
                'message': 'Email and password are required.'
            })

        email = email.strip()
        password = password.strip()
        user = authenticate(username=email, password=password)

        if user is not None and user.is_superuser:
            data = {
                'status': status.HTTP_404_NOT_FOUND,
                'jwt': '',
                "message": "No user found with this credential",
            }

        elif user is not None and user.get_role() is not None and user.is_verified:
            # Corrected Secret Key Handling
            raw_secret_key = '6ju2av4vzs4tm5gq5tb4rrxcnj7ga5eqszafysmfw8hqh88uhtqctrm8bqgqudfy'  
            secret_key = base64.b64encode(raw_secret_key.encode()).decode()  # Ensure proper encoding

            expiration_time = datetime.utcnow() + timedelta(hours=1)
            check_player = Player.objects.filter(player_email=user.email, player_phone_number=user.phone)
            create_team_option = check_player.exists()

            full_name = f"{user.first_name} {user.last_name}"
            payload = {
                'user_id': str(user.uuid),
                'uuid': str(user.uuid),
                'secret_key': user.secret_key,
                "role": user.role.role,
                "email": user.email,
                "full_name": full_name,
                'timestamp': int(datetime.utcnow().timestamp()),
                'is_verified': user.is_verified,
                'create_team_option': create_team_option,
                'team_name': "",
                'team_created_by': "",
                'exp': int(expiration_time.timestamp()),  # Ensure correct expiration format
                'is_organizer': user.is_organizer,
                "self_ranking": user.is_rank,
            }

            algorithm = 'HS256'  # Keep it as HS256 unless the server expects a different one
            token = jwt.encode(payload, secret_key, algorithm=algorithm)
            refresh_token = jwt.encode({'uuid': str(user.uuid)}, secret_key, algorithm=algorithm)

            # Room Name Handling
            check_room = NotifiRoom.objects.filter(user=user)
            if check_room.exists():
                room_name = check_room.first().name
            else:
                room_name = f"user_{user.id}"
                room = NotifiRoom.objects.create(user=user, name=room_name)
                NotificationBox.objects.create(
                    room=room,
                    titel="Profile completion.",
                    text_message=f"Hi {user.username}, Welcome to PickleIT! Remember to fully update your profile.",
                    notify_for=user
                )

            data = {
                'status': status.HTTP_200_OK,
                'jwt': token,
                'refresh_token': refresh_token,
                'room_name': room_name,
                'is_show_screen': user.is_screen,
                "self_ranking": user.is_rank,
                'is_organizer': user.is_organizer,
                "message": "Successfully logged in",
            }

        elif user is not None and user.get_role() is not None and not user.is_verified:
            data = {
                'status': status.HTTP_401_UNAUTHORIZED,
                'jwt': '',
                'refresh_token': '',
                "message": "Please verify your email, a verification link is sent to your email",
            }

        else:
            check_user = User.objects.filter(username=email)
            if check_user.exists():
                data = {
                    'status': status.HTTP_404_NOT_FOUND,
                    'jwt': '',
                    "message": "Your password does not match our records",
                }
            else:
                data = {
                    'status': status.HTTP_404_NOT_FOUND,
                    'jwt': '',
                    "message": "No user found with these credentials",
                }

    except Exception as e:
        data = {
            'status': status.HTTP_400_BAD_REQUEST,
            'jwt': '',
            'message': f"Error: {str(e)}",  # Make error messages clear
        }

    return Response(data)



@api_view(('POST',))
def get_user_access_token(request):
    try :
        data = {'status':'','message':''}
        refresh_token = request.data.get('refresh_token')
        if refresh_token and refresh_token != "" :
            algorithm = 'HS384'
            secret_key_base64 = base64.b64encode('rngscpebarrr'.encode()).decode()
            decoded_token = jwt.decode(refresh_token, secret_key_base64, algorithms=[algorithm])
            user_uuid = decoded_token['uuid']
            user = User.objects.filter(uuid=user_uuid)
            if user.first():
                user=user.first()
                if user is not None and user.get_role() is not None and user.is_verified :
                    # secret_key_base64 = base64.b64encode(user.username.encode()).decode()
                    secret_key_base64 = base64.b64encode('rngscpebarrr'.encode()).decode()
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
            check_user = User.objects.filter(email=email,username=email)
            if password == confirm_password :
                if check_user.exists():
                    get_user = check_user.first()
                    if get_user.is_active:
                        data['status'], data['message'] = status.HTTP_409_CONFLICT, 'User already exists'
                    else:
                        get_user.first_name=first_name
                        get_user.last_name=last_name
                        get_user.latitude=latitude 
                        get_user.longitude=longitude 
                        get_user.current_location = current_location
                        get_user.password_raw = password
                        get_user.password = make_password(password)
                        get_user.save()
                        data['status'], data['message'] = status.HTTP_200_OK, 'User account created successfully'
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
                                            role_id=check_role.first().id,password=hash_password,password_raw=raw_password,generated_otp=generated_otp,
                                            gender=gender, is_player=True, latitude=latitude, longitude=longitude, current_location=current_location,
                                            permanent_location=current_location)
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
            is_active = get_user.is_active
            if not is_verified or is_active:
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
    try :
        data = {}
        context = {}
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
                get_user.is_active = True
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

#@1
@api_view(('POST',))
def forgot_password(request):
    data = {'status': '', 'message': ''}
    try:        
        email = request.data.get('email')
        check_email = User.objects.filter(email=str(email).strip())
        if check_email.exists():
            get_user = check_email.first()
            active = get_user.is_active
            if active:
                obj = GenerateKey()
                generate_password = str(obj.generated_otp())[:6]
                get_user = check_email.first()
                get_user.password = make_password(generate_password)
                get_user.password_raw =  generate_password
                get_user.save()
                data['status'], data['message'] = status.HTTP_200_OK, f"New password is send to {email}"
            else: 
                data['status'], data['message'] = status.HTTP_200_OK, f"{email} doesn't exists"
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


#@1
@api_view(('POST',))
def email_send_forgot_password(request):
    data = {'status': '', 'message': ''}
    try:        
        email = request.data.get('email')
        check_email = User.objects.filter(email=str(email).strip())
        if check_email.exists():
            get_user = check_email.first()
            if get_user.is_active:
                host = request.get_host()
                current_site = f"{protocol}://{host}"
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
                data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{get_user.email} doesn't exists"
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
    data = {'status': '', 'data': "", 'message': '', 'is_sponsor': False, 'is_ambassador': False}

    try:
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)

        host = request.get_host()
        # protocol = 'https' if request.is_secure() else 'http'
        # media_base_url = f"{protocol}://{host}{settings.MEDIA_URL}"

        if check_user.exists():
            get_user = check_user.first()
            user_data = check_user.values(
                'uuid', 'secret_key', 'username', 'first_name', 'last_name', 'phone', 'image',
                'is_admin', 'is_team_manager', 'is_player', 'is_coach', 'is_organizer', 'is_ambassador', 'is_sponsor',
                'latitude', 'longitude', 'permanent_location', 'current_location', 'gender','bio',
                'is_updated', 'user_birthday', 'availability'
            )

            user_rank = get_user.rank
            if not user_rank or user_rank in ["null", ""]:
                user_rank = 1
            else:
                user_rank = float(user_rank)

            if get_user.is_ambassador:
                data["is_ambassador"] = True
            if get_user.is_sponsor:
                data["is_sponsor"] = True

            user_data = list(user_data)
            for user in user_data:
                user['phone'] = str(user['phone'])
                for key, value in user.items():
                    if value == "" or value == "null":
                        user[key] = None

            data["status"] = status.HTTP_200_OK
            data["message"] = "Data found"
            data['data'] = {"user_data": user_data, "player_data": "", "followers": {"followers": 0, "following": 0}, "post": [], "ads_data": []}

            player_profile = Player.objects.filter(player=get_user).first()

            if player_profile:
                followers_count = player_profile.follower.count()
                following_count = player_profile.following.count()
                data['data']["followers"] = {"followers": followers_count, "following": following_count}

            # Shared player_data block
            data['data']["player_data"] = {"player_rank": user_rank, "player_rank_lock": False}

            if get_user.is_player:
                # For player only (player_data already added above)
                pass

            if get_user.is_ambassador:
                post_data = AmbassadorsPost.objects.filter(created_by=get_user).values()
                data['data']["post"] = list(post_data)

            if get_user.is_sponsor:
                ads_data = Advertisement.objects.filter(created_by=get_user).values()
                data['data']["ads_data"] = list(ads_data)

        else:
            data["status"] = status.HTTP_404_NOT_FOUND
            data['data'] = ""
            data["message"] = "User not found"

    except Exception as e:
        data['status'] = status.HTTP_400_BAD_REQUEST
        data['message'] = f"{e}"

    return Response(data, content_type='application/json')


# @api_view(('GET',))
# def user_profile_view_using_pagination(request):
#     data = {'status':'', 'data':"", 'message':'','is_sponsor':False, 'is_ambassador':False}
#     try:        
#         user_uuid = request.GET.get('user_uuid')
#         user_secret_key = request.GET.get('user_secret_key')
#         check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
#         #protocol = 'https' if request.is_secure() else 'http'
#         host = request.get_host()
#         # Construct the complete URL for media files
#         media_base_url = f"{protocol}://{host}{settings.MEDIA_URL}"
#         if check_user.exists():
#             get_user = check_user.first()
#             user_data = check_user.values('uuid','secret_key','username','first_name','last_name','phone','user_birthday','image','gender','street',
#                                           'city','state','postal_code','country','fb_link','twitter_link','youtube_link','tictok_link','instagram_link',
#                                           'is_admin','is_team_manager','is_player','is_coach','is_organizer','is_ambassador','is_sponsor', 'latitude',
#                                           'longitude', 'permanent_location', 'current_location')
            
#             wallet = getattr(get_user, 'wallet', None)
#             if wallet:
#                 wallet_id = wallet.id
#                 wallet_balance = wallet.balance
#                 wallet_created_at = wallet.created_at.strftime('%Y-%m-%d %H:%M:%S')
                
#             else:
#                 wallet_id = None
#                 wallet_balance = 0.0,
#                 wallet_created_at = None
            
            
            
#             user_rank = get_user.rank
#             if user_rank == "null" or user_rank == "" or  not user_rank:
#                 user_rank = 1
#             else:
#                 user_rank = float(user_rank)

#             if get_user.is_ambassador == True:
#                 data["is_ambassador"] = True
#             if get_user.is_sponsor == True:
#                 data["is_sponsor"] = True
#             # Convert phone number to string
#             user_data = list(user_data)
#             for user in user_data:
#                 user['phone'] = str(user['phone'])
#                 for key, value in user.items():
#                     # If the value is an empty string or "null", set it to None
#                     if value == "" or value == "null":
#                         user[key] = None

#                 user["wallet_id"] = wallet_id
#                 user['wallet_balance'] = wallet_balance
#                 user['wallet_created_at'] = wallet_created_at
            
#             data["status"], data['data'], data["message"] = status.HTTP_200_OK, {"user_data": user_data, "player_data":""}, "Data found"
#             counter = 0
#             if get_user.is_player and counter == 0:
#                 # print("hit")
#                 # player_rank = Player.objects.filter(player_id=get_user.id)
#                 # if player_rank.exists():
#                 #     player_rank=player_rank.first()
#                 #     data['data']["player_data"] = {"player_rank":player_rank.player.rank,"player_rank_lock":player_rank.player_rank_lock}
#                 # else:
#                 data['data']["player_data"] = {"player_rank":user_rank,"player_rank_lock":False}
                    
#                 foll__ = Player.objects.filter(player_email=get_user.email).first()
#                 data['data']["followers"] = {"followers":foll__.follower.count(),"following":foll__.following.count()}
#                 data['data']["post"] = []
#                 data['data']["ads_data"] = []
            
#             if get_user.is_ambassador and counter == 0:
#                 # counter += 1
#                 # player_rank = Player.objects.filter(player_id=get_user.id)
#                 # if player_rank.exists():
#                 #     player_rank=player_rank.first()
#                 #     data['data']["player_data"] = {"player_rank":player_rank.player_ranking,"player_rank_lock":player_rank.player_rank_lock}
#                 # else:
#                 data['data']["player_data"] = {"player_rank":user_rank,"player_rank_lock":False}
#                 # foll_ = AmbassadorsDetails.objects.all()
#                 foll__ = Player.objects.filter(player_email=get_user.email).first()
                
#                 if foll__:
#                     data['data']["followers"] = {"followers":foll__.follower.count(),"following":foll__.following.count()}
#                 else:
#                     data['data']["followers"] = {"followers":0, "following":0}
                
#                 post_data = AmbassadorsPost.objects.filter(created_by=get_user).values("id","uuid","secret_key","file","thumbnail","post_text","approved_by_admin","created_at","created_by_id","likes")
#                 paginator = PageNumberPagination()
#                 paginator.page_size = 2  # Set the page size to 20
#                 posts = paginator.paginate_queryset(post_data, request)
#                 paginated_response = paginator.get_paginated_response(posts)
#                 for i in post_data:
#                     i["file"] = i["file"]
                
#                 data['data']["post"] = paginated_response.data
#                 data['data']["ads_data"] = []
#                 return Response(data, content_type='application/json')
#             if get_user.is_sponsor and counter == 0:
#                 counter += 1
#                 # print(Advertisement.objects.filter(created_by=get_user).values())
#                 ads_data = Advertisement.objects.filter(created_by=get_user).values()
#                 paginator = PageNumberPagination()
#                 paginator.page_size = 2  # Set the page size to 20
#                 ads = paginator.paginate_queryset(ads_data, request)
#                 paginated_response = paginator.get_paginated_response(ads)
#                 foll__ = Player.objects.filter(player_email=get_user.email).first()
                
#                 if foll__:
#                     data['data']["followers"] = {"followers":foll__.follower.count(),"following":foll__.following.count()}
#                 else:
#                     data['data']["followers"] = {"followers":0, "following":0}
#                 data['data']["post"] = []
#                 data['data']["ads_data"] = paginated_response.data
#                 return Response(data, content_type='application/json')
#             if counter == 0:
#                 print("elase")
#                 data['data']["ads_data"]=[]
#                 data['data']["post"]=[]
#                 data['data']["player_data"] = {"player_rank":user_rank,"player_rank_lock":False}
#                 return Response(data, content_type='application/json')
#         else:
#             data["status"], data['data'], data["message"] = status.HTTP_404_NOT_FOUND, "", "User not found"
#     except Exception as e:
#         data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
#     return Response(data, content_type='application/json')

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
            
            wallet = getattr(get_user, 'wallet', None)
            if wallet:
                wallet_id = wallet.id
                wallet_balance = wallet.balance
                wallet_created_at = wallet.created_at.strftime('%Y-%m-%d %H:%M:%S')
                
            else:
                wallet_id = None
                wallet_balance = 0.0,
                wallet_created_at = None
            
            
            
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

                user["wallet_id"] = wallet_id
                user['wallet_balance'] = wallet_balance
                user['wallet_created_at'] = wallet_created_at
            
            data["status"], data['data'], data["message"] = status.HTTP_200_OK, {"user_data": user_data, "player_data":""}, "Data found"
                         
            data['data']["player_data"] = {"player_rank":user_rank,"player_rank_lock":False}
                
            foll__ = Player.objects.filter(player_email=get_user.email).first()
            
            if foll__:
                data['data']["followers"] = {"followers":foll__.follower.count(),"following":foll__.following.count()}
            else:
                data['data']["followers"] = {"followers":0, "following":0}
        
            
            post_data = AmbassadorsPost.objects.filter(created_by=get_user).values("id","uuid","secret_key","file","thumbnail","post_text","approved_by_admin","created_at","created_by_id","likes")
            paginator = PageNumberPagination()
            paginator.page_size = 2  # Set the page size to 20
            posts = paginator.paginate_queryset(post_data, request)
            paginated_response = paginator.get_paginated_response(posts)
            for i in post_data:
                i["file"] = i["file"]
            
            data['data']["post"] = paginated_response.data
            
            
            # print(Advertisement.objects.filter(created_by=get_user).values())
            ads_data = Advertisement.objects.filter(created_by=get_user).values()
            paginator = PageNumberPagination()
            paginator.page_size = 2  # Set the page size to 20
            ads = paginator.paginate_queryset(ads_data, request)
            paginated_response = paginator.get_paginated_response(ads)
            foll__ = Player.objects.filter(player_email=get_user.email).first()
            
            if foll__:
                data['data']["followers"] = {"followers":foll__.follower.count(),"following":foll__.following.count()}
            else:
                data['data']["followers"] = {"followers":0, "following":0}
            data['data']["post"] = []
            data['data']["ads_data"] = paginated_response.data
            return Response(data, content_type='application/json')
            
        else:
            data["status"], data['data'], data["message"] = status.HTTP_404_NOT_FOUND, "", "User not found"
    except Exception as e:
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data, content_type='application/json')


# @api_view(('POST',))
# def user_profile_edit_api(request):
#     data = {'status':'','message':''}
#     try:        
#         user_uuid = request.data.get('user_uuid')
#         user_secret_key = request.data.get('user_secret_key')
#         first_name = request.data.get('first_name')
#         last_name = request.data.get('last_name')
#         user_birthday = request.data.get('user_birthday')
#         image = request.data.get('image')
#         gender = request.data.get('gender')
#         street = request.data.get('street')
#         city = request.data.get('city')
#         state = request.data.get('state')
#         postal_code = request.data.get('postal_code')
#         country = request.data.get('country')
#         latitude = request.data.get('latitude')
#         longitude = request.data.get('longitude')
#         phone = request.data.get('phone')
#         player_rank = request.data.get('player_rank')
#         player_rank_lock = request.data.get('player_rank_lock')
#         bio = request.data.get('bio')
#         fb_link = request.data.get('fb_link')
#         twitter_link = request.data.get('twitter_link')
#         youtube_link = request.data.get('youtube_link')
#         tictok_link = request.data.get('tictok_link')
#         instagram_link = request.data.get('instagram_link')

#         check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
#         if check_user.exists():
#             if user_birthday and user_birthday not in ["", "null", " ", None,'undefined'] :
#                 # mm/dd/yy
#                 user_birthday = datetime.strptime(user_birthday, '%m/%d/%Y').strftime('%Y-%m-%d')
#             else:
#                 user_birthday = None
#             get_user = check_user.first()
#             get_user.first_name = first_name
#             get_user.last_name = last_name
#             get_user.user_birthday = user_birthday
#             get_user.image = image
#             get_user.gender = gender
#             get_user.rank = player_rank
#             get_user.bio = bio
#             get_user.street = street
#             get_user.city = city
#             get_user.state = state
#             get_user.postal_code = postal_code
#             get_user.country = country
#             get_user.latitude = latitude
#             get_user.longitude = longitude
#             check_delivery_address = ProductDeliveryAddress.objects.filter(created_by_id=get_user.id)
#             if street and city and state and postal_code and country and not check_delivery_address.exists() :
#                 obj = GenerateKey()
#                 delivery_address_key = obj.gen_delivery_address_sk()
#                 complete_address = f'{street}, {city}, {state}, {country}, PIN-{postal_code}'
#                 save_delivery_address = ProductDeliveryAddress(secret_key=delivery_address_key,
#                                         street=street,city=city,state=state,postal_code=postal_code,
#                                         country=country,complete_address=complete_address,
#                                         created_by_id=get_user.id)
#                 save_delivery_address.save()
#             get_user.fb_link = fb_link
#             get_user.twitter_link = twitter_link
#             get_user.youtube_link = youtube_link
#             get_user.tictok_link = tictok_link
#             get_user.instagram_link = instagram_link
#             get_user.phone = phone
            
#             get_player = Player.objects.filter(player_email=get_user.email,player_phone_number=phone)
#             if get_player.exists() and get_user.is_player:
#                 for i in range(len(get_player)) :
#                     upadate_player = get_player[i]
#                     upadate_player.player_image = image
#                     upadate_player.player_first_name = first_name
#                     upadate_player.player_last_name = last_name
#                     player_full_name = f"{first_name} {last_name}"
#                     upadate_player.player_full_name = player_full_name
                    
#                     upadate_player.player_ranking = player_rank

#                     if player_rank_lock == "True" :
#                         upadate_player.player_rank_lock = True
                    
#                     upadate_player.save()
#             else:
#                 get_user.rank = player_rank
#             get_user.save()
#             data["status"], data['data'], data["message"] = status.HTTP_200_OK, "","Your profile edited successfully"
#         else:
#             data["status"], data['data'], data["message"] = status.HTTP_404_NOT_FOUND, "","User not found"
#     except Exception as e :
#         data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
#     return Response(data)


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

####start match me

@api_view(['GET'])
def user_update_details(request):
    data = {}
    
    user_uuid = request.GET.get("user_uuid")
    if not user_uuid:
        data["message"] = "User UUID is required"
        return Response(data, status=status.HTTP_400_BAD_REQUEST)

    user = get_object_or_404(User, uuid=user_uuid)
    data["is_updated"] = user.is_updated
    data["phone"] = user.phone
    data["gender"] = user.gender
    data["rank"] = user.rank
    data["location"] = user.current_location
    data["latitute"] = user.latitude
    data["longitute"] = user.longitude
    data["dob"] = str(user.user_birthday)
    data["availability"] = user.availability 
    data["message"] = "Found Details"
    return Response(data, status=status.HTTP_200_OK)



#change_1
@api_view(['POST'])
def update_user_details(request):
    try:
        data = json.loads(request.body)
        required_fields = ["user_uuid", "mobile_number", "dob", "location", "latitude", "longitude", "rank"]
        # Validate required fields
        if not all(data.get(field) for field in required_fields):
            return Response({"message": "All fields are required!", "data": {}}, status=status.HTTP_400_BAD_REQUEST)
        
        user_uuid = data["user_uuid"]
        mobile_number = data["mobile_number"]
        location = data["location"]
        latitude = data["latitude"]
        longitude = data["longitude"]
        rank = data["rank"]
        gender = data["gender"]
        availability = data["availability"]
        dob = data["dob"]
        dob = datetime.strptime(dob, "%Y-%m-%d").date()
        user = get_object_or_404(User, uuid=user_uuid)
        user.phone = mobile_number
        user.gender = gender
        user.current_location = location
        user.latitude = latitude
        user.longitude = longitude
        user.availability = availability
        user.user_birthday = dob
        user.is_updated = True
        user.rank = rank
        user.save()
        
        # Update player ranking and phone number if exists
        player_ins = Player.objects.filter(player=user).first()
        if player_ins:
            player_ins.player_ranking = rank
            player_ins.player_phone_number = mobile_number
            player_ins.save()
        return Response({"message": "Saved the data successfully!"}, status=status.HTTP_201_CREATED)
    
    except Exception as e:
        return Response({"message": str(e)}, status=status.HTTP_400_BAD_REQUEST)


#change_2
@api_view(['POST'])
def update_user_search_preference(request):
    try:
        data = request.data  # Use request.data for JSON payload
        user_uuid = data.get("user_uuid")
        from_rank = data.get("from_rank")
        to_rank = data.get("to_rank")
        availability = data.get("availability")  # Expecting a dictionary
        gender = data.get("gender")
        from_age = data.get("from_age")
        to_age = data.get("to_age")
        redious = data.get("redious")
        team_type = data.get("team_type")

        user = get_object_or_404(User, uuid=user_uuid)
        matching_details, created = MatchingDetails.objects.get_or_create(user=user)

        # Update the existing instance
        matching_details.from_rank = from_rank
        matching_details.to_rank = to_rank
        matching_details.gender = gender
        matching_details.search_availability = availability
        matching_details.from_age = int(from_age) if from_age else None
        matching_details.to_age = int(to_age) if to_age else None
        matching_details.redious = int(redious) if redious else None
        matching_details.team_type = team_type

        matching_details.save()

        return Response({"message": "Saved the data successfully!"}, status=status.HTTP_201_CREATED)

    except Exception as e:
        return Response({"message": str(e)}, status=status.HTTP_400_BAD_REQUEST)


#change_3
@api_view(['GET'])
def view_matching_player(request):
    data = {"from_rank": None, "to_rank": None,  "redious": 0,
            "from_age": 0, "to_age": 0, "gender": None, "availability": {}, 
            "message": None}
    
    user_uuid = request.GET.get("user_uuid")
    if not user_uuid:
        data["message"] = "User UUID is required"
        return Response(data, status=status.HTTP_400_BAD_REQUEST)

    user = get_object_or_404(User, uuid=user_uuid)
    check_matching_details = MatchingDetails.objects.filter(user=user)

    if check_matching_details.exists():
        matching_details = check_matching_details.first()
        data.update({
            "from_rank": matching_details.from_rank, 
            "to_rank": matching_details.to_rank,  
            "redious": matching_details.redious,
            "from_age": matching_details.from_age, 
            "to_age": matching_details.to_age, 
            "gender": matching_details.gender, 
            "availability": matching_details.search_availability, 
            "team_type":matching_details.team_type,
            "message": None})
        return Response(data, status=status.HTTP_200_OK)
    
    data["message"] = "Matching details not found"
    return Response(data, status=status.HTTP_200_OK)



def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371  # Earth's radius in km

    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    distance = R * c  # Distance in km
    return distance

def calculate_age(dob):
    today = datetime.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def is_availability_matching(user_availability, search_availability):
    """
    Check if user availability matches search availability.
    
    Args:
        user_availability (dict): User's availability, e.g., 
            {"Friday": [{"start": "2:00 PM", "end": "6:00 PM"}], ...}
        search_availability (dict): Search availability, e.g., 
            {"Friday": ["14:45", "17:30"], ...}
    
    Returns:
        bool: True if there's a match in availability, False otherwise.
    """
    try:
        # If either availability is empty, return False
        if not user_availability or not search_availability:
            return False

        # Get common days between user and search availability
        common_days = set(user_availability.keys()) & set(search_availability.keys())
        if not common_days:
            return False

        for day in common_days:
            user_slots = user_availability.get(day, [])
            search_times = search_availability.get(day, [])

            # Ensure both slots and times exist
            if not user_slots or not search_times:
                continue

            for slot in user_slots:
                # Parse user start and end times (12-hour format with AM/PM)
                start_str = slot.get("start")
                end_str = slot.get("end")
                if not start_str or not end_str:
                    continue

                try:
                    user_start = datetime.strptime(start_str, "%I:%M %p")
                    user_end = datetime.strptime(end_str, "%I:%M %p")
                except ValueError:
                    continue  # Skip if time format is invalid

                for search_time in search_times:
                    try:
                        # Parse search time (24-hour format)
                        search_dt = datetime.strptime(search_time, "%H:%M")
                    except ValueError:
                        continue  # Skip if time format is invalid

                    # Compare times: check if search_time falls within user slot
                    if user_start.time() <= search_dt.time() <= user_end.time():
                        return True  # Match found

        return False  # No match found
    except Exception as e:
        # Silently handle errors to avoid affecting the response structure
        return False

@api_view(['GET'])
def get_matching_users(request):
    try:
        user_uuid = request.GET.get("user_uuid")
        page = request.GET.get("page", 1)
        per_page = 100
        
        user = get_object_or_404(User, uuid=user_uuid)
        try:
            matching_details = MatchingDetails.objects.get(user=user)
        except MatchingDetails.DoesNotExist:
            return JsonResponse({"message": "Please set your Matching Preference details", "data": []}, status=200)

        user_latitude = float(user.latitude) if user.latitude not in ['null', None, '', " "] else None
        user_longitude = float(user.longitude) if user.longitude not in ['null', None, '', " "] else None
        user_from_rank = float(matching_details.from_rank) if matching_details.from_rank else None
        user_to_rank = float(matching_details.to_rank) if matching_details.to_rank else None
        user_radius = matching_details.redious
        user_from_age = matching_details.from_age
        user_to_age = matching_details.to_age
        user_gender = matching_details.gender
        user_availability = matching_details.search_availability
        user_teamtype = matching_details.team_type
        matching_users = User.objects.all().exclude(id=user.id)
        msg_ = None
        if user_gender:
            matching_users = matching_users.filter(gender=user_gender)
        
        if user_from_age and user_to_age:
            matching_users = [
                u for u in matching_users 
                if u.user_birthday and user_from_age <= calculate_age(u.user_birthday) <= user_to_age
            ]
        
        if user_from_rank and user_to_rank:
            user_from_rank = float(user_from_rank)
            user_to_rank = float(user_to_rank)
            matching_users = [
                u for u in matching_users 
                if float(u.rank) >= user_from_rank and float(u.rank) <= user_to_rank
            ]
        
        if user_availability:
            matching_users = [
                u for u in matching_users 
                if is_availability_matching(u.availability, user_availability)
            ]
       
        if user_latitude and user_longitude and user_radius:
            matching_users = [
                    u for u in matching_users
                    if u.latitude and u.longitude and u.latitude not in ['null', None, '', ' '] and u.longitude not in ['null', None, '', ' '] 
                    and calculate_distance(user_latitude, user_longitude, float(u.latitude), float(u.longitude)) <= int(user_radius)
                ]
        
        if user_teamtype:
            try:
                matching_users = []
                for u in matching_users:
                    matching_detail = MatchingDetails.objects.filter(user__uuid=u.user_uuid).first()
                    if matching_detail and matching_detail.team_type == user_teamtype:
                        matching_users.append(u)
            except Exception as e:
                msg_ = str(e)
        
        paginator = Paginator(matching_users, per_page)
        try:
            paginated_users = paginator.page(page)
        except PageNotAnInteger:
            paginated_users = paginator.page(1)
        except EmptyPage:
            return JsonResponse({"message": "No more matching players", "data": []}, status=200)

        response_data = [
            {
                "user_uuid": Player.objects.filter(player=u).first().uuid if Player.objects.filter(player=u).exists() else None,
                "key": Player.objects.filter(player=u).first().secret_key if Player.objects.filter(player=u).exists() else None,
                "chat_uuid": u.uuid,
                "chat_key": u.secret_key,
                "user_image": str(u.image) if u.image not in ["null", None, "", " "] else "user_images/pickleit_newlogo.jpg",
                "first_name": u.first_name,
                "last_name": u.last_name,
                "mobile_number": u.phone,
                "is_superuser": u.is_superuser,
                "is_admin": u.is_admin,
                "rank": u.rank,
                "location": u.current_location,
                "latitude": u.latitude,
                "longitude": u.longitude,
                "gender": u.gender,
                "availability": u.availability,
            }
            for u in paginated_users if not u.is_superuser and not u.is_admin
        ]

        # Build next and previous URLs
        base_url = request.build_absolute_uri()
        next_url = None
        previous_url = None
        
        if paginated_users.has_next():
            next_params = request.GET.copy()
            next_params['page'] = paginated_users.next_page_number()
            next_url = f"{base_url.split('?')[0]}?{next_params.urlencode()}"
        
        if paginated_users.has_previous():
            prev_params = request.GET.copy()
            prev_params['page'] = paginated_users.previous_page_number()
            previous_url = f"{base_url.split('?')[0]}?{prev_params.urlencode()}"
        
        return JsonResponse({
            "message": "Matching players found" + (f" {msg_}" if msg_ else ""),
            "count": len(matching_users),
            "next": next_url,
            "previous": previous_url,
            "data": response_data
        }, status=200)
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        return JsonResponse(
            {"message": str(e), "line": error_trace.splitlines()[-2], "data": []},
            status=400
        )



####end match me

def get_player_fun(team_id):
    team = get_object_or_404(Team, id=team_id)
    players = Player.objects.filter(team = team)
    if players:
        return list(players.values("player_first_name", "player_last_name"))
    return []



@api_view(['GET'])
def get_open_play_team(request):
    data = {
        "message": None,
        "need_team_create": False,
        "teams": []
    }
    
    try:
        user_uuid = request.GET.get("user_uuid")
        player_uuid = request.GET.get("player_uuid")  
        team_type = request.GET.get("team_type", None)

        # Get user and player objects
        user = get_object_or_404(User, uuid=user_uuid)
        player = get_object_or_404(Player, uuid=player_uuid)

        # Get player's teams and user_player teams
        user_player = Player.objects.filter(player=user).first()
        
        player_teams = player.team.filter(is_disabled=False)
        user_player_teams = user_player.team.filter(is_disabled=False) if user_player else []
        if team_type:
            player_teams = player_teams.filter(team_person=team_type)
            user_player_teams = user_player_teams.filter(team_person=team_type)
        
        # Combine unique teams
        teams = list(player_teams) + list(user_player_teams)
        if teams:
            data["teams"] = [
                {
                    "uuid": str(team.uuid),
                    "id": team.id,
                    "name": team.name,
                    "players": get_player_fun(team.id),
                    "team_person": team.team_person,
                    "created_first_name": team.created_by.first_name if team.created_by else "Admin",
                    "created_last_name": team.created_by.last_name if team.created_by else "Admin",
                    "team_image": str(team.team_image) if team.team_image not in [None, "null", ""] else ""
                } for team in teams
            ]
            
            if not data["teams"]:
                data["message"] = "No matching teams found for your criteria."
                data["need_team_create"] = True
        
        
        condition_one = player_teams.exists()
        condition_two = user_player_teams.exists()
        if not condition_one and not condition_two:
            data["message"] = "No teams found. Please create a team to participate."
            data["need_team_create"] = True
        elif condition_two and not condition_one:
            data["message"] = "You have a team, but your opponent does not. They need to create a team first."
            data["need_team_create"] = True
        elif not condition_two and condition_one:
            data["message"] = "Your opponent has a team, but you don't. Please create a team to proceed."
            data["need_team_create"] = True  

        return Response(data, status=status.HTTP_200_OK)

    except Exception as e:
        # error_trace = traceback.format_exc()
        data["message"] = f"An error occurred: {str(e)}"
        # data["error_details"] = error_trace
        return Response(data, status=status.HTTP_400_BAD_REQUEST)


@api_view(('POST',))
def create_open_play(request):
    data = {"message":None}
    try:
        user_uuid = request.data.get("user_uuid")
        team_ids = request.data.get("team_ids", [])
        leagues_start_date = request.data.get("leagues_start_date")
        leagues_start_date = datetime.strptime(leagues_start_date, '%Y-%m-%d').date()
        location = request.data.get("location")
        latitude = request.data.get("latitude")
        longitude = request.data.get("longitude")
        team_person = request.data.get("team_person")
        description = request.data.get("description", None)
        league_type = request.data.get("league_type", "Invites only")
        team_type = request.data.get("team_type", "Open-team")
        play_type = request.data.get("play_type", "Individual Match Play")
        
        user = get_object_or_404(User, uuid=user_uuid)
        teams = Team.objects.filter(id__in=team_ids)
        obj3 = GenerateKey()
        secret_key = obj3.gen_leagues_key()
        check_leagues = LeaguesTeamType.objects.filter(name=team_type)
        check_person = LeaguesPesrsonType.objects.filter(name=team_person)
        tournament_name = None
        for team in teams:
            if tournament_name:
                tournament_name = tournament_name + " VS " +team.name
            else:
                tournament_name = team.name
        if tournament_name:
            tournament_name = tournament_name + secret_key[:5]
        else:
            tournament_name = "OpenPlay" + secret_key[:10]
        save_leagues = Leagues(
            secret_key=secret_key,
            name=tournament_name,
            location = location,
            latitude = latitude,
            longitude = longitude,
            leagues_start_date = leagues_start_date,
            created_by = user,
            max_number_team = 2,
            play_type = play_type,
            registration_fee = 0,
            description = description,
            league_type = league_type,
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
        
        data["message"] = f"successfully create your Individual Match Play{tournament_name}"
    except Exception as e:
        data["message"] = str(e)
    return Response(data, status=status.HTTP_200_OK)



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
                team_image = None
                location = get_user.location
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


# @api_view(("POST",))
# def fcm_token_store(request):
#     data = {"status":"", "message":"", "data":[]}
#     try:        
#         user_uuid = request.data.get("user_uuid")
#         user_secret_key = request.data.get("user_secret_key")
#         fcm_token = request.data.get("fcm_token")
#         check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
#         if check_user.exists():
#             get_user = check_user.first()
#             check_token = FCMTokenStore.objects.filter(user=get_user)
#             if check_token.exists():
#                 get_token = check_token.first()
#                 token_list = get_token.fcm_token["fcm_token"]
#                 if str(fcm_token) not in token_list:
#                     token_list.append(str(fcm_token))
#                 get_token.save()
#             else:
#                 get_token = FCMTokenStore.objects.create(user=get_user,fcm_token={"fcm_token":[fcm_token]})
#             data["status"] = status.HTTP_200_OK
#             data["message"] = "FCM Token saved successfully."
#         else:
#             data["status"] = status.HTTP_404_NOT_FOUND
#             data["message"] = "User not found."

#     except Exception as e:
#         data['status'] = status.HTTP_400_BAD_REQUEST
#         data['message'] = str(e)
#     return Response(data)


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
                # ✅ Replace old token with new one
                get_token = check_token.first()
                get_token.fcm_token = {"fcm_token":[fcm_token]}
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
            data["status"], data["message"] = status.HTTP_200_OK, "Missing required parameters."
            return Response(data)

        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if not check_user.exists():
            data["status"], data["message"] = status.HTTP_200_OK, "User not found."
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
                    return Response(data, status=status.HTTP_200_OK)

        data["status"] = status.HTTP_200_OK
        data["message"] = "Location check completed."
        data["alert"] = alert

    except Exception as e:
        data["status"], data["message"] = status.HTTP_200_OK, f"Error: {e}"

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


@api_view(("GET",))
def get_wallet_details(request):
    """
    Retrieves the details of a wallet.
    """
    data = {"status": "", "message": ""} 
    try:
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')

        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if not check_user.exists():
            return Response(
                {"status": status.HTTP_401_UNAUTHORIZED, "message": "Unauthorized access", "data": []}
            )

        get_user = check_user.first()

        check_wallet = Wallet.objects.filter(user=get_user)
        if not check_wallet.exists():
            return Response(
                {"status": status.HTTP_400_BAD_REQUEST, "message": "Wallet not found", "data": []}
            )

        get_wallet = check_wallet.first()

        wallet_data = {
            "user": get_user.username,
            "wallet_id": get_wallet.id,
            "balance": float(get_wallet.balance), 
            "created_at": get_wallet.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": get_wallet.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
        }

        return Response(
            {"status": status.HTTP_200_OK, "message": "Wallet details retrieved successfully", "data": wallet_data}
        )
    except Exception as e:
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"Error: {e}"

    return Response(data)


@api_view(("POST",))
def add_money_to_wallet(request):
    """
    Adds money to wallet.
    """
    data = {"status": "", "message": ""} 
    try:
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key') 
        wallet_id = request.data.get('wallet_id')
        amount= float(request.data.get('amount')) 
        
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if not check_user.exists():
            return Response({
                "data": [],
                "status": status.HTTP_401_UNAUTHORIZED, 
                "message": "Unauthorized access"
            })
        
        get_user = check_user.first() 

        check_wallet = Wallet.objects.filter(id=int(wallet_id), user=get_user)
        if not check_wallet.exists():            
            return Response({
                "data": [],
                "status": status.HTTP_400_BAD_REQUEST, 
                "message": "Invalid wallet."
            })
        
        get_wallet = check_wallet.first()
        stripe.api_key = settings.STRIPE_SECRET_KEY
        
        product_name = f"Payment for adding money to wallet"
        product_description = "Payment received by Pickleit"   
        if get_user.stripe_customer_id:
            stripe_customer_id = get_user.stripe_customer_id
        else:
            customer = stripe.Customer.create(email=get_user.email)
            stripe_customer_id = customer["id"]
            get_user.stripe_customer_id = stripe_customer_id
            get_user.save()     
        
        payment_data = json.dumps({"wallet_id": get_wallet.id, "amount": amount}).encode('utf-8')
        encoded_data = base64.b64encode(payment_data).decode('utf-8')

        host = request.get_host()
        protocol = "https"
        payment_for = "Add_money_to_wallet"
        current_site = f"{protocol}://{host}"
        
        success_url = f"{current_site}/user/285631b6075a10ddfc536d3d9be994d05a932abc3d6f091fabe8e7aa77ccfd25/{payment_for}/{encoded_data}/{{CHECKOUT_SESSION_ID}}/"
        cancel_url = f"{current_site}/payment/cancel/"
        print(success_url)
        product = stripe.Product.create(name=product_name, description=product_description)
        price = stripe.Price.create(unit_amount=int(amount* 100), currency='usd', product=product.id)

        checkout_session = stripe.checkout.Session.create(
            customer=stripe_customer_id,
            line_items=[{"price": price.id, "quantity": 1}],
            mode='payment',
            success_url=success_url,
            cancel_url=cancel_url,
        )
        # Add payment details to add_fund
        AllPaymentsTable.objects.create(
            user=get_user,
            amount=amount,
            checkout_session_id=checkout_session.id,
            payment_mode="Stripe",
            payment_for=payment_for,
            status="Pending"
        )
        return Response({"stripe_url": checkout_session.url})

    except Exception as e:
        return Response({"status": status.HTTP_400_BAD_REQUEST, "message": str(e)})


@api_view(['GET',])
def payment_for_adding_money_to_wallet(request, payment_for, encoded_data, checkout_session_id):
    try:
        stripe.api_key = settings.STRIPE_SECRET_KEY
        payment_info = stripe.checkout.Session.retrieve(checkout_session_id)        

        stripe_customer_id = payment_info["customer"]
        payment_status = payment_info["payment_status"]
        amount_total = Decimal(str(float(payment_info["amount_total"]) / 100))
        payment_method_types = payment_info["payment_method_types"]
        
        # Decode payment data
        decoded_data = base64.b64decode(encoded_data)
        request_data = json.loads(decoded_data.decode('utf-8'))
        add_amount = Decimal(str(request_data["amount"]))
        Percentagefee = Decimal("0.029")
        Fixed_fee = Decimal("0.30")
        wallet_amount = add_amount - (add_amount * Percentagefee) - Fixed_fee
        get_user = User.objects.filter(stripe_customer_id=stripe_customer_id).first()
        # print(get_user, payment_status)
        
        if not get_user:
            return render(request, "failed_payment.html")

        check_existing_payment = AllPaymentsTable.objects.filter(checkout_session_id=checkout_session_id, user=get_user)
        if check_existing_payment.exists():
            existing_payment = check_existing_payment.first()
            if existing_payment.status == "Completed":
                return render(request, "success_payment.html", {"charge_for": payment_for})

        # Save Payment       
        AllPaymentsTable.objects.create(
            user=get_user,
            amount=amount_total,
            checkout_session_id=checkout_session_id,
            payment_mode=", ".join(payment_method_types),
            payment_for = payment_for,
            status="Completed" if payment_status == "paid" else "Failed"
        )

        if payment_status == "paid":    
            stripe_fee = Decimal(str((amount_total * Decimal("0.029")) + Decimal("0.30")))  
            final_amount = wallet_amount

            wallet = Wallet.objects.filter(user=get_user, id=request_data["wallet_id"]).first()
            # print(wallet)
            if wallet:
                try:
                    transaction = WalletTransaction.objects.create(
                        # wallet=wallet,
                        sender = get_user,
                        reciver = get_user,
                        amount = Decimal(final_amount).quantize(Decimal('0.001'), rounding=ROUND_DOWN),
                        admin_cost = 0,
                        getway_charge = Decimal(stripe_fee).quantize(Decimal('0.001'), rounding=ROUND_DOWN),
                        transaction_for="AddMoney",
                        transaction_type="credit",
                        payment_id=checkout_session_id,  # Fixed the typo
                        description=f"${final_amount} is added to your PickleIt wallet."
                    )
                    wallet.balance = wallet.balance + Decimal(str(final_amount))
                    wallet.save()
                    # print(f"Transaction created successfully: {transaction}")
                except Exception as e:
                    # print(f"Error creating transaction: {e}")
                    return render(request, "failed_payment.html", {"error": "Transaction creation failed."})

                return render(request, "success_payment_for_add_mony.html", {"charge_for": payment_for})
        else:
            return render(request, "failed_payment.html")

    except Exception as e:
        return render(request, "failed_payment.html", {"error": str(e)})
    

@api_view(("GET",))
def get_all_wallet_transactions(request):
    """
    Retrieves all transactions associated with a wallet.
    """
    data = {"status": "", "message": ""} 
    try:
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key') 
        wallet_id = request.GET.get('wallet_id')
        filter_type = request.GET.get('filter')

        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if not check_user.exists():
            return Response({
                "data": [],
                "status": status.HTTP_401_UNAUTHORIZED, 
                "message": "Unauthorized access"
            })
        
        get_user = check_user.first()

        check_wallet = Wallet.objects.filter(id=int(wallet_id), user=get_user)
        if not check_wallet.exists():            
            return Response({
                "data": [],
                "status": status.HTTP_400_BAD_REQUEST, 
                "message": "Invalid wallet."
            })
        
        get_wallet = check_wallet.first()
        transactions = WalletTransaction.objects.filter(Q(sender=get_user) | Q(reciver=get_user)).order_by('-created_at')
        
        if filter_type == "last_10":
            transactions = transactions.filter(created_at__gte=now() - timedelta(days=10))
        elif filter_type == "last_1_month":
            transactions = transactions.filter(created_at__gte=now() - timedelta(days=30))
        elif filter_type == "last_3_months":
            transactions = transactions.filter(created_at__gte=now() - timedelta(days=90))
        elif filter_type == "last_6_months":
            transactions = transactions.filter(created_at__gte=now() - timedelta(days=180))
        elif filter_type == "last_1_year":
            transactions = transactions.filter(created_at__gte=now() - timedelta(days=365))
        else:
            transactions = transactions[:10]
        
        paginator = PageNumberPagination()
        paginator.page_size = 20
        result_page = paginator.paginate_queryset(transactions, request)
        serializer = WalletTransactionSerializer(result_page, many=True)
        serialized_data = serializer.data       
        
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

    except Exception as e:
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"Error: {e}"

    return Response(data)


@api_view(("POST",)) 
def create_withdrawal_request(request):
    """
    Requests for withdrawal of money from wallet.
    """
    data = {"status": "", "message": ""} 
    try:
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')         
        amount= request.data.get('amount')

        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if not check_user.exists():
            return Response({
                "data": [],
                "status": status.HTTP_401_UNAUTHORIZED, 
                "message": "Unauthorized access"
            })
        
        get_user = check_user.first() 

        check_wallet = Wallet.objects.filter(user=get_user)
        if not check_wallet.exists():            
            return Response({
                "data": [],
                "status": status.HTTP_400_BAD_REQUEST, 
                "message": "Invalid wallet."
            })
        
        get_wallet = check_wallet.first()

        balance = get_wallet.balance
        if float(amount) > float(balance):
            return Response({
                "balance": balance,
                "data": [],
                "status": status.HTTP_400_BAD_REQUEST, 
                "message": "Insufficient balance in wallet."
            })
        
        withdrawal_request = WithdrawalRequest.objects.create(
            user=get_user,
            amount = Decimal(amount),
            status="pending"
        )
        get_wallet.balance =get_wallet.balance - Decimal(amount)
        get_wallet.save()
        # Send notification to admin
        admin_users = User.objects.filter(is_admin=True, is_superuser=True).values_list('id', flat=True)
        title = "Money withdrawal request."
        message = f"{get_user.first_name} {get_user.last_name} has requested for withdrawal of amount ${withdrawal_request.amount}."
        for user_id in admin_users:
            notify_edited_player(user_id, title, message)        

        data["status"] = status.HTTP_200_OK
        data["balance"] = get_wallet.balance
        data["message"] = f"Withdrawal request of amount ${withdrawal_request.amount} has been sent successfully."
        return Response(data)
    
    except Exception as e:
        return Response({"status": status.HTTP_400_BAD_REQUEST, "message": str(e)})


@api_view(("GET",)) 
def withdrawal_request_list(request):
    """
    Requests for withdrawal of money from wallet.
    """
    data = {"status": "", "message": ""} 
    try:
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key') 
        filter = request.GET.get('filter')

        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if not check_user.exists():
            return Response({
                "data": [],
                "status": status.HTTP_401_UNAUTHORIZED, 
                "message": "Unauthorized access"
            })

        get_user = check_user.first() 

        withdrawal_requests = WithdrawalRequest.objects.filter(user=get_user).order_by('-created_at')

        if filter == "pending":
            withdrawal_requests = withdrawal_requests.filter(status="pending")

        elif filter == "approved":
            withdrawal_requests = withdrawal_requests.filter(status="approved")

        elif filter == "rejected":
            withdrawal_requests = withdrawal_requests.filter(status="rejected")

        paginator = PageNumberPagination()
        paginator.page_size = 20
        result_page = paginator.paginate_queryset(withdrawal_requests, request)
        serializer = WithdrawalRquestSerializer(result_page, many=True)
        serialized_data = serializer.data       
        
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

        return Response(data)
    except Exception as e:
        return Response({"status": status.HTTP_400_BAD_REQUEST, "message": str(e)})


@api_view(["POST"])
def deactivate_account(request):
    """
    Deactivate user account.
    """
    user_uuid = request.data.get("user_uuid")
    if not user_uuid:
        return Response({"message": "User UUID is required."}, status=status.HTTP_400_BAD_REQUEST)

    user = get_object_or_404(User, uuid=user_uuid)

    User.objects.filter(uuid=user_uuid).update(is_active=False)

    return Response({"message": "Account deleted successfully!"}, status=status.HTTP_200_OK)


### create function for adjust user to 
### create function for adjust user to player
def check_player(request):
    for user in User.objects.all():
        player = Player.objects.filter(player=user)
        if not player:
            obj = GenerateKey()
            scr_key = obj.gen_player_keyget()
            Player.objects.create(secret_key=scr_key,player=user,player_image=user.image, player_first_name=user.first_name,player_last_name=user.last_name, player_email=user.email, player_phone_number=user.phone, player_ranking=user.rank)
    return HttpResponse({"players":[]})


from getstream import Stream
from getstream.models import CallRequest, MemberRequest
import time

# Initialize the Stream client for Video API
client = Stream(api_key=settings.STREAM_API_KEY, api_secret=settings.STREAM_API_SECRET)

def create_livestream_call(user_id, call_id, role):
    try:
        # Create call object
        call = client.video.call('livestream', call_id)

        # Create the call with recording enabled and quality specified
        create_response = call.create(
            data=CallRequest(
                created_by_id=user_id,
                members=[
                    MemberRequest(user_id=user_id, role=role),
                ],
                custom={'color': 'blue'},
                settings_override={
                    'recording': {
                        'mode': 'auto-on',
                        'audio_only': False,
                        'quality': '720p',
                        'layout': {
                            'name': 'grid',  # REQUIRED by Stream API
                            'custom': {
                                'aspect_ratio': '16:9',
                                'max_resolution': '1280x720'
                            }
                        }
                    }
                }
            )
        )

        # Get members data (adjusted for proper response handling)
        members_data = getattr(create_response, 'call', None)  # Access 'call' attribute safely
        if members_data and hasattr(members_data, 'members'):
            members = [
                {'user_id': member.user_id, 'role': member.role}
                for member in members_data.members
            ]
        else:
            members = []

        # Generate a token
        token = client.create_token(user_id=user_id)
        return {
            'call_id': call_id,
            'token': token,
            'members': members
        }

    except Exception as e:
        return {'error': f"Failed to create livestream call: {str(e)}"}

@api_view(['POST'])
def get_stream_token(request):
    """
    API endpoint to create a livestream call and return a token for the user.
    Expects 'user_uuid' in the POST data; optionally accepts 'call_id'.
    """
    try:
        user_id = request.data.get('user_uuid')
        description = request.data.get('description', None)
        start_time = request.data.get('start_time')
        role = request.data.get('role')
        if role == 'viewer':
            role = 'user'
        elif role == 'admin':
            role = 'admin'
        else:
            return JsonResponse({'error': 'role is invalid'}, status=200)
        if not user_id:
            return JsonResponse({'error': 'user_uuid is required'}, status=400)

        user = get_object_or_404(User, uuid=user_id)

        call_id = request.data.get('call_id', f'livestream_{user_id}_{int(time.time())}')
        result = create_livestream_call(user_id, call_id, role)

        if 'error' in result:
            return JsonResponse({'error': result['error']}, status=500)

        # Convert `start_time` to datetime, or use current time if not provided
        if start_time:
            try:
                start_time = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                return JsonResponse({'error': 'Invalid start_time format. Use YYYY-MM-DD HH:MM:SS'}, status=400)
        else:
            start_time = now()

        
        if role != 'admin':
            role = 'viewer'
        call_instance = StoreCallId.objects.create(
            user=user,
            call_id=result['call_id'],
            token=result['token'],
            role=role,
            description=description,
            start_time=start_time
        )

        # Send notification to player's followers
        player = Player.objects.filter(player=user).first()
        if player:
            followers = player.follower.all()  # ManyToMany field
            title = "Start Streaming"
            notify_message = f"{user.first_name} started streaming" if not description else f"{user.first_name} started streaming for {description}"
            for follower in followers:
                notify_edited_player(follower.id, title, notify_message)

        # Format `start_time` before returning response
        formatted_start_time = call_instance.start_time.strftime("%Y-%m-%d %H:%M:%S")

        return JsonResponse({
            'id': call_instance.id,
            'call_id': result['call_id'],
            'token': result['token'],
            'role': role,
            'members': result['members'],
            'start_time': formatted_start_time,
            'message': 'Livestream call created successfully'
        }, status=200)

    except Exception as e:
        return JsonResponse({'error': f"Server error: {str(e)}"}, status=500)

import requests
import time
def get_video_url(call_id, api_key, token):
    """
    Retrieve the video URL for a recorded livestream call.
    
    Args:
        call_id (str): The ID of the call (e.g., 'livestream_a8b0d24e-7487-4c33-bc7a-e2a858cff795_1744115660')
        api_key (str): Stream API key
        token (str): JWT token for authentication
    
    Returns:
        dict: Contains 'video_url' (str or None) and 'message'
    """
    try:
        # Correct URL with /recordings endpoint
        url = f"https://video.stream-io-api.com/video/call/livestream/{call_id}/recordings"
        headers = {
            "accept": "application/json",
            "Authorization": token,
            "Stream-Auth-Type": "jwt"
        }
        params = {
            "api_key": api_key
        }

        # Make the GET request
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()  # Raise an exception for 4xx/5xx status codes

        # Parse the JSON response
        data = response.json()
        recordings = data.get('recordings', [])
        
        if recordings:
            video_url = recordings[0].get('url')
            return {
                'video_url': video_url,
                'message': 'Video URL retrieved successfully'
            }
        else:
            return {
                'video_url': None,
                'message': 'No recordings available for this call'
            }

    except requests.exceptions.RequestException as e:
        return {
            'video_url': None,
            'message': f"Error retrieving video URL: {str(e)}"
        }


@api_view(['POST'])
def close_stream_token(request):
    try:
        user_id = request.data.get('user_uuid')
        stream_id = request.data.get('stream_id')
        end_time = request.data.get('end_time')

        if not user_id:
            return JsonResponse({'message': 'user_uuid is required'}, status=400)

        user = get_object_or_404(User, uuid=user_id)
        stream = get_object_or_404(StoreCallId, id=stream_id)

        if stream.user != user:
            return JsonResponse({'message': 'Unauthorized to close this stream'}, status=403)

        if end_time:
            try:
                end_time = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                return JsonResponse({'error': 'Invalid end_time format. Use YYYY-MM-DD HH:MM:SS'}, status=400)
        else:
            end_time = now()

        # Stop recording and get the video URL

        # Update stream metadata
        stream.status = False
        stream.end_time = end_time
        stream.save()

        return JsonResponse({'message': 'Stream closed successfully'}, status=200)

    except Exception as e:
        return JsonResponse({'message': f"Server error: {str(e)}"}, status=500)

@api_view(['POST'])
def delete_stream(request):
    try:
        user_id = request.data.get('user_uuid')
        stream_id = request.data.get('stream_id')
    
        if not user_id:
            return JsonResponse({'message': 'user_uuid is required'}, status=200)

        user = get_object_or_404(User, uuid=user_id)
        stream = get_object_or_404(StoreCallId, id=stream_id)

        if stream.user != user:
            return JsonResponse({'message': 'Unauthorized to close this stream'}, status=200)
        stream.delete()

        return JsonResponse({
            'message': 'Stream deleted successfully',
        }, status=200)

    except Exception as e:
        return JsonResponse({'message': f"Server error: {str(e)}"}, status=500)


@api_view(["GET"])
def get_video_link(request):
    try:
        stream_id = request.GET.get("stream_id")
        if not stream_id:
            return Response({'error': 'Missing stream_id'}, status=400)

        stream = get_object_or_404(StoreCallId, id=stream_id)
        call_id = stream.call_id

        api_key = settings.STREAM_API_KEY
        token = stream.token  

        result = get_video_url(call_id, api_key, token)

        if result.get("video_url"):
            return Response({"url": result["video_url"]}, status=200)
        else:
            return Response({"error": result.get("error", "Video URL not found")}, status=404)

    except Exception as e:
        return Response({'error': f"Server error: {str(e)}"}, status=500)

@api_view(["GET"])
def get_call_token(request):
    context = {"call_id_list": []}
    pre = request.GET.get("status", None)
    

    if pre:
        call_id_list = StoreCallId.objects.filter(status=False, role='admin').order_by("-end_time")[:30]  # Get only the latest 30 records

    else:
        call_id_list = StoreCallId.objects.filter(status=True, role='admin')

    

    call_id_list = call_id_list.values(
                "id", "user__uuid", "user__secret_key", "user__first_name","video_url","start_time",
                "user__last_name", "description", "call_id", "token", "status")
    context["call_id_list"] = call_id_list
    return Response(context, status=status.HTTP_200_OK)

@api_view(["GET"])
def get_my_call(request):
    context = {"call_id_list": []}
    user_uuid = request.GET.get("user_uuid", None)
    user = get_object_or_404(User, uuid=user_uuid)
    call_id_list = StoreCallId.objects.filter(user=user, role='admin').order_by('status')
    if call_id_list:
        call_id_list = call_id_list.values(
                "id", "user__uuid", "user__secret_key", "user__first_name","video_url","start_time",
                "user__last_name", "description", "call_id", "token", "status")
    else:
        call_id_list = []
    context["call_id_list"] = call_id_list
    return Response(context, status=status.HTTP_200_OK)


#### map find courts, club, event, open-play api
from geopy.distance import geodesic
RADIUS_KM = 200  # 200 km radius

def is_within_radius(obj, user_location):
    """Check if an object is within the given radius of the user location."""
    if not obj.latitude or not obj.longitude:
        return False  # Ignore objects with no coordinates
    obj_location = (float(obj.latitude), float(obj.longitude))
    return geodesic(user_location, obj_location).km <= RADIUS_KM

def get_nearby_objects(queryset, user_location):
    """Filter objects within the specified radius."""
    return [obj for obj in queryset if is_within_radius(obj, user_location)]

def serialize_league(league):
    """Serialize League objects."""
    return {
        "name": league.name,
        "uuid": league.uuid,
        "secret_key": league.secret_key,
        "location": league.location,
        "latitude": league.latitude,
        "longitude": league.longitude,
    }

def serialize_court(court):
    """Serialize Court objects."""
    return {
        "id": court.id,
        "name": court.name,
        "location": court.location,
        "latitude": court.latitude,
        "longitude": court.longitude,
    }

def serialize_club(club):
    """Serialize Club objects."""
    return {
        "id": club.id,
        "name": club.name,
        "location": club.location,
        "latitude": club.latitude,
        "longitude": club.longitude,
    }

@api_view(['GET'])
def find_nearby_places(request):
    """API to find courts, clubs, events, and open-play areas within a given radius."""
    lat = request.GET.get('latitude')
    lon = request.GET.get('longitude')

    if not lat or not lon:
        return Response({'error': 'Latitude and Longitude are required'}, status=400)

    try:
        user_location = (float(lat), float(lon))
    except ValueError:
        return Response({'error': 'Invalid latitude or longitude format'}, status=400)

    # Fetching filtered objects
    event = get_nearby_objects(Leagues.objects.exclude(team_type__name="Open-team"), user_location)
    open_play = get_nearby_objects(Leagues.objects.filter(team_type__name="Open-team"), user_location)
    courts = get_nearby_objects(Courts.objects.all(), user_location)
    clubs = get_nearby_objects(Club.objects.all(), user_location)

    response_data = {
        "event": [serialize_league(league) for league in event],
        "open_play": [serialize_league(league) for league in open_play],
        "courts": [serialize_court(court) for court in courts],
        "clubs": [serialize_club(club) for club in clubs],
        "event_count": len(event),
        "open_play_count": len(open_play),
        "total_courts": len(courts),
        "total_clubs": len(clubs),
    }

    return Response(response_data)

@api_view(["GET"])
def get_promo_codes(request):
    try:
        for_value = request.GET.get("codefor", None)
        user_uuid = request.GET.get("user_uuid")
        data = {"message":"", "data":[]}
        if not for_value:
            data["message"] = "Parameter 'codefor' is required."
            data["data"] = []
            return Response(data, status=status.HTTP_400_BAD_REQUEST)

        promo_codes = PromoCode.objects.filter(codefor=for_value)
        serializer = PromoCodeSerializer(promo_codes, many=True)
        data["message"] = "Done"
        data["data"] = serializer.data
        return Response(data, status=status.HTTP_200_OK)
    except Exception as e:
        data["message"] = str(e)
        data["data"] = []
        return Response(data, status=status.HTTP_400_BAD_REQUEST)


from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

@api_view(['POST'])
def account_deletion_request(request):
    try:
        user_id = request.data.get('user_uuid')
        reason = request.data.get('reason', None)  # Get reason for deletion
        user = get_object_or_404(User, uuid=user_id)
        email = user.username  # Assuming username is the email

        # Prepare email content
        context = {
            "full_name": f"{user.first_name} {user.last_name}",
            "user_email": email,
            "reason": reason,
            "date_now": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        # Render HTML email
        html_content = render_to_string('email/delete_request.html', context)
        text_content = strip_tags(html_content)  # Plain text version

        # Send email
        subject = "Request for Account Deletion"
        from_email = email  # The user's email address
        # recipient_list = ["joinpickleit@gmail.com"]  # Admin email
        recipient_list = ["joinpickleit@gmail.com"]

        email_message = EmailMultiAlternatives(subject, text_content, from_email, recipient_list)
        email_message.attach_alternative(html_content, "text/html")
        email_message.send()

        return JsonResponse({'message': "Account deletion request sent successfully"}, status=200)
    except Exception as e:
        return JsonResponse({'message': f"Server error: {str(e)}"}, status=500)


def event_matches_table(request):
    context = {}
    try:
        event_uuid = request.GET.get("event_uuid")
        event = get_object_or_404(Leagues, uuid=event_uuid)
        matches = Tournament.objects.filter(leagues=event).order_by("match_number")
        for m in matches:
            score = TournamentSetsResult.objects.filter(tournament=m)
            m.team1_score = list(score.values_list("team1_point", flat=True))
            m.team2_score = list(score.values_list("team2_point", flat=True))
        context["event"] = event
        context["matches"] = matches
        return render(request, 'match_pdf/matces_table.html', context)
    except Exception as e:
        context["message"] = str(e)
        return render(request, 'match_pdf/matces_table.html', context)



from collections import defaultdict

@api_view(["GET"])
def del_user_stripe_id(request):
    try:
        wallet_user_list = []

        # Group wallets by user ID
        for wallet in Wallet.objects.all():
            wallet_user_list.append(wallet.user.id)

        
        return Response({"done":wallet_user_list}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)    
        
