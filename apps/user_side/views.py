import stripe
import uuid
import base64
import requests
import json
from decimal import Decimal
from pyexpat.errors import messages
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login as auth_login, logout
from django.urls import reverse
from django.utils.timezone import make_aware
from django.http import HttpResponseRedirect
from django.contrib import messages
from django.db.models import Exists, OuterRef
from django.views.decorators.http import require_POST
from apps.team.models import *
from apps.user.models import AllPaymentsTable, User, Wallet, Transaction, WalletTransaction
from apps.socialfeed.models import *
from django.db.models import Q
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from datetime import timezone, datetime
from django.views.decorators.csrf import csrf_exempt
from apps.clubs.models import *
from apps.courts.models import *
from django.conf import settings
from geopy.distance import geodesic
from rest_framework import status
from apps.user.helpers import *
from apps.team.views import notify_edited_player, check_add_player
from decimal import Decimal, ROUND_DOWN
from apps.chat.models import NotificationBox
from apps.socialfeed.models import *
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from haversine import haversine, Unit
from django.db import transaction
import os, math
from django.contrib import messages
from apps.store.models import MerchandiseStore, MerchandiseStoreCategory, MerchandiseStoreProduct, CustomerMerchandiseStoreProductBuy, Leagues
stripe.api_key = settings.STRIPE_SECRET_KEY
protocol = settings.PROTOCALL
from django.templatetags.static import static

def get_lat_long_google(api_key, location):
    base_url = "https://maps.googleapis.com/maps/api/geocode/json"
    
    # Prepare the request parameters
    params = {
        "address": location,
        "key": api_key
    }

    # Make the request
    response = requests.get(base_url, params=params)
    data = response.json()

    # Extract latitude and longitude
    if data["status"] == "OK":
        lat = data["results"][0]["geometry"]["location"]["lat"]
        lng = data["results"][0]["geometry"]["location"]["lng"]
        return lat, lng
    else:
        return None

def user_login(request):
    context = {}
    if request.method == "POST":
        username = request.POST.get("email", "").strip()
        password = request.POST.get("password", "").strip()

        if not username or not password:
            context['message'] = "Email and password are required!"
            return render(request, "auth/login.html", context)

        user = authenticate(request, username=username, password=password)

        if user is None:
            context['message'] = "Invalid credentials!"
        elif user.is_superuser:
            context['message'] = "You are not authorized to log in here!"
        else:
            auth_login(request, user)
            return redirect('user_side:user_index')

    return render(request, "auth/login.html", context)

def go_app_to_web(request, user_uuid):
    user = get_object_or_404(User, uuid=user_uuid)
    auth_login(request, user)
    return redirect("user_side:user_index")

@login_required(login_url="/user_side/")
def logout_view_user(request):
    logout(request)
    return redirect('user_side:user_login')

def user_signup(request):
    return render(request, 'auth/signup.html')

@login_required(login_url="/user_side/")
def profile(request):  
    player = Player.objects.filter(player=request.user).first()
    if not player:  
        return render(request, 'sides/profile.html', {"user_details": request.user, "player": None})
    teams = player.team.all()
    match_history = Tournament.objects.filter(Q(team1__in=teams) | Q(team2__in=teams)).order_by("-id")
    match_history_cal = match_history.values_list("winner_team", flat=True)
    wins = sum(1 for winner_team in match_history_cal if winner_team in teams)
    losses = match_history.count() - wins
    #my feed 
    user_likes = LikeFeed.objects.filter(
        user=request.user, post=OuterRef('pk')
    )
    check_plan = Subscription.objects.filter(
        user=request.user,
        is_active=True,
        end_date__date__gte=datetime.now().date()
    ).exists()
    # Annotate posts with is_like
    posts = socialFeed.objects.filter(user=request.user).annotate(is_like=Exists(user_likes)).order_by('-created_at')
    context = {
        "user_details": request.user,
        "player": player,
        "total_match": match_history.count(),
        "losses": losses,
        "wins": wins,
        "socail_feed_list" : posts,
        "MAP_API_KEY": settings.MAP_API_KEY,
        'error': "Upgrade your plan" if not check_plan else None
    }

    return render(request, 'sides/profile.html', context)

@login_required(login_url="/user_side/")
def edit_profile(request):
   
    #print("Before form submission:", request.user, request.user.is_authenticated)  # Debugging line

    user = request.user

    if request.method == "POST":
        user.first_name = request.POST.get("first_name", user.first_name)
        user.last_name = request.POST.get("last_name", user.last_name)
        user.phone = request.POST.get("phone", user.phone)
        user.gender = request.POST.get("gender", user.gender)
        user.rank = request.POST.get("rank", user.rank)
        user.user_birthday = request.POST.get("dob", user.user_birthday)
        user.permanent_location = request.POST.get("location", user.permanent_location)
        
        # Fixing incorrect latitude and longitude field names
        user.latitude = request.POST.get("latitude", user.latitude)
        user.longitude = request.POST.get("longitude", user.longitude)
        
        user.bio = request.POST.get("bio", user.bio)

        if 'profile_picture' in request.FILES:
            user.image = request.FILES['profile_picture']
        
        try:
            user.save()
            auth_login(request, user)  # Keep the user logged in
            #print("After form submission:", request.user, request.user.is_authenticated)  # Debugging line
            return redirect('user_side:user_profile') 
        except Exception as e:
            messages.error(request, f"Error updating profile: {str(e)}")

    context = {"user_details": user, "MAP_API_KEY" : 'AIzaSyAfBo6-cZlOpKGrD1ZYwISIGjYvhH_wPmk'}
    return render(request, 'sides/editprofile.html', context)

