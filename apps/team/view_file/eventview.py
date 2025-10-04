import os
import json
import email
import pytz
from datetime import timedelta
from itertools import combinations
from apps.team.views import notify_edited_player
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

def parse_date(date_str, timezone_):
    if not date_str:
        return None
    try:
        # Parse the naive datetime
        parsed_date = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')

        # Make it aware using the provided timezone or default
        tz = pytz.timezone(timezone_) if timezone_ else timezone.get_default_timezone()
        aware_date = tz.localize(parsed_date)

        # Convert to 'America/New_York' if not already
        if timezone_ != 'America/New_York':
            ny_tz = pytz.timezone('America/New_York')
            aware_date = aware_date.astimezone(ny_tz)

        return aware_date
    except ValueError:
        raise ValueError(
            f"Invalid date format: '{date_str}'. Expected format: YYYY-MM-DD HH:MM:SS (e.g., 2025-05-15 14:30:00)"
        )

#### all event list 
def get_timezone(request, default_tz='America/New_York'):
    """Utility function to get and validate timezone from request."""
    timezone_str = request.GET.get('timezone', default_tz)
    try:
        return pytz.timezone(timezone_str), timezone_str
    except pytz.exceptions.UnknownTimeZoneError:
        logger.warning(f"Invalid timezone provided: {timezone_str}. Falling back to {default_tz}.")
        return pytz.timezone(default_tz), default_tz

def convert_datetime_fields(item_dict, tz, fields):
    """Convert specified datetime fields to the given timezone and format as ISO string."""
    for field in fields:
        if item_dict.get(field):
            try:
                if item_dict[field].tzinfo is None:
                    item_dict[field] = pytz.UTC.localize(item_dict[field])
                item_dict[field] = item_dict[field].astimezone(tz).isoformat()
            except Exception as e:
                logger.error(f"Error converting {field} to timezone {tz.zone}: {str(e)}")
                item_dict[field] = None

class CustomPagination(PageNumberPagination):
    page_size = 7

    def get_previous_page_number(self):
        """Return the previous page number or None if no previous page exists."""
        if self.page.has_previous():
            return self.page.previous_page_number()
        return None

    def get_next_page_number(self):
        """Return the next page number or None if no next page exists."""
        if self.page.has_next():
            return self.page.next_page_number()
        return None

    def get_current_page_number(self, request):
        """Extract the current page number from the request URL."""
        page_query_param = self.page_query_param
        page_number = request.query_params.get(page_query_param, 1)
        try:
            return int(page_number)
        except ValueError:
            return 1

def process_leagues_response(queryset, user, request, tournament_league_ids=None):
    """
    Process a Leagues queryset and return a paginated response with grouped data.
    
    Args:
        queryset: Leagues queryset
        user: User object for organizer checks
        request: HTTP request for pagination and timezone
        tournament_league_ids: Set of league IDs with tournaments (optional, fetched if None)
    
    Returns:
        Dict with status, count, current_page, previous_page, next_page, data, and message
    """
    try:
        tz, timezone_str = get_timezone(request)
        
        if tournament_league_ids is None:
            tournament_league_ids = set(Tournament.objects.values_list('leagues_id', flat=True))

        leagues = queryset.values(
            'id', 'uuid', 'secret_key', 'name', 'location', 'leagues_start_date', 'leagues_end_date',
            'registration_start_date', 'registration_end_date', 'team_type__name', 'team_person__name',
            'play_type', 'any_rank', 'start_rank', 'end_rank', 'latitude', 'longitude', 'image', 'others_fees', 'league_type',
            'registration_fee', 'max_number_team', 'registered_team_count', 'created_by_id'
        )
        current_time = now().astimezone(tz)
        grouped_data = {}
        datetime_fields = ['leagues_start_date', 'leagues_end_date', 'registration_start_date', 'registration_end_date']
        for item in leagues:
            item_dict = dict(item)
            convert_datetime_fields(item_dict, tz, datetime_fields)
            
            is_team_limit_reached = item['max_number_team'] <= item['registered_team_count']
            is_registration_closed = item['registration_end_date'] and current_time > item['registration_end_date'].astimezone(tz)

            item_dict['is_reg_diable'] = not (is_team_limit_reached or is_registration_closed)
            item_dict['main_organizer'] = user.id == item['created_by_id'] if user else False
            item_dict['sub_organizer'] = Leagues.objects.filter(id=item['id']).first().add_organizer.filter(id=user.id).exists() if user else False
            
            key = item['name']
            if key not in grouped_data:
                grouped_data[key] = {
                    'name': item['name'],
                    'registration_start_date': item_dict['registration_start_date'],
                    'location': item['location'],
                    'image': item['image'],
                    'type': [item['team_type__name']] if item['team_type__name'] else [],
                    'data': [item_dict]
                }
            else:
                if item['team_type__name'] and item['team_type__name'] not in grouped_data[key]['type']:
                    grouped_data[key]['type'].append(item['team_type__name'])
                grouped_data[key]['data'].append(item_dict)

        events_list = list(grouped_data.values())
        for item in events_list:
            item['data'] = sorted(item['data'], key=lambda x: x['id'], reverse=True)
            item['is_edit'] = True
            item['is_delete'] = True
        leagues_sorted = sorted(events_list, key=lambda x: x['data'][0]['id'], reverse=True)

        paginator = CustomPagination()
        result_page = paginator.paginate_queryset(leagues_sorted, request)
        current_page = paginator.get_current_page_number(request)

        return {
            'status': status.HTTP_200_OK,
            'count': paginator.page.paginator.count,
            'current_page': current_page,
            'previous_page': paginator.get_previous_page_number(),
            'next_page': paginator.get_next_page_number(),
            'data': result_page,
            'message': 'Data found',
            'timezone': timezone_str
        }

    except Exception as e:
        logger.error(f'Error in process_leagues_response: {str(e)}', exc_info=True)
        return {
            'status': status.HTTP_400_BAD_REQUEST,
            'count': None,
            'current_page': None,
            'previous_page': None,
            'next_page': None,
            'data': [],
            'message': str(e)
        }

@api_view(['GET'])
def list_leagues_admin(request):
    try:
        user_uuid = request.GET.get('user_uuid')
        filter_by = request.GET.get('filter_by', None)
        search_text = request.GET.get('search_text')
        tz, timezone_str = get_timezone(request)

        user = get_object_or_404(User, uuid=user_uuid)
        today_date = datetime.now(tz).date()

        events = Leagues.objects.exclude(team_type__name='Open-team').select_related(
            'team_type', 'team_person', 'created_by'
        ).prefetch_related(
            'registered_team', 'add_organizer'
        ).annotate(
            registered_team_count=Count('registered_team')
        )

        if filter_by == "future":
            events = events.filter(
                Q(registration_start_date__date__lte=today_date, registration_end_date__date__gte=today_date) |
                Q(registration_start_date__date__gte=today_date)
            )
        elif filter_by == "past":
            events = events.filter(leagues_end_date__date__lte=today_date, is_complete=True)
        elif filter_by == "registration_open":
            events = events.filter(
                leagues_start_date__date__lte=today_date,
                leagues_end_date__date__gte=today_date,
                is_complete=False
            )

        if search_text:
            events = events.filter(Q(name__icontains=search_text) & Q(is_created=True))

        response = process_leagues_response(events, user, request)
        return Response(response)

    except Exception as e:
        logger.error(f'Error in list_leagues_admin: {str(e)}', exc_info=True)
        return {
            'status': status.HTTP_400_BAD_REQUEST,
            'count': None,
            'current_page': None,
            'previous_page': None,
            'next_page': None,
            'data': [],
            'message': str(e)
        }

@api_view(['GET'])
def tournament_joined_details(request):
    try:
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        order_by = request.GET.get('order_by')
        tz, _ = get_timezone(request)

        check_user = User.objects.filter(secret_key=user_secret_key, uuid=user_uuid).first()
        if not check_user:
            return {
                'status': status.HTTP_400_BAD_REQUEST,
                'count': None,
                'current_page': None,
                'previous_page': None,
                'next_page': None,
                'data': [],
                'message': 'User not found'
            }

        user = check_user
        today_date = datetime.now(tz).date()

        check_player = Player.objects.filter(player_email=user.email).first()
        if not check_player:
            return {
                'status': status.HTTP_400_BAD_REQUEST,
                'count': None,
                'current_page': None,
                'previous_page': None,
                'next_page': None,
                'data': [],
                'message': 'Player not found'
            }

        player_teams = check_player.team.values_list('id', flat=True)
        all_leagues = Leagues.objects.exclude(
            Q(registration_end_date__date__lte=today_date) | Q(is_complete=True) | Q(leagues_start_date__date__lte=today_date)
        ).filter(
            registered_team__in=player_teams, is_complete=False
        ).select_related(
            'team_type', 'team_person', 'created_by'
        ).prefetch_related(
            'registered_team', 'add_organizer'
        ).annotate(
            registered_team_count=Count('registered_team')
        ).distinct()

        order_mapping = {
            'registration_open_date': 'leagues_start_date',
            'registration_open_name': 'name',
            'registration_open_city': 'city',
            'registration_open_state': 'state',
            'registration_open_country': 'country'
        }
        if order_by in order_mapping:
            all_leagues = all_leagues.order_by(order_mapping[order_by])

        response = process_leagues_response(all_leagues, user, request)
        return Response(response)

    except Exception as e:
        logger.error(f'Error in tournament_joined_details: {str(e)}', exc_info=True)
        return {
            'status': status.HTTP_400_BAD_REQUEST,
            'count': None,
            'current_page': None,
            'previous_page': None,
            'next_page': None,
            'data': [],
            'message': str(e)
        }

