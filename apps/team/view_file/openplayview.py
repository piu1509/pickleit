import os
import json
import email
import random
from datetime import timedelta
from itertools import combinations
from apps.team.views import notify_edited_player
import random, json, base64, stripe, uuid
from django.db.models import Q
from math import radians, cos, sin, asin, sqrt
from decimal import Decimal, ROUND_DOWN
from apps.user.models import *
from apps.chat.models import *
from apps.team.models import *
from apps.user.helpers import *
from apps.team.serializers import *
from apps.pickleitcollection.models import *
from django.conf import settings
from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.pagination import PageNumberPagination
from geopy.distance import geodesic
from rest_framework.serializers import SerializerMethodField
from rest_framework import serializers
from rest_framework.pagination import LimitOffsetPagination
#### match me section ####
"""
store the matching cradentials
get the matching user wise data
"""
### Match me section end ###


###open play section ###
"""
create the open play
#1 User selects Singles or Doubles
#2 User selects Location 
#3 User selects Date
#4 User selects Time
#5 User selects Play Format (Select Round Robbin Compete to Final)
#6 User selects Number of Courts
#7 User selects Match Format
#8 User Selects Type of Open Play
    -> Select from List (Select Round Robbin Group to Final)
#9 User searches for players to invite
    -> User selects players to invite from list of players
    -> User Can filter players in search by location, ranking
#10 After user selects the players, User clicks on “Invite Players”
    -> Players receive email notification
    -> Players receive pop up notification on phones
    -> Players receive in app notification
#11 Event is created in calendar and “My Events”
inivite the players
get the open play user wise data
"""
import logging, pytz
logger = logging.getLogger('myapp')


##### serializers 
class UserListSerializer(serializers.ModelSerializer):
    name = SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'uuid', 'name', 'image']

    def get_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"

class TeamListSerializer(serializers.ModelSerializer):
    image = serializers.ImageField(source='team_image', use_url=True, allow_null=True)
    class Meta:
        model = Team
        fields = ['id', 'uuid', 'name', 'image']


class InvitationPagination(PageNumberPagination):
    page_size = 10

class UserSerializer(serializers.ModelSerializer):
    full_name = SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'uuid', 'first_name', 'last_name', 'full_name', 'image']

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"

class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Leagues
        fields = ['uuid', 'secret_key', 'name', 'leagues_start_date', 'location', 'play_type']

class OpenPlayInvitationSerializer(serializers.ModelSerializer):
    invited_user = UserSerializer(source='user')
    invited_by = UserSerializer()
    event = EventSerializer()

    class Meta:
        model = OpenPlayInvitation
        fields = ['id', 'event', 'invited_user', 'invited_by', 'status', 'created_at']

###### function view
@api_view(['GET'])
def team_list_open_play(request):
    data = {'status': status.HTTP_200_OK, 'data': [], 'message': ''}
    try:
        user_uuid = request.GET.get('user_uuid')
        filter_by = request.GET.get('filter_by', None)
        search_text = request.GET.get('search_text', None)
        user = get_object_or_404(User, uuid=user_uuid)
        
        # Get teams created by user
        teams_query = Team.objects.filter(created_by=user)
        if filter_by:
            if filter_by not in ["Two Person Team", "One Person Team"]:
                data['status'] = status.HTTP_400_BAD_REQUEST
                data['data'] = []
                data['message'] = "Filter must be Two Person Team, One Person Team"
                return Response(data)
            teams_query = teams_query.filter(team_person=filter_by)
        if search_text:
            teams_query = teams_query.filter(name__icontains=search_text)
        main_data = teams_query.values("id", "uuid", "name", "team_type","created_by__first_name", "created_by__last_name", "team_image")
        data["data"] = list(main_data)
        data["message"] = "Data found"

    except Exception as e:
        logger.error(f'Error in team_list_open_play: {str(e)}', exc_info=True)
        data['status'] = status.HTTP_400_BAD_REQUEST
        data['data'] = []
        data['message'] = str(e)

    return Response(data)


