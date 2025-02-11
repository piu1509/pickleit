import json, csv

from django.db.models import Q
from django.core.paginator import Paginator
from django.contrib.admin.models import LogEntry
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.hashers import make_password
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.http import HttpResponse, JsonResponse, Http404
from django.contrib.auth import authenticate, login as auth_login, logout
from django.shortcuts import render, get_object_or_404, redirect, reverse

from apps.team.models import *
from apps.user.models import *
from apps.user.models import *
from apps.user.helpers import *
from apps.store.models import *
from apps.pickleitcollection.models import *
from apps.chat.views import notify_all_users
from apps.team.views import notify_edited_player, check_add_player

protocol = settings.PROTOCALL


# Create your views here.
@login_required(login_url="/admin/login/")
def index(request):
    total_team = Team.objects.all().count()
    total_player = Player.objects.all().count()
    total_tournament = Leagues.objects.all().count()
    log_entries = LogEntry.objects.select_related("user", "content_type").all().order_by("-action_time")[:20]
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
         'entries':entries})


@login_required(login_url="/admin/login/")
def download_logs_csv(request):
    # Create the HTTP response with CSV content type
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="log_entries.csv"'
    writer = csv.writer(response)
   
    writer.writerow(['LOG TYPE', 'ACTION', 'INSTANCE ID', 'ACTION BY', 'ACTION DATE AND TIME'])
    log_entries = LogEntry.objects.select_related("user", "content_type").all()

    for log in log_entries:
        writer.writerow([
            log.content_type.model if log.content_type else "N/A",  
            log.get_action_flag_display(),  
            log.object_id,  
            log.user.username if log.user else "N/A",  
            log.action_time, 
        ])

    return response


def login(request):
    context = {}
    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(username=username, password=password)
        if user is not None:
            if user.is_superuser or user.is_admin:
                auth_login(request, user) 
                return index(request)
        else:
            context['message'] = "You are not a verified user!!"
            return render(request, "dashboard/login.html", context)
    return render(request, "dashboard/login.html", context)


def logout_view(request):
    logout(request)
    return redirect(reverse('dashboard:user_login'))


@login_required(login_url="/admin/login/")
def player_list_(request):
    players = Player.objects.all().values("id","player_full_name","player_email","player","player_phone_number","created_at","player_ranking","created_by__username", "player__gender")
    for player in players:
        if player["player_ranking"] == "0" or player["player_ranking"] in [0,"","null",None]:
            player["player_ranking"] = 1
    context = {"player_list":players, "message":""}
    return render(request, "dashboard/side/player_list.html", context)


@login_required(login_url="/admin/login/")
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


@login_required(login_url="/admin/login/")
def player_view(request, user_id):
    context = {"message":""}
    player = get_object_or_404(Player, id=user_id)
    user = User.objects.get(id=player.player.id)
    if user.is_ambassador == True:
        context["posts"] = AmbassadorsPost.objects.filter(created_by=user).values()
    context["player"] = player
    return render(request, "dashboard/side/player_view.html", context)


@login_required(login_url="/admin/login/")
def edit_player(request, user_id):
    context = {'message':''}
    player = get_object_or_404(Player, id=user_id)
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
            player.player_image = request.FILES.get('player_image')        

        player.player_first_name  = p_first_name
        player.player_last_name = p_last_name
        player.player_phone_number = p_phone_no
        player.player_ranking = p_rank         
        player.save()
        user = User.objects.filter(email=player.player_email)
        user.update(gender=p_gender, rank=p_rank)
        if "player_image" in request.FILES:
            user.update(image=player.player_image)
        return redirect(reverse('dashboard:player_list_'))
    else:
        context = {"player": player}
        return render(request, "dashboard/side/edit_player.html", context)


