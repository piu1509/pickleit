from django.db.models import Q
from django.utils import timezone
from apps.team.models import Leagues, RoundRobinGroup, Tournament, Team, player, LeaguesPlayType
from apps.user.models import User


def getnarate_group_for_group_starge(event, playtype_details, join_teams, court=None, set=None, point=None):
    groups = []
    tournamnets = []
    
    return groups, tournamnets


def getnarate_group_for_round_robin(event, check_group, playtype_details, join_teams):
    groups = []
    tournamnets = []
    return groups, tournamnets


def getnarate_group_for_elimination(event, check_group, playtype_details, join_teams):
    groups = []
    tournamnets = []
    return groups, tournamnets


def getnarate_group_for_indivitual(event, check_group, playtype_details, join_teams):
    groups = []
    tournamnets = []
    return groups, tournamnets