@api_view(['GET'])
def tournament_saved_details(request):
    try:
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        order_by = request.GET.get('order_by')
        tz, _ = get_timezone(request)

        check_user = User.objects.filter(secret_key=user_secret_key, uuid=user_uuid).first()
        if not check_user:
            return Response({
                'status': status.HTTP_400_BAD_REQUEST,
                'count': None,
                'current_page': None,
                'previous_page': None,
                'next_page': None,
                'data': [],
                'message': 'User not found'
            }, status=status.HTTP_400_BAD_REQUEST)

        user = check_user
        save_league_ids = SaveLeagues.objects.filter(created_by=user).values_list('ch_league_id', flat=True)
        all_leagues = Leagues.objects.filter(id__in=save_league_ids).select_related(
            'team_type', 'team_person', 'created_by'
        ).prefetch_related(
            'registered_team', 'add_organizer'
        ).annotate(
            registered_team_count=Count('registered_team')
        )

        order_mapping = {
            'registration_open_date': 'leagues_start_date',
            'registration_open_name': 'name',
            'registration_open_city': 'city',
            'registration_open_state': 'state',
            'registration_open_country': 'country'
        }
        if order_by in order_mapping:
            all_leagues = all_leagues.order_by(order_mapping[order_by])

        response = process_leagues_response(all_leagues, user, request)
        return Response(response)

    except Exception as e:
        logger.error(f'Error in tournament_saved_details: {str(e)}', exc_info=True)
        return Response({
            'status': status.HTTP_400_BAD_REQUEST,
            'count': None,
            'current_page': None,
            'previous_page': None,
            'next_page': None,
            'data': [],
            'message': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
def open_play_details(request):
    try:
        user_uuid = request.GET.get('user_uuid')
        search_text = request.GET.get('search_text', '').strip()  # Get search_text, default to empty string
        tz, _ = get_timezone(request)
        user = get_object_or_404(User, uuid=user_uuid)

        invited_league_ids = OpenPlayInvitation.objects.filter(
            user=user
        ).exclude(status='Declined').values_list('event_id', flat=True).distinct()

        check_player = Player.objects.filter(player=user).first()
        team_ids = check_player.team.values_list('id', flat=True) if check_player else []
        all_leagues = Leagues.objects.filter(
            Q(is_complete=False) & 
            (Q(registered_team__id__in=team_ids) | Q(created_by=user)),
            team_type__name="Open-team"
        )

        # Apply search filter if search_text is provided
        leagues = Leagues.objects.filter(
            Q(id__in=invited_league_ids) | Q(id__in=all_leagues.values_list('id', flat=True))
        )
        if search_text:
            leagues = leagues.filter(name__icontains=search_text)  # Case-insensitive search on league name

        leagues = leagues.select_related(
            'team_type', 'team_person', 'created_by'
        ).prefetch_related(
            'registered_team', 'add_organizer'
        ).annotate(
            registered_team_count=Count('registered_team')
        ).distinct()

        response = process_leagues_response(leagues, user, request)
        return Response(response)

    except Exception as e:
        logger.error(f'Error in open_play_details: {str(e)}', exc_info=True)
        return Response({
            'status': status.HTTP_400_BAD_REQUEST,
            'count': None,
            'current_page': None,
            'previous_page': None,
            'next_page': None,
            'data': [],
            'message': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
def tournament_joined_completed_details(request):
    try:
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        order_by = request.GET.get('order_by')
        tz, _ = get_timezone(request)

        check_user = User.objects.filter(secret_key=user_secret_key, uuid=user_uuid).first()
        if not check_user:
            return {
                'status': status.HTTP_400_BAD_REQUEST,
                'count': None,
                'current_page': None,
                'previous_page': None,
                'next_page': None,
                'data': [],
                'message': 'User not found'
            }

        user = check_user
        if not (user.is_coach or user.is_team_manager or user.is_organizer):
            return {
                'status': status.HTTP_400_BAD_REQUEST,
                'count': None,
                'current_page': None,
                'previous_page': None,
                'next_page': None,
                'data': [],
                'message': 'User does not have required permissions'
            }

        check_player = Player.objects.filter(player_email=user.email).first()
        if not check_player:
            return {
                'status': status.HTTP_400_BAD_REQUEST,
                'count': None,
                'current_page': None,
                'previous_page': None,
                'next_page': None,
                'data': [],
                'message': 'Player not found'
            }

        team_ids = check_player.team.values_list('id', flat=True)
        all_leagues = Leagues.objects.filter(
            Q(registered_team__id__in=team_ids, is_complete=True) |
            Q(add_organizer__id=user.id, is_complete=True) |
            Q(created_by=user, is_complete=True)
        ).select_related(
            'team_type', 'team_person', 'created_by'
        ).prefetch_related(
            'registered_team', 'add_organizer'
        ).annotate(
            registered_team_count=Count('registered_team')
        ).distinct()

        order_mapping = {
            'registration_open_date': 'leagues_start_date',
            'registration_open_name': 'name',
            'registration_open_city': 'city',
            'registration_open_state': 'state',
            'registration_open_country': 'country'
        }
        if order_by in order_mapping:
            all_leagues = all_leagues.order_by(order_mapping[order_by])

        response = process_leagues_response(all_leagues, user, request)
        return Response(response)

    except Exception as e:
        logger.error(f'Error in tournament_joined_completed_details: {str(e)}', exc_info=True)
        return {
            'status': status.HTTP_400_BAD_REQUEST,
            'count': None,
            'current_page': None,
            'previous_page': None,
            'next_page': None,
            'data': [],
            'message': str(e)
        }   

@api_view(['GET'])
def my_league(request):
    """
    Retrieve leagues created by the user with pagination and timezone support.
    
    Args:
        request: HTTP request containing user_uuid, filter_by, and search_text.
    
    Returns:
        Response with status, count, current_page, previous_page, next_page, data, message, and timezone.
    """
    try:
        user_uuid = request.GET.get('user_uuid')
        filter_by = request.GET.get('filter_by', None)
        search_text = request.GET.get('search_text')
        tz, timezone_str = get_timezone(request)

        user = get_object_or_404(User, uuid=user_uuid)
        today_date = datetime.now(tz).date()

        # Optimize query with select_related, prefetch_related, and annotate
        events = Leagues.objects.filter(created_by=user).exclude(team_type__name='Open-team').select_related(
            'team_type', 'team_person', 'created_by'
        ).prefetch_related(
            'registered_team', 'add_organizer'
        ).annotate(
            registered_team_count=Count('registered_team')
        )

        # Apply filters
        if filter_by == "future":
            events = events.filter(
                Q(registration_start_date__date__lte=today_date, registration_end_date__date__gte=today_date) |
                Q(registration_start_date__date__gte=today_date)
            )
        elif filter_by == "past":
            events = events.filter(leagues_end_date__date__lte=today_date, is_complete=True)
        elif filter_by == "registration_open":
            events = events.filter(
                leagues_start_date__date__lte=today_date,
                leagues_end_date__date__gte=today_date,
                is_complete=False
            )

        if search_text:
            events = events.filter(Q(name__icontains=search_text) & Q(is_created=True)).order_by('-id')

        # Fetch tournament league IDs for is_reg_diable logic
        tournament_league_ids = set(Tournament.objects.values_list('leagues_id', flat=True))

        # Process the queryset using the shared utility function
        response = process_leagues_response(events, user, request, tournament_league_ids)

        # Add timezone to response
        response['timezone'] = timezone_str

        return Response(response)

    except Exception as e:
        logger.error(f'Error in my_league: {str(e)}', exc_info=True)
        return Response({
            'status': status.HTTP_400_BAD_REQUEST,
            'count': None,
            'current_page': None,
            'previous_page': None,
            'next_page': None,
            'data': [],
            'message': str(e),
            'timezone': get_timezone(request)[1]  # Default timezone in case of error
        })


### optimize code


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
        logger.error(f'Error in home page open event show: {str(e)}', exc_info=True)
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
        logger.error(f'Error in event save completed details: {str(e)}', exc_info=True)
        data['status'], data['data'], data['message'] = status.HTTP_400_BAD_REQUEST, [], f"{e}"
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
        timezone_ = request.data.get('timezone', 'America/New_York')
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
        invited_code = request.data.get('invited_code', None)
        latitude = request.data.get('latitude', None)
        longitude = request.data.get('longitude', None)
        start_rank = request.data.get('start_rank') 
        end_rank = request.data.get('end_rank')       
        
        if int(max_number_team) % 2 != 0 or int(max_number_team) == 0 or int(max_number_team) == 1:
            data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "Max number of team must be even"
            return Response(data)
        leagues_start_date = parse_date(leagues_start_date, timezone_) or None
        leagues_end_date = parse_date(leagues_end_date, timezone_) or None
        registration_start_date = parse_date(registration_start_date, timezone_) or None
        registration_end_date = parse_date(registration_end_date, timezone_) or None
        
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        leagues_id = []
        if check_user.exists():
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
                                    city=city,max_number_team=max_number_team, play_type=play_type,
                                    registration_fee=registration_fee,description=description,image=image,league_type=league_type)
                if league_type == "Invites only":
                    save_leagues.invited_code = invited_code 
                cleaned_others_fees = {k: v for k, v in others_fees.items() if k and v is not None}
                save_leagues.others_fees = cleaned_others_fees
                # save_leagues.others_fees = others_fees
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
            logger.warning('No user data provided in the request in create enent')
            data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "User not found."
    except Exception as e :
        logger.error(f'Error in create event: {str(e)}', exc_info=True)
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
        logger.error(f'Error in view match result: {str(e)}', exc_info=True)
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, str(e)
    return Response(data)

@api_view(['GET'])
def view_leagues_for_edit(request):
    response = {
        'data': [],
        'name': None,
        'person_type': None,
        'play_type':None,
        'team_type': None,
        'max_number_team': None,
        'location': None,
        'latitude': None,
        'longitude': None,
        'leagues_start_date': None,
        'leagues_end_date': None,
        'registration_start_date': None,
        'registration_end_date': None,
        'tournament_details': [],
        'status': '',
        'message': '',
    }

    try:
        user_uuid = request.GET.get('user_uuid')
        league_uuid = request.GET.get('league_uuid')

        if not user_uuid or not league_uuid:
            raise ValueError("Both 'user_uuid' and 'league_uuid' are required.")

        user = get_object_or_404(User, uuid=user_uuid)
        league = get_object_or_404(Leagues, uuid=league_uuid)

        t_details = LeaguesPlayType.objects.filter(league_for=league)
        if t_details.exists():
            playtype = t_details.first()
            data_structure = playtype.data
        else:
            data_structure = [
                {"name": "Round Robin", "number_of_courts": 0, "sets": 0, "point": 0, "is_show": True},
                {"name": "Elimination", "number_of_courts": 0, "sets": 0, "point": 0, "is_show": True},
                {"name": "Final", "number_of_courts": 0, "sets": 0, "point": 0, "is_show": True}
            ]

        response.update({
            'name': league.name,
            'person_type': league.team_person.name,
            'team_type': league.team_type.name,
            'play_type':league.play_type,
            'max_number_team': league.max_number_team,
            'location': league.location,
            'latitude': league.latitude,
            'longitude': league.longitude,
            'leagues_start_date': league.leagues_start_date,
            'leagues_end_date': league.leagues_end_date,
            'registration_start_date': league.registration_start_date,
            'registration_end_date': league.registration_end_date,
            'tournament_details': data_structure,
            'status': status.HTTP_200_OK,
            'message': "Data Found"
        })

    except Exception as e:
        response['status'] = status.HTTP_400_BAD_REQUEST
        response['message'] = str(e)
        logger.error(f'Error in event edit: {str(e)}', exc_info=True)
    return Response(response)


@api_view(['POST'])
def edit_leagues(request):
    response = {'status': '', 'message': ''}

    try:
        user_uuid = request.data.get('user_uuid')
        league_uuid = request.data.get('league_uuid')
        timezone_ = request.data.get('timezone', 'America/New_York')
        if not user_uuid or not league_uuid:
            raise ValueError("Both 'user_uuid' and 'league_uuid' are required.")

        user = get_object_or_404(User, uuid=user_uuid)
        league = get_object_or_404(Leagues, uuid=league_uuid)

        # Parse JSON data list
        total_data = request.data.get('data')
        if isinstance(total_data, str):
            data_list = json.loads(total_data) if total_data else []
        elif isinstance(total_data, list):
            data_list = total_data
        else:
            data_list = []

        # Update PlayType data
        LeaguesPlayType.objects.update_or_create(
            league_for=league,
            defaults={'data': data_list}
        )

        # Optional fields
        max_number_team = request.data.get('max_number_team')
        league.leagues_start_date = parse_date(request.data.get('leagues_start_date'), timezone_) or league.leagues_start_date
        league.leagues_end_date = parse_date(request.data.get('leagues_end_date'), timezone_) or league.leagues_end_date
        league.registration_start_date = parse_date(request.data.get('registration_start_date'), timezone_) or league.registration_start_date
        league.registration_end_date = parse_date(request.data.get('registration_end_date'), timezone_) or league.registration_end_date

        if max_number_team:
            league.max_number_team = int(max_number_team)

        league.save()

        response['status'] = status.HTTP_200_OK
        response['message'] = "Your Event updated successfully"

    except Exception as e:
        response['status'] = status.HTTP_400_BAD_REQUEST
        response['message'] = str(e)
        logger.error(f'Error in edit event for user {user_uuid}, league {league_uuid}: {str(e)}', exc_info=True)
    return Response(response)


def determine_match_winner(team1_points, team2_points, total_sets):
    """
    Determine set winners and overall match winner based on points per set.
    Returns:
        tuple: ([list of set winners], overall winner), e.g., (['t1', 't1', 't2'], 't1').
    """
    if len(team1_points) != len(team2_points):
        raise ValueError("Both teams must have the same number of set points.")

    set_winners = []
    team1_sets_won = 0
    team2_sets_won = 0

    for set_idx in range(len(team1_points)):
        if team1_points[set_idx] > team2_points[set_idx]:
            set_winners.append('t1')
            team1_sets_won += 1
        elif team2_points[set_idx] > team1_points[set_idx]:
            set_winners.append('t2')
            team2_sets_won += 1
        else:
            set_winners.append('draw')

    if team1_sets_won > team2_sets_won:
        match_winner = 't1'
    elif team2_sets_won > team1_sets_won:
        match_winner = 't2'
    else:
        match_winner = 'draw'

    return set_winners, match_winner

@api_view(['POST'])
def set_tournamens_result(request):
    data = {'status': '', 'data': [], 'message': ''}

    try:
        user_uuid = request.data.get('user_uuid')
        league_uuid = request.data.get('league_uuid')
        tournament_uuid = request.data.get('tournament_uuid')
        team1_point = request.data.get('team1_point')
        team2_point = request.data.get('team2_point')
        set_number = request.data.get('set_number')

        user = get_object_or_404(User, uuid=user_uuid)
        event = get_object_or_404(Leagues, uuid=league_uuid)
        tournament = get_object_or_404(Tournament, uuid=tournament_uuid)

        team1_point_list = [int(x) for x in team1_point.split(",")]
        team2_point_list = [int(x) for x in team2_point.split(",")]
        set_number_list = set_number.split(",")

        organizer_list = [event.created_by.id] + list(event.add_organizer.all().values_list("id", flat=True))

        team1_p_list = list(Player.objects.filter(team=tournament.team1).values_list("player_id", flat=True)) + [tournament.team1.created_by.id] if tournament.team1 else []
        team2_p_list = list(Player.objects.filter(team=tournament.team2).values_list("player_id", flat=True)) + [tournament.team2.created_by.id] if tournament.team2 else []

        user_type = None
        if user.id in organizer_list:
            user_type = "Organizer"
        elif user.id in team1_p_list:
            user_type = "Team1"
        elif user.id in team2_p_list:
            user_type = "Team2"

        if not user_type:
            data["status"] = status.HTTP_403_FORBIDDEN
            data["message"] = "You are not authorized to update the score"
            return Response(data)

        # Always clear old results
        TournamentSetsResult.objects.filter(tournament=tournament).delete()

        set_winner_list, final_winner = determine_match_winner(team1_point_list, team2_point_list, len(set_number_list))

        # Save each set result
        for set_index in range(1, len(set_number_list) + 1):
            t1_score = team1_point_list[set_index - 1]
            t2_score = team2_point_list[set_index - 1]
            winner_flag = set_winner_list[set_index - 1]

            score_obj = TournamentSetsResult.objects.create(
                tournament=tournament,
                set_number=set_index,
                team1_point=t1_score,
                team2_point=t2_score,
                is_completed=True
            )

            if winner_flag == "t1":
                score_obj.win_team = tournament.team1
            elif winner_flag == "t2":
                score_obj.win_team = tournament.team2

            score_obj.save()

        if final_winner == 't1':
            winner = tournament.team1
            looser = tournament.team2
            winner_sets = set_winner_list.count('t1')
            loser_sets = set_winner_list.count('t2')
        elif final_winner == 't2':
            winner = tournament.team2
            looser = tournament.team1
            winner_sets = set_winner_list.count('t2')
            loser_sets = set_winner_list.count('t1')
        else:
            winner = None
            looser = None
            winner_sets = 0
            loser_sets = 0

            data["status"] = status.HTTP_400_BAD_REQUEST
            data["message"] = "Match result could not be determined"
            return Response(data)

        # Update tournament record
        tournament.winner_team = winner
        tournament.loser_team = looser
        tournament.winner_team_score = str(winner_sets)
        tournament.loser_team_score = str(loser_sets)
        tournament.is_completed = True if user_type == "Organizer" else False

        title = "Match score update"
        message_win = f"Wow, you have won the match {tournament.match_number}."
        message_lose = f"Sorry, you have lost the match {tournament.match_number}."
        org_message = f"{winner.name} has won the match {tournament.match_number} of league {event.name}."

        # Notify players and organizers
        if final_winner == "t1":
            winner_list = team1_p_list
            loser_list = team2_p_list
        else:
            winner_list = team2_p_list
            loser_list = team1_p_list

        for user_id in winner_list:
            notify_edited_player(user_id, title, message_win)
        for user_id in loser_list:
            notify_edited_player(user_id, title, message_lose)
        for user_id in organizer_list:
            notify_edited_player(user_id, title, org_message)

        tournament.save()

        # Update event winner if needed
        if tournament.match_type in ["final", "Individual Match Play"] and user.id in organizer_list:
            event.winner_team = winner
            event.save()

        data["status"] = status.HTTP_200_OK
        data["message"] = "Successfully updated the score"

    except Exception as e:
        logger.error(f'Error in save match result: {str(e)}', exc_info=True)
        data['status'] = status.HTTP_400_BAD_REQUEST
        data['message'] = f"Error occurred: {str(e)}"

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
            main_org = list(User.objects.filter(id=league.created_by.id).values_list('id', flat=True))
            sub_org_list = list(league.add_organizer.all().values_list("id", flat=True))
            org_list = main_org +  sub_org_list

            if (tournament_obj.team1.created_by == get_user) or (tournament_obj.team2.created_by == get_user) or (get_user.id in team1_p_list) or (get_user.id in team2_p_list) and get_user.id not in org_list:
                check_approval = TournamentScoreApproval.objects.filter(tournament=tournament_obj)
                if check_approval.exists():
                    if (tournament_obj.team1.created_by == get_user) or (get_user.id in team1_p_list):
                        check_approval.update(team1_approval = True)                        
                    else:
                        check_approval.update(team2_approval = True)

                else:
                    if (tournament_obj.team1.created_by == get_user) or (get_user.id in team1_p_list):
                        TournamentScoreApproval.objects.create(tournament=tournament_obj, team1_approval = True)                        
                    else:
                        TournamentScoreApproval.objects.create(tournament=tournament_obj, team2_approval = True)
                data["status"], data["message"] = status.HTTP_200_OK, f"The scores of the match {tournament_obj.match_number} has been successfully approved by you." 

            elif get_user.id in org_list:
                check_approval = TournamentScoreApproval.objects.filter(tournament=tournament_obj)  
                if check_approval.exists():
                    check_approval.update(team1_approval=True, team2_approval=True, organizer_approval=True)  

                    tournament_obj.is_completed = True
                    tournament_obj.save()
                else:
                    TournamentScoreApproval.objects.create(tournament=tournament_obj, team1_approval=True, team2_approval=True, organizer_approval=True) 
                    tournament_obj.is_completed = True
                    tournament_obj.save()
                    #for notification                  

                    title = "Match score update"
                    if not tournament_obj.is_drow:                            
                        message = f"Wow, you have won the match {tournament_obj.match_number}, the scores are approved"
                        message2 = f"Sorry, you have lost the match {tournament_obj.match_number}, the scores are approved"
                        
                        winner_player = list(Player.objects.filter(team__id=tournament_obj.winner_team.id).values_list("player_id", flat=True))
                        
                        if tournament_obj.winner_team.created_by.id not in winner_player:
                            winner_player.append(tournament_obj.winner_team.created_by.id)

                        if len(winner_player) > 0:
                            for user_id in winner_player:                            
                                notify_edited_player(user_id, title, message)
                                
                        looser_player = list(Player.objects.filter(team__id=tournament_obj.loser_team.id).values_list("player_id", flat=True))
                        
                        if tournament_obj.loser_team.created_by.id not in looser_player:
                            looser_player.append(tournament_obj.loser_team.created_by.id)

                        if len(looser_player) > 0:
                            for user_id in looser_player:                                
                                notify_edited_player(user_id, title, message2)

                        org_message = f"{tournament_obj.winner_team.name} has won the match {tournament_obj.match_number} of league {tournament_obj.leagues.name}"
                        for user_id in org_list:
                            notify_edited_player(user_id, title, org_message)
                    else:                            
                        message = f"The match {tournament_obj.match_number} was drawn, the scores are approved"                        
                        team_one_player_list = list(Player.objects.filter(team__id = tournament_obj.team1.id).values_list("player_id", flat=True))
                        team_two_player_list = list(Player.objects.filter(team__id = tournament_obj.team2.id).values_list("player_id", flat=True))

                        if tournament_obj.team1.created_by.id not in team_one_player_list:
                            team_one_player_list.append(tournament_obj.team1.created_by.id)

                        for user_id in team_one_player_list:                            
                            notify_edited_player(user_id, title, message)

                        if tournament_obj.team2.created_by.id not in team_two_player_list:
                            team_two_player_list.append(tournament_obj.team2.created_by.id)

                        for user_id in team_two_player_list:
                            notify_edited_player(user_id, title, message) 
                        
                        org_message = f"The match {tournament_obj.match_number} of league {tournament_obj.leagues.name} was drawn."
                        for user_id in org_list:
                            notify_edited_player(user_id, title, org_message)

                data["status"], data["message"] = status.HTTP_200_OK, f"The scores of the match {tournament_obj.match_number} has been successfully approved."     
            else:
                data["status"], data["message"] = status.HTTP_200_OK, "You can't approve the score"
        else:
            data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "User or Tournament not found."

    except Exception as e:
        logger.error(f'Error in approved result: {str(e)}', exc_info=True)
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
                main_org = list(User.objects.filter(id=league.created_by.id).values_list('id', flat=True))
                sub_org_list = list(league.add_organizer.all().values_list("id", flat=True))
                org_list = main_org +  sub_org_list

                title = "Match score report"
                message = f'{get_user.first_name} {get_user.last_name} has reported the scores of match {tournament_obj.match_number} of league {tournament_obj.leagues.name}. Please resolve this and update the score.'
                for user_id in org_list:
                    notify_edited_player(user_id, title, message)

                player_list = team1_p_list + team2_p_list
                if tournament_obj.team2.created_by.id not in player_list:
                    player_list.append(tournament_obj.team2.created_by.id)
                
                if tournament_obj.team1.created_by.id not in player_list:
                    player_list.append(tournament_obj.team1.created_by.id)

                title = "Match score report"
                message = f'{get_user.first_name} {get_user.last_name} has reported the scores of match {tournament_obj.match_number} of league {tournament_obj.leagues.name}.'
                for user_id in player_list:
                    notify_edited_player(user_id, title, message)

                data["status"], data["message"] = status.HTTP_200_OK, f"You have successfully reported the scores of match {tournament_obj.match_number}"
            else:
                data["status"], data["message"] = status.HTTP_200_OK, "You can't report the score"
        else:
            data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "User or Tournament not found."

    except Exception as e:
        logger.error(f'Error in report match score in event: {str(e)}', exc_info=True)
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, str(e)
    return Response(data)



##### new assign match section
def calculate_team_rank(team):
    """Calculate average rank of a team based on its players."""
    players = team.player_set.all()
    if not players.exists():
        return 0
    total_rank = sum(float(player.player.rank or '1') for player in players)
    return total_rank / players.count()

def create_group(team_ids, num_parts):
    """Create balanced groups from team IDs based on team ranks."""
    num_parts = int(num_parts)
    if num_parts <= 0:
        return "Number of parts should be greater than zero."
    
    teams = Team.objects.filter(id__in=team_ids)
    team_ranks = [(team.id, calculate_team_rank(team)) for team in teams]
    team_ranks.sort(key=lambda x: x[1], reverse=True)
    sorted_team_ids = [team_id for team_id, _ in team_ranks]
    total_teams = len(sorted_team_ids)
    
    teams_per_group = total_teams // num_parts
    remainder = total_teams % num_parts
    groups = [[] for _ in range(num_parts)]
    
    for i, team_id in enumerate(sorted_team_ids):
        group_idx = i % num_parts
        groups[group_idx].append(team_id)
    
    max_group_size = teams_per_group + (1 if remainder > 0 else 0)
    for i in range(num_parts):
        groups[i] = groups[i][:max_group_size]
    
    print(groups)
    return groups

def make_shuffle(input_list):
    """Shuffle pairs of teams to create matchups (A1, B2, A2, B1 pattern)."""
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

def notify_tournament_start(league, teams):
    """Send tournament start notifications to team managers and players."""
    league_name = league.name
    try:
        for team_id in teams:
            team = Team.objects.get(id=team_id)
            team_manager = team.created_by
            notify_edited_player(
                team_manager.id,
                "Start Tournament",
                f"The tournament {league_name}, has started."
            )
            for player in Player.objects.filter(team__id=team_id):
                notify_edited_player(
                    player.player.id,
                    "Start Tournament",
                    f"Player, get ready! The tournament {league_name}, has started."
                )
    except Exception:
        pass

def create_tournament_match(league, team1_id, team2_id, match_type, round_number, court_num, sets, points, match_number, group_id=None):
    """Create a single tournament match with given parameters."""
    obj = GenerateKey()
    secret_key = obj.generate_league_unique_id()
    Tournament.objects.create(
        set_number=sets,
        court_num=court_num,
        points=points,
        court_sn=court_num,
        match_number=match_number,
        secret_key=secret_key,
        leagues=league,
        team1_id=team1_id,
        team2_id=team2_id,
        match_type=match_type,
        elimination_round=round_number,
        group_id=group_id
    )

def handle_single_elimination(data, league, team_ids, elimination, final):
    """Handle Single Elimination tournament logic."""
    try:
        tournaments = Tournament.objects.filter(leagues=league)
        if tournaments.exists():
            completed = tournaments.filter(is_completed=True)
            if len(tournaments) == len(completed) and completed.exists():
                winners = list(completed.order_by('-match_number').values_list("winner_team_id", flat=True))
                pre_round = completed.last().elimination_round
                match_number = completed.last().match_number
                court_num = 0
                
                if len(winners) == 4:
                    settings, match_type = elimination, "Semi Final"
                elif len(winners) == 2:
                    settings, match_type = final, "Final"
                else:
                    settings, match_type = elimination, "Elimination Round"
                    pre_round += 1
                
                random.shuffle(winners)
                for i in range(0, len(winners), 2):
                    court_num = (court_num % settings["courts"]) + 1
                    create_tournament_match(
                        league, winners[i], winners[i+1], match_type, 0,
                        court_num, settings["sets"], settings["points"], match_number + 1
                    )
                    match_number += 1
                data.update({
                    "status": status.HTTP_200_OK,
                    "message": f"Matches created for {match_type}"
                })
            else:
                data.update({
                    "status": status.HTTP_200_OK,
                    "message": "Previous Round is not completed or not updated"
                })
        else:
            settings, match_type = elimination, "Elimination Round"
            if len(team_ids) == 4:
                settings, match_type = elimination, "Semi Final"
            elif len(team_ids) == 2:
                settings, match_type = final, "Final"
            
            random.shuffle(team_ids)
            court_num = 0
            match_number = 0
            for i in range(0, len(team_ids), 2):
                court_num = (court_num % settings["courts"]) + 1
                create_tournament_match(
                    league, team_ids[i], team_ids[i+1], match_type, 1 if match_type == "Elimination Round" else 0,
                    court_num, settings["sets"], settings["points"], match_number + 1
                )
                match_number += 1
            data.update({
                "status": status.HTTP_200_OK,
                "message": f"Matches created for {match_type}"
            })
        return Response(data)
    except Exception as e:
        logger.error(f'Error in assign match Single elimination: {str(e)}', exc_info=True)
        data.update({
            "status": status.HTTP_200_OK,
            "message": f"Bad Request error: {str(e)}"
        })
        return Response(data)

def handle_group_stage(data, league, team_ids, round_robin, elimination, final):
    """Handle Group Stage tournament logic."""
    try:
        tournaments = Tournament.objects.filter(leagues=league)
        if tournaments.exists():
            completed = tournaments.filter(is_completed=True)
            if tournaments.count() == completed.count():
                last_match = tournaments.last()
                if last_match.match_type == "Round Robin":
                    groups = RoundRobinGroup.objects.filter(league_for=league)
                    teams = []
                    for group in groups:
                        group_teams = group.all_teams.all()
                        scores = []
                        for team in group_teams:
                            matches = tournaments.filter(Q(team1=team) | Q(team2=team))
                            completed_matches = matches.filter(is_completed=True)
                            wins = completed_matches.filter(winner_team=team).count()
                            losses = completed_matches.filter(loser_team=team).count()
                            draws = len(completed_matches) - (wins + losses)
                            points = (wins * 3) + draws
                            for_score, against_score = 0, 0
                            for match in matches:
                                sets = TournamentSetsResult.objects.filter(tournament_id=match.id)
                                if match.team1 == team:
                                    for_score += sum(sets.values_list("team1_point", flat=True))
                                    against_score += sum(sets.values_list("team2_point", flat=True))
                                else:
                                    for_score += sum(sets.values_list("team2_point", flat=True))
                                    against_score += sum(sets.values_list("team1_point", flat=True))
                            scores.append({
                                "uuid": team.uuid,
                                "secret_key": team.secret_key,
                                "point": points,
                                "for_score": for_score
                            })
                        top_teams = sorted(scores, key=lambda x: (x['point'], x['for_score']), reverse=True)[:2]
                        group_winners = [Team.objects.get(uuid=t["uuid"], secret_key=t["secret_key"]).id for t in top_teams]
                        teams.append(group_winners)
                        RoundRobinGroup.objects.filter(id=group.id).update(
                            seleced_teams=Team.objects.get(uuid=top_teams[0]["uuid"], secret_key=top_teams[0]["secret_key"])
                        )
                    
                    if len(teams) != len(groups):
                        data.update({
                            "status": status.HTTP_200_OK,
                            "message": "Not all groups have winners selected"
                        })
                        return Response(data)
                    
                    teams = make_shuffle(teams)
                    match_type, settings, round_number = "Elimination Round", elimination, 1
                    if len(teams) == 2:
                        match_type, settings, round_number = "Final", final, 0
                    elif len(teams) == 4:
                        match_type, settings, round_number = "Semi Final", elimination, 0
                    
                    court_num = 0
                    match_number = last_match.match_number
                    for i in range(0, len(teams), 2):
                        court_num = (court_num % settings["courts"]) + 1
                        create_tournament_match(
                            league, teams[i], teams[i+1], match_type, round_number,
                            court_num, settings["sets"], settings["points"], match_number + 1
                        )
                        match_number += 1
                    data.update({
                        "status": status.HTTP_200_OK,
                        "message": f"Matches are created for {match_type}"
                    })
                elif last_match.match_type == "Elimination Round":
                    winners = list(tournaments.filter(elimination_round=last_match.elimination_round).values_list("winner_team_id", flat=True))
                    if len(winners) != len(tournaments.filter(elimination_round=last_match.elimination_round)):
                        data.update({
                            "status": status.HTTP_200_OK,
                            "message": "Not all groups have winners selected"
                        })
                        return Response(data)
                    
                    match_type, settings, round_number = "Elimination Round", elimination, last_match.elimination_round + 1
                    if len(winners) == 2:
                        match_type, settings, round_number = "Final", final, 0
                    elif len(winners) == 4:
                        match_type, settings, round_number = "Semi Final", elimination, 0
                    
                    random.shuffle(winners)
                    court_num = 0
                    match_number = last_match.match_number
                    for i in range(0, len(winners), 2):
                        court_num = (court_num % settings["courts"]) + 1
                        create_tournament_match(
                            league, winners[i], winners[i+1], match_type, round_number,
                            court_num, settings["sets"], settings["points"], match_number + 1
                        )
                        match_number += 1
                    data.update({
                        "status": status.HTTP_200_OK,
                        "message": f"Matches are created for {match_type} {round_number}"
                    })
                elif last_match.match_type == "Semi Final":
                    winners = list(tournaments.filter(match_type="Semi Final").values_list('winner_team_id', flat=True))
                    if len(winners) != 2:
                        data.update({
                            "status": status.HTTP_200_OK,
                            "message": "Not all groups have winners selected"
                        })
                        return Response(data)
                    
                    random.shuffle(winners)
                    create_tournament_match(
                        league, winners[0], winners[1], "Final", 0,
                        1, final["sets"], final["points"], last_match.match_number + 1
                    )
                    data.update({
                        "status": status.HTTP_200_OK,
                        "message": "Matches are created for Final"
                    })
                elif last_match.match_type == "Final":
                    data.update({
                        "status": status.HTTP_200_OK,
                        "message": "The event results are out! The event is completed successfully."
                    })
            else:
                data.update({
                    "status": status.HTTP_200_OK,
                    "message": "All matches in this round are not completed yet."
                })
        else:
            groups = create_group(team_ids, round_robin["courts"])
            round_robin_groups = RoundRobinGroup.objects.filter(league_for=league)
            if round_robin_groups.exists() and len(round_robin_groups) == round_robin["courts"]:
                data.update({
                    "status": status.HTTP_200_OK,
                    "message": f"Round Robin matches already created for {league.name}"
                })
                return Response(data)
            elif round_robin_groups.exists():
                for group in round_robin_groups:
                    Tournament.objects.filter(group_id=group.id).delete()
                    group.delete()
            
            serial_number = 0
            for index, group_teams in enumerate(groups, start=1):
                group = RoundRobinGroup.objects.create(court=index, league_for=league, number_sets=round_robin["sets"])
                for team_id in group_teams:
                    group.all_teams.add(Team.objects.get(id=team_id))
                
                match_combinations = [(t1, t2) for i, t1 in enumerate(group_teams) for t2 in group_teams[i+1:]]
                random.shuffle(match_combinations)
                for team1, team2 in match_combinations:
                    serial_number += 1
                    create_tournament_match(
                        league, team1, team2, "Round Robin", 0,
                        index, round_robin["sets"], round_robin["points"], serial_number, group.id
                    )
            data.update({
                "status": status.HTTP_200_OK,
                "message": "Matches are created successfully"
            })
        return Response(data)
    except Exception as e:
        logger.error(f'Error in assign match Group stage : {str(e)}', exc_info=True)
        data.update({
            "status": status.HTTP_200_OK,
            "message": f"Bad Request error: {str(e)}"
        })
        return Response(data)

def handle_round_robin(data, league, team_ids, round_robin, play_type):
    try:
        """Handle Round Robin tournament logic."""
        groups = create_group(team_ids, 1)
        round_robin_groups = RoundRobinGroup.objects.filter(league_for=league)
        if round_robin_groups.exists() and len(round_robin_groups) == 1:
            data.update({
                "status": status.HTTP_200_OK,
                "message": f"Round Robin group already created for {league.name}"
            })
            return Response(data)
        elif round_robin_groups.exists():
            for group in round_robin_groups:
                Tournament.objects.filter(group_id=group.id).delete()
                group.delete()
        
        serial_number = 0
        for index, group_teams in enumerate(groups, start=1):
            group = RoundRobinGroup.objects.create(court=index, league_for=league, number_sets=round_robin["sets"])
            for team_id in group_teams:
                group.all_teams.add(Team.objects.get(id=team_id))
            
            match_combinations = [(t1, t2) for i, t1 in enumerate(group_teams) for t2 in group_teams[i+1:]]
            random.shuffle(match_combinations)
            for team1, team2 in match_combinations:
                serial_number += 1
                create_tournament_match(
                    league, team1, team2, "Round Robin", 0,
                    index, round_robin["sets"], round_robin["points"], serial_number, group.id
                )
        data.update({
            "status": status.HTTP_200_OK,
            "message": f"Matches created for {play_type}"
        })
        return Response(data)
    except Exception as e:
        logger.error(f'Error in assign match Round Robin: {str(e)}', exc_info=True)
        data.update({
            "status": status.HTTP_200_OK,
            "message": f"Bad Request error: {str(e)}"
        })
        return Response(data)

def handle_individual_match_play(data, league, team_ids, final):
    """Handle Individual Match Play tournament logic."""
    try:
        if Tournament.objects.filter(leagues=league, match_type="Individual Match Play").exists():
            data.update({
                "status": status.HTTP_200_OK,
                "message": "Matches are already created"
            })
            return Response(data)
        
        if len(team_ids) != 2:
            data.update({
                "status": status.HTTP_200_OK,
                "message": "Minimum 2 teams are needed for individual match play"
            })
            return Response(data)
        
        random.shuffle(team_ids)
        for court in range(1, final["courts"] + 1):
            create_tournament_match(
                league, team_ids[0], team_ids[1], "Individual Match Play", 0,
                court, final["sets"], final["points"], court
            )
        data.update({
            "status": status.HTTP_200_OK,
            "message": "Matches created for Individual Match Play"
        })
        return Response(data)
    except Exception as e:
        logger.error(f'Error in assign match Individual match play: {str(e)}', exc_info=True)
        data.update({
            "status": status.HTTP_200_OK,
            "message": f"Bad Request error: {str(e)}"
        })
        return Response(data)

@api_view(['POST'])
def assign_match(request):
    """Handle match assignment for various tournament types."""
    data = {'status': '', 'message': ''}
    try:
        # Extract and validate request data
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        league_uuid = request.data.get('league_uuid')
        league_secret_key = request.data.get('league_secret_key')
        
        # Validate user and league
        user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        league = Leagues.objects.filter(uuid=league_uuid, secret_key=league_secret_key)
        
        if not (user.exists() and league.exists()):
            data.update({
                "status": status.HTTP_404_NOT_FOUND,
                "data": [user_uuid, user_secret_key, league_uuid, league_secret_key],
                "ttt": list(league),
                "uuu": list(user),
                "message": "User or Tournament not found."
            })
            return Response(data)
        
        league = league.first()
        play_type = league.play_type
        play_details = LeaguesPlayType.objects.filter(league_for=league).values("data").first()
        
        # Validate team registration
        registered_teams = league.registered_team.all()
        team_ids = [team.id for team in registered_teams]
        if len(team_ids) != league.max_number_team:
            data.update({
                "status": status.HTTP_200_OK,
                "message": "All teams are not registered"
            })
            return Response(data)
        
        # Extract play type settings
        settings = play_details["data"]
        round_robin = {
            "courts": int(settings[0]["number_of_courts"]),
            "sets": int(settings[0]["sets"]),
            "points": int(settings[0]["point"])
        }
        elimination = {
            "courts": int(settings[1]["number_of_courts"]),
            "sets": int(settings[1]["sets"]),
            "points": int(settings[1]["point"])
        }
        final = {
            "courts": int(settings[2]["number_of_courts"]),
            "sets": int(settings[2]["sets"]),
            "points": int(settings[2]["point"])
        }
        
        # Notify teams of tournament start
        if not Tournament.objects.filter(leagues=league).exists():
            notify_tournament_start(league, team_ids)
        
        if play_type == "Single Elimination":
            return handle_single_elimination(data, league, team_ids, elimination, final)
        
        elif play_type == "Group Stage":
            return handle_group_stage(data, league, team_ids, round_robin, elimination, final)
        
        elif play_type in ["Round Robin", "Round Robin Compete to Final", "Robin Randomizer"]:
            return handle_round_robin(data, league, team_ids, round_robin, play_type)
        
        elif play_type == "Individual Match Play":
            return handle_individual_match_play(data, league, team_ids, final)
    except Exception as e:
        logger.error(f'Error in assign match API main function: {str(e)}', exc_info=True)
        data.update({
            "status": status.HTTP_200_OK,
            "message": f"Bad Request error: {str(e)}"
        })
        return Response(data)

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
        logger.error(f'Error in send_notification_organizer_to_player Api: {str(e)}', exc_info=True)
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, str(e)
    return Response(data)

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
        logger.error(f'Error in edit league max team update: {str(e)}', exc_info=True)
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)

@api_view(('POST',))
def declare_winner_team(request):
    data = {'status':'','message':''}
    try:        
        user_uuid = request.data.get('user_uuid')
        league_uuid = request.data.get('league_uuid')
        winner_team_uuid = request.data.get('winner_team_uuid', None)
        
        if not winner_team_uuid:
            data["status"], data["message"] = status.HTTP_200_OK, "Please select Winner team"
            return Response(data)
        
        user = get_object_or_404(User, uuid=user_uuid)
        event = get_object_or_404(Leagues, uuid=league_uuid)
        team = get_object_or_404(Team, uuid=winner_team_uuid)
        event.winner_team = team
        event.save()
        data["status"], data["message"] = status.HTTP_200_OK, "Winner tean declear successfully"
    except Exception as e :
        logger.error(f'Error in declare_winner_team event: {str(e)}', exc_info=True)
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"Bad request error: {e}"
    return Response(data)

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
                logger.warning(f'try to delecte: {get_tornament.name} user is {get_user.username}')
                data["status"], data["message"] = status.HTTP_200_OK, "You cann't  delete this tournament"
            else:
                check_league.delete()
                logger.info(f'Delecte: {get_tornament.name} user is {get_user.username}')
                data["status"], data["message"] = status.HTTP_200_OK, "League deleted successfully"
        else:
            data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "User or League not found"
    except Exception as e :
        logger.error(f'Error in delete event: {str(e)}', exc_info=True)
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)

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
            
            for i in leagues:
                i["is_edit"] = True
                i["is_delete"] = True
            data["status"], data['data'], data["message"] = status.HTTP_200_OK, leagues, "League data"
        else:
            data["status"], data['data'], data["message"] = status.HTTP_404_NOT_FOUND, "","User not found."
    except Exception as e :
        logger.error(f'Error in event list user: {str(e)}', exc_info=True)
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)

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
        logger.error(f'Error in edit event: {str(e)}', exc_info=True)
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, str(e)
    
    return Response(data)

