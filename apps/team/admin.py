from django.contrib import admin
from apps.team.models import *

admin.site.register(Team)
admin.site.register(Player)
admin.site.register(SaveLeagues)
admin.site.register(PaymentDetailsForRegister)

#Tournament Details(Old)
admin.site.register(LeaguesTeamType)
admin.site.register(LeaguesPesrsonType)
# admin.site.register(Leagues)
# admin.site.register(Tournament)
# admin.site.register(LeaguesPlayType)
# admin.site.register(RoundRobinGroup)
# admin.site.register(TournamentSetsResult)


#Tournament Details(New)
class RoundRobinGroupInline(admin.TabularInline):
    model = RoundRobinGroup
    extra = 0
    verbose_name = "Round Robin Group"
    verbose_name_plural = "Round Robin Groups"
    can_delete = False
    readonly_fields = ('court', 'number_sets', 'all_games_status', 'seleced_teams')

    def has_module_permission(self, request):
        # Check if there are any `RoundRobinGroup` records
        return self.model.objects.exists()


class TournamentInline(admin.TabularInline):
    model = Tournament
    extra = 0
    verbose_name = "Tournament Match"
    verbose_name_plural = "Tournament Matches"
    fields = ('match_number', 'team1', 'team2', 'winner_team', 'is_drow','winner_team_score', 'loser_team_score', 'is_completed', 'set_number','court_num')


class TournamentSetsResultInline(admin.TabularInline):
    model = TournamentSetsResult
    extra = 0
    verbose_name = "Set Result"
    verbose_name_plural = "Set Results"


@admin.register(Leagues)
class LeaguesAdmin(admin.ModelAdmin):
    list_display = ('name', 'play_type', 'team_type', 'leagues_start_date', 'leagues_end_date', 'is_complete')
    list_filter = ('play_type', 'team_type', 'is_complete', 'is_disabled', 'league_type')
    search_fields = ('name', 'city', 'country', 'description')
    readonly_fields = ('uuid', 'created_at', 'updated_at', 'latitude', 'longitude')
    fieldsets = (
        ("Basic Information", {
            "fields": ('uuid','secret_key', 'name', 'description', 'play_type', 'team_type', 'league_type', 'image')
        }),
        ("Date Settings", {
            "fields": (
                'leagues_start_date', 'leagues_end_date',
                'registration_start_date', 'registration_end_date'
            )
        }),
        ("Location", {
            "fields": (
                'location', 'street', 'city', 'state', 'postal_code', 
                'country', 'latitude', 'longitude', 'complete_address'
            )
        }),
        ("Organizers and Teams", {
            "fields": ('add_organizer', 'registered_team', 'max_number_team', 'winner_team')
        }),
        ("Other Settings", {
            "fields": ('registration_fee', 'others_fees', 'is_complete', 'is_disabled', 'any_rank', 'start_rank', 'end_rank')
        }),
        ("Audit", {
            "fields": ('created_at', 'created_by', 'updated_at', 'updated_by')
        }),
    )
    inlines = [TournamentInline]  

    def get_inline_instances(self, request, obj=None):
        """
        Dynamically add `RoundRobinGroupInline` if there are related objects.
        """
        inline_instances = super().get_inline_instances(request, obj)
        
        # Check if `RoundRobinGroup` exists for the given `Leagues` object
        if obj and RoundRobinGroup.objects.filter(league_for=obj).exists():
            inline_instances.append(RoundRobinGroupInline(self.model, self.admin_site))
        
        return inline_instances


@admin.register(Tournament)
class TournamentAdmin(admin.ModelAdmin):
    list_display = ('leagues', 'match_number', 'team1', 'team2', 'winner_team', 'is_completed', 'playing_date_time')
    list_filter = ('is_completed', 'match_type', 'elimination_round')
    search_fields = ('leagues__name', 'team1__name', 'team2__name', 'play_ground_name')
    readonly_fields = ('uuid', 'created_at')
    inlines = [TournamentSetsResultInline]


@admin.register(TournamentSetsResult)
class TournamentSetsResultAdmin(admin.ModelAdmin):
    list_display = ('tournament', 'set_number', 'win_team', 'team1_point', 'team2_point', 'is_completed')
    list_filter = ('is_completed',)
    search_fields = ('tournament__leagues__name', 'win_team__name')


@admin.register(LeaguesPlayType)
class LeaguesPlayTypeAdmin(admin.ModelAdmin):
    list_display = ('league_for', 'type_name')
    list_filter = ('type_name',)
    search_fields = ('league_for__name',)


@admin.register(RoundRobinGroup)
class RoundRobinGroupAdmin(admin.ModelAdmin):
    list_display = ('league_for', 'court', 'number_sets', 'all_games_status')
    list_filter = ('all_games_status',)
    search_fields = ('league_for__name', 'court')
