import requests
import uuid, requests
from phonenumber_field.modelfields import PhoneNumberField

from django.db import models
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone

from apps.user.models import User


def get_address_details(full_address, api_key):
    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={full_address}&key={api_key}"
  
    response = requests.get(url)
    data = response.json()   
   
    if data['status'] == 'OK':
        
        components = data['results'][0]['address_components']
        state = country = pincode = None
        for component in components:
            types = component['types']
            if 'administrative_area_level_1' in types:
                state = component['long_name']
            elif 'country' in types:
                country = component['long_name']
            elif 'postal_code' in types:
                pincode = component['long_name']        
       
        location = data['results'][0]['geometry']['location']
        latitude = location['lat']
        longitude = location['lng']

        return state, country, pincode, latitude, longitude
    else:
        print("Failed to fetch address details. Status:", data['status'])
        return None, None, None, None, None


TEAM_PERSON_STATUS_CHOICES =(
    ("Two Person Team", "Two Person Team"),
    ("One Person Team", "One Person Team"),
)

TEAM_TYPE =(
    ("Women", "Women"),
    ("Men", "Men"),
    ("Co-ed", "Co-ed"),
    ("Open-team", "Open-team"),
)

PLAY_TYPE =(
    ("Group Stage", "Group Stage"),
    ("Round Robin", "Round Robin"),
    ("Single Elimination", "Single Elimination"),
    ("Individual Match Play", "Individual Match Play"),
)

class Team(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4)
    secret_key = models.CharField(max_length=250, unique=True)
    name = models.CharField(max_length=250, null=True, blank=True, unique=True)
    location = models.CharField(max_length=250, null=True, blank=True)
    team_person = models.CharField(choices=TEAM_PERSON_STATUS_CHOICES, max_length=250, null=True, blank=True)
    team_image = models.ImageField(upload_to='team_image/', null=True, blank=True)
    team_type = models.CharField(choices=TEAM_TYPE, max_length=250, null=True, blank=True)
    is_paid = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User,on_delete=models.SET_NULL, null=True, blank=True, related_name='teamCreatedBy')
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User,on_delete=models.SET_NULL, null=True, blank=True, related_name='teamUpdatedBy')
    is_disabled = models.BooleanField(default=False)
    
    def __str__(self) :
        return f"{self.name}, {self.team_person}, {self.team_type}"


class Player(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4)
    secret_key = models.CharField(max_length=250, unique=True)  
    team = models.ManyToManyField(Team, blank=True)
    var_team_name = models.CharField(max_length=250, null=True, blank=True)
    var_team_person = models.CharField(max_length=250, null=True, blank=True)
    player = models.ForeignKey(User,on_delete=models.SET_NULL, null=True, blank=True, related_name='player')
    player_image = models.ImageField(upload_to='player_image/', null=True, blank=True)
    player_first_name = models.CharField(max_length=250, null=True, blank=True)
    player_last_name = models.CharField(max_length=250, null=True, blank=True)
    player_full_name = models.CharField(max_length=250, null=True, blank=True)
    player_email = models.EmailField(max_length=250, null=True, blank=True)
    player_phone_number = models.CharField(max_length=20,null = True, blank = True)
    player_ranking = models.CharField(max_length=255, null=True, blank=True,default="1")
    player_rank_lock = models.BooleanField(default=False)
    identify_player = models.CharField(max_length=250, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User,on_delete=models.SET_NULL, null=True, blank=True, related_name='playerCreatedBy')
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User,on_delete=models.SET_NULL, null=True, blank=True, related_name='playerUpdatedBy')

    def __str__(self) :
        return f"{self.player_full_name}, {self.player_email}, {self.player_phone_number}"


class LeaguesTeamType(models.Model):
    ''' Women // Men // Co-ed '''
    uuid = models.UUIDField(default=uuid.uuid4)
    secret_key = models.CharField(max_length=250, unique=True)
    name = models.CharField(max_length=250, null=True, blank=True)

    def __str__(self) :
        return f"{self.name}"


class LeaguesPesrsonType(models.Model):
    ''' Two Person Team // One Person Team '''
    uuid = models.UUIDField(default=uuid.uuid4)
    secret_key = models.CharField(max_length=250, unique=True)
    name = models.CharField(max_length=250, null=True, blank=True)

    def __str__(self) :
        return f"{self.name}"


LEAGUE_TYPE = (
    ("Invites only", "Invites only"),
    ("Open to all", "Open to all"),
)

