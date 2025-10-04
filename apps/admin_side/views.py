from django.shortcuts import render, get_object_or_404, redirect, reverse
from apps.user.models import *
from apps.user.helpers import *
from apps.team.models import *
from apps.user.models import *
from apps.pickleitcollection.models import *
from apps.store.models import *
from django.http import Http404, HttpResponse
import json
import stripe
from django.contrib.auth.hashers import make_password
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login as auth_login
from django.contrib.auth import logout
from apps.team.views import notify_edited_player, check_add_player
from django.contrib.admin.models import LogEntry
from django.contrib.contenttypes.models import ContentType
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
from apps.chat.views import notify_all_users
from apps.socialfeed.models import *
from apps.courts.models import *
from apps.clubs.models import *
protocol = settings.PROTOCALL
import math
from django.contrib.auth import update_session_auth_hash
from django.db.models import Q
from django.conf import settings
import requests
from django.http import HttpResponseRedirect
from functools import wraps
from decimal import Decimal, ROUND_DOWN

def check_data_structure(data_structure):
    for item in data_structure:
        if item["number_of_courts"] != 0 or item["sets"] != 0 or item["point"] != 0:
            return False
    return True

def superuser_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_superuser:
            return HttpResponseRedirect(reverse("dashboard:user_login"))  # Or your login URL
        return view_func(request, *args, **kwargs)
    return wrapper

# Create your views here.
@superuser_required
def index(request):
    total_team = Team.objects.all().count()
    total_player = Player.objects.all().count()
    total_tournament = Leagues.objects.all().count()
    log_entries = LogEntry.objects.select_related("user", "content_type").all().order_by("-action_time")[:20]
    wallet_balance = Wallet.objects.filter(user=request.user).first().balance
    

    # Step 2: Count subscribers per plan name (Apple + Google combined)
    plan_summary = (
        SubscriptionPlan.objects
        .values('name')
        .annotate(total_subscribers=Count('subscription'))
    )
   

    plan_counts = {item['name']: item['total_subscribers'] for item in plan_summary}
    print("Plan Counts:", plan_counts)

    # Count users with no subscription (free users)
    users_with_subscriptions = Subscription.objects.values_list('user_id', flat=True).distinct()
    free_users_count = User.objects.exclude(id__in=users_with_subscriptions).count()
    print("Free Users Count:", free_users_count)

    # Prepare final summary with all plans
    final_summary = []
    for name in ['Free Version', 'Paid Version', 'Pro Version', 'Enterprise Version']:  # List of your plans
        count = plan_counts.get(name, 0)  # Default to 0 if no plan is found

        if name == 'Free Version':
            count += free_users_count  # Add free users to the "Free" plan

        final_summary.append({'name': name, 'total_subscribers': count})
        print(f"Plan {name}: {count} subscribers")
    print(final_summary)
    entries = [
        {
            "model_name": log.content_type.model if log.content_type else "N/A",
            "action": log.get_action_flag_display(),
            "instance_id": log.object_id,
            "user": log.user.username,
            "timestamp": log.action_time,
        }
        for log in log_entries
    ]
    return render(request, 'dashboard/index.html',{
         'total_team_count': total_team,
         'total_player_count': total_player,
         'total_tournament_count': total_tournament,
         'entries':entries,
         'balance': wallet_balance,
         'plans':final_summary
         })


def login(request):
    context = {}
    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(username=username, password=password)
        if user is not None:
            if user.is_superuser:
                auth_login(request, user) 
                return index(request)
            else:
                context['message'] = "You are not authorized to access this page."
                return render(request, "dashboard/login.html", context)
        else:
            context['message'] = "Invalid username or password."
            return render(request, "dashboard/login.html", context)

    return render(request, "dashboard/login.html", context)


def logout_view(request):
    logout(request)
    return redirect(reverse('dashboard:user_login'))

# --- Helper functions ---

def get_lat_long(api_key, address):
    try:
        url = f"https://maps.googleapis.com/maps/api/geocode/json?address={address}&key={api_key}"
        response = requests.get(url)
        results = response.json().get('results')
        if results:
            location = results[0]['geometry']['location']
            return location['lat'], location['lng']
    except Exception as e:
        print(f"Error fetching lat/long for '{address}':", e)
    return None, None


