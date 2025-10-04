from apps.team.views import haversine
from apps.user.models import *
from apps.chat.models import *
from apps.team.models import *
from apps.user.helpers import *
from apps.team.serializers import *
from apps.pickleitcollection.models import *
from django.conf import settings
from django.core.cache import cache
from django.shortcuts import render, get_object_or_404
from django.db.models import Q
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.pagination import PageNumberPagination
import pytz
import logging
logger = logging.getLogger('myapp')



logger = logging.getLogger(__name__)


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

@api_view(['GET'])
def view_playtype_details(request):
    data = {
        'status': '',
        'create_group_status': False,
        'max_team': None,
        'total_register_team': None,
        'is_organizer': False,
        'is_register': False,
        'sub_organizer_data': [],
        'organizer_name_data': [],
        'invited_code': None,
        'winner_team': 'Not Declared',
        'data': [],
        'tournament_detais': [],
        'message': '',
        'timezone': ''  # Added to match other endpoints
    }
    try:
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        league_uuid = request.GET.get('league_uuid')
        league_secret_key = request.GET.get('league_secret_key')
        tz, timezone_str = get_timezone(request)
        data['timezone'] = timezone_str

        # Optimize user and league checks with single queries
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key).first()
        check_league = Leagues.objects.filter(uuid=league_uuid, secret_key=league_secret_key).select_related(
            'created_by', 'team_type', 'team_person'
        ).prefetch_related('registered_team', 'add_organizer').first()

        if not (check_user and check_league):
            data['status'] = status.HTTP_404_NOT_FOUND
            data['message'] = 'User or league not found.'
            return Response(data)

        # Fetch league data with timezone conversion
        league_data = {
            'id':check_league.id,
            'uuid': check_league.uuid,
            'secret_key': check_league.secret_key,
            'name': check_league.name,
            'location': check_league.location,
            'leagues_start_date': check_league.leagues_start_date,
            'leagues_end_date': check_league.leagues_end_date,
            'registration_start_date': check_league.registration_start_date,
            'registration_end_date': check_league.registration_end_date,
            'team_type__name': check_league.team_type.name if check_league.team_type else None,
            'team_person__name': check_league.team_person.name if check_league.team_person else None,
            'street': check_league.street,
            'city': check_league.city,
            'state': check_league.state,
            'postal_code': check_league.postal_code,
            'country': check_league.country,
            'complete_address': check_league.complete_address,
            'latitude': check_league.latitude,
            'longitude': check_league.longitude,
            'play_type': check_league.play_type,
            'registration_fee': check_league.registration_fee,
            'description': check_league.description,
            'image': str(check_league.image) if check_league.image else None,
            'others_fees': check_league.others_fees,
            'league_type': check_league.league_type
        }
        convert_datetime_fields(league_data, tz, [
            'leagues_start_date', 'leagues_end_date', 'registration_start_date', 'registration_end_date'
        ])
        data['data'] = [league_data]

        # Check registration eligibility
        today_date = datetime.now(tz).date()
        if (check_league.registration_end_date and
            check_league.registration_end_date.date() >= today_date and
            check_league.league_type != "Invites only" and
            check_league.max_number_team > check_league.registered_team.count() and
            not check_league.is_complete):
            data['is_register'] = True

        # Fetch organizer and sub-organizer data in one query
        organizer_ids = [check_league.created_by.id] + list(check_league.add_organizer.values_list('id', flat=True))
        organizers = User.objects.filter(id__in=organizer_ids).values(
            'id', 'uuid', 'secret_key', 'username', 'first_name', 'last_name', 'email', 'phone',
            'gender', 'user_birthday', 'role', 'rank', 'image', 'street', 'city', 'state', 'country', 'postal_code'
        )
        organizer_list = [
            {
                **org,
                'phone': str(org['phone']) if org['phone'] else None,
                'image': f"https://{request.get_host()}{settings.MEDIA_URL}{org['image']}" if org['image'] else None
            } for org in organizers
        ]
        data['sub_organizer_data'] = organizer_list
        data['organizer_name_data'] = [
            f"{org['first_name'] or ''} {org['last_name'] or ''}".strip() for org in organizer_list
        ]

        # Check if user is organizer
        data['is_organizer'] = check_user == check_league.created_by or check_user.id in organizer_ids
        data['create_group_status'] = check_user.is_organizer and check_user == check_league.created_by
        data['invited_code'] = check_league.invited_code if data['is_organizer'] else None
        from urllib.parse import urljoin
        # Fetch teams
        # media_base_url = f"{request.scheme}://{request.get_host()}{settings.MEDIA_URL}"
        media_base_url = urljoin(f"https://{request.get_host()}/", settings.MEDIA_URL)
        teams = []
        for team in check_league.registered_team.all():
            team_image = f"{media_base_url}{team.team_image}" if team.team_image else "https://pickleit.app/static/images/pickleit_newlogo.jpg"
            players = list(Player.objects.filter(team=team).values_list('player_full_name', flat=True))
            teams.append({
                'team_uuid': team.uuid,
                'team_secret_key': team.secret_key,
                'name': team.name,
                'team_image': team_image,
                'person': team.team_person,
                'team_type': team.team_type,
                'player': players
            })
        data['teams'] = teams
        data['max_team'] = check_league.max_number_team
        data['total_register_team'] = check_league.registered_team.count()

        # Cancellation policy and refund calculation
        day_left = (check_league.leagues_start_date.date() - today_date).days if check_league.leagues_start_date else 0
        data['is_cancel_button'] = check_league.leagues_start_date.date() > today_date if check_league.leagues_start_date else False
        data['day_left'] = day_left

        cancellation_policy = list(LeaguesCancellationPolicy.objects.filter(league=check_league).order_by('within_day').values('within_day', 'refund_percentage'))
        charge_refund_percentage_per_team = 100.0 if not cancellation_policy or not check_league.policy else 0.0
        if check_league.policy and cancellation_policy:
            for rule in cancellation_policy:
                if day_left >= rule['within_day']:
                    charge_refund_percentage_per_team = rule['refund_percentage']
        data['cancellation_policy'] = cancellation_policy
        data['refund_parcentage'] = charge_refund_percentage_per_team

        # Calculate fees
        fees = check_league.registration_fee or 0
        if check_league.others_fees:
            for val in check_league.others_fees.values():
                if isinstance(val, (int, float)):
                    fees += val
                elif isinstance(val, str) and val.isdigit():
                    fees += int(val)
        data['fees'] = fees
        data['refund_amount'] = fees * (charge_refund_percentage_per_team / 100)

        # Tournament details
        data['tournament_detais'] = list(LeaguesPlayType.objects.filter(league_for=check_league).values())
        # save event
        data["is_save_league"] = SaveLeagues.objects.filter(ch_league=check_league).exists()
        # Winner team
        data['winner_team'] = check_league.winner_team.name if check_league.winner_team else 'Not Declared'

        data['status'] = status.HTTP_200_OK
        data['message'] = 'Play type details fetched successfully.'
        return Response(data)

    except Exception as e:
        logger.error(f'Error in view_playtype_details: {str(e)}', exc_info=True)
        data['status'] = status.HTTP_404_NOT_FOUND
        data['message'] = f'Error: {str(e)}'
        return Response(data)