class Leagues(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4)
    secret_key = models.CharField(max_length=250, unique=True)
    name = models.CharField(max_length=250, null=True, blank=True)
    leagues_start_date = models.DateTimeField(null=True, blank=True)
    leagues_end_date = models.DateTimeField(null=True, blank=True)
    registration_start_date = models.DateTimeField(null=True, blank=True)
    registration_end_date = models.DateTimeField(null=True, blank=True)
    registration_fee = models.IntegerField(default=5)
    others_fees = models.JSONField(null=True, blank=True)
    image = models.ImageField(upload_to='tournament_image/', null=True, blank=True)
    description = models.TextField(default="Lorem Ipsum has been the industry's standard dummy text ever since the 1500s, when an unknown printer took a galley of type and scrambled it to make a type")
    play_type = models.CharField(max_length=255, choices=PLAY_TYPE, null=True, blank=True)
    # Womens, Mens, Co-ed
    team_type = models.ForeignKey(LeaguesTeamType,on_delete=models.SET_NULL, null=True, blank=True, related_name='leagues_team_type')
    # Two Person Team, Four Person Team
    team_person = models.ForeignKey(LeaguesPesrsonType,on_delete=models.SET_NULL, null=True, blank=True, related_name='leagues_pesrson_type')
    registered_team = models.ManyToManyField(Team, blank=True)
    add_organizer = models.ManyToManyField(User, blank=True)
    max_number_team = models.PositiveIntegerField(default=2)
    # Address
    location = models.TextField(null=True, blank=True,help_text="location")
    street = models.CharField(max_length=255, null=True, blank=True)
    city = models.CharField(max_length=255, null=True, blank=True)
    state = models.CharField(max_length=255, null=True, blank=True)
    postal_code = models.CharField(max_length=20, null=True, blank=True)
    country = models.CharField(max_length=255, null=True, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, default=38.908683)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, default=-76.937352)
    complete_address = models.TextField(null=True, blank=True,help_text="street, city, state, country, PIN-postal_code")
    # Added by
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    created_by = models.ForeignKey(User,on_delete=models.SET_NULL, null=True, blank=True, related_name='leagues_createdUserBy')
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    updated_by = models.ForeignKey(User,on_delete=models.SET_NULL, null=True, blank=True, related_name='leagues_updatedUserBy')
    winner_team = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True, related_name='winner_team_for_all_league')
   
    league_type = models.CharField(choices=LEAGUE_TYPE, max_length=200, null=True, blank=True)
    invited_code = models.CharField(max_length=6,null=True, blank=True)
    is_complete = models.BooleanField(default=False)
    is_disabled = models.BooleanField(default=False)
    is_created = models.BooleanField(default=True)
    any_rank = models.BooleanField(default=True)
    start_rank = models.FloatField(null=True, blank=True)
    end_rank = models.FloatField(null=True, blank=True)

    def __str__(self) :
        return f"{self.name} - {self.team_type}"


    # def save(self, *args, **kwargs):
    #     # Check if any of the address components are not None
    #     if self.street and self.city and self.state and self.postal_code and self.country:
    #         # Concatenate the address components to form the complete_address
    #         self.complete_address = f"{self.street}, {self.city}, {self.state}, {self.country}, PIN-{self.postal_code}"
            
    #     # Use Google Maps Geocoding API to get latitude and longitude
    #     api_key = settings.MAP_API_KEY
    #     try:
    #         # address = f"{self.city}, {self.state}, {self.country}"
    #         # response = requests.get(
    #         #     f"https://nominatim.openstreetmap.org/search?format=json&q={address}"
    #         # )
    #         # result = response.json()
    #         # print("result",result[0]["lat"],"....",result[0]["lon"])
    #         # if response.status_code == 200:
    #         #     self.latitude = result[0]["lat"]
    #         #     self.longitude = result[0]["lon"]
    #         address = self.complete_address
    #         response = requests.get(
    #             f'https://maps.googleapis.com/maps/api/geocode/json?address={address}&key={api_key}'
    #         )
    #         result = response.json()
    #         if response.status_code == 200:
    #             self.latitude = result["results"][0]["geometry"]["location"]["lat"]
    #             self.longitude = result["results"][0]["geometry"]["location"]["lng"]
    #     except :
    #         pass
            
    #     super().save(*args, **kwargs)


def default_json():
    return [
        {
        "name":"Round Robin",
        "number_of_courts":8,
        "sets": 3,
        "point":21
        },
        {
        "name":"Elimination",
        "number_of_courts":4,
        "sets": 3,
        "point":15
        },
        {
        "name":"Final",
        "number_of_courts":1,
        "sets": 3,
        "point":15
        }
        ]


class LeaguesPlayType(models.Model):
    type_name = models.CharField(max_length=255, choices=PLAY_TYPE)
    league_for = models.ForeignKey(Leagues, on_delete=models.CASCADE)
    data = models.JSONField(default=default_json)

    def __str__(self):
        return f"{self.league_for.name}-{self.type_name} || {self.league_for.team_type}"