def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Radius of Earth in km
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    lat1 = math.radians(lat1)
    lat2 = math.radians(lat2)

    a = math.sin(d_lat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(d_lon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def get_custom_pagination_range(page, paginator):
    """
    Generate pagination range: "1 2 ... 10 11 12 ... 23 24 25"
    """
    current_page = page.number
    total_pages = paginator.num_pages
    delta = 2  # Adjust number of visible pages before and after the current page

    if total_pages <= 7:
        return range(1, total_pages + 1)

    pages = []
    if current_page > delta + 2:
        pages.extend([1, 2, "..."])

    start = max(1, current_page - delta)
    end = min(total_pages, current_page + delta)

    pages.extend(range(start, end + 1))

    if current_page < total_pages - delta - 1:
        pages.extend(["...", total_pages - 1, total_pages])

    return pages

## Helper functions end

#### player section / now known as a user

@superuser_required
def player_list_(request):
    search_text = request.GET.get("search_text", None)
    location = request.GET.get("location", None)
    select_plan = request.GET.get("select_plan", None)
    page_length = request.GET.get("page_length", 60)

    user_q = []
    if not search_text:
        user_q = User.objects.all().order_by('-id')
    if search_text:
       user_q = User.objects.filter(Q(first_name__icontains=search_text) |Q(last_name__icontains=search_text) |Q(username__icontains=search_text) |Q(email__icontains=search_text) |Q(rank__icontains=search_text) |Q(gender__icontains=search_text)).order_by('-id')
    if select_plan:
        if select_plan != "Free Version":
            # print(select_plan)
            user_ids = list(Subscription.objects.filter(plan__name=select_plan).values_list("user_id", flat=True))
            # print(user_ids)
            user_q = user_q.filter(id__in=user_ids)
        else:
            user_ids = list(Subscription.objects.exclude(plan__name__in=['Paid Version', 'Pro Version', 'Enterprise Version']).values_list("user_id", flat=True))
            user_q = user_q.exclude(id__in=user_ids)
        
    if not select_plan and not search_text:
        user_q= User.objects.all().order_by('-id')
    users = user_q.values(
        "id", "first_name", "last_name", "username", "phone",
        "image", "rank", "gender", "email", "created_at", 'latitude', 'longitude'
    )
        
    if location:
        ref_lat, ref_lon = get_lat_long(settings.MAP_API_KEY, location)
        if ref_lat is not None and ref_lon is not None:
            filtered_users = []
            for user in users:
                if user['latitude'] not in ['0', 0, None, "", "null"] and user["longitude"] not in ['0', 0, None, "", "null"]:
                    user_lat, user_long = float(user["latitude"]), float(user["longitude"])
                    if user_lat is not None and user_long is not None:
                        distance = haversine(ref_lat, ref_lon, user_lat, user_long)
                        if distance <= 100:  # radius in KM
                            filtered_users.append(user)
            users = filtered_users
        else:
            users = [] 

    today_date = date.today()
    for user in users:
        image_path = user.get("image")
        if image_path and image_path.lower() != 'null':
            if image_path.startswith("/"):
                user["image_url"] = request.build_absolute_uri(image_path)
            else:
                user["image_url"] = request.build_absolute_uri(settings.MEDIA_URL + image_path)
        else:
            user["image_url"] = None
        user_wallet = Wallet.objects.filter(user_id=user["id"])
        if user_wallet:
            get_user_wallet = user_wallet.first()
            user["balance"] = get_user_wallet.balance
        else:
            user["balance"] = 0.0
        membership_plan = Subscription.objects.filter(user_id=user["id"], end_date__gte=today_date)
        if membership_plan:
            membership_plan_concatinate = ""
            for splan in membership_plan:
                membership_plan_concatinate += splan.plan.name + " || "

            # Remove the last " || " to avoid trailing delimiters
            membership_plan_concatinate = membership_plan_concatinate.rstrip(" || ")
            user["plan"] = membership_plan_concatinate
        else:
            user["plan"] = "Free"
    # Pagination setup
    page = request.GET.get("page", 1)
    paginator = Paginator(users, page_length)  # 10 players per page

    try:
        players_page = paginator.page(page)
    except:
        players_page = paginator.page(1)

    context = {
        "player_list": players_page,
        "page_range": get_custom_pagination_range(players_page, paginator),
        "search_text": search_text,
        "select_plan": select_plan,
        "page_length": str(page_length),
        "location":location
    }
    return render(request, "dashboard/side/player_list.html", context)


@superuser_required
def create_player_(request):
    context = {"message":""}
    rank_values = [i/4 for i in range(4,21)]
    context["rank_values"] = rank_values
    if request.method == 'POST':
        admin_user = User.objects.get(id=request.user.id)
        p_first_name = request.POST.get('player_first_name')
        p_last_name = request.POST.get('player_last_name')
        p_email = request.POST.get('player_email')
        p_phone_no = request.POST.get('player_phone_number')        
        p_gender = request.POST.get('player_gender')
        p_rank = request.POST.get('player_ranking')   
        p_image = request.FILES.get('player_image') 
        if not p_rank or p_rank == 0:              
            p_rank = 1
        if not p_email:
            context["message"] = "Player email is required."
            return render(request, "dashboard/side/create_player_form.html", context)
        check_player = User.objects.filter(email=p_email)
        if not check_player.exists():
            obj = GenerateKey()
            secret_key = obj.gen_player_key()
            player_full_name = f"{p_first_name} {p_last_name}"
            identify_player = f"{str(p_first_name)[0]} {str(p_last_name)[0]}"
            role = Role.objects.filter(role="User")
            if not role.exists():               
                # return HttpResponse("Role does not exist.")
                context["message"] = "Role does not exist."
                return render(request, "dashboard/side/create_player_form.html", context)
            six_digit_number = str(random.randint(100000, 999999))
            user_secret_key = obj.gen_user_key()
            user = User.objects.create(
                secret_key=user_secret_key,
                phone=p_phone_no,
                first_name=p_first_name,
                last_name=p_last_name,
                username=p_email,
                email=p_email,
                password=make_password(six_digit_number),
                password_raw=six_digit_number,
                is_player=True,
                is_verified=True,
                rank=p_rank,
                gender=p_gender,
                role_id=role.first().id
            ) 
            if p_image:
                user.image = p_image
            user.save()
            player = Player.objects.create(
                secret_key=secret_key,
                player_first_name=p_first_name,
                player_last_name=p_last_name,
                player_full_name=player_full_name,
                player_email=p_email,
                player=user,
                player_phone_number=p_phone_no,
                player_ranking=p_rank,
                identify_player=identify_player,
                created_by=admin_user,
            ) 
            if p_image: 
                player.player_image = p_image 
            app_name = "PICKLEit"
            login_link = "#"
            password = six_digit_number
            send_email_this_user = send_email_for_invite_player(p_first_name, p_email, app_name, login_link, password)         

            return redirect(reverse('dashboard:player_list_'))
        else:
            # return HttpResponse("Player already exist.")
            context["message"] = "Player already exists."
            return render(request, "dashboard/side/create_player_form.html", context)
    return render(request, "dashboard/side/create_player_form.html", context)


@superuser_required
def player_view(request, user_id):
    context = {"message":""}
    user = get_object_or_404(User, id=user_id)

    Wallet_details = Wallet.objects.filter(user=user)
    if Wallet_details:
        Get_Wallet_details = Wallet_details.first()
    transaction = WalletTransaction.objects.filter(Q(sender=user) | Q(reciver=user)).order_by('-id')
    all_buy_plan = Subscription.objects.filter(user=user).order_by('-id')[:3]
    created_teams = Team.objects.filter(created_by=user)
    player = Player.objects.filter(player=user).prefetch_related('team').first()
    joined_teams = Team.objects.filter(player__player=user).distinct()
    teams = list(set(list(created_teams) + list(joined_teams)))
    all_team_data = []
    
    for team in teams:
        players_in_team = list(Player.objects.filter(team=team).values("player_full_name", "player__image"))
        dat = {
            "name":team.name,
            "image":team.team_image,
            "players":players_in_team,
            "created_by":team.created_by
               }
        all_team_data.append(dat)
    

    # Match history queryset
    match_history_qs = Tournament.objects.filter(
        Q(team1__in=teams) | Q(team2__in=teams)
    ).distinct()

    for match_ in match_history_qs:
        match_.opponent = match_.team2 if match_.team1 in teams else match_.team1
        match_.scores = TournamentSetsResult.objects.filter(tournament=match_)

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

    context["total_posts"] = total_posts
    context['followers'] = followers
    context["followings"] = followings
    context["user"] = user
    context["wallet_details"] = Get_Wallet_details
    context["transaction"] = transaction
    context["all_team_data"] = all_team_data
    context["all_match_history"] = match_history_page
    context["all_buy_plan"] = all_buy_plan
    context["social_feed_list"] = social_feed_page
    return render(request, "dashboard/side/player_view.html", context)


@superuser_required
def edit_player(request, user_id):
    context = {'message':''}
    user = get_object_or_404(User, id=user_id)
    rank_values = [i/4 for i in range(4,21)]
    context["rank_values"] = rank_values
    if request.method == 'POST':
        
        p_first_name = request.POST.get('player_first_name')
        p_last_name = request.POST.get('player_last_name')
        p_phone_no = request.POST.get('player_phone_number')
        
        p_gender = request.POST.get('player_gender')
        p_rank = request.POST.get('player_ranking')
        if not p_rank or p_rank == 0:              
            p_rank = 1
        if "player_image" in request.FILES:
            user.image = request.FILES.get('player_image')    

        if request.POST.get('remove_player_image') == 'true':
            if user.image:
                user.image.delete()    

        user.first_name  = p_first_name
        user.last_name = p_last_name
        user.phone= p_phone_no
        user.rank = p_rank 
        user.gender = p_gender        
        user.save()        
        player = Player.objects.filter(player_email=user.email)
        
        if player.exists():         
            player.update(player_first_name=p_first_name, player_last_name=p_last_name, player_phone_number=p_phone_no, player_ranking=p_rank)
            
            if "player_image" in request.FILES:                
                player.update(player_image=request.FILES.get("player_image")) 

        if request.user.id == user.id:
            update_session_auth_hash(request, user)
        return redirect(reverse('dashboard:player_list_'))
    else:
        context = {"player": user}
        return render(request, "dashboard/side/edit_player.html", context)


@superuser_required
def delete_player(request, user_id):
    context = {"message":""}
    user = get_object_or_404(User, id=user_id)
    user_email = user.email
    context["player"] = user
    if request.method == 'POST':
        player = Player.objects.filter(player_email=user_email)
        if player.exists():
            all_teams = player.first().team.all()
            if not all_teams:
                player.first().delete()                
                user.delete()
            else:
                for team in all_teams:
                    team_id = team.id
                    check_team_have_any_tournament = Leagues.objects.filter(registered_team__in=[team_id], is_complete=False)
                    if not check_team_have_any_tournament.exists():
                        player.first().delete()                        
                        user.delete()
                    else:
                        context["message"] = "User can not be deleted as he/she is in registered teams for tournament." 
                        return render(request, 'dashboard/side/player_delete_confirm.html', context) 
        else:
            user.delete()  
        return redirect(reverse('dashboard:player_list_'))
    return render(request, 'dashboard/side/player_delete_confirm.html', {'player': user})

### player section end


### subscribed user list 

def subscription_plan_users(request, plan_name):
    search_text = request.GET.get("search_text", None)    
    page_length = request.GET.get("page_length", 20)

    plan_names = ['Free Version', 'Paid Version', 'Pro Version', 'Enterprise Version']
    if plan_name not in plan_names:
        return render(request, '404.html', status=404)

    subscriptions = Subscription.objects.select_related('user', 'plan')

    users_data = []

    if plan_name == 'Free Version':
        # Users without subscription
        users_with_subs = subscriptions.values_list('user_id', flat=True).distinct()
        users = User.objects.exclude(id__in=users_with_subs)

        for user in users:
            users_data.append({
                'user': user,
                'end_date': None  # No subscription → no expiry date
            })
    else:
        subs = subscriptions.filter(plan__name=plan_name)
        for sub in subs:
            users_data.append({
                'user': sub.user,
                'end_date': sub.end_date
            })
    print(user["user"] for user in users_data)
    if search_text:
        
        users_data = [user for user in users_data if 
                  (user['user'].first_name and search_text.lower() in user['user'].first_name.lower()) or
                  (user['user'].last_name and search_text.lower() in user['user'].last_name.lower()) or
                  (user['user'].username and search_text.lower() in user['user'].username.lower()) or
                  (user['user'].email and search_text.lower() in user['user'].email.lower())]
    # Pagination setup
    page = request.GET.get("page", 1)
    paginator = Paginator(users_data, page_length)  # 10 players per page

    try:
        players_page = paginator.page(page)
    except:
        players_page = paginator.page(1)
    context = {
        'plan_name': plan_name,
        'users_data': players_page,
        "page_range": get_custom_pagination_range(players_page, paginator),
        "search_text": search_text,
        "page_length": str(page_length)
    }
    return render(request, 'dashboard/side/subscription_plan_users.html', context)

### subscribed user list ends

#### team section 

# @superuser_required
# def team_list_for_admin(request):
#     context = {"table_data":[], "message":""}
#     try:
#         search_text = request.GET.get("search_text", None)        
#         page_length = request.GET.get("page_length", 10)
#         location = request.GET.get('location')
#         if search_text:
#             teams = Team.objects.filter(is_disabled=False).filter(Q(name__icontains=search_text) | Q(team_type__icontains=search_text) | Q(team_person__icontains=search_text) | Q(location__icontains=search_text)).order_by('-id')
#         else:
#             teams = Team.objects.filter(is_disabled=False).order_by('-id')

#         if location:
#             ref_lat, ref_lon = get_lat_long(settings.MAP_API_KEY, location)
#             radius_km = 100  # adjust as needed
#             filtered_teams = []

#             for team in teams:
#                 if team.location:
#                     team_lat, team_lon = get_lat_long(settings.MAP_API_KEY, team.location)
#                     if team_lat is not None and team_lon is not None:
#                         distance = haversine(ref_lat, ref_lon, team_lat, team_lon)
#                         if distance <= radius_km:
#                             filtered_teams.append(team)
#             teams = filtered_teams

#         team_data = list(teams.values("id", "name", "team_person", "team_image", "team_type", "created_by__first_name", "created_by__last_name"))
#         team_rank = 0
#         for team in team_data:                 
#             players = Player.objects.filter(team__id=team["id"])
#             team_rank = 0
#             for player in players:
#                 if player.player.rank == "0" or player.player.rank in [0,"", "null", None]:
#                     # player.player_ranking = 1.0
#                     team_rank += 1
#                 else:
#                     team_rank += float(player.player.rank)

#             team_rank = team_rank / len(players) if players else 0     
#             team["players"] = list(players.values("id", "player_full_name", "player__rank", "player__image", "player__gender"))
#             team["team_rank"] = team_rank  

#         # Pagination setup
#         page = request.GET.get("page", 1)
#         paginator = Paginator(team_data, page_length)  # 10 players per page

#         try:
#             team_page = paginator.page(page)
#         except:
#             team_page = paginator.page(1)  
            
#         context = {
#             "table_data": team_page,
#             "page_range": get_custom_pagination_range(team_page, paginator),
#             "search_text": search_text,            
#             "page_length": page_length
#         }
#         return render(request, "dashboard/side/team_list.html", context)
#     except:
#         context["message"] = "Something is Wrong"
#         return render(request, "dashboard/side/team_list.html", context)


@superuser_required
def team_list_for_admin(request):
    context = {"table_data": [], "message": ""}
    
    try:
        search_text = request.GET.get("search_text")
        page_length = int(request.GET.get("page_length", 60))
        location = request.GET.get("location")

        team_type = request.GET.get('team_type')
        team_person = request.GET.get('team_person')

        # Step 1: Filter base teams
        teams = Team.objects.filter(is_disabled=False)
        if search_text:
            teams = teams.filter(
                Q(name__icontains=search_text) |
                Q(team_type__icontains=search_text) |
                Q(team_person__icontains=search_text) 
            )
        teams = teams.order_by("-id")
        if team_person and team_person != 'all':
            teams = teams.filter(team_person__iexact=team_person)

        # Filter by team_type
        if team_type and team_type != 'all':
            teams = teams.filter(team_type__iexact=team_type)

        # Step 2: Filter by proximity if location is provided
        if location:
            ref_lat, ref_lon = get_lat_long(settings.MAP_API_KEY, location)
            if ref_lat is not None and ref_lon is not None:
                filtered_teams = []
                for team in teams:
                    if team.location:
                        team_lat, team_lon = get_lat_long(settings.MAP_API_KEY, team.location)
                        if team_lat is not None and team_lon is not None:
                            distance = haversine(ref_lat, ref_lon, team_lat, team_lon)
                            if distance <= 100:  # radius in KM
                                filtered_teams.append(team)
                teams = filtered_teams
            else:
                teams = []  # If location lookup failed, return no results

        # Step 3: Build team data with rank and players
        team_data = []
        for team in teams:
            players = Player.objects.filter(team__id=team.id)
            team_rank = 0

            for player in players:
                rank_val = player.player.rank
                
                try:
                    rank = float(rank_val) if rank_val not in ["", "0", 0, None, "null"] else 1.0
                except:
                    rank = 1.0
                team_rank += rank                

            team_rank = team_rank / len(players) if players else 0           

            team_data.append({
                "id": team.id,
                "name": team.name,
                "team_person": team.team_person,
                "team_image": team.team_image.url if team.team_image else "",
                "team_type": team.team_type,
                "created_by__first_name": team.created_by.first_name if team.created_by else "",
                "created_by__last_name": team.created_by.last_name if team.created_by else "",
                "players": list(players.values("id", "player_full_name", "player__rank", "player__image", "player__gender")),
                "team_rank": team_rank
            })

        # Step 4: Pagination
        page = request.GET.get("page", 1)
        paginator = Paginator(team_data, page_length)
        try:
            team_page = paginator.page(page)
        except:
            team_page = paginator.page(1)

        context.update({
            "table_data": team_page,
            "page_range": get_custom_pagination_range(team_page, paginator),
            "search_text": search_text,
            "page_length": str(page_length),
            "location": location,
            'team_person':team_person,
            'team_type':team_type
        })
        return render(request, "dashboard/side/team_list.html", context)

    except Exception as e:
        print("Error in team_list_for_admin:", e)
        context["message"] = "Something went wrong."
        return render(request, "dashboard/side/team_list.html", context)


def get_players_by_team_type(request):
    team_type = request.GET.get('team_type')

    # Filter players based on team type
    if team_type == "Men":
        players = Player.objects.filter(player__gender='Male')
    elif team_type == "Women":
        players = Player.objects.filter(player__gender='Female')
    elif team_type == "Co-ed":
        players = Player.objects.all()
    else:
        players = Player.objects.none()

    # Return player data in JSON
    data = {
        'players': [
            {
                'id': p.id,
                'name': p.player_full_name,
                'gender': p.player.gender,
                'rank': p.player.rank
            } for p in players
        ]
    }
    return JsonResponse(data)


@superuser_required
def create_team_(request):
    admin_user = User.objects.get(id=request.user.id)    
    context = {"team_info":[], "message":"","pre_player_ids":[], "oppration":"Create", "button":"Submit"}
    
    if request.method == "POST":
        team_name = request.POST.get('team_name')
        team_image = request.FILES.get('team_image')
        team_person = request.POST.get('team_person')
        team_type = request.POST.get('team_type')
        player_ids = request.POST.getlist('player_ids')

        if not team_name and not team_person and not team_type:            
            context["message"] = "Team name, team person and team type are required."
            return render(request, "dashboard/side/create_team_form.html", context)
        
        if Team.objects.filter(name = team_name).exists():         
            context["message"] = "Team name already exists."
            return render(request, "dashboard/side/create_team_form.html", context) 
        
        if team_person == "Two Person Team" and len(player_ids) == 2:
            if team_type == "Men":                
                players = Player.objects.filter(id__in=player_ids)
                for player in players:
                    if not player.player.gender == "Male":                        
                        context["message"] = "Select male players only."
                        return render(request, "dashboard/side/create_team_form.html", context)                          
                
                obj = GenerateKey()
                secret_key = obj.gen_team_key()
                team = Team.objects.create(
                    name=team_name,
                    secret_key=secret_key,
                    team_image=team_image,
                    team_person=team_person,
                    team_type=team_type,
                    created_by_id=admin_user.id
                )                            
                for player in players:                    
                    player.team.add(team)
                    notify_message = f"Hey {player.player_first_name}! You have been added to an awesome team - {team.name}"
                    title = "Team Created."
                    notify_edited_player(user_id=player.player.id, titel=title, message=notify_message)
        
                return redirect(reverse('dashboard:team_list_for_admin'))            

            elif team_type == "Women":                
                players = Player.objects.filter(id__in=player_ids)
                for player in players:
                    if not player.player.gender == "Female":                       
                        context["message"] = "Select female players only."
                        return render(request, "dashboard/side/create_team_form.html", context)  
                    
                obj = GenerateKey()
                secret_key = obj.gen_team_key()
                team = Team.objects.create(
                    name=team_name,
                    secret_key=secret_key,
                    team_image=team_image,
                    team_person=team_person,
                    team_type=team_type,
                    created_by_id=admin_user.id
                )                        
                        
                for player in players:
                    player.team.add(team)
                    notify_message = f"Hey {player.player_first_name}! You have been added to an awesome team - {team.name}"
                    title = "Team Created."
                    notify_edited_player(user_id=player.player.id, titel=title, message=notify_message)
        
                return redirect(reverse('dashboard:team_list_for_admin'))
                    
            elif team_type == "Co-ed":
                players = Player.objects.filter(id__in=player_ids)
                male_player = players.filter(player__gender='Male') 
                female_player = players.filter(player__gender='Female')    
                if len(male_player) == 1 and len(female_player) == 1:                    
                    obj = GenerateKey()
                    secret_key = obj.gen_team_key()
                    team = Team.objects.create(
                        name=team_name,
                        secret_key=secret_key,
                        team_image=team_image,
                        team_person=team_person,
                        team_type=team_type,
                        created_by_id=admin_user.id
                    )                        
                   
                    players = Player.objects.filter(id__in=player_ids)
                    for player in players:
                        player.team.add(team)
                        notify_message = f"Hey {player.player_first_name}! You have been added to an awesome team - {team.name}"
                        title = "Team Created."
                        notify_edited_player(user_id=player.player.id, titel=title, message=notify_message)
            
                    return redirect(reverse('dashboard:team_list_for_admin'))
                else:
                    context["message"] = "Select one male player and one female player."
                    return render(request, "dashboard/side/create_team_form.html", context)
        elif team_person == "Two Person Team" and len(player_ids) != 2:
            context["message"] = "Need to select two players."
            return render(request, "dashboard/side/create_team_form.html", context) 
          
        elif team_person == "One Person Team" and len(player_ids) == 1:
            if team_type == "Men":                
                players = Player.objects.filter(id__in=player_ids)
                if not players.first().player.gender == "Male": 
                    context["message"] = "Select male player only."
                    return render(request, "dashboard/side/create_team_form.html", context)     
                    
                obj = GenerateKey()
                secret_key = obj.gen_team_key()
                team = Team.objects.create(
                    name=team_name,
                    secret_key=secret_key,
                    team_image=team_image,
                    team_person=team_person,
                    team_type=team_type,
                    created_by_id=admin_user.id
                )                                  
                for player in players:
                    player.team.add(team)
                    notify_message = f"Hey {player.player_first_name}! You have been added to an awesome team - {team.name}"
                    title = "Team Created."
                    notify_edited_player(user_id=player.player.id, titel=title, message=notify_message)
        
                return redirect(reverse('dashboard:team_list_for_admin'))                       

            elif team_type == "Women":
                players = Player.objects.filter(id__in=player_ids)
                if not players.first().player.gender == "Female":       
                    context["message"] = "Select female player only."
                    return render(request, "dashboard/side/create_team_form.html", context)
                obj = GenerateKey()
                secret_key = obj.gen_team_key()
                team = Team.objects.create(
                    name=team_name,
                    secret_key=secret_key,
                    team_image=team_image,
                    team_person=team_person,
                    team_type=team_type,
                    created_by_id=1
                )                                    
                for player in players:
                    player.team.add(team)
                    notify_message = f"Hey {player.player_first_name}! You have been added to an awesome team - {team.name}"
                    title = "Team Created."
                    notify_edited_player(user_id=player.player.id, titel=title, message=notify_message)
        
                return redirect(reverse('dashboard:team_list_for_admin'))
                    
        elif team_person == "One Person Team" and len(player_ids) != 1:
            context["message"] = "Need to select only one person."
            return render(request, "dashboard/side/create_team_form.html", context)
    return render(request, "dashboard/side/create_team_form.html", context)


@superuser_required
def edit_team_(request, team_id):
    team_info = get_object_or_404(Team, id=team_id)
    pre_player_ids = list(Player.objects.filter(team__id=team_id).values_list("id", flat=True))
    context = {"team_info":team_info, "message":"","pre_player_ids":pre_player_ids, "oppration":"Edit", "button":"Submit"}
    
    if request.method == "POST":
        team_name = request.POST.get('team_name')
        team_image = request.FILES.get('team_image')
        team_person = request.POST.get('team_person')
        team_type = request.POST.get('team_type')
        player_ids = request.POST.getlist('player_ids')
        if not team_name and not team_person and not team_type:
            # return HttpResponse("Team name, team person and team type are required.")
            context["message"] = "Team name, team person and team type are required."
            return render(request, "dashboard/side/edit_team_form.html", context)
        
        # Update team information
        team_info.name = team_name
        if team_image:
            team_info.team_image = team_image
        team_info.team_person = team_person
        team_info.team_type = team_type
        team_info.save()
        
        # Update players associated with the team
        if team_person == "Two Person Team":
            if len(player_ids) != 2:
                context["message"] = "Need to select two players."
                return render(request, "dashboard/side/edit_team_form.html", context)
        elif team_person == "One Person Team":
            if len(player_ids) != 1:
                context["message"] = "Need to select only one player."
                return render(request, "dashboard/side/edit_team_form.html", context)
        
        removed_players = []
        new_players = []
        # Assign the selected players to the team
        if team_person == "Two Person Team" and len(player_ids) == 2:
            if team_type == "Men":
                players = Player.objects.filter(id__in=player_ids)
                for player in players:
                    if not player.player.gender == "Male":
                        # return HttpResponse("Select male players only.")
                        context["message"] = "Select male players only."
                        return render(request, "dashboard/side/edit_team_form.html", context)
                for player_id in pre_player_ids:
                    pre_player = Player.objects.get(id=player_id)
                    removed_players.append(player_id) 
                    pre_player.team.remove(team_info)
                for player in players:
                    new_players.append(player.id)
                    player.team.add(team_info)
                team_info.save()
                add, rem = check_add_player(new_players, removed_players)
                    
                titel = "Team Membership Modification"
                for r in rem:
                    message = f"You have been removed from team {team_info.name}"
                    user_id = Player.objects.filter(id=r).first().player.id
                    notify_edited_player(user_id, titel, message)

                titel = "Team Membership Modification"
                for r in add:
                    message = f"You have been added to team {team_info.name}"
                    user_id = Player.objects.filter(id=r).first().player.id
                    notify_edited_player(user_id, titel, message)

                return redirect(reverse('dashboard:team_list_for_admin'))
                
            elif team_type == "Women":
                players = Player.objects.filter(id__in=player_ids)
                for player in players:
                    if not player.player.gender == "Female":
                        # return HttpResponse("Select female players only.")
                        context["message"] = "Select female players only."
                        return render(request, "dashboard/side/edit_team_form.html", context)
                for player_id in pre_player_ids:
                    pre_player = Player.objects.get(id=player_id)
                    removed_players.append(player_id) 
                    pre_player.team.remove(team_info)
                for player in players:
                    new_players.append(player.id)
                    player.team.add(team_info)
                team_info.save()
                add, rem = check_add_player(new_players, removed_players)
                    
                titel = "Team Membership Modification"
                for r in rem:
                    message = f"You have been removed from team {team_info.name}"
                    user_id = Player.objects.filter(id=r).first().player.id
                    notify_edited_player(user_id, titel, message)

                titel = "Team Membership Modification"
                for r in add:
                    message = f"You have been added to team {team_info.name}"
                    user_id = Player.objects.filter(id=r).first().player.id
                    notify_edited_player(user_id, titel, message)

                return redirect(reverse('dashboard:team_list_for_admin'))
                    
            elif team_type == "Co-ed":
                players = Player.objects.filter(id__in=player_ids)
                male_player = players.filter(player__gender='Male') 
                female_player = players.filter(player__gender='Female')    
                if len(male_player) == 1 and len(female_player) == 1:
                    for player_id in pre_player_ids:
                        pre_player = Player.objects.get(id=player_id)
                        removed_players.append(player_id) 
                        pre_player.team.remove(team_info)
                    for player in players:                            
                        new_players.append(player.id)
                        player.team.add(team_info)
                    team_info.save()
                    add, rem = check_add_player(new_players, removed_players)
                    
                    titel = "Team Membership Modification"
                    for r in rem:
                        message = f"You have been removed from team {team_info.name}"
                        user_id = Player.objects.filter(id=r).first().player.id
                        notify_edited_player(user_id, titel, message)

                    titel = "Team Membership Modification"
                    for r in add:
                        message = f"You have been added to team {team_info.name}"
                        user_id = Player.objects.filter(id=r).first().player.id
                        notify_edited_player(user_id, titel, message)
                    return redirect(reverse('dashboard:team_list_for_admin'))
                else:
                    context["message"] = "Select one male player and one female player."
                    return render(request, "dashboard/side/edit_team_form.html", context)    
        elif team_person == "One Person Team" and len(player_ids) == 1: 
            if team_type == "Men":
                players = Player.objects.filter(id__in=player_ids)
                if not players.first().player.gender == "Male":
                    # return HttpResponse("Select male player only.")
                    context["message"] = "Select male player only."
                    return render(request, "dashboard/side/edit_team_form.html", context)
                for player_id in pre_player_ids:
                    pre_player = Player.objects.get(id=player_id)
                    removed_players.append(player_id) 
                    pre_player.team.remove(team_info)
                for player in players:
                    new_players.append(player.id)
                    player.team.add(team_info)
                team_info.save()
                add, rem = check_add_player(new_players, removed_players)
                
                titel = "Team Membership Modification"
                for r in rem:
                    message = f"You have been removed from team {team_info.name}"
                    user_id = Player.objects.filter(id=r).first().player.id
                    notify_edited_player(user_id, titel, message)

                titel = "Team Membership Modification"
                for r in add:
                    message = f"You have been added to team {team_info.name}"
                    user_id = Player.objects.filter(id=r).first().player.id
                    notify_edited_player(user_id, titel, message)
                return redirect(reverse('dashboard:team_list_for_admin'))
                    
            elif team_type == "Women":
                players = Player.objects.filter(id__in=player_ids)
                if not players.first().player.gender == "Female":
                    # return HttpResponse("Select female player only.")
                    context["message"] = "Select female player only."
                    return render(request, "dashboard/side/edit_team_form.html", context)
                for player_id in pre_player_ids:
                    pre_player = Player.objects.get(id=player_id)
                    removed_players.append(player_id) 
                    pre_player.team.remove(team_info)
                for player in players:
                    new_players.append(player.id)
                    player.team.add(team_info)
                team_info.save()
                add, rem = check_add_player(new_players, removed_players)
                
                titel = "Team Membership Modification"
                for r in rem:
                    message = f"You have been removed from team {team_info.name}"
                    user_id = Player.objects.filter(id=r).first().player.id
                    notify_edited_player(user_id, titel, message)

                titel = "Team Membership Modification"
                for r in add:
                    message = f"You have been added to team {team_info.name}"
                    user_id = Player.objects.filter(id=r).first().player.id
                    notify_edited_player(user_id, titel, message)

                return redirect(reverse('dashboard:team_list_for_admin'))                   
        else:
            context["message"] = "Something is Wrong"
    return render(request, "dashboard/side/edit_team_form.html", context)


from urllib.parse import quote
@superuser_required
def view_team_(request,team_id):
    context={}
    # team_view = list(Team.objects.filter(id=team_id).values("id","name","team_person","team_image","team_type","created_by__first_name", "created_by__last_name"))
    base_url = request.build_absolute_uri('/')[:-1]
    no_img = base_url + "/media/team_image/No_Image_Available.jpg"
    
    team = Team.objects.get(id=team_id)
    context["team_id"] = team.id
    context['name'] = team.name
    context['team_image'] = team.team_image if team.team_image else no_img
    context['team_person'] = team.team_person
    context['team_type'] = team.team_type
    context['created_by__first_name'] = team.created_by.first_name
    context['created_by__last_name'] = team.created_by.last_name
    player_qs = Player.objects.filter(team__id=team.id).values(
        "id", "player_full_name", "player__rank", "player__image", "player__gender"
    )

    player_list = []
    for p in player_qs:
        image_path = p.get("image")
        if image_path and image_path.lower() != 'null':
            if image_path.startswith("/"):
                p["image_url"] = request.build_absolute_uri(image_path)
            else:
                p["image_url"] = request.build_absolute_uri(settings.MEDIA_URL + image_path)
        else:
            p["image_url"] = None
        player_list.append(p)

    context["player_list"] = player_list

    match_history = Tournament.objects.filter(Q(team1=team) | Q(team2=team)).order_by("-id")

    wins = match_history.filter(winner_team=team).count()
    losses = match_history.count() - wins
    total_matches = match_history.count()

    for match in match_history:
        match.opponent = match.team2 if team.id == match.team1.id else match.team1
        match.scores = TournamentSetsResult.objects.filter(tournament=match)

    # Pagination for match_history
    match_page_number = request.GET.get('match_page')
    match_paginator = Paginator(match_history, 6)  # Show 5 matches per page
    match_history_page = match_paginator.get_page(match_page_number)

    context["total_matches"] = total_matches
    context["wins"] = wins
    context["losses"] = losses
    context["all_match_history"] = match_history_page
    return render(request, "dashboard/side/team_view.html",context)


@superuser_required
def delete_team_(request,team_id):
    message = ""
    team_del = get_object_or_404(Team, id=team_id)
    if request.method == 'POST':
        check_team_have_any_tournament = Leagues.objects.filter(registered_team__in=[team_id], is_complete=False)
        check_winner_team = Leagues.objects.filter(is_complete=True, winner_team=team_del)
        if not check_team_have_any_tournament.exists():
            team_name = team_del.name
            players = Player.objects.filter(team__id=team_id)
            players_list = list(players)
            if check_winner_team.exists():
                team_del.is_disabled = True
            else:                 
                team_del.delete()
                for player in players_list:
                    player.team.remove(team_del)
            titel = "Team Membership Modification"
            notify_message = f"Hey player! the team {team_name} has been deleted."
            for player in players_list:
                notify_edited_player(player.player.id, titel, notify_message)
            return redirect(reverse('dashboard:team_list_for_admin'))
        else:
            # return HttpResponse('Team cannot be deleted as it is registered for tournament.')
            message = "Team cannot be deleted as it is registered for tournament."
            return render(request, 'dashboard/side/team_delete_confirm.html', {'team_del': team_del, "message":message})
    return render(request, 'dashboard/side/team_delete_confirm.html', {'team_del': team_del, "message":message})

#### team section end

### tournament section

@superuser_required
def tournament_list(request, filter_by):
    context = {"tournament_data": []}
    filter_by = request.GET.get('filter_by')
    search_text = request.GET.get("search_text")
    page_length = int(request.GET.get("page_length", 20))
    location = request.GET.get("location")

    
    all_leagues = Leagues.objects.filter(is_disabled=False).exclude(team_type__name="Open-team").order_by('-created_at')  # Order by created_at descending

    if search_text:
        all_leagues = all_leagues.filter(Q(name__icontains=search_text) | Q(description__icontains=search_text) | Q(play_type__icontains=search_text))

    today_date = datetime.now().date()

    # Filter leagues based on filter_by
    if filter_by == "all":
        all_leagues = all_leagues
    elif filter_by == "upcoming":
        all_leagues = all_leagues.filter(leagues_start_date__date__gte=today_date)
    elif filter_by == "past":
        all_leagues = all_leagues.filter(registration_end_date__date__lte=today_date)
    elif filter_by == "open":
        all_leagues = all_leagues.filter(registration_start_date__date__lte=today_date,
                                         registration_end_date__date__gte=today_date)
    elif filter_by == "ongoing":
        all_leagues = all_leagues.filter(leagues_start_date__date__lte=today_date,
                                         leagues_end_date__date__gte=today_date)

    leagues = all_leagues.annotate(
            registered_team_count=Count('registered_team')
        ).values('id', 'description', 'uuid', 'secret_key', 'name', 'location', 'leagues_start_date', 
                                 'leagues_end_date', 'registration_start_date', 'registration_end_date', 
                                 'team_type__name', 'team_person__name', 'street', 'city', 'state', 'postal_code', 
                                 'country', 'complete_address', 'latitude', 'longitude', 'image', 'others_fees', 
                                 'league_type', 'registration_fee', 'created_at', 'max_number_team', 'registered_team_count')
    
    if location:
        ref_lat, ref_lon = get_lat_long(settings.MAP_API_KEY, location)
        if ref_lat is not None and ref_lon is not None:
            filtered_leagues = []
            for league in leagues:
                if league['latitude'] not in [0, "", None, "null"] and league["longitude"] not in [0, "", None, "null"]:
                    league_lat, league_long = float(league['latitude']), float(league['longitude'])
                    
                    distance = haversine(ref_lat, ref_lon, league_lat, league_long)
                    if distance <= 100:  # radius in KM
                        filtered_leagues.append(league)
            leagues = filtered_leagues
        else:
            leagues = []

    for league in leagues:
        image_path = league.get("image")
        if image_path and image_path.lower() != 'null':
            if image_path.startswith("/"):
                league["image_url"] = request.build_absolute_uri(image_path)
            else:
                league["image_url"] = request.build_absolute_uri(settings.MEDIA_URL + image_path)
        else:
            league["image_url"] = None

    # Pagination   
    page = request.GET.get('page')
    paginator = Paginator(leagues, page_length)
    try:
        page_obj = paginator.page(page)
    except:
        page_obj = paginator.page(1)

    
    context.update({
            "tournament_data": page_obj,
            "page_range": get_custom_pagination_range(page_obj, paginator),
            "search_text": search_text,
            "page_length": str(page_length),
            "location": location,
            'filter_by':filter_by
        })
    return render(request, "dashboard/side/tournament_list.html", context)


@superuser_required
def view_tournament(request, tour_id):
    context = {
        "league_details": [],
        "matches":[],
        "teams":[],
        "message":None
    }
    today = timezone.now()
    try:      
        League_details = Leagues.objects.filter(id=tour_id).first()
        context["league_details"] = League_details
        if League_details.leagues_start_date > today:
            context["is_unregister"] = True
        else:
            context["is_unregister"] = False
        
        
        if League_details.registration_end_date:
            context["is_join"] = League_details.registration_end_date.date() >= today.date()
        else:
            context["is_join"] = False
        have_score = TournamentSetsResult.objects.filter(tournament__leagues = League_details)
        if have_score:
            context["is_edit_match"] = False
        else:
            context["is_edit_match"] = True
        if League_details.registered_team:
            context["teams"] = League_details.registered_team.all()
        matches = Tournament.objects.filter(leagues=League_details).values().order_by('id')
        for mtch in matches:
            mtch["result"] = TournamentSetsResult.objects.filter(tournament=mtch["id"])
            if mtch["team1_id"]:
                mtch["team1"] = Team.objects.filter(id=mtch["team1_id"]).first().name
                mtch["team1_image"] = Team.objects.filter(id=mtch["team1_id"]).first().team_image
            else:
                mtch["team1"] = None
                mtch["team1_image"] = None

            if mtch["team2_id"]:
                mtch["team2"] = Team.objects.filter(id=mtch["team2_id"]).first().name
                mtch["team2_image"] = Team.objects.filter(id=mtch["team2_id"]).first().team_image
            else:
                mtch["team2"] = None
                mtch["team2_image"] = None

            if mtch["winner_team_id"]:
                mtch["winner_team"] = Team.objects.filter(id=mtch["winner_team_id"]).first().name
                mtch["winner_team_image"] = Team.objects.filter(id=mtch["winner_team_id"]).first().team_image
            else:
                mtch["winner_team"] = None
                mtch["winner_team_image"] = None

            if mtch["loser_team_id"]:
                mtch["loser_team"] = Team.objects.filter(id=mtch["loser_team_id"]).first().name
                mtch["loser_team_image"] = Team.objects.filter(id=mtch["loser_team_id"]).first().team_image
            else:
                mtch["loser_team"] = None
                mtch["loser_team_image"] = None
        context["matches"] = matches
    except Exception as e:
        context["message"] = str(e)
    
    play_type_details = LeaguesPlayType.objects.filter(league_for=League_details)
    if play_type_details:
        play_type_details = play_type_details.first().data
    else:
        play_type_details = [
                        {"name": "Round Robin", "number_of_courts": 0, "sets": 0, "point": 0},
                        {"name": "Elimination", "number_of_courts": 0, "sets": 0, "point": 0},
                        {"name": "Final", "number_of_courts": 0, "sets": 0, "point": 0}
                        ]
    check_data = check_data_structure(play_type_details)
    context["play_details_update"] = check_data
    
    return render(request, "dashboard/side/tournament_type_details.html",context)


@superuser_required
def edit_tournament(request, tour_id):
    context = {}
    league_details = Leagues.objects.get(id=tour_id)
    # try:
        # Get the league details or raise an error if it doesn't exist
    if request.method == "POST":
        # Process the POST request and update the league details
        league_details.name = request.POST.get("tournament_name", league_details.name)
        league_details.leagues_start_date = request.POST.get("league_start_date", league_details.leagues_start_date)
        league_details.leagues_end_date = request.POST.get("league_end_date", league_details.leagues_end_date)
        league_details.registration_start_date = request.POST.get("registration_start_date", league_details.registration_start_date)
        league_details.registration_end_date = request.POST.get("registration_end_date", league_details.registration_end_date)
        league_details.max_number_team = request.POST.get("max_join_team", league_details.max_number_team)
        league_details.registration_fee = request.POST.get("registration_fee", league_details.registration_fee)
        league_details.description = request.POST.get("description", league_details.description)
        league_details.location = request.POST.get("location", league_details.location)
        
        # Handle many-to-many relationship with teams (Join Team)
        selected_teams = request.POST.getlist("join_team")
        league_details.registered_team.set(selected_teams)

        # Handle other fees, if any
        other_fees_topic = request.POST.getlist("other_fees_topic[]")
        other_fees = request.POST.getlist("other_fees[]")
        other_fees_dict = dict(zip(other_fees_topic, other_fees))
        league_details.others_fees = other_fees_dict
        if "image" in request.FILES:
            league_details.image = request.FILES["image"]

        # Handle Organizer Selection
        organizer_ids = request.POST.getlist("organizer")  # Get multiple selected users
        if organizer_ids:
            league_details.add_organizer.set(organizer_ids)  # Directly set the ManyToMany field
        else:
            league_details.add_organizer.clear()

        cancellation_days = request.POST.getlist("cancellation_days[]")
        refund_percentages = request.POST.getlist("refund_percentage[]")

        # Clear existing policies
        LeaguesCancellationPolicy.objects.filter(league=league_details).delete()

        # Save new policies
        for day, refund in zip(cancellation_days, refund_percentages):
            if day and refund:
                LeaguesCancellationPolicy.objects.create(
                    league=league_details,
                    within_day=int(day),
                    refund_percentage=(float(refund))
                )

        league_details.save()


        courts_1 = request.POST.get("courts_1", 0)
        sets_1 = request.POST.get("sets_1", 0)
        points_1 = request.POST.get("points_1", 0)

        courts_2 = request.POST.get("courts_2", 0)
        sets_2 = request.POST.get("sets_2", 0)
        points_2 = request.POST.get("points_2", 0)

        courts_3 = request.POST.get("courts_3", 0)
        sets_3 = request.POST.get("sets_3", 0)
        points_3 = request.POST.get("points_3", 0)

        play_details = LeaguesPlayType.objects.filter(league_for=league_details).first()
        tournament_play_type = league_details.play_type
        data_ = [{"name": "Round Robin", "number_of_courts": courts_1, "sets": sets_1, "point": points_1},
                {"name": "Elimination", "number_of_courts": courts_2, "sets": sets_2, "point": points_2},
                {"name": "Final", "number_of_courts": courts_3, "sets": sets_3, "point": points_3}]
        # print(data_, "data")
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
        # print("hit", data_)
        play_details.data = data_
        play_details.save()
        return redirect(reverse('dashboard:view_tournament', kwargs={"tour_id":tour_id}))


    tournament_play_type = league_details.play_type
    play_type_details = LeaguesPlayType.objects.filter(league_for=league_details)
    cancelation_policy = LeaguesCancellationPolicy.objects.filter(league=league_details)
    if play_type_details:
        play_type_details = play_type_details.first().data
        
    else:
        play_type_details = [
                    {"name": "Round Robin", "number_of_courts": 0, "sets": 0, "point": 0},
                    {"name": "Elimination", "number_of_courts": 0, "sets": 0, "point": 0},
                    {"name": "Final", "number_of_courts": 0, "sets": 0, "point": 0}
                    ]
    for se in play_type_details:
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
    # Initialize context dictionary
    context = {
        "league_details": Leagues.objects.get(id=tour_id),
        "teams": Team.objects.all(),
        "play_type_details": play_type_details,
        "policies": cancelation_policy,
    }
    check_data = check_data_structure(play_type_details)
    context["play_details_update"] = check_data
    users = User.objects.all()  # Fetch all users
    context["users"] = users
    # print(context)
    return render(request, "dashboard/side/edit_tournamnet.html", context)

    # except Leagues.DoesNotExist:
    #     # If the league doesn't exist, raise a 404 error
    #     raise Http404("Tournament not found.")
    # except Exception as e:
    #     # Log or handle other exceptions
    #     context["message"] = str(e)
    #     print(context)
    #     return render(request, "dashboard/side/edit_tournamnet.html", context)
    

@superuser_required
def edit_matches__(request, tour_id):
    
    league_details = Leagues.objects.get(id=tour_id)
    
    # Initialize context dictionary
    context = {
        "matches": Tournament.objects.filter(leagues=league_details), 
        "league_name": league_details.name
    }
    
    return render(request, "dashboard/side/edit_matches.html", context)


@csrf_exempt
@superuser_required
def update_match_order(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            match_order = data.get('matchOrder', [])
            for index, match_id in enumerate(match_order):
                Tournament.objects.filter(id=match_id).update(match_number=index + 1)
            return JsonResponse({"success": True})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})
    return JsonResponse({"success": False, "error": "Invalid request"})


@superuser_required
def update_match(request, set_score_id):
    match = get_object_or_404(TournamentSetsResult, id=set_score_id)
    if request.method == 'POST':
        
        # tournament_id = request.POST.get('tournament_id')
        set_number = request.POST.get(f'set_num_{match.id}')
        team1_score = request.POST.get(f't1_score_{match.id}')
        team2_score = request.POST.get(f't2_score_{match.id}')
        # status = request.POST.get(f'status_{match.id}')

        if set_number and team1_score and team2_score:
            match.set_number = int(set_number)
            match.team1_point = int(team1_score)
            match.team2_point = int(team2_score)
            match.is_completed = True
            match.save()
        return redirect(reverse("dashboard:view_tournament", kwargs={"tour_id":match.tournament.leagues.id}))
    
    return redirect(reverse("dashboard:view_tournament", kwargs={"tour_id":match.tournament.leagues.id}))


@superuser_required
def hit_start_tournamnet(request, tour_id):
    check_tour = Leagues.objects.filter(id=tour_id).first()
    tour_create_by = check_tour.created_by
    max_number_teams = check_tour.registered_team.count()
    check_tour.max_number_team = max_number_teams
    check_tour.save()
    host = request.get_host()
    current_site = f"{protocol}://{host}"
    url = f"{current_site}/team/22fef865dab2109505b61d85df50c5126e24f0c0a10990f2670c179fb841bfd2/"
    # print(url)
    payload = {
        'user_uuid': str(tour_create_by.uuid),
        'user_secret_key': str(tour_create_by.secret_key),
        'league_uuid': str(check_tour.uuid),
        'league_secret_key': str(check_tour.secret_key)
    }
    try:
        response = requests.post(url, json=payload)
        response_data = response.json()
        if response.status_code == 200:
            messages.success(request, response_data.get("message", "Tournament started successfully."))
        else:
            messages.error(request, response_data.get("message", "Failed to start tournament."))
    except Exception as e:
        messages.error(request, f"API error: {str(e)}")
    return redirect('dashboard:view_tournament', tour_id=tour_id)


@superuser_required
def create_tournamnet(request):
    context = {}
    if request.method == 'POST':
        name = request.POST.get('name')
        r_start_date = request.POST.get('r_start_date')
        r_end_date = request.POST.get('r_end_date')
        t_start_date = request.POST.get('t_start_date')
        t_end_date = request.POST.get('t_end_date')
        image = request.FILES.get('image')
        description = request.POST.get('description')
        location = request.POST.get('location')
        max_team = request.POST.get('max_team')
        registration_fee = request.POST.get('registration_fees')
        other_fees_names = request.POST.getlist('other_fees_name[]')
        other_fees_costs = request.POST.getlist('other_fees_cost[]')
        play_type = request.POST.getlist('play_type')
        team_type = request.POST.getlist('team_type')
        team_person = request.POST.getlist('player_type')
        league_type = request.POST.get('league_type')
        city = None
        others_fees = {}
        for i in range(len(other_fees_names)):
            key = other_fees_names[i] 
            value = other_fees_costs[i]
            others_fees[key] = value

        if int(max_team) % 2 != 0 or int(max_team) == 0 or int(max_team) == 1:
            context["message"] = "Max number of team is must be even"
            return render(request, "dashboard/side/create_tournamnet_form.html", context)
        max_number_team=max_team
        leagues_start_date = t_start_date
        leagues_end_date = t_end_date
        registration_start_date = r_start_date
        registration_end_date = r_end_date
        leagues_id = []
        
        mesage_box = []
        counter = 0
        for kk in team_type:
            # print(team_person[counter])
            check_leagues = LeaguesTeamType.objects.filter(name=str(kk))
            check_person = LeaguesPesrsonType.objects.filter(name=str(team_person[counter]))
            # print(check_leagues)
            # print(check_person)
            if check_leagues.exists() and check_person.exists():
                check_leagues_id = check_leagues.first().id
                check_person_id = check_person.first().id
                check_unq = Leagues.objects.filter(team_person_id=check_person_id,team_type_id=check_leagues_id,name=name,created_by=request.user.id)
                if check_unq.exists():
                    message = f"{name}-{kk}"
                    mesage_box.append(message)
                    continue
                else:
                    pass
            
            full_address = location
            api_key = settings.MAP_API_KEY
            state, country, pincode, latitude, longitude = get_address_details(full_address,api_key)

            latitude = str(latitude)[:15] if latitude else "38.908683"
            longitude = str(longitude)[:15] if longitude else "-76.937352"
            obj = GenerateKey()
            secret_key = obj.gen_leagues_key()
            save_leagues = Leagues(secret_key=secret_key,name=name,leagues_start_date=leagues_start_date,leagues_end_date=leagues_end_date,location=location,
                                registration_start_date=registration_start_date,registration_end_date=registration_end_date,created_by_id=request.user.id,
                                street=state,city=city,state=state,postal_code=pincode,country=country,max_number_team=max_number_team, play_type=play_type[counter],
                                registration_fee=registration_fee,description=description,image=image,league_type=league_type)
            if league_type == "Invites only":
                invited_code = generate_invited_code(save_leagues.name)
                save_leagues.invited_code = invited_code 
            save_leagues.others_fees = others_fees
            save_leagues.save() 
            
            # if lat is not None and long is not None:
            save_leagues.latitude=latitude
            save_leagues.longitude=longitude
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
            tournament_play_type = main_data.first().play_type
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
                # print(i)
                i["team_type"] = LeaguesTeamType.objects.filter(id = i["team_type_id"]).first().name
                i["team_person"] = LeaguesPesrsonType.objects.filter(id = i["team_person_id"]).first().name
                user_first_name = request.user.first_name
                user_last_name = request.user.last_name
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
        context["message"] = set_msg
        return redirect("/admin/tournamnet_list/all")

    return render(request, "dashboard/side/create_tournamnet_form.html", context)


@superuser_required
def submit_score(request, tour_id):
    context = {"dis_message":""}
    tournament = Leagues.objects.filter(id=tour_id).first()
    if request.method == "POST":
        match_id = request.POST.get("match_id")
        get_team1_score = request.POST.getlist("team1_score")
        team1_score = []
        for i in get_team1_score:
            if i == "" or not i:
                pass
            else:
                team1_score.append(int(i))

        get_team2_score = request.POST.getlist("team2_score")
        team2_score = []
        for i in get_team2_score:
            if i == "" or not i:
                pass
            else:
                team2_score.append(int(i))
        match = Tournament.objects.filter(id=match_id).first()
        set_number = match.set_number
        print(match_id, team1_score, team2_score, set_number)
        if int(set_number) == len(team1_score):
            te1_win=[]
            te2_win=[]
            for up_ in range(len(team1_score)):
                set_num = up_ + 1
                team1_point = team1_score[up_]
                team2_point = team2_score[up_]
                if int(team1_point) >= int(team2_point):
                    winner = match.team1
                    te1_win.append(True)
                    te2_win.append(False)
                else:
                    te1_win.append(False)
                    te2_win.append(True)
                    winner = match.team2
                match_result = TournamentSetsResult.objects.filter(tournament=match, set_number=set_num)
                if match_result.exists():
                    match_result.update(team1_point=team1_point, team2_point=team2_point, is_completed=True,win_team=winner)
                else:
                    TournamentSetsResult.objects.create(tournament=match, set_number=set_num, team1_point=team1_point, team2_point=team2_point, is_completed=True,win_team=winner)
            te1_wins = sum(1 for result in te1_win if result)
            te2_wins = sum(1 for result in te2_win if result)
            is_drow = False
            # print(te1_wins,te2_wins,is_drow)
            if te1_wins > te2_wins:
                winner = match.team1
                looser = match.team2
            elif te2_wins > te1_wins:
                winner = match.team2
                looser = match.team1
            else:
                winner = None
                looser = None
                is_drow = True
            match.winner_team = winner
            match.loser_team = looser
            if is_drow is True:
                match.is_drow = True
                match.winner_team_score = 1
                match.loser_team_score = 1
            else:
                match.winner_team_score = 3
                match.loser_team_score = 0
            match.is_completed = True
            match.save()
            title = "Match score update"
            if winner is not None and looser is not None:
                message = f"Wow, you have won the match {match.match_number}, the scores are approved"
                message2 = f"Sorry, you have lost the match {match.match_number}, the scores are approved"
                
                winner_player = Player.objects.filter(team__id=winner.id)
                if winner_player.exists():
                    for pl in winner_player:
                        user_id = pl.player.id
                        notify_edited_player(user_id, title, message)
                looser_player = Player.objects.filter(team__id=looser.id)
                
                if looser_player.exists():
                    for pl in looser_player:
                        user_id = pl.player.id
                        notify_edited_player(user_id, title, message2)
            else:
                message = f"The match {match.match_number} was drawn, the scores are approved"
                team_1_ins = match.team1
                team_2_ins = match.team2
                team_one_player_list = Player.objects.filter(team__id = team_1_ins.id)
                team_two_player_list = Player.objects.filter(team__id = team_2_ins.id)
                for pl1 in team_one_player_list:
                    user_id = pl1.player.id
                    notify_edited_player(user_id, title, message) 
                for pl2 in team_two_player_list:
                    user_id = pl2.player.id
                    notify_edited_player(user_id, title, message)
        else:
            for up_ in range(len(team1_score)):
                set_num = up_ + 1
                team1_point = team1_score[up_]
                team2_point = team2_score[up_]
                if int(team1_point) >= int(team2_point):
                    winner = match.team1
                else:
                    winner = match.team2
                match_result = TournamentSetsResult.objects.filter(tournament=match, set_number=set_num)
                if match_result.exists():
                    match_result.update(team1_point=team1_point, team2_point=team2_point)
                else:
                    TournamentSetsResult.objects.create(tournament=match, set_number=set_num, team1_point=team1_point, team2_point=team2_point)
        return redirect(reverse("dashboard:view_tournament", kwargs={"tour_id":tour_id}))
    
    return redirect(reverse("dashboard:view_tournament", kwargs={"tour_id":tour_id}))


@superuser_required
def delete_tournament(request, tour_id):
    print("call")
    tournament = get_object_or_404(Leagues, id=tour_id)
    TournamentSetsResult.objects.filter(tournament__leagues=tournament).delete()
    Tournament.objects.filter(leagues=tournament).delete()
    RoundRobinGroup.objects.filter(league_for=tournament).delete()
    LeaguesPlayType.objects.filter(league_for=tournament).delete()
    LeaguesCancellationPolicy.objects.filter(league=tournament).delete()
    SaveLeagues.objects.filter(ch_league=tournament).delete()

    tournament.delete()
   
    return redirect("/admin/tournamnet_list/all") 


@superuser_required
def join_team_tournament(request, tour_id):
    context = {"STRIPE_PUBLIC_KEY": settings.STRIPE_PUBLIC_KEY}
    user = User.objects.filter(is_superuser=True).first()
    print(user)
    today = datetime.now()
    event = get_object_or_404(Leagues, id=tour_id)
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
    print(my_team)
    team_type = event.team_type
    team_person = event.team_person
    if team_type:
        my_team = my_team.filter(team_type=team_type)
    if team_person:
        my_team = my_team.filter(team_person=team_person)
    for team in my_team:
        team.players = Player.objects.filter(team=team)
    print(my_team)
    context["my_team"] = my_team
    context["event"] = event
    context["balance"] = float(Wallet.objects.filter(user=request.user).first().balance)
    is_open_team = event.team_type.name == "Open-team"
    context['is_open_team'] = is_open_team
    fees = Decimal(float(event.registration_fee))

    others_fees = event.others_fees
    if others_fees:
        for val in others_fees.values():
            try:
                fees += Decimal(float(val))  
            except (ValueError, TypeError):
                continue  
    context["total_fees"] = float(fees)
    return render(request, 'dashboard/side/register_team.html', context=context)

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

            # Calculate refund based on policy
            refund_amount =  Decimal(league.registration_fee)

            # Add refund to user's wallet
            if refund_amount > 0:
                wallet, created = Wallet.objects.get_or_create(user=user)
                wallet.balance += refund_amount
                wallet.save()
                print(wallet.balance)

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

            # Send notification to team owner
            player_ids = list(Player.objects.filter(team=team).values_list('player_id', flat=True))
            user_ids = player_ids
            if team.created_by.id not in player_ids:
                user_ids = [team.created_by.id] + player_ids
            title = "Team Removed From Tournament"
            message = f"Your team {team.name} has been removed from tournament {league.name} by admin. Kindly contact admin for more information"

            for id in user_ids:
                notify_edited_player(id, title, message)
            return JsonResponse({
                'success': True,
                'refund': str(refund_amount)
            })

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)