@api_view(('GET',))
def get_organizer_league(request):
    data = {'status': '', 'message': '', 'data': []}
    try:
        user_uuid = request.GET.get('user_uuid')       
        league_uuid = request.GET.get('league_uuid')       

        user = get_object_or_404(User, uuid=user_uuid)
        league = get_object_or_404(Leagues, uuid=league_uuid)

        organizers = list(league.add_organizer.values(
            "id", "uuid", "secret_key", "first_name", "last_name", "email", "image"
        ))

        creator = league.created_by
        creator_data = {
            "id": creator.id,
            "uuid": creator.uuid,
            "secret_key": creator.secret_key,
            "first_name": creator.first_name,
            "last_name": creator.last_name,
            "email": creator.email,
            "image": creator.image.url if creator.image else None
        }

        # Combine the creator and organizers into one list
        data['data'] = [creator_data] + organizers
        data["status"], data["message"] = status.HTTP_200_OK, "Organizers fetched successfully."

    except Exception as e:
        logger.error(f'Error in get_organizer_league: {str(e)}', exc_info=True)
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, str(e)

    return Response(data)

@api_view(('POST',))
def add_organizer_league(request):
    data = {'status': '', 'message': ''}
    try:
        user_uuid = request.data.get('user_uuid')       
        league_uuid = request.data.get('league_uuid')       
        organizer_id_list = request.data.get('organizer_id_list')      
        if isinstance(organizer_id_list, str):
            try:
                organizer_id_list = json.loads(organizer_id_list)  # Convert JSON string to list
            except json.JSONDecodeError:
                return Response({
                    "status": status.HTTP_400_BAD_REQUEST,
                    "message": "Invalid JSON format for organizer_id_list."
                }, status=status.HTTP_400_BAD_REQUEST)

        # If it's a single integer, convert it to a list
        if isinstance(organizer_id_list, int):
            organizer_id_list = [organizer_id_list]  # Wrap in a list

        # Ensure it's a list of integers
        if not isinstance(organizer_id_list, list) or not all(isinstance(i, int) for i in organizer_id_list):
            return Response({
                "status": status.HTTP_400_BAD_REQUEST,
                "message": "organizer_id_list must be a list of integers."
            }, status=status.HTTP_400_BAD_REQUEST)
        
        check_user = User.objects.filter(uuid=user_uuid)
        check_league = Leagues.objects.filter(uuid=league_uuid)

        if not check_user.exists():
            return Response({
                "data": [],
                "status": status.HTTP_401_UNAUTHORIZED, 
                "message": "Unauthorized access"
            })
        
        if not check_league.exists():
            return Response({
                "data": [],
                "status": status.HTTP_401_UNAUTHORIZED, 
                "message": "League not found"
            })
         
        get_user = check_user.first()
        get_league = check_league.first()

        if get_league.created_by == get_user or get_user in get_league.add_organizer.all():            
            get_league.add_organizer.clear()
            for org_id in organizer_id_list:
                organizer_instance = User.objects.filter(id=int(org_id)).first()
                if organizer_instance:
                    get_league.add_organizer.add(organizer_instance)
            get_league.save()

            data["status"], data["message"] = status.HTTP_200_OK, "Tournament organizers updated successfully."
        else:
            data["status"], data["message"] = status.HTTP_403_FORBIDDEN, "User does not have permission to add organizers for this tournament."
        
    except Exception as e:
        logger.error(f'Error in add organizer to event: {str(e)}', exc_info=True)
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, str(e)

    return Response(data)