def haversine_calculation(lat1, lon1, lat2, lon2):
    R = 6371  # Radius of Earth in km
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    lat1 = math.radians(lat1)
    lat2 = math.radians(lat2)

    a = math.sin(d_lat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(d_lon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c

@csrf_exempt
def nearby_pickleball(request):
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            lat = float(body.get('lat'))
            lng = float(body.get('lng'))
        except (TypeError, ValueError, json.JSONDecodeError):
            return JsonResponse({'error': 'Invalid latitude or longitude'}, status=400)

        player_data = []
        event_data = []
        today_date = datetime.now().date()
        for player in Player.objects.select_related('player').all():
            player_lat = player.player.latitude
            player_lng = player.player.longitude
            if player_lat and player_lng not in ['0', 0, None, "", "null"]:
                try:
                    dist = haversine_calculation(lat, lng, float(player_lat), float(player_lng))
                    if dist <= 100:
                        player_data.append({
                            "name": f'{player.player.first_name} {player.player.last_name}',
                            "lat": float(player_lat),
                            "lng": float(player_lng),
                            'image':player.player.image.url if player.player.image else static('img/no_image.jpg'),
                            'rank':player.player.rank,
                            'location':player.player.current_location
                        })
                except:
                    continue

        for event in Leagues.objects.filter(Q(registration_start_date__date__gte=today_date) | Q(leagues_end_date__date__gte=today_date)):
            if event.latitude and event.longitude not in ['0', 0, None, "", "null"]:
                try:
                    dist = haversine_calculation(lat, lng, float(event.latitude), float(event.longitude))
                    if dist <= 100:
                        event_data.append({
                            "name": event.name,
                            "lat": float(event.latitude),
                            "lng": float(event.longitude),
                            "start_date":event.leagues_start_date,
                            "reg_start_date":event.registration_start_date,
                            "reg_end_date":event.registration_end_date,
                            "team_type":event.team_type.name,
                            "image":event.image.url if event.image else static('img/pickleit_logo.jpg'),
                            "max_teams":event.max_number_team,
                            "joined_teams":event.registered_team.count(),
                            "location":event.location
                        })
                except:
                    continue

        return JsonResponse({
            "player_data": player_data,
            "event_data": event_data,
        })

    return JsonResponse({'error': 'Invalid request'}, status=400)

@csrf_exempt
def proxy_google_places(request):
    if request.method == "POST":
        try:
            body = json.loads(request.body)
            lat = float(body.get("lat"))
            lng = float(body.get("lng"))
            radius_m = float(body.get("radius", 10000))  # in meters
            radius_km = radius_m / 1000  # in meters
            keyword = body.get("keyword")

            if not lat or not lng or not keyword:
                return JsonResponse({"error": "Missing required parameters"}, status=400)

            # ---- 1. GOOGLE RESULTS ----
            google_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
            params = {
                "location": f"{lat},{lng}",
                "radius": radius_km,
                "keyword": keyword,
                "key": settings.MAP_API_KEY,
            }

            google_response = requests.get(google_url, params=params)
            google_data = google_response.json().get("results", [])

            # ---- 2. LOCAL DATABASE RESULTS ----
            def is_within_radius(obj_lat, obj_lng):
                return haversine_calculation(float(lat), float(lng), float(obj_lat), float(obj_lng)) <= radius_km

            nearby_courts = []
            for court in Courts.objects.all():
                if float(court.latitude) and float(court.longitude) and is_within_radius(float(court.latitude), float(court.longitude)):
                    court_image = CourtImage.objects.filter(court=court).first()
                    nearby_courts.append({
                        "name": court.name,
                        "type": "court",
                        "latitude": court.latitude,
                        "longitude": court.longitude,
                        "opening_time": court.open_time.strftime("%H:%M") if court.open_time else None,
                        "closing_time": court.close_time.strftime("%H:%M") if court.close_time else None,
                        "rating": getattr(court, "avg_rating", None),
                        "image": court_image.image.url if court_image and court_image.image else static('img/pickleit_logo.jpg'),
                        "contact": getattr(court, "contact", ""),
                    })

            nearby_clubs = []
            for club in Club.objects.all():
                if float(club.latitude) and float(club.longitude) and is_within_radius(float(club.latitude), float(club.longitude)):
                    club_image = ClubImage.objects.filter(club=club).first()
                    nearby_clubs.append({
                        "name": club.name,
                        "type": "club",
                        "latitude": club.latitude,
                        "longitude": club.longitude,
                        "opening_time": club.open_time.strftime("%H:%M") if club.open_time else None,
                        "closing_time": club.close_time.strftime("%H:%M") if club.close_time else None,
                        "rating": getattr(club, "overall_rating", None),
                        "image": club_image.image.url if club_image and club_image.image else static('img/pickleit_logo.jpg'),
                        "contact": getattr(club, "contact", ""),
                    })

            # ---- 3. RESPONSE ----
            return JsonResponse({
                "google_places": google_data,
                "local_courts": nearby_courts,
                "local_clubs": nearby_clubs,
            }, safe=False)

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Invalid request method"}, status=405)

@login_required(login_url="/user_side/")
def index(request):
    context = {
        "user_teams_count": 0,
        "balance": 0,
        "join_event_count":0,
        "completed_event_count":0,
        "match_history":[],
        "socail_feed_list":[],
        "invitation_list":[],
        "API_KEY": settings.MAP_API_KEY
    }
    player = Player.objects.filter(player=request.user).first()
    user_teams = Team.objects.filter(created_by=request.user)
    teams = list(player.team.all()) + list(user_teams)
    join_event = Leagues.objects.filter(registered_team__in = user_teams, is_complete=False).distinct()
    completed_event = Leagues.objects.filter(registered_team__in = user_teams, is_complete=True).distinct()
    user_teams_count = user_teams.count()
    balance = Wallet.objects.filter(user=request.user).first().balance
    join_event_count = join_event.count()
    completed_event_count = completed_event.count()
    
    match_history = Tournament.objects.filter(Q(team1__in=user_teams) | Q(team2__in=user_teams)).distinct()[:5]
    for match_ in match_history:
        if match_.team1 in teams:
            match_.opponent = match_.team2
        else:
            match_.opponent = match_.team1

        match_.scores = TournamentSetsResult.objects.filter(tournament=match_)
    
    user_likes = LikeFeed.objects.filter(
        user=request.user, post=OuterRef('pk')
    )
    
    # Annotate posts with is_like
    posts = socialFeed.objects.filter(block=False).annotate(is_like=Exists(user_likes)).order_by('-created_at')[:9]
    context["invitation_list"] = OpenPlayInvitation.objects.filter(user=request.user).order_by("-id")
    context["user_teams_count"] = user_teams_count
    context["balance"] = balance
    context["join_event_count"] = join_event_count
    context["completed_event_count"] = completed_event_count
    context["match_history"] = match_history
    context["socail_feed_list"] = posts
    return render(request, 'sides/index.html', context=context)

@login_required(login_url="/user_side/")
def user_list(request):
    # Get query parameters
    keyword = request.GET.get('keyword', '')
    latitude = request.GET.get('latitude', '')
    longitude = request.GET.get('longitude', '')
    gender = request.GET.get('gender', '')
    radius = request.GET.get('radius', '')  # Radius in kilometers
    page = request.GET.get('page', 1)
    # Base queryset
    users = User.objects.filter(is_active=True)

    # Apply keyword and gender filters
    if keyword:
        users = users.filter(
            Q(first_name__icontains=keyword) |
            Q(last_name__icontains=keyword) |
            Q(rank__icontains=keyword)
        )
    if gender:
        users = users.filter(gender=gender)

    # Apply location and radius filter
    user_data = []
    if latitude and longitude and radius:
        try:
            search_lat = float(latitude)
            search_lng = float(longitude)
            radius = float(radius)
            for user in users:
                if user.latitude not in ["null", "", None, "None"] and user.longitude not in ["null", "", None, "None"]:
                    distance = haversine(search_lat, search_lng, user.latitude, user.longitude)
                    if distance <= radius:
                        user_data.append({
                            'user': user,
                            'distance': round(distance, 2)
                        })
            # Sort by distance
            user_data.sort(key=lambda x: x['distance'])
        except ValueError:
            pass  # Invalid coordinates or radius, skip location filtering
    else:
        user_data = [{'user': user, 'distance': None} for user in users]

    # Pagination
    paginator = Paginator(user_data, 50)  # Show 12 users per page
    try:
        user_page = paginator.page(page)
    except PageNotAnInteger:
        user_page = paginator.page(1)
    except EmptyPage:
        user_page = paginator.page(paginator.num_pages)

    context = {
        'user_data': user_page,
        'keyword': keyword,
        'latitude': latitude,
        'longitude': longitude,
        'gender': gender,
        'radius': radius,
        'location': request.GET.get('location', ''),
        'API_KEY': settings.MAP_API_KEY,
    }
    return render(request, 'sides/user_list.html', context)


@login_required(login_url="/user_side/")
def player_profile(request, pk):
    user = get_object_or_404(User, id=int(pk))
    player = Player.objects.filter(player=user).first()
    user_teams = Team.objects.filter(created_by=user)
    teams = list(player.team.all()) + list(user_teams)

    # Match history queryset
    match_history_qs = Tournament.objects.filter(
        Q(team1__in=user_teams) | Q(team2__in=user_teams)
    ).distinct()

    for match_ in match_history_qs:
        match_.opponent = match_.team2 if match_.team1 in teams else match_.team1
        match_.scores = TournamentSetsResult.objects.filter(tournament=match_)

    # Social feed queryset
    social_feed_qs = socialFeed.objects.filter(user=user).order_by('-id')

    total_posts = social_feed_qs.count()
    followers = player.follower.count()
    followings = player.following.count()
    

    # Pagination for match_history
    match_page_number = request.GET.get('match_page')
    match_paginator = Paginator(match_history_qs, 6)  # Show 5 matches per page
    match_history_page = match_paginator.get_page(match_page_number)

    # Pagination for social_feed_list
    feed_page_number = request.GET.get('feed_page')
    feed_paginator = Paginator(social_feed_qs, 6)  # Show 5 posts per page
    social_feed_page = feed_paginator.get_page(feed_page_number)

    context = {
        "user": user,
        "total_posts":total_posts,
        "followers":followers,
        "followings":followings,
        "match_history": match_history_page,
        "social_feed_list": social_feed_page,
    }
    if request.user in player.follower.all():
        context["is_follow"] = True
    else:
        context["is_follow"] = False
    return render(request, 'sides/player_profile.html', context)


@login_required(login_url="/user_side/")
def follow_player(request, pk):
    user_player = Player.objects.filter(player=request.user).first()
    user = get_object_or_404(User, id=int(pk))
    player = Player.objects.filter(player=user).first()
    if request.method == 'POST':
        if request.user in player.follower.all():
            player.follower.remove(request.user)
            user_player.following.remove(user)
        else:
            player.follower.add(request.user)
            user_player.following.add(user)
        return redirect('user_side:player_profile', pk=pk)
    return redirect('user_side:player_profile', pk=pk)


@login_required(login_url="/user_side/")
def find_team_list(request):
    query = request.GET.get('q', '')
    team_type_filter = request.GET.get('team_type', '')
    teams = Team.objects.all()
    
    if query:
        teams = teams.filter(name__icontains=query)
    if team_type_filter:
        teams = teams.filter(team_type=team_type_filter)
    
    for team in teams:
        team.players = Player.objects.filter(team=team).count()
    
    paginator = Paginator(teams, 10)  # Show 10 teams per page
    page = request.GET.get('page')
    
    try:
        teams = paginator.page(page)
    except PageNotAnInteger:
        teams = paginator.page(1)
    except EmptyPage:
        teams = paginator.page(paginator.num_pages)
    
    return render(request, 'sides/teamlist_for_user.html', {
        "teams": teams,
        "query": query,
        "team_type_filter": team_type_filter,
    })

@login_required(login_url="/user_side/")
def find_my_team_list(request):
    query = request.GET.get('q', '')
    team_type_filter = request.GET.get('team_type', '')
    
    teams = Team.objects.filter(created_by = request.user)
    
    if query:
        teams = teams.filter(name__icontains=query)
    if team_type_filter:
        teams = teams.filter(team_type=team_type_filter)
    
    for team in teams:
        team.players = Player.objects.filter(team=team).count()
    
    paginator = Paginator(teams, 50)  # Show 10 teams per page
    page = request.GET.get('page')
    
    try:
        teams = paginator.page(page)
    except PageNotAnInteger:
        teams = paginator.page(1)
    except EmptyPage:
        teams = paginator.page(paginator.num_pages)
    return render(request, 'sides/my_team_list.html', {
        "teams": teams,
        "query": query,
        "team_type_filter": team_type_filter,
    })

@login_required(login_url="/user_side/")
def create_team_user_side(request):
    player_details = list(Player.objects.all().values("id", "player_full_name", "player__rank", "player__image", "player__gender", "player__id"))
    context = {"players":player_details, "team_info":[], "message":"","pre_player_ids":[], "operation":"Create", "button":"Submit"}
    if request.method == "POST":
        name = request.POST.get('team_name')
        location = request.POST.get('location')
        team_person = request.POST.get('team_person')
        team_type = request.POST.get('team_type')
        team_image = request.FILES.get('team_image')
        player_ids = request.POST.get('players', '').split(',')

        if not name and not team_person and not team_type:
            # return HttpResponse("Team name, team person and team type are required.")
            context["message"] = "Team name, team person and team type are required."
            return render(request, "sides/add_team.html", context)
        
        if Team.objects.filter(name = name).exists():
            # return HttpResponse("Team name already exists")
            context["message"] = "Team name already exists."
            return render(request, "sides/add_team.html", context)

        if team_person == "Two Person Team" and len(player_ids) == 2:
            if team_type == "Men":                
                players = Player.objects.filter(id__in=player_ids)
                for player in players:
                    if not player.player.gender == "Male":
                        # return HttpResponse("Select male players only.")  
                        context["message"] = "Select male players only."
                        return render(request, "sides/add_team.html", context)                          
                
                obj = GenerateKey()
                secret_key = obj.gen_team_key()
                team = Team.objects.create(
                    name=name,
                    secret_key=secret_key,
                    team_image=team_image,
                    team_person=team_person,
                    team_type=team_type,
                    created_by_id=request.user.id,
                    location=location
                )                            
                for player in players:                    
                    player.team.add(team)
                    notify_message = f"Hey {player.player_first_name}! You have been added to an awesome team - {team.name}"
                    title = "Team Created."
                    notify_edited_player(user_id=player.player.id, titel=title, message=notify_message)
        
                return redirect(reverse('user_side:find_my_team_list'))            

            elif team_type == "Women":                
                players = Player.objects.filter(id__in=player_ids)
                for player in players:
                    if not player.player.gender == "Female":
                        # return HttpResponse("Select female players only.")  
                        context["message"] = "Select female players only."
                        return render(request, "sides/add_team.html", context)  
                    
                obj = GenerateKey()
                secret_key = obj.gen_team_key()
                team = Team.objects.create(
                    name=name,
                    secret_key=secret_key,
                    team_image=team_image,
                    team_person=team_person,
                    team_type=team_type,
                    created_by_id=request.user.id,
                    location=location
                )                        
                        
                for player in players:
                    player.team.add(team)
                    notify_message = f"Hey {player.player_first_name}! You have been added to an awesome team - {team.name}"
                    title = "Team Created."
                    notify_edited_player(user_id=player.player.id, titel=title, message=notify_message)
        
                return redirect(reverse('user_side:find_my_team_list'))
                    
            elif team_type == "Co-ed":
                players = Player.objects.filter(id__in=player_ids)
                male_player = players.filter(player__gender='Male') 
                female_player = players.filter(player__gender='Female')    
                if len(male_player) == 1 and len(female_player) == 1:                    
                    obj = GenerateKey()
                    secret_key = obj.gen_team_key()
                    team = Team.objects.create(
                        name=name,
                        secret_key=secret_key,
                        team_image=team_image,
                        team_person=team_person,
                        team_type=team_type,
                        created_by_id=request.user.id,
                        location=location
                    )                        
                   
                    players = Player.objects.filter(id__in=player_ids)
                    for player in players:
                        player.team.add(team)
                        notify_message = f"Hey {player.player_first_name}! You have been added to an awesome team - {team.name}"
                        title = "Team Created."
                        notify_edited_player(user_id=player.player.id, titel=title, message=notify_message)
            
                    return redirect(reverse('user_side:find_my_team_list'))
                else:
                    context["message"] = "Select one male player and one female player."
                    return render(request, "sides/add_team.html", context)
                
        elif team_person == "Two Person Team" and len(player_ids) != 2:
            context["message"] = "Need to select two players."
            return render(request, "sides/add_team.html", context) 
          
        elif team_person == "One Person Team" and len(player_ids) == 1:
            if team_type == "Men":                
                players = Player.objects.filter(id__in=player_ids)
                if not players.first().player.gender == "Male": 
                    context["message"] = "Select male player only."
                    return render(request, "sides/add_team.html", context)     
                    
                obj = GenerateKey()
                secret_key = obj.gen_team_key()
                team = Team.objects.create(
                    name=name,
                    secret_key=secret_key,
                    team_image=team_image,
                    team_person=team_person,
                    team_type=team_type,
                    created_by_id=request.user.id,
                    location=location
                )                                  
                for player in players:
                    player.team.add(team)
                    notify_message = f"Hey {player.player_first_name}! You have been added to an awesome team - {team.name}"
                    title = "Team Created."
                    notify_edited_player(user_id=player.player.id, titel=title, message=notify_message)
        
                return redirect(reverse('user_side:find_my_team_list'))                       

            elif team_type == "Women":
                players = Player.objects.filter(id__in=player_ids)
                if not players.first().player.gender == "Female":       
                    context["message"] = "Select female player only."
                    return render(request, "sides/add_team.html", context)
                obj = GenerateKey()
                secret_key = obj.gen_team_key()
                team = Team.objects.create(
                    name=name,
                    secret_key=secret_key,
                    team_image=team_image,
                    team_person=team_person,
                    team_type=team_type,
                    created_by_id=request.user.id,
                    location=location
                )                                    
                for player in players:
                    player.team.add(team)
                    notify_message = f"Hey {player.player_first_name}! You have been added to an awesome team - {team.name}"
                    title = "Team Created."
                    notify_edited_player(user_id=player.player.id, titel=title, message=notify_message)
        
                return redirect(reverse('user_side:find_my_team_list'))
                    
        elif team_person == "One Person Team" and len(player_ids) != 1:
            context["message"] = "Need to select only one person."
            return render(request, "sides/add_team.html.html", context)

        return redirect('user_side:find_my_team_list')  # Redirect to team list

    return render(request, 'sides/add_team.html', context)

@login_required(login_url="/user_side/")
def search_players_user_side(request):
    query = request.GET.get('query', '')
    players = Player.objects.filter(player_full_name__icontains=query)[:10]

    player_data = [{
        'id': p.id, 
        'name': p.player_full_name, 
        'image': p.player.image.url if p.player.image else static('img/no_image.jpg'),  # Get image URL if available
    } for p in players]

    return JsonResponse({'players': player_data})

@login_required(login_url="/user_side/")
def team_view_user(request, team_id):
    context = {}
    team = get_object_or_404(Team, id=team_id)
    query = request.GET.get('q', '').strip()
    
    player = Player.objects.filter(player=request.user).first()
    if not player:
        context["error"] = "Player profile not found."
        return render(request, 'sides/match_history.html', context)

    players = Player.objects.filter(team=team)
    match_history = Tournament.objects.filter(Q(team1=team) | Q(team2=team)).order_by("-id")

    wins = match_history.filter(winner_team=team).count()
    losses = match_history.count() - wins
    total_matches = match_history.count()

    if query:
        match_history = match_history.filter(
            Q(team1__name__icontains=query) |
            Q(team2__name__icontains=query) |
            Q(leagues__name__icontains=query) |
            Q(match_number__icontains=query) |
            Q(leagues__team_type__name__icontains=query)
        ).order_by("-id")

    paginator = Paginator(match_history, 21)
    page_number = request.GET.get('page')
    paginated_matches = paginator.get_page(page_number)

    # Fetch match scores
    for match in paginated_matches:
        match.scores = TournamentSetsResult.objects.filter(tournament=match)

    context.update({
        "team_details": team,
        "players": players,  
        "match_history": paginated_matches if total_matches > 0 else None,  
        "total_matches": total_matches,
        "wins": wins,
        "losses": losses,
        "query": query,  
    })
    return render(request, 'sides/team_view.html', context)


@login_required(login_url="/user_side/")
def add_event(request):
    YOUR_API_KEY = settings.MAP_API_KEY
    PLAY_TYPE = PLAY_TYPE =(
            ("Group Stage", "Group Stage"),
            ("Round Robin", "Round Robin"),
            ("Single Elimination", "Single Elimination"),
            ("Individual Match Play", "Individual Match Play"),
        )
    LEAGUE_TYPE = LEAGUE_TYPE = (
            ("Invites only", "Invites only"),
            ("Open to all", "Open to all"),
        )
    # Get dynamic choices
    play_type_choices = [choice[0] for choice in PLAY_TYPE]
    team_type_choices = LeaguesTeamType.objects.all()
    person_type_choices = LeaguesPesrsonType.objects.all()
    league_type_choices = [choice[0] for choice in LEAGUE_TYPE]

    
    if request.method == "POST":
        try:
            # Initialize event_data dictionary for processing
            event_data = {
                'event_name': request.POST.get('event_name'),
                'event_description': request.POST.get('event_description'),
                'event_image': request.FILES.get('event_image'),
                'location': request.POST.get('location'),
                'max_team': request.POST.get('max_team'),
                'total_fee': request.POST.get('total_fee'),
                'registration_start': request.POST.get('registration_start'),
                'registration_end': request.POST.get('registration_end'),
                'event_start': request.POST.get('event_start'),
                'event_end': request.POST.get('event_end'),
                'start_rank': request.POST.get('start_rank'),
                'end_rank': request.POST.get('end_rank'),
                'registration_type': request.POST.get('registration_type'),
                'extra_fees': [],
                'cancel_policies': [],
                'play_configs': [],
                'invite_code': None,
                'latitude': request.POST.get('latitude'),
                'longitude': request.POST.get('longitude')
            }

            # Validate required fields
            required_fields = ['event_name', 'event_description', 'location', 'max_team', 
                             'total_fee', 'registration_start', 'registration_end', 
                             'event_start', 'event_end', 'registration_type']
            for field in required_fields:
                if not event_data[field]:
                    raise ValueError(f"{field.replace('_', ' ').title()} is required")

            # Validate league_type
            if event_data['registration_type'] not in league_type_choices:
                raise ValueError("Invalid league type selected")

            # Extra fees
            extra_fee_names = request.POST.getlist('extra_fee_name[]')
            extra_fee_amounts = request.POST.getlist('extra_fee_amount[]')
            for name, amount in zip(extra_fee_names, extra_fee_amounts):
                if name and amount:
                    try:
                        event_data['extra_fees'].append({
                            'name': name.strip(),
                            'amount': float(amount)
                        })
                    except ValueError:
                        raise ValueError("Invalid extra fee amount")

            # Cancellation policy
            cancel_durations = request.POST.getlist('cancel_duration[]')
            cancel_percentages = request.POST.getlist('cancel_percentage[]')
            for duration, percentage in zip(cancel_durations, cancel_percentages):
                if duration and percentage:
                    try:
                        event_data['cancel_policies'].append({
                            'duration': int(duration),
                            'percentage': float(percentage)
                        })
                    except ValueError:
                        raise ValueError("Invalid cancellation policy values")

            # Play configuration
            play_types = request.POST.getlist('play_type[]')
            team_types = request.POST.getlist('team_type[]')
            player_types = request.POST.getlist('player_type[]')
            court_round_robins = request.POST.getlist('court_round_robin[]')
            set_round_robins = request.POST.getlist('set_round_robin[]')
            point_round_robins = request.POST.getlist('point_round_robin[]')
            court_eliminations = request.POST.getlist('court_elimination[]')
            set_eliminations = request.POST.getlist('set_elimination[]')
            point_eliminations = request.POST.getlist('point_elimination[]')
            court_finals = request.POST.getlist('court_final[]')
            set_finals = request.POST.getlist('set_final[]')
            point_finals = request.POST.getlist('point_final[]')

            # Validate play configuration arrays length
            if not (len(play_types) == len(team_types) == len(player_types) ==
                    len(court_round_robins) == len(set_round_robins) == len(point_round_robins) ==
                    len(court_eliminations) == len(set_eliminations) == len(point_eliminations) ==
                    len(court_finals) == len(set_finals) == len(point_finals)):

                raise ValueError("Play configuration arrays have inconsistent lengths")

            for i in range(len(play_types)):
                if (play_types[i] and team_types[i] and player_types[i] and
                    court_round_robins[i] and set_round_robins[i] and point_round_robins[i] and
                    court_eliminations[i] and set_eliminations[i] and point_eliminations[i] and
                    court_finals[i] and set_finals[i] and point_finals[i]):
                    try:
                        # Validate play_type
                        if play_types[i] not in play_type_choices:
                            raise ValueError(f"Invalid play type: {play_types[i]}")
                        # Validate team_type
                        if not LeaguesTeamType.objects.filter(name=team_types[i]).exists():
                            raise ValueError(f"Invalid team type: {team_types[i]}")
                        # Validate person_type
                        if not LeaguesPesrsonType.objects.filter(name=player_types[i]).exists():
                            raise ValueError(f"Invalid person type: {player_types[i]}")
                            
                        event_data['play_configs'].append({
                            'play_type': play_types[i],
                            'team_type': team_types[i],
                            'player_type': player_types[i],
                            'round_robin': {
                                'court': int(court_round_robins[i]),
                                'set': int(set_round_robins[i]),
                                'point': int(point_round_robins[i])
                            },
                            'elimination': {
                                'court': int(court_eliminations[i]),
                                'set': int(set_eliminations[i]),
                                'point': int(point_eliminations[i])
                            },
                            'final': {
                                'court': int(court_finals[i]),
                                'set': int(set_finals[i]),
                                'point': int(point_finals[i])
                            }
                        })
                    except ValueError as e:
                        raise ValueError(f"Invalid play configuration values at index {i}: {str(e)}")

            # Generate invite code if registration_type is 'Invites only'
            if event_data['registration_type'] == 'Invites only':
                event_data['invite_code'] = str(uuid.uuid4())[:6].upper()

            # Create a Leagues instance for each play configuration
            for config in event_data['play_configs']:
                # Retrieve team_type and person_type instances
                team_type = LeaguesTeamType.objects.filter(name=config['team_type']).first()
                if not team_type:
                    raise ValueError(f"Team type {config['team_type']} does not exist")
                
                person_type = LeaguesPesrsonType.objects.filter(name=config['player_type']).first()
                if not person_type:
                    raise ValueError(f"Person type {config['player_type']} does not exist")

                # Create Leagues instance
                league = Leagues.objects.create(
                    secret_key=str(uuid.uuid4()),
                    name=event_data['event_name'],
                    description=event_data['event_description'],
                    image=event_data['event_image'],
                    complete_address=event_data['location'],
                    location=event_data['location'],
                    max_number_team=int(event_data['max_team']) if event_data['max_team'] else 2,
                    registration_fee=float(event_data['total_fee']) if event_data['total_fee'] else 5.0,
                    others_fees=event_data['extra_fees'] if event_data['extra_fees'] else None,
                    registration_start_date=event_data['registration_start'],
                    registration_end_date=event_data['registration_end'],
                    leagues_start_date=event_data['event_start'],
                    leagues_end_date=event_data['event_end'],
                    latitude=float(event_data['latitude']) if event_data['latitude'] else None,
                    longitude=float(event_data['longitude']) if event_data['longitude'] else None,
                    start_rank=float(event_data['start_rank']) if event_data['start_rank'] else None,
                    end_rank=float(event_data['end_rank']) if event_data['end_rank'] else None,
                    league_type=event_data['registration_type'],
                    invited_code=event_data['invite_code'],
                    created_by=request.user,
                    updated_by=request.user,
                    any_rank=False if event_data['start_rank'] or event_data['end_rank'] else True,
                    policy=bool(event_data['cancel_policies']),
                    play_type=config['play_type'],
                    team_type=team_type,
                    team_person=person_type
                )

                # Save cancellation policies
                for policy in event_data['cancel_policies']:
                    LeaguesCancellationPolicy.objects.create(
                        league=league,
                        within_day=policy['duration'],
                        refund_percentage=policy['percentage']
                    )

                
                # Create LeaguesPlayType entry
                play_type_data = [
                    {
                        "name": "Round Robin",
                        "number_of_courts": config['round_robin']['court'],
                        "sets": config['round_robin']['set'],
                        "point": config['round_robin']['point']
                    },
                    {
                        "name": "Elimination",
                        "number_of_courts": config['elimination']['court'],
                        "sets": config['elimination']['set'],
                        "point": config['elimination']['point']
                    },
                    {
                        "name": "Final",
                        "number_of_courts": config['final']['court'],
                        "sets": config['final']['set'],
                        "point": config['final']['point']
                    }
                ]

                LeaguesPlayType.objects.create(
                    type_name=config['play_type'],
                    league_for=league,
                    data=play_type_data
                )

            messages.success(request, f"Successfully created {len(event_data['play_configs'])} events!")
            return redirect('user_side:event_user')

        except ValueError as e:
            messages.error(request, f"Error creating events: {str(e)}")
        except Exception as e:
            messages.error(request, f"Unexpected error: {str(e)}")
            
        return render(request, 'sides/add_event_form.html', {
            'MAP_API_KEY': YOUR_API_KEY,
            'event_data': event_data,
            'play_type_choices': play_type_choices,
            'team_type_choices': team_type_choices,
            'person_type_choices': person_type_choices,
            'league_type_choices': league_type_choices
        })

    return render(request, 'sides/add_event_form.html', {
        'MAP_API_KEY': YOUR_API_KEY,
        'play_type_choices': play_type_choices,
        'team_type_choices': team_type_choices,
        'person_type_choices': person_type_choices,
        'league_type_choices': league_type_choices
    })

@login_required(login_url="/user_side/")
def event(request):
    query = request.GET.get('q', '')
    team_type_filter = request.GET.get('team_type', 'all')
    my_event_type_filter = request.GET.get('my_event_type', 'all')

    # Base queryset: Exclude "Individual Match Play" and order by start date
    leagues = Leagues.objects.exclude(team_type__name="Open-team")

    # Apply my_event_type_filter
    if my_event_type_filter != 'all':
        if my_event_type_filter == 'org_event':
            leagues = leagues.filter(created_by=request.user) | leagues.filter(add_organizer=request.user)
            leagues = leagues.distinct()
        elif my_event_type_filter == 'join_event':
            player = Player.objects.filter(player=request.user).first()
            if player:
                teams = player.team.all()
                leagues = leagues.filter(registered_team__in=teams, is_complete=False).distinct()
            else:
                leagues = Leagues.objects.none()  # No leagues if user is not a player

    # Apply team_type_filter
    today = datetime.now().date()
    if team_type_filter == 'all':
        pass
    elif team_type_filter == 'Open':
        leagues = leagues.filter(registration_start_date__date__lte=today, registration_end_date__date__gte=today)
    elif team_type_filter == 'Upcoming':
        leagues = leagues.filter(leagues_start_date__date__gte=today, is_complete=False)
    elif team_type_filter == 'Ongoing':
        leagues = leagues.filter(leagues_start_date__date__lte=today, leagues_end_date__date__gte=today, is_complete=False)
    elif team_type_filter == 'Past':
        leagues = leagues.filter(leagues_end_date__date__lte=today, is_complete=True)

    # Apply search query if provided
    if query:
        leagues = leagues.filter(name__icontains=query)

    # Order the final queryset
    leagues = leagues.order_by('-leagues_start_date')

    # Add pagination
    paginator = Paginator(leagues, 50)  # Show 10 leagues per page
    page = request.GET.get('page', 1)

    try:
        leagues_page = paginator.page(page)
    except PageNotAnInteger:
        leagues_page = paginator.page(1)
    except EmptyPage:
        leagues_page = paginator.page(paginator.num_pages)

    return render(request, 'sides/event.html', {
        'leagues': leagues_page,
        'team_type_filter': team_type_filter,
        'my_event_type_filter': my_event_type_filter,
        'text': query
    })

###open play
def openplay_list(request):
    query = request.GET.get('q', '')
    team_type_filter = request.GET.get('team_type', 'all')
    my_event_type_filter = request.GET.get('my_event_type', 'all')
    user = request.user
    team_type = "Open-team"
    team_type_ins = get_object_or_404(LeaguesTeamType, name=team_type)
    created_list = list(Leagues.objects.filter(team_type=team_type_ins).values_list('id', flat=True).distinct())
    invited_list = list(OpenPlayInvitation.objects.filter(user=user).values_list('event_id', flat=True).distinct())
    openplay_leagues_list = list(set(created_list + invited_list))
    leagues = Leagues.objects.filter(id__in=openplay_leagues_list)
    
    # Apply my_event_type_filter
    if my_event_type_filter != 'all':
        if my_event_type_filter == 'org_event':
            leagues = leagues.filter(created_by=request.user) | leagues.filter(add_organizer=request.user)
            leagues = leagues.distinct()
        elif my_event_type_filter == 'join_event':
            player = Player.objects.filter(player=request.user).first()
            if player:
                teams = player.team.all()
                leagues = leagues.filter(registered_team__in=teams, is_complete=False).distinct()
            else:
                leagues = Leagues.objects.none()  # No leagues if user is not a player

    # Apply team_type_filter
    today = datetime.now().date()
    if team_type_filter == 'all':
        pass
    elif team_type_filter == 'Open':
        leagues = leagues.filter(registration_start_date__date__lte=today, registration_end_date__date__gte=today)
    elif team_type_filter == 'Upcoming':
        leagues = leagues.filter(leagues_start_date__date__gte=today, is_complete=False)
    elif team_type_filter == 'Ongoing':
        leagues = leagues.filter(leagues_start_date__date__lte=today, leagues_end_date__date__gte=today, is_complete=False)
    elif team_type_filter == 'Past':
        leagues = leagues.filter(leagues_end_date__date__lte=today, is_complete=True)

    if query:
        leagues = leagues.filter(name__icontains=query)

    leagues = leagues.order_by('-leagues_start_date')

    # Add pagination
    paginator = Paginator(leagues, 50)  # Show 10 leagues per page
    page = request.GET.get('page', 1)

    try:
        leagues_page = paginator.page(page)
    except PageNotAnInteger:
        leagues_page = paginator.page(1)
    except EmptyPage:
        leagues_page = paginator.page(paginator.num_pages)


    return render(request, 'sides/open_play_list.html', {
        'leagues': leagues_page,
        'team_type_filter': team_type_filter,
        'my_event_type_filter': my_event_type_filter,
        'text': query
    })


def create_openplay(request):
    if request.method == 'POST':
        # Collect form data
        form_data = {
            'open_play_type': request.POST.get('open_play_type', '').strip(),
            'play_type': request.POST.get('play_type', '').strip(),
            'location': request.POST.get('location', '').strip(),
            'latitude': request.POST.get('latitude', ''),
            'longitude': request.POST.get('longitude', ''),
            'fees': request.POST.get('fees', '0').strip(),
            'description': request.POST.get('description', '').strip(),
            'date': request.POST.get('date', '').strip(),
            'time': request.POST.get('time', '').strip(),
            'courts': request.POST.get('courts', '').strip(),
            'sets': request.POST.get('sets', '').strip(),
            'points': request.POST.get('points', '').strip(),
            'players': request.POST.getlist('players', [])
        }

        # Validate form data
        errors = {}
        if not form_data['open_play_type']:
            errors['open_play_type'] = 'Open play type is required'
        if not form_data['play_type']:
            errors['play_type'] = 'Play type is required'
        if not form_data['location']:
            errors['location'] = 'Location is required'
        try:
            form_data['latitude'] = float(form_data['latitude'])
            form_data['longitude'] = float(form_data['longitude'])
        except (ValueError, TypeError):
            errors['location'] = 'Valid location coordinates are required'
        try:
            form_data['fees'] = float(form_data['fees'])
        except (ValueError, TypeError):
            form_data['fees'] = 0.0
        if not form_data['date']:
            errors['date'] = 'Date is required'
        if not form_data['time']:
            errors['time'] = 'Time is required'
        try:
            form_data['courts'] = int(form_data['courts'])
            if form_data['courts'] < 1:
                raise ValueError
        except (ValueError, TypeError):
            errors['courts'] = 'Valid number of courts is required'
        try:
            form_data['sets'] = int(form_data['sets'])
            if form_data['sets'] < 1:
                raise ValueError
        except (ValueError, TypeError):
            errors['sets'] = 'Valid number of sets is required'
        try:
            form_data['points'] = int(form_data['points'])
            if form_data['points'] < 1:
                raise ValueError
        except (ValueError, TypeError):
            errors['points'] = 'Valid number of points is required'
        if not form_data['players']:
            errors['players'] = 'At least one player must be selected'

        # Validate date and time
        try:
            event_datetime = datetime.strptime(
                f"{form_data['date']} {form_data['time']}",
                "%Y-%m-%d %H:%M"
            )
            if event_datetime < datetime.now():
                errors['date'] = 'Event cannot be scheduled in the past'
        except ValueError:
            errors['date'] = 'Invalid date or time format'

        if errors:
            return render(request, 'sides/create_open_play.html', {
                'MAP_API_KEY': settings.MAP_API_KEY,
                'form_data': form_data,
                'errors': errors
            })

        try:
            with transaction.atomic():
                # Generate secret key
                secret_key = GenerateKey().gen_leagues_key()
                tournament_name = f"PICKLEIT OPEN - PLAY {secret_key[-5:]}"
                team_type = LeaguesTeamType.objects.filter(name='Open-team').first()
                if not team_type:
                    messages.error(request, f"Invalid team type: {form_data['team_type']}")
                    return render(request, 'sides/create_open_play.html', {
                        'MAP_API_KEY': settings.MAP_API_KEY,
                        'form_data': form_data,
                        'errors': {'team_type': 'Invalid team type selected'}
                    })
                team_person = LeaguesPesrsonType.objects.filter(name=form_data['play_type']).first()
                if not team_person:
                    messages.error(request, f"Invalid open play type: {form_data['play_type']}")
                    return render(request, 'sides/create_open_play.html', {
                        'MAP_API_KEY': settings.MAP_API_KEY,
                        'form_data': form_data,
                        'errors': {'open_play_type': 'Invalid  person type selected'}
                    })
                # Create league
                open_play_event = Leagues(
                    secret_key=secret_key,
                    name=tournament_name,
                    leagues_start_date=event_datetime,
                    registration_fee=form_data['fees'],
                    others_fees={},
                    image=None,
                    description=form_data['description'],
                    play_type=form_data['open_play_type'],
                    team_type=team_type,  # Fixed from team_type__name
                    team_person = team_person,  # Fixed from team_person__name
                    max_number_team=500,
                    location=form_data['location'],
                    latitude=form_data['latitude'],
                    longitude=form_data['longitude'],
                    created_by=request.user,
                    league_type='Open to all',
                )
                open_play_event.save()

                # Invite players
                title = "Created Open Play event invitation"
                for player_uuid in form_data['players']:
                    try:
                        player = User.objects.get(uuid=player_uuid)
                        notify_message = f"{request.user.first_name} sent you an invitation for OpenPlay, Please show your interest"
                        OpenPlayInvitation.objects.create(
                            user=player,
                            event=open_play_event,
                            invited_by = request.user,
                            status='Pending'
                        )
                        notify_edited_player(player.id, title, notify_message)
                    except User.DoesNotExist:
                        messages.warning(request, f"Player with UUID {player_uuid} not found")
                        continue

                messages.success(request, "Open Play event created successfully!")
                return redirect(reverse('user_side:openplay_list'))

        except Exception as e:
            messages.error(request, f"Failed to create Open Play event: {str(e)}")
            return render(request, 'sides/create_open_play.html', {
                'MAP_API_KEY': settings.MAP_API_KEY,
                'form_data': form_data,
                'errors': {'general': str(e)}
            })

    # For GET requests
    return render(request, 'sides/create_open_play.html', {
        'MAP_API_KEY': settings.MAP_API_KEY,
        'form_data': {}
    })

def search_users(request):
    query = request.GET.get('keyword', None).strip()
    category = request.GET.get('category', None).strip()
    latitude = request.GET.get('latitude', None).strip()
    longitude = request.GET.get('longitude', None).strip()
    radius = request.GET.get('radius', '100').strip()
    min_rank = request.GET.get('min_rank', None).strip()
    max_rank = request.GET.get('max_rank', None).strip()
    # print(f"Search query: {query}, Category: {category}, Latitude: {latitude}, Longitude: {longitude}, Radius: {radius}, Min Rank: {min_rank}, Max Rank: {max_rank}")
    players = User.objects.all()

    if query:
        players = players.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(username__icontains=query)
        )

    if category:
        if category == "Women":
            players = players.filter(gender="Female")
        elif category == "Men":
            players = players.filter(gender="Male")

    if latitude and longitude and radius:
        # try:
        user_location = (float(latitude), float(longitude))
        radius = float(radius)
        
        # Filter players by distance
        filtered_players = []
        for player in players:
            if player.latitude not in [None, "null", "", " "] and player.longitude not in [None, "null", "", " "]:
                distance = haversine(
                    user_location,
                    (float(player.latitude), float(player.longitude)),
                    unit=Unit.KILOMETERS
                )
                # print(distance, radius, player.first_name, player.last_name)
                if distance <= radius:
                    filtered_players.append(player)
        # print(filtered_players)
        players = filtered_players
        # except (ValueError, TypeError):
        #     pass  # Invalid coordinates or radius, skip location filter

    if min_rank:
        try:
            players = [p for p in players if p.rank is not None and p.rank >= float(min_rank)]
        except ValueError:
            pass  # Invalid min_rank, skip filter

    if max_rank:
        try:
            players = [p for p in players if p.rank is not None and p.rank <= float(max_rank)]
        except ValueError:
            pass  # Invalid max_rank, skip filter

    player_data = [
        {
            "id": player.id,
            "uuid": str(player.uuid),
            "name": f"{player.first_name} {player.last_name}",
            "image": player.image.url if player.image and player.image.url not in ["null", None, "", " "] else static('img/no_image.jpg'),
            "rank": float(player.rank) if player.rank else None,
            "get_full_name": f"{player.first_name} {player.last_name}"
        }
        for player in players
    ]

    return JsonResponse({"players": player_data})

def invitation_list(request):
    user = request.user
    invitations = OpenPlayInvitation.objects.filter(user=user).exclude(status="Declined").order_by("-id")
    context = {
        "invitation_list": invitations,
    }
    return render(request, 'sides/invitation_list.html', context)

@login_required(login_url="/user_side/")
def event_view(request, event_id):
    context = {}
    user = request.user
    today = timezone.now()
    event = get_object_or_404(Leagues, id=event_id)
    context["event"] = event
    context["league_type"] = LeaguesPlayType.objects.filter(league_for=event)
    context["policy"] = LeaguesCancellationPolicy.objects.filter(league=event)
    context["all_join_teams"] = event.registered_team.all()
    context["organizer"] = user == event.created_by

    user_player = Player.objects.filter(player_email=user.email).first()
    player_teams = user_player.team.all() if user_player else Team.objects.none()

    # Get teams created by the user
    created_teams = Team.objects.filter(created_by=user)
    # Get registered teams
    registered_teams = event.registered_team.all()
    # Filter only those that are in the registered teams
    user_event_teams = (player_teams | created_teams).distinct().filter(id__in=registered_teams.values_list('id', flat=True))
    # Add to context
    context["user_registered_teams"] = user_event_teams 

    # Calculate total fees
    fees = event.registration_fee
    others_fees = event.others_fees
    if others_fees:
        for val in others_fees:
            if isinstance(val, (int, float)):
                fees += val
            elif isinstance(val, str) and val.isdigit():
                fees += int(val)
    context["total_fees"] = fees

    # Wallet balance
    try:
        wallet = Wallet.objects.filter(user=user).first()
        balance = wallet.balance
    except:
        balance = 0
    context["balance"] = balance

    # My team
    my_team = Team.objects.filter(created_by=user)
    team_type = event.team_type
    team_person = event.team_person
    if team_type:
        my_team = my_team.filter(team_type=team_type)
    if team_person:
        my_team = my_team.filter(team_person=team_person)
    for team in my_team:
        team.players = Player.objects.filter(team=team)
    context["my_team"] = my_team

    # Matches
    matches = Tournament.objects.filter(leagues=event)
    for match in matches:
        match.score = TournamentSetsResult.objects.filter(tournament=match)
    context["matches"] = matches

    # Team stats
    team_stats = {}
    for match in matches:
        if match.team1 and match.team2:
            if match.team1 not in team_stats:
                team_stats[match.team1] = {"played": 0, "wins": 0, "losses": 0, "draws": 0, "points": 0}
            if match.team2 not in team_stats:
                team_stats[match.team2] = {"played": 0, "wins": 0, "losses": 0, "draws": 0, "points": 0}

            team_stats[match.team1]["played"] += 1
            team_stats[match.team2]["played"] += 1

            if match.is_drow:
                team_stats[match.team1]["draws"] += 1
                team_stats[match.team2]["draws"] += 1
                team_stats[match.team1]["points"] += 1
                team_stats[match.team2]["points"] += 1
            elif match.winner_team:
                team_stats[match.winner_team]["wins"] += 1
                team_stats[match.winner_team]["points"] += 3
                loser_team = match.team1 if match.winner_team == match.team2 else match.team2
                team_stats[loser_team]["losses"] += 1

    # Point table
    point_table = []
    play_type_check_win = event.play_type
    all_group_details = RoundRobinGroup.objects.filter(league_for=event)
    for grp in all_group_details:
        teams = grp.all_teams.all()
        group_score_point_table = []
        for team in teams:
            team_score = {}
            total_match_details = Tournament.objects.filter(leagues=event, match_type="Round Robin").filter(Q(team1=team) | Q(team2=team))
            completed_match_details = total_match_details.filter(is_completed=True)
            win_match_details = completed_match_details.filter(winner_team=team).count()
            loss_match_details = completed_match_details.filter(loser_team=team).count()
            drow_match = len(completed_match_details) - (win_match_details + loss_match_details)
            match_list = list(total_match_details.values_list("id", flat=True))
            for_score = 0
            against_score = 0
            for sc in match_list:
                co_team_position = Tournament.objects.filter(id=sc).first()
                set_score = TournamentSetsResult.objects.filter(tournament_id=sc)
                if co_team_position.team1 == team:
                    for_score += sum(list(set_score.values_list("team1_point", flat=True)))
                    against_score += sum(list(set_score.values_list("team2_point", flat=True)))
                else:
                    for_score += sum(list(set_score.values_list("team2_point", flat=True)))
                    against_score += sum(list(set_score.values_list("team1_point", flat=True)))
                
            point = (win_match_details * 3) + (drow_match * 1)
            team_score["uuid"] = str(team.uuid)
            team_score["secret_key"] = team.secret_key
            team_score["name"] = team.name
            team_score["completed_match"] = len(completed_match_details)
            team_score["win_match"] = win_match_details
            team_score["loss_match"] = loss_match_details
            team_score["drow_match"] = drow_match
            team_score["for_score"] = for_score
            team_score["against_score"] = against_score
            team_score["point"] = point
            group_score_point_table.append(team_score)

        # Sort group score point table
        group_score_point_table = sorted(group_score_point_table, key=lambda x: (x['point'], x['for_score']), reverse=True)

        # Update winner for Round Robin
        if play_type_check_win == "Round Robin":
            total_tournament = Tournament.objects.filter(leagues=event, match_type="Round Robin", leagues__play_type="Round Robin")
            completed_tournament = total_tournament.filter(is_completed=True)
            if total_tournament.count() == completed_tournament.count() and group_score_point_table:
                winner_team = Team.objects.filter(uuid=group_score_point_table[0]["uuid"]).first()
                event.winner_team = winner_team
                event.is_complete = True
                event.save()
                context["winner_team"] = winner_team.name

        grp_data = {
            "id": grp.id,
            "court": grp.court,
            "league_for_id": grp.league_for_id,
            "all_games_status": grp.all_games_status,
            "all_teams": group_score_point_table,
            # "tournament": list(tournament_details_group),
            "seleced_teams_id": grp.seleced_teams_id
        }
        point_table.append(grp_data)

    context["point_table"] = point_table

    # Other context
    if event.registered_team.all().count() == 0 and event.created_by == user:
        context["is_del"] = True
    else:
        context["is_del"] = False
    if event.leagues_start_date > today:
        context["is_unregister"] = True
    else:
        context["is_unregister"] = False
    teams = Player.objects.filter(player=user).first().team.all() if Player.objects.filter(player=user).exists() else []
    if event.registered_team.filter(id__in=teams).exists() and not event.is_complete and Tournament.objects.filter(leagues=event).exists():
        context["score_update"] = True
    elif user == event.created_by and Tournament.objects.filter(leagues=event).exists():
        context["score_update"] = True
    else:
        context["score_update"] = False
    if event.registration_end_date:
        context["is_join"] = event.registration_end_date.date() >= today.date()
    else:
        context["is_join"] = False
    sorted_teams = sorted(team_stats.items(), key=lambda x: x[1]["points"], reverse=True)
    context["sorted_teams"] = sorted_teams
    context["groups"] = RoundRobinGroup.objects.filter(league_for=event)

    return render(request, 'sides/event_view.html', context=context)



def get_cancellation_policy(request):
    league_id = request.GET.get('league_id')
    try:
        league = Leagues.objects.get(id=league_id)
        policies = LeaguesCancellationPolicy.objects.filter(league=league).order_by('within_day')
        if policies.exists():
            # Convert policies to readable format
            policy_text = ""
            for policy in policies:
                policy_text += f"If cancelled within {policy.within_day} day(s): {policy.refund_percentage}% refund<br>"
            return JsonResponse({'has_policy': True, 'policy': policy_text})
        else:
            return JsonResponse({'has_policy': False})
    except Leagues.DoesNotExist:
        return JsonResponse({'has_policy': False})
    

@csrf_exempt
def remove_team_from_league(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            team_id = data.get('team_id')
            league_id = data.get('league_id')
            user = request.user  # You may need to ensure the user is authenticated

            league = Leagues.objects.get(id=league_id)
            team = Team.objects.get(id=team_id)
            policies = LeaguesCancellationPolicy.objects.filter(league=league).order_by('within_day')

            # Calculate refund based on policy
            refund_amount = 0
            if policies.exists():  # Only check if `policy` flag is True
                
                days_until_start = (league.leagues_start_date - timezone.now()).days
                # print(days_until_start)

                # Find applicable policy
                for policy in policies:
                    if days_until_start <= policy.within_day:
                        refund_amount = (Decimal(policy.refund_percentage) / 100) * Decimal(league.registration_fee)
                        # print(refund_amount)
                        break

            # Add refund to user's wallet
            if refund_amount > 0:
                wallet, created = Wallet.objects.get_or_create(user=user)
                wallet.balance += refund_amount
                wallet.save()
                # print(wallet.balance)

                organizer_amount = (Decimal(refund_amount) * Decimal(settings.ORGANIZER_PERCENTAGE)) / Decimal(100)
                admin_amount = (Decimal(refund_amount) * Decimal(settings.ADMIN_PERCENTAGE)) / Decimal(100)

                # ✅ Update admin wallet
                admin_wallet = Wallet.objects.filter(user__is_superuser=True).first()
                if admin_wallet:
                    admin_wallet.balance = Decimal(admin_wallet.balance - admin_amount)
                    admin_wallet.save()
                
                # ✅ Update organizer wallet
                organizer_wallet = Wallet.objects.filter(user=league.created_by).first()
                if organizer_wallet:
                    organizer_wallet.balance = Decimal(str(organizer_wallet.balance)) - organizer_amount
                    organizer_wallet.save()

            # Remove team from league
            league.registered_team.remove(team)

            return JsonResponse({
                'success': True,
                'refund': str(refund_amount)
            })

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)


@login_required(login_url="/user_side/")
def event_delete(request, event_id):
    event = get_object_or_404(Leagues, id=event_id)
    
    if event.registered_team.all().count() == 0 and event.created_by == request.user:
        try:
            # Delete related cancellation policies and play types
            LeaguesCancellationPolicy.objects.filter(league=event).delete()
            LeaguesPlayType.objects.filter(league_for=event).delete()
            # Delete the event
            event.delete()
            # messages.success(request, "Event deleted successfully.")
            return redirect('user_side:event_user')
        except Exception as e:
            # messages.error(request, f"Error deleting event: {str(e)}")
            return redirect('user_side:event_user')
    else:
        # messages.error(
        #     request,
        #     "You cannot delete this event because it has registered teams. Please contact an admin to delete the event."
        # )
        return redirect(reverse('user_side:event_view', kwargs={'event_id': event_id}))
 
@login_required(login_url="/user_side/")
def start_tournament(request, event_id):
    """View to start a tournament and assign matches based on play type."""
    event = get_object_or_404(Leagues, id=event_id)
    if request.user != event.created_by:
        messages.error(request, "You are not authorized to start this tournament.")
        return redirect('user_side:event_view', event_id=event_id)

    # Fetch play type details
    playtype_details = get_playtype_details(event)
    registered_teams = event.registered_team.all()
    team_ids = [team.id for team in registered_teams]
    max_teams = event.max_number_team

    # Validate team registration
    if len(team_ids) != max_teams:
        messages.error(request, "All teams are not registered.")
        return redirect('user_side:event_view', event_id=event_id)

    # Send tournament start notifications
    send_tournament_notifications(event, team_ids)

    # Process based on play type
    playtype = event.play_type
    if playtype == "Single Elimination":
        result = handle_single_elimination(event, team_ids, playtype_details)
    elif playtype == "Group Stage":
        result = handle_group_stage(event, team_ids, playtype_details)
    elif playtype == "Round Robin":
        result = handle_round_robin(event, team_ids, playtype_details)
    elif playtype == "Individual Match Play":
        result = handle_individual_match_play(event, team_ids, playtype_details)
    else:
        messages.error(request, "Invalid play type.")
        return redirect('user_side:event_view', event_id=event_id)

    # Display result message
    messages.success(request, result["message"]) if result["status"] == status.HTTP_200_OK else messages.error(request, result["message"])
    return redirect('user_side:event_view', event_id=event_id)

def get_playtype_details(event):
    """Fetch and return play type details for the event."""
    playtype_details = LeaguesPlayType.objects.filter(league_for=event).first()
    if playtype_details:
        return playtype_details.data
    return [
        {"name": "Round Robin", "number_of_courts": 0, "sets": 0, "point": 0},
        {"name": "Elimination", "number_of_courts": 0, "sets": 0, "point": 0},
        {"name": "Final", "number_of_courts": 0, "sets": 0, "point": 0}
    ]

def send_tournament_notifications(event, team_ids):
    """Send notifications to team managers and players when tournament starts."""
    league_name = event.name
    for team_id in team_ids:
        team = Team.objects.get(id=team_id)
        team_manager = team.created_by
        notify_edited_player(
            team_manager.id,
            "Start Tournament",
            f"The tournament {league_name} has started."
        )
        players = Player.objects.filter(team__id=team_id)
        for player in players:
            notify_edited_player(
                player.player.id,
                "Start Tournament",
                f"Player, get ready! The tournament {league_name} has started."
            )

def calculate_team_rank(team):
    """Calculate the average rank of a team based on its players."""
    players = team.player_set.all()
    if not players.exists():
        return 0
    total_rank = sum(float(player.player.rank or '1') for player in players)
    return total_rank / players.count()

def create_group(team_ids, num_parts):
    """Create balanced groups of teams based on their ranks."""
    num_parts = int(num_parts)
    if num_parts <= 0:
        return {"status": status.HTTP_400_BAD_REQUEST, "message": "Number of parts should be greater than zero."}

    teams = Team.objects.filter(id__in=team_ids)
    team_list = [(team.id, calculate_team_rank(team)) for team in teams]
    team_list.sort(key=lambda x: x[1], reverse=True)
    sorted_team_ids = [team[0] for team in team_list]
    total_teams = len(sorted_team_ids)
    teams_per_group = total_teams // num_parts
    remainder = total_teams % num_parts

    group_list = [[] for _ in range(num_parts)]
    for i, team_id in enumerate(sorted_team_ids):
        group_idx = i % num_parts
        group_list[group_idx].append(team_id)

    max_group_size = teams_per_group + (1 if remainder > 0 else 0)
    for i in range(num_parts):
        if len(group_list[i]) > max_group_size:
            group_list[i] = group_list[i][:max_group_size]

    return {"status": status.HTTP_200_OK, "message": "Groups created", "groups": group_list}

def make_shuffle(input_list):
    """Shuffle pairs of teams for elimination rounds."""
    result = []
    try:
        for i in range(0, len(input_list), 2):
            result.extend([
                input_list[i][0],    # A1
                input_list[i+1][1],  # B2
                input_list[i][1],    # A2
                input_list[i+1][0]   # B1
            ])
    except IndexError:
        pass
    return result

def create_tournament_match(event, team1_id, team2_id, match_type, round_number, court_num, sets, points, match_number, group_id=None):
    """Create a tournament match with the given parameters."""
    obj = GenerateKey()
    secret_key = obj.generate_league_unique_id()
    Tournament.objects.create(
        set_number=sets,
        court_num=court_num,
        points=points,
        court_sn=court_num,
        match_number=match_number,
        secret_key=secret_key,
        leagues=event,
        team1_id=team1_id,
        team2_id=team2_id,
        match_type=match_type,
        elimination_round=round_number,
        group_id=group_id
    )

def handle_single_elimination(event, team_ids, playtype_details):
    """Handle Single Elimination tournament logic."""
    court_num_e = int(playtype_details[1]["number_of_courts"])
    set_num_e = int(playtype_details[1]["sets"])
    point_num_e = int(playtype_details[1]["point"])
    court_num_f = int(playtype_details[2]["number_of_courts"])
    set_num_f = int(playtype_details[2]["sets"])
    point_num_f = int(playtype_details[2]["point"])

    if len(team_ids) != event.max_number_team:
        return {"status": status.HTTP_200_OK, "message": "All teams are not joined"}

    check_pre_game = Tournament.objects.filter(leagues=event)
    if check_pre_game.exists():
        check_leagues_com = check_pre_game.filter(is_completed=True)
        if len(check_pre_game) == len(check_leagues_com) and check_leagues_com.exists():
            pre_match_round = check_leagues_com.last().elimination_round
            pre_round_details = Tournament.objects.filter(leagues=event, elimination_round=pre_match_round)
            teams = list(pre_round_details.values_list("winner_team_id", flat=True))
            pre_match_number = check_leagues_com.last().match_number
            court_num = 0

            if len(teams) == 4:
                match_type = "Semi Final"
                sets, courts, points = set_num_e, court_num_e, point_num_e
            elif len(teams) == 2:
                match_type = "Final"
                sets, courts, points = set_num_f, court_num_f, point_num_f
            else:
                match_type = "Elimination Round"
                sets, courts, points = set_num_e, court_num_e, point_num_e
                pre_match_round += 1

            random.shuffle(teams)
            match_number_now = pre_match_number
            for i in range(0, len(teams), 2):
                court_num = (court_num % courts) + 1
                match_number_now += 1
                create_tournament_match(
                    event, teams[i], teams[i+1], match_type, 0 if match_type in ["Semi Final", "Final"] else pre_match_round,
                    court_num, sets, points, match_number_now
                )
            return {"status": status.HTTP_200_OK, "message": f"Matches created for {match_type}"}
        return {"status": status.HTTP_200_OK, "message": "Previous Round is not completed or not updated"}
    else:
        sets, courts, points = set_num_e, court_num_e, point_num_e
        match_number_now = 0
        court_num = 0
        random.shuffle(team_ids)

        if len(team_ids) == 4:
            match_type = "Semi Final"
        elif len(team_ids) == 2:
            match_type = "Final"
            sets, courts, points = set_num_f, court_num_f, point_num_f
        else:
            match_type = "Elimination Round"

        for i in range(0, len(team_ids), 2):
            court_num = (court_num % courts) + 1
            match_number_now += 1
            create_tournament_match(
                event, team_ids[i], team_ids[i+1], match_type, 1 if match_type == "Elimination Round" else 0,
                court_num, sets, points, match_number_now
            )
        return {"status": status.HTTP_200_OK, "message": f"Matches created for {match_type}"}

def handle_group_stage(event, team_ids, playtype_details):
    """Handle Group Stage tournament logic."""
    court_num_r = int(playtype_details[0]["number_of_courts"])
    set_num_r = int(playtype_details[0]["sets"])
    point_num_r = int(playtype_details[0]["point"])
    court_num_e = int(playtype_details[1]["number_of_courts"])
    set_num_e = int(playtype_details[1]["sets"])
    point_num_e = int(playtype_details[1]["point"])
    court_num_f = int(playtype_details[2]["number_of_courts"])
    set_num_f = int(playtype_details[2]["sets"])
    point_num_f = int(playtype_details[2]["point"])

    check_pre_game = Tournament.objects.filter(leagues=event)
    if check_pre_game.exists():
        all_round_robin_match = Tournament.objects.filter(leagues=event)
        all_completed_round_robin_match = Tournament.objects.filter(leagues=event, is_completed=True)
        if all_round_robin_match.count() == all_completed_round_robin_match.count():
            last_match_type = check_pre_game.last().match_type
            last_round = check_pre_game.last().elimination_round
            last_match_number = check_pre_game.last().match_number

            if last_match_type == "Round Robin":
                teams = select_top_teams(event)
                if len(teams) != len(RoundRobinGroup.objects.filter(league_for=event)):
                    return {"status": status.HTTP_200_OK, "message": "Not all groups have winners selected"}

                teams = make_shuffle(teams)
                match_type = "Elimination Round" if len(teams) > 4 else "Semi Final" if len(teams) == 4 else "Final"
                sets = set_num_f if len(teams) == 2 else set_num_e
                courts = court_num_f if len(teams) == 2 else court_num_e
                points = point_num_f if len(teams) == 2 else point_num_e
                round_number = 0 if match_type in ["Semi Final", "Final"] else 1

                court_num = 0
                match_number_now = last_match_number
                for i in range(0, len(teams), 2):
                    court_num = (court_num % courts) + 1
                    match_number_now += 1
                    create_tournament_match(
                        event, teams[i], teams[i+1], match_type, round_number,
                        court_num, sets, points, match_number_now
                    )
                return {"status": status.HTTP_200_OK, "message": f"Matches are created for {match_type}"}
            elif last_match_type in ["Elimination Round", "Semi Final"]:
                teams = list(Tournament.objects.filter(leagues=event, match_type=last_match_type).values_list("winner_team_id", flat=True))
                if len(teams) != len(Tournament.objects.filter(leagues=event, match_type=last_match_type)):
                    return {"status": status.HTTP_200_OK, "message": "Not all groups have winners selected"}

                match_type = "Final" if len(teams) == 2 else "Semi Final" if len(teams) == 4 else "Elimination Round"
                sets = set_num_f if len(teams) == 2 else set_num_e
                courts = court_num_f if len(teams) == 2 else court_num_e
                points = point_num_f if len(teams) == 2 else point_num_e
                round_number = 0 if match_type in ["Semi Final", "Final"] else last_round + 1

                random.shuffle(teams)
                court_num = 0
                match_number_now = last_match_number
                for i in range(0, len(teams), 2):
                    court_num = (court_num % courts) + 1
                    match_number_now += 1
                    create_tournament_match(
                        event, teams[i], teams[i+1], match_type, round_number,
                        court_num, sets, points, match_number_now
                    )
                return {"status": status.HTTP_200_OK, "message": f"Matches are created for {match_type} {round_number}"}
            elif last_match_type == "Final":
                return {"status": status.HTTP_200_OK, "message": "The event results are out! The event is completed successfully."}
        return {"status": status.HTTP_200_OK, "message": "All matches in this round are not completed yet."}
    else:
        group_result = create_group(team_ids, court_num_r)
        if group_result["status"] != status.HTTP_200_OK:
            return group_result

        group_list = group_result["groups"]
        round_robin_group_details = RoundRobinGroup.objects.filter(league_for=event)
        if round_robin_group_details.count() == court_num_r:
            return {"status": status.HTTP_200_OK, "message": f"Round Robin matches already created for {event.name}"}
        round_robin_group_details.delete()

        serial_number = 0
        for index, group_teams in enumerate(group_list, start=1):
            group = RoundRobinGroup.objects.create(court=index, league_for=event, number_sets=set_num_r)
            for team_id in group_teams:
                group.all_teams.add(Team.objects.get(id=team_id))

            match_combinations = [(team1, team2) for i, team1 in enumerate(group_teams) for team2 in group_teams[i+1:]]
            random.shuffle(match_combinations)
            for team1, team2 in match_combinations:
                serial_number += 1
                create_tournament_match(
                    event, team1, team2, "Round Robin", 0,
                    index, set_num_r, point_num_r, serial_number, group.id
                )
        return {"status": status.HTTP_200_OK, "message": "Matches are created successfully"}

def select_top_teams(event):
    """Select top two teams from each group based on points and score."""
    all_group_details = RoundRobinGroup.objects.filter(league_for=event)
    teams = []
    for grp in all_group_details:
        teams_ins = grp.all_teams.all()
        group_score_point_table = []
        for team in teams_ins:
            team_score = {}
            total_match_detals = Tournament.objects.filter(leagues=event).filter(Q(team1=team) | Q(team2=team))
            completed_match_details = total_match_detals.filter(is_completed=True)
            win_match_details = completed_match_details.filter(winner_team=team).count()
            loss_match_details = completed_match_details.filter(loser_team=team).count()
            drow_match = len(completed_match_details) - (win_match_details + loss_match_details)
            point = (win_match_details * 3) + (drow_match * 1)
            match_list = list(total_match_detals.values_list("id", flat=True))
            for_score = aginst_score = 0
            for sc in match_list:
                co_team_position = Tournament.objects.filter(id=sc).first()
                set_score = TournamentSetsResult.objects.filter(tournament_id=sc)
                if co_team_position.team1 == team:
                    for_score += sum(list(set_score.values_list("team1_point", flat=True)))
                    aginst_score += sum(list(set_score.values_list("team2_point", flat=True)))
                else:
                    for_score += sum(list(set_score.values_list("team2_point", flat=True)))
                    aginst_score += sum(list(set_score.values_list("team1_point", flat=True)))
            team_score.update({
                "uuid": team.uuid, "secret_key": team.secret_key,
                "completed_match": len(completed_match_details),
                "win_match": win_match_details, "loss_match": loss_match_details,
                "drow_match": drow_match, "for_score": for_score,
                "aginst_score": aginst_score, "point": point
            })
            group_score_point_table.append(team_score)

        grp_team = sorted(group_score_point_table, key=lambda x: (x['point'], x['for_score']), reverse=True)
        top_two_teams = grp_team[:2]
        teams_ = [Team.objects.get(uuid=top_team["uuid"], secret_key=top_team["secret_key"]).id for top_team in top_two_teams]
        teams.append(teams_)
        RoundRobinGroup.objects.filter(id=grp.id).update(seleced_teams=Team.objects.get(uuid=grp_team[0]["uuid"], secret_key=grp_team[0]["secret_key"]))
    return teams

def handle_round_robin(event, team_ids, playtype_details):
    """Handle Round Robin tournament logic."""
    court_num_r = int(playtype_details[0]["number_of_courts"])
    set_num_r = int(playtype_details[0]["sets"])
    point_num_r = int(playtype_details[0]["point"])

    if len(team_ids) != event.max_number_team:
        return {"status": status.HTTP_200_OK, "message": "All teams are not registered"}

    group_result = create_group(team_ids, 1)
    if group_result["status"] != status.HTTP_200_OK:
        return group_result

    group_list = group_result["groups"]
    round_robin_group_details = RoundRobinGroup.objects.filter(league_for=event)
    if round_robin_group_details.count() == 1:
        return {"status": status.HTTP_200_OK, "message": f"Round Robin group already created for {event.name}"}
    round_robin_group_details.delete()

    serial_number = 0
    for index, group_teams in enumerate(group_list, start=1):
        group = RoundRobinGroup.objects.create(court=index, league_for=event, number_sets=set_num_r)
        for team_id in group_teams:
            group.all_teams.add(Team.objects.get(id=team_id))

        match_combinations = [(team1, team2) for i, team1 in enumerate(group_teams) for team2 in group_teams[i+1:]]
        random.shuffle(match_combinations)
        for team1, team2 in match_combinations:
            serial_number += 1
            create_tournament_match(
                event, team1, team2, "Round Robin", 0,
                index, set_num_r, point_num_r, serial_number, group.id
            )
    return {"status": status.HTTP_200_OK, "message": "Matches created for Round Robin"}

def handle_individual_match_play(event, team_ids, playtype_details):
    """Handle Individual Match Play tournament logic."""
    court_num_f = int(playtype_details[2]["number_of_courts"])
    set_num_f = int(playtype_details[2]["sets"])
    point_num_f = int(playtype_details[2]["point"])

    if Tournament.objects.filter(leagues=event, match_type="Individual Match Play").exists():
        return {"status": status.HTTP_200_OK, "message": "Matches are already created"}
    if len(team_ids) < 2:
        return {"status": status.HTTP_200_OK, "message": "Minimum 2 teams are needed for individual match play"}

    random.shuffle(team_ids)
    match_number_now = 0
    for court_num in range(1, court_num_f + 1):
        match_number_now = court_num
        for i in range(0, len(team_ids), 2):
            create_tournament_match(
                event, team_ids[i], team_ids[i+1], "Individual Match Play", 0,
                court_num, set_num_f, point_num_f, match_number_now
            )
    return {"status": status.HTTP_200_OK, "message": "Matches created for Individual Match Play"}

@login_required(login_url="/user_side/")
def event_update_score(request, event_id):
    context = {}
    query = request.GET.get('q', '')
    status_filter = request.GET.get('status_filter', '')
    
    event = get_object_or_404(Leagues, id=event_id)
    matches = Tournament.objects.filter(leagues=event).select_related('team1', 'team2', 'leagues').order_by('id')
    
    if query:
        matches = matches.filter(
            Q(match_number__icontains=query) |
            Q(team1__name__icontains=query) |
            Q(team2__name__icontains=query) |
            Q(match_type__icontains=query)
        )
    
    if status_filter:
        if status_filter == "completed":
            matches = matches.filter(is_completed=True)
        elif status_filter == "incompleted":
            matches = matches.filter(is_completed=False)
    
    # Optimize score fetching with prefetch_related
    # matches = matches.prefetch_related('tournamentsetsresult_set')
    
    for match_ in matches:
        match_.score = TournamentSetsResult.objects.filter(tournament=match_)
        match_.set_list = [i+1 for i in range(match_.set_number)]
    context["matches"] = matches
    context["event"] = event
    
    return render(request, 'sides/update_events_score.html', context=context)

def update_event_winner(event, match):
    try:
        return True
    except Exception as e:
        return False

@login_required(login_url="/user_side/")
@require_POST
def update_match_scores(request, match_id):
    try:
        # Get the match
        match = get_object_or_404(Tournament, id=match_id)
        
        # Parse JSON data from request
        data = json.loads(request.body)
        scores = data.get('scores', [])
        submitted_set_numbers = set()
        # Update or create scores for each set
        for score in scores:
            set_number = score.get('set_number')
            team1_point = score.get('team1_point')
            team2_point = score.get('team2_point')
            # print(set_number, team1_point, team2_point)
            
            # Ensure valid data
            if set_number is None or team1_point is None or team2_point is None:
                return JsonResponse({'success': False, 'error': 'Invalid score data'}, status=400)
            
            submitted_set_numbers.add(set_number)
            # Update or create TournamentSetsResult
            tournament_set, created = TournamentSetsResult.objects.get_or_create(
                tournament=match,
                set_number=set_number,
                defaults={
                    'team1_point': team1_point,
                    'team2_point': team2_point,
                    'is_completed': True,
                    'win_team': match.team1 if team1_point > team2_point else match.team2
                }
            )
            # print(tournament_set)
            if not created:
                tournament_set.team1_point = team1_point
                tournament_set.team2_point = team2_point
                tournament_set.is_completed = True
                tournament_set.win_team = match.team1 if team1_point > team2_point else match.team2
                tournament_set.save()
        
        # Refresh match scores
        if match.set_number and len(submitted_set_numbers) == match.set_number:
            match.is_completed = True
            match.save()
        match.score = TournamentSetsResult.objects.filter(tournament=match)
        update_event_winner(match.leagues, match)
        # print(tournament_set)
        # Prepare response data
        score_data = [
            {
                'set_number': score.set_number,
                'team1_point': score.team1_point,
                'team2_point': score.team2_point,
                'win_team': score.win_team.name if score.win_team else None
            } for score in match.score
        ]
        # print(match.is_completed)
        return JsonResponse({
            'success': True,
            'scores': score_data,
            'is_completed': match.is_completed,
            'team1_name': match.team1.name if match.team1 else '',
            'team2_name': match.team2.name if match.team2 else ''
        })
    
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required(login_url="/user_side/")
@require_GET
def get_match_scores(request, match_id):
    try:
        match = get_object_or_404(Tournament, id=match_id)
        scores = TournamentSetsResult.objects.filter(tournament=match)
        
        score_data = [
            {
                'set_number': score.set_number,
                'team1_point': score.team1_point,
                'team2_point': score.team2_point
            } for score in scores
        ]
        
        return JsonResponse({
            'success': True,
            'scores': score_data,
            'team1_name': match.team1.name if match.team1 else '',
            'team2_name': match.team2.name if match.team2 else ''
        })
    
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required(login_url="/user_side/")
@require_POST
def update_tournament_settings(request, match_id):
    try:
        match = get_object_or_404(Tournament, id=match_id)
        
        # Ensure match is not completed
        if match.is_completed:
            return JsonResponse({'success': False, 'error': 'Cannot edit settings for a completed match'}, status=400)
        
        # Parse JSON data
        data = json.loads(request.body)
        set_number = data.get('set_number')
        points = data.get('points')
        
        # Validate data
        if not isinstance(set_number, int) or set_number < 1:
            return JsonResponse({'success': False, 'error': 'Invalid set number'}, status=400)
        if not isinstance(points, int) or points < 1:
            return JsonResponse({'success': False, 'error': 'Invalid points value'}, status=400)
        
        # Update match
        match.set_number = set_number
        match.points = points
        match.save()
        
        return JsonResponse({
            'success': True,
            'set_number': match.set_number,
            'points': match.points,
            'league_name': match.leagues.name if match.leagues else '',
            'court_num': match.court_num,
            'team1_name': match.team1.name if match.team1 else '',
            'team2_name': match.team2.name if match.team2 else '',
            'is_completed': match.is_completed
        })
    
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required(login_url="/user_side/")
def join_team_event(request, event_id):
    context = {"STRIPE_PUBLIC_KEY": settings.STRIPE_PUBLIC_KEY}
    user = request.user
    today = datetime.now()
    event = get_object_or_404(Leagues, id=event_id)
    user_player = Player.objects.filter(player_email=user.email).first()
    player_teams = user_player.team.all() if user_player else Team.objects.none()

    # Get teams created by the user
    created_teams = Team.objects.filter(created_by=user)

    # Get registered teams
    registered_teams = event.registered_team.all()

    # Filter only those that are in the registered teams
    user_event_teams = (player_teams | created_teams).distinct().filter(id__in=registered_teams.values_list('id', flat=True))

    # Add to context
    context["user_registered_teams"] = user_event_teams  
    
    # my team
    my_team = Team.objects.filter(created_by=user)
    team_type = event.team_type
    team_person = event.team_person
    if team_type:
        my_team = my_team.filter(team_type=team_type)
    if team_person:
        my_team = my_team.filter(team_person=team_person)
    for team in my_team:
        team.players = Player.objects.filter(team=team)
    context["my_team"] = my_team
    context["event"] = event
    context["balance"] = float(Wallet.objects.filter(user=request.user).first().balance)
    fees = Decimal(float(event.registration_fee))

    others_fees = event.others_fees
    if others_fees:
        for val in others_fees.values():
            try:
                fees += Decimal(float(val))  
            except (ValueError, TypeError):
                continue  
    context["total_fees"] = float(fees)
    return render(request, 'sides/join_event.html', context=context)

@login_required(login_url="/user_side/")
def match_history(request):
    query = request.GET.get('q', '').strip()
    context = {}

    player = Player.objects.filter(player=request.user).first()
    if not player:
        context["error"] = "Player profile not found."
        return render(request, 'sides/match_history.html', context)

    user_teams = Team.objects.filter(created_by=request.user)
    teams = list(player.team.all()) + list(user_teams)
    match_history = Tournament.objects.filter(Q(team1__in=teams) | Q(team2__in=teams)).order_by("-id")
    
    match_history_cal = match_history.only("team1", "team2", "winner_team")
    wins = sum(1 for match_ in match_history_cal if match_.winner_team in teams)
    losses = len(match_history_cal) - wins

    if query:
        match_history = match_history.filter(
            Q(team1__name__icontains=query) |
            Q(team2__name__icontains=query) |
            Q(leagues__name__icontains=query) |
            Q(match_number__icontains=query) |
            Q(leagues__team_type__name__icontains=query)
        ).order_by("-id")

    total_matches = match_history.count()
    paginator = Paginator(match_history, 21)
    page_number = request.GET.get('page')
    paginated_matches = paginator.get_page(page_number)

    # Process only paginated matches
    for match_ in paginated_matches:
        if match_.team1 in teams:
            match_.opponent = match_.team2
        else:
            match_.opponent = match_.team1

        match_.scores = TournamentSetsResult.objects.filter(tournament=match_)
        
    for match_ in match_history:
        match_.score = TournamentSetsResult.objects.filter(tournament=match_)
    context.update({
        "match_history": paginated_matches,
        "total_matches": total_matches,
        "wins": wins,
        "losses": losses,
        "query": query,  # Pass query for template usage
    })

    return render(request, 'sides/match_history.html', context)

@login_required(login_url="/user_side/")
def user_wallet_foruser(request):
    start_date = request.GET.get("start_date", None)
    end_date = request.GET.get("end_date", None)
    page = request.GET.get("page", 1)  # Get the current page number from request
    
    wallet = Wallet.objects.filter(user=request.user)
    
    balance = 0.0
    transactions = WalletTransaction.objects.filter(Q(sender=request.user) | Q(reciver=request.user)).order_by("-created_at")
    if start_date and end_date:
        transactions = transactions.filter(created_at__date__gte=start_date, created_at__date__lte=end_date)
    #print(transactions)
    paginator = Paginator(transactions, 10)  
    transactions_page = paginator.get_page(page)  

    if wallet.exists():
        balance = wallet.first().balance

    return render(
        request,
        "sides/wallet.html",
        {
            "wallet_balance": balance,
            "transactions": transactions_page, 
        },
    )

@login_required(login_url="/user_side/")
def add_fund(request):
    return render(request, "sides/add_fund.html", {"STRIPE_PUBLIC_KEY": settings.STRIPE_PUBLIC_KEY})

@csrf_exempt
def create_checkout_session(request):
    """ Creates a Stripe Checkout session """
    if request.method == "POST":
        amount = int(request.POST.get("amount")) * 100  # Convert to cents
        user = request.user
        stripe.api_key = settings.STRIPE_SECRET_KEY 
        # #print("stripe.api_key", stripe.api_key)
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {"name": "Add Funds"},
                    "unit_amount": amount,
                },
                "quantity": 1,
            }],
            mode="payment",
            success_url=settings.SITE_URL + "/payment-success/?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=settings.SITE_URL + "/payment-failed/",
        )
        # #print("hgsdfhgsa")
        # Save to AllPaymentsTable with Pending Status
        AllPaymentsTable.objects.create(
            user=user,
            amount=amount / 100,  # Convert from cents to dollars
            checkout_session_id=session.id,
            payment_for="AddMoney",
            status="Pending",
        )
        # #print("jsgd")
        return JsonResponse({"id": session.id})