### tournament section end


#### social feed section

@superuser_required
def social_feed_list(request):
    search_text = request.GET.get("search_text", "")
    page_length = int(request.GET.get("page_length", 15))
    feed_query = socialFeed.objects.all().order_by("-created_at")
    filter_type = request.GET.get('filter_type')
    view_mode = request.GET.get("view", "my")

    if view_mode == "all":
        feed_query = feed_query
    else:
        feed_query = feed_query.filter(
            user=request.user
        )
    
    if search_text:
        feed_query = feed_query.filter(text__icontains=search_text)
    
    if filter_type == "all":
        feed_query = feed_query
    elif filter_type == 'unblocked':
        feed_query = feed_query.filter(block=False)
    elif filter_type == "blocked":
        feed_query = feed_query.filter(block=True)
    else:
        feed_query = feed_query

    # Attach files to each feed
    for feed in feed_query:
        # print(FeedFile.objects.filter(post=feed))
        files = FeedFile.objects.filter(post=feed).first()
        if files:
            feed.file = files.file.url
        else:
            feed.file = None
    
    page = request.GET.get("page", 1)
    paginator = Paginator(feed_query, page_length)
    try:
        feedlist = paginator.page(page)
    except:
        feedlist = paginator.page(1)
    context = {
        "feedlist": feedlist,
        "search_text": search_text,
        "page_range": get_custom_pagination_range(feedlist, paginator),
        "search_text": search_text,
        "page_length": str(page_length),
        "view_mode":view_mode
    }
    
    return render(request, 'dashboard/side/socail_feed/socailfeedlist.html', context)


