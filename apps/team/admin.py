from django.contrib import admin
from apps.team.models import *
# Register your models here.

# Inline class to show Players in the Team admin section (optional, kept for editing)
class PlayerInline(admin.TabularInline):
    model = Player.team.through  # Access the intermediate table for ManyToManyField
    extra = 1  # Number of empty rows to display
    verbose_name = "Player"
    verbose_name_plural = "Players"

# Admin class for Team model
@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'team_person', 'team_type', 'get_created_by', 'get_players')
    list_filter = ('is_paid', 'team_type', 'is_disabled')
    search_fields = ('name', 'location')
    inlines = [PlayerInline]  # Optional: Keep this if you want inline editing
    fieldsets = (
        (None, {
            'fields': ('name', 'secret_key', 'uuid', 'location', 'team_person', 'team_type', 'team_image')
        }),
        ('Status', {
            'fields': ('is_paid', 'is_disabled')
        }),
        ('Metadata', {
            'fields': ('created_at', 'created_by', 'updated_at', 'updated_by')
        }),
    )
    readonly_fields = ('uuid', 'created_at', 'updated_at')

    # Custom method to display created_by as "first_name last_name"
    def get_created_by(self, obj):
        if obj.created_by:
            return f"{obj.created_by.first_name} {obj.created_by.last_name}"
        return "Unknown"
    get_created_by.short_description = "Created By"  # Column header in admin list view

    # Custom method to display players in list_display
    def get_players(self, obj):
        players = obj.player_set.all()  # Access all players related to this team
        return ", ".join([player.player_full_name or "Unnamed Player" for player in players])
    get_players.short_description = "Players"  # Column header in admin list view

# Admin class for Player model
@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ('player_full_name', 'player_email', 'player_ranking', 'get_created_by')
    list_filter = ('player_ranking', 'player_rank_lock')
    search_fields = ('player_full_name', 'player_email', 'player_phone_number')
    filter_horizontal = ('team', 'follower', 'following')
    fieldsets = (
        (None, {
            'fields': ('player', 'player_first_name', 'player_last_name', 'player_full_name', 
                       'player_email', 'player_phone_number', 'player_image', 'team')
        }),
        ('Ranking', {
            'fields': ('player_ranking', 'player_rank_lock')
        }),
        ('Social', {
            'fields': ('follower', 'following')
        }),
        ('Metadata', {
            'fields': ('uuid', 'secret_key', 'created_at', 'created_by', 'updated_at', 'updated_by')
        }),
    )
    readonly_fields = ('uuid', 'created_at', 'updated_at')

    # Custom method to display created_by as "first_name last_name"
    def get_created_by(self, obj):
        if obj.created_by:
            return f"{obj.created_by.first_name} {obj.created_by.last_name}"
        return "Unknown"
    get_created_by.short_description = "Created By"  # Column header in admin list view

    
admin.site.register(PaymentDetailsForRegister)
admin.site.register(LeaguesCancellationPolicy)

@admin.register(SaveLeagues)
class SaveLeaguesAdmin(admin.ModelAdmin):
    list_display = ("get_league_name", "get_team_name", "created_by", "created_at")
    search_fields = ("ch_league__name", "ch_team__name", "created_by__username")
    list_filter = ("ch_league", "created_by")
    readonly_fields = ("uuid", "secret_key", "ch_league", "ch_team", "created_at", "created_by")
    ordering = ("-created_at",)

    def get_league_name(self, obj):
        return obj.ch_league.name if obj.ch_league else "-"

    def get_team_name(self, obj):
        return obj.ch_team.name if obj.ch_team else "-"

    get_league_name.short_description = "League Name"
    get_team_name.short_description = "Team Name"

class LeaguesCancellationPolicyInline(admin.TabularInline):
    model = LeaguesCancellationPolicy
    extra = 0  # Allows adding a new row inline

class LeaguesPlayTypeInline(admin.TabularInline):
    model = LeaguesPlayType
    extra = 0