@api_view(['GET'])
def search_invite_player_for_open_play(request):
    data = {'status': status.HTTP_200_OK, 'data': [], 'message': ''}
    try:
        user_uuid = request.GET.get('user_uuid')
        search_text = request.GET.get('search_text', None)
        lat = request.GET.get('lat', None)
        lon = request.GET.get('lon', None)
        distance_limit = request.GET.get('distance', 500)
        start_ranking = request.GET.get('start_ranking', None)
        end_ranking = request.GET.get('end_ranking', None)

        user = get_object_or_404(User, uuid=user_uuid)

        users = User.objects.filter(is_active=True).exclude(uuid=user.uuid)

        # Keyword filtering
        if search_text:
            users = users.filter(
                Q(first_name__icontains=search_text) |
                Q(last_name__icontains=search_text) |
                Q(username__icontains=search_text)
            )

        # Rank filtering
        if end_ranking and start_ranking:
            users = users.filter(rank__gte = start_ranking, rank__lte = end_ranking)

        # Location-based filtering
        if lat and lon and distance_limit:
            try:
                lat = float(lat)
                lon = float(lon)
                distance_limit = float(distance_limit)

                filtered_users = []
                for u in users:
                    if u.latitude and u.longitude:
                        try:
                            user_location = (lat, lon)
                            other_location = (float(u.latitude), float(u.longitude))
                            dist = geodesic(user_location, other_location).km
                            if dist <= distance_limit:
                                filtered_users.append(u)
                        except:
                            continue
                users = filtered_users
            except ValueError:
                pass  # fallback if invalid lat/lon

        # Prepare response
        result = []
        for u in users.order_by("first_name"):
            result.append({
                'user_uuid': str(u.uuid),
                'first_name': u.first_name,
                'last_name': u.last_name,
                'rank': u.rank,
                'image': request.build_absolute_uri(u.image.url) if u.image else None,
                'location': {
                    'latitude': u.latitude,
                    'longitude': u.longitude
                },
                'location_text': u.permanent_location,
            })

        data['data'] = result
        data['message'] = "Users fetched successfully"

    except Exception as e:
        logger.error(f'Error in search_invite_player_for_open_play: {str(e)}', exc_info=True)
        data['status'] = status.HTTP_400_BAD_REQUEST
        data['message'] = str(e)

    return Response(data, status=data['status'])

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
    
@api_view(['POST'])
def create_open_play_event_randomize(request):
    data = {'status': '', 'message': ''}

    try:
        # Input validation
        required_fields = [
            'user_uuid', 'leagues_start_date', 'location', 'latitude', 
            'longitude', 'team_person', 'invite_user_uuid', 'court', 'sets', 'points'
        ]
        
        for field in required_fields:
            if not request.data.get(field):
                raise ValidationError(f"Missing required field: {field}")

        # Extract and validate data
        open_play_type = request.data.get('open_play_type', 'Round Robbin Compete to Final')
        user_uuid = request.data.get('user_uuid')
        invite_user_uuid = request.data.get('invite_user_uuid')  # Expecting a list
        leagues_start_date = request.data.get('leagues_start_date')
        location = request.data.get('location')
        latitude = float(request.data.get('latitude'))
        longitude = float(request.data.get('longitude'))
        team_person = request.data.get('team_person')
        court = int(request.data.get('court'))
        sets = int(request.data.get('sets'))
        points = int(request.data.get('points'))
        timezone_ = request.data.get('timezone', 'America/New_York')

        # Validate invite_user_uuid is a list
        if not isinstance(invite_user_uuid, list):
            raise ValidationError("invite_user_uuid must be a list of UUIDs")

        # Validate each UUID in the list
        for uuid in invite_user_uuid:
            if not isinstance(uuid, str) or len(uuid) == 0:
                raise ValidationError(f"Invalid UUID in invite_user_uuid: {uuid}")

        # Validate numeric inputs
        if court < 1:
            raise ValidationError("Court number must be positive")
        if sets < 1:
            raise ValidationError("Number of sets must be positive")
        if points < 1:
            raise ValidationError("Points must be positive")

        # Validate datetime format
        try:
            leagues_start_datetime = parse_date(leagues_start_date, 'America/New_York')
            if not leagues_start_datetime:
                raise ValidationError("leagues_start_date cannot be empty")
            formatted_datetime = leagues_start_datetime.strftime('%Y-%m-%d %H:%M:%S')
        except ValueError as e:
            raise ValidationError(str(e))

        # Validate play type data
        play_type_data = [
            {"name": "Round Robin", "sets": "1", "point": "15", "is_show": False, "number_of_courts": "4"}, 
            {"name": "Elimination", "sets": "1", "point": "15", "is_show": False, "number_of_courts": "4"}, 
            {"name": "Final", "sets": str(sets), "point": str(points), "is_show": True, "number_of_courts": str(court)}
        ]

        # Static data
        team_type = "Open-team"
        play_type = open_play_type
        max_number_team = 500
        registration_fee = 0
        description = None
        league_type = "Open to all"

        # Database queries with error handling
        user = get_object_or_404(User, uuid=user_uuid)
        team_type_obj = get_object_or_404(LeaguesTeamType, name=team_type)
        person_type_obj = get_object_or_404(LeaguesPesrsonType, name=team_person)

        # Generate secret key
        try:
            secret_key = GenerateKey().gen_leagues_key()
        except Exception as e:
            raise ValidationError(f"Failed to generate secret key: {str(e)}")
        
        # Generate tournament name
        tournament_name = f"PICKLEIT OPEN - PLAY {secret_key[-5:]}"

        # Create league
        open_play_event = Leagues(
            secret_key=secret_key,
            name=tournament_name,
            leagues_start_date=formatted_datetime,
            registration_fee=registration_fee,
            others_fees={},
            image=None,
            description=description,
            play_type=play_type,
            team_type=team_type_obj,
            team_person=person_type_obj,
            max_number_team=max_number_team,
            location=location,
            latitude=latitude,
            longitude=longitude,
            created_by=user,
            league_type=league_type,
        )
        
        # Save league and handle potential database errors
        try:
            open_play_event.save()
        except Exception as e:
            raise ValidationError(f"Failed to save league: {str(e)}")

        # Store play type
        try:
            LeaguesPlayType.objects.create(
                type_name=play_type,
                league_for=open_play_event,
                data=play_type_data
            )
        except Exception as e:
            raise ValidationError(f"Failed to create play type: {str(e)}")

        # Handle invitations
        invited_users = set(invite_user_uuid)  # Remove duplicates
        if user.uuid not in invited_users:  # Ensure the creator is included
            invited_users.add(str(user.uuid))

        # Send notifications
        title = "Created Open Play event invitation"
        notify_message = f"{user.first_name} sent you an invitation for OpenPlay, Please show your interest"
        flg = None
        for invite_uuid in invited_users:
            invite_user = get_object_or_404(User, uuid=invite_uuid)
            try:
                OpenPlayInvitation.objects.create(
                    user=invite_user,
                    event=open_play_event,
                    invited_by=user
                )
                notify_edited_player(invite_user.id, title, notify_message)
            except Exception as e:
                flg = str(e)

        

        data["status"] = status.HTTP_200_OK
        data["message"] = f"Open Play created and players invited successfully"
        if flg:
            data["message"] = f"Open Play created and players invited successfully. error {flg}"
    except Exception as e:
        logger.error(f'Error in create_open_play_event_randomize: {str(e)}', exc_info=True)
        data["status"] = status.HTTP_200_OK
        data["message"] = f"error: {str(e)}"
    return Response(data)