@superuser_required
def add_social_feed(request):
    if request.method == "POST":
        text = request.POST.get("text")

        # Create the post
        post = socialFeed.objects.create(user=request.user, text=text)

        # Handle file uploads (if any)
        if request.FILES.getlist("files"):
            for file in request.FILES.getlist("files"):
                FeedFile.objects.create(post=post, file=file)

        return redirect("dashboard:social_feed_list")  # Redirect to the post list

    return render(request, "dashboard/side/socail_feed/add_post.html")


@superuser_required
def social_feed_view(request, post_id):
    post = get_object_or_404(socialFeed, id=post_id)
    files = FeedFile.objects.filter(post=post)
    comments = CommentFeed.objects.filter(post=post, parent_comment=None).order_by("-created_at")
    total_likes = LikeFeed.objects.filter(post=post).count()
    
    context = {
        "post": post,
        "files": files,
        "comments": comments,
        "total_likes": total_likes,
    }
    return render(request, "dashboard/side/socail_feed/postview.html", context)


@superuser_required
def edit_social_feed(request, post_id):
    post = get_object_or_404(socialFeed, id=post_id)
    files = post.post_file.all()

    if request.method == "POST":
        # Update post text
        post.text = request.POST.get("text")
        post.save()

        # Handle file uploads
        if request.FILES.getlist("files"):
            for file in request.FILES.getlist("files"):
                FeedFile.objects.create(post=post, file=file)

        return redirect("dashboard:social_feed_view", post_id=post_id)
    
    return render(request, "dashboard/side/socail_feed/editpost.html", {"post": post, "files": files})


@superuser_required
def delete_file(request, file_id):
    file = get_object_or_404(FeedFile, id=file_id, post__user=request.user)
    post_id = file.post.id
    file.delete()
    return redirect("dashboard:edit_social_feed", post_id=post_id)


@superuser_required
def block_social_feed(request, post_id):
    post = get_object_or_404(socialFeed, id=post_id)
    if post.block == False:
        post.block = True
    else:
        post.block = False
    post.save()
    return redirect(reverse("dashboard:social_feed_list"))