@api_view(("GET",))
def view_match_details(request):
    data = {
             'status':'',             
             'message':'',
             'match':[]
             }
    try:
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        league_uuid = request.GET.get('league_uuid')
        league_secret_key = request.GET.get('league_secret_key')
        protocol = 'https' if request.is_secure() else 'http'
        host = request.get_host()
        media_base_url = f"{protocol}://{host}{settings.MEDIA_URL}"
        '''
        registration_open, future, past
        '''
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        check_leagues = Leagues.objects.filter(uuid=league_uuid,secret_key=league_secret_key)
        if check_user.exists() and check_leagues.exists():
            league = check_leagues.first()
            get_user = check_user.first()
            tournament_details = Tournament.objects.filter(leagues=check_leagues.first()).order_by("match_number").values("id","match_number","uuid","secret_key","leagues__name"
                                                                                                                            ,"team1_id", "team2_id", "team1__team_image", "team2__team_image", 
                                                                                                                            "team1__name", "team2__name", "winner_team_id", "winner_team__name", 
                                                                                                                            "playing_date_time","match_type","group__court","is_completed"
                                                                                                                            ,"elimination_round","court_sn","set_number","court_num","points","is_drow")
            
            sub_org_list = list(league.add_organizer.all().values_list("id", flat=True))
            organizers = list(User.objects.filter(id=league.created_by.id).values_list('id', flat=True))
            
            
            organizer_list = organizers + sub_org_list
            for sc in tournament_details:
                if sc["group__court"] is None:
                    sc["group__court"] = sc["court_sn"]

                team_1_player = list(Player.objects.filter(team__id=sc["team1_id"]).values_list("player_id", flat=True))
                team_2_player = list(Player.objects.filter(team__id=sc["team2_id"]).values_list("player_id", flat=True))
                team_1_created_by = Team.objects.filter(id=sc["team1_id"]).first().created_by
                team_2_created_by = Team.objects.filter(id=sc["team2_id"]).first().created_by            
                team_1_created_by_id = team_1_created_by.id if team_1_created_by else None
                team_2_created_by_id = team_2_created_by.id if team_2_created_by else None
                check_score_set = TournamentSetsResult.objects.filter(tournament__id=sc["id"])
                if sc["is_completed"] == True:
                    sc["is_save"] = False

                if (get_user.id in organizer_list) or (get_user.id in team_1_player) or (get_user.id == team_1_created_by_id) or (get_user.id in team_2_player) or (get_user.id == team_2_created_by_id):
                    
                    sc["is_save"] = True
                    sc["is_edit"] = True
                    
                else:
                    sc["is_save"] = False
                    sc["is_edit"] = False

                check_score_approved = TournamentScoreApproval.objects.filter(tournament__id=sc["id"],  organizer_approval=True)

                if check_score_approved.exists():                
                    sc["is_save"] = False     
                    sc["is_score_approved"] = True
                    sc["is_edit"] = False   
                else:
                    sc["is_score_approved"] = False                  
                
                check_score_reported = TournamentScoreReport.objects.filter(tournament__id=sc["id"], status="Pending")
                if check_score_reported.exists():
                    sc["is_score_reported"] = True   
                            
                    if get_user.id in organizer_list:
                        sc["is_save"] = True
                        sc["is_edit"] = True
                    else:
                        sc["is_save"] = False 
                        sc["is_edit"] = True 
                else:
                    sc["is_score_reported"] = False 

                team1_approval = TournamentScoreApproval.objects.filter(tournament__id=sc["id"], team1_approval=True).exists()
                team2_approval = TournamentScoreApproval.objects.filter(tournament__id=sc["id"], team2_approval=True).exists()           

                if check_score_set.exists() and not team1_approval and ((get_user.id in team_1_player) or (get_user == team_1_created_by)) and not check_score_approved.exists() and not check_score_reported.exists():
                    sc['is_organizer'] = False
                    sc["is_button_show"] = True
                    sc['is_approve'] = True
                    sc["is_report"] = True
                    sc["is_save"] = False

                elif check_score_set.exists() and team1_approval and ((get_user.id in team_1_player) or (get_user == team_1_created_by)) and not check_score_approved.exists() and not check_score_reported.exists():
                    sc['is_organizer'] = False
                    sc["is_button_show"] = False
                    sc['is_approve'] = False
                    sc["is_report"] = False
                    sc["is_save"] = False
                
                elif check_score_set.exists() and not team2_approval and ((get_user.id in team_2_player) or (get_user == team_2_created_by)) and not check_score_approved.exists() and not check_score_reported.exists():
                    sc['is_organizer'] = False
                    sc["is_button_show"] = True
                    sc['is_approve'] = True
                    sc["is_report"] = True
                    sc["is_save"] = False
                
                elif check_score_set.exists() and  team2_approval and ((get_user.id in team_2_player) or (get_user == team_2_created_by)) and not check_score_approved.exists() and not check_score_reported.exists():
                    sc['is_organizer'] = False
                    sc["is_button_show"] = False
                    sc['is_approve'] = False
                    sc["is_report"] = False
                    sc["is_save"] = False
                    
                elif check_score_set.exists() and (get_user.id in organizer_list) and team1_approval and team2_approval and not check_score_approved.exists() and not check_score_reported.exists():
                    sc['is_organizer'] = True
                    sc["is_button_show"] = True
                    sc['is_approve'] = True
                    sc["is_report"] = False
                    sc["is_save"] = False
                    
                elif check_score_set.exists() and (get_user.id in organizer_list) and (team1_approval or team2_approval) and not check_score_approved.exists() and not check_score_reported.exists():   
                    sc['is_organizer'] = True
                    sc["is_button_show"] = True        
                    sc['is_approve'] = True
                    sc["is_report"] = False
                    sc["is_save"] = False

                elif check_score_set.exists() and (get_user.id in organizer_list) and not (team1_approval or team2_approval) and not check_score_approved.exists() and not check_score_reported.exists():   
                    sc['is_organizer'] = True
                    sc["is_button_show"] = True            
                    sc['is_approve'] = True
                    sc["is_report"] = False
                    sc["is_save"] = False
                else:
                    sc['is_organizer'] = False
                    sc["is_button_show"] = False
                    sc['is_approve'] = False
                    sc["is_report"] = False
                    # sc["is_save"] = False

                if sc["team1__team_image"] != "":
                    img_str = sc["team1__team_image"]
                    sc["team1__team_image"] = f"{media_base_url}{img_str}"
                if sc["team2__team_image"] != "":
                    img_str = sc["team2__team_image"]
                    sc["team2__team_image"] = f"{media_base_url}{img_str}"
                #"set_number","court_num","points"
                set_list_team1 = []
                set_list_team2 = []
                score_list_team1 = []
                score_list_team2 = []
                win_status_team1 = []
                win_status_team2 = []
                is_completed_match = sc["is_completed"]
                is_win_match_team1 = False
                is_win_match_team2 = False
                team1_name = sc["team1__name"]
                team2_name = sc["team2__name"]
                if sc["team1_id"] == sc["winner_team_id"] and sc["winner_team_id"] is not None:
                    is_win_match_team1 = True
                    is_win_match_team2 = False
                elif sc["team2_id"] == sc["winner_team_id"] and sc["winner_team_id"] is not None:
                    is_win_match_team2 = True
                    is_win_match_team1 = False
            
                for s in range(sc["set_number"]):
                    index = s+1
                    set_str = f"s{index}"
                    set_list_team1.append(set_str)
                    set_list_team2.append(set_str)
                    score_details_for_set = TournamentSetsResult.objects.filter(tournament_id=sc["id"],set_number=index).values()
                    if len(score_details_for_set)!=0:
                        team_1_score = score_details_for_set[0]["team1_point"]
                        team_2_score = score_details_for_set[0]["team2_point"]
                    else:
                        team_1_score = None
                        team_2_score = None
                    score_list_team1.append(team_1_score)
                    score_list_team2.append(team_2_score)
                    if team_1_score is not None and team_2_score is not None:
                        if team_1_score >= team_2_score:
                            win_status_team1.append(True)
                            win_status_team2.append(False)
                        else:
                            win_status_team1.append(False)
                            win_status_team2.append(True)
                    else:
                        win_status_team1.append(False)
                        win_status_team2.append(False)
                score = [
                    {
                        "name": team1_name,"set": set_list_team1,
                        "score": score_list_team1,"win_status": win_status_team1,
                        "is_win": is_win_match_team1,"is_completed": is_completed_match,
                        "is_drow":sc["is_drow"]
                        },
                    {
                    "name": team2_name,"set": set_list_team2,
                    "score": score_list_team2,"win_status": win_status_team2,
                    "is_win": is_win_match_team2,"is_completed": is_completed_match,
                    "is_drow":sc["is_drow"]
                    }
                    ]
                sc["score"] = score
                # print(score)
            
                # List to store data for the point table
            tournament_details = sorted(tournament_details, key=lambda x: x['is_completed'])
            data['match'] = tournament_details
            data['message'] = "Match details fetched successfully."
            data['status'] = status.HTTP_200_OK
        else:
            data["status"], data["message"] = status.HTTP_404_NOT_FOUND, f"User or league not found."
        return Response(data)
    except Exception as e:
        logger.error(f'Error in view match details: {str(e)}', exc_info=True)
        data["status"], data["message"] = status.HTTP_200_OK, f"error: {str(e)}"
        return Response(data)