class TournamentInline(admin.TabularInline):
    model = Tournament
    extra = 0  # Prevent extra empty rows
    fields = ("match_number", "get_team1_name", "get_team2_name", "get_team1_scores",  "get_team2_scores", "is_completed")
    readonly_fields = ("match_number", "get_team1_name", "get_team2_name", "get_team1_scores",  "get_team2_scores", "is_completed")  
    can_delete = False  # Prevent deletion
    max_num = 0  # Prevent adding new tournaments

    def get_team1_name(self, obj):
        """Return team1 name"""
        return obj.team1.name if obj.team1 else "-"

    def get_team2_name(self, obj):
        """Return team2 name"""
        return obj.team2.name if obj.team2 else "-"

    def get_team1_scores(self, obj):
        """Fetch all set scores for team1 as a comma-separated string"""
        scores = TournamentSetsResult.objects.filter(tournament=obj).values_list('team1_point', flat=True)
        return ", ".join(map(str, scores)) if scores else "0"

    def get_team2_scores(self, obj):
        """Fetch all set scores for team2 as a comma-separated string"""
        scores = TournamentSetsResult.objects.filter(tournament=obj).values_list('team2_point', flat=True)
        return ", ".join(map(str, scores)) if scores else "0"

    get_team1_name.short_description = "Team 1"
    get_team2_name.short_description = "Team 2"
    get_team1_scores.short_description = "Team 1 Scores"
    get_team2_scores.short_description = "Team 2 Scores"


@admin.register(Leagues)
class LeaguesAdmin(admin.ModelAdmin):
    list_display = ("name", "team_type", "league_type", "leagues_start_date", "leagues_end_date", "is_complete")
    search_fields = ("name", "team_type__name", "league_type")
    list_filter = ("league_type", "is_complete", "is_disabled", "is_created")
    readonly_fields = ("created_at", "updated_at")
    inlines = [LeaguesCancellationPolicyInline, LeaguesPlayTypeInline, TournamentInline]


class TournamentSetsResultInline(admin.TabularInline):
    model = TournamentSetsResult
    extra = 0
    fields = ("set_number", "is_completed", "team1_point", "team2_point", "win_team")

@admin.register(Tournament)
class TournamentAdmin(admin.ModelAdmin):
    list_display = ("leagues", "match_number", "court_num", "get_team1_name", "get_team2_name", "get_winner_team_name", "is_completed")
    search_fields = ("leagues__name", "team1__name", "team2__name", "winner_team__name")
    list_filter = ("is_completed", "match_type", "elimination_round", "leagues")
    readonly_fields = ("created_at", "playing_date_time")
    ordering = ("-playing_date_time",)
    inlines = [TournamentSetsResultInline]

    def get_team1_name(self, obj):
        return obj.team1.name if obj.team1 else "-"

    def get_team2_name(self, obj):
        return obj.team2.name if obj.team2 else "-"

    def get_winner_team_name(self, obj):
        return obj.winner_team.name if obj.winner_team else "-"

    get_team1_name.short_description = "Team 1"
    get_team2_name.short_description = "Team 2"
    get_winner_team_name.short_description = "Winner"

    # def save_related(self, request, form, formsets, change):
    #     """Override to update Tournament when all sets are completed."""
    #     super().save_related(request, form, formsets, change)
    #     obj = form.instance  # The Tournament instance

    #     # Check if all sets are completed
    #     sets = obj.tournament.all()  # Using related_name 'tournament'
    #     if sets.exists() and all(set_result.is_completed for set_result in sets):
    #          # Check if all sets are completed
    #         # Calculate total points for each team
    #         team1_total = sum(set_result.team1_point for set_result in sets)
    #         team2_total = sum(set_result.team2_point for set_result in sets)

    #         # Determine winner and loser
    #         if team1_total > team2_total:
    #             obj.winner_team = obj.team1
    #             obj.loser_team = obj.team2
    #         elif team2_total > team1_total:
    #             obj.winner_team = obj.team2
    #             obj.loser_team = obj.team1
    #         else:
    #             obj.is_drow = True  # Handle tie case if applicable

    #         # Update scores
    #         obj.winner_team_score = str(max(team1_total, team2_total))
    #         obj.loser_team_score = str(min(team1_total, team2_total))

    #         # Mark tournament as completed
    #         obj.is_completed = True
    #         if not obj.playing_date_time:
    #             obj.playing_date_time = timezone.now()
    #         obj.save()