@login_required(login_url="/admin/login/")
def delete_player(request, user_id):
    context = {"message":""}
    player = get_object_or_404(Player, id=user_id)
    p_email = player.player_email
    context["player"] = player
    if request.method == 'POST':
        all_teams = player.team.all()
        if not all_teams:
            player.delete()
            user = User.objects.filter(email=p_email)
            user.first().delete()
        else:
            for team in all_teams:
                team_id = team.id
                check_team_have_any_tournament = Leagues.objects.filter(registered_team__in=[team_id], is_complete=False)
                if not check_team_have_any_tournament.exists():
                    player.delete()
                    user = User.objects.filter(email=p_email)
                    user.first().delete()
                else:
                    context["message"] = "Player can not be deleted as he/she is in registered teams for tournament." 
                    return render(request, 'dashboard/side/player_delete_confirm.html', context)   
        return redirect(reverse('dashboard:player_list_'))
    return render(request, 'dashboard/side/player_delete_confirm.html', {'player': player})


@login_required(login_url="/admin/login/")
def team_list_for_admin(request):
    context = {"table_data":[], "message":""}
    try:
        team_data = list(Team.objects.filter(is_disabled=False).values("id", "name", "team_person", "team_image", "team_type", "created_by__first_name", "created_by__last_name"))
        team_rank = 0
        
        for team in team_data:   
                   
            players = Player.objects.filter(team__id=team["id"])
            team_rank = 0
            for player in players:
                player_rank = player.player.rank
                if player_rank == "0" or player_rank in [0,"", "null", None]:
                    # player.player_ranking = 1.0
                    team_rank += 1
                else:
                    team_rank += float(player.player.rank)
                print(team_rank)
            print(team_rank)
            if len(players) == 0:
                team_rank = 0
            else:
                team_rank = team_rank / len(players)     
            team["players"] = list(players.values("id", "player_full_name", "player__rank", "player__image", "player__gender"))
            team["team_rank"] = team_rank    
        context["table_data"] = team_data

        return render(request, "dashboard/side/team_list.html", context)
    except Exception as e:
        print(str(e))
        context["message"] = "Something is Wrong"
        return render(request, "dashboard/side/team_list.html", context)


@login_required(login_url="/admin/login/")
def create_team_(request):
    admin_user = User.objects.get(id=request.user.id)
    player_details = list(Player.objects.all().values("id", "player_full_name", "player__rank", "player__image", "player__gender", "player__id"))
    context = {"players":player_details, "team_info":[], "message":"","pre_player_ids":[], "oppration":"Create", "button":"Submit"}
    if request.method == "POST":
        team_name = request.POST.get('team_name')
        team_image = request.FILES.get('team_image')
        team_person = request.POST.get('team_person')
        team_type = request.POST.get('team_type')
        player_ids = request.POST.getlist('player_ids')
        if not team_name and not team_person and not team_type:
            # return HttpResponse("Team name, team person and team type are required.")
            context["message"] = "Team name, team person and team type are required."
            return render(request, "dashboard/side/create_team_form.html", context)
        
        if Team.objects.filter(name = team_name).exists():
            # return HttpResponse("Team name already exists")
            context["message"] = "Team name already exists."
            return render(request, "dashboard/side/create_team_form.html", context) 
        
        if team_person == "Two Person Team" and len(player_ids) == 2:
            if team_type == "Men":                
                players = Player.objects.filter(id__in=player_ids)
                for player in players:
                    if not player.player.gender == "Male":
                        # return HttpResponse("Select male players only.")  
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
                        # return HttpResponse("Select female players only.")  
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


@login_required(login_url="/admin/login/")
def edit_team_(request, team_id):
    team_info = get_object_or_404(Team, id=team_id)
    player_details = list(Player.objects.all().values("id", "player_full_name", "player__rank", "player__image", "player__gender", "player__id"))
    pre_player_ids = list(Player.objects.filter(team__id=team_id).values_list("id", flat=True))
    context = {"players":player_details, "team_info":team_info, "message":"","pre_player_ids":pre_player_ids, "oppration":"Edit", "button":"Submit"}
    
    if request.method == "POST":
        team_name = request.POST.get('team_name')
        team_image = request.FILES.get('team_image')
        team_person = request.POST.get('team_person')
        team_type = request.POST.get('team_type')
        player_ids = request.POST.getlist('player_ids')
        if not team_name and not team_person and not team_type:
            # return HttpResponse("Team name, team person and team type are required.")
            context["message"] = "Team name, team person and team type are required."
            return render(request, "dashboard/side/create_team_form.html", context)
        
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
                return render(request, "dashboard/side/create_team_form.html", context)
        elif team_person == "One Person Team":
            if len(player_ids) != 1:
                context["message"] = "Need to select only one player."
                return render(request, "dashboard/side/create_team_form.html", context)
        
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
                        return render(request, "dashboard/side/create_team_form.html", context)
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
                        return render(request, "dashboard/side/create_team_form.html", context)
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
                    return render(request, "dashboard/side/create_team_form.html", context)    
        elif team_person == "One Person Team" and len(player_ids) == 1: 
            if team_type == "Men":
                players = Player.objects.filter(id__in=player_ids)
                if not players.first().player.gender == "Male":
                    # return HttpResponse("Select male player only.")
                    context["message"] = "Select male player only."
                    return render(request, "dashboard/side/create_team_form.html", context)
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
                    return render(request, "dashboard/side/create_team_form.html", context)
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
    return render(request, "dashboard/side/create_team_form.html", context)


