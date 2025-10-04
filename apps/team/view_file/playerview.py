from datetime import timedelta
from math import radians, cos, sin, asin, sqrt
from dateutil.relativedelta import relativedelta
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
from django.contrib.auth.hashers import make_password 
from django.shortcuts import render, get_object_or_404
from django.core.cache.backends.base import DEFAULT_TIMEOUT
from django.db.models.functions import Cast, TruncMonth
from django.db.models import Avg, Sum, Count, Value, F, Q, Case, When, IntegerField, FloatField, CharField, ExpressionWrapper
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.pagination import PageNumberPagination

import logging
logger = logging.getLogger('myapp')


# @api_view(['GET'])
# def player_list_using_pagination(request):
#     data = {'status': '', 'count': '', 'previous': '', 'next': '', 'data': [], 'message': ''}
#     try:
#         user_uuid = request.GET.get('user_uuid')
#         user_secret_key = request.GET.get('user_secret_key')
#         search_text = request.GET.get('search_text')
#         ordering = request.GET.get('ordering')
#         gender = request.GET.get('gender')        
#         start_rank = request.GET.get('start_rank')
#         end_rank = request.GET.get('end_rank')

#         check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
#         if check_user.exists():
#             get_user = check_user.first()
#             if not search_text:
#                 all_players = Player.objects.all()
#             else:
#                 all_players = Player.objects.filter(Q(player_first_name__icontains=search_text) | Q(player_last_name__icontains=search_text))

#             following = AmbassadorsDetails.objects.filter(ambassador=get_user)
#             if following.exists():
#                 following_instance = following.first()
#                 following_ids = list(following_instance.following.all().values_list("id", flat=True))
#             else:
#                 following_instance = AmbassadorsDetails.objects.create(ambassador=get_user)
#                 following_instance.save()
#                 following_ids = list(following_instance.following.all().values_list("id", flat=True))

#             if ordering == 'latest':
#                 all_players = all_players.order_by('-id')  # Order by latest ID
#             elif ordering == 'a-z':
#                 all_players = all_players.order_by('player_first_name') 
#             else:
#                 all_players = all_players.order_by('-id')

#             if gender not in [None, "null", "", "None"]:
#                 all_players = all_players.filter(player__gender__iexact=gender).order_by("-id")

#             if start_rank not in [None, "null", "", "None"] and end_rank not in [None, "null", "", "None"]:
#                 all_players = all_players.filter(player__rank__gte=start_rank, player__rank__lte=end_rank).order_by("-id")

#             #cache implementation
#             if not search_text and not ordering:
#                 players_list = f'player_list'
#                 if cache.get(players_list):
#                     players = cache.get(players_list)
#                 else:
#                     players = all_players
#                     cache.set(players_list, players)
#             elif search_text and not ordering:
#                 search_list = f'{search_text}'
#                 if cache.get(search_list):
#                     players = cache.get(search_list)
#                 else:
#                     players = all_players
#                     cache.set(search_list, players)
#             elif not search_text and ordering:
#                 ordered_list = f'{ordering}'
#                 if cache.get(ordered_list): 
#                     players = cache.get(ordered_list)
#                 else:
#                     players = all_players
#                     cache.set(ordered_list, players)
#             else:
#                 cache_key = f'player_list_{search_text}_{ordering}'
#                 if cache.get(cache_key):
#                     players = cache.get(cache_key)
#                 else:
#                     players = all_players
#                     cache.set(cache_key, players)
                    
#             paginator = PageNumberPagination()
#             paginator.page_size = 10  # Set the page size to 20
#             result_page = paginator.paginate_queryset(all_players, request)
#             serializer = PlayerSerializer(result_page, many=True, context={'request': request})
#             serialized_data = serializer.data
            
#             def add_additional_fields(player_data):
#                 player_data["is_edit"] = player_data["created_by_id"] == get_user.id
#                 player_data["is_follow"] = player_data["player_id"] in following_ids
#                 return player_data

#             serialized_data = list(map(add_additional_fields, serialized_data))
                

