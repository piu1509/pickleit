from rest_framework import serializers
from apps.team.models import *
from apps.user.models import *
from apps.pickleitcollection.models import *

class TeamSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = '__all__'


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['rank', 'username', 'email', 'first_name', 'last_name', 'uuid', 'secret_key', 'phone', 'image', 'is_ambassador', 'is_sponsor', 'is_organizer', 'is_player', 'gender']



class PlayerSerializer(serializers.ModelSerializer):
    team = TeamSerializer(many=True, read_only=True)
    user = serializers.SerializerMethodField()
    player_ranking = serializers.SerializerMethodField()
    gender = serializers.SerializerMethodField()
    player_image = serializers.SerializerMethodField()
    user_uuid = serializers.SerializerMethodField()
    user_secret_key = serializers.SerializerMethodField()
    player__is_ambassador = serializers.SerializerMethodField()
    player__bio = serializers.SerializerMethodField()
    player_location = serializers.SerializerMethodField()

    class Meta:
        model = Player
        fields = [
            'id', 'uuid', 'secret_key', 'var_team_name', 'var_team_person',
            'player_id', 'player_image', 'player_first_name', 'player_last_name',
            'player_full_name', 'player_email', 'player_phone_number', 'player_ranking', 'player__bio',
            'player_rank_lock', 'identify_player', 'created_at', 'user', 'gender', 'user_uuid',
            'player__is_ambassador', 'user_secret_key', 'team', 'player_location', 'created_by_id'
        ]

    def _get_user(self, obj):
        """Helper method to fetch user once and reuse it."""
        if not hasattr(obj, '_cached_user'):
            obj._cached_user = User.objects.filter(id=obj.player_id).first()
        return obj._cached_user

    def get_user(self, obj):
        user = self._get_user(obj)
        return UserSerializer(user).data if user else []

    def get_player_ranking(self, obj):
        user = self._get_user(obj)
        if not user or not user.rank or user.rank in ["null", "", " "]:
            return 1.0
        try:
            return float(user.rank)
        except (ValueError, TypeError):
            return 1.0  # Fallback to 1.0 if rank is invalid

    def get_gender(self, obj):
        user = self._get_user(obj)
        return user.gender if user and user.gender else "Male"

    def get_player_image(self, obj):
        user = self._get_user(obj)
        if user and hasattr(user, 'image') and user.image and user.image.name not in ["null", None, "", " "]:
            return user.image.name
        return None

    def get_user_uuid(self, obj):
        user = self._get_user(obj)
        return str(user.uuid) if user and user.uuid else None

    def get_user_secret_key(self, obj):
        user = self._get_user(obj)
        return user.secret_key if user and user.secret_key else None

    def get_player__is_ambassador(self, obj):
        user = self._get_user(obj)
        return user.is_ambassador if user and hasattr(user, 'is_ambassador') else False

    def get_player__bio(self, obj):
        user = self._get_user(obj)
        return user.bio if user and hasattr(user, 'bio') else None

    def get_player_location(self, obj):
        user = self._get_user(obj)
        try:
            return user.current_location if user and hasattr(user, 'current_location') else None
        except AttributeError:
            return None


class SearchPlayerSerializer(serializers.ModelSerializer):
    player_ranking = serializers.SerializerMethodField()    
    gender = serializers.SerializerMethodField()    
    player_image = serializers.SerializerMethodField()
    player_location = serializers.SerializerMethodField()
    
    class Meta:
        model = Player
        fields = [
            'id', 'uuid', 'secret_key', 'player_image', 'player_first_name', 'player_last_name', 
            'player_full_name',  'player_ranking', 'gender', 'player_location'
        ]
    def get_player_ranking(self, obj):
        user = User.objects.filter(id=obj.player_id).first()
        if user.rank == "null" or user.rank == "" or not user.rank:
            return 1.0
        else:
            return float(user.rank)

    def get_gender(self, obj):
        user = User.objects.filter(id=obj.player_id).first()
        return user.gender if user.gender else "Male"

    def get_player_image(self, obj):
        print(obj, obj.player)
        if obj.player.image:
            return obj.player.image.name  
        return None
    
    def get_player_location(self, obj):
        location = obj.player.current_location
        return location


class TeamListSerializer(serializers.ModelSerializer):
    created_by = serializers.SerializerMethodField()
    created_by_uuid = serializers.SerializerMethodField()
    created_by_secret_key = serializers.SerializerMethodField()
    player_data = serializers.SerializerMethodField()
    team_rank = serializers.SerializerMethodField()
    team_image = serializers.SerializerMethodField()

    class Meta:
        model = Team
        fields = [
            'id', 'uuid', 'secret_key', 'name', 'team_image','location',
            'team_type', 'team_person', 'created_by', 'created_by_uuid',
            'created_by_secret_key', 'player_data', 'team_rank', 'created_by_id'
        ]

    def get_created_by(self, obj):
        first_name = obj.created_by.first_name if obj.created_by is not None else None
        last_name = obj.created_by.last_name if obj.created_by is not None else None
        return f"{first_name} {last_name}"

    def get_created_by_uuid(self, obj):
        uuid = obj.created_by.uuid if obj.created_by is not None else None
        return uuid

    def get_created_by_secret_key(self, obj):
        secret_key = obj.created_by.secret_key if obj.created_by is not None else None
        return secret_key

    def get_player_data(self, obj):
        players = Player.objects.filter(team=obj).values(
            'uuid', 'secret_key', 'player_full_name', 'player__image', 'player__gender',
            'player_ranking', 'player__rank', 'player__uuid','player_id'
        )
        for player in players:
            player["user_id"] = player["player_id"]
            player['player_ranking'] = float(player['player__rank']) if player['player__rank'] not in ["", "null", None] else 1
            player['player__image'] = player['player__image'] if player['player__image'] not in ["", "null", None] else None
        return list(players)

    def get_team_rank(self, obj):
        players = Player.objects.filter(team=obj)
        if players.exists():
            team_rank = sum(float(player.player.rank) if player.player.rank not in ["", "null", None] else 1 for player in players)
            return team_rank / len(players)
        return 0.0
    
    def get_team_image(self, obj):
        if obj.team_image:
            return obj.team_image.name  
        return None