#### social feed section end


### advertisement section 

@superuser_required
def advertisement_list(request, filter_type):
    context = {"advertisements": "", "message": ""}
    
    filter_type = request.GET.get('filter_type', filter_type or "pending_requests")
    search_text = request.GET.get("search_text", "")
    page_length = int(request.GET.get("page_length", 20))
    
    ads = Advertisement.objects.all().order_by('created_at')
    if search_text:
        ads = ads.filter(Q(name__icontains=search_text) | Q(script_text__icontains=search_text) | Q(company_name__icontains=search_text) | Q(company_website__icontains=search_text))
    
    if filter_type == "all":
        ads = ads
    elif filter_type == "pending_requests":
        ads = ads.filter(admin_approve_status="Pending", approved_by_admin=False)
    elif filter_type == "rejected_requests":
        ads = ads.filter(admin_approve_status="Rejected", approved_by_admin=False)
    elif filter_type == "approved_requests":
        ads = ads.filter(admin_approve_status="Approved", approved_by_admin=True)
    else:
        ads = ads

    advertisemnts = ads
    page = request.GET.get("page", 1)
    paginator = Paginator(advertisemnts, page_length)
    try:
        advs = paginator.page(page)
    except:
        advs = paginator.page(1)
    context = {
        "advertisements": advs,
        "search_text": search_text,
        "page_range": get_custom_pagination_range(advs, paginator),
        "search_text": search_text,
        "page_length": str(page_length),
        "filter_type":filter_type
    }
    return render(request, "dashboard/side/advertisement_list.html", context)


@superuser_required
def advertisement_view(request, ad_id):
    context = {"ad":"", "message":""}
    ad = get_object_or_404(Advertisement, id=ad_id)
    context["ad"] = ad
    return render(request, "dashboard/side/advertisement_view.html", context)


@superuser_required
def ad_approve(request, ad_id):
    ad = get_object_or_404(Advertisement, id=ad_id)
    ad.approved_by_admin = True
    ad.admin_approve_status = "Approved"
    if ad.duration:
        ad.start_date = timezone.now()
        ad.end_date = timezone.now() + timedelta(days=ad.duration.duration)
    ad.save()
    return redirect(reverse("dashboard:advertisement_list", kwargs={"filter_type": "pending_requests"}))


@superuser_required
def ad_reject(request, ad_id):
    context = {"ad":"", "message":""}
    ad = get_object_or_404(Advertisement, id=ad_id)
    ad.approved_by_admin = False
    ad.admin_approve_status = "Rejected"
    ad.save()
    return redirect(reverse("dashboard:advertisement_list", kwargs={"filter_type": "pending_requests"}))

## advertisement section ends


###  payment list
@superuser_required
def payment_table(request):
    search_text = request.GET.get('search_text', '') 
    page_length = int(request.GET.get("page_length", 20)) 
    start_date = request.GET.get("start_date", None)
    end_date = request.GET.get("end_date", None)

    add_fund_payment = AllPaymentsTable.objects.all().order_by('-id')
    if search_text:
        add_fund_payment = add_fund_payment.filter(Q(user__first_name__icontains=search_text) | Q(user__last_name__icontains=search_text) | Q(user__username__icontains=search_text) | Q(checkout_session_id__icontains=search_text) | Q(payment_for__icontains=search_text))

    if start_date and end_date:
        add_fund_payment = add_fund_payment.filter(payment_date__date__gte=start_date, payment_date__date__lte=end_date)

    page = request.GET.get("page", 1) 
    paginator = Paginator(add_fund_payment, page_length)  # 10 players per page

    try:
        payment_page = paginator.page(page)
    except:
        payment_page = paginator.page(1)

    return render(
        request,
        "dashboard/side/payment/payment_details.html",
        {
            
            "add_fund_payment": payment_page, 
            "page_range": get_custom_pagination_range(payment_page, paginator),
            "page_length": str(page_length),
            "search_text":search_text
        },
    )
   
# Payment table ends

### admin profile
  
@superuser_required
def admin_profile(request):
    context = {"message":""}
    user = User.objects.get(id=request.user.id)
    Wallet_details = Wallet.objects.filter(user=user)
    if Wallet_details:
        Get_Wallet_details = Wallet_details.first()
    transaction = WalletTransaction.objects.filter(Q(sender=user) | Q(reciver=user)).order_by('-id')
    all_buy_plan = Subscription.objects.filter(user=user).order_by('-id')[:3]
    created_teams = Team.objects.filter(created_by=user)
    player = Player.objects.filter(player=user).prefetch_related('team').first()
    joined_teams = Team.objects.filter(player__player=user).distinct()
    teams = list(set(list(created_teams) + list(joined_teams)))
    all_team_data = []
    
    for team in teams:
        players_in_team = list(Player.objects.filter(team=team).values("player_full_name", "player__image"))
        dat = {
            "name":team.name,
            "image":team.team_image,
            "players":players_in_team,
            "created_by":team.created_by
               }
        all_team_data.append(dat)
    

    # Match history queryset
    match_history_qs = Tournament.objects.filter(
        Q(team1__in=teams) | Q(team2__in=teams)
    ).distinct()

    for match_ in match_history_qs:
        match_.opponent = match_.team2 if match_.team1 in teams else match_.team1
        match_.scores = TournamentSetsResult.objects.filter(tournament=match_)

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

    context["total_posts"] = total_posts
    context['followers'] = followers
    context["followings"] = followings
    context["user"] = user
    context["wallet_details"] = Get_Wallet_details
    context["transaction"] = transaction
    context["all_team_data"] = all_team_data
    context["all_match_history"] = match_history_page
    context["all_buy_plan"] = all_buy_plan
    context["social_feed_list"] = social_feed_page
    return render(request, 'dashboard/side/admin_profile.html', context)

## admin profile ends

### App version section 

@superuser_required
def app_update(request):
    context = {"data":[], "message":""}
    
    if request.method == "POST":
        version = request.POST["version"]
        version = float(version)
        version_ios = f"iOS {version}"
        version_andr = f"andr {version}"
        
        with open("data.json", "r") as file:
            data = json.load(file)
        
        data["version"].append(str(version_ios))
        data["version_"].append(str(version_andr))

        # Write the updated JSON data back to the file
        with open("data.json", "w") as file:
            json.dump(data, file, indent=4)
        update_data = AppUpdate.objects.filter(update=True).first()
        if update_data:
            update_data.updated_users.clear()
            
        context['message'] = f"Version{version} is Updated"
    with open("data.json", "r") as file:
        data_json = json.load(file)
    main_data = []
    for vr in range(len(data_json["version"])):
        set_data  = []
        set_data.append(data_json["version"][vr])
        set_data.append(data_json["version_"][vr])
        main_data.append(set_data)
    context["data"] = main_data[::-1]
    return render(request, 'dashboard/side/update/app_update_list.html', context)


@superuser_required
def version_update_list(request):
    context = {}
    version_updates = AppVersionUpdate.objects.all().values("version", "release_date", "description", "created_by", "updated_users")
    context["version_updates"] = version_updates
    return render(request, "dashboard/side/update/version_updates_list.html", context)


@superuser_required
def version_update(request):
    context = {}     
    if request.method == "POST":
        version = request.POST.get("version")
        release_date = request.POST.get("release_date")
        print(release_date)
        description = request.POST.get("description")            
        AppVersionUpdate.objects.create(version=version,release_date=release_date, description=description, created_by=request.user.username)
        return redirect("dashboard:version_update_list")
    return render(request, "dashboard/side/update/version_update.html", context)

## App version section ends

### Product section
@superuser_required
def add_product(request):
    context = {}    
    admin_user = get_object_or_404(User, id=request.user.id)
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
                        return render(request, 'dashboard/side/store/add_product_form.html')

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
                created_by=admin_user
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

            return redirect('dashboard:product_list')

        except Exception as e:
            print(f"Error: {str(e)}")
            messages.error(request, f"{str(e)}")
            return render(request, 'dashboard/side/store/add_product_form.html')
        
    context["categories"] = MerchandiseStoreCategory.objects.all().values("id", "name")
    context["events"] = Leagues.objects.all().values("id", "name")
    return render(request, 'dashboard/side/store/add_product_form.html', context)


from rest_framework import serializers
from django.db.models import Count

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

@superuser_required
def product_list(request):
    context = {}
    categories = MerchandiseStoreCategory.objects.all()
    search_text = request.GET.get("search_text")
    page_length = int(request.GET.get("page_length", 20))
    product_list = MerchandiseStoreProduct.objects.all()

    categories = sorted(
        categories,
        key=lambda c: (c.name.lower() == "others", c.name.lower())
    )
    search_text = request.GET.get("search_text")
    
    if search_text:
        product_list = product_list.filter(Q(name__icontains=search_text) | Q(description__icontains=search_text) | Q(specifications__icontains=search_text) | Q(category__name__icontains=search_text) | Q(leagues_for__name__icontains=search_text)).distinct()
    
    category_id = request.GET.get("category")
    print("Category id", category_id)

    if category_id:
        product_list = product_list.filter(category_id=category_id)

    # Step 4: Pagination
    page = request.GET.get("page", 1)
    paginator = Paginator(product_list, page_length)
    try:
        product_page = paginator.page(page)
    except:
        product_page = paginator.page(1)
    serialized_products = ProductListSerializer(product_page, many=True, context={'request': request}).data
    cart_products = CustomerMerchandiseStoreProductBuy.objects.filter(
        created_by=request.user,
        status='CART'
    ).values(
        'product', 'size', 'color'
    ).annotate(
        total_quantity=Count('id')
    )

    cart_products_count = cart_products.count()
    context.update({
        "product_list": serialized_products,
        "page_range": get_custom_pagination_range(product_page, paginator),
        "search_text": search_text,
        "page_length": str(page_length),
        "categories":categories,
        "cart_products_count":cart_products_count
    })
    return render(request, "dashboard/side/store/product_list.html", context)


@superuser_required
def view_product(request, product_id):
    product = get_object_or_404(MerchandiseStoreProduct, id=int(product_id))
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
    return render(request, 'dashboard/side/store/view_product.html', context)


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


@superuser_required
def edit_product(request, product_id):
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
                    return render(request, 'dashboard/side/store/edit_product_form.html')

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
        print(remove_ids) # Keep only numeric IDs
        if remove_ids:
            MerchandiseProductImages.objects.filter(id__in=remove_ids, product=product).delete()

        # Handle new product images
        for img_file in request.FILES.getlist("productImages"):
            MerchandiseProductImages.objects.create(product=product, image=img_file)

        messages.success(request, "Product updated successfully.")
        return redirect("dashboard:view_product", product_id=product.id)

    return render(request, 'dashboard/side/store/edit_product_form.html', context)


@superuser_required
def delete_product(request, product_id):
    context = {"message":""}
    product = get_object_or_404(MerchandiseStoreProduct, id=product_id)
    context["product"] = product
    if request.method == "POST":
        product.delete()
        return redirect(reverse("dashboard:product_list"))
    return render(request, "dashboard/side/store/delete_product.html", context)


from dateutil.relativedelta import relativedelta

@superuser_required
def my_received_orders(request):    
    filter_type = request.GET.get('filter_type')
    delivery_status = request.GET.get('status', 'pending')
    view_mode = request.GET.get("view", "my")
    page_length = int(request.GET.get("page_length", 20))
    search_text = request.GET.get('search_text')

    if view_mode == "all":
        orders = CustomerMerchandiseStoreProductBuy.objects.all()
    else:
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
    paginator = Paginator(orders_with_ratings, page_length)

    try:
        order_page = paginator.page(page)
    except:
        order_page = paginator.page(1)
    return render(request, 'dashboard/side/store/my_orders.html',
                   {'orders_with_ratings': order_page,
                    "page_range": get_custom_pagination_range(order_page, paginator),
                    "search_text": search_text,
                    "page_length": str(page_length),
                    "view_mode": view_mode,
                    'status_choices': ['ORDER PLACED', 'SHIPPED', 'DELIVERED'], 
                    })


@superuser_required
def my_placed_orders(request):
    filter_type = request.GET.get('filter_type')
    delivery_status = request.GET.get('status', 'pending')
    page_length = int(request.GET.get("page_length", 20))
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
                'items': [item],  # Optional: list of all matching entries
            }   
    page = request.GET.get("page", 1)   
    paginator = Paginator(list(grouped_cart.values()), page_length)

    try:
        order_page = paginator.page(page)
    except:
        order_page = paginator.page(1)
    return render(request, 'dashboard/side/store/my_placed_orders.html',
                   {'orders': order_page,
                    "page_range": get_custom_pagination_range(order_page, paginator),
                    "search_text": search_text,
                    "page_length": str(page_length)
                    }) 


@superuser_required
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
            return redirect(request.META.get("HTTP_REFERER", "dashboard:my_placed_orders"))
    

        except Exception as e:
            messages.error(request, "Invalid request.")
            return redirect("dashboard:my_placed_orders")
        
    messages.error(request, "Invalid request.")
    return redirect("dashboard:my_placed_orders")


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


@superuser_required
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
@superuser_required
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



@superuser_required
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

        if spec.available_product < quantity:
            return redirect("dashboard:view_product", pk=product_id)

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
        return redirect("dashboard:checkout_summary", order_id=order.id)

    except MerchandiseStoreProduct.DoesNotExist:
        return redirect("dashboard:product_list")
    except MerchandiseProductSpecification.DoesNotExist:
        return redirect("dashboard:product_list")
    

@superuser_required
def checkout_summary(request, order_id):
    try:
        order = CustomerMerchandiseStoreProductBuy.objects.select_related('product').get(id=order_id, created_by=request.user)

        context = {
            'order': order,
            'product': order.product,
            'image': MerchandiseProductImages.objects.filter(product=order.product).first()
        }
        return render(request, 'dashboard/side/store/checkout_summary.html', context)

    except CustomerMerchandiseStoreProductBuy.DoesNotExist:
        return redirect('dashboard:product_list')


@superuser_required
def wishlist(request):
    context = {}
    search_text = request.GET.get("search_text")
    page_length = int(request.GET.get("page_length", 20))
    wishlisted_products = MerchandiseStoreProduct.objects.filter(is_love=request.user)
    if search_text:
        wishlisted_products = wishlisted_products.filter(Q(name__icontains=search_text) | Q(description__icontains=search_text) | Q(specifications__icontains=search_text) | Q(category__name__icontains=search_text) | Q(leagues_for__name__icontains=search_text)).distinct()
    
    # Step 4: Pagination
    page = request.GET.get("page", 1)
    paginator = Paginator(wishlisted_products, page_length)
    try:
        product_page = paginator.page(page)
    except:
        product_page = paginator.page(1)
    serialized_products = ProductListSerializer(product_page, many=True, context={'request': request}).data
    context.update({
        "product_list": serialized_products,
        "page_range": get_custom_pagination_range(product_page, paginator),
        "search_text": search_text,
        "page_length": str(page_length)
    })
    return render(request, "dashboard/side/store/wishlist.html", context)

from collections import defaultdict
from django.db.models import Sum

@superuser_required
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
    return render(request, 'dashboard/side/store/cart.html', context)


@superuser_required
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
    return redirect('dashboard:cart')