@csrf_exempt
def stripe_webhook(request):
    """ Handles Stripe Webhook for successful payments """
    payload = request.body
    sig_header = request.headers.get("Stripe-Signature")
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except ValueError:
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        return HttpResponse(status=400)

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        user = AllPaymentsTable.objects.filter(checkout_session_id=session["id"]).first().user
        amount = session["amount_total"] / 100  # Convert from cents to dollars

        # Update Payment Status
        payment = AllPaymentsTable.objects.get(checkout_session_id=session["id"])
        payment.status = "Completed"
        payment.payment_mode = "Card"
        payment.json_response = session
        payment.save()

        # Create Wallet Transaction
        WalletTransaction.objects.create(
            sender=user,
            transaction_type="credit",
            transaction_for="AddMoney",
            amount=amount,
            payment_id=session["id"],
            json_response=session
        )

    return HttpResponse(status=200)

@login_required(login_url="/user_side/")
def payment_success(request):
    session_id = request.GET.get("session_id")

    if not session_id:
        return render(request, "payments/payment_failed.html", {"error": "Invalid session ID."})

    stripe.api_key = settings.STRIPE_SECRET_KEY

    try:
        session = stripe.checkout.Session.retrieve(session_id)

        # Ensure payment is completed
        if session.payment_status == "paid":
            user = request.user
            amount = session.amount_total / 100  # Convert cents to dollars
            
            wallet = Wallet.objects.filter(user=user).first()
            wallet.balance += Decimal(str(amount))  # Convert float to Decimal
            wallet.save()
           
            # Store payment record
            payment = AllPaymentsTable.objects.create(
                user=user,
                amount=amount,
                checkout_session_id=session.id,
                payment_for="Wallet Recharge",
                payment_mode="Stripe",
                json_response=session,
                status="Completed"
            )

            # Add to Wallet Transaction
            WalletTransaction.objects.create(
                sender=user,
                transaction_type="credit",
                transaction_for="AddMoney",
                amount=amount,
                payment_id=session.id,
                json_response=session,
                description=f"${amount} is added to your PickleIt wallet."
            )

            return render(request, "payments/payment_success.html", {"amount": amount})
        else:
            return render(request, "payments/payment_failed.html", {"error": "Payment not completed."})

    except stripe.error.StripeError as e:
        return render(request, "payments/payment_failed.html", {"error": str(e)})