@api_view(("GET",))
def view_elimination_details(request):
    data = {
             'status':'',             
             'elemination':[], 
             'semi_final':[],
             'final':[], 
             'message':''
             }
    try:
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        league_uuid = request.GET.get('league_uuid')
        league_secret_key = request.GET.get('league_secret_key')
        protocol = 'https' if request.is_secure() else 'http'
        host = request.get_host()
        media_base_url = f"{protocol}://{host}{settings.MEDIA_URL}"
        '''
        registration_open, future, past
        '''
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        check_leagues = Leagues.objects.filter(uuid=league_uuid,secret_key=league_secret_key)
        if check_user.exists() and check_leagues.exists():
            league = check_leagues.first()
            get_user = check_user.first()
            sub_org_list = list(league.add_organizer.all().values_list("id", flat=True))        
            organizers = list(User.objects.filter(id=league.created_by.id).values_list('id', flat=True))
            
            
            organizer_list = organizers + sub_org_list
            knock_out_tournament_elimination_data = Tournament.objects.filter(leagues=check_leagues.first(),match_type="Elimination Round").values("id","uuid","secret_key","match_number","match_type","elimination_round","team1__name", "team1_id", "team2_id"
                                                                                                                ,"team1__team_image","team2__name","team2__team_image","winner_team__name", "winner_team_id", "loser_team_id", "winner_team__team_image","loser_team__name","loser_team__team_image","is_completed","play_ground_name")
            for ele_tour in knock_out_tournament_elimination_data:

                team_1_player = list(Player.objects.filter(team__id=ele_tour["team1_id"]).values_list("player_id", flat=True))
                team_2_player = list(Player.objects.filter(team__id=ele_tour["team2_id"]).values_list("player_id", flat=True))
                team_1_created_by = Team.objects.filter(id=ele_tour["team1_id"]).first().created_by
                team_2_created_by = Team.objects.filter(id=ele_tour["team2_id"]).first().created_by

                # ele_tour["is_edit"] = get_user.is_organizer and check_leagues.first().created_by == get_user or ele_tour["team1_id"] == get_user.id or ele_tour["team2_id"] == get_user.id
                if (get_user.id in organizer_list) or (get_user.id in team_1_player) or (get_user == team_1_created_by) or (get_user.id in team_2_player) or ((get_user == team_2_created_by)):
                    ele_tour["is_save"] = True
                    ele_tour["is_edit"] = True
                else:
                    ele_tour["is_save"] = False
                    ele_tour["is_edit"] = False

                check_score_approved = TournamentScoreApproval.objects.filter(tournament__id=ele_tour["id"], organizer_approval=True)

                if check_score_approved.exists():                
                    ele_tour["is_save"] = False     
                    ele_tour["is_score_approved"] = True
                    ele_tour["is_edit"] = False   
                else:
                    ele_tour["is_score_approved"] = False                  
                
                check_score_reported = TournamentScoreReport.objects.filter(tournament__id=ele_tour["id"], status="Pending")
                if check_score_reported.exists():
                    ele_tour["is_score_reported"] = True   
                            
                    if get_user.id in organizer_list:
                        ele_tour["is_save"] = True
                        ele_tour["is_edit"] = True
                    else:
                        ele_tour["is_save"] = False 
                        ele_tour["is_edit"] = False 
                else:
                    ele_tour["is_score_reported"] = False 

                team1_approval = TournamentScoreApproval.objects.filter(tournament__id=ele_tour["id"], team1_approval=True).exists()
                team2_approval = TournamentScoreApproval.objects.filter(tournament__id=ele_tour["id"], team2_approval=True).exists()
                check_score_set = TournamentSetsResult.objects.filter(tournament__id=ele_tour["id"])

                if check_score_set.exists() and not team1_approval and ((get_user.id in team_1_player) or (get_user == team_1_created_by)) and not check_score_approved.exists() and not check_score_reported.exists():
                    ele_tour['is_organizer'] = False
                    ele_tour["is_button_show"] = True
                    ele_tour['is_approve'] = True
                    ele_tour["is_report"] = True
                    ele_tour["is_save"] = False

                elif check_score_set.exists() and team1_approval and ((get_user.id in team_1_player) or (get_user == team_1_created_by)) and not check_score_approved.exists() and not check_score_reported.exists():
                    ele_tour['is_organizer'] = False
                    ele_tour["is_button_show"] = False
                    ele_tour['is_approve'] = False
                    ele_tour["is_report"] = False
                    ele_tour["is_save"] = False
                
                elif check_score_set.exists() and not team2_approval and ((get_user.id in team_2_player) or (get_user == team_2_created_by)) and not check_score_approved.exists() and not check_score_reported.exists():
                    ele_tour['is_organizer'] = False
                    ele_tour["is_button_show"] = True
                    ele_tour['is_approve'] = True
                    ele_tour["is_report"] = True
                    ele_tour["is_save"] = False
                
                elif check_score_set.exists() and  team2_approval and ((get_user.id in team_2_player) or (get_user == team_2_created_by)) and not check_score_approved.exists() and not check_score_reported.exists():
                    ele_tour['is_organizer'] = False
                    ele_tour["is_button_show"] = False
                    ele_tour['is_approve'] = False
                    ele_tour["is_report"] = False
                    ele_tour["is_save"] = False
                    
                elif check_score_set.exists() and (get_user.id in organizer_list) and team1_approval and team2_approval and not check_score_approved.exists() and not check_score_reported.exists():
                    ele_tour['is_organizer'] = True
                    ele_tour["is_button_show"] = True
                    ele_tour['is_approve'] = True
                    ele_tour["is_report"] = False
                    ele_tour["is_save"] = False
                    
                elif check_score_set.exists() and (get_user.id in organizer_list) and (team1_approval or team2_approval) and not check_score_approved.exists() and not check_score_reported.exists():   
                    ele_tour['is_organizer'] = True
                    ele_tour["is_button_show"] = True        
                    ele_tour['is_approve'] = True
                    ele_tour["is_report"] = False
                    ele_tour["is_save"] = False

                elif check_score_set.exists() and (get_user.id in organizer_list) and not (team1_approval or team2_approval) and not check_score_approved.exists() and not check_score_reported.exists():   
                    ele_tour['is_organizer'] = True
                    ele_tour["is_button_show"] = True            
                    ele_tour['is_approve'] = True
                    ele_tour["is_report"] = False
                    ele_tour["is_save"] = False
                else:
                    ele_tour['is_organizer'] = False
                    ele_tour["is_button_show"] = False
                    ele_tour['is_approve'] = False
                    ele_tour["is_report"] = False
                    # ele_tour["is_save"] = False

                score = [{"name": "","set": [],"score": [],"win_status": [],"is_win": True,"is_completed": True},{"name": "","set": [],"score": [],"win_status": [],"is_win": True,"is_completed": True}]
                
                if ele_tour["team1_id"] == ele_tour["winner_team_id"] and ele_tour["winner_team_id"] is not None:
                    score[0]["is_win"] = True
                    score[1]["is_win"] = False
                elif ele_tour["team2_id"] == ele_tour["winner_team_id"] and ele_tour["winner_team_id"] is not None:
                    score[1]["is_win"] = True
                    score[0]["is_win"] = False
                else:
                    score[1]["is_win"] = None
                    score[0]["is_win"] = None
                score_details = TournamentSetsResult.objects.filter(tournament_id=ele_tour["id"]).values()
                score[0]["name"] = ele_tour["team1__name"]
                score[1]["name"] = ele_tour["team2__name"]
                score[0]["set"] = ["s1","s2","s3"]
                score[1]["set"] = ["s1","s2","s3"]
                for l__ in range(3):
                    
                    if l__ < len(score_details):
                        l = {"team1_point":score_details[l__]["team1_point"],"team2_point":score_details[l__]["team2_point"]}
                    else:
                        l = {"team1_point":None,"team2_point":None}
                    
                    score[0]["score"].append(l["team1_point"])
                    score[1]["score"].append(l["team2_point"])
                    
                    if l["team1_point"] == None or l["team1_point"] == None:
                        score[0]["win_status"].append(None)
                        score[1]["win_status"].append(None)
                    elif l["team1_point"] > l["team2_point"]:
                        score[0]["win_status"].append(True)
                        score[1]["win_status"].append(False)
                    else:
                        score[0]["win_status"].append(False)
                        score[1]["win_status"].append(True)
                ele_tour["score"] = score
            data['elemination'] = list(knock_out_tournament_elimination_data)

            #this data for Semi Final   
            knock_out_semifinal_tournament_data = Tournament.objects.filter(leagues=check_leagues.first(),match_type="Semi Final").values("id","uuid","secret_key","match_number","match_type","elimination_round","team1__name", "team1_id", "team2_id"
                                                                                                            ,"team1__team_image","team2__name","team2__team_image","winner_team__name", "winner_team_id", "loser_team_id", "winner_team__team_image","loser_team__name","loser_team__team_image","is_completed","play_ground_name")
            for semi_tour in knock_out_semifinal_tournament_data:
                team_1_player = list(Player.objects.filter(team__id=semi_tour["team1_id"]).values_list("player_id", flat=True))
                team_2_player = list(Player.objects.filter(team__id=semi_tour["team2_id"]).values_list("player_id", flat=True))
                team_1_created_by = Team.objects.filter(id=semi_tour["team1_id"]).first().created_by
                team_2_created_by = Team.objects.filter(id=semi_tour["team2_id"]).first().created_by

                if (get_user.id in organizer_list) or (get_user.id in team_1_player) or (get_user == team_1_created_by) or (get_user.id in team_2_player) or ((get_user == team_2_created_by)):
                    semi_tour["is_save"] = True
                    semi_tour["is_edit"] = True
                else:
                    semi_tour["is_save"] = False
                    semi_tour["is_edit"] = False

                check_score_approved = TournamentScoreApproval.objects.filter(tournament__id=semi_tour["id"], organizer_approval=True)

                if check_score_approved.exists():                
                    semi_tour["is_save"] = False     
                    semi_tour["is_score_approved"] = True
                    semi_tour["is_edit"] = False   
                else:
                    semi_tour["is_score_approved"] = False                  
                
                check_score_reported = TournamentScoreReport.objects.filter(tournament__id=semi_tour["id"], status="Pending")
                if check_score_reported.exists():
                    semi_tour["is_score_reported"] = True   
                            
                    if get_user.id in organizer_list:
                        semi_tour["is_save"] = True
                        semi_tour["is_edit"] = True
                    else:
                        semi_tour["is_save"] = False 
                        semi_tour["is_edit"] = False 
                else:
                    semi_tour["is_score_reported"] = False 

                team1_approval = TournamentScoreApproval.objects.filter(tournament__id=semi_tour["id"], team1_approval=True).exists()
                team2_approval = TournamentScoreApproval.objects.filter(tournament__id=semi_tour["id"], team2_approval=True).exists()
                check_score_set = TournamentSetsResult.objects.filter(tournament__id=semi_tour["id"])

                if check_score_set.exists() and not team1_approval and ((get_user.id in team_1_player) or (get_user == team_1_created_by)) and not check_score_approved.exists() and not check_score_reported.exists():
                    semi_tour['is_organizer'] = False
                    semi_tour["is_button_show"] = True
                    semi_tour['is_approve'] = True
                    semi_tour["is_report"] = True
                    semi_tour["is_save"] = False

                elif check_score_set.exists() and team1_approval and ((get_user.id in team_1_player) or (get_user == team_1_created_by)) and not check_score_approved.exists() and not check_score_reported.exists():
                    semi_tour['is_organizer'] = False
                    semi_tour["is_button_show"] = False
                    semi_tour['is_approve'] = False
                    semi_tour["is_report"] = False
                    semi_tour["is_save"] = False
                
                elif check_score_set.exists() and not team2_approval and ((get_user.id in team_2_player) or (get_user == team_2_created_by)) and not check_score_approved.exists() and not check_score_reported.exists():
                    semi_tour['is_organizer'] = False
                    semi_tour["is_button_show"] = True
                    semi_tour['is_approve'] = True
                    semi_tour["is_report"] = True
                    semi_tour["is_save"] = False
                
                elif check_score_set.exists() and  team2_approval and ((get_user.id in team_2_player) or (get_user == team_2_created_by)) and not check_score_approved.exists() and not check_score_reported.exists():
                    semi_tour['is_organizer'] = False
                    semi_tour["is_button_show"] = False
                    semi_tour['is_approve'] = False
                    semi_tour["is_report"] = False
                    semi_tour["is_save"] = False
                    
                elif check_score_set.exists() and (get_user.id in organizer_list) and team1_approval and team2_approval and not check_score_approved.exists() and not check_score_reported.exists():
                    semi_tour['is_organizer'] = True
                    semi_tour["is_button_show"] = True
                    semi_tour['is_approve'] = True
                    semi_tour["is_report"] = False
                    semi_tour["is_save"] = False
                    
                elif check_score_set.exists() and (get_user.id in organizer_list) and (team1_approval or team2_approval) and not check_score_approved.exists() and not check_score_reported.exists():   
                    semi_tour['is_organizer'] = True
                    semi_tour["is_button_show"] = True        
                    semi_tour['is_approve'] = True
                    semi_tour["is_report"] = False
                    semi_tour["is_save"] = False

                elif check_score_set.exists() and (get_user.id in organizer_list) and not (team1_approval or team2_approval) and not check_score_approved.exists() and not check_score_reported.exists():   
                    semi_tour['is_organizer'] = True
                    semi_tour["is_button_show"] = True            
                    semi_tour['is_approve'] = True
                    semi_tour["is_report"] = False
                    semi_tour["is_save"] = False
                else:
                    semi_tour['is_organizer'] = False
                    semi_tour["is_button_show"] = False
                    semi_tour['is_approve'] = False
                    semi_tour["is_report"] = False
                
                score = [{"name": "","set": [],"score": [],"win_status": [],"is_win": True,"is_completed": True},{"name": "","set": [],"score": [],"win_status": [],"is_win": True,"is_completed": True}]
                
                if semi_tour["team1_id"] == semi_tour["winner_team_id"] and semi_tour["winner_team_id"] is not None:
                    score[0]["is_win"] = True
                    score[1]["is_win"] = False
                elif semi_tour["team2_id"] == semi_tour["winner_team_id"] and semi_tour["winner_team_id"] is not None:
                    score[1]["is_win"] = True
                    score[0]["is_win"] = False
                else:
                    score[1]["is_win"] = None
                    score[0]["is_win"] = None
                score_details = TournamentSetsResult.objects.filter(tournament_id=semi_tour["id"]).values()
                score[0]["name"] = semi_tour["team1__name"]
                score[1]["name"] = semi_tour["team2__name"]
                score[0]["set"] = ["s1","s2","s3"]
                score[1]["set"] = ["s1","s2","s3"]
                for l__ in range(3):
                    
                    if l__ < len(score_details):
                        l = {"team1_point":score_details[l__]["team1_point"],"team2_point":score_details[l__]["team2_point"]}
                    else:
                        l = {"team1_point":None,"team2_point":None}
                    
                    score[0]["score"].append(l["team1_point"])
                    score[1]["score"].append(l["team2_point"])
                    
                    if l["team1_point"] == None or l["team1_point"] == None:
                        score[0]["win_status"].append(None)
                        score[1]["win_status"].append(None)
                    elif l["team1_point"] > l["team2_point"]:
                        score[0]["win_status"].append(True)
                        score[1]["win_status"].append(False)
                    else:
                        score[0]["win_status"].append(False)
                        score[1]["win_status"].append(True)
                semi_tour["score"] = score
            data['semi_final'] = list(knock_out_semifinal_tournament_data)

            #this data for Final 
            knock_out_final_tournament_data = Tournament.objects.filter(leagues=check_leagues.first(),match_type="Final").values("id","uuid","secret_key","match_number","match_type","elimination_round","team1__name", "team1_id", "team2_id"
                                                                                                            ,"team1__team_image","team2__name","team2__team_image","winner_team__name", "winner_team_id", "loser_team_id", "winner_team__team_image","loser_team__name","loser_team__team_image","is_completed","play_ground_name")
            for final_tour in knock_out_final_tournament_data:
                team_1_player = list(Player.objects.filter(team__id=final_tour["team1_id"]).values_list("player_id", flat=True))
                team_2_player = list(Player.objects.filter(team__id=final_tour["team2_id"]).values_list("player_id", flat=True))
                team_1_created_by = Team.objects.filter(id=final_tour["team1_id"]).first().created_by
                team_2_created_by = Team.objects.filter(id=final_tour["team2_id"]).first().created_by

                if (get_user.id in organizer_list) or (get_user.id in team_1_player) or (get_user == team_1_created_by) or (get_user.id in team_2_player) or ((get_user == team_2_created_by)):
                    final_tour["is_save"] = True
                    final_tour["is_edit"] = True
                else:
                    final_tour["is_save"] = False
                    final_tour["is_edit"] = False

                check_score_approved = TournamentScoreApproval.objects.filter(tournament__id=final_tour["id"], organizer_approval=True)

                if check_score_approved.exists():                
                    final_tour["is_save"] = False     
                    final_tour["is_score_approved"] = True
                    final_tour["is_edit"] = False   
                else:
                    final_tour["is_score_approved"] = False                  
                
                check_score_reported = TournamentScoreReport.objects.filter(tournament__id=final_tour["id"], status="Pending")
                if check_score_reported.exists():
                    final_tour["is_score_reported"] = True   
                            
                    if get_user.id in organizer_list:
                        final_tour["is_save"] = True
                        final_tour["is_edit"] = True
                    else:
                        final_tour["is_save"] = False 
                        final_tour["is_edit"] = False 
                else:
                    final_tour["is_score_reported"] = False 

                team1_approval = TournamentScoreApproval.objects.filter(tournament__id=final_tour["id"], team1_approval=True).exists()
                team2_approval = TournamentScoreApproval.objects.filter(tournament__id=final_tour["id"], team2_approval=True).exists()
                check_score_set = TournamentSetsResult.objects.filter(tournament__id=final_tour["id"])

                if check_score_set.exists() and not team1_approval and ((get_user.id in team_1_player) or (get_user == team_1_created_by)) and not check_score_approved.exists() and not check_score_reported.exists():
                    final_tour['is_organizer'] = False
                    final_tour["is_button_show"] = True
                    final_tour['is_approve'] = True
                    final_tour["is_report"] = True
                    final_tour["is_save"] = False

                elif check_score_set.exists() and team1_approval and ((get_user.id in team_1_player) or (get_user == team_1_created_by)) and not check_score_approved.exists() and not check_score_reported.exists():
                    final_tour['is_organizer'] = False
                    final_tour["is_button_show"] = False
                    final_tour['is_approve'] = False
                    final_tour["is_report"] = False
                    final_tour["is_save"] = False
                
                elif check_score_set.exists() and not team2_approval and ((get_user.id in team_2_player) or (get_user == team_2_created_by)) and not check_score_approved.exists() and not check_score_reported.exists():
                    final_tour['is_organizer'] = False
                    final_tour["is_button_show"] = True
                    final_tour['is_approve'] = True
                    final_tour["is_report"] = True
                    final_tour["is_save"] = False
                
                elif check_score_set.exists() and  team2_approval and ((get_user.id in team_2_player) or (get_user == team_2_created_by)) and not check_score_approved.exists() and not check_score_reported.exists():
                    final_tour['is_organizer'] = False
                    final_tour["is_button_show"] = False
                    final_tour['is_approve'] = False
                    final_tour["is_report"] = False
                    final_tour["is_save"] = False
                    
                elif check_score_set.exists() and (get_user.id in organizer_list) and team1_approval and team2_approval and not check_score_approved.exists() and not check_score_reported.exists():
                    final_tour['is_organizer'] = True
                    final_tour["is_button_show"] = True
                    final_tour['is_approve'] = True
                    final_tour["is_report"] = False
                    final_tour["is_save"] = False
                    
                elif check_score_set.exists() and (get_user.id in organizer_list) and (team1_approval or team2_approval) and not check_score_approved.exists() and not check_score_reported.exists():   
                    final_tour['is_organizer'] = True
                    final_tour["is_button_show"] = True        
                    final_tour['is_approve'] = True
                    final_tour["is_report"] = False
                    final_tour["is_save"] = False

                elif check_score_set.exists() and (get_user.id in organizer_list) and not (team1_approval or team2_approval) and not check_score_approved.exists() and not check_score_reported.exists():   
                    final_tour['is_organizer'] = True
                    final_tour["is_button_show"] = True            
                    final_tour['is_approve'] = True
                    final_tour["is_report"] = False
                    final_tour["is_save"] = False
                else:
                    final_tour['is_organizer'] = False
                    final_tour["is_button_show"] = False
                    final_tour['is_approve'] = False
                    final_tour["is_report"] = False
                    # final_tour["is_save"] = False

                score = [{"name": "","set": [],"score": [],"win_status": [],"is_win": True,"is_completed": True},{"name": "","set": [],"score": [],"win_status": [],"is_win": True,"is_completed": True}]
                
                if final_tour["team1_id"] == final_tour["winner_team_id"] and final_tour["winner_team_id"] is not None:
                    score[0]["is_win"] = True
                    score[1]["is_win"] = False
                elif final_tour["team2_id"] == final_tour["winner_team_id"] and final_tour["winner_team_id"] is not None:
                    score[1]["is_win"] = True
                    score[0]["is_win"] = False
                else:
                    score[1]["is_win"] = None
                    score[0]["is_win"] = None
                score_details = TournamentSetsResult.objects.filter(tournament_id=final_tour["id"]).values()
                score[0]["name"] = final_tour["team1__name"]
                score[1]["name"] = final_tour["team2__name"]
                score[0]["set"] = ["s1","s2","s3"]
                score[1]["set"] = ["s1","s2","s3"]
                for l__ in range(3):
                    
                    if l__ < len(score_details):
                        l = {"team1_point":score_details[l__]["team1_point"],"team2_point":score_details[l__]["team2_point"]}
                    else:
                        l = {"team1_point":None,"team2_point":None}
                    
                    score[0]["score"].append(l["team1_point"])
                    score[1]["score"].append(l["team2_point"])
                    
                    if l["team1_point"] == None or l["team1_point"] == None:
                        score[0]["win_status"].append(None)
                        score[1]["win_status"].append(None)
                    elif l["team1_point"] > l["team2_point"]:
                        score[0]["win_status"].append(True)
                        score[1]["win_status"].append(False)
                    else:
                        score[0]["win_status"].append(False)
                        score[1]["win_status"].append(True)
                final_tour["score"] = score
            data['final'] = list(knock_out_final_tournament_data)
            data['message'] = "Elimination details fetched successfully."
            data['status'] = status.HTTP_200_OK
            
        else:
            data["status"], data["message"] = status.HTTP_404_NOT_FOUND, f"User or league not found."
        return Response(data)
    except Exception as e:
        logger.error(f'Error in event elimination details: {str(e)}', exc_info=True)
        data["status"], data["message"] = status.HTTP_404_NOT_FOUND, f"Error : {str(e)}"
        return Response(data)