@login_required(login_url="/admin/login/")
def view_team_(request,team_id):
    context={}
    # team_view = list(Team.objects.filter(id=team_id).values("id","name","team_person","team_image","team_type","created_by__first_name", "created_by__last_name"))
    base_url = request.build_absolute_uri('/')[:-1]
    no_img = base_url + "/media/team_image/No_Image_Available.jpg"
    
    obj_id = Team.objects.get(id=team_id)
    print(obj_id)
    if obj_id:
        context['name'] = obj_id.name
        context['team_image'] = obj_id.team_image if obj_id.team_image else no_img
        context['team_person'] = obj_id.team_person
        context['team_type'] = obj_id.team_type
        context['created_by__first_name'] = obj_id.created_by.first_name
        context['created_by__last_name'] = obj_id.created_by.last_name
        context['player_list'] = list(Player.objects.filter(team__id=obj_id.id).values("id", "player_full_name", "player__rank", "player__image", "player__gender"))
    return render(request, "dashboard/side/team_view.html",context)


@login_required(login_url="/admin/login/")
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


@login_required(login_url="/admin/login/")
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


@login_required(login_url="/admin/login/")    
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


@login_required(login_url="/admin/login/")
def view_user(request, user_id):
    context = {"message":""}
    user = get_object_or_404(User, id=user_id)
    if user.is_ambassador:
        context["posts"] = AmbassadorsPost.objects.filter(created_by=user).values()
    context["user"] = user 
    return render(request, "dashboard/side/user/view_user.html", context)


@login_required(login_url="/admin/login/")
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
        if not is_verified:
            user.is_verified = False
        else:
            user.is_verified = True
        user.save()
        check_player = Player.objects.filter(player=user)
        check_player.update(player_ranking=user.rank)
        if 'image' in request.FILES:
            check_player.update(player_image=user.image)
        if "is_admin" in responsibilities:
            user.is_admin= True
            user.save()
        else:
            user.is_admin= False
            user.save()    
                    
        if "is_organizer" in responsibilities:
            user.is_organizer = True
            user.save()
        else:
            user.is_organizer = False
            user.save()
        if "is_sponsor" in responsibilities:
            user.is_sponsor = True
            role = Role.objects.filter(role="Sponsor").first()
            user.role = role
            user.is_player = False
            user.save()
            check_player = Player.objects.filter(player_email=user.email)
            if check_player.exists():
                player = check_player.first()
                player.delete()
            check_sponsor_details = IsSponsorDetails.objects.filter(sponsor=user)
            if not check_sponsor_details.exists():
                obj = GenerateKey()
                secret_key = obj.gen_user_key()
                sponsor_details = IsSponsorDetails.objects.create(secret_key=secret_key, sponsor=user,sponsor_added_by=admin_user)
        else:
            user.is_sponsor = False
            role = Role.objects.filter(role="User").first()            
            user.role = role
            user.is_player = True
            user.save()
            obj = GenerateKey()
            secret_key = obj.gen_player_key()
            check_player = Player.objects.filter(player_email=user.email)
            if not check_player:
                player = Player(secret_key=secret_key,player_first_name=user.first_name,player_last_name=user.last_name,player_phone_number=user.phone,player_ranking=user.rank,
                                player_full_name=f"{user.first_name} {user.last_name}",player_email=user.email,created_by=admin_user)
                player.save()
            check_sponsor_details = IsSponsorDetails.objects.filter(sponsor=user)
            if check_sponsor_details.exists():
                check_sponsor_details.first().delete()
        if "is_ambassador" in responsibilities:
            user.is_ambassador = True
            user.save()
            check_ambassador_details = AmbassadorsDetails.objects.filter(ambassador=user)
            if not check_ambassador_details:
                ambassador_details = AmbassadorsDetails.objects.create(ambassador=user)
        else:
            user.is_ambassador = False
            user.save()
        if not request.user.is_admin:                   
            return redirect(reverse('dashboard:user_list', kwargs={'filter_by': "All"}))
        else:
            return redirect(reverse('dashboard:admin_profile'))
    return render(request, "dashboard/side/user/edit_user.html", context)


