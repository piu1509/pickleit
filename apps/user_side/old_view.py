from pyexpat.errors import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login as auth_login, logout
from django.urls import reverse
from apps.team.models import *
from apps.user.models import User, Wallet, Transaction, WalletTransaction
from apps.socialfeed.models import socialFeed, FeedFile
from django.db.models import Q
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from datetime import timezone, datetime
from apps.clubs.models import *
from django.conf import settings
from geopy.distance import geodesic


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


### modified
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


@login_required
def logout_view_user(request):
    logout(request)
    return redirect('user_side:user_login')

def user_signup(request):
    return render(request, 'auth/signup.html')

@login_required
def profile(request):
    player = Player.objects.filter(player=request.user).first()
    teams = player.team.all()
    match_history = Tournament.objects.filter(Q(team1__in=teams) | Q(team2__in=teams)).order_by("-id")
    match_history_cal = match_history.only("team1", "team2", "winner_team")
    wins = sum(1 for match_ in match_history_cal if match_.winner_team in teams)
    losses = len(match_history_cal) - wins
    context = {
        "user_details": None,
        "player" : player,
        "total_match": match_history.count(),
        "losses" : losses,
        "wins" : wins
    }
    context["user_details"] = request.user
    return render(request, 'sides/profile.html', context=context)

@login_required
def edit_profile(request):
    user = User.objects.filter(id=request.user.id).first()

    if request.method == "POST":
        user.first_name = request.POST.get("first_name", user.first_name)
        user.last_name = request.POST.get("last_name", user.last_name)
        user.phone = request.POST.get("phone", user.phone)
        user.gender = request.POST.get("gender", user.gender)
        user.rank = request.POST.get("rank", user.rank)
        user.dob = request.POST.get("dob", user.dob)
        user.permanent_location = request.POST.get("location", user.permanent_location)
        
        # Fixing incorrect latitude and longitude field names
        user.latitude = request.POST.get("latitude", user.latitude)
        user.longitude = request.POST.get("longitude", user.longitude)
        
        user.bio = request.POST.get("bio", user.bio)

        if 'profile_picture' in request.FILES:
            user.image = request.FILES['profile_picture']
        
        try:
            user.save()
            # messages.success(request, "Profile updated successfully!")
            return redirect('user_side:user_profile')
        except Exception as e:
            messages.error(request, f"Error updating profile: {str(e)}")

    context = {"user_details": user, "MAP_API_KEY" : 'AIzaSyAQ_OGAb4yuL8g55IMufP3Dwd4yjrWxrdI'}
    return render(request, 'sides/editprofile.html', context)


@login_required
def index(request):
    context = {
        "user_teams_count": 0,
        "balance": 0,
        "join_event_count":0,
        "completed_event_count":0,
        "match_history":[],
        "socail_feed_list":[]
    }
    user_teams = Team.objects.filter(created_by=request.user)
    join_event = Leagues.objects.filter(registered_team__in = user_teams, is_complete=False).distinct()
    completed_event = Leagues.objects.filter(registered_team__in = user_teams, is_complete=True).distinct()
    user_teams_count = user_teams.count()
    balance = Wallet.objects.filter(user=request.user).first().balance
    join_event_count = join_event.count()
    completed_event_count = completed_event.count()
    match_history = Tournament.objects.filter(Q(team1__in=user_teams) | Q(team2__in=user_teams)).distinct()[:5]
    socail_feed_list = socialFeed.objects.all().order_by("-created_at")[:5]
    for match_ in match_history:
        match_.score = TournamentSetsResult.objects.filter(tournament=match_)
    for feed in socail_feed_list:
        images = FeedFile.objects.filter(post=feed)
        if images:
            feed.image = images.first().file.url
    context["user_teams_count"] = user_teams_count
    context["balance"] = balance
    context["join_event_count"] = join_event_count
    context["completed_event_count"] = completed_event_count
    context["match_history"] = match_history
    context["socail_feed_list"] = socail_feed_list
    return render(request, 'sides/index.html', context=context)

@login_required
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

@login_required
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
    
    paginator = Paginator(teams, 10)  # Show 10 teams per page
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

@login_required
def team_view_user(request, team_id):
    context = {}
    team = get_object_or_404(Team, id=team_id)
    query = request.GET.get('q', '').strip()
    
    player = Player.objects.filter(player=request.user).first()
    if not player:
        context["error"] = "Player profile not found."
        return render(request, 'sides/match_history.html', context)

    teams = team
    match_history = Tournament.objects.filter(Q(team1=teams) | Q(team2=teams)).order_by("-id")
    match_history_cal = match_history.only("team1", "team2", "winner_team")
    wins = sum(1 for match_ in match_history_cal if match_.winner_team == teams)
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
        match_.scores = TournamentSetsResult.objects.filter(tournament=match_)

    context.update({
        "team_details": team,
        "match_history": paginated_matches,
        "total_matches": total_matches,
        "wins": wins,
        "losses": losses,
        "query": query,  
    })
    return render(request, 'sides/team_view.html', context)