@api_view(('POST',))
def remove_organizer_to_league(request):
    data = {'status': '', 'message': ''}
    try:
        user_uuid = request.data.get('user_uuid')       
        league_uuid = request.data.get('league_uuid')       
        organizer_id_list = request.data.get('organizer_id_list')      
        if isinstance(organizer_id_list, str):
            try:
                organizer_id_list = json.loads(organizer_id_list)  # Convert JSON string to list
            except json.JSONDecodeError:
                return Response({
                    "status": status.HTTP_400_BAD_REQUEST,
                    "message": "Invalid JSON format for organizer_id_list."
                }, status=status.HTTP_400_BAD_REQUEST)

        # If it's a single integer, convert it to a list
        if isinstance(organizer_id_list, int):
            organizer_id_list = [organizer_id_list]  # Wrap in a list

        # Ensure it's a list of integers
        if not isinstance(organizer_id_list, list) or not all(isinstance(i, int) for i in organizer_id_list):
            return Response({
                "status": status.HTTP_400_BAD_REQUEST,
                "message": "organizer_id_list must be a list of integers."
            }, status=status.HTTP_400_BAD_REQUEST)
        
        user = get_object_or_404(User, uuid=user_uuid)
        league = get_object_or_404(Leagues, uuid=league_uuid)

        if league.created_by == user:            
            # league.add_organizer.clear()
            for org_id in organizer_id_list:
                organizer_instance = User.objects.filter(id=int(org_id)).first()
                if organizer_instance:
                    league.add_organizer.remove(organizer_instance)
            league.save()

            data["status"], data["message"] = status.HTTP_200_OK, "organizers removed successfully."
        else:
            data["status"], data["message"] = status.HTTP_403_FORBIDDEN, "User does not have permission to add organizers for this tournament."
        
    except Exception as e:
        logger.error(f'Error in removed organizer to event: {str(e)}', exc_info=True)
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, str(e)
    return Response(data)


