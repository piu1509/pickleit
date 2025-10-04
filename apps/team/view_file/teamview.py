import os
import json
import email
from datetime import timedelta
from itertools import combinations
from apps.team.views import check_add_player, notify_edited_player
import random, json, base64, stripe
from math import radians, cos, sin, asin, sqrt
from dateutil.relativedelta import relativedelta
from decimal import Decimal, ROUND_DOWN
from apps.user.models import *
from apps.chat.models import *
from apps.team.models import *
from apps.user.helpers import *
from apps.team.serializers import *
from apps.pickleitcollection.models import *

from django.conf import settings
from django.utils import timezone
from django.core.cache import cache
from django.core.mail import send_mail
from django.forms.models import model_to_dict
from django.contrib.auth.hashers import make_password 
from django.shortcuts import render, get_object_or_404
from django.core.cache.backends.base import DEFAULT_TIMEOUT
from django.db.models.functions import Cast, Concat, TruncMonth
from django.db.models import Avg, Sum, Count, Value, F, Q, Case, When, IntegerField, FloatField, CharField, ExpressionWrapper

from rest_framework.response import Response
from rest_framework import serializers, status
from rest_framework.decorators import api_view
from rest_framework.pagination import PageNumberPagination

import logging
logger = logging.getLogger('myapp')

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
        logger.error(f'Error in create team: {str(e)}', exc_info=True)
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
        logger.error(f'Error in team list: {str(e)}', exc_info=True)
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, str(e)
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
            
            teams_query = Team.objects.exclude(team_type='Open-team').filter(
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
                is_edit = team.created_by == check_user
                join_league = Leagues.objects.filter(registered_team=team)   
                if join_league:
                    is_edit = False 
                team_data['is_edit'] = is_edit
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
        logger.error(f'Error in my team list: {str(e)}', exc_info=True)
        data["status"] = status.HTTP_200_OK
        data["message"] = str(e)

    return Response(data)



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
            ).exclude(team_type='Open-team').distinct()
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

            paginator = PageNumberPagination()
            paginator.page_size = 10
            paginated_teams = paginator.paginate_queryset(teams_query, request)

            main_data = []
            for team in paginated_teams:
                players = Player.objects.filter(team=team)
                team_rank = sum(float(player.player.rank) if player.player.rank not in ["", "null", None] else 1 for player in players) / max(len(players), 1)
                
                team_data = TeamListSerializer(team).data
                team_data['team_image'] = str(team.team_image) if team.team_image not in ["null", None, "", " "] else None
                team_data['team_uuid'] = team_data.pop('uuid')
                team_data['team_secret_key'] = team_data.pop('secret_key')
                team_data['team_name'] = team_data.pop('name')
                team_data['location'] = team_data.pop('location')
                team_data['team_rank'] = team_rank
                is_edit = team.created_by == check_user
                join_league = Leagues.objects.filter(registered_team=team)   
                if join_league:
                    is_edit = False 
                team_data['is_edit'] = is_edit
                main_data.append(team_data)

            paginated_response = paginator.get_paginated_response(main_data)
            
            data["status"] = status.HTTP_200_OK
            data["count"] = paginated_response.data["count"]
            data["previous"] = paginated_response.data["previous"]
            data["next"] = paginated_response.data["next"]
            data["data"] = paginated_response.data["results"]
            data["message"] = "Data found for Admin" if user.is_admin or user.is_organizer else "Data found"
           
        else:
            data["count"] = 0
            data["previous"] = None
            data["next"] = None
            data["data"] = []
            data['status'] = status.HTTP_401_UNAUTHORIZED
            data['message'] = "Unauthorized access"

    except Exception as e:
        logger.error(f'Error in team list pagination: {str(e)}', exc_info=True)
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
        logger.error(f'Error in team view: {str(e)}', exc_info=True)
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


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
        logger.error(f'Error in team edit: {str(e)}', exc_info=True)
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
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
        logger.error(f'Error in delete team: {str(e)}', exc_info=True)
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


@api_view(('POST',))
def send_team_member_notification(request):
    data = {'status':'','message':''}
    try:
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        team_person = request.data.get('team_person')
        
        app_name = "PICKLEit"
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        subject = f'You are invited to register in {app_name}'
        protocol = 'https' if request.is_secure() else 'http'
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
        logger.error(f'Error in team member notification: {str(e)}', exc_info=True)
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
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
        logger.error(f'Error in team profile details: {str(e)}', exc_info=True)
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
        logger.error(f'Error in team stats: {str(e)}', exc_info=True)
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
        logger.error(f'Error in team match history: {str(e)}', exc_info=True)
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
        logger.error(f'Error in team tournamnet history: {str(e)}', exc_info=True)
        data['status'] = status.HTTP_400_BAD_REQUEST
        data['message'] = f"{e}"
        data['data'] = []
    return Response(data)