@api_view(("GET",))
def view_point_table_details(request):
    data = {
             'status':'',             
             'point_table':[],              
             'message':''             
             }
    try:
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        league_uuid = request.GET.get('league_uuid')
        league_secret_key = request.GET.get('league_secret_key')
        protocol = 'https' if request.is_secure() else 'http'
        host = request.get_host()
        media_base_url = f"{protocol}://{host}{settings.MEDIA_URL}"
        '''
        registration_open, future, past
        '''
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        check_leagues = Leagues.objects.filter(uuid=league_uuid,secret_key=league_secret_key)
        if check_user.exists() and check_leagues.exists():
            league = check_leagues.first()
            get_user = check_user.first()
            play_type_check_win = league.play_type        
            all_group_details = RoundRobinGroup.objects.filter(league_for=league)
            for grp in all_group_details:
                teams = grp.all_teams.all()
                group_score_point_table = []
                # print(teams)
                for team in teams:
                    team_score = {}
                    total_match_detals = Tournament.objects.filter(leagues=league, match_type="Round Robin").filter(Q(team1=team) | Q(team2=team))
                    completed_match_details = total_match_detals.filter(is_completed=True)
                    win_match_details = completed_match_details.filter(winner_team=team).count()
                    loss_match_details = completed_match_details.filter(loser_team=team).count()
                    drow_match = len(completed_match_details) - (win_match_details + loss_match_details)
                    match_list = list(total_match_detals.values_list("id", flat=True))
                    for_score = 0
                    aginst_score = 0
                    for sc in match_list:
                        co_team_position = Tournament.objects.filter(id=sc).first()
                        set_score = TournamentSetsResult.objects.filter(tournament_id=sc)
                        if co_team_position.team1 == team:
                            for_score = for_score + sum(list(set_score.values_list("team1_point", flat=True)))
                            aginst_score = aginst_score + sum(list(set_score.values_list("team2_point", flat=True)))
                        else:
                            for_score = for_score + sum(list(set_score.values_list("team2_point", flat=True)))
                            aginst_score = aginst_score + sum(list(set_score.values_list("team1_point", flat=True)))
                    
                    point = (win_match_details * 3) + (drow_match * 1)
                    team_score["uuid"], team_score["secret_key"] = team.uuid, team.secret_key
                    team_score["name"], team_score["completed_match"] = team.name, len(completed_match_details)
                    team_score["win_match"], team_score["loss_match"] = win_match_details, loss_match_details
                    team_score["drow_match"], team_score["for_score"] = drow_match, for_score
                    team_score["aginst_score"], team_score["point"] = aginst_score, point
                    group_score_point_table.append(team_score)
            
                tournament_details_group = Tournament.objects.filter(leagues=league,group=grp).values("id","uuid","secret_key","team1__name","team2__name","leagues__name","match_type","is_completed","group__court","play_ground_name","playing_date_time","group_id")
                for k_ in tournament_details_group:
                    round_robin_group_detals = RoundRobinGroup.objects.filter(league_for=league, id=k_["group_id"]).first()
                    k_["sets"] = round_robin_group_detals.number_sets
                    k_["court"] = round_robin_group_detals.court
                    k_["score"] = list(TournamentSetsResult.objects.filter(tournament_id=k_["id"]).values())
                
                group_score_point_table = sorted(group_score_point_table, key=lambda x: (x['point'], x['for_score']), reverse=True)
            
                ###### tournament winning team update and declare
                if play_type_check_win == "Round Robin":
                    total_tournament = Tournament.objects.filter(leagues=check_leagues.first(),match_type="Round Robin",leagues__play_type="Round Robin")
                    completed_tournament = total_tournament.filter(is_completed=True)
                    if total_tournament.count() == completed_tournament.count():
                        winner_team = Team.objects.filter(uuid=group_score_point_table[0]["uuid"]).first()
                        winner_team_name = winner_team.name
                        league.winner_team = winner_team
                        league.is_complete = True
                        league.save()
                        data["winner_team"] = winner_team_name
                grp_data = {
                    "id": grp.id,
                    "court": grp.court,
                    "league_for_id": grp.league_for_id,
                    "all_games_status": grp.all_games_status,
                    "all_tems": group_score_point_table,
                    "tournament": tournament_details_group,
                    "seleced_teams_id": grp.seleced_teams_id
                }
                data['point_table'].append(grp_data)
            
            data["status"], data["message"] = status.HTTP_200_OK, "Point table data fetched successfully."
        else:
            data["status"], data['data'], data["message"] = status.HTTP_404_NOT_FOUND, [],  "User or League not found."
        return Response(data)
    except Exception as e:
        logger.error(f'Error in event point table details: {str(e)}', exc_info=True)
        data["status"], data['data'], data["message"] = status.HTTP_404_NOT_FOUND, [],  f"Error: {str(e)}"
        return Response(data)