@api_view(('GET',))
def search_user_to_add_organizer(request):
    data = {'status': '', 'message': ''}
    try:
        user_uuid = request.GET.get('user_uuid') 
        search_name = request.GET.get('search_name')
        check_user = User.objects.filter(uuid=user_uuid)

        if not check_user.exists():
            return Response({
                "data": [],
                "status": status.HTTP_401_UNAUTHORIZED, 
                "message": "Unauthorized access"
            })
        matching_users = User.objects.filter(Q(first_name__icontains=search_name) | Q(last_name__icontains=search_name)).exclude(uuid=user_uuid)

        if not matching_users.exists():
            return Response({
                "data": [],
                "status": status.HTTP_404_NOT_FOUND,
                "message": "No users found with the given name."
            }, status=status.HTTP_404_NOT_FOUND)

        # Prepare response data
        data['data'] = [{"id": user.id, "first_name": user.first_name, "last_name": user.last_name} for user in matching_users]
        data['status'], data['message'] = status.HTTP_200_OK, "Users retrieved successfully."  

    except Exception as e:
        logger.error(f'Error in search user to add organizer: {str(e)}', exc_info=True)
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
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if check_user.exists():
            get_user = check_user.first()
            # Retrieve teams created by the user
            get_teams = Team.objects.filter(created_by=get_user)
            # Check if league exists
            check_league = Leagues.objects.filter(uuid=league_uuid, secret_key=league_secret_key)
            if check_league.exists():
                league = check_league.first()
                if league.team_type.name == "Open-team":
                    team_type = None
                else:
                    team_type = league.team_type.name
                team_person = league.team_person.name
                team_data = []
                
                team_id_list = list(league.registered_team.all().values_list("id", flat=True))
                # print(team_id_list)
                # Iterate through user's teams
                for team in get_teams:
                    flg = True
                    flg_text = ""
                    register_team_id_list = list(league.registered_team.all().values_list("id", flat=True))
                    is_view = False
                    if team.id not in register_team_id_list:
                       is_view = True 
                    # Check if team's type and person type match the league's requirements
                    if team_person and team.team_person:
                        if team_person.strip() != team.team_person.strip():
                            flg = False
                    if team_type and team.team_type:
                        if team_type.strip() != team.team_type.strip():
                            flg = False

                        
                    # Retrieve players in the team
                    player_data = Player.objects.filter(team=team).values("player_full_name", "player_ranking", "player__rank")
                    team_rank = 0
                    for pla in player_data:
                        pla["player_ranking"] = pla["player__rank"]                  
                        if pla["player__rank"] == "0" or pla["player__rank"] in [0,"", "null", None]:
                            team_rank += 1
                        else:
                            team_rank += float(pla["player__rank"])
                    try:
                        team_rank = team_rank / len(player_data)
                    except:
                        team_rank = 1.0

                    # Append team details to the response
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
                fees = league.registration_fee
                others_fees = league.others_fees
                if others_fees:
                    for val in others_fees.values():
                        if isinstance(val, (int, float)):  # Ensure the value is numeric
                            fees += val
                        elif isinstance(val, str) and val.isdigit():  # Convert string numbers
                            fees += int(val)
                if league.policy is True:
                    cancel_policy = list(LeaguesCancellationPolicy.objects.filter(league=league).values())
                else:
                    cancel_policy = []
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
                    "any_rank_status":league.any_rank,
                    "league_start_rank":league.start_rank,
                    "league_end_rank":league.end_rank,
                    "fees": fees,
                    "cancelation_policy": cancel_policy
                }
                # Prepare response data
                main_data = {"league_data": [league_data], "team_data": team_data}
                data["status"], data['data'], data["message"] = status.HTTP_200_OK, main_data, "Data found."
            else:
                data["status"], data['data'], data["message"] = status.HTTP_404_NOT_FOUND, "", "Tournament  not found"
        else:
            data["status"], data['data'], data["message"] = status.HTTP_404_NOT_FOUND, "", "User not found."
    except Exception as e:
        logger.error(f'Error in team_register_user: {str(e)}', exc_info=True)
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, str(e)
    return Response(data)