def payment_failed(request):
    return render(request, "payments/payment_failed.html", {"error": "Your payment was unsuccessful."})

@csrf_exempt
def confirm_payment(request):
    if request.method == "POST":
        data = json.loads(request.body)
        event_id = data.get("event_id")
        team_ids = data.get("team_id_list", [])
        total_amount = float(data.get("total_amount", 0))
        #print(data)

        user = request.user
        event = Leagues.objects.get(id=event_id)
        wallet = Wallet.objects.get(user=user)

        if float(wallet.balance) >= total_amount:
            organizer_amount = (Decimal(total_amount) * Decimal(settings.ORGANIZER_PERCENTAGE)) / Decimal(100)
            admin_amount = (Decimal(total_amount) * Decimal(settings.ADMIN_PERCENTAGE)) / Decimal(100)

            WalletTransaction.objects.create(
                sender=request.user,
                reciver=event.created_by,                        
                admin_cost=admin_amount.quantize(Decimal('0.001'), rounding=ROUND_DOWN),
                reciver_cost=organizer_amount.quantize(Decimal('0.001'), rounding=ROUND_DOWN),
                getway_charge=Decimal(0),                        
                transaction_for="TeamRegistration",                                   
                transaction_type="debit",
                amount=Decimal(total_amount).quantize(Decimal('0.001'), rounding=ROUND_DOWN),
                payment_id=None, 
                description=f"${total_amount} is debited from your PickleIt wallet for registering teams to league {event.name}."
            )

            # ✅ Update admin wallet
            admin_wallet = Wallet.objects.filter(user__is_superuser=True).first()
            if admin_wallet:
                admin_wallet.balance = Decimal(admin_wallet.balance + admin_amount)
                admin_wallet.save()

            # ✅ Deduct from user wallet
            wallet.balance = Decimal(float(wallet.balance) - total_amount)
            wallet.save()
            
            # ✅ Update organizer wallet
            organizer_wallet = Wallet.objects.filter(user=event.created_by).first()
            if organizer_wallet:
                organizer_wallet.balance = Decimal(str(organizer_wallet.balance)) + organizer_amount
                organizer_wallet.save()

            for team_id in team_ids:
                team = Team.objects.get(id=team_id)
                event.registered_team.add(team)

            return JsonResponse({"success": True, "message": "Teams joined successfully!"})
        else:
            return JsonResponse({"success": False, "message": "Insufficient balance."})

    return JsonResponse({"success": False, "message": "Invalid request."})

@csrf_exempt
def initiate_stripe_payment(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            #print("Received Data:", data)
            event_id = data.get("event_id")
            team_ids = data.get("team_id_list", [])
            total_amount = data.get("total_amount", 0)

            try:
                total_amount = float(total_amount)  # Convert from string to float
            except ValueError:
                #print("Error: Invalid total_amount format:", total_amount)
                return JsonResponse({"success": False, "message": "Invalid total amount format."})

            unit_amount = int(total_amount * 100)  # Convert to cents

            if unit_amount <= 0:
                #print("Error: Amount cannot be zero or negative:", unit_amount)
                return JsonResponse({"success": False, "message": "Amount cannot be zero or negative."})

            #print("Final Amounts:", total_amount, unit_amount)

            # Create Stripe session
            host = request.get_host()
            current_site = f"{protocol}://{host}"
            main_url = f"{current_site}/user_side/stripe_success/{event_id}/{'-'.join(team_ids)}/"
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[{
                    "price_data": {
                        "currency": "usd",
                        "product_data": {"name": "Event Registration"},
                        "unit_amount": unit_amount,  # Must be an integer
                    },
                    "quantity": 1,
                }],
                mode="payment",
                success_url=f"{main_url}{{CHECKOUT_SESSION_ID}}/",
                cancel_url=request.build_absolute_uri(reverse("user_side:event_view", args=[event_id])),
            )

            #print("Session Created:", session)
            return JsonResponse({"success": True, "payment_url": session.url, "session_id": session.id})

        except Exception as e:
            #print("Stripe Error:", str(e))
            return JsonResponse({"success": False, "message": str(e)})

    return JsonResponse({"success": False, "message": "Invalid request."})

def stripe_success(request, event_id, team_ids, checkout_session_id):
    
    try:
        # Fetch session details from Stripe
        session = stripe.checkout.Session.retrieve(checkout_session_id)
        
        total_amount = Decimal(session.amount_total) / 100  # Convert cents to dollars
        #print(total_amount)
        payment_status = session.get("payment_status") == "paid"
        payment_method_types = session.get("payment_method_types", [])

        if not payment_status:
            return JsonResponse({"success": False, "message": "Payment not completed."})

        user = request.user
        wallet = Wallet.objects.get(user=user)
        event = Leagues.objects.get(id=event_id)
        team_ids = team_ids.split('-')

        
        wallet.balance = Decimal(wallet.balance) + total_amount  
        wallet.balance -= total_amount  
        wallet.save()

        AllPaymentsTable.objects.create(
            user=user,
            amount=total_amount,
            checkout_session_id=checkout_session_id,
            payment_mode=", ".join(payment_method_types),
            payment_for=f"Registering {len(team_ids)} Team(s) in {event.name}",
            status="Completed"
        )
        fees = float(event.registration_fee)

        others_fees = event.others_fees
        if others_fees:
            for val in others_fees.values():
                try:
                    fees += float(val) 
                except (ValueError, TypeError):
                    continue  
        total_amount = fees * len(team_ids)
        organizer_amount = round((Decimal(total_amount) * Decimal(settings.ORGANIZER_PERCENTAGE)) / 100, 2)
        admin_amount = round((Decimal(total_amount) * Decimal(settings.ADMIN_PERCENTAGE)) / 100, 2)

        WalletTransaction.objects.create(
            sender=user,
            reciver=event.created_by,
            admin_cost=admin_amount,
            reciver_cost=organizer_amount,
            getway_charge=Decimal(0),
            transaction_for="TeamRegistration",
            transaction_type="debit",
            amount=Decimal(total_amount),
            payment_id=checkout_session_id,
            description=f"${total_amount} is debited from your PickleIt wallet for registering teams in event {event.name}."
        )
        for team_id in team_ids:
            team = Team.objects.get(id=team_id)
            event.registered_team.add(team)

        return redirect("user_side:event_view", event_id=event_id)

    except stripe.error.StripeError as e:
        return JsonResponse({"success": False, "message": f"Stripe error: {str(e)}"})
    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)})

def edit_team(request, team_id):
    team = get_object_or_404(Team, id=team_id)
    players = list(Player.objects.filter(team=team).values("id", "player_full_name", "player__rank", "player__image", "player__gender", "player__id"))
    pre_player_ids = list(Player.objects.filter(team__id=team_id).values_list("id", flat=True))
    context = {"players":players, "team":team, "message":"","pre_player_ids":pre_player_ids, "oppration":"Edit", "button":"Submit"}
    
    if request.method == "POST":
        team_name = request.POST.get('team_name')
        team_image = request.FILES.get('team_image')
        team_person = request.POST.get('team_person')
        team_type = request.POST.get('team_type')
        player_ids = request.POST.getlist('selected_players')  
        if not team_name and not team_person and not team_type:
            # return HttpResponse("Team name, team person and team type are required.")
            context["message"] = "Team name, team person and team type are required."
            return render(request, "sides/edit_team.html", context)
        
        # Update team information
        team.name = team_name
        if team_image:
            team.team_image = team_image
        team.team_person = team_person
        team.team_type = team_type
        team.save()
        
        # Update players associated with the team
        if team_person == "Two Person Team":
            if len(player_ids) != 2:
                context["message"] = "Need to select two players."
                return render(request, "sides/edit_team.html", context)
        elif team_person == "One Person Team":
            if len(player_ids) != 1:
                context["message"] = "Need to select only one player."
                return render(request, "sides/edit_team.html", context)
        
        removed_players = []
        new_players = []
        if team_type == "Men" or team_type == "Women":
            players = Player.objects.filter(id__in=player_ids)
            
            for player_id in pre_player_ids:
                pre_player = Player.objects.get(id=player_id)
                removed_players.append(player_id) 
                pre_player.team.remove(team)
            for player in players:
                new_players.append(player.id)
                player.team.add(team)
            team.save()
            add, rem = check_add_player(new_players, removed_players)
                
            titel = "Team Membership Modification"
            for r in rem:
                message = f"You have been removed from team {team.name}"
                user_id = Player.objects.filter(id=r).first().player.id
                notify_edited_player(user_id, titel, message)

            titel = "Team Membership Modification"
            for r in add:
                message = f"You have been added to team {team.name}"
                user_id = Player.objects.filter(id=r).first().player.id
                notify_edited_player(user_id, titel, message)

            return redirect(reverse('user_side:find_my_team_list'))
                              
        elif team_type == "Co-ed":
            players = Player.objects.filter(id__in=player_ids)
            male_player = players.filter(player__gender='Male') 
            female_player = players.filter(player__gender='Female')    
            if len(male_player) == 1 and len(female_player) == 1:
                for player_id in pre_player_ids:
                    pre_player = Player.objects.get(id=player_id)
                    removed_players.append(player_id) 
                    pre_player.team.remove(team)
                for player in players:                            
                    new_players.append(player.id)
                    player.team.add(team)
                team.save()
                add, rem = check_add_player(new_players, removed_players)
                
                titel = "Team Membership Modification"
                for r in rem:
                    message = f"You have been removed from team {team.name}"
                    user_id = Player.objects.filter(id=r).first().player.id
                    notify_edited_player(user_id, titel, message)

                titel = "Team Membership Modification"
                for r in add:
                    message = f"You have been added to team {team.name}"
                    user_id = Player.objects.filter(id=r).first().player.id
                    notify_edited_player(user_id, titel, message)
                return redirect(reverse('user_side:find_my_team_list'))
            else:
                context["message"] = "Select one male player and one female player."
                return render(request, "sides/edit_team.html", context)    
                         
        else:
            context["message"] = "Something is Wrong"
    return render(request, "sides/edit_team.html", context)