@login_required(login_url="/admin/login/")
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


@login_required(login_url="/admin/login/")
def tournament_list(request, filter_by):
    context = {"tournament_data": []}
    filter_by = request.GET.get('filter_by')
    context["filter_by"] = filter_by
    all_leagues = Leagues.objects.filter(is_disabled=False).order_by('-created_at')  # Order by created_at descending
    today_date = datetime.now()

    # Filter leagues based on filter_by
    if filter_by == "all":
        all_leagues = all_leagues
    elif filter_by == "upcoming":
        all_leagues = all_leagues.filter(registration_start_date__date__gte=today_date)
    elif filter_by == "past":
        all_leagues = all_leagues.filter(registration_end_date__date__lte=today_date)
    elif filter_by == "open":
        all_leagues = all_leagues.filter(registration_start_date__date__lte=today_date,
                                         registration_end_date__date__gte=today_date)

    leagues = all_leagues.values('id', 'description', 'uuid', 'secret_key', 'name', 'location', 'leagues_start_date', 
                                 'leagues_end_date', 'registration_start_date', 'registration_end_date', 
                                 'team_type__name', 'team_person__name', 'street', 'city', 'state', 'postal_code', 
                                 'country', 'complete_address', 'latitude', 'longitude', 'image', 'others_fees', 
                                 'league_type', 'registration_fee', 'created_at')

    # Grouping data by 'name'
    grouped_data = {}
    for item in list(leagues):
        item["is_reg_disabled"] = True
        match_ = Tournament.objects.filter(leagues_id=item["id"]).values()
        if match_.exists():
            item["is_reg_disabled"] = False
        le = Leagues.objects.filter(id=item["id"]).first()
        reg_team = le.registered_team.all().count()
        max_team = le.max_number_team
        if max_team <= reg_team:
            item["is_reg_disabled"] = False
        
        key = item['name']
        sub_organizer = le.add_organizer.all().values()
        
        created_by = f"{le.created_by.first_name} {le.created_by.last_name}"
        
        team_type = {
            'id': le.id,  # Assuming `team_type` has an `id` field
            'type': le.team_type.name
        }
        
        if key not in grouped_data:
            grouped_data[key] = {
                'id': item['id'],
                'name': item['name'],
                'lat': item['latitude'],
                'long': item["longitude"],
                'registration_start_date': item["registration_start_date"],
                'registration_end_date': item["registration_end_date"],
                'description': item["description"],
                'leagues_start_date': item["leagues_start_date"],
                'leagues_end_date': item["leagues_end_date"],
                'location': item["location"],
                'image': item["image"],
                'type': [team_type],
                'sub_organizer': sub_organizer,
                'created_by': created_by,
                'data': [item]
            }
        else:
            if team_type not in grouped_data[key]['type']:
                grouped_data[key]['type'].append(team_type)
            grouped_data[key]['data'].append(item)

    # Sorting the grouped data by the created_at field (latest tournament first)
    output = []
    for key, value in grouped_data.items():
        value['data'].sort(key=lambda x: x['created_at'], reverse=True)
        output.append(value)

    # Pagination
    paginator = Paginator(output, 5)  # Show 5 tournaments per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context["tournament_data"] = page_obj
    return render(request, "dashboard/side/tournament_list.html", context)