@csrf_exempt
@superuser_required
def remove_cart_item(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            product_id = data.get('product_id')
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

            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request'})


@superuser_required
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


@superuser_required
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
            return redirect('dashboard:cart_payment_gateway')  # 👈 Redirects to the payment page

    return render(request, 'dashboard/side/store/select_address.html', {
        'addresses': addresses,
        'grand_total': request.session.get('cart_grand_total', 0),
        "MAP_API_KEY":settings.MAP_API_KEY
    })

@superuser_required
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
            return redirect('dashboard:buy_now_payment_gateway')  # 👈 Redirects to the payment page

    return render(request, 'dashboard/side/store/select_address_buy_now.html', {
        'addresses': addresses,
        'order_id': request.session.get('order_id', 0),
        "MAP_API_KEY":settings.MAP_API_KEY
    })


@superuser_required
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

@superuser_required
def cart_payment_gateway(request):
    total_amount = request.session.get('cart_grand_total', 0)
    return render(request, 'dashboard/side/store/cart_payment_gateway.html', {
        'total_amount': total_amount,
        'STRIPE_PUBLISHABLE_KEY': settings.STRIPE_PUBLIC_KEY
    })

@csrf_exempt
@superuser_required
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
                success_url = f"{domain}/admin/cart_payment_success/?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url = f"{domain}/admin/cart_payment_cancel/"
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
        print(event)
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


@superuser_required
def cart_payment_success(request):
    session_id = request.GET.get("session_id")
    if not session_id:
        return render(request, "dashboard/side/store/payment_cancel.html", {"error": "Invalid session."})

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
            return render(request, "dashboard/side/store/payment_success.html", {"amount": amount})
        else:
            return render(request, "dashboard/side/store/payment_cancel.html", {"error": "Payment not completed."})
    except stripe.error.StripeError as e:
        return render(request, "dashboard/side/store/payment_cancel.html", {"error": str(e)})


@superuser_required
def cart_payment_cancel(request):
    return render(request, "dashboard/side/store/payment_cancel.html", {"error": "Payment was cancelled."})


@superuser_required
def buy_now_payment_gateway(request):
    order_id = request.session.get('order_id', 0)
    order = CustomerMerchandiseStoreProductBuy.objects.filter(id=int(order_id)).first()
    total_amount = order.total_price
    print(order_id)
    return render(request, 'dashboard/side/store/buy_now_payment_gateway.html', {
        'total_amount': total_amount,
        'order_id': order.id,
        'STRIPE_PUBLISHABLE_KEY': settings.STRIPE_PUBLIC_KEY
    })

@csrf_exempt
@superuser_required
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
                success_url=f"{domain}/admin/buy_now_payment_success/?session_id={{CHECKOUT_SESSION_ID}}&order_id={order.id}",
                cancel_url=f"{domain}/admin/buy_now_payment_cancel/"
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


@superuser_required
def buy_now_payment_success(request):
    session_id = request.GET.get("session_id")
    order_id = request.GET.get("order_id")

    if not session_id or not order_id:
        return render(request, "dashboard/side/store/payment_cancel.html", {"error": "Missing session or order ID."})

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

            return render(request, "dashboard/side/store/payment_success.html", {"amount": amount})

        else:
            return render(request, "dashboard/side/store/payment_cancel.html", {"error": "Payment not completed."})

    except stripe.error.StripeError as e:
        return render(request, "dashboard/side/store/payment_cancel.html", {"error": str(e)})


@superuser_required
def buy_now_payment_cancel(request):
    return render(request, "dashboard/side/store/payment_cancel.html", {"error": "Payment was cancelled."})

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
### product section ends

### Notification section

@superuser_required
def send_universal_notification(request):
    context = {"message":""}
    if request.method == "POST":
        titel = request.POST.get("title")
        message = request.POST.get("message")
        if titel and message:
            notify_all_users(titel, message)
        else:
            context["message"] = "Title and message are required."
            return render(request, "dashboard/side/universal_notification.html", context)
        return redirect(reverse("dashboard:dashboard"))
    return render(request, "dashboard/side/notification/universal_notification.html", context)


from apps.chat.models import NotificationBox
import json
from django.http import JsonResponse

@superuser_required
def mark_notifications_as_read(request):
    """
    Marks notifications as read based on provided IDs.
    """
    if request.method == "POST":
        try:
            data = json.loads(request.body)  # ✅ Correct way to get JSON data
            notification_ids = data.get("unread_notification_ids", [])

            if not notification_ids:
                return JsonResponse({"error": "No notification IDs provided"}, status=400)

            # Update notifications where the ID is in the provided list and belongs to the user
            updated_count = NotificationBox.objects.filter(
                id__in=notification_ids, notify_for=request.user, is_read=False
            ).update(is_read=True)

            return JsonResponse({"success": True, "updated_count": updated_count}, status=200)

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON format"}, status=400)
    
    return JsonResponse({"error": "Invalid request method"}, status=405)



@csrf_exempt
def delete_notification(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            notification_id = data.get("notification_id")
            NotificationBox.objects.filter(id=notification_id).delete()
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})
## notification ends

#### club section

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

@superuser_required
def club_list(request, filter_type):
    filter_type = request.GET.get('filter_type', filter_type or "active")
    location = request.GET.get('location', None)
    search_text = request.GET.get('search_text', '') 
    page_length = int(request.GET.get("page_length", 20))  
    clubs = Club.objects.all()

    
    if search_text:
    # Filter clubs by keyword
        clubs = clubs.filter(
            Q(name__icontains=search_text) | Q(description__icontains=search_text)
        )
    if filter_type == "all":
        clubs = clubs
    elif filter_type == "active":
        clubs = clubs.filter(diactivate=False)
    elif filter_type == "disabled":
        clubs = clubs.filter(diactivate=True)
    else:
        clubs = clubs

    clubs_ = clubs    
    if location:
        ref_lat, ref_lon = get_lat_long(settings.MAP_API_KEY, location)
        if ref_lat is not None and ref_lon is not None:
            filtered_clubs = []
            for club in clubs:                    
                club_lat, club_long = float(club.latitude), float(club.longitude)
                if club_lat is not None and club_long is not None:
                    distance = haversine(ref_lat, ref_lon, club_lat, club_long)
                    if distance <= 100:  # radius in KM
                        filtered_clubs.append(club)
            clubs_ = filtered_clubs
        else:
            clubs_ = []              
    
    clubs_json = json.dumps(list(clubs_.values('id', 'name', 'location', 'latitude', 'longitude')))

    for club_ins in clubs_:
        
        find_image = ClubImage.objects.filter(club=club_ins)        
        if find_image:            
            club_ins.image = find_image.first().image.url
        else:
            club_ins.image = None

    page = request.GET.get("page", 1)
    paginator = Paginator(clubs_, page_length)
    try:
        club_page = paginator.page(page)
    except:
        club_page = paginator.page(1)

    context = {        
        "page_range": get_custom_pagination_range(club_page, paginator),
        "search_text": search_text,
        "page_length": str(page_length),
        "location": location,
        'clubs': club_page,
        'search_text': search_text,
        'location':location,
        "google_api_key": settings.MAP_API_KEY, 
        "clubs_json": clubs_json, 
        "filter_type":filter_type
        
    }
    return render(request, 'dashboard/side/clubs/club_list.html', context)


@superuser_required
def club_add(request):
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
        latitude, longitude = get_lat_long(settings.MAP_API_KEY, location)

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

        return redirect(reverse("dashboard:club_list", kwargs={"filter_type": "active"}))  # Redirect to a club list or another page

    return render(request, "dashboard/side/clubs/add_club.html")


@superuser_required
def edit_club(request, club_id):
    context = {}
    club = get_object_or_404(Club, id=int(club_id))
    club_images = ClubImage.objects.filter(club=club)
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
        latitude, longitude = get_lat_long(settings.MAP_API_KEY, location)
        
        club.name=name
        club.location=location
        club.latitude=latitude
        club.longitude=longitude
        club.open_time=open_time
        club.close_time=close_time
        club.contact=contact
        club.email=email
        club.is_vip=is_vip
        club.description=description
        club.join_amount=join_amount
        club.unit=unit 
        club.save()

        deleted_image_ids = request.POST.get("deleted_images", "")
        if deleted_image_ids:
            image_ids = [int(i) for i in deleted_image_ids.split(",") if i.isdigit()]
            ClubImage.objects.filter(id__in=image_ids, club=club).delete()

        # Save new images
        images = request.FILES.getlist("images")
        for image in images:
            ClubImage.objects.create(club=club, image=image)

        return redirect(reverse("dashboard:view_club", kwargs={"club_id": club.id}))
  
    
    context["club"] = club
    context["club_images"] = club_images
    return render(request, "dashboard/side/clubs/edit_club.html", context)


@superuser_required
def view_club(request, club_id):
    club = get_object_or_404(Club, id=int(club_id))
    club_paackages = ClubPackage.objects.filter(club=club)

    return render(request, 'dashboard/side/clubs/club_view.html', {
        'club': club, 
        'packages': club_paackages,         
    })


@superuser_required
def delete_club(request, club_id):
    club = get_object_or_404(Club, id=int(club_id))
    if request.method == "POST":
        if club.diactivate == False:
            club.diactivate = True
        else:
            club.diactivate = False
        club.save()
        return redirect(reverse("dashboard:club_list", kwargs={"filter_type": "active"}))
    return redirect(reverse("dashboard:view_club", kwargs={"club_id": club.id}))


## club section ends

## Court section

@superuser_required
def court_list(request):
    context = {}
    location = request.GET.get('location', None)
    search_text = request.GET.get('search_text', '') 
    page_length = int(request.GET.get("page_length", 20)) 
    courts = Courts.objects.all()

    if search_text:
        courts = courts.filter(Q(name__icontains=search_text) | Q(about__icontains=search_text))
    courts_ = courts
    if location:
        ref_lat, ref_lon = get_lat_long(settings.MAP_API_KEY, location)
        if ref_lat is not None and ref_lon is not None:
            filtered_courts = []
            for court in courts:                    
                court_lat, court_long = float(court.latitude), float(court.longitude)
                if court_lat is not None and court_long is not None:
                    distance = haversine(ref_lat, ref_lon, court_lat, court_long)
                    if distance <= 100:  # radius in KM
                        filtered_courts.append(court)
            courts_ = filtered_courts
        else:
            courts_ = []              
        
    courts_json = json.dumps([
        {
            "id": court.id,
            "name": court.name,
            "location": court.location,
            "latitude": float(court.latitude) if isinstance(court.latitude, Decimal) else court.latitude,
            "longitude": float(court.longitude) if isinstance(court.longitude, Decimal) else court.longitude,
        }
        for court in courts_
    ])
    for court_in in courts_:
        
        find_image = CourtImage.objects.filter(court=court_in)        
        if find_image:            
            court_in.image = find_image.first().image.url
        else:
            court_in.image = None
    
    page = request.GET.get("page", 1)
    paginator = Paginator(courts_, page_length)
    try:
        court_page = paginator.page(page)
    except:
        court_page = paginator.page(1)

    context = {        
        "page_range": get_custom_pagination_range(court_page, paginator),
        "search_text": search_text,
        "page_length": str(page_length),
        "location": location,
        'courts': court_page,
        'search_text': search_text,
        'location':location,
        "google_api_key": settings.MAP_API_KEY, 
        "courts_json": courts_json
        
    }
    
    return render(request, 'dashboard/side/courts/courts_list.html', context)


from decimal import Decimal, ROUND_HALF_UP
@superuser_required
def add_court(request):
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
        latitude, longitude = get_lat_long(settings.MAP_API_KEY, location)

        latitude = Decimal(str(latitude)).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
        longitude = Decimal(str(longitude)).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)

        court = Courts(
            name=name,
            location=location,
            latitude=latitude,
            longitude=longitude,
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

        return redirect("dashboard:court_list")  # Redirect to a court list or another page

    return render(request, "dashboard/side/courts/add_court.html")


@superuser_required
def view_court(request, court_id):
    court = get_object_or_404(Courts, id=int(court_id))
    return render(request, 'dashboard/side/courts/view_court.html', {'court':court})


@superuser_required
def edit_court(request, court_id):
    context = {}
    court = get_object_or_404(Courts, id=int(court_id))
    court_images = CourtImage.objects.filter(court=court)
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
        latitude, longitude = get_lat_long(settings.MAP_API_KEY, location)

        latitude = Decimal(str(latitude)).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
        longitude = Decimal(str(longitude)).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)

        court.name=name
        court.location=location
        court.latitude=latitude
        court.longitude=longitude
        court.open_time=open_time
        court.close_time=close_time
        court.price=price
        court.price_unit=price_unit
        court.offer_price=offer_price
        court.about=about
        court.owner_name=owner_name
        court.save()

        deleted_image_ids = request.POST.get("deleted_images", "")
        if deleted_image_ids:
            image_ids = [int(i) for i in deleted_image_ids.split(",") if i.isdigit()]
            CourtImage.objects.filter(id__in=image_ids, court=court).delete()

        images = request.FILES.getlist("images")
        for image in images:
            CourtImage.objects.create(court=court, image=image)

        return redirect(reverse("dashboard:view_court", kwargs={"court_id": court.id}))  # Redirect to a court list or another page
    context["court"] = court
    context["court_images"] = court_images
    return render(request, "dashboard/side/courts/edit_court.html", context)
    

@superuser_required
def delete_court(request, court_id):
    court = get_object_or_404(Courts, id=int(court_id))
    if request.method == "POST":
        court.delete()
        return redirect(reverse("dashboard:court_list"))
    return redirect(reverse("dashboard:view_court", kwargs={"court_id": court.id}))

### Court section ends

## wallet details for admin
@superuser_required
def wallet_details(request):
    start_date = request.GET.get("start_date", None)
    end_date = request.GET.get("end_date", None)
    page_length = request.GET.get("page_length", 10)
    page = request.GET.get("page", 1)  # Get the current page number from request
    
    wallet = Wallet.objects.filter(user=request.user)
    
    balance = 0.0
    transactions = WalletTransaction.objects.filter(Q(sender=request.user) | Q(reciver=request.user) | Q(admin_cost__isnull=False) & ~Q(admin_cost='0') & ~Q(admin_cost='0.00')).order_by("-created_at")
    if start_date and end_date:
        transactions = transactions.filter(created_at__date__gte=start_date, created_at__date__lte=end_date)
 
    # Pagination setup
    
    paginator = Paginator(transactions, page_length)  # 10 players per page

    try:
        transactions_page = paginator.page(page)
    except:
        transactions_page = paginator.page(1)

    if wallet.exists():
        balance = wallet.first().balance

    return render(
        request,
        "dashboard/side/wallet.html",
        {
            "wallet_balance": balance,
            "transactions": transactions_page, 
            "page_range": get_custom_pagination_range(transactions_page, paginator),
            "page_length": page_length
        },
    )


@superuser_required
def get_transaction_details(request, transaction_id):
    transaction = get_object_or_404(WalletTransaction, id=int(transaction_id))
    data = {
        "success": True,
        "transaction": {
            "transaction_id": transaction.transaction_id,
            "transaction_type": transaction.transaction_type,
            'sender':transaction.sender.username if transaction.sender else None,
            'receiver':transaction.reciver.username if transaction.reciver else None,
            "amount": float(transaction.amount),
            'receiver_cost': float(transaction.reciver_cost) if transaction.reciver_cost else 0,
            "admin_cost": float(transaction.admin_cost) if transaction.admin_cost else 0,
            "description": transaction.description,
            "created_at": transaction.created_at.strftime("%d %b %Y, %I:%M %p"),
        }
    }
    return JsonResponse(data)

## wallet ends

## Open Play section

# @superuser_required
# def create_open_play(request):
#     context = {"message":""}
#     admin_user = User.objects.filter(id=request.user.id).first()
#     teams = Team.objects.all()
#     context["teams"] = teams
#     if request.method == "POST":
#         player_type = request.POST.get("player_type")
#         start_date = request.POST.get("t_start_date")
#         location = request.POST.get("location")
#         team_type = "Open-team"
#         description = request.POST.get("description")
#         court = request.POST.get("court")
#         points = request.POST.get("points")
#         sets = request.POST.get("set")
#         team_id_list = request.POST.getlist("team_ids")
#         play_type = request.POST.get("play_type")
#         max_number_team = 2
#         registration_fee = 0
#         league_type = "Open to all"
        

#         if len(team_id_list) != 2:
#             context["message"] = "Need to select 2 teams."
#             return render(request, "dashboard/side/create_open_play_form.html",context)
        
#         team_1_id = team_id_list[0]
#         team_2_id = team_id_list[1]
#         team1_players = list(Player.objects.filter(team__id=team_1_id).values_list("id", flat=True))
#         team2_players = list(Player.objects.filter(team__id=team_2_id).values_list("id", flat=True))
#         for player_id in team1_players:
#             if player_id in team2_players:
#                 context["message"] = "Need to select One person team."
#                 return render(request, "dashboard/side/create_open_play_form.html",context)
        
#         if player_type == "One Person Team":
#             for team_id in team_id_list:
#                 team = Team.objects.filter(id=team_id).first()
#                 if team.team_person != "One Person Team":
#                     context["message"] = "Need to select One person team."
#                     return render(request, "dashboard/side/create_open_play_form.html",context)
                
#         if player_type == "Two Person Team":
#             for team_id in team_id_list:
#                 team = Team.objects.filter(id=team_id).first()
#                 if team.team_person != "Two Person Team":
#                     context["message"] = "Need to select Two person team."
#                     return render(request, "dashboard/side/create_open_play_form.html",context)
#         team_names = {}
#         counter = 0
#         for team in team_id_list:
#             counter += 1
#             team_instance = Team.objects.filter(id=team).first()
#             team_names[f'team{counter}_name'] = team_instance.name
#         tournament_name = f"{team_names['team1_name']} VS {team_names['team2_name']}"
#         check_leagues = LeaguesTeamType.objects.filter(name=team_type)
#         check_person = LeaguesPesrsonType.objects.filter(name=player_type)
#         full_address = location
#         api_key = settings.MAP_API_KEY
#         state, country, pincode, latitude, longitude = get_address_details(full_address, api_key)
#         if latitude is None:
#             latitude = 38.908683
#         if longitude is None:
#             longitude = -76.937352
#         obj = GenerateKey()
#         secret_key = obj.gen_leagues_key()