def search_players(request):
    query = request.GET.get('q', '').strip()
    category = request.GET.get('category', '').strip()  # Get category from request

    if query:
        players = Player.objects.filter(Q(player__first_name__icontains=query) | Q(player__last_name__icontains=query) | Q(player__username__icontains=query))
        #print(players)
        if category: 
            if category == "Women":
                players = players.filter(player__gender="Female")
            elif category == "Men":
                players = players.filter(player__gender="Male")
            else:
                players = players
            #print(players)

        player_data = [
            {
                "id": player.id,
                "name": player.player_full_name,
                "image": player.player.image.url if player.player.image else static('img/no_image.jpg')
            }
            for player in players
        ]
        #print(players)
        return JsonResponse({"players": player_data})

    return JsonResponse({"players": []})

def check_data_structure(data_structure):
    for item in data_structure:
        if item["number_of_courts"] != 0 or item["sets"] != 0 or item["point"] != 0:
            return False
    return True

def edit_event(request, event_id):
    context = {}
    event = get_object_or_404(Leagues, id=event_id)  
    context["event"] = event
    users = User.objects.all()  # Fetch all users
    context["users"] = users
    play_type_details = LeaguesPlayType.objects.filter(league_for=event)
    cancelation_policy = LeaguesCancellationPolicy.objects.filter(league=event)

    tournament_play_type = event.play_type
    #print(event.team_type, event.team_person, event.play_type)   
    if play_type_details:
        play_type_details = play_type_details.first().data

    else:
        play_type_details = [
                    {"name": "Round Robin", "number_of_courts": 0, "sets": 0, "point": 0},
                    {"name": "Elimination", "number_of_courts": 0, "sets": 0, "point": 0},
                    {"name": "Final", "number_of_courts": 0, "sets": 0, "point": 0}
                    ]
    # #print(play_type_details, "play_type_details")    
    for se in play_type_details:
        #print(tournament_play_type, "tournament_play_type")
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
        else:
            # #print("hit")
            se["is_show"] = True 
        # #print(se, "se")
    # #print(play_type_details, "play_type_details")
    context["teams"] = Team.objects.all()
    context["play_type_details"] = play_type_details
    context["policies"] = cancelation_policy
        
    check_data = check_data_structure(play_type_details)
    context["play_details_update"] = check_data


    if request.method == "POST": 
        event.name = request.POST.get("tournament_name", event.name)
        event.leagues_start_date = request.POST.get("league_start_date", event.leagues_start_date)
        event.leagues_end_date = request.POST.get("league_end_date", event.leagues_end_date)
        event.registration_start_date = request.POST.get("registration_start_date", event.registration_start_date)
        event.registration_end_date = request.POST.get("registration_end_date", event.registration_end_date)
        event.max_number_team = request.POST.get("max_join_team", event.max_number_team)
        event.registration_fee = request.POST.get("registration_fee", event.registration_fee)
        event.description = request.POST.get("description", event.description)
        event.location = request.POST.get("location", event.location)
        
        # Handle many-to-many relationship with teams (Join Team)
        selected_teams = request.POST.getlist("join_team")
        event.registered_team.set(selected_teams)

        # Handle other fees, if any
        other_fees_topic = request.POST.getlist("other_fees_topic[]")
        other_fees = request.POST.getlist("other_fees[]")
        other_fees_dict = dict(zip(other_fees_topic, other_fees))
        event.others_fees = other_fees_dict
        if "image" in request.FILES:
            event.image = request.FILES["image"]

        # Handle Organizer Selection
        organizer_ids = request.POST.getlist("organizer")  # Get multiple selected users
        if organizer_ids:
            event.add_organizer.set(organizer_ids)  # Directly set the ManyToMany field
        else:
            event.add_organizer.clear()

        cancellation_days = request.POST.getlist("cancellation_days[]")
        refund_percentages = request.POST.getlist("refund_percentage[]")

        # Clear existing policies
        LeaguesCancellationPolicy.objects.filter(league=event).delete()

        # Save new policies
        for day, refund in zip(cancellation_days, refund_percentages):
            if day and refund:
                LeaguesCancellationPolicy.objects.create(
                    league=event,
                    within_day=int(day),
                    refund_percentage=(float(refund))
                )

        event.save()


        courts_1 = request.POST.get("courts_1", 0)
        sets_1 = request.POST.get("sets_1", 0)
        points_1 = request.POST.get("points_1", 0)

        courts_2 = request.POST.get("courts_2", 0)
        sets_2 = request.POST.get("sets_2", 0)
        points_2 = request.POST.get("points_2", 0)

        courts_3 = request.POST.get("courts_3", 0)
        sets_3 = request.POST.get("sets_3", 0)
        points_3 = request.POST.get("points_3", 0)

        play_details = LeaguesPlayType.objects.filter(league_for=event).first()
        tournament_play_type = event.play_type
        data_ = [{"name": "Round Robin", "number_of_courts": courts_1, "sets": sets_1, "point": points_1},
                {"name": "Elimination", "number_of_courts": courts_2, "sets": sets_2, "point": points_2},
                {"name": "Final", "number_of_courts": courts_3, "sets": sets_3, "point": points_3}]
        # #print(data_, "data")
        for se in data_:
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
        # #print("hit", data_)
        play_details.data = data_
        play_details.save()


        return redirect(reverse("user_side:event_view", kwargs={"event_id":event_id}))
    else:
        return render(request, "sides/edit_event.html", context)

def search_teams(request):
    query = request.GET.get("q", "").strip()
    if query:
        teams = Team.objects.filter(name__icontains=query).values("id", "name", "team_image")
        return JsonResponse({"teams": list(teams)})
    return JsonResponse({"teams": []})

def search_organizers(request):
    query = request.GET.get("q", "").strip()
    if query:
        organizers = User.objects.filter(Q(first_name__icontains=query) | Q(last_name__icontains=query) | Q(username__icontains=query)).values("id", "first_name", "last_name", "image", "email")
        return JsonResponse({"organizers": list(organizers)})
    return JsonResponse({"organizers": []})


@login_required(login_url="/user_side/")
def my_ad_list(request):
    context = {}
    query = request.GET.get('q', '')
    check_plan = Subscription.objects.filter(
        user=request.user,
        is_active=True,
        end_date__date__gte=datetime.now().date()
    ).exists()
    
    
    ads = Advertisement.objects.filter(approved_by_admin=True, created_by=request.user)
    if query:
        ads = ads.filter(Q(name__icontains=query) | Q(description__icontains=query) | Q(script_text__icontains=query))

    # Calculate status (days until expiry)
    for ad in ads:
        days_left = (ad.end_date - now()).days
        if days_left < 0:
            ad.status = "Expired"
        else:
            ad.status = f"Expires in {days_left} days"

    # Pagination
    paginator = Paginator(ads, 9)  # Show 9 ads per page
    page = request.GET.get('page')
    
    try:
        ads = paginator.page(page)
    except PageNotAnInteger:
        ads = paginator.page(1)
    except EmptyPage:
        ads = paginator.page(paginator.num_pages)
    if not check_plan:
        context["advertisements"] = ads
        context['query'] = query
        context["error"] = "You need to subscribe to a plan to create advertisements."
        return render(request, 'sides/my_ad_list.html', context)
    context["advertisements"] = ads
    context['query'] = query
    context["error"] = None
    return render(request, 'sides/my_ad_list.html', context)


@login_required(login_url="/user_side/")
def create_advertisement(request):
    durations = AdvertisementDurationRate.objects.all()
    wallet_balance = Wallet.objects.get(user=request.user).balance

    return render(request, 'sides/advertisement_form.html', {
        'durations': durations, 
        'wallet_balance': wallet_balance
    })


def get_ad_rate(request):
    duration_id = request.GET.get("duration_id")
    try:
        duration = AdvertisementDurationRate.objects.get(id=duration_id)
        return JsonResponse({"rate": duration.rate})
    except AdvertisementDurationRate.DoesNotExist:
        return JsonResponse({"error": "Invalid duration ID"}, status=400)


@login_required(login_url="/user_side/")
def confirm_payment_for_advertisement(request):
    """Handles the payment confirmation after checking wallet balance."""
    if request.method == "POST":
        duration_id = request.POST.get('duration_id')
        name = request.POST.get('name')
        url = request.POST.get('url')
        company_name = request.POST.get('company_name')
        company_website = request.POST.get('company_website')
        start_date = request.POST.get('start_date')

        image = request.FILES.get('image') 
        script_text = request.POST.get('script_text') 
        description = request.POST.get('description')

        wallet = get_object_or_404(Wallet, user=request.user)

        duration_instance = AdvertisementDurationRate.objects.filter(id=int(duration_id)).first()
        rate = duration_instance.rate
        if float(balance) >= float(rate):
            obj = GenerateKey()
            advertisement_key = obj.gen_advertisement_key()
            ad = Advertisement.objects.create(
                    secret_key=advertisement_key,
                    name=name,
                    image=image,
                    url=url,
                    created_by_id=request.user.id,
                    description=description,
                    script_text=script_text,
                    start_date=start_date,
                    company_name=company_name,
                    company_website=company_website,
                    duration=duration_instance)
            
            WalletTransaction.objects.create(
                sender = request.user,
                reciver = None,                        
                admin_cost=Decimal(rate),
                getway_charge = 0,                        
                transaction_for="Advertisement",                                   
                transaction_type="debit",
                amount=Decimal(rate),
                payment_id=None, 
                description=f"${rate} is debited from your PickleIt wallet for creating advertisement."
                )
            balance = float(balance) - float(rate)
            wallet.balance = Decimal(balance)
            wallet.save()

            admin_wallet = Wallet.objects.filter(user__is_superuser=True).first()
            admin_balance = float(admin_wallet.balance) + float(rate)
            admin_wallet.balance = Decimal(admin_balance)
            admin_wallet.save()
            
            # send notification to admin
            admin_users = User.objects.filter(is_admin=True).values_list('id', flat=True)
            title = "New Advertisement created."
            message = f"{request.user.first_name} {request.user.last_name} has created an advertisement named {ad.name}. Please review this."
            for user_id in admin_users:
                notify_edited_player(user_id, title, message)
            
            return JsonResponse({'success': 'Advertisement created successfully'}, status=201)   
        else:
            return JsonResponse({'error': 'Insufficient balance'}, status=400)         
    
    return JsonResponse({'error': 'Invalid request'}, status=400)

import urllib.parse
@csrf_exempt
def initiate_stripe_payment_for_advertisement(request):
    if request.method == "POST":
        duration_id = request.POST.get("duration_id")
        remaining_amount = float(request.POST.get("total_amount_with_fees"))

        # Save form data in session
        form_data = request.POST.dict()
        request.session["ad_form_data"] = form_data

        # Convert form data to JSON and encode it for URL
        json_data = json.dumps({"duration_id": duration_id, "form_data": form_data})
        my_data = urllib.parse.quote(json_data)
        stripe.api_key = settings.STRIPE_SECRET_KEY
        host = request.get_host()
        current_site = f"{protocol}://{host}"
        main_url = f"{current_site}/user_side/stripe_success_for_advertisement/{my_data}/"

        try:
            # Create Stripe Checkout Session
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[{
                    "price_data": {
                        "currency": "usd",
                        "product_data": {"name": "Ad Payment"},
                        "unit_amount": int(remaining_amount * 100),  # Convert to cents
                    },
                    "quantity": 1,
                }],
                mode="payment",
                success_url=f"{main_url}{{CHECKOUT_SESSION_ID}}/",
                cancel_url=request.build_absolute_uri(reverse("user_side:my_ad_list")),
            )

            return JsonResponse({"success": True, "stripe_url": session.url})
        
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    return JsonResponse({"success": False, "error": "Invalid request"})


def stripe_success_for_advertisement(request, my_data, checkout_session_id):
    # Retrieve saved form data from session
    try:
        # Fetch session details from Stripe
        session = stripe.checkout.Session.retrieve(checkout_session_id)

        json_data = json.loads(urllib.parse.unquote(my_data))
        duration_id = json_data.get("duration_id")
        form_data = json_data.get("form_data")
        #print(form_data)
        
        total_amount = Decimal(session.amount_total) / 100  # Convert cents to dollars
        #print(total_amount)
        payment_status = session.get("payment_status") == "paid"
        payment_method_types = session.get("payment_method_types", [])

        if not payment_status:
            return JsonResponse({"success": False, "message": "Payment not completed."})

        user = request.user
        wallet = Wallet.objects.get(user=user)
        wallet.balance = Decimal(wallet.balance) + total_amount  
        wallet.balance -= total_amount  
        wallet.save()

        AllPaymentsTable.objects.create(
            user=user,
            amount=total_amount,
            checkout_session_id=checkout_session_id,
            payment_mode=", ".join(payment_method_types),
            payment_for=f"Creating Advertisement.",
            status="Completed"
        )
        rate = AdvertisementDurationRate.objects.get(id=duration_id).rate
        WalletTransaction.objects.create(
                sender = request.user,
                reciver = None,                        
                admin_cost=Decimal(rate),
                getway_charge = 0,                        
                transaction_for="Advertisement",                                   
                transaction_type="debit",
                amount=Decimal(rate),
                payment_id=None, 
                description=f"${rate} is debited from your PickleIt wallet for creating advertisement."
                )

        obj = GenerateKey()
        advertisement_key = obj.gen_advertisement_key()
        duration_instance = AdvertisementDurationRate.objects.filter(id=int(duration_id)).first()
        ad = Advertisement.objects.create(
                secret_key=advertisement_key,
                name=form_data.get('name'),
                image=form_data.get('image'),
                url=form_data.get('url'),
                created_by_id=request.user.id,
                description=form_data.get('description'),
                script_text=form_data.get('script_text'),
                start_date=form_data.get('start_date'),
                company_name=form_data.get('company_name'),
                company_website=form_data.get('company_website'),
                duration=duration_instance)

        return redirect("user_side:my_ad_list")

    except stripe.error.StripeError as e:
        return JsonResponse({"success": False, "message": f"Stripe error: {str(e)}"})
    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)})


def fetch_google_clubs(request):
    """
    Fetch nearby clubs using Google Places API
    """
    google_api_key = settings.MAP_API_KEY
    lat = request.GET.get("lat")  # Get latitude from request
    lng = request.GET.get("lng")  # Get longitude from request
    radius = 5000  # 5km radius

    google_places_url = (
        f"https://maps.googleapis.com/maps/api/place/nearbysearch/json?"
        f"location={lat},{lng}&radius={radius}&type=club&key={google_api_key}"
    )

    response = requests.get(google_places_url)
    data = response.json()

    if "results" in data:
        google_clubs = [
            {"name": place["name"], "latitude": place["geometry"]["location"]["lat"],
             "longitude": place["geometry"]["location"]["lng"]}
            for place in data["results"]
        ]
        return JsonResponse({"google_clubs": google_clubs})
    return JsonResponse({"google_clubs": []})


def fetch_pickleball_courts(request):
    """
    Fetch nearby pickleball courts using Google Places API
    """
    google_api_key = settings.MAP_API_KEY
    lat = request.GET.get("lat")  # Get latitude from request
    lng = request.GET.get("lng")  # Get longitude from request
    radius = 5000  # 5km radius

    google_places_url = (
        f"https://maps.googleapis.com/maps/api/place/nearbysearch/json?"
        f"location={lat},{lng}&radius={radius}&keyword=pickleball+court&key={google_api_key}"
    )

    response = requests.get(google_places_url)
    data = response.json()

    if "results" in data:
        pickleball_courts = [
            {
                "name": place["name"],
                "latitude": place["geometry"]["location"]["lat"],
                "longitude": place["geometry"]["location"]["lng"],
                "address": place.get("vicinity", "No address available")
            }
            for place in data["results"]
        ]
        return JsonResponse({"pickleball_courts": pickleball_courts})
    
    return JsonResponse({"pickleball_courts": []})


@login_required(login_url="/user_side/")
def all_club_list(request):
    query = request.GET.get('q', '')
    location = request.GET.get('location', '')
    
    clubs = Club.objects.filter(diactivate=False)

    if query:
        clubs = clubs.filter(Q(name__icontains=query) | Q(description__icontains=query))
    if location:
        latitude, longitude = get_lat_long_google(settings.MAP_API_KEY, location)
        user_location = (float(latitude), float(longitude))
        max_distance_km = 100  # Search radius in km

        # Filter clubs by distance using geopy
        clubs = [club for club in clubs if geodesic(user_location, (float(club.latitude), float(club.longitude))).km <= max_distance_km]

    clubs_json = json.dumps(list(clubs.values('id', 'name', 'location', 'latitude', 'longitude')))
    paginator = Paginator(clubs, 9)  # Show 10 teams per page
    page = request.GET.get('page')
    
    try:
        clubs = paginator.page(page)
    except PageNotAnInteger:
        clubs = paginator.page(1)
    except EmptyPage:
        clubs = paginator.page(paginator.num_pages)

    
    return render(request, 'sides/club_list.html', {'clubs':clubs, 'query':query, 'location_query':location, "google_api_key": settings.MAP_API_KEY, "clubs_json": clubs_json})


def club_view(request, pk):
    club = get_object_or_404(Club, id=int(pk))
    club_paackages = ClubPackage.objects.filter(club=club)
    check_join = JoinClub.objects.filter(user=request.user, club=club)

    # Check if the user has joined the club
    is_joined = check_join.exists()  # Returns True if any record exists, otherwise False
    wallet_balance = Wallet.objects.filter(user=request.user).first().balance
    return render(request, 'sides/club_view.html', {
        'club': club, 
        'packages': club_paackages, 
        'is_joined': is_joined,
        'wallet_balance':wallet_balance
    })

def get_wallet_balance_and_amount_to_pay(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        package_id = data.get('package_id')
        booking_date = data.get('booking_date')

        # Get the package and calculate the amount to pay
        package = ClubPackage.objects.get(id=package_id)
        if JoinClub.objects.filter(user=request.user, club=package.club).exists():
            discount = package.member_ship_discount
            if not discount:
                discount = 0
            pay_amount = package.price - (package.price*discount)/100
        else:
            pay_amount = package.price  # Assuming the price of the package is the amount to pay

        # Get the user's wallet balance
        wallet = Wallet.objects.get(user=request.user)
        wallet_balance = wallet.balance

        return JsonResponse({
            'wallet_balance': wallet_balance,
            'amount_to_pay': pay_amount,
        })
    
    
def confirm_payment_for_book_club(request):
    if request.method == "POST":
        data = json.loads(request.body)
        package_id = data.get('package_id')
        booking_date = data.get('booking_date')
        if not booking_date:
            return JsonResponse({"error": "not proper date"}, status=400)
        date = datetime.strptime(booking_date, "%Y-%m-%d %H:%M:%S")  # Adjust format as needed
        date = make_aware(date)
        date_today = timezone.now()
        if date_today >= date:
            return JsonResponse({"error": "please select proper date"}, status=400)
        
        club_package = get_object_or_404(ClubPackage, id=int(package_id))

        if JoinClub.objects.filter(user=request.user, club=club_package.club).exists():
            discount = club_package.member_ship_discount
            if not discount:
                discount = 0
            pay_amount = club_package.price - (club_package.price*discount)/100
        else:
            pay_amount = club_package.price
        
        wallet = get_object_or_404(Wallet, user=request.user)
        balance = wallet.balance if wallet else 0
        
        if pay_amount in [0, 0.00, None, "0.0"]:
            join = BookClub(user=request.user, package=club_package, price=pay_amount, date=date)
            join.status = True
            join.save()
            return JsonResponse({"message": "Club Booked successfully!"}, status=201)

        club_wallet = Wallet.objects.filter(user=club_package.club.user).first()
        admin_wallet = Wallet.objects.filter(user__is_superuser=True).first()
        
        if balance >= pay_amount:
            club_amount = (pay_amount * Decimal(settings.CLUB_PERCENTAGE)) / 100
            admin_amount = (pay_amount * Decimal(settings.ADMIN_PERCENTAGE_CLUB)) / 100
            if admin_amount is not None:
                admin_amount = admin_amount.quantize(Decimal("0.01"))  # Keeps 2 decimal places
            if club_amount is not None:
                club_amount = club_amount.quantize(Decimal("0.01"))

            WalletTransaction.objects.create(
                sender = request.user,
                reciver = club_package.club.user, 
                reciver_cost =  str(club_amount),                      
                admin_cost= str(admin_amount),
                getway_charge = 0,                        
                transaction_for="BookClub",                                   
                transaction_type="debit",
                amount=pay_amount,
                payment_id=None, 
                description=f"${pay_amount} is debited from your PickleIt wallet for Booking {club_package.name} package from {club_package.club.name} club."
                )
            wallet.balance -= pay_amount
            wallet.save()
            club_wallet.balance += club_amount
            club_wallet.save()
            admin_wallet.balance += admin_amount
            admin_wallet.save()
            # ✅ Create JoinClub Entry
            join = BookClub(user=request.user, package=club_package, price=pay_amount, date=date)
            join.status = True
            join.save()
            # ✅ Send Notification
            user_id = club_package.club.user.id
            message = f"{request.user.first_name} booked your club: {club_package.club.name} at {date}"
            title = "User Booked Club"
            notify_edited_player(user_id, title, message)
            
            return JsonResponse({'success': 'Booking club is successfull'}, status=201)   
        else:
            return JsonResponse({'error': 'Insufficient balance'}, status=400)         
    
    return JsonResponse({'error': 'Invalid request'}, status=400)

protocol = settings.PROTOCALL
def initiate_stripe_payment_for_booking_club(request):
    # #print('this function called')
    if request.method == "POST":
        data = json.loads(request.body)
        #print('Data received:', data)
        package_id = data.get('package_id')
        booking_date = data.get('booking_date')
        without_fees = float(data.get('remaining_amount'))
        remaining_amount = float(data.get("total_amount_with_fees"))

        if not booking_date:
            return JsonResponse({"error": "not proper date"}, status=400)
        try:
            if " " in booking_date:  # Check if time is included
                date = datetime.strptime(booking_date, "%Y-%m-%d %H:%M:%S")
            else:
                date = datetime.strptime(booking_date, "%Y-%m-%d")
        except ValueError:
            return JsonResponse({"error": "Invalid date format"}, status=400)

        date = make_aware(date)
        date_today = timezone.now()
        if date_today >= date:
            return JsonResponse({"error": "please select proper date"}, status=400)
             
        package = ClubPackage.objects.filter(id=package_id).first()
        json_data = json.dumps({"booking_date": date.strftime("%Y-%m-%d %H:%M:%S"), "package_id": package_id})
        my_data = base64.b64encode(json_data.encode("utf-8")).decode("utf-8")
        stripe.api_key = settings.STRIPE_SECRET_KEY

        host = request.get_host()
        current_site = f"{settings.PROTOCALL}://{host}"
       
        product_name = f"Book {package.name} package in {package.club.name} Club"
        product_description = "Payment received by Pickleit"
        stripe.api_key = settings.STRIPE_SECRET_KEY
        if request.user.stripe_customer_id :
            stripe_customer_id = request.user.stripe_customer_id
        else:
            customer = stripe.Customer.create(email=request.user.email).to_dict()
            stripe_customer_id = customer["id"]
            request.user.stripe_customer_id = stripe_customer_id
            request.user.save()
        
        protocol = settings.PROTOCALL
        host = request.get_host()
        current_site = f"{protocol}://{host}"
        total_charge = round(Decimal(remaining_amount), 2)
        charge_amount = round(float(total_charge * 100))
        stripe_fees = Decimal(remaining_amount - without_fees)

        main_url = f"{current_site}/user_side/stripe_success_for_booking_club/{stripe_fees}/{my_data}/"
        product = stripe.Product.create(name=product_name,description=product_description,).to_dict()
        price = stripe.Price.create(unit_amount=charge_amount,currency='usd',product=product["id"],).to_dict()

        try:
            # Create Stripe Checkout Session
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[
                    {
                        # Provide the exact Price ID (for example, pr_1234) of the product you want to sell
                        'price': price["id"],
                        'quantity': 1,
                    },
                ],
                mode="payment",
                success_url=f"{main_url}{{CHECKOUT_SESSION_ID}}/",
                cancel_url=request.build_absolute_uri(reverse("user_side:club_view", args=[package.club.id])),
            )

            return JsonResponse({"success": True, "stripe_url": session.url})
        
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    return JsonResponse({"success": False, "error": "Invalid request"})