@api_view(('POST',))
def register_teams_to_league(request):
    try:     
        chage_amount = None   
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        league_uuid = request.data.get('league_uuid')
        league_secret_key = request.data.get('league_secret_key')
        team_uuid_all = request.data.get('team_uuid')
        team_secret_key_all = request.data.get('team_secret_key') 
        discount = request.data.get('discount', 0) 

        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        check_league = Leagues.objects.filter(uuid=league_uuid, secret_key=league_secret_key)

        if not check_user.exists() or not check_league.exists():
            return Response({"status": status.HTTP_400_BAD_REQUEST,"payement": None, "url":None, "add_amount":None, "message": "User or Tournament not found"})

        get_league = check_league.first() 
        get_user = check_user.first()

        check_wallet = Wallet.objects.filter(user=get_user)
        if not check_wallet.exists():
            return Response({"status": status.HTTP_404_NOT_FOUND, "message": "No wallet found."})

        get_wallet = check_wallet.first()
        balance = Decimal(str(get_wallet.balance))  # ✅ Ensure balance is Decimal

        total_registered_teams = get_league.registered_team.count()
        today_date = timezone.now()
        if get_league.team_type.name != 'Open-team':
            if get_league.registration_end_date < today_date or get_league.max_number_team == total_registered_teams or get_league.is_complete:
                return Response({"status": status.HTTP_400_BAD_REQUEST,"payement": None, "url":None, "add_amount":None, "message": "Registration is over."})
        else:
            if get_league.leagues_start_date < today_date :
                return Response({"status": status.HTTP_400_BAD_REQUEST,"payement": None, "url":None, "add_amount":None, "message": "Registration is over."})

        team_uuid_all = str(team_uuid_all).split(",")
        team_secret_key_all = str(team_secret_key_all).split(",")
        all_team_id = []
        team_details_list = []

        for t in range(len(team_uuid_all)):
            team = Team.objects.filter(uuid=team_uuid_all[t], secret_key=team_secret_key_all[t])
            if team.exists():
                get_team = team.first()
                all_team_id.append(get_team.id)
                team_details_list.append((get_team.id, get_team.name))

        if not all_team_id:
            return Response({"status": status.HTTP_400_BAD_REQUEST, "payement": None, "url":None,"add_amount":None,"message": "No valid teams found."})

        if get_league.start_rank and get_league.end_rank:
            for team_id in all_team_id:
                team = Team.objects.get(id=team_id)
                players = Player.objects.filter(team=team).select_related('player')

                if not players.exists():
                    return Response({"status": status.HTTP_400_BAD_REQUEST, "message": f"Team {team['name']} has no players."})

                team_rank = sum(float(p.player.rank or 0) for p in players) / max(len(players), 1)
                
                if not (get_league.start_rank <= team_rank <= get_league.end_rank):
                    return Response({"status": status.HTTP_400_BAD_REQUEST,"payement": None, "url":None, "add_amount":None, "message": f"{team.name} does not have the required rank."})

        # ✅ Calculate fees with Decimal
        number_of_team_join = len(all_team_id)
        fees = Decimal(str(get_league.registration_fee))

        others_fees = get_league.others_fees
        if others_fees:
            for val in others_fees.values():
                try:
                    fees += Decimal(str(val))  # Convert everything to Decimal safely
                except (ValueError, TypeError):
                    continue  # Skip non-numeric values safely
        total_amount = fees * Decimal(number_of_team_join)
        #add discount
        if discount != 0:
            discount = Decimal(str(discount))  # Ensure discount is a Decimal
            total_amount = Decimal(str(total_amount))  # Ensure total_amount is a Decimal
            total_amount -= (total_amount * discount) / Decimal("100")
        organizer_amount = (total_amount * Decimal(settings.ORGANIZER_PERCENTAGE)) / Decimal(100)
        admin_amount = (total_amount * Decimal(settings.ADMIN_PERCENTAGE)) / Decimal(100)



        #redy the user register data
        transactiondetails = {}
        transactiondetails["event_id"] = get_league.id
        transactiondetails["event_name"] = get_league.name
        transactiondetails["event_person_type"] = get_league.team_person.name
        transactiondetails["register_user"] = get_user.id
        transactiondetails["team_details_list"] = team_details_list
        if total_amount in [0, "0.0", 0.0]:
           get_league.registered_team.add(*all_team_id) 
           logger.info(f'{get_user.username} hit the register team  to {get_league.name}||{get_league.uuid}. team is {all_team_id}| register fee is 0')
           return Response({"status": status.HTTP_200_OK,"payement": None, "url":None, "add_amount":None, "message": f"You have successfully registered the teams to event {get_league.name}"})
        if balance >= total_amount:
            get_league.registered_team.add(*all_team_id)

            wallet_transaction = WalletTransaction.objects.create(
                sender=get_user,
                reciver=get_league.created_by,                        
                admin_cost=admin_amount.quantize(Decimal('0.001'), rounding=ROUND_DOWN),
                reciver_cost=organizer_amount.quantize(Decimal('0.001'), rounding=ROUND_DOWN),
                getway_charge=Decimal(0),                        
                transaction_for="TeamRegistration",                                   
                transaction_type="debit",
                amount=total_amount.quantize(Decimal('0.001'), rounding=ROUND_DOWN),
                payment_id=None, 
                description=f"${total_amount} is debited from your PickleIt wallet for registering teams to league {get_league.name}."
            )
            # ✅ store team register details
            transaction_for = TransactionFor(transaction=wallet_transaction, details=transactiondetails)
            transaction_for.save()

            # ✅ Update admin wallet
            admin_wallet = Wallet.objects.filter(user__is_superuser=True).first()
            if admin_wallet:
                admin_wallet.balance = Decimal(str(admin_wallet.balance)) + admin_amount
                admin_wallet.save()

            # ✅ Deduct from user wallet
            get_wallet.balance = balance - total_amount
            get_wallet.save()
            
            # ✅ Update organizer wallet
            organizer_wallet = Wallet.objects.filter(user=get_league.created_by).first()
            if organizer_wallet:
                organizer_wallet.balance = Decimal(str(organizer_wallet.balance)) + organizer_amount
                organizer_wallet.save()
            logger.info(f'{get_user.username} hit the register team  to {get_league.name}||{get_league.uuid}. team is {all_team_id}')
            return Response({"status": status.HTTP_200_OK,"payement": "wallet", "url":None, "add_amount":None, "message": f"You have successfully registered the teams to event {get_league.name}"})

        else:
            
            pay_balance = float(total_amount - balance)
            
            stripe_fee = Decimal(pay_balance * 0.029) + Decimal(0.30)
            total_charge = Decimal(pay_balance) + stripe_fee  # Add Stripe fee to total amount
            total_charge = round(total_charge, 2)
            stripe_send_amount = int(round(float(total_charge * 100)))
            # Convert to cents (Stripe works with smallest currency unit)
            chage_amount = int(round(float(pay_balance * 100)))
            # print("chage_amount", chage_amount)
            make_request_data = {"tournament_id":get_league.id,"user_id":get_user.id,"team_id_list":all_team_id, "debited_wallet_balance":str(balance), "details":transactiondetails}
            json_bytes = json.dumps(make_request_data).encode('utf-8')
            my_data = base64.b64encode(json_bytes).decode('utf-8')
            product_name = "Payment For Register Team"
            product_description = "Payment received by Pickleit"
            stripe.api_key = settings.STRIPE_SECRET_KEY
            if get_user.stripe_customer_id :
                stripe_customer_id = get_user.stripe_customer_id
            else:
                customer = stripe.Customer.create(email=get_user.email).to_dict()
                stripe_customer_id = customer["id"]
                get_user.stripe_customer_id = stripe_customer_id
                get_user.save()
            
            protocol = 'https'
            host = request.get_host()
            current_site = f"{protocol}://{host}"
            main_url = f"{current_site}/team/c80e2caf03546f11a39db8703fb7f7457afc5cb20db68b5701497fd992a0c29f/{chage_amount}/{my_data}/"
            product = stripe.Product.create(name=product_name,description=product_description,).to_dict()
            price = stripe.Price.create(unit_amount=stripe_send_amount,currency='usd',product=product["id"],).to_dict()
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
            logger.info(f'{get_user.username} hit the register team  to {get_league.name}||{get_league.uuid}. team is {all_team_id}')
            return Response({"status": status.HTTP_200_OK,"payement": "stripe", "url": checkout_session.url,"add_amount":total_charge, "message": f"Please add ${total_charge} to your wallet to register the teams."}) 
    except Exception as e:
        logger.error(f'Error in go for register team user : {str(e)}', exc_info=True)
        return Response({"status": status.HTTP_400_BAD_REQUEST,"payement": None, "url": None,"add_amount":None, "message": str(e)}) 