"""
get match result details
"""
def _handle_not_found(data):
    """Handle case when user or match is not found."""
    data["status"] = status.HTTP_404_NOT_FOUND
    data["message"] = "User or Match not found."
    data["match_details"] = []
    return data

def _get_media_base_url(request):
    """Generate media base URL for image paths."""
    protocol = 'https'
    host = request.get_host()
    return f"{protocol}://{host}{settings.MEDIA_URL}"

def _get_organizer_list(league):
    """Retrieve list of organizer IDs for the league."""
    sub_org_list = list(league.add_organizer.all().values_list("id", flat=True))
    organizers = list(User.objects.filter(id=league.created_by.id).values_list('id', flat=True))
    return organizers + sub_org_list

def _check_user_permissions(get_user, organizer_list, team1_player, team2_player, team1_created_by, team2_created_by):
    """Determine if user has save/edit permissions."""
    return (get_user.id in organizer_list or
            get_user.id in team1_player or
            get_user == team1_created_by or
            get_user.id in team2_player or
            get_user == team2_created_by)

def _handle_score_approval_and_report(sc, get_user, organizer_list, team1_player, team2_player, team1_created_by, team2_created_by):
    """Handle score approval and reporting logic."""
    check_score_approved = TournamentScoreApproval.objects.filter(tournament__id=sc["id"], organizer_approval=True)
    check_score_reported = TournamentScoreReport.objects.filter(tournament__id=sc["id"], status="Pending")
    team1_approval = TournamentScoreApproval.objects.filter(tournament__id=sc["id"], team1_approval=True).exists()
    team2_approval = TournamentScoreApproval.objects.filter(tournament__id=sc["id"], team2_approval=True).exists()
    check_score_set = TournamentSetsResult.objects.filter(tournament__id=sc["id"])

    if check_score_approved.exists():
        sc["is_save"] = False
        sc["is_score_approved"] = True
        sc["is_edit"] = False
    else:
        sc["is_score_approved"] = False

    if check_score_reported.exists():
        sc["is_score_reported"] = True
        if get_user.id in organizer_list:
            sc["is_save"] = True
            sc["is_edit"] = True
        else:
            sc["is_save"] = False
            sc["is_edit"] = False
    else:
        sc["is_score_reported"] = False

    return _handle_team_approvals(sc, get_user, organizer_list, team1_player, team2_player, team1_created_by, team2_created_by,
                                 team1_approval, team2_approval, check_score_set, check_score_approved, check_score_reported)