def stripe_success_for_booking_club(request, stripe_fees, my_data, checkout_session_id):
    try:
        stripe.api_key = settings.STRIPE_SECRET_KEY
        pay = stripe.checkout.Session.retrieve(checkout_session_id).to_dict()
        
        payment_status = pay.get("payment_status") == "paid"
        amount_total = Decimal(pay.get("amount_total", 0)) / 100  # Convert to Decimal
        payment_method_types = pay.get("payment_method_types", [])

        # Decode and parse JSON data
        json_bytes = base64.b64decode(my_data)
        request_data = json.loads(json_bytes.decode('utf-8'))
        #print(request_data)
        booking_date = request_data.get("booking_date")
        date = datetime.strptime(booking_date, "%Y-%m-%d %H:%M:%S")  # Adjust format as needed      
       
        package_id = request_data.get("package_id")
        package = get_object_or_404(ClubPackage, id=package_id)
        club = get_object_or_404(Club, id=package.club.id)

        payment_for = f"join {club.name} club"
        user_wallet = Wallet.objects.filter(user=request.user).first()
        get_wallet = Wallet.objects.filter(user=club.user).first()
        admin_wallet = Wallet.objects.filter(user__is_superuser=True).first()
        existing_payment = AllPaymentsTable.objects.filter(user=request.user, checkout_session_id=checkout_session_id).exists()

        if not existing_payment and payment_status:
            AllPaymentsTable.objects.create(
                user=request.user,
                amount=amount_total,
                checkout_session_id=checkout_session_id,
                payment_mode=", ".join(payment_method_types),
                payment_for=payment_for,
                status="Completed" if payment_status else "Failed"
            )
            join = BookClub(user=request.user, package=package, price=package.price, date=date)
            join.status = True
            join.save()
            ###
            # try:
            club_amount = (package.price * settings.CLUB_PERCENTAGE) / 100
            admin_amount = (package.price * settings.ADMIN_PERCENTAGE_CLUB) / 100
            
            if admin_amount is not None:
                admin_amount = admin_amount.quantize(Decimal("0.01"))  # Keeps 2 decimal places
            if club_amount is not None:
                club_amount = club_amount.quantize(Decimal("0.01"))
            
            WalletTransaction.objects.create(
                sender=request.user,
                reciver=club.user,
                admin_cost=admin_amount,
                reciver_cost=club_amount,
                getway_charge=stripe_fees,
                transaction_for="BookClub",
                transaction_type="debit",
                amount=package.price,
                payment_id=checkout_session_id,
                description=f"${package.price} is debited from your PickleIt wallet for join club to {club.name}."
            )
            get_wallet.balance += club_amount
            admin_wallet.balance += admin_amount
            get_wallet.save()
            admin_wallet.save()
            user_wallet.balance = 0.0
            user_wallet.save()

            # messages.success(request, f"You have successfully joined {club.name}!")

                # ✅ Redirect to club view
            return redirect("user_side:club_view", pk=club.id)
        else:
            return JsonResponse({"success": True, "message": f"You have already booked the club."})

    except stripe.error.StripeError as e:
        return JsonResponse({"success": False, "message": f"Stripe error: {str(e)}"})
    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)})


def booking_list(request, club_id):
    date = request.GET.get("date")
    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")
    search_query = request.GET.get("search", "")
    
    club = Club.objects.get(id=int(club_id))
    packages = ClubPackage.objects.filter(club=club)
    bookings = BookClub.objects.filter(package__in=packages)

    # Filter by single date or date range
    if date:
        bookings = bookings.filter(date__date=date)
    elif start_date and end_date:
        bookings = bookings.filter(date__date__range=[start_date, end_date])

    # Search filter
    if search_query:
        bookings = bookings.filter(
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query) |
            Q(user__username__icontains=search_query)
        )


    paginator = Paginator(bookings, 10)  # Show 10 teams per page
    page = request.GET.get('page')
    
    try:
        bookings = paginator.page(page)
    except PageNotAnInteger:
        bookings = paginator.page(1)
    except EmptyPage:
        bookings = paginator.page(paginator.num_pages)

    results = [
        {
            "name": booking.user.username,
            "email": booking.user.email,
            "booking_date": booking.date.strftime("%Y-%m-%d %H:%M:%S"),
        }
        for booking in bookings
    ]

    return render(request, 'sides/booking_list.html', {
        "results": results,
        
        "total_bookings": len(bookings),  # Total booking count
        "search_query": search_query,
        "selected_date": date,
        "start_date": start_date,
        "end_date": end_date,
        'club_id':club.id
        
    })


def joined_list(request, club_id):
    search_query = request.GET.get("search", "")
    club = get_object_or_404(Club, id=club_id)
    
    joined_users = JoinClub.objects.filter(club=club, status=True, block=False)
    if search_query:
        joined_users = joined_users.filter(
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query) |
            Q(user__username__icontains=search_query)
        )
    paginator = Paginator(joined_users, 10)  # Show 10 teams per page
    page = request.GET.get('page')
    
    try:
        joined_users = paginator.page(page)
    except PageNotAnInteger:
        joined_users = paginator.page(1)
    except EmptyPage:
        joined_users = paginator.page(paginator.num_pages)

    results = [
        {
            "name": join.user.username,
            "email": join.user.email,
        }
        for join in joined_users
    ]

    return render(request, 'sides/joined_list.html', {
        "results": results,
        
        "total_joined": len(joined_users),  # Total booking count
        "search_query": search_query,
        'club_id':club.id
        
    })

def confirm_payment_for_join_club(request):
    if request.method == "POST":
        data = json.loads(request.body)
        #print('Data received:', data)
        club_id = data.get('club_id')
        club = Club.objects.filter(id=club_id).first()
        if JoinClub.objects.filter(user=request.user, club=club).exists():
            return JsonResponse({"error": "Already joined in club"}, status=400)

        # ✅ Get User Wallet & Balance
        wallet = Wallet.objects.filter(user=request.user).first()
        club_wallet = Wallet.objects.filter(user=club.user).first()
        admin_wallet = Wallet.objects.filter(user__is_superuser=True).first()
        balance = wallet.balance if wallet else 0

        if club.join_amount in [0, 0.0, None, "0"]:
            # ✅ Create JoinClub Entry
            join = JoinClub(user=request.user, club=club)
            join.status = True
            join.save()
            return JsonResponse({"success": "Club joined successfully!"}, status=201)

        # ✅ Validate Join Price
        join_price = club.join_amount if club.join_amount not in [None, "null", "None"] else 0
        club_wonner_wallet = Wallet.objects.filter(user=club.user).first()
        if balance >= join_price:
            club_amount = (club.join_amount * Decimal(settings.CLUB_PERCENTAGE)) / 100
            admin_amount = (club.join_amount * Decimal(settings.ADMIN_PERCENTAGE_CLUB)) / 100
            
            WalletTransaction.objects.create(
                sender = request.user,
                reciver = club.user,   
                reciver_cost = round(club_amount, 2),                  
                admin_cost= round(admin_amount, 2),
                getway_charge = 0,                        
                transaction_for="JoinClub",                                   
                transaction_type="debit",
                amount= club.join_amount,
                payment_id=None, 
                description=f"${club.join_amount} is debited from your PickleIt wallet for join {club.name} club."
                )
            wallet.balance -= join_price
            club_wallet.balance += club_amount
            admin_wallet.balance += admin_amount
            admin_wallet.save()
            club_wallet.save()
            wallet.save()
            club_wonner_wallet.balance = club_wonner_wallet.balance + join_price
            club_wonner_wallet.save()
            
            # ✅ Create JoinClub Entry
            join = JoinClub(user=request.user, club=club)
            join.status = True
            join.save()
            #update admin wallet balance
            admin_wallet = Wallet.objects.filter(user__is_superuser=True).first()
            if admin_wallet:
                admin_wallet.balance = Decimal(str(admin_wallet.balance)) + join_price
                admin_wallet.save()
            
            # ✅ Send Notification
            user_id = club.user.id
            message = f"{request.user.first_name} join your club: {club.name}"
            title = "User Join Club"
            notify_edited_player(user_id, title, message)
            return JsonResponse({'success': 'Booking club is successfull'}, status=201)   
        else:
            return JsonResponse({'error': 'Insufficient balance'}, status=400)         
    
    return JsonResponse({'error': 'Invalid request'}, status=400)


def initiate_stripe_payment_for_join_club(request):
    if request.method == "POST":
        data = json.loads(request.body)
        #print('Data received:', data)
        club_id = data.get('club_id')
        club = Club.objects.filter(id=club_id).first()
        without_fees = float(data.get('remaining_amount'))
        remaining_amount = float(data.get("total_amount_with_fees"))

        total_charge = round(Decimal(remaining_amount), 2)
        charge_amount = round(float(total_charge * 100))
        stripe_fees = Decimal(remaining_amount - without_fees)

        #print(charge_amount)
        make_request_data = {"club_id":club.id}
        json_bytes = json.dumps(make_request_data).encode('utf-8')
        my_data = base64.b64encode(json_bytes).decode('utf-8')
        product_name = f"Join {club.name} Club"
        product_description = "Payment received by Pickleit"
        stripe.api_key = settings.STRIPE_SECRET_KEY
        if request.user.stripe_customer_id :
            stripe_customer_id = request.user.stripe_customer_id
        else:
            customer = stripe.Customer.create(email=request.user.email).to_dict()
            stripe_customer_id = customer["id"]
            request.user.stripe_customer_id = stripe_customer_id
            request.user.save()        

        protocol = settings.PROTOCALL
        host = request.get_host()
        current_site = f"{protocol}://{host}"
        main_url = f"{current_site}/user_side'stripe_success_for_join_club/{stripe_fees}/{my_data}/"
        product = stripe.Product.create(name=product_name,description=product_description,).to_dict()
        price = stripe.Price.create(unit_amount=charge_amount,currency='usd',product=product["id"],).to_dict()
        try:
            session = stripe.checkout.Session.create(
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
            return JsonResponse({"success": True, "stripe_url": session.url})
        
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    return JsonResponse({"success": False, "error": "Invalid request"})


def stripe_success_for_join_club(request, stripe_fees, my_data, checkout_session_id):
    try:
        
        pay = stripe.checkout.Session.retrieve(checkout_session_id).to_dict()
        payment_status = pay.get("payment_status") == "paid"
        amount_total = Decimal(pay.get("amount_total", 0)) / 100  # Convert to Decimal
        payment_method_types = pay.get("payment_method_types", [])

        # Decode and parse JSON data
        json_bytes = base64.b64decode(my_data)
        request_data = json.loads(json_bytes.decode('utf-8'))
        club_id = request_data.get("club_id")
        club = get_object_or_404(Club, id=club_id)
        get_user = get_object_or_404(User, id=request_data.get("user_id"))
        payment_for = f"join {club.name} club"
        wallet = Wallet.objects.filter(user_id=request.user.id).first()
        get_wallet = Wallet.objects.filter(user=club.user).first()
        admin_wallet = Wallet.objects.filter(user__is_superuser=True).first()
            
        existing_payment = AllPaymentsTable.objects.filter(user=get_user, checkout_session_id=checkout_session_id).exists()

        if not existing_payment and payment_status:
            AllPaymentsTable.objects.create(
                user=get_user,
                amount=club.join_amount,
                checkout_session_id=checkout_session_id,
                payment_mode=", ".join(payment_method_types),
                payment_for=payment_for,
                status="Completed" if payment_status else "Failed"
            )
            wallet.balance=0
            wallet.save()
            join = JoinClub(user=get_user, club=club)
            join.status = True
            join.save()
            
            club_amount = (club.join_amount * Decimal(settings.CLUB_PERCENTAGE)) / 100
            admin_amount = (club.join_amount * Decimal(settings.ADMIN_PERCENTAGE_CLUB)) / 100

            # Ensure rounding is done while keeping values as Decimal
            if admin_amount is not None:
                admin_amount = admin_amount.quantize(Decimal("0.01"))  # Keeps 2 decimal places
            if club_amount is not None:
                club_amount = club_amount.quantize(Decimal("0.01"))
            WalletTransaction.objects.create(
                sender=get_user,
                reciver=club.user,
                admin_cost=str(admin_amount),
                reciver_cost=str(club_amount),
                getway_charge=str(stripe_fees),
                transaction_for="JoinClub",
                transaction_type="debit",
                amount=Decimal(round(float(club.join_amount), 2)),
                payment_id=checkout_session_id,
                description=f"${amount_total} is debited from your PickleIt wallet for join club to {club.name}."
            )
            #print(type(get_wallet.balance), get_wallet.balance, type(club_amount), club_amount)
            get_wallet.balance += club_amount
            admin_wallet.balance += admin_amount
            get_wallet.save()
            admin_wallet.save()
            return redirect("user_side:club_view", pk=club.id)
        else:
            return JsonResponse({"success": True, "message": f"You have already booked the club."})

    except stripe.error.StripeError as e:
        return JsonResponse({"success": False, "message": f"Stripe error: {str(e)}"})
    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)})


@login_required(login_url="/user_side/")
def add_my_club(request):
    if request.method == "POST":
        name = request.POST.get("name")
        location = request.POST.get("location")        
        open_time = request.POST.get("open_time")
        close_time = request.POST.get("close_time")
        contact = request.POST.get("contact")
        email = request.POST.get("email")
        is_vip = request.POST.get("is_vip") == "on"
        description = request.POST.get("description")
        join_amount = request.POST.get("join_amount")
        unit = request.POST.get("unit")
        latitude, longitude = get_lat_long_google(settings.MAP_API_KEY, location)

        club = Club.objects.create(
            user=request.user,
            name=name,
            location=location,
            latitude=latitude,
            longitude=longitude,
            open_time=open_time,
            close_time=close_time,
            contact=contact,
            email=email,
            is_vip=is_vip,
            description=description,
            join_amount=join_amount,
            unit=unit           
        )

        # Handling Image Uploads
        images = request.FILES.getlist("images")
        for image in images:
            ClubImage.objects.create(club=club, image=image)

        return redirect("user_side:my_club_list")  # Redirect to a club list or another page

    return render(request, "sides/add_my_club.html")

def my_club_list(request):
    query = request.GET.get('q', '')
    latitude = request.GET.get('latitude', '')
    longitude = request.GET.get('longitude', '')
    check_plan = Subscription.objects.filter(
        user=request.user,
        is_active=True,
        end_date__date__gte=datetime.now().date()
    ).exists()
    clubs = Club.objects.filter(diactivate=False, user=request.user)

    if query:
        clubs = clubs.filter(Q(name__icontains=query) | Q(description__icontains=query))
    if latitude and longitude:
        try:
            user_location = (float(latitude), float(longitude))
            max_distance_km = 100  # Search radius in km
            clubs = [club for club in clubs if geodesic(user_location, (float(club.latitude), float(club.longitude))).km <= max_distance_km]
        except ValueError:
            clubs = clubs  # No filtering if coordinates are invalid
    if clubs:
        clubs_json = json.dumps([
            {
                'id': club.id,
                'name': club.name,
                'location': club.location,
                'latitude': float(club.latitude),
                'longitude': float(club.longitude)
            } for club in clubs
        ])
    else:
        clubs_json = json.dumps([])
    paginator = Paginator(clubs, 9)
    page = request.GET.get('page')
    
    try:
        clubs = paginator.page(page)
    except PageNotAnInteger:
        clubs = paginator.page(1)
    except EmptyPage:
        clubs = paginator.page(paginator.num_pages)
     
    return render(request, 'sides/my_club_list.html', {
        'clubs': clubs,
        'query': query,
        'location_query': request.GET.get('location', ''),
        'latitude': latitude,
        'longitude': longitude,
        'google_api_key': settings.MAP_API_KEY,
        'clubs_json': clubs_json,
        'error': 'Upgrade your plan' if not check_plan else None
    })

@csrf_exempt
def add_my_club_package(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            club = Club.objects.get(id=data["club_id"])
            
            # Ensure only the club creator can add packages
            if request.user != club.user:
                return JsonResponse({"success": False, "error": "Permission denied!"}, status=403)

            ClubPackage.objects.create(
                club=club,
                name=data["name"],
                price=data["price"],
                unit=data["unit"],
                valid_start_date=data.get("valid_start_date"),
                valid_end_date=data.get("valid_end_date"),
                member=data.get("member", 1),
                member_ship_discount=data.get("member_ship_discount", 0),
                description=data["description"]
            )

            return JsonResponse({"success": True})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)}, status=400)

    return JsonResponse({"success": False, "error": "Invalid request method!"}, status=405)


def load_more_reviews(request, club_id):
    reviews = ClubRating.objects.filter(club_id=club_id).order_by("id")
    paginator = Paginator(reviews, 2)  # Load 2 reviews per request
    page = request.GET.get("page", 1)

    try:
        reviews_page = paginator.page(page)  # Correct way to get a specific page
    except:
        return JsonResponse({"reviews": [], "has_more": False})

    reviews_data = [
        {"username": r.name, "rating": r.rating, "comment": r.comment} for r in reviews_page
    ]

    return JsonResponse({"reviews": reviews_data, "has_more": reviews_page.has_next()})


@csrf_exempt
def add_review(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            club = Club.objects.get(id=data["club_id"])

            if request.user == club.user:
                return JsonResponse({"success": False, "error": "You cannot review your own club!"}, status=403)

            ClubRating.objects.create(
                club=club,
                name=f"{request.user.first_name}",
                rating=int(data["rating"]),
                comment=data.get("comment", "")
            )

            return JsonResponse({"success": True})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)}, status=400)

    return JsonResponse({"success": False, "error": "Invalid request method!"}, status=405)


def all_court_list(request):
    query = request.GET.get('q', '')
    location = request.GET.get('location', '')
    
    courts = Courts.objects.all()

    if query:
        courts = courts.filter(Q(name__icontains=query) | Q(about__icontains=query))
    if location:
        latitude, longitude = get_lat_long_google(settings.MAP_API_KEY, location)
        user_location = (float(latitude), float(longitude))
        max_distance_km = 100  # Search radius in km

        # Filter clubs by distance using geopy
        courts = [court for court in courts if geodesic(user_location, (float(court.latitude), float(court.longitude))).km <= max_distance_km]

    courts_json = json.dumps([
        {
            "id": court.id,
            "name": court.name,
            "location": court.location,
            "latitude": float(court.latitude) if isinstance(court.latitude, Decimal) else court.latitude,
            "longitude": float(court.longitude) if isinstance(court.longitude, Decimal) else court.longitude,
        }
        for court in courts
    ])
    paginator = Paginator(courts, 9)  # Show 10 teams per page
    page = request.GET.get('page')
    
    try:
        courts = paginator.page(page)
    except PageNotAnInteger:
        courts = paginator.page(1)
    except EmptyPage:
        courts = paginator.page(paginator.num_pages)

    
    return render(request, 'sides/court_list.html', {'courts':courts, 'query':query, 'location_query':location, "google_api_key": settings.MAP_API_KEY, "courts_json": courts_json})


def my_court_list(request):
    query = request.GET.get('q', '')
    latitude = request.GET.get('latitude', '')
    longitude = request.GET.get('longitude', '')
    
    # Check if the user has an active subscription
    check_plan = Subscription.objects.filter(
        user=request.user,
        is_active=True,
        end_date__date__gte=datetime.now().date()
    ).exists()
    
    courts = Courts.objects.filter(created_by=request.user)

    if query:
        courts = courts.filter(Q(name__icontains=query) | Q(about__icontains=query))
    if latitude and longitude:
        try:
            user_location = (float(latitude), float(longitude))
            max_distance_km = 100  # Search radius in km
            courts = [court for court in courts if geodesic(user_location, (float(court.latitude), float(court.longitude))).km <= max_distance_km]
        except ValueError:
            courts = courts  # No filtering if coordinates are invalid

    # Convert courts to a list of dictionaries for JSON serialization
    courts_json = json.dumps([
        {
            'id': court.id,
            'name': court.name,
            'location': court.location,
            'latitude': float(court.latitude),
            'longitude': float(court.longitude),
        }
        for court in courts
    ])

    paginator = Paginator(courts, 9)  # Show 9 courts per page
    page = request.GET.get('page')
    
    try:
        courts = paginator.page(page)
    except PageNotAnInteger:
        courts = paginator.page(1)
    except EmptyPage:
        courts = paginator.page(paginator.num_pages)

    return render(request, 'sides/my_court_list.html', {
        'courts': courts,
        'query': query,
        'location_query': request.GET.get('location', ''),
        'latitude': latitude,
        'longitude': longitude,
        'google_api_key': settings.MAP_API_KEY,
        'courts_json': courts_json,
        'error': 'Upgrade your plan' if not check_plan else None
    })


def court_view(request, pk):
    court = get_object_or_404(Courts, id=int(pk))
    return render(request, 'sides/court_view.html', {'court':court})

def add_my_court(request):
    if request.method == "POST":
        name = request.POST.get('name')
        location = request.POST.get('location')
        open_time = request.POST.get('open_time')
        close_time = request.POST.get('close_time')
        price = request.POST.get('price')
        price_unit = request.POST.get('price_unit')
        offer_price = request.POST.get('offer_price') if request.POST.get('offer_price') else None
        about = request.POST.get('about')
        owner_name = request.POST.get('owner_name')
        latitude, longitude = get_lat_long_google(settings.MAP_API_KEY, location)

        court = Courts(
            name=name,
            location=location,
            open_time=open_time,
            close_time=close_time,
            price=price,
            price_unit=price_unit,
            offer_price=offer_price,
            about=about,
            owner_name=owner_name,
            created_by=request.user  # Set the user who created the court
        )


        # Handling Image Uploads
        images = request.FILES.getlist("images")
        for image in images:
            CourtImage.objects.create(court=court, image=image)

        return redirect("user_side:my_court_list")  # Redirect to a club list or another page

    return render(request, "sides/add_my_court.html")


def read_notifications(request):
    """
    Marks notifications as read based on provided IDs.
    """
    if request.method == "POST":
        try:
            data = json.loads(request.body)  
            notification_ids = data.get("unread_notification_ids", [])

            if not notification_ids:
                return JsonResponse({"error": "No notification IDs provided"}, status=400)
            
            updated_count = NotificationBox.objects.filter(
                id__in=notification_ids, notify_for=request.user, is_read=False
            ).update(is_read=True)

            return JsonResponse({"success": True, "updated_count": updated_count}, status=200)

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON format"}, status=400)
    
    return JsonResponse({"error": "Invalid request method"}, status=405)