def payment_for_team_registration(request, charge_for, my_data, checkout_session_id):
    try:
        stripe.api_key = settings.STRIPE_SECRET_KEY
        pay = stripe.checkout.Session.retrieve(checkout_session_id).to_dict()

        stripe_customer_id = pay.get("customer")
        payment_status = pay.get("payment_status") == "paid"
        expires_at = pay.get("expires_at")
        amount_total = Decimal(pay.get("amount_total", 0)) / 100  # Convert to Decimal
        payment_method_types = pay.get("payment_method_types", [])

        # Decode and parse JSON data
        json_bytes = base64.b64decode(my_data)
        request_data = json.loads(json_bytes.decode('utf-8'))
        debited_wallet_balance = request_data.get("balance")
        transactiondetails = request_data.get("details")
        teams_list = list(request_data.get("team_id_list", []))
        get_user = get_object_or_404(User, id=request_data.get("user_id"))
        teams_count = len(teams_list)
        payment_for = f"Register {teams_count} Team"

        check_tournament = Leagues.objects.filter(id=request_data.get("tournament_id")).first()
        existing_payment = AllPaymentsTable.objects.filter(user=get_user, checkout_session_id=checkout_session_id).exists()

        if not existing_payment and payment_status:
            AllPaymentsTable.objects.create(
                user=get_user,
                amount=amount_total,
                checkout_session_id=checkout_session_id,
                payment_mode=", ".join(payment_method_types),
                payment_for=payment_for,
                status="Completed" if payment_status else "Failed"
            )
            check_tournament.registered_team.add(*teams_list)
            try:
                organizer_amount = (amount_total * Decimal(settings.ORGANIZER_PERCENTAGE)) / 100
                admin_amount = (amount_total * Decimal(settings.ADMIN_PERCENTAGE)) / 100
                if debited_wallet_balance not in ["", 0.00, "None", None, "null", "0.00", 0, "0"]: 
                    total_debit = float(debited_wallet_balance) + float(amount_total)
                else:
                    total_debit = float(amount_total)
                if admin_amount is not None:
                    admin_amount = round(float(admin_amount), 2)
                if organizer_amount is not None:
                    organizer_amount = round(float(organizer_amount), 2)
                if total_debit is not None:
                    total_debit = round(float(total_debit), 2)
                wallet_transaction = WalletTransaction.objects.create(
                    sender=get_user,
                    reciver=check_tournament.created_by,
                    admin_cost=admin_amount,
                    reciver_cost=organizer_amount,
                    getway_charge=Decimal(0),
                    transaction_for="TeamRegistration",
                    transaction_type="debit",
                    amount=total_debit,
                    payment_id=checkout_session_id,
                    description=f"${amount_total} is debited from your PickleIt wallet for registering teams to event {check_tournament.name}."
                )
                # ✅ store team register details
                transaction_for = TransactionFor(transaction=wallet_transaction, details=transactiondetails)
                transaction_for.save()
            except:
                pass

        if payment_status:
            return render(request, "success_payment_for_register_team.html")
        else:
            return render(request, "failed_paymentregister_team.html")

    except Exception as e:
        # print(f"Error in payment_for_team_registration: {str(e)}")
        logger.error(f'Error in payment_for_team_registration: {str(e)}', exc_info=True)
        return render(request, "failed_paymentregister_team.html")

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
        logger.error(f'Error in player manage details: {str(e)}', exc_info=True)
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
        logger.error(f'Error in registered_team_for_leauge_list: {str(e)}', exc_info=True)
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
        logger.error(f'Error in Tournament details: {str(e)}', exc_info=True)
        data['status'],data['upcoming_leagues'], data['previous_matches'],data['signed_up_matches'],data['save_league'], data['message'] = status.HTTP_400_BAD_REQUEST,[],[],[],[], f"{e}"
    return Response(data)