@login_required(login_url="/admin/login/")
def view_tournament(request, tour_id):
    context = {
        "league_details": [],
        "matches":[],
        "teams":[],
        "message":None
    }
    try:
        League_details = Leagues.objects.filter(id=tour_id).first()
        context["league_details"] = League_details
        if League_details.registered_team:
            context["teams"] = League_details.registered_team.all()
        matches = Tournament.objects.filter(leagues=League_details).values()
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
    print(context["message"])
    return render(request, "dashboard/side/tournament_type_details.html",context)


@login_required(login_url="/admin/login/")
def edit_tournament(request, tour_id):
    try:
        # Get the league details or raise an error if it doesn't exist
        league_details = Leagues.objects.get(id=tour_id)
        
        # Initialize context dictionary
        context = {
            "league_details": league_details,
            "teams": Team.objects.all()
        }

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

            # Handle many-to-many relationship with teams (Join Team)
            selected_teams = request.POST.getlist("join_team")
            league_details.registered_team.set(selected_teams)

            # Handle other fees, if any
            other_fees_topic = request.POST.getlist("other_fees_topic[]")
            other_fees = request.POST.getlist("other_fees[]")
            other_fees_dict = dict(zip(other_fees_topic, other_fees))
            league_details.others_fees = other_fees_dict

            # Save updated details
            league_details.save()

            # Redirect to a success page or show a success message
            return redirect("tournament_success_page_url")  # Replace with actual URL

    except Leagues.DoesNotExist:
        # If the league doesn't exist, raise a 404 error
        raise Http404("Tournament not found.")
    except Exception as e:
        # Log or handle other exceptions
        context["message"] = str(e)
        return render(request, "dashboard/side/edit_tournamnet.html", context)
    return render(request, "dashboard/side/edit_tournamnet.html", context)


@login_required(login_url="/admin/login/")
def edit_matches__(request, tour_id):
    
    league_details = Leagues.objects.get(id=tour_id)
    
    # Initialize context dictionary
    context = {
        "matches": Tournament.objects.filter(leagues=league_details), 
        "league_name": league_details.name
    } 
    return render(request, "dashboard/side/edit_matches.html", context)


@csrf_exempt
@login_required(login_url="/admin/login/")
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


@login_required(login_url="/admin/login/")
def update_match(request, set_score_id):
    if request.method == 'POST':
        match = get_object_or_404(TournamentSetsResult, id=set_score_id)

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
        return JsonResponse({"success": True, "message": "Match updated successfully!"})

    return JsonResponse({"success": False, "message": "Invalid request method."}, status=400)


@login_required(login_url="/admin/login/")
def hit_start_tournamnet(request, tour_id):
    check_tour = Leagues.objects.filter(id=tour_id).first()
    tour_create_by = check_tour.created_by
    host = request.get_host()
    current_site = f"{protocol}://{host}"
    url = f"{current_site}/team/22fef865dab2109505b61d85df50c5126e24f0c0a10990f2670c179fb841bfd2/"
    payload = {
        'user_uuid': str(tour_create_by.uuid),
        'user_secret_key': str(tour_create_by.secret_key),
        'league_uuid': str(check_tour.uuid),
        'league_secret_key': str(check_tour.secret_key)
    }
    response = requests.post(url, json=payload)
    return redirect('dashboard:view_tournament', tour_id=tour_id)


@login_required(login_url="/admin/login/")
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
            print(team_person[counter])
            check_leagues = LeaguesTeamType.objects.filter(name=str(kk))
            check_person = LeaguesPesrsonType.objects.filter(name=str(team_person[counter]))
            print(check_leagues)
            print(check_person)
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

            if latitude is None:
                latitude = 38.908683
            if longitude is None:
                longitude = -76.937352
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