@admin.register(TournamentSetsResult)
class TournamentSetsResultAdmin(admin.ModelAdmin):
    list_display = ("tournament", "set_number", "win_team", "team1_point", "team2_point", "is_completed")
    search_fields = ("tournament__leagues__name", "win_team__name")
    list_filter = ("is_completed","tournament")
    ordering = ("-set_number",)


@admin.register(RoundRobinGroup)
class RoundRobinGroupAdmin(admin.ModelAdmin):
    list_display = ("league_for", "court", "number_sets", "all_games_status")
    search_fields = ("league_for__name",)
    list_filter = ("all_games_status",)
    inlines = [TournamentInline]


@admin.register(LeaguesTeamType)
class LeaguesTeamTypeAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(LeaguesPesrsonType)
class LeaguesPesrsonTypeAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)






# @admin.register(Tournament)
# class TournamentAdmin(admin.ModelAdmin):
#     list_display = ('leagues', 'match_number', 'team1', 'team2', 'winner_team', 'is_completed', 'playing_date_time')
#     list_filter = ('is_completed', 'match_type', 'elimination_round')
#     search_fields = ('leagues__name', 'team1__name', 'team2__name', 'play_ground_name')
#     readonly_fields = ('uuid', 'created_at')
#     inlines = [TournamentSetsResultInline]

# @admin.register(TournamentSetsResult)
# class TournamentSetsResultAdmin(admin.ModelAdmin):
#     list_display = ('tournament', 'set_number', 'win_team', 'team1_point', 'team2_point', 'is_completed')
#     list_filter = ('is_completed',)
#     search_fields = ('tournament__leagues__name', 'win_team__name')

# @admin.register(LeaguesPlayType)
# class LeaguesPlayTypeAdmin(admin.ModelAdmin):
#     list_display = ('league_for', 'type_name')
#     list_filter = ('type_name',)
#     search_fields = ('league_for__name',)

# @admin.register(RoundRobinGroup)
# class RoundRobinGroupAdmin(admin.ModelAdmin):
#     list_display = ('league_for', 'court', 'number_sets', 'all_games_status')
#     list_filter = ('all_games_status',)
#     search_fields = ('league_for__name', 'court')

admin.site.register(TournamentScoreApproval)
admin.site.register(TournamentScoreReport)



@admin.register(OpenPlayInvitation)
class OpenPlayInvitationAdmin(admin.ModelAdmin):
    # Fields to display in the list view
    list_display = ('user', 'event', 'invited_by', 'status', 'created_at')

    # Fields to search
    search_fields = (
        'user__first_name', 'user__last_name', 'user__email',
        'invited_by__first_name', 'invited_by__last_name', 'invited_by__email',
        'event__name', 'status'
    )

    # Filters for the sidebar
    list_filter = ('status', 'created_at', 'user', 'invited_by')

    # Optional: Customize how ForeignKey fields are displayed
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'event', 'invited_by')

    # Optional: Display user names instead of object IDs
    def user(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}"
    user.admin_order_field = 'user__first_name'  # Enable sorting by first name

    def invited_by(self, obj):
        return f"{obj.invited_by.first_name} {obj.invited_by.last_name}"
    invited_by.admin_order_field = 'invited_by__first_name'  # Enable sorting by first name

    def event(self, obj):
        return obj.event.name
    event.admin_order_field = 'event__name'  # Enable sorting by event name
    