def _handle_team_approvals(sc, get_user, organizer_list, team1_player, team2_player, team1_created_by, team2_created_by,
                          team1_approval, team2_approval, check_score_set, check_score_approved, check_score_reported):
    """Handle team-specific approval logic."""
    if check_score_set.exists():
        if not team1_approval and (get_user.id in team1_player or get_user == team1_created_by) and not check_score_approved.exists() and not check_score_reported.exists():
            sc.update({'is_organizer': False, 'is_button_show': True, 'is_approve': True, 'is_report': True, 'is_save': False})
        elif team1_approval and (get_user.id in team1_player or get_user == team1_created_by) and not check_score_approved.exists() and not check_score_reported.exists():
            sc.update({'is_organizer': False, 'is_button_show': False, 'is_approve': False, 'is_report': False, 'is_save': False})
        elif not team2_approval and (get_user.id in team2_player or get_user == team2_created_by) and not check_score_approved.exists() and not check_score_reported.exists():
            sc.update({'is_organizer': False, 'is_button_show': True, 'is_approve': True, 'is_report': True, 'is_save': False})
        elif team2_approval and (get_user.id in team2_player or get_user == team2_created_by) and not check_score_approved.exists() and not check_score_reported.exists():
            sc.update({'is_organizer': False, 'is_button_show': False, 'is_approve': False, 'is_report': False, 'is_save': False})
        elif get_user.id in organizer_list and team1_approval and team2_approval and not check_score_approved.exists() and not check_score_reported.exists():
            sc.update({'is_organizer': True, 'is_button_show': True, 'is_approve': True, 'is_report': False, 'is_save': False})
        elif get_user.id in organizer_list and (team1_approval or team2_approval) and not check_score_approved.exists() and not check_score_reported.exists():
            sc.update({'is_organizer': True, 'is_button_show': True, 'is_approve': True, 'is_report': False, 'is_save': False})
        elif get_user.id in organizer_list and not (team1_approval or team2_approval) and not check_score_approved.exists() and not check_score_reported.exists():
            sc.update({'is_organizer': True, 'is_button_show': True, 'is_approve': True, 'is_report': False, 'is_save': False})
        else:
            sc.update({'is_organizer': False, 'is_button_show': False, 'is_approve': False, 'is_report': False})
    return sc

def _process_score_details(sc, team1_name, team2_name):
    """Process score details for each set in the match."""
    set_list_team1, set_list_team2 = [], []
    score_list_team1, score_list_team2 = [], []
    win_status_team1, win_status_team2 = [], []
    is_completed_match = sc["is_completed"]
    is_win_match_team1 = sc["team1_id"] == sc["winner_team_id"] and sc["winner_team_id"] is not None
    is_win_match_team2 = sc["team2_id"] == sc["winner_team_id"] and sc["winner_team_id"] is not None

    for s in range(sc["set_number"]):
        index = s + 1
        set_str = f"s{index}"
        set_list_team1.append(set_str)
        set_list_team2.append(set_str)
        score_details = TournamentSetsResult.objects.filter(tournament_id=sc["id"], set_number=index).values()
        team_1_score = score_details[0]["team1_point"] if score_details else None
        team_2_score = score_details[0]["team2_point"] if score_details else None
        score_list_team1.append(team_1_score)
        score_list_team2.append(team_2_score)
        win_status_team1.append(team_1_score is not None and team_2_score is not None and team_1_score >= team_2_score)
        win_status_team2.append(team_1_score is not None and team_2_score is not None and team_1_score < team_2_score)

    return [
        {
            "name": team1_name, "set": set_list_team1, "score": score_list_team1,
            "win_status": win_status_team1, "is_win": is_win_match_team1, "is_completed": is_completed_match,
            "is_drow": sc["is_drow"]
        },
        {
            "name": team2_name, "set": set_list_team2, "score": score_list_team2,
            "win_status": win_status_team1, "is_win": is_win_match_team2, "is_completed": is_completed_match,
            "is_drow": sc["is_drow"]
        }
    ]

def _process_match_details(request, get_user, get_match, data):
    """Process tournament details and permissions."""
    league = get_match.leagues
    media_base_url = _get_media_base_url(request)
    organizer_list = _get_organizer_list(league)

    tournament_details = Tournament.objects.filter(id=get_match.id).order_by("match_number").values(
        "id", "match_number", "uuid", "secret_key", "leagues__name", "team1_id", "team2_id",
        "team1__team_image", "team2__team_image", "team1__name", "team2__name", "winner_team_id",
        "winner_team__name", "playing_date_time", "match_type", "group__court", "is_completed",
        "elimination_round", "court_sn", "set_number", "court_num", "points", "is_drow"
    )

    for sc in tournament_details:
        sc["group__court"] = sc["court_sn"] if sc["group__court"] is None else sc["group__court"]
        
        team1_player = list(Player.objects.filter(team__id=sc["team1_id"]).values_list("player_id", flat=True))
        team2_player = list(Player.objects.filter(team__id=sc["team2_id"]).values_list("player_id", flat=True))
        team1_created_by = Team.objects.filter(id=sc["team1_id"]).first().created_by
        team2_created_by = Team.objects.filter(id=sc["team2_id"]).first().created_by

        # Set permissions
        if _check_user_permissions(get_user, organizer_list, team1_player, team2_player, team1_created_by, team2_created_by):
            sc["is_save"] = True
            sc["is_edit"] = True
        else:
            sc["is_save"] = False
            sc["is_edit"] = False

        # Handle score approval and reporting
        sc = _handle_score_approval_and_report(sc, get_user, organizer_list, team1_player, team2_player, team1_created_by, team2_created_by)

        # Update image URLs
        if sc["team1__team_image"]:
            sc["team1__team_image"] = f"{media_base_url}{sc['team1__team_image']}"
        if sc["team2__team_image"]:
            sc["team2__team_image"] = f"{media_base_url}{sc['team2__team_image']}"

        # Add score details
        sc["score"] = _process_score_details(sc, sc["team1__name"], sc["team2__name"])

    data['match_details'] = tournament_details
    return data


@api_view(("GET",))
def get_match_result(request):
    """
    Retrieve match result details based on user credentials and match ID.
    """
    data = {'status': '', 'match_details': [], 'message': ''}

    try:
        # Extract request parameters
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        match_id = request.GET.get('match_id')

        # Validate user and match
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        check_match = Tournament.objects.filter(id=match_id)

        if not check_user.exists() or not check_match.exists():
            return _handle_not_found(data)

        # Process match details
        data = _process_match_details(request, check_user.first(), check_match.first(), data)

        data['message'] = "Match result fetched successfully."
        data['status'] = status.HTTP_200_OK

    except Exception as e:
        logger.error(f'Error in match result: {str(e)}', exc_info=True)
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, str(e)

    return Response(data)


            