@login_required(login_url="/admin/login/")
def edit_tournamnet(request, tour_id):
    context = {"details":[], "message":"", "data":[],"button":"submit"}
    league = Leagues.objects.filter(id=tour_id)
    check_tour = league.first()
    context["details"] = league.values()
    context["data"] = LeaguesPlayType.objects.filter(league_for=check_tour).first().data
    pre_data = context["data"]
    if request.method == "POST":
        court_type = request.POST.getlist("court_type_name[]")
        court_number = request.POST.getlist("court_number[]")
        set_number = request.POST.getlist("set_number[]")
        max_score = request.POST.getlist("max_score[]")
        for i in range(len(pre_data)):
            for k in range(len(court_type)):
                if pre_data[i]["name"] == court_type[k]:
                    pre_data[i]["number_of_courts"] = int(court_number[k])
                    pre_data[i]["sets"] = int(set_number[k])
                    pre_data[i]["point"] = int(max_score[k])
        LeaguesPlayType.objects.filter(league_for=check_tour).update(data=pre_data)
        type = check_tour.team_type.name
        return redirect(reverse("dashboard:view_tournament", kwargs={"tour_id":tour_id, "type":type}))
    return render(request, "dashboard/side/tournament_edit_details.html", context)


@login_required(login_url="/admin/login/")
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
    type = tournament.team_type.name
    return redirect(reverse("dashboard:view_tournament", kwargs={"tour_id":tour_id, "type":type}))


@login_required(login_url="/admin/login/")
def delete_tournament(request, tour_id):
    context = {"dis_message":""}
    tournament = get_object_or_404(Leagues, id=tour_id)
    type = tournament.team_type.name
    context["tournament"] = tournament
    if request.method == 'POST':
        if tournament.is_complete== False:
            # return HttpResponse("This tournament cannot be deleted as teams have registered for it.")
            context["dis_message"] = "This tournament cannot be deleted as its still not completed "
            type = tournament.team_type.name
            return render(request, "dashboard/side/tournament_type_details.html", context)
        else:
            matches =  Tournament.objects.filter(leagues=tournament)
            round_robin = RoundRobinGroup.objects.filter(league_for=tournament)
            if matches.exists():
                set_result = TournamentSetsResult.objects.filter(tournament__leagues=tournament)
                if set_result.exists():
                    set_result.delete()
                if round_robin.exists():
                    round_robin.delete()
                matches.delete()
            tournament.delete()            
            return redirect("/admin/tournamnet_list/all")
    return render(request, "dashboard/side/tournament_type_details.html", context)


@login_required(login_url="/admin/login/")
def ambassador_post_list(request):
    context = {"posts":"","message":""}
    posts = AmbassadorsPost.objects.all().order_by("created_at").values("id","file","post_text","approved_by_admin","created_at","created_by__username")
    context["posts"] = posts
    return render(request, "dashboard/side/ambassador_post_list.html", context)


@login_required(login_url="/admin/login/")
def advertisement_list(request):
    context = {"advertisemnets":"","message":""}
    ads = Advertisement.objects.all().order_by('created_at').values("id","name","image","script_text","url","approved_by_admin","description","start_date","end_date","created_at","created_by__username")
    context["advertisements"] = ads
    return render(request, "dashboard/side/advertisement_list.html", context)


@login_required(login_url="/admin/login/")
def advertisement_view(request, ad_id):
    context = {"ad":"", "message":""}
    ad = get_object_or_404(Advertisement, id=ad_id)
    context["ad"] = ad
    return render(request, "dashboard/side/advertisement_view.html", context)


@login_required(login_url="/admin/login/")
def ad_approve(request, ad_id):
    context = {"ad":"", "message":""}
    ad = get_object_or_404(Advertisement, id=ad_id)
    ad.approved_by_admin = True
    ad.save()
    return redirect(reverse("dashboard:advertisement_list"))


@login_required(login_url="/admin/login/")
def ad_reject(request, ad_id):
    context = {"ad":"", "message":""}
    ad = get_object_or_404(Advertisement, id=ad_id)
    ad.approved_by_admin = False
    ad.save()
    return redirect(reverse("dashboard:advertisement_list"))


@login_required(login_url="/admin/login/")
def ambassador_post_approve(request, post_id):
    context = {"ad":"", "message":""}
    post = get_object_or_404(AmbassadorsPost, id=post_id)
    post.approved_by_admin = True
    post.save()
    return redirect(reverse("dashboard:ambassador_post_list"))


@login_required(login_url="/admin/login/")
def ambassador_post_reject(request, post_id):
    context = {"ad":"", "message":""}
    post = get_object_or_404(AmbassadorsPost, id=post_id)
    post.approved_by_admin = False
    post.save()
    return redirect(reverse("dashboard:ambassador_post_list"))