@api_view(['GET'])
def show_invitation_list(request):
    """API to list pending open play invitations with user and event details."""
    context = {
        'message': '',
        'data': [],
        'count': 0,
        'previous': None,
        'next': None,
        'status': status.HTTP_200_OK
    }
    
    try:
        user_uuid = request.GET.get('user_uuid')
        if not user_uuid:
            raise ValueError("user_uuid is required")
        
        user = get_object_or_404(User, uuid=user_uuid)
        
        # Define today
        today = date.today()
        
        # Filter invitations for the user with status 'Pending' and future events
        invitations = OpenPlayInvitation.objects.filter(
            user=user,
            event__leagues_start_date__gte=today
        ).exclude(status="Declined").select_related('user', 'event', 'invited_by').order_by('-created_at')
        
        # Paginate the queryset
        paginator = InvitationPagination()
        result_page = paginator.paginate_queryset(invitations, request)
        
        # Serialize the data
        serializer = OpenPlayInvitationSerializer(result_page, many=True)
        paginated_response = paginator.get_paginated_response(serializer.data)
        
        context.update({
            'message': 'Data found',
            'data': paginated_response.data['results'],
            'count': paginated_response.data['count'],
            'previous': paginated_response.data['previous'],
            'next': paginated_response.data['next'],
            'status': status.HTTP_200_OK
        })
        
    except User.DoesNotExist:
        logger.error(f'Error in show_invitation_list no user', exc_info=True)
        context.update({
            'message': 'User not found',
            'status': status.HTTP_404_NOT_FOUND
        })
    except ValueError as ve:
        logger.error(f'Error in show_invitation_list value error: {str(ve)}', exc_info=True)
        context.update({
            'message': str(ve),
            'status': status.HTTP_400_BAD_REQUEST
        })
    except Exception as e:
        logger.error(f'Error in show_invitation_list: {str(e)}', exc_info=True)
        context.update({
            'message': f"An unexpected error occurred: {str(e)}",
            'status': status.HTTP_400_BAD_REQUEST
        })
    
    return Response(context)