@api_view(["GET"])
def profile_stats_match_history(request):
    data = {'status': '', 'message': ''}
    try:
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        user_info = {}
        tournament_stats = {}
        match_stats = {}
        matches = []

        if check_user.exists():
            get_user = check_user.first()

            user_info["rank"] = get_user.rank
            try:
                image = get_user.image.url if get_user.image not in ["null", None, "", " "] else None
            except:
                image = None

            user_info["first_name"] = get_user.first_name
            user_info["last_name"] = get_user.last_name
            user_info["is_rank"] = get_user.is_rank
            user_info["profile_image"] = image
            

            check_player = Player.objects.filter(player__id=get_user.id)

            if check_player.exists():
                total_league = 0
                win_league = 0
                get_player = check_player.first()
                team_ids = list(get_player.team.values_list('id', flat=True))

                if len(team_ids) > 0:
                    total_played_matches = 0
                    win_match = 0

                    for team_id in team_ids:
                        lea = Leagues.objects.filter(registered_team__in=[team_id], is_complete=True)
                        total_league += lea.count()
                        win_leagues_count = lea.filter(winner_team_id=team_id).count()
                        check_match = Tournament.objects.filter(
                            Q(team1_id=team_id, is_completed=True) | Q(team2_id=team_id, is_completed=True)
                        )
                        win_check_match = check_match.filter(winner_team_id=team_id).count()
                        total_played_matches += check_match.count()
                        win_match += win_check_match
                        win_league += win_leagues_count

                        matches.extend(
                            Tournament.objects.filter(Q(team1_id=team_id) | Q(team2_id=team_id)).filter(is_completed=True).order_by("playing_date_time")
                        )

                    paginator = PageNumberPagination()
                    paginator.page_size = 5
                    result_page = paginator.paginate_queryset(matches, request)
                    serializer = TournamentSerializer(result_page, many=True, context={'request': request})

                    paginated_response = paginator.get_paginated_response(serializer.data)

                    for match in paginated_response.data["results"]:
                        match["team1"]["player_images"] = [
                            player_image if player_image else None
                            for player_image in Player.objects.filter(team__id=match["team1"]["id"]).values_list("player__image", flat=True)
                        ]

                        match["team2"]["player_images"] = [
                            player_image if player_image else None
                            for player_image in Player.objects.filter(team__id=match["team2"]["id"]).values_list("player__image", flat=True)
                        ]
                        match["team1"]["player_names"] = [
                            player_name for player_name in Player.objects.filter(team__id=match["team1"]["id"]).values_list("player_full_name", flat=True)
                        ]
                        match["team2"]["player_names"] = [
                            player_name for player_name in Player.objects.filter(team__id=match["team2"]["id"]).values_list("player_full_name", flat=True)
                        ]
                        match["is_win"] = match["winner_team_id"] in team_ids

                    tournament_stats["total_completed_turnament"] = total_league
                    tournament_stats["total_win_turnament"] = win_league
                    match_stats["total_completed_match"] = total_played_matches
                    match_stats["total_win_match"] = win_match
                    data["matches"] = paginated_response.data["results"]
                    data["count"] = paginated_response.data["count"]
                    data["previous"] = paginated_response.data["previous"]
                    data["next"] = paginated_response.data["next"]

                else:
                    tournament_stats["total_completed_turnament"] = 0
                    tournament_stats["total_win_turnament"] = 0
                    match_stats["total_completed_match"] = 0
                    match_stats["total_win_match"] = 0
                    data["matches"] = []
                    data["count"] = 0
                    data["previous"] = None
                    data["next"] = None
            else:
                tournament_stats["total_completed_turnament"] = 0
                tournament_stats["total_win_turnament"] = 0
                match_stats["total_completed_match"] = 0
                match_stats["total_win_match"] = 0
                data["matches"] = []
                data["count"] = 0
                data["previous"] = None
                data["next"] = None

            data['status'] = status.HTTP_200_OK
            data["user_info"] = user_info
            data["tournament_stats"] = tournament_stats
            data["match_stats"] = match_stats
            data['message'] = "Stats and match history fetched successfully."
        else:
            data['status'] = status.HTTP_404_NOT_FOUND
            data['message'] = "User not found."
    except Exception as e :
        logger.error(f'Error in profile_stats_match_history: {str(e)}', exc_info=True)
        data['status'], data['data'], data['message'] = status.HTTP_400_BAD_REQUEST, [], f"{e}"
    return Response(data)
 
@api_view(("GET",))
def get_tournament_count(request):
    data = {'status':'', 'message':''}
    try:
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
       
        check_user = User.objects.filter(secret_key=user_secret_key,uuid=user_uuid)
        today = datetime.now()        
        if check_user:
            get_user = check_user.first() 
            created = list(Leagues.objects.filter(created_by=get_user).values())        
            
            check_player = Player.objects.filter(player=get_user)
            if check_player:
                get_player = check_player.first()
                player_teams = get_player.team.values_list("id", flat=True) if get_player else []
                registration_end_date_leage = Leagues.objects.exclude(Q(registration_end_date__date__lte=today)|Q(is_complete=True)|Q(leagues_start_date__date__lte=today))
                joined = registration_end_date_leage.filter(registered_team__in=player_teams, is_complete=False).distinct()
                
                saved = SaveLeagues.objects.filter(created_by=get_user).count()
                
                completed = Leagues.objects.filter(
                                    Q(registered_team__in=player_teams, is_complete=True) |
                                    Q(add_organizer__in=[get_user.id], is_complete=True) |
                                    Q(created_by=get_user, is_complete=True)
                                ).distinct().count()
                data["total_joined"] = joined.count()
                data["total_saved"] = saved
                data["total_created"] = len(created)
                data["total_completed"] = completed               
            else:   
                data["total_joined"] = 0
                data["total_saved"] = 0
                data["total_created"] = 0
                data["total_completed"] = 0   
            data["status"] = status.HTTP_200_OK            
            data["message"] = f"Tournament count fetched successfully."
        else:
            data["status"] = status.HTTP_404_NOT_FOUND
            data["total_joined"] = 0
            data["total_saved"] = 0
            data["total_created"] = 0
            data["total_completed"] = 0
            data["message"] = f"User not found."
    except Exception as e :
        logger.error(f'Error in get_tournament_count: {str(e)}', exc_info=True)
        data["status"] = status.HTTP_400_BAD_REQUEST
        data["total_joined"] = 0
        data["total_saved"] = 0
        data["total_created"] = 0
        data["total_completed"] = 0
        data["message"] = f"{e}"
    return Response(data)

@api_view(("GET",))
def get_leagues_list(request):
    data = {'status':'', 'message':''}
    try:
        user_uuid = request.GET.get('user_uuid')
        check_user = User.objects.filter(uuid=user_uuid)
        if check_user:
            get_user = check_user.first()
            today_date = datetime.now()
            live_leagues = Leagues.objects.filter(leagues_start_date__date__lte=today_date, leagues_end_date__date__gte=today_date)
            upcoming_leagues = Leagues.objects.filter(Q(registration_start_date__date__lte=today_date, registration_end_date__date__gte=today_date) | Q(registration_start_date__date__gte=today_date) | Q(registration_end_date__date__lte=today_date, leagues_start_date__date__gte=today_date))
            serializer_live_leagues = LeagueSerializer(live_leagues, many=True)
            serializer_upcoming_leagues = LeagueSerializer(upcoming_leagues, many=True)
            unique_leagues = {}
            for league in serializer_live_leagues.data + serializer_upcoming_leagues.data:
                league_id = league.get('id')  
                if league_id not in unique_leagues:
                    unique_leagues[league_id] = league
            
            data_list = list(unique_leagues.values())
                
            data['status'], data['data'], data['message'] = status.HTTP_200_OK, data_list, f"Leagues fetched successfully."
        else:
            data['status'], data['data'], data['message'] = status.HTTP_404_NOT_FOUND, [], f"User not found."               
    except Exception as e :
        logger.error(f'Error in get_leagues_list: {str(e)}', exc_info=True)
        data['status'], data['data'], data['message'] = status.HTTP_400_BAD_REQUEST, [], f"{e}"
    return Response(data)


@api_view(("GET",))
def get_final_match_details(request):
    data = {'status':'', 'message':'', 'data':[]}
    try:
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        league_uuid = request.GET.get('league_uuid')
        league_secret_key = request.GET.get('league_secret_key')
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        check_league = Leagues.objects.filter(uuid=league_uuid, secret_key=league_secret_key)
        if check_user and check_league:
            league = check_league.first()
            league_type = league.play_type
            tournaments = Tournament.objects.filter(leagues=league)
            if tournaments:
                if league_type == 'Group Stage' or league_type == 'Single Elimination':
                    final_match = tournaments.filter(match_type='Final').first()
                 
                    serializer = TournamentSerializer(final_match)
                    data['status'] = status.HTTP_200_OK
                    data['message'] = 'Final match data fetched successfully.'
                    data['data'] = serializer.data
                else:
                    data['status'] = status.HTTP_200_OK
                    data['message'] = 'No final match, check tournament details.'
                    data['data'] = serializer.data
            else:
                data['status'] = status.HTTP_404_NOT_FOUND
                data['message'] = 'Matches have not started yet.'
                data['data'] = []
        else:
            data['status'] = status.HTTP_404_NOT_FOUND
            data['message'] = 'User or League not found.'
            data['data'] = []
    except Exception as e:
        logger.error(f'Error in get_final_match_details: {str(e)}', exc_info=True)
        data['status'] = status.HTTP_400_BAD_REQUEST
        data['message'] = f'{str(e)}'
        data['data'] = []
    return Response(data)