@login_required(login_url="/admin/login/")
def admin_profile(request):
    context = {"message":""}
    admin_user = User.objects.get(id=request.user.id)
    context["user"] = admin_user
    return render(request, 'dashboard/side/admin_profile.html', context)


@login_required(login_url="/admin/login/")
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


@login_required(login_url="/admin/login/")
def create_open_play(request):
    context = {"message":""}
    admin_user = User.objects.filter(id=request.user.id).first()
    teams = Team.objects.all()
    context["teams"] = teams
    if request.method == "POST":
        player_type = request.POST.get("player_type")
        start_date = request.POST.get("t_start_date")
        location = request.POST.get("location")
        team_type = "Open-team"
        description = request.POST.get("description")
        court = request.POST.get("court")
        points = request.POST.get("points")
        sets = request.POST.get("set")
        team_id_list = request.POST.getlist("team_ids")
        play_type = request.POST.get("play_type")
        max_number_team = 2
        registration_fee = 0
        league_type = "Open to all"
        

        if len(team_id_list) != 2:
            context["message"] = "Need to select 2 teams."
            return render(request, "dashboard/side/create_open_play_form.html",context)
        
        team_1_id = team_id_list[0]
        team_2_id = team_id_list[1]
        team1_players = list(Player.objects.filter(team__id=team_1_id).values_list("id", flat=True))
        team2_players = list(Player.objects.filter(team__id=team_2_id).values_list("id", flat=True))
        for player_id in team1_players:
            if player_id in team2_players:
                context["message"] = "Need to select One person team."
                return render(request, "dashboard/side/create_open_play_form.html",context)
        
        if player_type == "One Person Team":
            for team_id in team_id_list:
                team = Team.objects.filter(id=team_id).first()
                if team.team_person != "One Person Team":
                    context["message"] = "Need to select One person team."
                    return render(request, "dashboard/side/create_open_play_form.html",context)
                
        if player_type == "Two Person Team":
            for team_id in team_id_list:
                team = Team.objects.filter(id=team_id).first()
                if team.team_person != "Two Person Team":
                    context["message"] = "Need to select Two person team."
                    return render(request, "dashboard/side/create_open_play_form.html",context)
        team_names = {}
        counter = 0
        for team in team_id_list:
            counter += 1
            team_instance = Team.objects.filter(id=team).first()
            team_names[f'team{counter}_name'] = team_instance.name
        tournament_name = f"{team_names['team1_name']} VS {team_names['team2_name']}"
        check_leagues = LeaguesTeamType.objects.filter(name=team_type)
        check_person = LeaguesPesrsonType.objects.filter(name=player_type)
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
            leagues_start_date=start_date,
            location=location,
            created_by_id=admin_user.id,
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
            j["is_show"] = True
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
        return redirect("/admin/tournamnet_list/all")
    return render(request, "dashboard/side/create_open_play_form.html",context)


@login_required(login_url="/admin/login/")
def add_product(request):
    context = {"message":""}
    all_category = MerchandiseStoreCategory.objects.all()
    leagues = Leagues.objects.all()
    context["categories"] = all_category
    context["leagues"] = leagues
    admin_user = get_object_or_404(User, id=request.user.id)
    if request.method == 'POST':
        product_name = request.POST.get("name")
        category = request.POST.get("category")
        league_ids = request.POST.getlist("leagues")
        description = request.POST.get("description")
        specification = request.POST.get("specification")
        product_old_price = request.POST.get("old_price")
        product_new_price = request.POST.get("new_price")
        product_image = request.FILES.get("image")
        product_size = request.POST.getlist("size")
        if not category or not product_new_price or not product_name:
           context["message"] = "Category/Price/Name is required." 
           return render(request, "dashboard/side/add_product_form.html", context)

        get_category = MerchandiseStoreCategory.objects.filter(id=category).first()
        
        percent_off = ((float(product_old_price) - float(product_new_price)) / float(product_old_price)) * 100
        obj = GenerateKey()
        secret_key = obj.gen_product_key()
        save_product = MerchandiseStoreProduct.objects.create(secret_key=secret_key,name=product_name,category=get_category,description=description,
                                                              specifications=specification,old_price=product_old_price,price=product_new_price,
                                                              percent_off=round(percent_off,2),image=product_image,size=product_size, created_by=admin_user)
        for id in league_ids:
            get_league = Leagues.objects.filter(id=id).first()
            save_product.leagues_for.add(get_league)
        save_product.save()
        return redirect(reverse("dashboard:product_list"))
    else:
        return render(request, "dashboard/side/add_product_form.html", context)