@api_view(['POST'])
def save_league(request):
    try:
        # Extract request data
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        league_uuid = request.data.get('league_uuid')

        # Validate required fields
        if not all([user_uuid, user_secret_key, league_uuid]):
            return Response({
                'status': status.HTTP_400_BAD_REQUEST,
                'message': 'user_uuid, user_secret_key, and league_uuid are required.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Check if user exists
        user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key).first()
        if not user:
            return Response({
                'status': status.HTTP_400_BAD_REQUEST,
                'message': 'User not found.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Get league details
        league = Leagues.objects.filter(uuid=league_uuid).first()
        if not league:
            return Response({
                'status': status.HTTP_400_BAD_REQUEST,
                'message': 'League not found.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Check if league is already saved
        saved_league = SaveLeagues.objects.filter(ch_league_id=league.id, created_by=user).first()
        
        if saved_league:
            # Unsave the league
            saved_league.delete()
            message = f"League '{league.name}' has been unsaved from your account."
        else:
            # Save the league
            SaveLeagues.objects.create(
                secret_key=GenerateKey().gen_advertisement_key(),
                ch_league_id=league.id,
                created_by=user
            )
            message = f"League '{league.name}' has been saved to your account."

        return Response({
            'status': status.HTTP_200_OK,
            'message': message
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f'Error in save_league: {str(e)}', exc_info=True)
        return Response({
            'status': status.HTTP_400_BAD_REQUEST,
            'message': f'Error: {str(e)}'
        }, status=status.HTTP_400_BAD_REQUEST)


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
        logger.error(f'Error in tournament_schedule: {str(e)}', exc_info=True)
        data['status'], data['data'], data['message'] = status.HTTP_400_BAD_REQUEST, [], f"{e}"
    return Response(data)         

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
        logger.error(f'Error in invite code check: {str(e)}', exc_info=True)
        data['status'] = status.HTTP_400_BAD_REQUEST
        data['message'] = f"{e}"
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
        logger.error(f'Error in stats details: {str(e)}', exc_info=True)
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


# tournamnet section
@api_view(["GET"])
def event_matches(request):
    data = {'status':'', 'message':'', 'match':[]}
    try:
        # user_uuid = request.GET.get('user_uuid')
        league_uuid = request.GET.get('league_uuid')
        # user = get_object_or_404(User, uuid=user_uuid)
        event = get_object_or_404(Leagues, uuid=league_uuid)
        tournamnets = Tournament.objects.filter(leagues=event).order_by("match_number")
        serializer = MatchListSerializer(tournamnets, many=True)
        data["status"] = status.HTTP_200_OK
        data["match"] = serializer.data
        return Response(data, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f'Error in match list of the event: {str(e)}', exc_info=True)
        data["status"] = status.HTTP_200_OK
        data["message"] = str(e)
        return Response(data, status=status.HTTP_200_OK)

@api_view(["GET"])
def match_view_score(request):
    data = {
        "status": None,
        "score": [],
        "is_edit": False,
        "is_save": False,
        "is_approve": False,
        "is_reject": False,
        "message": None
    }

    try:
        user_uuid = request.GET.get('user_uuid')
        tournament_uuid = request.GET.get('tournament_uuid')

        user = get_object_or_404(User, uuid=user_uuid)
        tournament = get_object_or_404(Tournament, uuid=tournament_uuid)
        set_results = TournamentSetsResult.objects.filter(tournament=tournament).order_by("set_number")

        # These lists should be filled based on logic
        organizer_user_list = []
        team1_player_user_list = []
        team2_player_user_list = []  # Note: This was declared but not used later; keeping it as is for consistency

        # Get team 1 and team 2 player IDs, handling cases where team might be None
        team_1_player = list(Player.objects.filter(team=tournament.team1).values_list("player_id", flat=True)) if tournament.team1 else []
        team_2_player = list(Player.objects.filter(team=tournament.team2).values_list("player_id", flat=True)) if tournament.team2 else []  # Fixed: using team2 instead of team1

        # Get created_by IDs for team1 and team2, with None checks
        team_1_created_by = [tournament.team1.created_by.id] if tournament.team1 and tournament.team1.created_by else []
        team_2_created_by = [tournament.team2.created_by.id] if tournament.team2 and tournament.team2.created_by else []

        # Update player user lists by combining player IDs and created_by IDs
        team1_player_user_list = list(set(team_1_player + team_1_created_by))
        team2_player_user_list = list(set(team_2_player + team_2_created_by))

        # Organizer list, with None checks
        organizers_id_list = [tournament.leagues.created_by.id] if tournament.leagues and tournament.leagues.created_by else []
        sub_organizer_data = list(tournament.leagues.add_organizer.values_list("id", flat=True)) if tournament.leagues else []
        organizer_user_list = list(set(organizers_id_list + sub_organizer_data))
        
        score_approved = TournamentScoreApproval.objects.filter(tournament=tournament).first()
        score_report = TournamentScoreReport.objects.filter(tournament=tournament).first()
        if not tournament.is_completed:
            report_form_team1 = report_form_team2 = False
            if score_report:
                report_user = score_report.created_by
                report_form_team1 = user.id in team1_player_user_list
                report_form_team2 = user.id in team2_player_user_list

            team1_approval = team2_approval = organizer_approval = False
            if score_approved:
                team1_approval = score_approved.team1_approval
                team2_approval = score_approved.team2_approval
                organizer_approval = score_approved.organizer_approval

            if user.id in organizer_user_list:
                if set_results:
                    if score_report:
                        data["message"] = "Opponent team has reported the score"
                        data["is_edit"] = True
                        data["is_save"] = True
                    else:
                        data["is_edit"] = True

                    if not organizer_approval:
                        data["is_edit"] =True
                        data["is_approve"] = True
                    else:
                        data["is_edit"] = True
                        
                else:
                    data["is_edit"] = True
                    data["is_save"] = True
           
            # Check permissions and statuses
            elif user.id in team1_player_user_list:
                if set_results:                    

                    if report_form_team2:
                        data["message"] = "Opponent team has reported your score"
                        data["is_edit"] = True

                    elif report_form_team1:
                        data["message"] = "You reported this score, wait for the organizer's action"
                        data["is_edit"] = True

                    if not report_form_team1 and not report_form_team2:
                        if not team1_approval and not organizer_approval:
                            data["is_edit"] = True
                            data["is_approve"] = True
                            data["is_reject"] = True

                        elif not team1_approval and organizer_approval:
                            data["is_edit"] = True
                            data["is_approve"] = False
                            data["is_reject"] = False

                        elif team1_approval:
                            data["is_edit"] = True
                            data["is_approve"] = False
                            data["is_reject"] = False  

                        elif not organizer_approval or not team1_approval or not team2_approval:
                            data["is_edit"] = True
                            data["message"] = "Waiting for all tournament players' approval"
                        
                else:
                    data["is_edit"] = True
                    data["is_save"] = True

            elif user.id in team2_player_user_list:
                if set_results:                   

                    if report_form_team1:
                        data["message"] = "Opponent team has reported your score"
                        data["is_edit"] = True 

                    elif report_form_team2:
                        data["message"] = "You reported this score, wait for the organizer's action"
                        data["is_edit"] = True

                    if not report_form_team1 and not report_form_team2:
                        if not team2_approval and not organizer_approval:
                            data["is_edit"] = True
                            data["is_approve"] = True
                            data["is_reject"] = True

                        elif not team2_approval and organizer_approval:
                            data["is_edit"] = True
                            data["is_approve"] = False
                            data["is_reject"] = False

                        elif team2_approval:
                            data["is_edit"] = True
                            data["is_approve"] = False
                            data["is_reject"] = False 

                        elif not organizer_approval or not team1_approval or not team2_approval:
                            data["is_edit"] = True
                            data["message"] = "Waiting for all tournament players' approval"
                else:
                    data["is_edit"] = True
                    data["is_save"] = True

            

        # Processing match scores
        team_scores = {}
        for set_result in set_results:
            for team in [tournament.team1, tournament.team2]:
                if not team:
                    continue

                team_name = team.name
                is_winner = set_result.win_team == team
                if team_name not in team_scores:
                    team_scores[team_name] = {
                        "name": team_name,
                        "set": [],
                        "score": [],
                        "win_status": [],
                        "is_win": False,
                        "is_completed": tournament.is_completed,
                        "is_drow": tournament.is_drow
                    }

                team_scores[team_name]["set"].append(f"s{set_result.set_number}")
                team_scores[team_name]["score"].append(
                    set_result.team1_point if team == tournament.team1 else set_result.team2_point
                )
                team_scores[team_name]["win_status"].append(is_winner)

        if tournament.winner_team and tournament.winner_team.name in team_scores:
            team_scores[tournament.winner_team.name]["is_win"] = True

        data["score"] = list(team_scores.values())
        data["status"] = status.HTTP_200_OK

    except Exception as e:
        logger.error(f'Error in match view of the event: {str(e)}', exc_info=True)
        data["status"] = "error"
        data["message"] = str(e)

    return Response(data)