@api_view(['POST'])
def response_invitation(request):
    data = {'status': '', 'message': ''}
    try:
        user_uuid = request.data.get('user_uuid')
        invitation_id = request.data.get('invitation_id')
        is_status = request.data.get('is_status')
        user = get_object_or_404(User, uuid=user_uuid)
        get_invitation = get_object_or_404(OpenPlayInvitation, id=invitation_id)
        slg = 'Pending'
        if is_status in ["True", "true", 1, True]:
            get_invitation.status = 'Accepted'
            slg = 'Accepted'
        else:
            get_invitation.status = 'Declined'
            slg = 'Declined'
        get_invitation.save()
        #send notification to invited by
        title = "Invitation Responce"
        notify_message = f"{user.first_name} {slg} your invitation for OpenPlay."
        notify_edited_player(get_invitation.invited_by.id, title, notify_message)
        data["status"] = status.HTTP_200_OK
        data["message"] = "Thank you for your response"
        return Response(data)
    except Exception as e:
        logger.error(f'Error in response_invitation: {str(e)}', exc_info=True)
        data["status"] = status.HTTP_200_OK
        data["message"] = str(e)
        return Response(data)


@api_view(['GET'])
def view_open_play_join_user_list(request):    
    data = {
        'status': '',
        'is_team': False,
        'data': [],
        'message': ''
    }
    
    try:
        # Extract query parameters
        user_uuid = request.GET.get('user_uuid')
        league_uuid = request.GET.get('league_uuid')
        
        # Validate query parameters
        if not user_uuid or not league_uuid:
            data['message'] = "Missing user_uuid or league_uuid parameters"
            data['status'] = status.HTTP_400_BAD_REQUEST
            return Response(data)

        # Fetch user and league, handling potential errors
        try:
            user = get_object_or_404(User, uuid=user_uuid)
            event = get_object_or_404(Leagues, uuid=league_uuid)
        except ValueError:
            data['message'] = "Invalid UUID format"
            data['status'] = status.HTTP_400_BAD_REQUEST
            return Response(data)

        # Check play_type
        if event.play_type != 'Robin Randomizer':
            data['data'] = []
            data['message'] = "Event is not a Robin Randomizer"
            data['status'] = status.HTTP_200_OK
            return Response(data)

        # Check for registered teams
        if event.registered_team.exists():  # Using exists() for efficiency
            try:
                serialized_team_list = TeamListSerializer(event.registered_team.all(), many=True, context={'request': request})
                data['data'] = serialized_team_list.data
                data['is_team'] = True
                data['message'] = "Get Event join team list"
                data['status'] = status.HTTP_200_OK
                return Response(data)
            except Exception as e:
                data['message'] = f"Error serializing team list: {str(e)}"
                data['status'] = status.HTTP_500_INTERNAL_SERVER_ERROR
                return Response(data)

        # Fetch accepted invitations
        try:
            accepted_invitations = OpenPlayInvitation.objects.filter(status='Accepted', event=event)
            accepted_users = [invitation.user for invitation in accepted_invitations]
            serialized_user_list = UserListSerializer(accepted_users, many=True, context={'request': request})
            data['data'] = serialized_user_list.data
            data['message'] = "Get Event join user list"
            data['status'] = status.HTTP_200_OK
            return Response(data)
        except Exception as e:
            data['message'] = f"Error processing user list: {str(e)}"
            data['status'] = status.HTTP_200_OK
            return Response(data)

    except Exception as e:
        logger.error(f'Error in view_open_play_join_user_list: {str(e)}', exc_info=True)
        data['message'] = f"An unexpected error occurred: {str(e)}"
        data['status'] = status.HTTP_200_OK
        return Response(data)


def create_random_sublists(player_ids, n=1):
    """
    Divide a list of player IDs into len(list)/n random sublists, each containing n elements.
    
    Args:
        player_ids (list): List of player IDs.
        n (int): Number of elements per sublist.
    
    Returns:
        list: A list of sublists, each containing n player IDs.
    
    Raises:
        ValueError: If the list is empty, n is invalid, or list length is not divisible by n.
    """
    if not player_ids:
        raise ValueError("Player ID list cannot be empty")
    if n <= 0:
        raise ValueError("n must be a positive integer")
    if len(player_ids) % n != 0:
        raise ValueError(f"Number of players ({len(player_ids)}) must be divisible by n ({n})")
    
    shuffled_list = player_ids.copy()
    random.shuffle(shuffled_list)
    
    num_sublists = len(player_ids) // n
    return [shuffled_list[i*n : (i+1)*n] for i in range(num_sublists)]