@login_required(login_url="/admin/login/")
def product_list(request):
    context = {"message":""}
    product_list = MerchandiseStoreProduct.objects.all()
    context["product_list"] = product_list
    return render(request, "dashboard/side/product_list.html", context)


@login_required(login_url="/admin/login/")
def view_product(request, product_id):
    context = {"message":""}
    product = get_object_or_404(MerchandiseStoreProduct, id=product_id)
    context["product"] = product
    return render(request, "dashboard/side/view_product.html", context)


@login_required(login_url="/admin/login/")
def edit_product(request, product_id):
    context = {"message":""}
    product = get_object_or_404(MerchandiseStoreProduct, id=product_id)
    all_category = MerchandiseStoreCategory.objects.all()
    leagues = Leagues.objects.all()
    context["categories"] = all_category
    context["leagues"] = leagues
    context["product"] = product
    if request.method == "POST":
        product_name = request.POST.get("name")
        category = request.POST.get("category")
        league_ids = request.POST.getlist("leagues")
        description = request.POST.get("description")
        specification = request.POST.get("specification")
        product_old_price = request.POST.get("old_price")
        product_new_price = request.POST.get("new_price")
        product_image = request.FILES.get("image")
        product_size = request.POST.getlist("size")
        if not category or not product_new_price or not product_name:
           context["message"] = "Category/Price/Name is required." 
           return render(request, "dashboard/side/edit_product_form.html", context)
        
        get_category = MerchandiseStoreCategory.objects.filter(id=category).first()
        product.name = product_name
        product.category = get_category
        product.old_price = product_old_price
        product.price = product_new_price
        if product_image:
            product.image = product_image
        product.description = description
        product.specifications = specification
        product.size = product_size
        percent_off = ((float(product_old_price) - float(product_new_price)) / float(product_old_price)) * 100
        product.percent_off = round(percent_off, 2)
        product.save()
        for id in league_ids:
            get_league = Leagues.objects.filter(id=id).first()
            product.leagues_for.add(get_league)
        product.save()
        return redirect(reverse("dashboard:product_list"))
    else:
        return render(request, "dashboard/side/edit_product_form.html", context)


@login_required(login_url="/admin/login/")
def delete_product(request, product_id):
    context = {"message":""}
    product = get_object_or_404(MerchandiseStoreProduct, id=product_id)
    context["product"] = product
    if request.method == "POST":
        product.delete()
        return redirect(reverse("dashboard:product_list"))
    return render(request, "dashboard/side/delete_product.html", context)


@login_required(login_url="/admin/login/")
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


@login_required(login_url="/admin/login/")
def payment_table(request):
    context = {"message":""}
    payments_for_buy_product = PaymentDetails.objects.filter(payment_for="product_buy")
    payment_for_advertisemnet = PaymentDetails.objects.all().exclude(payment_for="product_buy")
    payments_for_team_registration = PaymentDetailsForRegister.objects.all()
    context["payment_for_product"] = payments_for_buy_product
    context["payment_for_team"] = payments_for_team_registration
    context["payment_for_ad"] = payment_for_advertisemnet
    return render(request, "dashboard/side/payment/payment_details.html", context)


#########
# merchant request
@login_required(login_url="/admin/login/")
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


@login_required(login_url="/admin/login/")
def version_update_list(request):
    context = {}
    version_updates = AppVersionUpdate.objects.all().values("version", "release_date", "description", "created_by", "updated_users")
    context["version_updates"] = version_updates
    return render(request, "dashboard/side/update/version_updates_list.html", context)


@login_required(login_url="/admin/login/")
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


def test(request):
    user_list = User.objects.all()
    search_query = request.GET.get('search', '')
    products = User.objects.filter(email__icontains=search_query)

    paginator = Paginator(products, 6) 
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'test.html',{"user_list":page_obj})