#         save_leagues = Leagues(
#             secret_key=secret_key,
#             name=tournament_name,
#             leagues_start_date=start_date,
#             location=location,
#             created_by_id=admin_user.id,
#             street=state,
#             city="Extract city from full_address",
#             state=state,
#             postal_code=pincode,
#             country=country,
#             max_number_team=max_number_team,
#             play_type=play_type,
#             registration_fee=registration_fee,
#             description=description,
#             league_type=league_type
#         )

#         save_leagues.save()

#         save_leagues.latitude = latitude
#         save_leagues.longitude = longitude
#         save_leagues.save()
#         if check_leagues.exists() and check_person.exists():
#             check_leagues_id = check_leagues.first().id
#             check_person_id = check_person.first().id
#             save_leagues.team_type_id = check_leagues_id
#             save_leagues.team_person_id = check_person_id
#             save_leagues.save()

#         for team in team_id_list:
#             team_instance = Team.objects.filter(id=team).first()
#             save_leagues.registered_team.add(team_instance)
#         if not court:
#                 court = 0
#         else:
#             court = int(court)

#         if not sets:
#             sets = 0
#         else:
#             sets = int(sets)

#         if not points:
#             points = 0
#         else:
#             points = int(points)

#         play_type_data = [{"name": "Round Robin", "number_of_courts": 0, "sets": 0, "point": 0},
#                             {"name": "Elimination", "number_of_courts": 0, "sets": 0, "point": 0},
#                             {"name": "Final", "number_of_courts": court, "sets": sets, "point": points}]
#         for j in play_type_data:            
#             j["is_show"] = True
#         LeaguesPlayType.objects.create(type_name=save_leagues.play_type, league_for=save_leagues,
#                                         data=play_type_data)
#         #notification           
#         for team_id in team_id_list:
#             team_instance = Team.objects.filter(id=team_id).first()
#             titel = "Open play created."
#             notify_message = f"Hey player! Your team {team_instance.name} has been added for an open play - {tournament_name}"
#             players = Player.objects.filter(team=team_instance)
#             for player in players:
#                 notify_edited_player(player.player.id, titel, notify_message)
#         return redirect("/admin/tournamnet_list/all")
#     return render(request, "dashboard/side/create_open_play_form.html",context)