@login_required
def social_feed(request):
    check_plan = Subscription.objects.filter(
        user=request.user,
        is_active=True,
        end_date__date__gte=datetime.now().date()
    ).exists()
    user_likes = LikeFeed.objects.filter(
        user=request.user, post=OuterRef('pk')
    )
    posts = socialFeed.objects.filter(block=False).annotate(is_like=Exists(user_likes)).order_by('-created_at')
    paginator = Paginator(posts, 6)
    page_number = request.GET.get('page', 1)
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)
    return render(request, 'sides/social_feed.html', {'socail_feed_list': page_obj, 'error': 'Upgrade your plan' if not check_plan else None})

@login_required
@require_POST
def edit_post(request, post_id):
    post = get_object_or_404(socialFeed, id=post_id)
    
    # Check if the user is authorized to edit the post
    if post.user != request.user:
        return JsonResponse({'error': 'You are not authorized to edit this post.'}, status=403)

    try:
        data = json.loads(request.body)
        new_text = data.get('text')
        if not new_text:
            return JsonResponse({'error': 'Post content cannot be empty.'}, status=400)

        post.text = new_text
        post.save()
        return JsonResponse({'success': True, 'text': post.text})
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid data format.'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def delete_post(request, post_id):
    post = get_object_or_404(socialFeed, id=post_id)
    
    # Check if the user is authorized to delete the post
    if post.user != request.user:
        return JsonResponse({'error': 'You are not authorized to delete this post.'}, status=403)

    try:
        # Delete associated files from the filesystem
        for feed_file in post.post_file.all():
            if feed_file.file and os.path.isfile(feed_file.file.path):
                os.remove(feed_file.file.path)  # Delete the file from the filesystem
            feed_file.delete()  # Delete the FeedFile record

        # Delete the post
        post.delete()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def add_post(request):
    if request.method == 'POST':
        text = request.POST.get('text')
        file = request.FILES.get('file')
        post = socialFeed.objects.create(user=request.user, text=text)
        if file:
            FeedFile.objects.create(post=post, file=file)
        messages.success(request, 'Post created successfully!')
        return redirect('user_side:socail_feed_list')
    return render(request, 'sides/social_feed.html')

@login_required
def like_post(request, post_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    # print("hit")
    post = get_object_or_404(socialFeed, id=post_id)
    like, created = LikeFeed.objects.get_or_create(post=post, user=request.user)
    
    if not created:
        like.delete()
        post.number_like = post.number_like - 1
        post.save()
        is_liked = False
    else:
        is_liked = True
    
    return JsonResponse({
        'is_liked': is_liked,
        'like_count': post.number_like
    })

@login_required
def add_comment(request, post_id):
    post = get_object_or_404(socialFeed, id=post_id)
    if request.method == 'POST':
        comment_text = request.POST.get('comment_text')
        if comment_text:
            CommentFeed.objects.create(post=post, user=request.user, comment_text=comment_text)
            messages.success(request, 'Comment added successfully!')
    return HttpResponseRedirect(request.META.get('HTTP_REFERER', reverse('user_side:socail_feed_list')))

@login_required
def view_post(request, post_id):
    post = get_object_or_404(socialFeed, id=post_id, block=False)
    comments = post.post_comment.all().order_by('-created_at')
    return render(request, 'sides/view_post.html', {'post': post, 'comments': comments})


@login_required
def create_store(request):
    if request.user.stores.exists():
        messages.warning(request, "You already have a store.")
        return redirect('user_side:my_store_user_side')
    
    if request.method == 'POST':
        name = request.POST.get('store_name')
        company_name = request.POST.get('company_name')
        description = request.POST.get('description')
        company_website = request.POST.get('company_website')
        
        if name and company_name:
            store = MerchandiseStore(
                name=name,
                company_name=company_name,
                description=description,
                company_website=company_website,
                owner=request.user
            )
            store.save()
            messages.success(request, "Store created successfully!")
            return redirect('user_side:my_store_user_side')
        else:
            messages.error(request, "Store name and company name are required.")
    
    return render(request, 'store/create_store.html')


from rest_framework import serializers
class ProductListSerializer(serializers.ModelSerializer):
    category__name = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    created_by__first_name = serializers.SerializerMethodField()
    created_by__last_name = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()
    old_price = serializers.SerializerMethodField()
    discount = serializers.SerializerMethodField()
    star_percentage = serializers.SerializerMethodField()
    

    class Meta:
        model = MerchandiseStoreProduct
        fields = ['id','uuid','secret_key','category__name','name','store_name','price','old_price','discount','description','specifications','rating','rating_count','advertisement_image','image','is_love','has_single_spec','created_by__first_name','created_by__last_name', 'star_percentage']
    
    def to_representation(self, instance):
        # Update rating before serialization
        instance.update_rating()
        return super().to_representation(instance)

    def get_category__name(self, obj):
        return obj.category.name
    
    def get_image(self, obj):
        images_ins = MerchandiseProductImages.objects.filter(product=obj).first()
        if images_ins and images_ins.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(images_ins.image.url)
            return images_ins.image.url
        return None
    
    def get_created_by__first_name(self, obj):
        return obj.created_by.first_name
    
    def get_created_by__last_name(self, obj):
        return obj.created_by.last_name
    
    def get_price(self, obj):
        try:
            prices = MerchandiseProductSpecification.objects.filter(product=obj).values_list('current_price', flat=True)
            # print(prices)
            price = min(prices)
            # print(price)
            return price
        except:
            return 0
    
    def get_old_price(self, obj):
        try:
            prices = MerchandiseProductSpecification.objects.filter(product=obj).values_list('old_price', flat=True)
            # print(prices)
            price = max(prices)
            # print(price)
            return price
        except:
            return 0

    def get_discount(self, obj):
        discounts = MerchandiseProductSpecification.objects.filter(product=obj).values_list('discount', flat=True)

        # Filter out None values
        discounts = [d for d in discounts if d is not None]

        discount = max(discounts) if discounts else 0
        return round(discount, 2)
    
    def get_star_percentage(self, obj):
        if obj.rating:
            star_percentage = (obj.rating / 5) * 100
        else:
            star_percentage = 0
        return star_percentage

@login_required
def product_list(request):
    context = {}
    categories = MerchandiseStoreCategory.objects.all()
    categories = sorted(
        categories,
        key=lambda c: (c.name.lower() == "others", c.name.lower())
    )
    search_text = request.GET.get("search_text")
    
    product_list = MerchandiseStoreProduct.objects.all().exclude(created_by=request.user)
    if search_text:
        product_list = product_list.filter(Q(name__icontains=search_text) | Q(description__icontains=search_text) | Q(specifications__icontains=search_text) | Q(category__name__icontains=search_text) | Q(leagues_for__name__icontains=search_text)).distinct()
    
    category_id = request.GET.get("category")
    print("Category id", category_id)

    if category_id:
        product_list = product_list.filter(category_id=category_id)
    # Step 4: Pagination
    page = request.GET.get("page", 1)
    paginator = Paginator(product_list, 20)
    try:
        product_page = paginator.page(page)
    except:
        product_page = paginator.page(1)
    serialized_products = ProductListSerializer(product_page, many=True, context={'request': request}).data
    context.update({
        "product_list": serialized_products,
        "search_text": search_text,
        "categories":categories,
        "page_obj":product_page
    })
    return render(request, "store/product_list.html", context)


@login_required
def my_store(request):
    search_text = request.GET.get("search_text")
    category_id = request.GET.get("category")
    check_plan = Subscription.objects.filter(
        user=request.user,
        is_active=True,
        end_date__date__gte=datetime.now().date()
    ).exists()
    # store = request.user.stores.first()
    # if not store:
    #     messages.warning(request, "Please create a store before accessing this page.")
    #     return redirect('user_side:create_store_user_side')
    
    categories = MerchandiseStoreCategory.objects.filter(
        id__in=MerchandiseStoreProduct.objects.filter(created_by=request.user).values_list("category_id", flat=True).distinct()
    ).order_by("name")

    # ✅ Keep your custom sorting (push "Others" to the bottom)
    categories = sorted(
        categories,
        key=lambda c: (c.name.lower() == "others", c.name.lower())
    )
    products = MerchandiseStoreProduct.objects.filter(created_by=request.user)
    if search_text:
        products = products.filter(Q(name__icontains=search_text) | Q(description__icontains=search_text) | Q(specifications__icontains=search_text) | Q(category__name__icontains=search_text) | Q(leagues_for__name__icontains=search_text)).distinct()

    if category_id:
        products = products.filter(category_id=category_id)

    paginator = Paginator(products, 15)
    page_number = request.GET.get('page', 1)
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)
    serialized_products = ProductListSerializer(page_obj, many=True, context={'request': request}).data
    
    return render(request, 'store/my_store.html', {
        'categories': categories,
        'products': serialized_products,
        'page_obj':page_obj,
        'error': 'Upgrade your plan' if not check_plan else None
    })


@login_required
def cart_count(request):
    cart_products = CustomerMerchandiseStoreProductBuy.objects.filter(
        created_by=request.user,
        status='CART'
    ).values(
        'product', 'size', 'color'
    ).annotate(
        total_quantity=Count('id')
    )

    cart_products_count = cart_products.count()
    return JsonResponse({'count': cart_products_count})


@login_required
def pending_received_order_count(request):
    pending_orders = CustomerMerchandiseStoreProductBuy.objects.filter(
        product__created_by=request.user,
        status='ORDER PLACED'
    )
    pending_received_order_count = pending_orders.count()
    return JsonResponse({'count': pending_received_order_count})

@csrf_exempt
@login_required
def add_store_product(request):
    context = {}
    
    if request.method == 'POST':
        try:
            # Extract base product info
            name = request.POST.get('productName')
            category_id = request.POST.get('productCategory')
            description = request.POST.get('description', '')
            specification_text = request.POST.get('specification', '')
            events = request.POST.getlist('events')
            poster_image = request.FILES.get('posterImage')
            product_images = request.FILES.getlist('productImages')
            variation_type = request.POST.get('variationType')

            # Get model instances
            category = MerchandiseStoreCategory.objects.get(id=category_id) if category_id else None
            leagues = Leagues.objects.filter(id__in=events) if events else []

            if variation_type != 'single':
                variation_ids = [key.split('-')[1] for key in request.POST.keys() if key.startswith('variationType-')]
                seen_combinations = set()

                for var_id in set(variation_ids):
                    var_type = request.POST.get(f'variationType-{var_id}')
                    size = (request.POST.get(f'size-{var_id}', '') or '').strip().lower() if var_type in ['size', 'both'] else None
                    color = (request.POST.get(f'color-{var_id}', '') or '').strip().lower() if var_type in ['color', 'both'] else None

                    if size and color:
                        key = f'{size}-{color}'
                    elif size and not color:
                        key = f'{size}-none'
                    elif color and not size:
                        key = f'none-{color}'
                    else:
                        key = 'none-none'

                    if key in seen_combinations:
                        messages.error(request, f"Duplicate specification detected: size/color combination '{key}' must be unique.")
                        return render(request, 'store/create_product_form.html')

                    seen_combinations.add(key)

            # Create base product
            secret_key = GenerateKey().gen_product_key()
            product = MerchandiseStoreProduct.objects.create(
                secret_key=secret_key,
                name=name,
                category=category,
                description=description,
                specifications=specification_text,
                advertisement_image=poster_image,
                has_single_spec=(variation_type == 'single'),
                created_by=request.user
            )
            product.leagues_for.set(leagues)

            # Add images
            for img in product_images:
                MerchandiseProductImages.objects.create(product=product, image=img)

            # Add variations
            if variation_type == 'single':
                # Only one spec allowed
                regular_price = request.POST.get('singleRegularPrice')
                sale_price = request.POST.get('singleSalePrice')
                available = request.POST.get('singleAvailable')

                spec = MerchandiseProductSpecification.objects.create(
                    product=product,
                    current_price=int(sale_price),
                    old_price=int(regular_price),
                    total_product=int(available),
                )

                # Add highlights
                topics = request.POST.getlist('highlightTopic-single')
                descriptions = request.POST.getlist('highlightDesc-single')
                for topic, desc in zip(topics, descriptions):
                    if topic or desc:
                        ProductSpecificationHighlights.objects.create(
                            specification=spec,
                            highlight_key=topic,
                            highlight_des=desc
                        )
            else:
                # Multiple specs allowed
                variation_ids = [key.split('-')[1] for key in request.POST.keys() if key.startswith('variationType-')]
                for var_id in set(variation_ids):
                    var_type = request.POST.get(f'variationType-{var_id}')
                    size = request.POST.get(f'size-{var_id}', '') if var_type in ['size', 'both'] else None
                    color = request.POST.get(f'color-{var_id}', '') if var_type in ['color', 'both'] else None
                    regular_price = request.POST.get(f'regularPrice-{var_id}')
                    sale_price = request.POST.get(f'salePrice-{var_id}')
                    available = request.POST.get(f'available-{var_id}')

                    spec = MerchandiseProductSpecification.objects.create(
                        product=product,
                        size=size,
                        color=color,
                        current_price=int(sale_price),
                        old_price=int(regular_price),
                        total_product=int(available),
                    )

                    # Add highlights
                    topics = request.POST.getlist(f'highlightTopic-{var_id}')
                    descriptions = request.POST.getlist(f'highlightDesc-{var_id}')
                    for topic, desc in zip(topics, descriptions):
                        if topic or desc:
                            ProductSpecificationHighlights.objects.create(
                                specification=spec,
                                highlight_key=topic,
                                highlight_des=desc
                            )

            return redirect('user_side:my_store_user_side')

        except Exception as e:
            # print(f"Error: {str(e)}")
            messages.error(request, f"{str(e)}")
            return render(request, 'store/create_product_form.html')
    # GET request
    context["categories"] = MerchandiseStoreCategory.objects.all().values("id", "name")
    context["events"] = Leagues.objects.all().values("id", "name")
    return render(request, 'store/create_product_form.html', context)


@login_required
def store_product_view(request, product_id):
    product = get_object_or_404(MerchandiseStoreProduct, id=product_id)
    if product.rating:
        product.star_percentage = (product.rating / 5) * 100
    else:
        product.star_percentage = 0
    images = product.productImages.all()
    all_ratings = product.ratedProduct.all().order_by('-created_at')
    latest_ratings = all_ratings[:5]


    specifications = product.specificProduct.all()
    colors = list(specifications.exclude(color__isnull=True).values_list('color', flat=True).distinct())
    sizes = list(specifications.exclude(size__isnull=True).values_list('size', flat=True).distinct())
    
    # ✅ Only select in-stock default
    default_spec = specifications.filter(available_product__gt=0).first()
    default_size = default_spec.size if default_spec else None
    default_color = default_spec.color if default_spec else None
    default_highlights = []
    if default_spec:
        default_highlights = list(default_spec.specificHighlight.values('highlight_key', 'highlight_des'))

    size_color_map = [
        {'size': spec.size, 'color': spec.color}
        for spec in specifications if spec.available_product > 0
    ]
    wishlist_status = False
    if request.user in product.is_love.all():
        wishlist_status = True
    context = {
        'product': product,
        'images': images,
        'specifications': specifications,
        'ratings': latest_ratings,
        'colors': colors,
        'sizes': sizes,
        'size_color_map': json.dumps(size_color_map),
        'default_size': default_size,
        'default_color': default_color,
        'default_highlights': default_highlights,
        "latest_ratings": latest_ratings,
        "all_ratings": all_ratings,
        "is_button": request.user.id == product.created_by.id,
        "wishlist_status":wishlist_status
    }
    return render(request, 'store/product_detail.html', context)


def get_specification_data(request):
    product_id = request.GET.get('product_id')
    size = request.GET.get('size')
    color = request.GET.get('color')

    try:
        spec = MerchandiseProductSpecification.objects.get(
            product_id=product_id, size=size, color=color
        )

        highlights = list(spec.specificHighlight.values('highlight_key', 'highlight_des'))

        return JsonResponse({
            'success': True,
            'old_price': spec.old_price,
            'current_price': spec.current_price,
            'discount': spec.discount,
            'available_product': spec.available_product,
            'highlights': highlights
        })
    except MerchandiseProductSpecification.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Specification not found'})


def load_single_variation_edit(request, product_id):
    product = get_object_or_404(MerchandiseStoreProduct, id=product_id)
    return render(request, 'component/single_variation_edit.html', {'product': product})


def load_multiple_variation_edit(request, product_id):
    product = get_object_or_404(MerchandiseStoreProduct, id=product_id)
    return render(request, 'component/multiple_variation_edit.html', {'product': product})


@login_required
def edit_store_product(request, product_id):
    context = {}
    product = get_object_or_404(MerchandiseStoreProduct, id=int(product_id))
    context["product"] = product
    context["categories"] = MerchandiseStoreCategory.objects.all().values("id", "name")
    context["events"] = Leagues.objects.all().values("id", "name")
    if request.method == "POST":
        product.name = request.POST.get("productName")
        category_id = request.POST.get("productCategory")        
        product.description = request.POST.get("description", "")
        product.specifications = request.POST.get("specification", "")
        # Handle variation type
        variation_type = request.POST.get("variationType")
        product.has_single_spec = variation_type == "single"

        if variation_type != 'single':
            variation_ids = [key.split('-')[1] for key in request.POST.keys() if key.startswith('variationType-')]
            seen_combinations = set()

            for var_id in set(variation_ids):
                var_type = request.POST.get(f'variationType-{var_id}')
                size = (request.POST.get(f'size-{var_id}', '') or '').strip().lower() if var_type in ['size', 'both'] else None
                color = (request.POST.get(f'color-{var_id}', '') or '').strip().lower() if var_type in ['color', 'both'] else None

                if size and color:
                    key = f'{size}-{color}'
                elif size and not color:
                    key = f'{size}-none'
                elif color and not size:
                    key = f'none-{color}'
                else:
                    key = 'none-none'

                if key in seen_combinations:
                    messages.error(request, f"Duplicate specification detected: size/color combination '{key}' must be unique.")
                    return render(request, 'store/edit_product.html')

                seen_combinations.add(key)

        if category_id:
            category = MerchandiseStoreCategory.objects.filter(id=int(category_id)).first()
            product.category = category
        
        product.save()
        # Events (many-to-many)
        event_ids = request.POST.getlist("events")
        for id in event_ids:
            event = Leagues.objects.filter(id=int(id)).first()
            if event:
                product.leagues_for.set(event_ids)
  
        # Handle Poster Image
        if request.FILES.get("posterImage"):
            product.advertisement_image = request.FILES.get("posterImage")

        # Save product early so we can use it for FK relations
        product.save()

        product.specificProduct.all().delete()

        if variation_type == "single":
            # Create single variation
            spec = MerchandiseProductSpecification.objects.create(
                product=product,
                size=request.POST.get("single-size") or None,
                color=request.POST.get("single-color") or None,
                old_price=int(request.POST.get("single-regularPrice")) or 0,
                current_price=int(request.POST.get("single-salePrice")) or 0,
                available_product=int(request.POST.get("single-available")) or 0,
            )

            # Save highlights for single
            topics = request.POST.getlist("highlightTopic-single")
            descs = request.POST.getlist("highlightDesc-single")
            for topic, desc in zip(topics, descs):
                if topic.strip() or desc.strip():
                    ProductSpecificationHighlights.objects.create(
                        specification=spec, highlight_key=topic.strip(), highlight_des=desc.strip()
                    )

        else:
            # Multiple variations are dynamically generated
            variation_ids = [key.split("-")[1] for key in request.POST if key.startswith("size-")]

            for vid in variation_ids:
                size = request.POST.get(f"size-{vid}", "")
                color = request.POST.get(f"color-{vid}", "")
                old_price = request.POST.get(f"regularPrice-{vid}", 0)
                current_price = request.POST.get(f"salePrice-{vid}", 0)
                available_product = request.POST.get(f"available-{vid}", 0)

                spec = MerchandiseProductSpecification.objects.create(
                    product=product,
                    size=size,
                    color=color,
                    old_price=int(old_price),
                    current_price=int(current_price),
                    available_product=int(available_product),
                )

                topics = request.POST.getlist(f"highlightTopic-{vid}")
                descs = request.POST.getlist(f"highlightDesc-{vid}")
                for topic, desc in zip(topics, descs):
                    if topic.strip() or desc.strip():
                        ProductSpecificationHighlights.objects.create(
                            specification=spec, highlight_key=topic.strip(), highlight_des=desc.strip()
                        )
        # Handle product image deletion
        remove_ids = request.POST.getlist("remove_image_ids")
        remove_ids = [id for id in remove_ids if id.strip().isdigit()]  
        # print(remove_ids) # Keep only numeric IDs
        if remove_ids:
            MerchandiseProductImages.objects.filter(id__in=remove_ids, product=product).delete()

        # Handle new product images
        for img_file in request.FILES.getlist("productImages"):
            MerchandiseProductImages.objects.create(product=product, image=img_file)

        messages.success(request, "Product updated successfully.")
        return redirect("user_side:product_view", product_id=product.id)

    return render(request, 'store/edit_product.html', context)


from dateutil.relativedelta import relativedelta

@login_required
def my_orders(request):    
    filter_type = request.GET.get('filter_type')
    delivery_status = request.GET.get('status', 'pending')
    search_text = request.GET.get('search_text')

    
    orders = CustomerMerchandiseStoreProductBuy.objects.filter(
            product__created_by=request.user
        )

    if delivery_status == "delivered":
        orders = orders.filter(is_delivered=True, status__in=["DELIVERED"])

    elif delivery_status == "cancelled":  # Default and fallback
        orders = orders.filter(status__in=["CANCEL"])

    elif delivery_status == "shipped":
        orders = orders.filter(status__in=["SHIPPED"])
    else:
        orders = orders.filter(is_delivered=False, status__in=["ORDER PLACED"])

    now = datetime.now()            
    start = None

    if filter_type == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif filter_type == "last_3_days":
        start = now - timedelta(days=3)
    elif filter_type == "last_7_days":
        start = now - timedelta(days=7)
    elif filter_type == "last_15_days":
        start = now - timedelta(days=15)
    elif filter_type == "last_1_month":
        start = now - relativedelta(months=1)
    elif filter_type == "last_6_months":
        start = now - relativedelta(months=6)
    elif filter_type == "last_1_year":
        start = now - relativedelta(years=1)

    if start:
        orders = orders.filter(created_at__gte=start)
    
    # Precompute ratings for each order
    orders_with_ratings = []
    for order in orders:
        rating = order.product.ratedProduct.filter(user=order.created_by).first()
        first_image = order.product.productImages.first()
        orders_with_ratings.append({
            'order': order,
            'rating': rating,
            'image': first_image.image.url if first_image else None
        })

    page = request.GET.get("page", 1)   
    paginator = Paginator(orders_with_ratings, 20)

    try:
        order_page = paginator.page(page)
    except:
        order_page = paginator.page(1)
    return render(request, 'store/my_orders.html',
                   {'orders_with_ratings': order_page,                   
                    "search_text": search_text,
                    'status_choices': ['ORDER PLACED', 'SHIPPED', 'DELIVERED'], 
                    })


@login_required
def my_placed_orders(request):
    filter_type = request.GET.get('filter_type')
    delivery_status = request.GET.get('status', 'pending')
    search_text = request.GET.get('search_text')
   
    orders = CustomerMerchandiseStoreProductBuy.objects.filter(
        created_by=request.user
    )

    if delivery_status == "delivered":
        orders = orders.filter(is_delivered=True, status__in=["DELIVERED"])

    elif delivery_status == "cancelled":  # Default and fallback
        orders = orders.filter(status__in=["CANCEL"])

    else:
        orders = orders.filter(is_delivered=False, status__in=["ORDER PLACED", "SHIPPED"])

    now = datetime.now()            
    start = None

    if filter_type == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif filter_type == "last_3_days":
        start = now - timedelta(days=3)
    elif filter_type == "last_7_days":
        start = now - timedelta(days=7)
    elif filter_type == "last_15_days":
        start = now - timedelta(days=15)
    elif filter_type == "last_1_month":
        start = now - relativedelta(months=1)
    elif filter_type == "last_6_months":
        start = now - relativedelta(months=6)
    elif filter_type == "last_1_year":
        start = now - relativedelta(years=1)

    if start:
        orders = orders.filter(created_at__gte=start)

    grouped_cart = {}
    for item in orders:
        key = (item.product_id, item.color, item.size)
        if key in grouped_cart:
            grouped_cart[key]['quantity'] += item.quantity
            grouped_cart[key]['items'].append(item)  # Optional, if you want full record access
        else:
            grouped_cart[key] = {
                'product': item.product,
                'color': item.color,
                'size': item.size,
                'quantity': item.quantity,
                'image': MerchandiseProductImages.objects.filter(product=item.product).first(),
                'price':item.price_per_product,
                'total_price':item.total_price,
                'status':item.status,
                'delivery_address':item.delivery_address_main.complete_address,
                'rating_status':True if ProductRating.objects.filter(user=request.user, product=item.product).exists() else False,
                'items': [item],  # Optional: list of all matching entries
            }   
    page = request.GET.get("page", 1)   
    paginator = Paginator(list(grouped_cart.values()), 20)

    try:
        order_page = paginator.page(page)
    except:
        order_page = paginator.page(1)
    return render(request, 'store/my_placed_orders.html',
                   {'orders': order_page,
                    "search_text": search_text,
                    }) 