MATCH_TYPE = (
    ("Group", "Group"),
    ("Quarter Final", "Quarter Final"),
    ("Semi Final", "Semi Final"),
    ("Final", "Final"),
)

class RoundRobinGroup(models.Model):
    court = models.CharField(max_length=255, null=True, blank=True)
    number_sets = models.IntegerField(null=True, blank=True)
    league_for = models.ForeignKey(Leagues, on_delete=models.CASCADE, related_name="league_for")
    all_teams = models.ManyToManyField(Team)
    all_games_status = models.BooleanField(default=False)
    seleced_teams = models.ForeignKey(Team, on_delete=models.CASCADE, null=True, blank=True, related_name="seleced_teams")

    def __str__(self):
        return f"{self.league_for.name}-{self.league_for.team_type}-{self.court}"


class Tournament(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4)
    secret_key = models.CharField(max_length=250, unique=True)
    match_number = models.IntegerField(null=True)
    leagues = models.ForeignKey(Leagues, on_delete=models.SET_NULL, null=True, blank=True, related_name='leagues')
    team1 = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True, related_name='team1')
    team2 = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True, related_name='team2')
    winner_team = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True, related_name='winner_team')
    loser_team = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True, related_name='loser_team')
    winner_team_score = models.CharField(max_length=250, null=True, blank=True)
    loser_team_score = models.CharField(max_length=250, null=True, blank=True)
    play_ground_name = models.CharField(max_length=250, null=True, blank=True)
    playing_date_time = models.DateTimeField(null=True, blank=True)
    match_type = models.CharField(max_length=250, null=True, blank=True)
    elimination_round = models.IntegerField(default=0)
    is_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    group = models.ForeignKey(RoundRobinGroup, on_delete=models.SET_NULL, null=True, blank=True, related_name='group')
    court_sn = models.IntegerField(null=True, blank=True)
    court_real = models.IntegerField(null=True, blank=True)
    is_drow = models.BooleanField(default=False)
    set_number = models.IntegerField(null=True, blank=True)
    court_num = models.IntegerField(null=True, blank=True)
    points = models.IntegerField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if self.is_completed and not self.playing_date_time:
            self.playing_date_time = timezone.now()
        super(Tournament, self).save(*args, **kwargs)
    
    def __str__(self) :        
        return f"{self.leagues.name}|| Match Number {self.match_number}"    


class TournamentSetsResult(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4)
    tournament = models.ForeignKey(Tournament, on_delete=models.SET_NULL, null=True, blank=True, related_name='tournament')
    set_number = models.IntegerField()
    team1_point = models.IntegerField()
    team2_point = models.IntegerField()
    win_team = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True, related_name='win_team')
    is_completed = models.BooleanField(default=False)

    def __str__(self):
        try:
            team_1 = self.tournament.team1.name
        except:
            team_1 = None
        try:
            team_2 = self.tournament.team2.name
        except:
            team_2 = None
        try:
            return_result = f"{self.tournament.leagues.name} ({team_1} VS {team_2}) || Match Number {self.tournament.match_number} || Point {self.team1_point}-{self.team2_point} || win {self.win_team}"
        except Exception as e:
            return_result = str(e)
        return return_result


class TournamentScoreApproval(models.Model):
    tournament = models.OneToOneField(Tournament, on_delete=models.CASCADE, related_name='approved_match')
    team1_approval = models.BooleanField(default=False)
    team2_approval = models.BooleanField(default=False)

    def __str__(self):
        return f'{self.tournament.leagues.name} - {self.tournament.match_number}'


REPORT_CHOICES = (
    ('Pending','Pending'),
    ('Resolved', 'Resolved'),
)

class TournamentScoreReport(models.Model): 
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name='reported_match')
    text = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=REPORT_CHOICES)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reporting_user')

    def __str__(self):
        return f'{self.tournament.leagues.name} - {self.tournament.match_number}'   


class PaymentDetailsForRegister(models.Model):
    tournament = models.ForeignKey('Leagues', related_name='payment_details', on_delete=models.CASCADE)
    payment_for = models.CharField(max_length=255)
    teams_ids = models.JSONField(null=True, blank=True)
    payment_by = models.ForeignKey(User, related_name='payments_made', on_delete=models.CASCADE)
    charge_amount = models.FloatField(null=True)
    payment_status = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.payment_for} | {self.payment_status}"
        

class SaveLeagues(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4)
    secret_key = models.CharField(max_length=250, unique=True)
    ch_league = models.ForeignKey(Leagues, on_delete=models.SET_NULL, null=True, blank=True, related_name='ch_league')
    ch_team = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True, related_name='ch_team')
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    created_by = models.ForeignKey(User,on_delete=models.SET_NULL, null=True, blank=True, related_name='save_turnamenet_user')

    def __str__(self) :
        return f"{self.ch_league.name}"