from django.db import transaction
import os, math
from django.contrib import messages
@superuser_required
def create_open_play(request):
    admin_user = User.objects.filter(id=request.user.id).first()
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
            return render(request, 'dashboard/side/create_open_play_form.html', {
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
                    return render(request, 'dashborad/side/create_open_play_form.html', {
                        'MAP_API_KEY': settings.MAP_API_KEY,
                        'form_data': form_data,
                        'errors': {'team_type': 'Invalid team type selected'}
                    })
                team_person = LeaguesPesrsonType.objects.filter(name=form_data['play_type']).first()
                if not team_person:
                    messages.error(request, f"Invalid open play type: {form_data['play_type']}")
                    return render(request, 'dashboard/side/create_open_play_form.html', {
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
                    created_by=admin_user,
                    league_type='Open to all',
                )
                open_play_event.save()

                play_type_data = [
                    {"name": "Round Robin", "sets": "0", "point": "0", "is_show": False, "number_of_courts": "0"}, 
                    {"name": "Elimination", "sets": "0", "point": "0", "is_show": False, "number_of_courts": "0"}, 
                    {"name": "Final", "sets": form_data['sets'], "point": form_data['points'], "is_show": True, "number_of_courts": form_data['courts']}
                ]

                # Store play type
                try:
                    LeaguesPlayType.objects.create(
                        type_name=form_data['open_play_type'],
                        league_for=open_play_event,
                        data=play_type_data
                    )
                except Exception as e:
                    messages.error(request, f"Failed to create play type: {str(e)}")

                # Invite players
                title = "Created Open Play event invitation"
                for player_uuid in form_data['players']:
                    try:
                        player = User.objects.get(uuid=player_uuid)
                        notify_message = f"{admin_user.first_name} sent you an invitation for OpenPlay, Please show your interest"
                        OpenPlayInvitation.objects.create(
                            user=player,
                            event=open_play_event,
                            invited_by = admin_user,
                            status='Pending'
                        )
                        notify_edited_player(player.id, title, notify_message)
                    except User.DoesNotExist:
                        messages.warning(request, f"Player with UUID {player_uuid} not found")
                        continue

                messages.success(request, "Open Play event created successfully!")
                return redirect(reverse('dashboard:open_play_list',  kwargs={'filter_by': 'all'}))

        except Exception as e:
            messages.error(request, f"Failed to create Open Play event: {str(e)}")
            return render(request, 'dashboard/side/create_open_play_form.html', {
                'MAP_API_KEY': settings.MAP_API_KEY,
                'form_data': form_data,
                'errors': {'general': str(e)}
            })

    # For GET requests
    return render(request, 'dashboard/side/create_open_play_form.html', {
        'MAP_API_KEY': settings.MAP_API_KEY,
        'form_data': {}
    })


def search_players(request):
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
        radius = float(radius)
        filtered_players = []
        for player in players:
            if player.latitude not in [None, "null", "", " "] and player.longitude not in [None, "null", "", " "]:
                distance = haversine(float(latitude), float(longitude), float(player.latitude), float(player.longitude))
                
                if distance <= radius:
                    filtered_players.append(player)
        players = filtered_players
        

    if min_rank:
        try:
            players = [p for p in players if p.rank is not None and p.rank >= float(min_rank)]
        except ValueError:
            pass  # Invalid min_rank, skip filter

    if max_rank:
        try:
            players = [p for p in players if p.rank is not None and float(p.rank) <= float(max_rank)]
        except ValueError:
            pass  # Invalid max_rank, skip filter

    player_data = [
        {
            "id": player.id,
            "uuid": str(player.uuid),
            "name": f"{player.first_name} {player.last_name}",
            "image": player.image.url if player.image and player.image.url not in ["null", None, "", " "] else "https://static.thenounproject.com/png/3918329-200.png",
            "rank": float(player.rank) if player.rank else None,
            "get_full_name": f"{player.first_name} {player.last_name}"
        }
        for player in players
    ]

    return JsonResponse({"players": player_data})


@superuser_required
def open_play_list(request, filter_by):
    context = {}
    filter_by = request.GET.get('filter_by')
    search_text = request.GET.get("search_text")
    page_length = int(request.GET.get("page_length", 20))
    location = request.GET.get("location")

    team_type = "Open-team"
    team_type_ins = get_object_or_404(LeaguesTeamType, name=team_type)
    open_plays = Leagues.objects.filter(team_type=team_type_ins).order_by('-created_at')

    if search_text:
        open_plays = open_plays.filter(Q(name__icontains=search_text) | Q(description__icontains=search_text))

    today_date = datetime.now().date()

    # Filter leagues based on filter_by
    if filter_by == "all":
        open_plays = open_plays
    elif filter_by == "ongoing":
        open_plays = open_plays.filter(leagues_start_date__date__gte=today_date)
    elif filter_by == "past":
        open_plays = open_plays.filter(leagues_start_date__date__lte=today_date)

    open_play_list = open_plays.annotate(
            registered_team_count=Count('registered_team')
        ).values('id', 'description', 'uuid', 'secret_key', 'name', 'location', 'leagues_start_date', 
                                 'leagues_end_date', 'registration_start_date', 'registration_end_date', 
                                 'team_type__name', 'team_person__name', 'street', 'city', 'state', 'postal_code', 
                                 'country', 'complete_address', 'latitude', 'longitude', 'image', 'others_fees', 
                                 'league_type', 'registration_fee', 'created_at', 'max_number_team', 'registered_team_count')
    
    if location:
        ref_lat, ref_lon = get_lat_long(settings.MAP_API_KEY, location)
        if ref_lat is not None and ref_lon is not None:
            filtered_open_plays = []
            for data in open_play_list:
                if data['latitude'] not in [0, "", None, "null"] and data["longitude"] not in [0, "", None, "null"]:
                    play_lat, play_long = float(data['latitude']), float(data['longitude'])
                    
                    distance = haversine(ref_lat, ref_lon, play_lat, play_long)
                    if distance <= 100:  # radius in KM
                        filtered_open_plays.append(data)
            open_play_list = filtered_open_plays
        else:
            open_play_list = []

    for league in open_play_list:
        image_path = league.get("image")
        if image_path and image_path.lower() != 'null':
            if image_path.startswith("/"):
                league["image_url"] = request.build_absolute_uri(image_path)
            else:
                league["image_url"] = request.build_absolute_uri(settings.MEDIA_URL + image_path)
        else:
            league["image_url"] = None
    # Pagination
   
    page = request.GET.get('page')
    paginator = Paginator(open_play_list, page_length)
    try:
        page_obj = paginator.page(page)
    except:
        page_obj = paginator.page(1)
   
    context.update({
            "open_play_data": page_obj,
            "page_range": get_custom_pagination_range(page_obj, paginator),
            "search_text": search_text,
            "page_length": str(page_length),
            "location": location,
            'filter_by':filter_by
        })
    return render(request, "dashboard/side/open_play_list.html", context)


@superuser_required
def view_open_play(request, tour_id):
    context = {
        "league_details": [],
        "matches":[],
        "teams":[],
        "message":None
    }
    today = timezone.now()
    try:      
        League_details = Leagues.objects.filter(id=tour_id).first()
        context["league_details"] = League_details
        if League_details.leagues_start_date > today:
            context["is_unregister"] = True
        else:
            context["is_unregister"] = False
        
        
        if League_details.leagues_start_date:
            context["is_join"] = League_details.leagues_start_date.date() >= today.date()
        else:
            context["is_join"] = False
        have_score = TournamentSetsResult.objects.filter(tournament__leagues = League_details)
        if have_score:
            context["is_edit_match"] = False
        else:
            context["is_edit_match"] = True
        if League_details.registered_team:
            context["teams"] = League_details.registered_team.all()
        matches = Tournament.objects.filter(leagues=League_details).values().order_by('id')
        for mtch in matches:
            mtch["result"] = TournamentSetsResult.objects.filter(tournament=mtch["id"])
            if mtch["team1_id"]:
                mtch["team1"] = Team.objects.filter(id=mtch["team1_id"]).first().name
                mtch["team1_image"] = Team.objects.filter(id=mtch["team1_id"]).first().team_image
            else:
                mtch["team1"] = None
                mtch["team1_image"] = None

            if mtch["team2_id"]:
                mtch["team2"] = Team.objects.filter(id=mtch["team2_id"]).first().name
                mtch["team2_image"] = Team.objects.filter(id=mtch["team2_id"]).first().team_image
            else:
                mtch["team2"] = None
                mtch["team2_image"] = None

            if mtch["winner_team_id"]:
                mtch["winner_team"] = Team.objects.filter(id=mtch["winner_team_id"]).first().name
                mtch["winner_team_image"] = Team.objects.filter(id=mtch["winner_team_id"]).first().team_image
            else:
                mtch["winner_team"] = None
                mtch["winner_team_image"] = None

            if mtch["loser_team_id"]:
                mtch["loser_team"] = Team.objects.filter(id=mtch["loser_team_id"]).first().name
                mtch["loser_team_image"] = Team.objects.filter(id=mtch["loser_team_id"]).first().team_image
            else:
                mtch["loser_team"] = None
                mtch["loser_team_image"] = None
        context["matches"] = matches
    except Exception as e:
        context["message"] = str(e)
    
    play_type_details = LeaguesPlayType.objects.filter(league_for=League_details)
    if play_type_details:
        play_type_details = play_type_details.first().data
    else:
        play_type_details = [
                        {"name": "Round Robin", "number_of_courts": 0, "sets": 0, "point": 0},
                        {"name": "Elimination", "number_of_courts": 0, "sets": 0, "point": 0},
                        {"name": "Final", "number_of_courts": 0, "sets": 0, "point": 0}
                        ]
    check_data = check_data_structure(play_type_details)
    context["play_details_update"] = check_data
    return render(request, "dashboard/side/open_play_details.html",context)


@superuser_required
def edit_open_play(request, tour_id):
    context = {}
    league_details = Leagues.objects.get(id=tour_id)
    # try:
        # Get the league details or raise an error if it doesn't exist
    if request.method == "POST":
        # Process the POST request and update the league details
        league_details.name = request.POST.get("tournament_name", league_details.name)
        league_details.leagues_start_date = request.POST.get("league_start_date", league_details.leagues_start_date)
        league_details.leagues_end_date = request.POST.get("league_end_date", league_details.leagues_end_date)
        league_details.registration_start_date = request.POST.get("registration_start_date", league_details.registration_start_date)
        league_details.registration_end_date = request.POST.get("registration_end_date", league_details.registration_end_date)
        league_details.max_number_team = request.POST.get("max_join_team", league_details.max_number_team)
        league_details.registration_fee = request.POST.get("registration_fee", league_details.registration_fee)
        league_details.description = request.POST.get("description", league_details.description)
        league_details.location = request.POST.get("location", league_details.location)
        
        # Handle many-to-many relationship with teams (Join Team)
        selected_teams = request.POST.getlist("join_team")
        league_details.registered_team.set(selected_teams)

        # Handle other fees, if any
        other_fees_topic = request.POST.getlist("other_fees_topic[]")
        other_fees = request.POST.getlist("other_fees[]")
        other_fees_dict = dict(zip(other_fees_topic, other_fees))
        league_details.others_fees = other_fees_dict
        if "image" in request.FILES:
            league_details.image = request.FILES["image"]

        # Handle Organizer Selection
        organizer_ids = request.POST.getlist("organizer")  # Get multiple selected users
        if organizer_ids:
            league_details.add_organizer.set(organizer_ids)  # Directly set the ManyToMany field
        else:
            league_details.add_organizer.clear()

        cancellation_days = request.POST.getlist("cancellation_days[]")
        refund_percentages = request.POST.getlist("refund_percentage[]")

        # Clear existing policies
        LeaguesCancellationPolicy.objects.filter(league=league_details).delete()

        # Save new policies
        for day, refund in zip(cancellation_days, refund_percentages):
            if day and refund:
                LeaguesCancellationPolicy.objects.create(
                    league=league_details,
                    within_day=int(day),
                    refund_percentage=(float(refund))
                )

        league_details.save()


        courts_1 = request.POST.get("courts_1", 0)
        sets_1 = request.POST.get("sets_1", 0)
        points_1 = request.POST.get("points_1", 0)

        courts_2 = request.POST.get("courts_2", 0)
        sets_2 = request.POST.get("sets_2", 0)
        points_2 = request.POST.get("points_2", 0)

        courts_3 = request.POST.get("courts_3", 0)
        sets_3 = request.POST.get("sets_3", 0)
        points_3 = request.POST.get("points_3", 0)

        play_details = LeaguesPlayType.objects.filter(league_for=league_details).first()
        tournament_play_type = league_details.play_type
        data_ = [{"name": "Round Robin", "number_of_courts": courts_1, "sets": sets_1, "point": points_1},
                {"name": "Elimination", "number_of_courts": courts_2, "sets": sets_2, "point": points_2},
                {"name": "Final", "number_of_courts": courts_3, "sets": sets_3, "point": points_3}]
        # print(data_, "data")
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
        # print("hit", data_)
        play_details.data = data_
        play_details.save()
        return redirect(reverse('dashboard:view_open_play', kwargs={"tour_id":tour_id}))


    tournament_play_type = league_details.play_type
    play_type_details = LeaguesPlayType.objects.filter(league_for=league_details)
    cancelation_policy = LeaguesCancellationPolicy.objects.filter(league=league_details)
    if play_type_details:
        play_type_details = play_type_details.first().data
        
    else:
        play_type_details = [
                    {"name": "Round Robin", "number_of_courts": 0, "sets": 0, "point": 0},
                    {"name": "Elimination", "number_of_courts": 0, "sets": 0, "point": 0},
                    {"name": "Final", "number_of_courts": 0, "sets": 0, "point": 0}
                    ]
    for se in play_type_details:
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
    # Initialize context dictionary
    context = {
        "league_details": Leagues.objects.get(id=tour_id),
        "teams": Team.objects.all(),
        "play_type_details": play_type_details,
        "policies": cancelation_policy,
    }
    check_data = check_data_structure(play_type_details)
    context["play_details_update"] = check_data
    users = User.objects.all()  # Fetch all users
    context["users"] = users
    # print(context)
    return render(request, "dashboard/side/edit_open_play.html", context)

    # except Leagues.DoesNotExist:
    #     # If the league doesn't exist, raise a 404 error
    #     raise Http404("Tournament not found.")
    # except Exception as e:
    #     # Log or handle other exceptions
    #     context["message"] = str(e)
    #     print(context)
    #     return render(request, "dashboard/side/edit_tournamnet.html", context)
    

@superuser_required
def edit_matches_open_play(request, tour_id):
    
    league_details = Leagues.objects.get(id=tour_id)
    
    # Initialize context dictionary
    context = {
        "matches": Tournament.objects.filter(leagues=league_details), 
        "league_name": league_details.name
    }
    
    return render(request, "dashboard/side/edit_matches_open_play.html", context)


@csrf_exempt
@superuser_required
def update_match_order_open_play(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            match_order = data.get('matchOrder', [])
            for index, match_id in enumerate(match_order):
                Tournament.objects.filter(id=match_id).update(match_number=index + 1)
            return JsonResponse({"success": True})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})
    return JsonResponse({"success": False, "error": "Invalid request"})


@superuser_required
def update_match_open_play(request, set_score_id):
    match = get_object_or_404(TournamentSetsResult, id=set_score_id)
    if request.method == 'POST':
        
        # tournament_id = request.POST.get('tournament_id')
        set_number = request.POST.get(f'set_num_{match.id}')
        team1_score = request.POST.get(f't1_score_{match.id}')
        team2_score = request.POST.get(f't2_score_{match.id}')
        # status = request.POST.get(f'status_{match.id}')

        if set_number and team1_score and team2_score:
            match.set_number = int(set_number)
            match.team1_point = int(team1_score)
            match.team2_point = int(team2_score)
            match.is_completed = True
            match.save()
        return redirect(reverse("dashboard:view_open_play", kwargs={"tour_id":match.tournament.leagues.id}))
    
    return redirect(reverse("dashboard:view_open_play", kwargs={"tour_id":match.tournament.leagues.id}))


@superuser_required
def start_open_play(request, tour_id):
    check_tour = Leagues.objects.filter(id=tour_id).first()
    tour_create_by = check_tour.created_by
    max_number_teams = check_tour.registered_team.count()
    check_tour.max_number_team = max_number_teams
    check_tour.save()
    host = request.get_host()
    current_site = f"{protocol}://{host}"
    url = f"{current_site}/team/22fef865dab2109505b61d85df50c5126e24f0c0a10990f2670c179fb841bfd2/"
    # print(url)
    payload = {
        'user_uuid': str(tour_create_by.uuid),
        'user_secret_key': str(tour_create_by.secret_key),
        'league_uuid': str(check_tour.uuid),
        'league_secret_key': str(check_tour.secret_key)
    }
    try:
        response = requests.post(url, json=payload)
        response_data = response.json()
        if response.status_code == 200:
            messages.success(request, response_data.get("message", "Tournament started successfully."))
        else:
            messages.error(request, response_data.get("message", "Failed to start tournament."))
    except Exception as e:
        messages.error(request, f"API error: {str(e)}")
    return redirect('dashboard:view_open_play', tour_id=tour_id)


@superuser_required
def submit_score_open_play(request, tour_id):
    context = {"dis_message":""}
    tournament = Leagues.objects.filter(id=tour_id).first()
    if request.method == "POST":
        match_id = request.POST.get("match_id")
        get_team1_score = request.POST.getlist("team1_score")
        team1_score = []
        for i in get_team1_score:
            if i == "" or not i:
                pass
            else:
                team1_score.append(int(i))

        get_team2_score = request.POST.getlist("team2_score")
        team2_score = []
        for i in get_team2_score:
            if i == "" or not i:
                pass
            else:
                team2_score.append(int(i))
        match = Tournament.objects.filter(id=match_id).first()
        set_number = match.set_number
        print(match_id, team1_score, team2_score, set_number)
        if int(set_number) == len(team1_score):
            te1_win=[]
            te2_win=[]
            for up_ in range(len(team1_score)):
                set_num = up_ + 1
                team1_point = team1_score[up_]
                team2_point = team2_score[up_]
                if int(team1_point) >= int(team2_point):
                    winner = match.team1
                    te1_win.append(True)
                    te2_win.append(False)
                else:
                    te1_win.append(False)
                    te2_win.append(True)
                    winner = match.team2
                match_result = TournamentSetsResult.objects.filter(tournament=match, set_number=set_num)
                if match_result.exists():
                    match_result.update(team1_point=team1_point, team2_point=team2_point, is_completed=True,win_team=winner)
                else:
                    TournamentSetsResult.objects.create(tournament=match, set_number=set_num, team1_point=team1_point, team2_point=team2_point, is_completed=True,win_team=winner)
            te1_wins = sum(1 for result in te1_win if result)
            te2_wins = sum(1 for result in te2_win if result)
            is_drow = False
            # print(te1_wins,te2_wins,is_drow)
            if te1_wins > te2_wins:
                winner = match.team1
                looser = match.team2
            elif te2_wins > te1_wins:
                winner = match.team2
                looser = match.team1
            else:
                winner = None
                looser = None
                is_drow = True
            match.winner_team = winner
            match.loser_team = looser
            if is_drow is True:
                match.is_drow = True
                match.winner_team_score = 1
                match.loser_team_score = 1
            else:
                match.winner_team_score = 3
                match.loser_team_score = 0
            match.is_completed = True
            match.save()
            title = "Match score update"
            if winner is not None and looser is not None:
                message = f"Wow, you have won the match {match.match_number}, the scores are approved"
                message2 = f"Sorry, you have lost the match {match.match_number}, the scores are approved"
                
                winner_player = Player.objects.filter(team__id=winner.id)
                if winner_player.exists():
                    for pl in winner_player:
                        user_id = pl.player.id
                        notify_edited_player(user_id, title, message)
                looser_player = Player.objects.filter(team__id=looser.id)
                
                if looser_player.exists():
                    for pl in looser_player:
                        user_id = pl.player.id
                        notify_edited_player(user_id, title, message2)
            else:
                message = f"The match {match.match_number} was drawn, the scores are approved"
                team_1_ins = match.team1
                team_2_ins = match.team2
                team_one_player_list = Player.objects.filter(team__id = team_1_ins.id)
                team_two_player_list = Player.objects.filter(team__id = team_2_ins.id)
                for pl1 in team_one_player_list:
                    user_id = pl1.player.id
                    notify_edited_player(user_id, title, message) 
                for pl2 in team_two_player_list:
                    user_id = pl2.player.id
                    notify_edited_player(user_id, title, message)
        else:
            for up_ in range(len(team1_score)):
                set_num = up_ + 1
                team1_point = team1_score[up_]
                team2_point = team2_score[up_]
                if int(team1_point) >= int(team2_point):
                    winner = match.team1
                else:
                    winner = match.team2
                match_result = TournamentSetsResult.objects.filter(tournament=match, set_number=set_num)
                if match_result.exists():
                    match_result.update(team1_point=team1_point, team2_point=team2_point)
                else:
                    TournamentSetsResult.objects.create(tournament=match, set_number=set_num, team1_point=team1_point, team2_point=team2_point)
        return redirect(reverse("dashboard:view_open_play", kwargs={"tour_id":tour_id}))
    
    return redirect(reverse("dashboard:view_open_play", kwargs={"tour_id":tour_id}))


@superuser_required
def delete_open_play(request, tour_id):
    print("call")
    tournament = get_object_or_404(Leagues, id=tour_id)
    TournamentSetsResult.objects.filter(tournament__leagues=tournament).delete()
    Tournament.objects.filter(leagues=tournament).delete()
    RoundRobinGroup.objects.filter(league_for=tournament).delete()
    LeaguesPlayType.objects.filter(league_for=tournament).delete()
    LeaguesCancellationPolicy.objects.filter(league=tournament).delete()
    SaveLeagues.objects.filter(ch_league=tournament).delete()

    tournament.delete()
    
    return redirect("/admin/open_play_list/all")
        
    

#### user section not needed
@superuser_required
def create_user(request):
    admin_user = User.objects.get(id=request.user.id)
    context = {"message": ""}
    rank_values = [i/4 for i in range(4,21)]
    context["rank_values"] = rank_values
    if request.method == 'POST':
        email = request.POST.get('email')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')        
        phone = request.POST.get('phone')
        rank = request.POST.get('rank')
        if not rank or rank == 0:              
            rank = 1
        gender = request.POST.get('gender')
        responsibilities = request.POST.getlist('responsibilities')
        image = request.FILES.get('image')  
        
        if not gender or gender == "":
            gender = "Male"

        if not email or not first_name:
            context["message"] = "Email, first name is required."
            return render(request, 'dashboard/side/user/create_user_form.html', context)
        
        elif email == "" or first_name == "":
            # return HttpResponse("Email, first nzme,  password and confirm password is required.")
            context["message"] = "Email, first name is required."
            return render(request, 'dashboard/side/user/create_user_form.html', context)
        else:
            check_user = User.objects.filter(email=email,username=email).values('id')            
            if check_user.exists():
                # return HttpResponse("User already exists.")
                context["message"] = "User already exists."
                return render(request, 'dashboard/side/user/create_user_form.html', context)
            else:
                obj = GenerateKey()
                obj2 = GenerateKey()
                generated_otp = obj2.generated_otp()
                secret_key = obj.gen_user_key()
                six_digit_number = str(random.randint(100000, 999999))
                raw_password = six_digit_number
                hash_password = make_password(six_digit_number)
                check_role = Role.objects.filter(role='User')
                if check_role.exists():
                    save_user = User(secret_key=secret_key,email=email,username=email,first_name=first_name,last_name=last_name,rank=rank,phone=phone,
                                        role_id=check_role.first().id,password=hash_password,password_raw=raw_password,generated_otp=generated_otp,gender=gender,is_player=True,is_verified=True)
                    save_user.image=image  
                    save_user.save()
                    if "is_admin" in responsibilities:
                        save_user.is_admin= True
                        save_user.save()     
                    if "is_organizer" in responsibilities:
                        save_user.is_organizer = True
                        save_user.save()
                    if "is_sponsor" in responsibilities:
                        save_user.is_sponsor = True
                        role = Role.objects.filter(role="sponsor").first()
                        save_user.role = role
                        save_user.is_player = False
                        save_user.save()
                        check_player = Player.objects.filter(player_email=save_user.email)
                        if check_player.exists():
                            player = check_player.first()
                            player.delete()
                        sponsor_details = IsSponsorDetails.objects.create(secret_key=secret_key, sponsor=save_user,sponsor_added_by=admin_user)
                        current_site = f"https://pickleit.app"
                        email = save_user.email
                        send_type = "send"
                        send_email_for_invite_sponsor(current_site, email, league="", send_type=send_type)
                        return redirect(reverse('dashboard:user_list', kwargs={'filter_by': "All"}))
                    if "is_ambassador" in responsibilities:
                        save_user.is_ambassador = True
                        save_user.save()
                        ambassador_details = AmbassadorsDetails.objects.create(ambassador=save_user)
                    
                    #add as a player
                    obj = GenerateKey()
                    secret_key = obj.gen_player_key()
                    save_player = Player(secret_key=secret_key,player_first_name=first_name,player_last_name=last_name,player_phone_number=phone,player_ranking=rank,
                                player_full_name=f"{first_name} {last_name}",player_email=email,created_by=admin_user)
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
                    app_name = "PICKLEit"
                    login_link = "#"
                    password = save_user.password_raw
                    send_email_this_user = send_email_for_invite_user(first_name, email, app_name, login_link, password)
                    return redirect(reverse('dashboard:user_list', kwargs={'filter_by': "All"}))
                else:
                    # return HttpResponse("Role does not exist.")
                    context["message"] = "Role does not exist."
                    return render(request, 'dashboard/side/user/create_user_form.html', context)
            
    else:
        return render(request, 'dashboard/side/user/create_user_form.html', context)


@superuser_required    
def user_list(request, filter_by):
    filter_by = request.GET.get('filter_by')
    user_list = User.objects.order_by('-is_verified').values("id","first_name","last_name","email","username","phone","user_birthday","gender",
                                 "rank","street","city","state","country","postal_code","fb_link","twitter_link","youtube_link","tictok_link",
                                 "instagram_link","is_player","is_organizer","is_sponsor","is_ambassador","is_verified")
    
    for user in user_list:
        if user["rank"] == "0" or user["rank"] in [0,"","null",None]:
            user["rank"] = 1
    if filter_by == "all":
        user_list = user_list.filter()
    if filter_by == "player":
        user_list = user_list.filter(is_player=True)
    if filter_by == "organizer":
        user_list = user_list.filter(is_organizer=True)
    if filter_by == "sponsor":
        user_list = user_list.filter(is_sponsor=True)
    if filter_by == "ambassador":
        user_list = user_list.filter(is_ambassador=True)
    
    context = {'user_list':user_list, "message":"", "filter_by":filter_by}
    return render(request, "dashboard/side/user/user_list.html", context)


@superuser_required
def view_user(request, user_id):
    context = {"message":""}
    user = get_object_or_404(User, id=user_id)
    if user.is_ambassador:
        context["posts"] = AmbassadorsPost.objects.filter(created_by=user).values()
    context["user"] = user 
    return render(request, "dashboard/side/user/view_user.html", context)


@superuser_required
def edit_user(request, user_id):
    admin_user = User.objects.get(id=request.user.id)
    user = get_object_or_404(User, id=user_id)
    context = {"user":user, "message":""}
    if request.method == 'POST':        
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')        
        phone = request.POST.get('phone')        
        user_birthday = request.POST.get('user_birthday')
        if user_birthday and user_birthday != "" :
                # mm/dd/yy
            user_birthday_date = datetime.strptime(user_birthday, '%m/%d/%Y').strftime('%Y-%m-%d')
        else:
            user_birthday_date = None        
        rank = request.POST.get('rank')
        if not rank or rank == 0:              
            rank = 1
        gender = request.POST.get('gender')
        if 'image' in request.FILES:
            user.image = request.FILES.get('image')
        responsibilities = request.POST.getlist('responsibilities')
        is_verified = request.POST.get("is_verified")
        
        user.first_name = first_name
        user.last_name = last_name
        user.phone = phone
        user.gender = gender        
        user.user_birthday = user_birthday_date        
        user.rank = rank
        
        user.save()
        check_player = Player.objects.filter(player=user)
        check_player.update(player_ranking=user.rank)
        if 'image' in request.FILES:
            check_player.update(player_image=user.image)
        user.save()
        
        return redirect(reverse('dashboard:admin_profile'))
    return render(request, "dashboard/side/user/edit_user.html", context)


@superuser_required
def delete_user(request, user_id):
    user = get_object_or_404(User, id=user_id)
    context = {"user":user, "message": ""}
    if request.method == 'POST':
        player = Player.objects.filter(player_email=user.email)
        if player.exists():
            all_teams = player.first().team.all()
            if not all_teams:
                user.delete()
                player.first().delete()
            else:
                for team in all_teams:
                    team_id = team.id
                    check_team_have_any_tournament = Leagues.objects.filter(registered_team__in=[team_id], is_complete=False)
                    if not check_team_have_any_tournament.exists():
                        user.delete()
                        player.first().delete()
                    else:
                        context["message"] = "User cannot be deleted as he/she is already registered for tournament."
                        return render(request, "dashboard/side/user/delete_user_confirm.html",context)
        elif user.is_sponsor:
            sponsor = IsSponsorDetails.objects.filter(sponsor=user).first()
            sponsor.delete()
            user.delete()
        else:
            pass

        return redirect(reverse('dashboard:user_list', kwargs={'filter_by': "All"}))
    return render(request, "dashboard/side/user/delete_user_confirm.html",context)
#### user section end

## Ambassador post section 

@superuser_required
def ambassador_post_list(request):
    context = {"posts":"","message":""}
    posts = AmbassadorsPost.objects.all().order_by("created_at").values("id","file","post_text","approved_by_admin","created_at","created_by__username")
    context["posts"] = posts
    return render(request, "dashboard/side/ambassador_post_list.html", context)


@superuser_required
def ambassador_post_approve(request, post_id):
    context = {"ad":"", "message":""}
    post = get_object_or_404(AmbassadorsPost, id=post_id)
    post.approved_by_admin = True
    post.save()
    return redirect(reverse("dashboard:ambassador_post_list"))


@superuser_required
def ambassador_post_reject(request, post_id):
    context = {"ad":"", "message":""}
    post = get_object_or_404(AmbassadorsPost, id=post_id)
    post.approved_by_admin = False
    post.save()
    return redirect(reverse("dashboard:ambassador_post_list"))

## Ambassador post section ends


# merchant request not needed
from django.db.models import Q
@superuser_required
def merchant_request_list(request):
    context = {}
    try:
        if request.method == "POST":
            req_id = request.POST.get("req_id")
            request_ins = ProductSellerRequest.objects.filter(id=int(req_id))

            #### delete action
            if request.POST.get("delete"):
                print("hello")
                request_ins.delete()
            print("hello1")
            #### edit action
            if request.POST.get("Rejected"):
                request_ins.update(status="Rejected")
            elif request.POST.get("Approved"):
                request_ins.update(status="True")
            else:
                pass
        data = ProductSellerRequest.objects.all()
        context["request_pending"] = data.filter(Q(status__icontains="False")|Q(status__icontains="Rejected")).count()
        context["request_list"] = data.order_by('status')
        context["message"] = ""
    except :

        context["request_list"] = []
        context["message"] = "Somethings is Wrong!"
    return render(request, "dashboard/side/merchant/merchantdice_request.html", context)