@api_view(("GET",))
def home_page_stats_count(request):
    data = {'status':'', 'message':''}
    try:
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if check_user.exists():
            # player_usernames = Player.objects.values_list("player__username", flat=True)

            # # Get users not in players
            # non_player_users = User.objects.exclude(username__in=player_usernames).values_list("username", flat=True)
            # print(non_player_users)
            get_user = check_user.first()
            today_date = datetime.now()
            total_courts = AdvertiserFacility.objects.all().count()
            total_tournaments = Leagues.objects.filter(leagues_start_date__date__lte=today_date,leagues_end_date__date__gte=today_date, is_complete=False).count()

            # total_teams = Team.objects.filter(Q(created_by=get_user) | Q(player__player=get_user)).distinct().count()
            total_teams = Team.objects.all().count()
            total_players = Player.objects.all().count()
            total_clubs_resorts = 0
            total_open_plays = 0
            team_type = LeaguesTeamType.objects.filter(name="Open-team").first()
            player = Player.objects.filter(player_email=get_user.email).first()
            if player:
                teams = player.team.all()
                if teams.exists():                    
                    open_plays = Leagues.objects.filter(registered_team__in=teams, team_type=team_type, is_complete=False).distinct().count()
                    total_open_plays += open_plays

            data["status"] = status.HTTP_200_OK
            data["message"] = "Stats count fetched successfully." 
            data["total_courts"] = total_courts
            data["total_tournaments"] = total_tournaments
            data["total_teams"] = total_teams
            data["total_players"] = total_players
            data["total_open_plays"] = total_open_plays
            data["total_clubs_resorts"] = total_clubs_resorts

    except Exception as e:
        logger.error(f'Error in home_page_stats_count: {str(e)}', exc_info=True)
        data['status'] = status.HTTP_400_BAD_REQUEST
        data['message'] = f'{str(e)}'
       
    return Response(data)

@api_view(["GET"])
def search_players_by_location(request):
    data = {'status': '', 'message': ''}
    
    try:
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        latitude = request.GET.get('latitude', '')
        longitude = request.GET.get('longitude', '')
        radius = float(request.GET.get('radius', 100))
        search_text = request.GET.get('search_text')
        gender = request.GET.get('gender')
        start_rank = request.GET.get('start_rank')
        end_rank = request.GET.get('end_rank')

        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if not check_user.exists():
            return Response({
                "count": 0, "previous": None, "next": None, "data": [], "available_data": [], "available_count":0,
                "status": status.HTTP_401_UNAUTHORIZED, "message": "Unauthorized access"
            })
        
        get_user = check_user.first()
        all_players = []
        available_players = []
        
        players = Player.objects.all()
        
        if search_text not in ['', None, "null"]:
            all_players = [  
                    {'player': player, 'distance_km': None} 
                    for player in players 
                    if search_text.lower() in player.player.first_name.lower() or 
                    search_text.lower() in player.player.last_name.lower()
                ]

            if latitude not in [0, '', None, "null"] and longitude not in [0, '', None, "null"]:
                latitude, longitude = float(latitude), float(longitude)
                
                for p in all_players:
                    # Check that the player's latitude and longitude are valid
                    if p['player'].player.latitude not in ["null", '', None] and p['player'].player.longitude not in ["null", '', None]:
                        distance = haversine(latitude, longitude, float(p['player'].player.latitude), float(p['player'].player.longitude))
                        if distance <= radius:
                            # Append only the player instance with the computed distance
                            available_players.append({'player': p['player'], 'distance_km': distance})
            
        else:            
            if latitude not in [0, '', None, "null"] and longitude not in [0, '', None, "null"]:
                latitude, longitude = float(latitude), float(longitude)
                
                for player in players:
                    if player.player.latitude not in ["null", '', None] and player.player.longitude not in ["null", '', None]:
                        distance = haversine(latitude, longitude, float(player.player.latitude), float(player.player.longitude))
                        if distance <= radius:
                            all_players.append({'player': player, 'distance_km': distance})
                            available_players.append({'player': player, 'distance_km': distance})

        if gender not in [None, "null", "", "None"]:
            if len(all_players) > 0:
                all_players = [p for p in all_players if p['player'].player.gender.lower() == gender.lower()]
            if len(available_players) > 0:
                available_players = [p for p in available_players if p['player'].player.gender.lower() == gender.lower()]
        
        if start_rank not in [None, "null", "", "None"] and end_rank not in [None, "null", "", "None"]:
            start_rank, end_rank = float(start_rank), float(end_rank)
            if len(all_players) > 0:
                all_players = [p for p in all_players if start_rank <= float(p['player'].player.rank) <= end_rank]
            if len(available_players) > 0:
                available_players = [p for p in available_players if start_rank <= float(p['player'].player.rank) <= end_rank]

        
        all_players.sort(key=lambda x: x['distance_km'] if x.get('distance_km') is not None else float('inf'))
        available_players.sort(key=lambda x: x['distance_km'] if x.get('distance_km') is not None else float('inf'))

        following_instance, _ = AmbassadorsDetails.objects.get_or_create(ambassador=get_user)
        following_ids = list(following_instance.following.all().values_list("id", flat=True))

        all_players_serialized = SearchPlayerSerializer(
            [p['player'] for p in all_players], many=True, context={'request': request}
        ).data
        
        available_players_serialized = SearchPlayerSerializer(
            [p['player'] for p in available_players], many=True, context={'request': request}
        ).data

        for p_data in all_players_serialized:            
            p_data["is_follow"] = p_data["id"] in following_ids
        
        for p_data in available_players_serialized:            
            p_data["is_follow"] = p_data["id"] in following_ids

        data.update({
            "status": status.HTTP_200_OK,
            "message": "Data found" if all_players_serialized or available_players_serialized else "No results found",
            "data": all_players_serialized,           
            "count": len(all_players_serialized),
            "available_count": len(available_players_serialized),
            "available_data": available_players_serialized,
        })

    except Exception as e:
        logger.error(f'Error in search player: {str(e)}', exc_info=True)
        data.update({
            "status": status.HTTP_400_BAD_REQUEST,
            "message": str(e),
            "count": 0, "previous": None, "next": None, "data": [], "available_data": [], "available_count":0,
        })

    return Response(data)

@api_view(["GET"])
def search_tournaments_by_location(request):
    data = {'status': '', 'message': '', 'data': []}
    try:
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        latitude = request.GET.get('latitude', '')
        longitude = request.GET.get('longitude', '')
        radius = float(request.GET.get('radius', 100))

        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if not check_user.exists():
            data.update({
                "count": 0,
                "previous": None,
                "next": None,
                "data": [],
                "status": status.HTTP_401_UNAUTHORIZED,
                "message": "Unauthorized access"
            })
            return Response(data)

        today_date = datetime.now()

        live_leagues = Leagues.objects.filter(leagues_start_date__date__lte=today_date, leagues_end_date__date__gte=today_date)
        upcoming_leagues = Leagues.objects.filter(
            Q(registration_start_date__date__lte=today_date, registration_end_date__date__gte=today_date) |
            Q(registration_start_date__date__gte=today_date) |
            Q(registration_end_date__date__lte=today_date, leagues_start_date__date__gte=today_date)
        )

        current_leagues = {}
        for league in live_leagues.union(upcoming_leagues):
            current_leagues[league.id] = league

        nearby_tournaments = []

        if latitude in [0, '', None] or longitude in [0, '', None]:            
            nearby_tournaments = [{'league': league, 'distance_km': None} for league in current_leagues.values()]
        else:            
            latitude = float(latitude)
            longitude = float(longitude)

            for league_id, league in current_leagues.items():
                if league.latitude and league.longitude:
                    distance = haversine(latitude, longitude, float(league.latitude), float(league.longitude))
                    if distance <= radius:
                        nearby_tournaments.append({
                            'league': league, 
                            'distance_km': distance
                        })

        nearby_tournaments.sort(key=lambda x: x['distance_km'] if x['distance_km'] is not None else float('inf'))

        paginator = PageNumberPagination()
        paginator.page_size = 10
        result_page = paginator.paginate_queryset(nearby_tournaments, request)
        response_data = [
            LeagueSerializer(tournament['league']).data  
            for tournament in result_page
        ]

        if not response_data:
            data.update({
                "count": 0,
                "previous": None,
                "next": None,
                "data": [],
                "status": status.HTTP_200_OK,
                "message": "No tournaments found"
            })
        else:
            paginated_response = paginator.get_paginated_response(response_data)
            data.update({
                "status": status.HTTP_200_OK,
                "count": paginated_response.data["count"],
                "previous": paginated_response.data["previous"],
                "next": paginated_response.data["next"],
                "data": paginated_response.data["results"],
                "message": "Tournaments found"
            })

    except Exception as e:
        logger.error(f'Error in search_tournaments_by_location: {str(e)}', exc_info=True)
        data.update({
            "count": 0,
            "previous": None,
            "next": None,
            "data": [],
            "status": status.HTTP_400_BAD_REQUEST,
            "message": str(e)
        })

    return Response(data)