@login_required
def event(request):
    query = request.GET.get('q', '')
    team_type_filter = request.GET.get('team_type', '')
    leagues = Leagues.objects.all().order_by('-leagues_start_date')  # Fetch all leagues sorted by start date
    today = datetime.now()
    if team_type_filter == "all":
        pass
    elif team_type_filter == "Open":
        leagues = leagues.filter(registration_start_date__date__lte=today,registration_end_date__date__gte=today)
    elif team_type_filter == "Upcoming":
        leagues = leagues.filter(leagues_start_date__date__gte = today, is_complete=False)
    elif team_type_filter == "Ongoing":
        leagues = leagues.filter(leagues_start_date__date__lte = today, leagues_end_date__date__gte = today, is_complete=False)
    elif team_type_filter == "Past":
        leagues = leagues.filter(leagues_end_date__date__lte = today, is_complete=True)
    return render(request, 'sides/event.html', {'leagues': leagues, "team_type_filter":team_type_filter, "text":query})

@login_required
def event_view(request, event_id):
    context = {}
    user = request.user
    today = datetime.now()
    event = get_object_or_404(Leagues, id=event_id)
    context["event"] = event
    context["league_type"] = LeaguesPlayType.objects.filter(league_for=event)
    context["policy"] = LeaguesCancellationPolicy.objects.filter(league=event)
    context["all_join_teams"] = event.registered_team.all()
    context["organizer"] = user == event.created_by
    # calculate total fees
    fees = event.registration_fee
    others_fees = event.others_fees
    if others_fees:
        for val in others_fees.values():
            if isinstance(val, (int, float)):  # Ensure the value is numeric
                fees += val
            elif isinstance(val, str) and val.isdigit():  # Convert string numbers
                fees += int(val)
    context["total_fees"] = fees
    ##wallet balance
    try:
        wallet = Wallet.objects.filter(user=user).first()
        balance = wallet.balance
    except:
        balance = 0
    context["balance"] = balance
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
    #matches 
    matches = Tournament.objects.filter(leagues=event)
    for matche in matches:
        matche.score = TournamentSetsResult.objects.filter(tournament=matche)

    context["matches"] = matches
    team_stats = {}
    for match_ in matches:
        if match_.team1 and match_.team2:
            if match_.team1 not in team_stats:
                team_stats[match_.team1] = {"played": 0, "wins": 0, "losses": 0, "draws": 0, "points": 0}
            if match_.team2 not in team_stats:
                team_stats[match_.team2] = {"played": 0, "wins": 0, "losses": 0, "draws": 0, "points": 0}

            team_stats[match_.team1]["played"] += 1
            team_stats[match_.team2]["played"] += 1

            if match_.is_drow:  # If match is a draw
                team_stats[match_.team1]["draws"] += 1
                team_stats[match_.team2]["draws"] += 1
                team_stats[match_.team1]["points"] += 1
                team_stats[match_.team2]["points"] += 1
            elif match_.winner_team:  # If there is a winner
                team_stats[match_.winner_team]["wins"] += 1
                team_stats[match_.winner_team]["points"] += 3  # 3 points for a win
                loser_team = match_.team1 if match_.winner_team == match_.team2 else match_.team2
                team_stats[loser_team]["losses"] += 1

    
    context["is_join"] = event.registration_end_date.date() >= today.date()
    # Sort teams based on points (highest first)
    sorted_teams = sorted(team_stats.items(), key=lambda x: x[1]["points"], reverse=True)
    context["sorted_teams"] = sorted_teams
    context["groups "] = RoundRobinGroup.objects.filter(league_for=event)
    return render(request, 'sides/event_view.html', context=context)

@login_required
def match_history(request):
    query = request.GET.get('q', '').strip()
    context = {}

    player = Player.objects.filter(player=request.user).first()
    if not player:
        context["error"] = "Player profile not found."
        return render(request, 'sides/match_history.html', context)

    teams = player.team.all()
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
    # print(match_history)
    # Pagination: 21 matches per page
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

    context.update({
        "match_history": paginated_matches,
        "total_matches": total_matches,
        "wins": wins,
        "losses": losses,
        "query": query,  # Pass query for template usage
    })

    return render(request, 'sides/match_history.html', context)


@login_required
def update_match_score(request):
    query = request.GET.get('q', '').strip()
    context = {}

    player = Player.objects.filter(player=request.user).first()
    if not player:
        context["error"] = "Player profile not found."
        return render(request, 'sides/update_score.html', context)

    teams = player.team.all()
    current_eventlist = Leagues.objects.filter(registered_team__in = teams, is_complete=False).distinct().only("id", "name", "team_type", "image")
    if query:
        current_eventlist = current_eventlist.filter(Q(name__icontence = query), Q(team_type__name__icontence = query))
    context["events"] = current_eventlist
    return render(request, 'sides/update_score.html', context)

@login_required
def user_wallet(request):
    start_date = request.GET.get("start_date", None)
    end_date = request.GET.get("end_date", None)
    page = request.GET.get("page", 1)  # Get the current page number from request
    
    wallet = Wallet.objects.filter(user=request.user)
    
    if start_date and end_date:
        wallet = wallet.filter(created_at__date__gte=start_date, created_at__date__lte=end_date)

    balance = 0.0
    transactions = WalletTransaction.objects.filter(Q(sender=request.user) | Q(reciver=request.user)).order_by("-created_at")

    # Apply pagination (10 transactions per page)
    paginator = Paginator(transactions, 10)  
    transactions_page = paginator.get_page(page)  

    if wallet.exists():
        balance = wallet.first().balance

    return render(
        request,
        "sides/wallet.html",
        {
            "wallet_balance": balance,
            "transactions": transactions_page,  # Pass paginated transactions
        },
    )