class LeagueListSerializer(serializers.ModelSerializer):
    leagues_team_type = serializers.SerializerMethodField()
    leagues_pesrson_type = serializers.SerializerMethodField()
    leagues_createdUserBy = serializers.SerializerMethodField()
    registered_team = serializers.SerializerMethodField()
    winner_team = serializers.SerializerMethodField()
    class Meta:
        model = Leagues
        fields = ["id","uuid","secret_key","name","leagues_start_date","leagues_end_date",
                  "image","play_type","leagues_team_type","leagues_pesrson_type","league_type",
                  "location","latitude","longitude","max_number_team","registered_team",
                  "leagues_createdUserBy","winner_team"]
    
    def get_leagues_team_type(self, obj):
        team_type = obj.team_type.name 
        return team_type
    
    def get_leagues_pesrson_type(self, obj):
        team_person = obj.team_person.name 
        return team_person

    def get_leagues_createdUserBy(self, obj):
        created_by_user = f"{obj.created_by.first_name} {obj.created_by.last_name}"
        return created_by_user
    
    def get_registered_team(self, obj):
        teams = obj.registered_team.values_list("name", flat=True) 
        return teams
    
    def get_winner_team(self, obj):
        winner_team = obj.winner_team.name if obj.winner_team else None
        return winner_team





class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id","uuid","secret_key","first_name","last_name"]

class LeagueSerializer(serializers.ModelSerializer):
    leagues_team_type = serializers.SerializerMethodField()
    leagues_pesrson_type = serializers.SerializerMethodField()
    registered_team = TeamSerializer(many=True, read_only=True)
    leagues_createdUserBy = serializers.SerializerMethodField()
    add_organizer = UserSerializer(many=True, read_only=True)
    class Meta:
        model = Leagues
        fields = ["id","uuid","secret_key","name","registration_start_date","registration_end_date","leagues_start_date","leagues_end_date",
                  "image","play_type","leagues_team_type","leagues_pesrson_type","league_type","location","latitude","longitude","street","city","state","postal_code",
                  "country","max_number_team","registered_team","add_organizer","leagues_createdUserBy"]
        
    def get_leagues_team_type(self, obj):
        team_type = obj.team_type.name 
        return team_type
    
    def get_leagues_pesrson_type(self, obj):
        team_person = obj.team_person.name 
        return team_person

    def get_leagues_createdUserBy(self, obj):
        created_by_user = f"{obj.created_by.first_name} {obj.created_by.last_name}"
        return created_by_user

class TeamsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = ["id","name","team_image","team_person","team_type"]

class TournamentSerializer(serializers.ModelSerializer):
    league_name = serializers.SerializerMethodField()
    team1 = TeamsSerializer()
    team2 = TeamsSerializer()
    leagues_location = serializers.SerializerMethodField()
    winner_team = serializers.SerializerMethodField()
    loser_team = serializers.SerializerMethodField()
    team1_score = serializers.SerializerMethodField()
    team2_score = serializers.SerializerMethodField()

    class Meta:
        model = Tournament
        fields = ["league_name","team1","team2","match_number","court_sn","court_num","set_number","winner_team","winner_team_id","loser_team","team1_score","team2_score","playing_date_time","is_drow","leagues_location"]

    def get_league_name(self, obj):
        return obj.leagues.name
    
    def get_leagues_location(self, obj):
        return obj.leagues.location
    
    def get_winner_team(self, obj):
        winner_team = obj.winner_team.id if obj.winner_team else None
        return winner_team
    
    def get_loser_team(self, obj):
        loser_name = obj.loser_team.id if obj.loser_team else None
        return loser_name

    def get_team1_score(self, obj):
        team1_score = []
        check_result = TournamentSetsResult.objects.filter(tournament=obj)
        if check_result:
            get_result = check_result.first()
            team1_score.append(get_result.team1_point)
        return team1_score
    
    def get_team2_score(self, obj):
        team2_score = []
        check_result = TournamentSetsResult.objects.filter(tournament=obj)
        if check_result:
            get_result = check_result.first()
            team2_score.append(get_result.team2_point)
        return team2_score


class MatchListSerializer(serializers.ModelSerializer):
    team1_name = serializers.CharField(source="team1.name", read_only=True)
    team2_name = serializers.CharField(source="team2.name", read_only=True)
    winner_team_name = serializers.CharField(source="winner_team.name", read_only=True)
    event_uuid = serializers.CharField(source="leagues.uuid", read_only=True)
    event_secret_key = serializers.CharField(source="leagues.secret_key", read_only=True)
    class Meta:
        model = Tournament
        fields = ["uuid", "secret_key", "match_number", "event_uuid", "event_secret_key" ,"is_completed", "team1_name", "team2_name", "winner_team_name", "set_number", "is_drow"] 