from django.views.decorators.http import require_POST

@require_POST
def change_order_status(request, order_id):
    order = get_object_or_404(CustomerMerchandiseStoreProductBuy, id=order_id)
    new_status = request.POST.get('status')
    if new_status in ['ORDER PLACED', 'SHIPPED', 'DELIVERED']:
        order.status = new_status
        if new_status == "DELIVERED":
            order.is_delivered = True
        order.save()
        messages.success(request, "Order status updated.")
    else:
        messages.error(request, "Invalid status selected.")
    return redirect(request.META.get('HTTP_REFERER', '/'))


@login_required
def add_to_wishlist(request):
    if request.method == "POST":
        product_id = request.POST.get("product_id")
        try:
            product = MerchandiseStoreProduct.objects.get(id=product_id)
            user = request.user
            if user in product.is_love.all():
                product.is_love.remove(user)
                return JsonResponse({"success": True, "message": "Removed from wishlist"})
            else:
                product.is_love.add(user)
                return JsonResponse({"success": True, "message": "Added to wishlist"})
        except MerchandiseStoreProduct.DoesNotExist:
            return JsonResponse({"success": False, "message": "Product not found"})

    return JsonResponse({"success": False, "message": "Invalid request"})


@require_POST
@login_required
def add_to_cart(request):
    product_id = request.POST.get("product_id")
    size = request.POST.get("size") or None
    color = request.POST.get("color") or None
    quantity = int(request.POST.get("quantity", 1))
    print(size, color, quantity)

    try:
        product = MerchandiseStoreProduct.objects.get(id=product_id)

        # Build dynamic filter
        spec_filter = {"product": product}
        if size:
            spec_filter["size"] = size
        if color:
            spec_filter["color"] = color

        spec = MerchandiseProductSpecification.objects.get(**spec_filter)

        if spec.available_product < quantity:
            return JsonResponse({"success": False, "message": "Not enough stock"})

        total_price = spec.current_price * quantity

        obj = GenerateKey()
        secret_key = obj.gen_buy_product_sk()
        CustomerMerchandiseStoreProductBuy.objects.create(
            secret_key=secret_key,
            product=product,
            size=size,
            color=color,
            quantity=quantity,
            price_per_product=spec.current_price,
            total_price=total_price,
            status="CART",
            created_by=request.user
        )

        return JsonResponse({"success": True, "message": "Added to cart"})
    
    except MerchandiseStoreProduct.DoesNotExist:
        return JsonResponse({"success": False, "message": "Product not found"})
    except MerchandiseProductSpecification.DoesNotExist:
        return JsonResponse({"success": False, "message": "Specification not found"})



@login_required
def buy_now(request):
    product_id = request.GET.get("product_id")
    size = request.GET.get("size")
    color = request.GET.get("color")

    # Normalize values: treat empty string or "undefined" as None
    if not size or size.lower() == "undefined":
        size = None
    if not color or color.lower() == "undefined":
        color = None
    quantity = int(request.GET.get("quantity", 1))
    print(size, color, quantity)

    try:
        product = MerchandiseStoreProduct.objects.get(id=product_id)

        # Build dynamic filter
        spec_filter = {"product": product}
        if size:
            spec_filter["size"] = size
        if color:
            spec_filter["color"] = color

        spec = MerchandiseProductSpecification.objects.get(**spec_filter)
        print(spec)

        if spec.available_product < quantity:
            return redirect("user_side:product_view", pk=product_id)

        total_price = spec.current_price * quantity

        obj = GenerateKey()
        secret_key = obj.gen_buy_product_sk()
        order = CustomerMerchandiseStoreProductBuy.objects.create(
            secret_key=secret_key,
            product=product,
            size=size,
            color=color,
            quantity=quantity,
            price_per_product=spec.current_price,
            total_price=total_price,
            status="BuyNow",
            created_by=request.user
        )

        # Redirect to address selection or payment page
        return redirect("user_side:checkout_summary_user_side", order_id=order.id)

    except MerchandiseStoreProduct.DoesNotExist:
        return redirect("user_side:product_list_user_side")
    except MerchandiseProductSpecification.DoesNotExist:
        return redirect("user_side:product_list_user_side")
    

@login_required
def checkout_summary(request, order_id):
    try:
        order = CustomerMerchandiseStoreProductBuy.objects.select_related('product').get(id=order_id, created_by=request.user)

        context = {
            'order': order,
            'product': order.product,
            'image': MerchandiseProductImages.objects.filter(product=order.product).first()
        }
        return render(request, 'store/checkout_summary.html', context)

    except CustomerMerchandiseStoreProductBuy.DoesNotExist:
        return redirect('user_side:product_list_user_side')


@login_required
def wishlist(request):
    context = {}
    search_text = request.GET.get("search_text")
    wishlisted_products = MerchandiseStoreProduct.objects.filter(is_love=request.user)
    if search_text:
        wishlisted_products = wishlisted_products.filter(Q(name__icontains=search_text) | Q(description__icontains=search_text) | Q(specifications__icontains=search_text) | Q(category__name__icontains=search_text) | Q(leagues_for__name__icontains=search_text)).distinct()
    
    # Step 4: Pagination
    page = request.GET.get("page", 1)
    paginator = Paginator(wishlisted_products, 20)
    try:
        product_page = paginator.page(page)
    except:
        product_page = paginator.page(1)
    serialized_products = ProductListSerializer(product_page, many=True, context={'request': request}).data
    context.update({
        "product_list": serialized_products,
        "search_text": search_text,
        "page_obj": product_page
    })
    return render(request, "store/wishlist.html", context)


from collections import defaultdict
from django.db.models import Sum

@login_required
def cart(request):
    context = {}

    # Fetch all cart items by the user
    cart_items = CustomerMerchandiseStoreProductBuy.objects.filter(created_by=request.user, status__in=["CART"])

    # Group items by (product, color, size)
    grouped_cart = {}
    for item in cart_items:
        key = (item.product_id, item.color, item.size)
        if key in grouped_cart:
            grouped_cart[key]['quantity'] += item.quantity
            grouped_cart[key]['items'].append(item)  # Optional, if you want full record access
        else:
            grouped_cart[key] = {
                'product': item.product,
                'color': item.color,
                'size': item.size,
                'quantity': item.quantity,
                'image': MerchandiseProductImages.objects.filter(product=item.product).first(),
                'price':item.price_per_product,
                'items': [item],  # Optional: list of all matching entries
            }

    # Convert grouped data to a list for the template
    context['cart_list'] = list(grouped_cart.values())
    return render(request, 'store/cart.html', context)


@login_required
@require_POST
def update_cart(request):
    for key, value in request.POST.items():
        if key.startswith("quantity_"):
            product_id = key.replace("quantity_", "")
            try:
                cart_item = CustomerMerchandiseStoreProductBuy.objects.get(id=product_id, created_by=request.user)
                cart_item.quantity = int(value)
                cart_item.save()
            except CustomerMerchandiseStoreProductBuy.DoesNotExist:
                continue
    return redirect('user_side:cart_user_side')




@csrf_exempt
@login_required
def remove_cart_item(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)

            product_id = data.get("product_id")
            size = data.get("size") or None
            color = data.get("color") or None

            # Ensure product exists
            product = MerchandiseStoreProduct.objects.get(id=product_id)
            spec_qs = MerchandiseProductSpecification.objects.filter(product=product)
            if size not in ["None", None, "null", ""]:
                spec_qs = spec_qs.filter(size__iexact=size)
            if color not in ["None", None, "null", ""]:
                spec_qs = spec_qs.filter(color__iexact=color)

            spec = spec_qs.first()

            # Remove from cart
            cart_product = CustomerMerchandiseStoreProductBuy.objects.filter(
                created_by=request.user,
                product_id=spec.product.id,
                status="CART"
            )
            if size not in ["None", None, "null", ""]:
                cart_product = cart_product.filter(size__iexact=size)
            if color not in ["None", None, "null", ""]:
                cart_product = cart_product.filter(color__iexact=color)
            cart_product.delete()

            return JsonResponse({"success": True})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    return JsonResponse({"success": False, "error": "Invalid request"})


@login_required
def apply_coupon(request):
    code = request.GET.get('code')
    cart_products = CustomerMerchandiseStoreProductBuy.objects.filter(created_by=request.user, status=["CART"])

    original_total_price = 0
    discount_amount = 0
    coupon_applied = False

    for product in cart_products:
        product_total = product.price_per_product * product.quantity
        original_total_price += product_total

        if code:
            coupon = CouponCode.objects.filter(
                coupon_code=code,
                product=product.product,
                start_date__lte=timezone.now(),
                end_date__gte=timezone.now()
            ).first()

            if coupon:
                discount = (coupon.percentage / 100) * product_total
                discount_amount += discount
                coupon_applied = True

    total_price = original_total_price - discount_amount

    if coupon_applied:
        return JsonResponse({
            'valid': True,
            'discount_amount': round(discount_amount, 2),
            'total_price': round(total_price, 2),
            'coupon_status': f"Coupon code '{code}' applied successfully."
        })
    else:
        return JsonResponse({
            'valid': False,
            'coupon_status': "Coupon code is not valid",
            'total_price': round(original_total_price, 2)
        })


@login_required
def select_address(request):
    user = request.user
    addresses = ProductDeliveryAddress.objects.filter(created_by=user)

    if request.method == 'POST':
        selected_address_id = request.POST.get('selected_address')
        if 'grand_total' in request.POST:
            
            request.session['cart_grand_total'] = request.POST.get('grand_total')
        # 👇 If selecting address to proceed to payment
        if selected_address_id:
            ProductDeliveryAddress.objects.filter(created_by=user).update(default_address=False)
            ProductDeliveryAddress.objects.filter(id=selected_address_id).update(default_address=True)
            return redirect('user_side:cart_payment_gateway_user_side')  # 👈 Redirects to the payment page

    return render(request, 'store/select_address.html', {
        'addresses': addresses,
        'grand_total': request.session.get('cart_grand_total', 0),
        "MAP_API_KEY":settings.MAP_API_KEY
    })

@login_required
def select_address_buy_now(request):
    user = request.user
    addresses = ProductDeliveryAddress.objects.filter(created_by=user)

    if request.method == 'POST':
        selected_address_id = request.POST.get('selected_address')
        if 'order_id' in request.POST:
            
            request.session['order_id'] = request.POST.get('order_id')
        # 👇 If selecting address to proceed to payment
        if selected_address_id:
            ProductDeliveryAddress.objects.filter(created_by=user).update(default_address=False)
            ProductDeliveryAddress.objects.filter(id=selected_address_id).update(default_address=True)
            return redirect('user_side:buy_now_payment_gateway_user_side')  # 👈 Redirects to the payment page

    return render(request, 'store/select_address_buy_now.html', {
        'addresses': addresses,
        'order_id': request.session.get('order_id', 0),
        "MAP_API_KEY":settings.MAP_API_KEY
    })

@login_required
def add_address_ajax(request):
    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        street = request.POST.get('street')
        city = request.POST.get('city')
        state = request.POST.get('state')
        postal_code = request.POST.get('postal_code')
        country = request.POST.get('country')

        # Mark all existing as non-default
        ProductDeliveryAddress.objects.filter(created_by=request.user).update(default_address=False)

        obj = GenerateKey()
        delivery_address_key = obj.gen_delivery_address_sk()
        ProductDeliveryAddress.objects.create(
            secret_key=delivery_address_key,
            created_by=request.user,
            street=street,
            city=city,
            state=state,
            postal_code=postal_code,
            country=country,
            default_address=True
        )

        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'message': 'Invalid request'})


@login_required
def cart_payment_gateway(request):
    total_amount = request.session.get('cart_grand_total', 0)
    return render(request, 'store/cart_payment_gateway.html', {
        'total_amount': total_amount,
        'STRIPE_PUBLISHABLE_KEY': settings.STRIPE_PUBLIC_KEY
    })


@csrf_exempt
@login_required
def create_cart_checkout_session(request):
    """ Creates Stripe Checkout session for cart payment """
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            total_amount = float(data.get("total_amount"))
            user = request.user

            stripe.api_key = settings.STRIPE_SECRET_KEY
            amount_in_paise = int(total_amount * 100)
            domain = request.build_absolute_uri('/').rstrip('/')

            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[{
                    "price_data": {
                        "currency": "usd",
                        "product_data": {"name": "Cart Payment"},
                        "unit_amount": amount_in_paise,
                    },
                    "quantity": 1,
                }],
                mode="payment",
                success_url = f"{domain}/user_side/cart_payment_success/?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url = f"{domain}/user_side/cart_payment_cancel/"
            )

            # Save pending transaction
            AllPaymentsTable.objects.create(
                user=user,
                amount=total_amount,
                checkout_session_id=session.id,
                status="Pending",
                payment_for=f"Buying cart products by {user.first_name} {user.last_name}."
            )

            return JsonResponse({"id": session.id})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)

    # 👇 this will handle non-POST methods
    return JsonResponse({"error": "Invalid request method."}, status=405)


@csrf_exempt
def stripe_cart_webhook(request):
    """ Webhook to confirm payment from Stripe """
    payload = request.body

    sig_header = request.headers.get("Stripe-Signature")
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
        # print(event)
    except (ValueError, stripe.error.SignatureVerificationError):
        return HttpResponse(status=400)

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        session_id = session.get("id")
        amount = session.get("amount_total", 0) / 100
        user=request.user
        payment = AllPaymentsTable.objects.filter(checkout_session_id=session_id).first()
        if payment:
            payment.status = "Completed"
            payment.payment_mode = "Card"
            payment.json_response = session
            payment.save()

            carted_products = CustomerMerchandiseStoreProductBuy.objects.filter(created_by=user, status__in=["CART"])
            carted_products.update(status="ORDER PLACED")           

    return HttpResponse(status=200)


@login_required
def cart_payment_success(request):
    session_id = request.GET.get("session_id")
    if not session_id:
        return render(request, "store/payment_cancel.html", {"error": "Invalid session."})

    stripe.api_key = settings.STRIPE_SECRET_KEY
    try:
        session = stripe.checkout.Session.retrieve(session_id)

        if session.payment_status == "paid":
            amount = session.amount_total / 100
            user=request.user
            payment = AllPaymentsTable.objects.filter(checkout_session_id=session_id).first()
            if payment:
                payment.status = "Completed"
                payment.payment_mode = "Card"
                payment.json_response = session
                payment.save()

                carted_products = CustomerMerchandiseStoreProductBuy.objects.filter(created_by=user, status__in=["CART"])
                default_delivery_address = ProductDeliveryAddress.objects.filter(created_by=request.user, default_address=True).first()
                carted_products.update(status="ORDER PLACED", is_paid=True, delivery_address_main=default_delivery_address)
            return render(request, "store/payment_success.html", {"amount": amount})
        else:
            return render(request, "store/payment_cancel.html", {"error": "Payment not completed."})
    except stripe.error.StripeError as e:
        return render(request, "store/payment_cancel.html", {"error": str(e)})


@login_required
def cart_payment_cancel(request):
    return render(request, "store/payment_cancel.html", {"error": "Payment was cancelled."})


@login_required
def buy_now_payment_gateway(request):
    order_id = request.session.get('order_id', 0)
    order = CustomerMerchandiseStoreProductBuy.objects.filter(id=int(order_id)).first()
    total_amount = order.total_price
    # print(order_id)
    return render(request, 'store/buy_now_payment_gateway.html', {
        'total_amount': total_amount,
        'order_id': order.id,
        'STRIPE_PUBLISHABLE_KEY': settings.STRIPE_PUBLIC_KEY
    })


@csrf_exempt
@login_required
def create_buy_now_checkout_session(request):
    if request.method == "POST":
        try:
            stripe.api_key = settings.STRIPE_SECRET_KEY
            user = request.user

            data = json.loads(request.body)
            order_id = data.get("order_id")
            order = CustomerMerchandiseStoreProductBuy.objects.filter(id=int(order_id)).first()
            total_price = float(order.total_price)

            amount_in_paise = int(total_price * 100)
            domain = request.build_absolute_uri('/').rstrip('/')
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[{
                    "price_data": {
                        "currency": "usd",
                        "product_data": {
                            "name": f"Buy Now - Product ID: {order.product.id}"
                        },
                        "unit_amount": int(amount_in_paise / order.quantity),
                    },
                    "quantity": order.quantity,
                }],
                mode="payment",
                success_url=f"{domain}/user_side/buy_now_payment_success/?session_id={{CHECKOUT_SESSION_ID}}&order_id={order.id}",
                cancel_url=f"{domain}/user_side/buy_now_payment_cancel/"
            )

            # Save pending payment
            AllPaymentsTable.objects.create(
                user=user,
                amount=total_price,
                checkout_session_id=session.id,
                status="Pending",
                payment_for= f"Buying product {order.product.name} by {user.first_name} {user.last_name}"
            )

            return JsonResponse({"id": session.id})

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)

    return JsonResponse({"error": "Invalid request method."}, status=405)


@login_required
def buy_now_payment_success(request):
    session_id = request.GET.get("session_id")
    order_id = request.GET.get("order_id")

    if not session_id or not order_id:
        return render(request, "store/payment_cancel.html", {"error": "Missing session or order ID."})

    stripe.api_key = settings.STRIPE_SECRET_KEY
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        if session.payment_status == "paid":
            amount = session.amount_total / 100
            user = request.user

            payment = AllPaymentsTable.objects.filter(checkout_session_id=session_id).first()
            if payment:
                payment.status = "Completed"
                payment.payment_mode = "Card"
                payment.json_response = session
                payment.save()

                order = CustomerMerchandiseStoreProductBuy.objects.filter(id=int(order_id)).first()
                default_delivery_address = ProductDeliveryAddress.objects.filter(created_by=request.user, default_address=True).first()
                if order:
                    order.status = "ORDER PLACED"
                    order.is_paid = True
                    order.delivery_address_main = default_delivery_address
                    order.save()

            return render(request, "store/payment_success.html", {"amount": amount})

        else:
            return render(request, "store/payment_cancel.html", {"error": "Payment not completed."})

    except stripe.error.StripeError as e:
        return render(request, "store/payment_cancel.html", {"error": str(e)})


@login_required
def buy_now_payment_cancel(request):
    return render(request, "store/payment_cancel.html", {"error": "Payment was cancelled."})


@login_required
def add_review(request):
    if request.method == "POST":
        product_id = request.POST.get("product_id")
        rating = request.POST.get("rating")
        comment = request.POST.get("review")  # textarea name from modal
        images = request.FILES.getlist("images")

        # Validation
        if not product_id or not rating:
            return JsonResponse({"success": False, "message": "Product ID and rating are required."})

        try:
            rating = int(rating)
            if rating < 1 or rating > 5:
                return JsonResponse({"success": False, "message": "Rating must be between 1 and 5."})
        except ValueError:
            return JsonResponse({"success": False, "message": "Invalid rating value."})

        try:
            product = MerchandiseStoreProduct.objects.get(id=product_id)
        except MerchandiseStoreProduct.DoesNotExist:
            return JsonResponse({"success": False, "message": "Product not found."})

        try:
            with transaction.atomic():
                # Create or update existing review (unique_together constraint)
                product_rating, created = ProductRating.objects.update_or_create(
                    user=request.user,
                    product=product,
                    defaults={
                        "rating": rating,
                        "comment": comment
                    }
                )

                # Clear old images if updating
                if not created:
                    product_rating.ratingImages.all().delete()

                # Save uploaded images
                for img in images:
                    RatingImages.objects.create(product_rating=product_rating, image=img)

            messages.success(request, "Review submitted successfully!")
            return redirect(request.META.get("HTTP_REFERER", "user_side:my_placed_orders_user_side"))
    

        except Exception as e:
            messages.error(request, "Invalid request.")
            return redirect("user_side:my_placed_orders_user_side")
        
    messages.error(request, "Invalid request.")
    return redirect("user_side:my_placed_orders_user_side")


@login_required
def accept_openplay_invitation(request, pk):
    invitation = get_object_or_404(OpenPlayInvitation, id=pk)

    if request.method == "POST":
        invitation.status = "Accepted"
        invitation.save()
        return redirect('user_side:user_index')

    return redirect('user_side:user_index')
    


@login_required
def decline_openplay_invitation(request, pk):
    invitation = get_object_or_404(OpenPlayInvitation, id=pk)

    if request.method == "POST":
        invitation.status = "Declined"
        invitation.save()
        return redirect('user_side:user_index')

    return redirect('user_side:user_index')


from django.views.decorators.csrf import csrf_exempt
from apps.user.subcription_view import user_subscription_data
def app_to_subscription_page(request, user_uuid):
    user = get_object_or_404(User, uuid=user_uuid)
    auth_login(request, user)
    return redirect("user_side:subcription_plan")

@login_required(login_url="/user_side/")
@csrf_exempt
def subcription_plan(request):
    plan = user_subscription_data(request.user.uuid, 'google')
    STRIPE_PUBLISHABLE_KEY = settings.STRIPE_PUBLIC_KEY
    return render(request, "sides/subcription_plan.html", {"plans": plan, "STRIPE_PUBLISHABLE_KEY": STRIPE_PUBLISHABLE_KEY})




#adveticement
@login_required
def get_advertisements(request):
    # All approved ad IDs
    all_ad_ids = list(Advertisement.objects.filter(
        approved_by_admin=True,
        admin_approve_status='Approved'
    ).values_list('id', flat=True))

    if not all_ad_ids:
        return JsonResponse({}, safe=False)

    # Get session data or initialize
    first_selected_id = request.session.get('first_selected_id')
    served_ads = request.session.get('served_ads', [])

    # Step 1: Pick and serve the first random ad
    if not first_selected_id:
        selected_id = random.choice(all_ad_ids)
        request.session['first_selected_id'] = selected_id
        served_ads.append(selected_id)
        request.session['served_ads'] = served_ads
    else:
        # Step 2: Serve remaining ads except already served
        remaining_ads = [ad_id for ad_id in all_ad_ids if ad_id not in served_ads]
        if not remaining_ads:
            # All served — reset session
            request.session['first_selected_id'] = None
            request.session['served_ads'] = []
            return JsonResponse({}, safe=False)
        selected_id = random.choice(remaining_ads)
        served_ads.append(selected_id)
        request.session['served_ads'] = served_ads

    # Get the ad
    get_ad = get_object_or_404(Advertisement, id=selected_id)
    data = {
        "url": get_ad.url,
        "company_name": get_ad.company_name,
        "script_text": get_ad.script_text,
        "image_url": get_ad.image.url if get_ad.image else None,
    }

    return JsonResponse(data, safe=False)


#### unauthenticated user side views
def unauthenticated_base_view(request, pk):
    if request.user.is_authenticated:
        post = get_object_or_404(socialFeed, id=pk, block=False)
        comments = post.post_comment.all().order_by('-created_at')
        return render(request, 'sides/view_post.html', {'post': post, 'comments': comments})
    return render(request, 'share/share_home.html', {'pk': pk })

def unauthenticated_feed_view(request, pk):
    post = get_object_or_404(socialFeed, id=pk, block=False)
    comments = post.post_comment.all().order_by('-created_at')
    if request.user.is_authenticated:
        return render(request, 'sides/view_post.html', {'post': post, 'comments': comments})
    return render(request, 'share/feed_share.html', {'post': post, 'comments': comments, 'pk': pk})