#             if not serialized_data:
#                 data["status"] = status.HTTP_200_OK
#                 data["count"] = 0
#                 data["previous"] = None
#                 data["next"] = None
#                 data["data"] = []
#                 data["message"] = "No Result found"
#             else:
#                 paginated_response = paginator.get_paginated_response(serialized_data)
#                 data["status"] = status.HTTP_200_OK
#                 data["count"] = paginated_response.data["count"]
#                 data["previous"] = paginated_response.data["previous"]
#                 data["next"] = paginated_response.data["next"]
#                 data["data"] = paginated_response.data["results"]
#                 data["message"] = "Data found"
#         else:
#             data["count"] = 0
#             data["previous"] = None
#             data["next"] = None
#             data["data"] = []
#             data['status'] = status.HTTP_401_UNAUTHORIZED
#             data['message'] = "Unauthorized access"

#     except Exception as e:
#         logger.error(f'Error in player list: {str(e)}', exc_info=True)
#         data["count"] = 0
#         data["previous"] = None
#         data["next"] = None
#         data["data"] = []
#         data['status'] = status.HTTP_200_OK
#         data['message'] = str(e)

#     return Response(data)

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

            check_player = Player.objects.filter(player_email=get_user.email).first()
            if check_player:
                following_ids = list(check_player.following.all().values_list("id", flat=True))
            else:
                following_ids = []
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
                    players = cache.get(players_list)
                else:
                    players = all_players
                    cache.set(players_list, players)
            elif search_text and not ordering:
                search_list = f'{search_text}'
                if cache.get(search_list):
                    players = cache.get(search_list)
                else:
                    players = all_players
                    cache.set(search_list, players)
            elif not search_text and ordering:
                ordered_list = f'{ordering}'
                if cache.get(ordered_list): 
                    players = cache.get(ordered_list)
                else:
                    players = all_players
                    cache.set(ordered_list, players)
            else:
                cache_key = f'player_list_{search_text}_{ordering}'
                if cache.get(cache_key):
                    players = cache.get(cache_key)
                else:
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
        else:
            data["count"] = 0
            data["previous"] = None
            data["next"] = None
            data["data"] = []
            data['status'] = status.HTTP_401_UNAUTHORIZED
            data['message'] = "Unauthorized access"

    except Exception as e:
        logger.error(f'Error in player list: {str(e)}', exc_info=True)
        data["count"] = 0
        data["previous"] = None
        data["next"] = None
        data["data"] = []
        data['status'] = status.HTTP_200_OK
        data['message'] = str(e)

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
        logger.error(f'Error in player view: {str(e)}', exc_info=True)
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
        
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

            check_player = Player.objects.filter(player_email=get_user.email).first()
            if check_player:
                following_ids = list(check_player.following.all().values_list("id", flat=True))
            else:
                following_ids = []

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
        logger.error(f'Error in my player list: {str(e)}', exc_info=True)
        data["count"] = 0
        data["previous"] = None
        data["next"] = None
        data["data"] = []
        data['status'] = status.HTTP_200_OK
        data['message'] = str(e)

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
        if check_user.exists():
            check_player = Player.objects.filter(uuid=player_uuid,secret_key=player_secret_key)
            if check_player:
                player = check_player.first()
                player_data = check_player.values("id", "player__first_name","player__last_name","player__email","player__rank","player__gender","player__phone","player__image","player__bio")
                get_user = check_user.first()
                ambassador_data = {"follower":player.follower.all().count(),
                                  "following":player.following.all().count(),
                                  "is_follow":get_user in player.follower.all(),
                                  "posts": 0,
                                  "post_data":[]}
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
        logger.error(f'Error in player profile details: {str(e)}', exc_info=True)
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
        logger.error(f'Error in player team details: {str(e)}', exc_info=True)
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
        logger.error(f'Error in player match history: {str(e)}', exc_info=True)
        data['status'] = status.HTTP_400_BAD_REQUEST
        data['match_count'] = []
        data['data_set'] = []
        data['message'] = f'{str(e)}'
    return Response(data)









##not working
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

##not working
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

##not working
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

##not working
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


##not working
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

##not working
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

##not working
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


# Not using
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