@api_view(['POST'])
def create_selected_user_team(request):
    """
    API to create teams from a list of selected players for an event with 'Robbin Randomizer' play type.
    
    Request logger.error(f'Error in view_open_play_join_user_list: {str(e)}', exc_info=True)body:
        - user_uuid: UUID of the user creating the team
        - event_uuid: UUID of the Leagues event
        - invitation_id: List of player IDs to form teams
    
    Returns:
        JSON response with status and message
    """
    data = {"status": None, "message": None}
    
    try:
        # Validate required fields
        required_fields = ['user_uuid', 'event_uuid', 'selected_user_list']
        for field in required_fields:
            if not request.data.get(field):
                raise ValidationError(f"Missing required field: {field}")
        
        # Fetch user and event
        user = get_object_or_404(User, uuid=request.data.get('user_uuid'))
        event = get_object_or_404(Leagues, uuid=request.data.get('event_uuid'))
        selected_user_list = request.data.get('selected_user_list')
        print(selected_user_list)
        # Validate event play type
        if event.play_type != 'Robin Randomizer':
            raise ValidationError("Event must have 'Robin Randomizer' play type")
        
        # Determine team person count
        team_person_count = 0
        team_person_name = event.team_person.name
        if team_person_name == "One Person Team":
            team_person_count = 1
        elif team_person_name == "Two Person Team":
            team_person_count = 2
 
        else:
            raise ValidationError("Invalid team person type")
        
        # Validate selected user list
        if not isinstance(selected_user_list, list) or len(selected_user_list) == 0:
            raise ValidationError("invitation_id must be a non-empty list of player IDs")
        
        # Validate player IDs and check for duplicates
        if len(selected_user_list) != len(set(selected_user_list)):
            raise ValidationError("Duplicate player IDs are not allowed")
        
        for player_id in selected_user_list:
            if not Player.objects.filter(player_id=player_id).exists():
                raise ValidationError(f"Invalid player ID: {player_id}")
        
        # Create random sublists
        user_sets = create_random_sublists(selected_user_list, team_person_count)
        # team_list = []
        # Create teams
        for player_set in user_sets:
            obj = GenerateKey()
            team_secret_key = obj.gen_team_key()
            
            if team_person_count == 1:
                player1 = Player.objects.get(player_id=player_set[0])
                team_name = f"{player1.player.first_name} {team_secret_key[-6:]}"
                team_person = 'One Person Team'
            else:
                player1 = Player.objects.get(player_id=player_set[0])
                player2 = Player.objects.get(player_id=player_set[1])
                team_name = f"{player1.player.first_name}&{player2.player.first_name} {team_secret_key[-6:]}"
                team_person = 'Two Person Team'
            
            # Check if players are already in a team for this event
            for player in [player1, player2] if team_person_count == 2 else [player1]:
                if player.team.filter(leagues=event).exists():
                    raise ValidationError(f"Player {player.player.first_name} is already in a team for this event")
            
            # Create team
            team = Team(
                secret_key=team_secret_key,
                name=team_name,
                team_person=team_person,
                team_type='Open-team',
                created_by=user,
                is_disabled=True
            )
            team.save()
            
            # Add players to the team
            event.registered_team.add(team)  # Assuming Team has a ManyToManyField to Leagues
            player1.team.add(team)
            if team_person_count == 2:
                player2.team.add(team)

        
        data['message'] = "Teams created successfully"
        data['status'] = status.HTTP_201_CREATED
    
    except ValidationError as ve:
        logger.error(f'Error in create_selected_user_team value error: {str(e)}', exc_info=True)
        data['status'] = status.HTTP_200_OK
        data['message'] = str(ve)
    except User.DoesNotExist:
        logger.error(f'Error in create_selected_user_team user do not exist', exc_info=True)
        data['status'] = status.HTTP_200_OK
        data['message'] = "User not found"
    except Leagues.DoesNotExist:
        logger.error(f'Error in create_selected_user_team event do not exist', exc_info=True)
        data['status'] = status.HTTP_200_OK
        data['message'] = "Event not found"
    except Player.DoesNotExist:
        logger.error(f'Error in create_selected_user_team player do not exist', exc_info=True)
        data['status'] = status.HTTP_200_OK
        data['message'] = "One or more players not found"
    except Exception as e:
        logger.error(f'Error in create_selected_user_team: {str(e)}', exc_info=True)
        data['status'] = status.HTTP_200_OK
        data['message'] = f"An unexpected error occurred: {str(e)}"
    
    return Response(data)
            


